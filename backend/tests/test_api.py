from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


client = TestClient(app)


def test_project_upload_metadata_job_flow():
    project = client.post("/api/projects", json={"name": "Demo project"}).json()
    assert project["name"] == "Demo project"

    upload = client.post(
        f"/api/projects/{project['id']}/files",
        files={"files": ("sample_a.mzML", b"fake mzml", "application/octet-stream")},
    )
    assert upload.status_code == 200
    assert upload.json()[0]["extension"] == ".mzml"

    metadata = client.post(
        f"/api/projects/{project['id']}/metadata",
        files={"file": ("metadata.csv", b"sample_name,condition\nsample_a,control\n", "text/csv")},
    )
    assert metadata.status_code == 200
    assert metadata.json()["validation"]["valid"] is True

    job = client.post(
        "/api/jobs",
        json={
            "project_id": project["id"],
            "job_type": "full_pipeline",
            "name": "Mock full pipeline",
            "parameters": {"mock": True},
        },
    )
    assert job.status_code == 200
    job_id = job.json()["id"]
    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["status"] == "complete"

    logs = client.get(f"/api/jobs/{job_id}/logs").json()
    assert "Mock LC-MS/MS workflow complete" in logs["content"]

    features = client.get(f"/api/jobs/{job_id}/results/features").json()
    assert len(features["rows"]) >= 3


def test_rejects_unsupported_upload_extension():
    project = client.post("/api/projects", json={"name": "Upload guard"}).json()
    response = client.post(
        f"/api/projects/{project['id']}/files",
        files={"files": ("malware.exe", b"nope", "application/octet-stream")},
    )
    assert response.status_code == 400


def test_workflow_presets_and_engine_status():
    presets = client.get("/api/workflows/presets").json()
    assert any(preset["engine"] == "mzmine" for preset in presets)

    engines = client.get("/api/system/engines").json()
    assert "mzmine" in engines
    assert "python" in engines


def test_download_job_zip_exists():
    project = client.post("/api/projects", json={"name": "Archive project"}).json()
    job = client.post(
        "/api/jobs",
        json={"project_id": project["id"], "job_type": "mzmine", "name": "Archive job"},
    ).json()
    response = client.get(f"/api/jobs/{job['id']}/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert Path(get_settings().results_dir).exists()
