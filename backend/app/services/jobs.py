from __future__ import annotations

import asyncio
import csv
import json
import math
import random
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import engine
from app.core.storage import job_dir, log_path, zip_paths
from app.models.domain import DatasetFile, Job, JobCreate, JobLog, ResultTable, Workflow
from app.services.engines import detect_engines
from app.services.parsers import normalize_feature_records, parse_table
from app.services.workflows import WORKFLOW_PRESETS

TASKS: dict[int, asyncio.Task] = {}


def append_log(session: Session, job: Job, message: str, level: str = "info") -> None:
    session.add(JobLog(job_id=job.id, level=level, message=message))
    log_path(job.id).open("a", encoding="utf-8").write(f"{datetime.utcnow().isoformat()}Z [{level}] {message}\n")
    session.commit()


def validate_job_create(session: Session, payload: JobCreate) -> None:
    if not session.get(Job, payload.project_id) and not session.exec(select(DatasetFile).where(DatasetFile.project_id == payload.project_id)).all():
        # Project existence is checked in the route; this keeps the service focused on workflow defaults.
        pass
    if payload.workflow_id and not session.get(Workflow, payload.workflow_id):
        raise ValueError("Workflow not found")


def create_job(session: Session, payload: JobCreate) -> Job:
    workflow_id = payload.workflow_id
    if workflow_id is None:
        preset = WORKFLOW_PRESETS[0]
        workflow = Workflow(
            project_id=payload.project_id,
            name=preset["name"],
            engine="pipeline",
            preset_key=preset["id"],
            parameters=preset["parameters"],
        )
        session.add(workflow)
        session.commit()
        session.refresh(workflow)
        workflow_id = workflow.id

    command_args = ["mock-runner", "--job-type", payload.job_type] if settings.mock_execution else ["external-runner"]
    job = Job(
        project_id=payload.project_id,
        workflow_id=workflow_id,
        name=payload.name,
        job_type=payload.job_type,
        status="queued",
        progress=0,
        stage="queued",
        parameters=payload.parameters,
        command_args=command_args,
        software_versions=detect_engines(),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    append_log(session, job, "Job queued")
    if settings.mock_execution:
        try:
            loop = asyncio.get_running_loop()
            TASKS[job.id] = loop.create_task(run_mock_job(job.id))
        except RuntimeError:
            run_mock_job_sync(job.id)
    return job


def run_mock_job_sync(job_id: int) -> None:
    asyncio.run(run_mock_job(job_id))


async def run_mock_job(job_id: int) -> None:
    stages = [
        ("validating input", "Validated uploads, sample metadata, and workflow parameters", 10),
        ("running MZmine", "Mock MZmine batch execution using preserved .mzbatch-compatible parameters", 28),
        ("exporting MZmine results", "Exported mock feature table, MGF, and quant summaries", 43),
        ("running SIRIUS", "Generated mock SIRIUS formula, CSI:FingerID, ZODIAC, and CANOPUS annotations", 58),
        ("running ML-MS/MS scoring", "Scored spectra with mock matchms, MS2DeepScore, MS2Query, and DREAMS outputs", 72),
        ("running statistics", "Computed mock PCA, volcano, heatmap, and two-group statistics", 86),
        ("generating report", "Wrote HTML report and downloadable ZIP artifacts", 95),
    ]
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if not job:
            return
        job.status = "running"
        job.started_at = datetime.utcnow()
        session.add(job)
        append_log(session, job, "Mock LC-MS/MS workflow started")

    try:
        for stage, message, progress in stages:
            await asyncio.sleep(settings.mock_job_step_seconds)
            with Session(engine) as session:
                job = session.get(Job, job_id)
                if not job or job.status == "canceled":
                    return
                job.stage = stage
                job.progress = progress
                session.add(job)
                append_log(session, job, message)
        write_mock_results(job_id)
        with Session(engine) as session:
            job = session.get(Job, job_id)
            if not job:
                return
            job.status = "complete"
            job.stage = "complete"
            job.progress = 100
            job.completed_at = datetime.utcnow()
            session.add(job)
            append_log(session, job, "Mock LC-MS/MS workflow complete")
    except Exception as exc:  # pragma: no cover
        with Session(engine) as session:
            job = session.get(Job, job_id)
            if job:
                job.status = "failed"
                job.stage = "failed"
                job.error_message = str(exc)
                session.add(job)
                append_log(session, job, f"Job failed: {exc}", "error")


def write_mock_results(job_id: int) -> None:
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if not job:
            return
        features = _load_feature_upload(session, job.project_id) or _generate_features()
        annotations = [_annotation(row, idx) for idx, row in enumerate(features, start=1)]
        statistics = [_statistics(row, idx) for idx, row in enumerate(features, start=1)]
        plots = _plot_payload(features, statistics)
        tables = [
            ResultTable(job_id=job.id, result_type="features", columns=_columns(features), rows=features),
            ResultTable(job_id=job.id, result_type="annotations", columns=_columns(annotations), rows=annotations),
            ResultTable(job_id=job.id, result_type="statistics", columns=_columns(statistics), rows=statistics),
            ResultTable(job_id=job.id, result_type="plots", columns=["plot", "payload"], rows=[plots]),
            ResultTable(job_id=job.id, result_type="network", columns=["nodes", "edges"], rows=[_network(annotations)]),
        ]
        for table in tables:
            session.add(table)
        session.commit()
        _write_artifacts(job, features, annotations, statistics, plots)


def _load_feature_upload(session: Session, project_id: int) -> list[dict[str, Any]] | None:
    for dataset_file in session.exec(select(DatasetFile).where(DatasetFile.project_id == project_id)).all():
        if dataset_file.file_type in {"csv", "tsv", "mztab"}:
            rows, _warnings = parse_table(Path(dataset_file.path), max_rows=500)
            if rows:
                normalized = normalize_feature_records(rows)
                return [
                    {
                        **row.get("original", {}),
                        "feature_id": row.get("feature_id", str(idx)),
                        "mz": _num(row.get("mz"), 100 + idx),
                        "rt": _num(row.get("rt"), idx / 10),
                        "intensity": _num(row.get("intensity"), 500000 + idx * 1000),
                    }
                    for idx, row in enumerate(normalized, start=1)
                ]
    return None


def _generate_features() -> list[dict[str, Any]]:
    rng = random.Random(42)
    rows = []
    for idx in range(1, 121):
        control = rng.uniform(2e5, 1.4e6)
        fold = rng.uniform(0.3, 3.4)
        treated = control * fold
        rows.append(
            {
                "feature_id": f"F{idx:04d}",
                "mz": round(95 + idx * 3.77 + rng.random(), 5),
                "rt": round(0.25 + idx * 0.09 + rng.random() * 0.15, 3),
                "ion_mode": "positive" if idx % 2 else "negative",
                "sample_control_mean": round(control, 2),
                "sample_treated_mean": round(treated, 2),
                "intensity": round((control + treated) / 2, 2),
                "missing_rate": round(rng.uniform(0, 0.28), 3),
            }
        )
    return rows


def _annotation(row: dict[str, Any], idx: int) -> dict[str, Any]:
    sirius = max(0.2, 0.97 - (idx % 17) * 0.035)
    cosine = max(0.18, 0.93 - (idx % 13) * 0.04)
    ml = max(0.15, 0.9 - (idx % 11) * 0.045)
    combined = round(0.4 * sirius + 0.25 * cosine + 0.2 * ml + 0.15 * max(0, 1 - abs(idx % 9 - 4) / 12), 4)
    return {
        "feature_id": row.get("feature_id", f"F{idx:04d}"),
        "mz": _num(row.get("mz"), 0),
        "rt": _num(row.get("rt"), 0),
        "ion_mode": row.get("ion_mode", "positive"),
        "adduct": "[M+H]+" if idx % 2 else "[M-H]-",
        "charge": 1,
        "formula": f"C{9 + idx % 30}H{14 + idx % 46}O{2 + idx % 10}",
        "candidate_name": f"Mock metabolite {idx}",
        "smiles": "CC(=O)O",
        "inchikey": f"MOCKINCHIKEY{idx:04d}",
        "compound_class": ["lipid", "alkaloid", "phenylpropanoid", "organic acid", "terpenoid"][idx % 5],
        "mzmine_library_score": round(cosine - 0.04, 4),
        "sirius_formula_score": round(sirius, 4),
        "sirius_structure_score": round(sirius - 0.05, 4),
        "csi_score": round(sirius - 0.08, 4),
        "canopus_class": ["Fatty acyls", "Flavonoids", "Terpenoids", "Benzenoids", "Organic acids"][idx % 5],
        "canopus_probability": round(min(0.99, sirius + 0.01), 4),
        "zodiac_score": round(sirius - 0.1, 4),
        "dreams_score": round(ml - 0.02, 4),
        "ms2deepscore": round(ml, 4),
        "ms2query_score": round(ml - 0.035, 4),
        "matchms_cosine": round(cosine, 4),
        "matched_peaks": 7 + idx % 18,
        "precursor_ppm_error": round((idx % 9 - 4) * 1.4, 3),
        "annotation_source": "mock_consensus",
        "combined_rank": idx,
        "confidence_level": "high" if combined >= 0.82 else "medium" if combined >= 0.62 else "low",
        "consensus_score": combined,
    }


def _statistics(row: dict[str, Any], idx: int) -> dict[str, Any]:
    control = _num(row.get("sample_control_mean") or row.get("control") or row.get("intensity"), 1)
    treated = _num(row.get("sample_treated_mean") or row.get("treated"), control * (1 + (idx % 6) / 10))
    fold = treated / control if control else 0
    log2fc = math.log(fold, 2) if fold > 0 else 0
    p_value = min(0.99, max(0.0002, abs(math.sin(idx * 0.71)) / 8))
    return {
        "feature_id": row.get("feature_id", f"F{idx:04d}"),
        "mz": _num(row.get("mz"), 0),
        "rt": _num(row.get("rt"), 0),
        "annotation": f"Mock metabolite {idx}",
        "formula": f"C{9 + idx % 30}H{14 + idx % 46}O{2 + idx % 10}",
        "class": ["lipid", "alkaloid", "phenylpropanoid", "organic acid"][idx % 4],
        "group_1_mean": round(control, 3),
        "group_2_mean": round(treated, 3),
        "group_1_median": round(control * 0.97, 3),
        "group_2_median": round(treated * 0.97, 3),
        "log2_fold_change": round(log2fc, 4),
        "fold_change": round(fold, 4),
        "test_name": "Welch t-test (mock)",
        "statistic": round(log2fc * 2.3, 4),
        "p_value": round(p_value, 6),
        "adjusted_p_value": round(min(1.0, p_value * 1.7), 6),
        "q_value": round(min(1.0, p_value * 1.7), 6),
        "effect_size": round(log2fc / 1.25, 4),
        "detection_frequency_group_1": round(0.74 + (idx % 8) * 0.03, 3),
        "detection_frequency_group_2": round(0.72 + (idx % 7) * 0.035, 3),
    }


def _plot_payload(features: list[dict[str, Any]], statistics: list[dict[str, Any]]) -> dict[str, Any]:
    xs = [_num(row.get("mz"), 0) for row in features[:80]]
    ys = [_num(row.get("rt"), 0) for row in features[:80]]
    return {
        "pca": {
            "x": [round(math.cos(i / 7) * 4 + i / 80, 3) for i in range(40)],
            "y": [round(math.sin(i / 6) * 3, 3) for i in range(40)],
            "group": ["control" if i < 20 else "treated" for i in range(40)],
        },
        "volcano": {
            "x": [_num(row.get("log2_fold_change"), 0) for row in statistics],
            "y": [round(-math.log10(max(_num(row.get("adjusted_p_value"), 1), 1e-8)), 4) for row in statistics],
        },
        "heatmap": {
            "z": [[round(math.sin((r + 1) * (c + 2) / 5), 3) for c in range(12)] for r in range(25)],
            "x": [f"S{idx}" for idx in range(1, 13)],
            "y": [row.get("feature_id", str(i)) for i, row in enumerate(features[:25], start=1)],
        },
        "rt_mz": {"x": xs, "y": ys},
    }


def _network(annotations: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = [
        {"data": {"id": row["feature_id"], "label": row["candidate_name"], "class": row["compound_class"], "score": row["consensus_score"]}}
        for row in annotations[:35]
    ]
    edges = [
        {"data": {"id": f"e{i}", "source": nodes[i]["data"]["id"], "target": nodes[(i + 3) % len(nodes)]["data"]["id"], "score": round(0.58 + (i % 7) * 0.05, 3)}}
        for i in range(len(nodes))
    ]
    return {"nodes": nodes, "edges": edges}


def _write_artifacts(job: Job, features: list[dict[str, Any]], annotations: list[dict[str, Any]], statistics: list[dict[str, Any]], plots: dict[str, Any]) -> None:
    directory = job_dir(job.id)
    _write_csv(directory / "features.csv", features)
    _write_csv(directory / "annotations.csv", annotations)
    _write_csv(directory / "statistics.csv", statistics)
    (directory / "plots.json").write_text(json.dumps(plots, indent=2), encoding="utf-8")
    (directory / "workflow_parameters.json").write_text(json.dumps(job.parameters, indent=2), encoding="utf-8")
    (directory / "software_versions.json").write_text(json.dumps(job.software_versions, indent=2), encoding="utf-8")
    (directory / "report.html").write_text(
        f"""<!doctype html><html><head><meta charset=\"utf-8\"><title>FragmentIQ Job {job.id}</title>
<style>body{{font-family:Inter,Arial,sans-serif;margin:2rem;color:#111827}}.card{{border:1px solid #e5e7eb;border-radius:12px;padding:1rem;margin:1rem 0}}</style></head>
<body><h1>FragmentIQ Mock Analysis Report</h1><div class=\"card\">Job {job.id}: {len(features)} features, {len(annotations)} annotations, {len(statistics)} statistics rows.</div>
<p>Mock mode preserves the same result contract used by real MZmine, SIRIUS, ML-MS/MS, statistics, and reporting workers.</p></body></html>""",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = _columns(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    return list(dict.fromkeys(key for row in rows for key in row.keys()))


def _num(value: Any, default: float) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def result_rows(job_id: int, result_type: str) -> list[dict[str, Any]]:
    with Session(engine) as session:
        result = session.exec(select(ResultTable).where(ResultTable.job_id == job_id, ResultTable.result_type == result_type)).first()
        return result.rows if result else []


def retry_job(session: Session, job_id: int) -> Job:
    old_job = session.get(Job, job_id)
    if not old_job:
        raise ValueError("Job not found")
    return create_job(
        session,
        JobCreate(
            project_id=old_job.project_id,
            workflow_id=old_job.workflow_id,
            name=f"Retry of {old_job.name}",
            job_type=old_job.job_type,
            parameters=old_job.parameters,
        ),
    )


async def event_stream(job_id: int):
    last_progress = -1
    while True:
        with Session(engine) as session:
            job = session.get(Job, job_id)
            if not job:
                yield "event: error\ndata: Job not found\n\n"
                return
            if job.progress != last_progress:
                yield f"data: {json.dumps({'status': job.status, 'stage': job.stage, 'progress': job.progress})}\n\n"
                last_progress = job.progress
            if job.status in {"complete", "failed", "canceled"}:
                return
        await asyncio.sleep(1)


def build_results_zip(job: Job) -> Path:
    directory = job_dir(job.id)
    if not any(directory.iterdir()):
        write_mock_results(job.id)
    output = settings.results_dir / f"job_{job.id}.zip"
    if output.exists():
        output.unlink()
    return zip_paths([directory, log_path(job.id)], output)
