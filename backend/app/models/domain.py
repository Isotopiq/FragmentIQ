from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class ProjectBase(SQLModel):
    name: str
    description: str = ""


class Project(ProjectBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProjectCreate(ProjectBase):
    pass


class DatasetFile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(index=True, foreign_key="project.id")
    original_name: str
    stored_name: str
    file_type: str
    size_bytes: int
    path: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MetadataCreate(SQLModel):
    name: str = "Sample metadata"
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    group_columns: list[str] = Field(default_factory=list)


class MetadataTable(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(index=True, foreign_key="project.id")
    name: str
    columns: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    rows: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    group_columns: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    warnings: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WorkflowCreate(SQLModel):
    project_id: int | None = None
    name: str
    engine: str = "pipeline"
    preset_key: str | None = None
    mzbatch_text: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class Workflow(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int | None = Field(default=None, index=True, foreign_key="project.id")
    name: str
    engine: str = "pipeline"
    preset_key: str | None = None
    mzbatch_text: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    validation_warnings: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class JobCreate(SQLModel):
    project_id: int
    workflow_id: int | None = None
    name: str
    job_type: str = "full_pipeline"
    parameters: dict[str, Any] = Field(default_factory=dict)


class Job(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(index=True, foreign_key="project.id")
    workflow_id: int | None = Field(default=None, foreign_key="workflow.id")
    name: str
    job_type: str = "full_pipeline"
    status: str = Field(default="queued", index=True)
    progress: int = 0
    stage: str = "queued"
    parameters: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    command_args: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    software_versions: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class JobLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(index=True, foreign_key="job.id")
    stage: str = "queued"
    level: str = "info"
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ResultTable(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(index=True, foreign_key="job.id")
    result_type: str = Field(index=True)
    columns: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    rows: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    warnings: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LibraryAsset(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    asset_type: str = "library"
    source: str = ""
    description: str = ""
    ion_mode: str | None = None
    supported_engines: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    path: str
    size_bytes: int = 0
    indexed: bool = False
    extra_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ModelAsset(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    engine: str
    version: str | None = None
    path: str
    size_bytes: int = 0
    extra_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
