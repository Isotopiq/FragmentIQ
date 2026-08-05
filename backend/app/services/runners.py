from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from sqlmodel import Session, select

from app.core.config import settings
from app.core.storage import job_dir, safe_child
from app.models.domain import DatasetFile, Job, LibraryAsset, MetadataTable, ModelAsset, ResultTable, Workflow
from app.services.parsers import parse_mzmine_outputs, parse_sirius_outputs


class RunnerConfigurationError(ValueError):
    """Raised when a submitted real-engine job cannot be represented safely."""


@dataclass(frozen=True)
class EngineCommand:
    engine: str
    args: list[str]
    cwd: Path
    stdout_path: Path
    stderr_path: Path


@dataclass(frozen=True)
class PythonEngineStep:
    name: str
    run: Callable[["RealRunContext", Path], dict[str, list[dict[str, Any]]]]


@dataclass(frozen=True)
class RealRunContext:
    job: Job
    workflow: Workflow
    files: list[DatasetFile]
    libraries: list[LibraryAsset] = field(default_factory=list)
    metadata: MetadataTable | None = None
    models: dict[str, ModelAsset | None] = field(default_factory=dict)


class ExternalToolError(RuntimeError):
    """Raised when an external engine exits unsuccessfully."""


def resolve_executable(configured_binary: str) -> str:
    resolved = shutil.which(configured_binary)
    if not resolved:
        raise RunnerConfigurationError(f"Executable is not installed or not on PATH: {configured_binary}")
    return resolved


def project_files(session: Session, project_id: int, kinds: set[str] | None = None) -> list[DatasetFile]:
    statement = select(DatasetFile).where(DatasetFile.project_id == project_id)
    files = list(session.exec(statement).all())
    if kinds:
        files = [item for item in files if item.file_type.lower() in {kind.lower() for kind in kinds}]
    return files


def validate_project_file(session: Session, project_id: int, file_id: int, kinds: set[str] | None = None) -> DatasetFile:
    item = session.get(DatasetFile, file_id)
    if not item or item.project_id != project_id:
        raise RunnerConfigurationError("Selected input file does not belong to this project.")
    if kinds and item.file_type.lower() not in {kind.lower() for kind in kinds}:
        raise RunnerConfigurationError(f"File {item.original_name} is not a supported input type for this engine.")
    return item


def selected_input_paths(ctx: RealRunContext, kinds: set[str] | None = None) -> list[Path]:
    """Return the workflow/Job selected input files, or all project files of the requested kinds."""
    file_ids = ctx.job.input_file_ids or (ctx.workflow.input_file_ids if ctx.workflow else [])
    if file_ids:
        selected = [f for f in ctx.files if f.id in file_ids]
    else:
        selected = ctx.files
    if kinds:
        selected = [f for f in selected if f.file_type.lower() in {k.lower() for k in kinds}]
    return [Path(f.path) for f in selected]


def selected_libraries(ctx: RealRunContext) -> list[LibraryAsset]:
    lib_ids = ctx.job.library_ids or (ctx.workflow.library_ids if ctx.workflow else [])
    if not lib_ids:
        return ctx.libraries
    return [lib for lib in ctx.libraries if lib.id in lib_ids]


def resolve_model(session: Session, engine: str, model_id: int | None) -> ModelAsset | None:
    if model_id:
        return session.get(ModelAsset, model_id)
    return session.exec(select(ModelAsset).where(ModelAsset.engine == engine, ModelAsset.is_default == True)).first()


def build_mzmine_command(session: Session, job: Job, workflow: Workflow | None, run_dir: Path) -> EngineCommand:
    from app.services.mzmine_batch import get_mzmine_batch_for_workflow

    executable = resolve_executable(settings.mzmine_binary)
    raw_files = [Path(f.path) for f in project_files(session, job.project_id, {"mzML", "mzXML", "imzML"})]
    if not raw_files:
        raise RunnerConfigurationError("MZmine requires at least one uploaded mzML/mzXML/imzML file.")

    mzbatch_path = get_mzmine_batch_for_workflow(workflow, raw_files, run_dir)
    args = [executable, settings.mzmine_batch_flag, str(mzbatch_path)]
    if workflow and workflow.parameters.get("use_cli_input"):
        args.extend(["-input", ",".join(str(p) for p in raw_files)])
    args.extend([
        "-memory", settings.mzmine_memory_mode,
        "-temp", str(settings.mzmine_temp_dir),
        "-output", str(run_dir / "mzmine_out"),
    ])
    return EngineCommand("mzmine", args, run_dir, run_dir / "mzmine.stdout.log", run_dir / "mzmine.stderr.log")


