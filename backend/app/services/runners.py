from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.core.storage import job_dir, safe_child
from app.models.domain import DatasetFile, Job, ResultTable, Workflow
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
class RealRunContext:
    job: Job
    workflow: Workflow
    files: list[DatasetFile]


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


def preserve_workflow_config(workflow: Workflow | None, job: Job, run_dir: Path) -> Path | None:
    if not workflow:
        return None
    text = workflow.mzbatch_text
    if not text:
        template = workflow.parameters.get("mzbatch_template") if workflow.parameters else None
        if template:
            template_path = Path(template)
            if template_path.exists():
                text = template_path.read_text(encoding="utf-8")
    if not text:
        return None
    output = safe_child(settings.workflow_configs_dir, f"job_{job.id}.mzbatch")
    output.write_text(text, encoding="utf-8")
    (run_dir / "workflow.mzbatch").write_text(text, encoding="utf-8")
    return output


def build_mzmine_command(session: Session, job: Job, workflow: Workflow | None, run_dir: Path) -> EngineCommand:
    executable = resolve_executable(settings.mzmine_binary)
    mzbatch_path = preserve_workflow_config(workflow, job, run_dir)
    if not mzbatch_path:
        raise RunnerConfigurationError("A preserved .mzbatch workflow is required for real MZmine execution.")
    raw_files = project_files(session, job.project_id, {"mzML", "mzXML", "imzML"})
    if not raw_files:
        raise RunnerConfigurationError("Real MZmine execution requires at least one uploaded mzML/mzXML/imzML file.")

    # MZmine CLI flags differ by release. Keep the user-provided batch file intact and avoid inventing
    # module-level CLI parameters; deployment operators can override the executable wrapper if needed.
    args = [executable, settings.mzmine_batch_flag, str(mzbatch_path)]
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
            raise RunnerConfigurationError("Real SIRIUS execution requires an uploaded MGF/MSP file or a selected input file.")
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


def commands_for_job(session: Session, job: Job) -> list[EngineCommand]:
    workflow = session.get(Workflow, job.workflow_id) if job.workflow_id else None
    run_dir = job_dir(job.id)
    run_dir.mkdir(parents=True, exist_ok=True)
    job_type = job.job_type.lower()
    commands: list[EngineCommand] = []
    if job_type in {"mzmine", "full_pipeline", "pipeline"}:
        commands.append(build_mzmine_command(session, job, workflow, run_dir))
    if job_type in {"sirius", "full_pipeline", "pipeline", "annotation"}:
        commands.append(build_sirius_command(session, job, run_dir))
    if not commands:
        raise RunnerConfigurationError(f"No real runner is configured for job type: {job.job_type}")
    return commands


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


def write_command_manifest(job: Job, commands: list[EngineCommand]) -> Path:
    run_dir = job_dir(job.id)
    payload: dict[str, Any] = {
        "job_id": job.id,
        "job_type": job.job_type,
        "parameters": job.parameters,
        "commands": [
            {
                "engine": command.engine,
                "args": command.args,
                "cwd": str(command.cwd),
                "stdout": str(command.stdout_path),
                "stderr": str(command.stderr_path),
            }
            for command in commands
        ],
    }
    output = run_dir / "command_manifest.json"
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output


def run_real_pipeline(context: RealRunContext) -> None:
    """Execute real engines and parse any supported outputs they create.

    This path is intentionally conservative: it does not synthesize successful results
    when external tools are missing or fail. Mock mode remains the default for local
    smoke testing.
    """
    with Session(settings_engine()) as session:
        job = session.get(Job, context.job.id)
        if not job:
            raise ExternalToolError("Job no longer exists")
        commands = commands_for_job(session, job)
        job.command_args = [arg for command in commands for arg in command.args]
        session.add(job)
        session.commit()

    manifest = write_command_manifest(context.job, commands)
    run_dir = job_dir(context.job.id)
    (run_dir / "real_run_note.txt").write_text(
        "This job used MOCK_EXECUTION=false. Commands were executed with shell=False; see command_manifest.json.\n",
        encoding="utf-8",
    )

    for command in commands:
        completed = run_command(command, settings.job_timeout_seconds)
        if completed.returncode != 0:
            raise ExternalToolError(
                f"{command.engine} failed with exit code {completed.returncode}. "
                f"See {command.stderr_path} and {manifest}."
            )

    mzmine = parse_mzmine_outputs(run_dir)
    sirius = parse_sirius_outputs(run_dir / "sirius")
    rows_by_type: dict[str, list[dict[str, Any]]] = {
        "features": mzmine.get("features", []),
        "annotations": sirius.get("annotations", []),
    }
    warnings = [*mzmine.get("warnings", []), *sirius.get("warnings", [])]

    with Session(settings_engine()) as session:
        for result_type, rows in rows_by_type.items():
            if rows:
                session.add(
                    ResultTable(
                        job_id=context.job.id,
                        result_type=result_type,
                        columns=list(dict.fromkeys(key for row in rows for key in row.keys())),
                        rows=rows,
                        warnings=warnings,
                    )
                )
        if warnings:
            session.add(
                ResultTable(
                    job_id=context.job.id,
                    result_type="parse_warnings",
                    columns=["warning"],
                    rows=[{"warning": warning} for warning in warnings],
                    warnings=warnings,
                )
            )
        session.commit()


def settings_engine():
    # Local import avoids a circular module dependency during FastAPI startup.
    from app.core.database import engine

    return engine
