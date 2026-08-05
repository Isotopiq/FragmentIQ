from collections.abc import Generator

import shutil
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import settings
from app.core.storage import project_dir
from app.models.domain import DatasetFile, Job, MetadataTable, Project, Workflow
from app.services.workflows import WORKFLOW_PRESETS


settings.ensure_directories()
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)


def create_db_and_tables() -> None:
    settings.ensure_directories()
    SQLModel.metadata.create_all(engine)


def seed_demo_data() -> dict[str, int] | None:
    with Session(engine) as session:
        if session.exec(select(Project)).first():
            return
        project = Project(
            name="Demo metabolomics project",
            description="Seeded end-to-end LC-MS/MS demo with metadata, feature table, workflow, and completed results.",
        )
        session.add(project)
        session.commit()
        session.refresh(project)

        upload_dir = project_dir(project.id)
        example_table = Path("example_data/mock_feature_table.csv")
        stored_table = upload_dir / "mock_feature_table.csv"
        if example_table.exists():
            shutil.copyfile(example_table, stored_table)
        else:
            stored_table.write_text(
                "feature_id,mz,rt,sample_control_mean,sample_treated_mean,intensity\n"
                "F001,101.1,2.3,10000,25000,17500\n"
                "F002,150.2,3.1,30000,12000,21000\n",
                encoding="utf-8",
            )
        session.add(
            DatasetFile(
                project_id=project.id,
                original_name="mock_feature_table.csv",
                stored_name="mock_feature_table.csv",
                file_type="CSV",
                size_bytes=stored_table.stat().st_size,
                path=str(stored_table),
            )
        )
        session.add(
            MetadataTable(
                project_id=project.id,
                name="Demo sample metadata",
                columns=["sample_name", "condition", "batch", "replicate", "subject_id"],
                rows=[
                    {"sample_name": "control_01", "condition": "control", "batch": "B1", "replicate": "1", "subject_id": "M01"},
                    {"sample_name": "control_02", "condition": "control", "batch": "B1", "replicate": "2", "subject_id": "M02"},
                    {"sample_name": "treated_01", "condition": "treated", "batch": "B1", "replicate": "1", "subject_id": "M03"},
                    {"sample_name": "treated_02", "condition": "treated", "batch": "B2", "replicate": "2", "subject_id": "M04"},
                ],
                group_columns=["condition", "batch"],
                warnings=[],
            )
        )
        preset = WORKFLOW_PRESETS[0]
        workflow = Workflow(
            project_id=project.id,
            name=preset["name"],
            engine="pipeline",
            preset_key=preset["id"],
            parameters=preset["parameters"],
            mzbatch_text=preset.get("mzbatch_template", ""),
        )
        session.add(workflow)
        session.commit()
        session.refresh(workflow)
        job = Job(
            project_id=project.id,
            workflow_id=workflow.id,
            name="Completed demo consensus pipeline",
            job_type="full_pipeline",
            status="queued",
            stage="queued",
            progress=0,
            parameters={"demo_seed": True, **preset["parameters"]},
            command_args=["mock-runner", "--job-type", "full_pipeline"],
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        project_id = project.id
        job_id = job.id

    from app.services.jobs import run_mock_job_sync

    run_mock_job_sync(job.id)
    return {"project_id": project_id, "job_id": job_id}


def reset_demo_data() -> None:
    settings.ensure_directories()
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    for relative in ("uploads", "results", "logs", "workflow_configs", "reports"):
        path = settings.storage_root / relative
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
