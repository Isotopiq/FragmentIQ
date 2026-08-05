from collections.abc import Generator

import shutil
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import settings
from app.core.storage import detect_file_kind, project_dir
from app.models.domain import DatasetFile, Job, LibraryAsset, MetadataTable, Project, Workflow
from app.services.workflows import WORKFLOW_PRESETS


settings.ensure_directories()
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)

DEMO_DATA_DIR = Path(__file__).resolve().parents[3] / "example_data"


def create_db_and_tables() -> None:
    settings.ensure_directories()
    SQLModel.metadata.create_all(engine)


def _preset_by_id(preset_id: str) -> dict:
    for preset in WORKFLOW_PRESETS:
        if preset["id"] == preset_id:
            return preset
    return WORKFLOW_PRESETS[0]


def seed_demo_data() -> dict[str, int] | None:
    from app.services.jobs import run_mock_job_sync
    from app.services.spectral_libraries import index_spectral_library

    with Session(engine) as session:
        if session.exec(select(Project)).first():
            return
        project = Project(
            name="Demo metabolomics project",
            description="Seeded end-to-end LC-MS/MS demo with mzXML data, a spectral library, metadata, workflows, and completed results.",
        )
        session.add(project)
        session.commit()
        session.refresh(project)

        upload_dir = project_dir(project.id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Mock CSV feature table
        example_table = DEMO_DATA_DIR / "mock_feature_table.csv"
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
        feature_file = DatasetFile(
            project_id=project.id,
            original_name="mock_feature_table.csv",
            stored_name="mock_feature_table.csv",
            file_type="CSV",
            size_bytes=stored_table.stat().st_size,
            path=str(stored_table),
        )
        session.add(feature_file)

        # Demo mzXML file with two MS/MS scans
        example_mzxml = DEMO_DATA_DIR / "demo.mzXML"
        stored_mzxml = upload_dir / "demo.mzXML"
        if example_mzxml.exists():
            shutil.copyfile(example_mzxml, stored_mzxml)
        else:
            stored_mzxml.write_text(
                "<?xml version=\"1.0\" encoding=\"ISO-8859-1\"?>\n"
                "<mzXML xmlns=\"http://sashimi.sourceforge.net/schema_revision/mzXML_2.1\">\n"
                "<msRun scanCount=\"2\">\n"
                '<scan num="1" msLevel="2" peaksCount="3" retentionTime="PT10S" polarity="+">\n'
                '<precursorMz precursorIntensity="1000">100.0</precursorMz>\n'
                '<peaks precision="32" byteOrder="network" pairOrder="m/z-int">'
                "QsgAAER6AABDSAAAQ/oAAEOWAABDegA=</peaks>\n"
                "</scan>\n"
                '<scan num="2" msLevel="2" peaksCount="3" retentionTime="PT20S" polarity="+">\n'
                '<precursorMz precursorIntensity="1000">200.0</precursorMz>\n'
                '<peaks precision="32" byteOrder="network" pairOrder="m/z-int">'
                "Q0gAAER6AABDlgAAQ8gAAEPIAABDSAA=</peaks>\n"
                "</scan>\n"
                "</msRun>\n"
                "</mzXML>\n",
                encoding="utf-8",
            )
        mzxml_file = DatasetFile(
            project_id=project.id,
            original_name="demo.mzXML",
            stored_name="demo.mzXML",
            file_type=detect_file_kind("demo.mzXML"),
            size_bytes=stored_mzxml.stat().st_size,
            path=str(stored_mzxml),
        )
        session.add(mzxml_file)

        # Demo spectral library
        example_lib = DEMO_DATA_DIR / "demo_library.mgf"
        stored_lib = settings.libraries_dir / "demo_library.mgf"
        settings.libraries_dir.mkdir(parents=True, exist_ok=True)
        if example_lib.exists():
            shutil.copyfile(example_lib, stored_lib)
        else:
            stored_lib.write_text(
                "BEGIN IONS\n"
                "PEPMASS=100.0\n"
                "NAME=Mock metabolite 1\n"
                "FORMULA=C6H12O6\n"
                "100.0 1000.0\n"
                "200.0 500.0\n"
                "300.0 250.0\n"
                "END IONS\n"
                "BEGIN IONS\n"
                "PEPMASS=200.0\n"
                "NAME=Mock metabolite 2\n"
                "FORMULA=C8H16O4\n"
                "200.0 1000.0\n"
                "300.0 400.0\n"
                "400.0 200.0\n"
                "END IONS\n",
                encoding="utf-8",
            )
        library = LibraryAsset(
            name="Demo spectral library",
            source="seed",
            description="Demo MGF spectral library used for matchms/MS2Query/DreaMS searches.",
            library_format="mgf",
            ion_mode="positive",
            supported_engines=["matchms", "ms2query", "dreams"],
            path=str(stored_lib),
            size_bytes=stored_lib.stat().st_size,
        )
        session.add(library)

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
        session.commit()
        session.refresh(library)
        session.refresh(mzxml_file)

        # Index the demo library so it is ready for searches
        try:
            index_spectral_library(library)
            session.add(library)
            session.commit()
        except Exception:
            pass

        # Full-pipeline demo workflow/job
        pipeline_preset = _preset_by_id("untargeted-positive")
        pipeline_workflow = Workflow(
            project_id=project.id,
            name=pipeline_preset["name"],
            engine="pipeline",
            preset_key=pipeline_preset["id"],
            parameters=pipeline_preset["parameters"],
            mzbatch_text=pipeline_preset.get("mzbatch_template", ""),
        )
        session.add(pipeline_workflow)
        session.commit()
        session.refresh(pipeline_workflow)

        pipeline_job = Job(
            project_id=project.id,
            workflow_id=pipeline_workflow.id,
            name="Completed demo consensus pipeline",
            job_type="full_pipeline",
            status="queued",
            stage="queued",
            progress=0,
            parameters={"demo_seed": True, **pipeline_preset["parameters"]},
            command_args=["mock-runner", "--job-type", "full_pipeline"],
        )
        session.add(pipeline_job)

        # matchms-library-search demo workflow/job using the demo mzXML + library
        matchms_preset = _preset_by_id("matchms-library-search")
        matchms_workflow = Workflow(
            project_id=project.id,
            name=matchms_preset["name"],
            engine="matchms",
            preset_key=matchms_preset["id"],
            parameters=matchms_preset["parameters"],
            input_file_ids=[mzxml_file.id],
            library_ids=[library.id],
            mzbatch_text=matchms_preset.get("mzbatch_template", ""),
        )
        session.add(matchms_workflow)
        session.commit()
        session.refresh(matchms_workflow)

        matchms_job = Job(
            project_id=project.id,
            workflow_id=matchms_workflow.id,
            name="Demo matchms mzXML search",
            job_type="matchms",
            status="queued",
            stage="queued",
            progress=0,
            input_file_ids=[mzxml_file.id],
            library_ids=[library.id],
            parameters={"demo_seed": True, **matchms_preset["parameters"], "minimum_matched_peaks": 3},
            command_args=["mock-runner", "--job-type", "matchms"],
        )
        session.add(matchms_job)
        session.commit()
        session.refresh(matchms_job)

        project_id = project.id
        pipeline_job_id = pipeline_job.id
        matchms_job_id = matchms_job.id

    run_mock_job_sync(pipeline_job_id)
    run_mock_job_sync(matchms_job_id)
    return {"project_id": project_id, "pipeline_job_id": pipeline_job_id, "matchms_job_id": matchms_job_id}


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