def build_sirius_command(session: Session, job: Job, run_dir: Path) -> EngineCommand:
    executable = resolve_executable(settings.sirius_binary)
    params = job.parameters or {}
    input_file_id = params.get("sirius_input_file_id") or params.get("input_file_id")
    if input_file_id:
        item = validate_project_file(session, job.project_id, int(input_file_id), {"MGF", "MSP", "mzML", "mzXML"})
    else:
        candidates = project_files(session, job.project_id, {"MGF", "MSP"})
        if not candidates:
            raise RunnerConfigurationError("SIRIUS execution requires an uploaded MGF/MSP file or a selected input file.")
        item = candidates[0]

    output_dir = run_dir / "sirius"
    output_dir.mkdir(parents=True, exist_ok=True)
    args = [executable, "--output", str(output_dir)]
    if params.get("ion_mode"):
        args.extend(["--ion-mode", str(params["ion_mode"])])
    if params.get("adduct"):
        args.extend(["--adduct", str(params["adduct"])])
    if params.get("precursor_mass_tolerance"):
        args.extend(["--ppm-max", str(params["precursor_mass_tolerance"])])
    if params.get("enable_zodiac"):
        args.append("zodiac")
    if params.get("enable_canopus"):
        args.append("canopus")
    args.append(str(Path(item.path)))
    return EngineCommand("sirius", args, run_dir, run_dir / "sirius.stdout.log", run_dir / "sirius.stderr.log")


def _normalized_library_mgf(library: LibraryAsset) -> Path:
    from app.services.spectral_libraries import ensure_normalized_mgf
    cache_dir = Path("./data/libraries/.cache")
    return ensure_normalized_mgf(Path(library.path), cache_dir)


