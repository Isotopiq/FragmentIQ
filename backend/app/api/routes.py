from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session, reset_demo_data, seed_demo_data
from app.core.storage import (
    detect_file_kind,
    file_size,
    job_dir,
    project_dir,
    safe_child,
    sanitize_filename,
    save_upload,
    zip_paths,
)
from app.models.domain import DatasetFile, Job, JobCreate, JobLog, LibraryAsset, MetadataTable, ModelAsset, Project, ResultTable, Workflow
from app.services.engines import INSTALLABLE_PACKAGES, detect_engines, install_package
from app.services.jobs import build_results_zip, create_job, event_stream, result_rows
from app.services.parsers import parse_metadata_text, validate_metadata_rows
from app.services.spectral_libraries import index_spectral_library
from app.services.sirius_api import test_sirius_connection
from app.services.workflows import WORKFLOW_PRESETS, validate_workflow_payload

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/demo/reset")
def reset_demo() -> dict[str, Any]:
    reset_demo_data()
    seeded = seed_demo_data()
    return {
        "status": "seeded",
        "project_id": seeded.get("project_id"),
        "job_id": seeded.get("job_id"),
    }


@router.post("/projects", response_model=Project)
def create_project(project: Project, session: Session = Depends(get_session)) -> Project:
    project.id = None
    session.add(project)
    session.commit()
    session.refresh(project)
    project_dir(project.id)
    return project


@router.get("/projects", response_model=list[Project])
def list_projects(session: Session = Depends(get_session)) -> list[Project]:
    return session.exec(select(Project).order_by(Project.created_at.desc())).all()


@router.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: int, session: Session = Depends(get_session)) -> Project:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/projects/{project_id}")
def delete_project(project_id: int, session: Session = Depends(get_session)) -> dict[str, str]:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    shutil.rmtree(project_dir(project_id), ignore_errors=True)
    session.delete(project)
    session.commit()
    return {"status": "deleted"}


@router.get("/projects/{project_id}/archive")
def project_archive(project_id: int, session: Session = Depends(get_session)) -> FileResponse:
    if not session.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    archive = settings.results_dir / f"project_{project_id}.zip"
    zip_paths([project_dir(project_id)], archive)
    return FileResponse(archive, filename=f"project-{project_id}.zip", media_type="application/zip")


@router.post("/projects/{project_id}/files", response_model=list[DatasetFile])
async def upload_files(project_id: int, files: list[UploadFile] = File(...), session: Session = Depends(get_session)) -> list[DatasetFile]:
    if not session.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    saved: list[DatasetFile] = []
    upload_dir = project_dir(project_id)
    for upload in files:
        filename = sanitize_filename(upload.filename or "upload.bin")
        kind = detect_file_kind(filename)
        if kind == "unknown":
            raise HTTPException(status_code=400, detail=f"Unsupported file extension for {filename}")
        destination = safe_child(upload_dir, filename)
        size = await save_upload(upload, destination)
        item = DatasetFile(
            project_id=project_id,
            original_name=upload.filename or filename,
            stored_name=filename,
            file_type=kind,
            size_bytes=size,
            path=str(destination),
        )
        session.add(item)
        saved.append(item)
    session.commit()
    for item in saved:
        session.refresh(item)
    return saved


@router.get("/projects/{project_id}/files", response_model=list[DatasetFile])
def list_files(project_id: int, session: Session = Depends(get_session)) -> list[DatasetFile]:
    return session.exec(select(DatasetFile).where(DatasetFile.project_id == project_id).order_by(DatasetFile.created_at.desc())).all()


@router.delete("/files/{file_id}")
def delete_file(file_id: int, session: Session = Depends(get_session)) -> dict[str, str]:
    item = session.get(DatasetFile, file_id)
    if not item:
        raise HTTPException(status_code=404, detail="File not found")
    Path(item.path).unlink(missing_ok=True)
    session.delete(item)
    session.commit()
    return {"status": "deleted"}


@router.post("/projects/{project_id}/metadata", response_model=MetadataTable)
async def create_metadata(
    project_id: int,
    name: str = "Sample metadata",
    file: UploadFile | None = File(default=None),
    session: Session = Depends(get_session),
) -> MetadataTable:
    if not session.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    if file:
        parsed = parse_metadata_text((await file.read()).decode("utf-8-sig"))
    else:
        parsed = {"columns": ["sample_name", "condition", "batch", "replicate"], "rows": []}
    warnings = validate_metadata_rows(parsed["columns"], parsed["rows"])
    table = MetadataTable(
        project_id=project_id,
        name=name,
        columns=parsed["columns"],
        rows=parsed["rows"],
        group_columns=[],
        warnings=warnings,
    )
    session.add(table)
    session.commit()
    session.refresh(table)
    return table


