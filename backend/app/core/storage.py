from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path
from typing import Iterable

from fastapi import HTTPException, UploadFile

from app.core.config import settings


ALLOWED_EXTENSIONS = {
    ".mzml": "mzML",
    ".mzxml": "mzXML",
    ".imzml": "imzML",
    ".mgf": "MGF",
    ".msp": "MSP",
    ".csv": "CSV",
    ".tsv": "TSV",
    ".txt": "text",
    ".mztab": "mzTab",
    ".mzbatch": "MZmine batch",
    ".zip": "archive",
}
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def ensure_storage_dirs() -> None:
    settings.ensure_directories()


def sanitize_filename(name: str) -> str:
    candidate = SAFE_NAME_RE.sub("_", Path(name).name).strip("._")
    if not candidate:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return candidate[:180]


def detect_file_kind(filename: str) -> str:
    return ALLOWED_EXTENSIONS.get(Path(filename).suffix.lower(), "unknown")


def safe_child(base: Path, *parts: str) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    base_resolved = base.resolve()
    target = base.joinpath(*parts).resolve()
    if target != base_resolved and base_resolved not in target.parents:
        raise HTTPException(status_code=400, detail="Invalid path")
    return target


def project_dir(project_id: int) -> Path:
    path = settings.uploads_dir / f"project_{project_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def job_dir(job_id: int) -> Path:
    path = settings.results_dir / f"job_{job_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_path(job_id: int) -> Path:
    path = settings.logs_dir / f"job_{job_id}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


async def save_upload(upload: UploadFile, destination: Path) -> int:
    size = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > settings.max_upload_size_bytes:
                handle.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Uploaded file exceeds configured size limit")
            handle.write(chunk)
    return size


def file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def zip_paths(paths: Iterable[Path], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            if path.is_file():
                archive.write(path, arcname=path.name)
            elif path.is_dir():
                for child in path.rglob("*"):
                    if child.is_file():
                        archive.write(child, arcname=str(child.relative_to(path.parent)))
    return output_path


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()
