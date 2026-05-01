from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import settings
from app.models.domain import Project, Workflow
from app.services.workflows import WORKFLOW_PRESETS


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)


def create_db_and_tables() -> None:
    settings.ensure_directories()
    SQLModel.metadata.create_all(engine)


def seed_demo_data() -> None:
    with Session(engine) as session:
        if session.exec(select(Project)).first():
            return
        project = Project(name="Demo metabolomics project", description="Seed project for mock LC-MS/MS workflows.")
        session.add(project)
        session.commit()
        session.refresh(project)
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


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