@router.post("/projects/{project_id}/metadata/json", response_model=MetadataTable)
def create_metadata_json(project_id: int, payload: MetadataTable, session: Session = Depends(get_session)) -> MetadataTable:
    if not session.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    warnings = validate_metadata_rows(payload.columns, payload.rows)
    table = MetadataTable(
        project_id=project_id,
        name=payload.name,
        columns=payload.columns,
        rows=payload.rows,
        group_columns=payload.group_columns,
        warnings=warnings,
    )
    session.add(table)
    session.commit()
    session.refresh(table)
    return table


@router.get("/projects/{project_id}/metadata", response_model=list[MetadataTable])
def list_metadata(project_id: int, session: Session = Depends(get_session)) -> list[MetadataTable]:
    return session.exec(select(MetadataTable).where(MetadataTable.project_id == project_id).order_by(MetadataTable.created_at.desc())).all()


@router.put("/metadata/{metadata_id}", response_model=MetadataTable)
def update_metadata(metadata_id: int, payload: MetadataTable, session: Session = Depends(get_session)) -> MetadataTable:
    table = session.get(MetadataTable, metadata_id)
    if not table:
        raise HTTPException(status_code=404, detail="Metadata not found")
    table.name = payload.name
    table.columns = payload.columns
    table.rows = payload.rows
    table.group_columns = payload.group_columns
    table.warnings = validate_metadata_rows(table.columns, table.rows)
    session.add(table)
    session.commit()
    session.refresh(table)
    return table


