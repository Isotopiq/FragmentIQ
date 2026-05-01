from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
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
from app.services.engines import detect_engines
from app.services.jobs import build_results_zip, create_job, event_stream, result_rows
from app.services.parsers import parse_metadata_text, validate_metadata_rows
from app.services.workflows import WORKFLOW_PRESETS, validate_workflow_payload

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
    table = MetadataTable(project_id=project_id, name=name, columns=parsed["columns"], rows=parsed["rows"], warnings=warnings)
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
    warnings = validate_workflow_payload({"parameters": payload.parameters, "mzbatch_text": payload.mzbatch_text})
    payload.parameters = {**payload.parameters, "validation_warnings": warnings}
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
    warnings = validate_workflow_payload({"parameters": workflow.parameters, "mzbatch_text": workflow.mzbatch_text})
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
async def upload_library(name: str, file: UploadFile = File(...), source: str = "user", session: Session = Depends(get_session)) -> LibraryAsset:
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
    asset.indexed = True
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