def run_sirius_api_step(ctx: RealRunContext, run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    from app.services.sirius_api import SiriusApiClient

    sirius_path = resolve_executable(settings.sirius_binary)
    input_paths = selected_input_paths(ctx, {"MGF", "MSP", "mzML", "mzXML"})
    if not input_paths:
        raise RunnerConfigurationError("SIRIUS API requires an uploaded MGF/MSP/mzML/mzXML file.")
    with SiriusApiClient(
        sirius_path=sirius_path,
        username=settings.sirius_username,
        password=settings.sirius_password,
        url=settings.sirius_api_url or None,
        accept_terms=settings.sirius_accept_terms,
    ) as client:
        project_id = f"fragmentiq_job_{ctx.job.id}"
        input_type = "ms_run" if input_paths[0].suffix.lower() in {".mzml", ".mzxml"} else "preprocessed"
        client.import_input(project_id, input_paths, input_type=input_type)
        for lib in selected_libraries(ctx):
            client.create_custom_spectral_database(f"lib_{lib.id}", _normalized_library_mgf(lib))
        client.run_identification(project_id, include_custom_dbs=bool(selected_libraries(ctx)))
        annotations = client.get_annotations(project_id)
    return {"annotations": annotations}


def run_ms2query_step(ctx: RealRunContext, run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    from app.services.ms2query_runner import Ms2QueryRunner

    query_paths = selected_input_paths(ctx, {"MGF", "MSP"})
    if not query_paths:
        raise RunnerConfigurationError("MS2Query requires an uploaded MGF/MSP query file.")
    libs = selected_libraries(ctx)
    if libs:
        library_dir = _normalized_library_mgf(libs[0]).parent
    else:
        library_dir = settings.ms2query_library_dir
    params = ctx.job.parameters or ctx.workflow.parameters or {}
    runner = Ms2QueryRunner(library_dir=library_dir, ion_mode=params.get("ion_mode", "positive"))
    query_dir = run_dir / "ms2query_input"
    query_dir.mkdir(parents=True, exist_ok=True)
    for p in query_paths:
        shutil.copy(p, query_dir / p.name)
    results_dir = runner.search(query_dir, run_dir / "ms2query_results")
    # Find first CSV result
    result_csv = next((p for p in results_dir.rglob("*.csv")), None)
    if not result_csv:
        return {"annotations": []}
    return {"annotations": runner.parse_results(result_csv)}


def run_dreams_step(ctx: RealRunContext, run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    from app.services.dreams_runner import DreamsRunner

    query_paths = selected_input_paths(ctx, {"MGF", "MSP"})
    if not query_paths:
        raise RunnerConfigurationError("DreaMS requires an uploaded MGF/MSP query file.")
    libs = selected_libraries(ctx)
    if not libs:
        raise RunnerConfigurationError("DreaMS library search requires a selected spectral library.")
    params = ctx.job.parameters or ctx.workflow.parameters or {}
    runner = DreamsRunner(cache_dir=settings.dreams_cache_dir)
    library_mgf = _normalized_library_mgf(libs[0])
    top_k = params.get("top_n", 5)
    all_rows: list[dict[str, Any]] = []
    for query in query_paths:
        all_rows.extend(runner.library_search(query, library_mgf, top_k=top_k))
    return {"annotations": all_rows}


def run_matchms_step(ctx: RealRunContext, run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    from app.services.mzxml_parser import _tolerant_load_spectra as load_query_spectra
    from app.services.spectral_libraries import ensure_normalized_mgf
    from app.services.spectral_search import _load_library_spectra, search_spectra_against_libraries

    query_paths = selected_input_paths(ctx, {"MGF", "MSP", "mzML", "mzXML"})
    if not query_paths:
        raise RunnerConfigurationError("matchms requires an uploaded query file.")
    libs = selected_libraries(ctx)
    if not libs:
        raise RunnerConfigurationError("matchms library search requires a selected spectral library.")

    query_spectra: list[dict[str, Any]] = []
    for p in query_paths:
        try:
            query_spectra.extend(load_query_spectra(p))
        except Exception as exc:
            raise RunnerConfigurationError(f"Failed to parse query spectra from {p.name}: {exc}") from exc

    lib_path = Path(libs[0].path)
    try:
        cache_dir = Path("./data/libraries/.cache")
        normalized_lib = ensure_normalized_mgf(lib_path, cache_dir)
        library_spectra = _load_library_spectra(normalized_lib)
    except Exception:
        library_spectra = _load_library_spectra(lib_path)

    params = ctx.job.parameters or ctx.workflow.parameters or {}

    # Prefer native matchms when installed; otherwise use the dependency-free simple cosine.
    try:
        from app.services.matchms_runner import load_spectra, run_matchms_library_search

        matchms_query = []
        for p in query_paths:
            matchms_query.extend(load_spectra(p))
        matchms_lib = load_spectra(_normalized_library_mgf(libs[0]))
        rows = run_matchms_library_search(
            matchms_query,
            matchms_lib,
            cosine_threshold=float(params.get("minimum_cosine", 0.7)),
            min_matched_peaks=int(params.get("minimum_matched_peaks", 6)),
            top_k=int(params.get("top_n", 5)),
        )
        return {"annotations": rows}
    except Exception:
        pass

    rows = search_spectra_against_libraries(
        query_spectra,
        engine_name="matchms",
        library_ids=[libs[0].id],
        threshold=float(params.get("minimum_cosine", 0.7)),
        min_matched_peaks=int(params.get("minimum_matched_peaks", 6)),
        top_k=int(params.get("top_n", 5)),
        precursor_tolerance=float(params.get("precursor_tolerance", 0.01)),
        mz_tolerance=float(params.get("mz_tolerance", 0.1)),
    )
    return {"annotations": rows}


def run_cfm_id_step(ctx: RealRunContext, run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    from app.services.cfm_id import CfmIdRunner

    model_id = ctx.job.parameters.get("cfm_model_id") if ctx.job.parameters else None
    model = None
    if model_id:
        from app.core.database import engine as db_engine
        with Session(db_engine) as _session:
            model = _session.get(ModelAsset, int(model_id))
    model_dir = Path(model.path) if model and model.path else Path(settings.models_dir) / "cfm"
    runner = CfmIdRunner(
        predict_binary=settings.cfm_binary,
        identify_binary=settings.cfm_id_binary,
        train_binary=settings.cfm_train_binary,
        model_dir=model_dir,
    )
    params = ctx.job.parameters or {}
    job_type = ctx.job.job_type.lower()
    ion_mode = str(params.get("ion_mode", "+")).lower()
    ion_arg = "+" if ion_mode in ("positive", "+", "pos") else "-"

    if job_type == "cfm_id_predict":
        smiles_list = params.get("smiles_list", [])
        output_dir = run_dir / "cfm_predict"
        output_dir.mkdir(parents=True, exist_ok=True)
        rows: list[dict[str, Any]] = []
        for idx, smiles in enumerate(smiles_list):
            out = output_dir / f"predicted_{idx}.txt"
            runner.predict_spectrum(smiles, out, ion_mode=ion_arg)
            rows.append({"feature_id": f"CFM{idx:04d}", "smiles": smiles, "predicted_spectrum_file": str(out), "annotation_source": "cfm_id"})
        return {"annotations": rows}

    query_paths = selected_input_paths(ctx, {"MGF", "MSP"})
    if not query_paths:
        raise RunnerConfigurationError("CFM-ID identification requires an uploaded query spectrum file.")
    candidate_file = run_dir / "candidates.txt"
    # Build candidate list from selected library metadata
    libs = selected_libraries(ctx)
    if libs:
        from app.services.spectral_libraries import ensure_normalized_mgf
        lib_path = ensure_normalized_mgf(Path(libs[0].path), Path("./data/libraries/.cache"))
        # Extract candidate SMILES from library MGF
        candidate_file.write_text("# id smiles\n", encoding="utf-8")
        # Simplified: use matchms to pull metadata
        from app.services.matchms_runner import load_spectra
        lib_spectra = load_spectra(lib_path)
        with candidate_file.open("a", encoding="utf-8") as handle:
            for i, spec in enumerate(lib_spectra):
                smiles = spec.get("smiles") or spec.get("SMILES")
                if smiles:
                    handle.write(f"{i}\t{smiles}\n")
    if not candidate_file.exists() or candidate_file.stat().st_size == 0:
        raise RunnerConfigurationError("CFM-ID identification requires a candidate list (SMILES) from a selected library.")
    out = run_dir / "cfm_id_results.txt"
    rows = runner.identify_compound(
        query_paths[0],
        candidate_file,
        out,
        ion_mode=ion_arg,
        score_type=str(params.get("score_type", "DotProduct")),
        num_highest=int(params.get("num_highest", 10)),
        ppm_mass_tol=float(params.get("ppm_mass_tol", 10.0)),
        abs_mass_tol=float(params.get("abs_mass_tol", 0.01)),
    )
    return {"annotations": rows}


def commands_for_job(session: Session, job: Job) -> list[EngineCommand | PythonEngineStep]:
    workflow = session.get(Workflow, job.workflow_id) if job.workflow_id else None
    run_dir = job_dir(job.id)
    run_dir.mkdir(parents=True, exist_ok=True)
    job_type = job.job_type.lower()
    steps: list[EngineCommand | PythonEngineStep] = []

    if job_type in {"mzmine", "full_pipeline", "pipeline"}:
        steps.append(build_mzmine_command(session, job, workflow, run_dir))

    if job_type in {"sirius", "full_pipeline", "pipeline", "annotation"}:
        steps.append(build_sirius_command(session, job, run_dir))

    if job_type in {"sirius_api"}:
        steps.append(PythonEngineStep("sirius_api", run_sirius_api_step))

    if job_type in {"ms2query"}:
        steps.append(PythonEngineStep("ms2query", run_ms2query_step))

    if job_type in {"dreams"}:
        steps.append(PythonEngineStep("dreams", run_dreams_step))

    if job_type in {"matchms"}:
        steps.append(PythonEngineStep("matchms", run_matchms_step))

    if job_type in {"cfm_id", "cfm_id_predict", "cfm_id_identify"}:
        steps.append(PythonEngineStep("cfm_id", run_cfm_id_step))

    if not steps:
        raise RunnerConfigurationError(f"No real runner is configured for job type: {job.job_type}")
    return steps


def run_command(command: EngineCommand, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    command.stdout_path.parent.mkdir(parents=True, exist_ok=True)
    command.stderr_path.parent.mkdir(parents=True, exist_ok=True)
    with command.stdout_path.open("w", encoding="utf-8") as stdout, command.stderr_path.open("w", encoding="utf-8") as stderr:
        return subprocess.run(
            command.args,
            cwd=command.cwd,
            stdout=stdout,
            stderr=stderr,
            text=True,
            shell=False,
            check=False,
            timeout=timeout_seconds,
        )


def write_command_manifest(job: Job, steps: list[EngineCommand | PythonEngineStep]) -> Path:
    run_dir = job_dir(job.id)
    payload: dict[str, Any] = {
        "job_id": job.id,
        "job_type": job.job_type,
        "parameters": job.parameters,
        "commands": [
            {
                "engine": step.name if isinstance(step, PythonEngineStep) else step.engine,
                "args": (step.args if isinstance(step, EngineCommand) else []),
                "cwd": str(step.cwd) if isinstance(step, EngineCommand) else str(run_dir),
                "stdout": str(step.stdout_path) if isinstance(step, EngineCommand) else None,
                "stderr": str(step.stderr_path) if isinstance(step, EngineCommand) else None,
            }
            for step in steps
        ],
    }
    output = run_dir / "command_manifest.json"
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output


def _persist_results(session: Session, job_id: int, result_buckets: dict[str, list[dict[str, Any]]], warnings: list[str]) -> None:
    for result_type, rows in result_buckets.items():
        if rows:
            session.add(
                ResultTable(
                    job_id=job_id,
                    result_type=result_type,
                    columns=list(dict.fromkeys(key for row in rows for key in row.keys())),
                    rows=rows,
                    warnings=warnings,
                )
            )
    if warnings:
        session.add(
            ResultTable(
                job_id=job_id,
                result_type="parse_warnings",
                columns=["warning"],
                rows=[{"warning": warning} for warning in warnings],
                warnings=warnings,
            )
        )
    session.commit()


def run_real_pipeline(context: RealRunContext) -> None:
    """Execute real engines (subprocess or Python) and parse/merge their outputs."""
    from app.services.consensus import merge_annotations
    from app.services.statistics import compute_metadata_aware_statistics

    with Session(settings_engine()) as session:
        job = session.get(Job, context.job.id)
        if not job:
            raise ExternalToolError("Job no longer exists")
        steps = commands_for_job(session, job)
        job.command_args = [arg for step in steps if isinstance(step, EngineCommand) for arg in step.args]
        session.add(job)
        session.commit()

    manifest = write_command_manifest(context.job, steps)
    run_dir = job_dir(context.job.id)
    (run_dir / "real_run_note.txt").write_text(
        "This job used MOCK_EXECUTION=false. See command_manifest.json.\n",
        encoding="utf-8",
    )

    aggregated: dict[str, list[dict[str, Any]]] = {"features": [], "annotations": []}
    warnings: list[str] = []

    for step in steps:
        if isinstance(step, EngineCommand):
            completed = run_command(step, settings.job_timeout_seconds)
            if completed.returncode != 0:
                raise ExternalToolError(
                    f"{step.engine} failed with exit code {completed.returncode}. "
                    f"See {step.stderr_path} and {manifest}."
                )
            if step.engine == "mzmine":
                parsed = parse_mzmine_outputs(run_dir)
                aggregated["features"].extend(parsed.get("features", []))
                warnings.extend(parsed.get("warnings", []))
            if step.engine == "sirius":
                parsed = parse_sirius_outputs(run_dir / "sirius")
                aggregated["annotations"].extend(parsed.get("annotations", []))
                warnings.extend(parsed.get("warnings", []))
        else:
            result = step.run(context, run_dir)
            aggregated["features"].extend(result.get("features", []))
            aggregated["annotations"].extend(result.get("annotations", []))

    # Build consensus annotations if multiple engines produced annotation rows
    sirius_rows = [r for r in aggregated["annotations"] if r.get("annotation_source") in ("sirius", "sirius_api")]
    ms2query_rows = [r for r in aggregated["annotations"] if r.get("annotation_source") == "ms2query"]
    dreams_rows = [r for r in aggregated["annotations"] if r.get("annotation_source") == "dreams"]
    matchms_rows = [r for r in aggregated["annotations"] if r.get("annotation_source") == "matchms"]
    cfm_rows = [r for r in aggregated["annotations"] if r.get("annotation_source") == "cfm_id"]

    non_empty_sources = sum(1 for group in (sirius_rows, ms2query_rows, dreams_rows, matchms_rows, cfm_rows) if group)
    if non_empty_sources > 1:
        consensus = merge_annotations(
            aggregated["features"],
            sirius_rows=sirius_rows or None,
            ms2query_rows=ms2query_rows or None,
            dreams_rows=dreams_rows or None,
            matchms_rows=matchms_rows or None,
            cfm_rows=cfm_rows or None,
            weights=context.workflow.parameters.get("weights") if context.workflow else None,
        )
        aggregated["annotations"] = consensus

    # Compute metadata-aware statistics if metadata is available
    if context.metadata and aggregated["features"]:
        stats = compute_metadata_aware_statistics(
            aggregated["features"],
            context.metadata,
            context.workflow.parameters if context.workflow else {},
        )
        if stats:
            aggregated["statistics"] = stats

    with Session(settings_engine()) as session:
        _persist_results(session, context.job.id, aggregated, warnings)


def settings_engine():
    from app.core.database import engine
    return engine