@router.post("/metadata/{metadata_id}/validate")
def validate_metadata(metadata_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    table = session.get(MetadataTable, metadata_id)
    if not table:
        raise HTTPException(status_code=404, detail="Metadata not found")
    warnings = validate_metadata_rows(table.columns, table.rows)
    table.warnings = warnings
    session.add(table)
    session.commit()
    return {"valid": not warnings, "warnings": warnings}


@router.get("/workflows/presets")
def workflow_presets() -> list[dict[str, Any]]:
    return WORKFLOW_PRESETS


@router.post("/workflows", response_model=Workflow)
def create_workflow(payload: Workflow, session: Session = Depends(get_session)) -> Workflow:
    if payload.project_id and not session.get(Project, payload.project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    payload.id = None
    workflow_warnings = validate_workflow_payload({
        "parameters": payload.parameters,
        "mzbatch_text": payload.mzbatch_text,
        "input_file_ids": payload.input_file_ids,
        "engines": payload.parameters.get("engines", []),
    })
    payload.validation_warnings = workflow_warnings
    session.add(payload)
    session.commit()
    session.refresh(payload)
    return payload


@router.get("/workflows/{workflow_id}", response_model=Workflow)
def get_workflow(workflow_id: int, session: Session = Depends(get_session)) -> Workflow:
    workflow = session.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.put("/workflows/{workflow_id}", response_model=Workflow)
def update_workflow(workflow_id: int, payload: Workflow, session: Session = Depends(get_session)) -> Workflow:
    workflow = session.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    workflow.name = payload.name
    workflow.engine = payload.engine
    workflow.preset_key = payload.preset_key
    workflow.mzbatch_text = payload.mzbatch_text
    workflow.library_ids = payload.library_ids
    workflow.input_file_ids = payload.input_file_ids
    workflow.parameters = payload.parameters
    session.add(workflow)
    session.commit()
    session.refresh(workflow)
    return workflow


@router.post("/workflows/{workflow_id}/validate")
def validate_workflow(workflow_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    workflow = session.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    warnings = validate_workflow_payload({
        "parameters": workflow.parameters,
        "mzbatch_text": workflow.mzbatch_text,
        "input_file_ids": workflow.input_file_ids,
        "engines": workflow.parameters.get("engines", []),
    })
    return {"valid": not warnings, "warnings": warnings}


@router.post("/jobs", response_model=Job)
def submit_job(payload: JobCreate, session: Session = Depends(get_session)) -> Job:
    if not session.get(Project, payload.project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return create_job(session, payload)


@router.get("/jobs", response_model=list[Job])
def list_jobs(project_id: int | None = None, session: Session = Depends(get_session)) -> list[Job]:
    statement = select(Job).order_by(Job.created_at.desc())
    if project_id:
        statement = select(Job).where(Job.project_id == project_id).order_by(Job.created_at.desc())
    return session.exec(statement).all()


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: int, session: Session = Depends(get_session)) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/cancel", response_model=Job)
def cancel_job(job_id: int, session: Session = Depends(get_session)) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = "canceled"
    job.stage = "canceled"
    job.progress = 100
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.post("/jobs/{job_id}/retry", response_model=Job)
def retry_job(job_id: int, session: Session = Depends(get_session)) -> Job:
    old = session.get(Job, job_id)
    if not old:
        raise HTTPException(status_code=404, detail="Job not found")
    return create_job(session, JobCreate(project_id=old.project_id, workflow_id=old.workflow_id, name=f"Retry of {old.name}", job_type=old.job_type, parameters=old.parameters))


@router.get("/jobs/{job_id}/logs")
def job_logs(job_id: int, session: Session = Depends(get_session)) -> dict[str, str]:
    if not session.get(Job, job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    logs = session.exec(select(JobLog).where(JobLog.job_id == job_id).order_by(JobLog.created_at)).all()
    return {"content": "\n".join(f"[{log.created_at.isoformat()}] {log.message}" for log in logs)}


@router.get("/jobs/{job_id}/events")
def job_events(job_id: int) -> StreamingResponse:
    return StreamingResponse(event_stream(job_id), media_type="text/event-stream")


@router.get("/jobs/{job_id}/results/features")
def job_features(job_id: int) -> dict[str, Any]:
    rows = result_rows(job_id, "features")
    return {"rows": rows, "columns": list(rows[0].keys()) if rows else []}


@router.get("/jobs/{job_id}/results/annotations")
def job_annotations(job_id: int) -> dict[str, Any]:
    rows = result_rows(job_id, "annotations")
    return {"rows": rows, "columns": list(rows[0].keys()) if rows else []}


@router.get("/jobs/{job_id}/results/statistics")
def job_statistics(job_id: int) -> dict[str, Any]:
    rows = result_rows(job_id, "statistics")
    return {"rows": rows, "columns": list(rows[0].keys()) if rows else []}


@router.get("/jobs/{job_id}/results/plots")
def job_plots(job_id: int) -> dict[str, Any]:
    features = result_rows(job_id, "features")
    stats = result_rows(job_id, "statistics")
    return {"features": features[:200], "statistics": stats[:200]}


@router.get("/jobs/{job_id}/results/consensus")
def job_consensus(job_id: int) -> dict[str, Any]:
    rows = result_rows(job_id, "annotations")
    return {"rows": rows, "columns": list(rows[0].keys()) if rows else []}


@router.get("/jobs/{job_id}/results/network")
def job_network(job_id: int) -> dict[str, Any]:
    rows = result_rows(job_id, "network")
    return rows[0] if rows else {"nodes": [], "edges": []}


@router.get("/jobs/{job_id}/download")
def job_download(job_id: int, session: Session = Depends(get_session)) -> FileResponse:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    archive = build_results_zip(job)
    return FileResponse(archive, filename=f"job-{job_id}.zip", media_type="application/zip")


@router.post("/libraries", response_model=LibraryAsset)
async def upload_library(
    file: UploadFile = File(...),
    name: str = Form(...),
    source: str = Form("user"),
    session: Session = Depends(get_session),
) -> LibraryAsset:
    filename = sanitize_filename(file.filename or "library.mgf")
    destination = safe_child(settings.libraries_dir, filename)
    await save_upload(file, destination)
    asset = LibraryAsset(name=name, source=source, path=str(destination), size_bytes=file_size(destination), supported_engines=["matchms", "ms2deepscore", "ms2query", "dreams"])
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


@router.get("/libraries", response_model=list[LibraryAsset])
def list_libraries(session: Session = Depends(get_session)) -> list[LibraryAsset]:
    return session.exec(select(LibraryAsset).order_by(LibraryAsset.created_at.desc())).all()


@router.delete("/libraries/{library_id}")
def delete_library(library_id: int, session: Session = Depends(get_session)) -> dict[str, str]:
    asset = session.get(LibraryAsset, library_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Library not found")
    Path(asset.path).unlink(missing_ok=True)
    session.delete(asset)
    session.commit()
    return {"status": "deleted"}


@router.post("/libraries/{library_id}/index", response_model=LibraryAsset)
def index_library(library_id: int, session: Session = Depends(get_session)) -> LibraryAsset:
    asset = session.get(LibraryAsset, library_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Library not found")
    meta = index_spectral_library(asset)
    asset.indexed = True
    asset.supported_engines = sorted(set(asset.supported_engines + ["matchms", "ms2query", "dreams", "sirius"]))
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


@router.post("/models", response_model=ModelAsset)
async def upload_model(name: str, engine: str, file: UploadFile = File(...), version: str | None = None, session: Session = Depends(get_session)) -> ModelAsset:
    filename = sanitize_filename(file.filename or "model.bin")
    destination = safe_child(settings.models_dir, filename)
    await save_upload(file, destination)
    asset = ModelAsset(name=name, engine=engine, version=version, path=str(destination), size_bytes=file_size(destination))
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


@router.get("/models", response_model=list[ModelAsset])
def list_models(session: Session = Depends(get_session)) -> list[ModelAsset]:
    return session.exec(select(ModelAsset).order_by(ModelAsset.created_at.desc())).all()


@router.post("/models/{model_id}/default")
def set_default_model(model_id: int, session: Session = Depends(get_session)) -> ModelAsset:
    asset = session.get(ModelAsset, model_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Model not found")
    for other in session.exec(select(ModelAsset).where(ModelAsset.engine == asset.engine)).all():
        other.is_default = False
        session.add(other)
    asset.is_default = True
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


@router.post("/models/train")
def submit_model_training_job(payload: dict[str, Any], session: Session = Depends(get_session)) -> Job:
    from app.models.domain import JobCreate
    project_id = int(payload["project_id"])
    if not session.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    params = payload.get("parameters", {})
    params["engine"] = payload.get("engine", params.get("engine"))
    params["training_file_id"] = payload.get("training_file_id")
    params["base_model_id"] = payload.get("base_model_id")
    job_payload = JobCreate(
        project_id=project_id,
        name=payload.get("name", f"Train {params.get('engine', 'model')}"),
        job_type="train_model",
        parameters=params,
    )
    return create_job(session, job_payload)


@router.delete("/models/{model_id}")
def delete_model(model_id: int, session: Session = Depends(get_session)) -> dict[str, str]:
    asset = session.get(ModelAsset, model_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Model not found")
    Path(asset.path).unlink(missing_ok=True)
    session.delete(asset)
    session.commit()
    return {"status": "deleted"}


@router.get("/system/status")
def system_status() -> dict[str, Any]:
    return {
        "app": settings.app_name,
        "mock_mode": settings.mock_execution,
        "storage_root": str(settings.storage_root),
        "max_upload_size_mb": settings.upload_max_mb,
        "engines": detect_engines(),
    }


@router.get("/system/engines")
def system_engines() -> dict[str, Any]:
    return detect_engines()


@router.get("/system/packages")
def list_installable_packages() -> dict[str, Any]:
    engines = detect_engines()
    packages = []
    for name, pip_name in INSTALLABLE_PACKAGES.items():
        engine_info = engines.get(name, {})
        packages.append({
            "name": name,
            "pip_name": pip_name,
            "status": engine_info.get("status", "unknown"),
            "version": engine_info.get("version"),
        })
    return {"packages": packages}


@router.post("/system/packages/install")
def install_system_package(payload: dict[str, str]) -> dict[str, Any]:
    package_name = payload.get("package")
    if not package_name:
        raise HTTPException(status_code=400, detail="Missing 'package' field")
    if package_name not in INSTALLABLE_PACKAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Package '{package_name}' is not installable. Allowed: {', '.join(sorted(INSTALLABLE_PACKAGES))}",
        )
    return install_package(package_name)


@router.post("/system/sirius/test")
def sirius_test_connection_endpoint(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    username = payload.get("username") or settings.sirius_username
    password = payload.get("password") or settings.sirius_password
    url = payload.get("url") or settings.sirius_api_url or None
    sirius_path = payload.get("sirius_path") or settings.sirius_binary
    raw_accept = payload.get("accept_terms")
    if raw_accept is None:
        raw_accept = settings.sirius_accept_terms
    accept_terms = str(raw_accept).lower() in ("true", "1", "yes")
    if not username or not password:
        raise HTTPException(status_code=400, detail="SIRIUS username and password are required")
    return test_sirius_connection(sirius_path, username, password, url=url, accept_terms=accept_terms)
