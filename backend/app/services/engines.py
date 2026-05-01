from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.core.config import settings


def command_status(command: str, args: list[str] | None = None) -> dict[str, Any]:
    executable = shutil.which(command)
    if not executable:
        return {"status": "not_installed", "version": None, "path": None}
    try:
        completed = subprocess.run(
            [executable, *(args or ["--version"])],
            capture_output=True,
            check=False,
            text=True,
            timeout=8,
        )
        output = (completed.stdout or completed.stderr).strip().splitlines()
        return {"status": "available", "version": output[0] if output else "installed", "path": executable}
    except Exception as exc:  # pragma: no cover
        return {"status": "error", "version": str(exc), "path": executable}


def package_status(module_name: str) -> dict[str, Any]:
    if importlib.util.find_spec(module_name) is None:
        return {"status": "not_installed", "version": None}
    try:
        module = __import__(module_name)
        return {"status": "available", "version": getattr(module, "__version__", "installed")}
    except Exception as exc:  # pragma: no cover
        return {"status": "error", "version": str(exc)}


def _asset_status(path: Path, empty_status: str) -> dict[str, Any]:
    items = sorted(child.name for child in path.glob("*") if child.is_file()) if path.exists() else []
    return {"status": "available" if items else empty_status, "count": len(items), "items": items}


def detect_engines() -> dict[str, Any]:
    return {
        "python": {"status": "available", "version": sys.version.split()[0]},
        "platform": {"status": "available", "version": platform.platform()},
        "java": command_status("java", ["-version"]),
        "mzmine": command_status(settings.mzmine_binary, ["--version"]),
        "sirius": {
            **command_status(settings.sirius_binary, ["--version"]),
            "notes": "SIRIUS login/license configuration is server-side only.",
        },
        "matchms": package_status("matchms"),
        "ms2deepscore": package_status("ms2deepscore"),
        "ms2query": package_status("ms2query"),
        "dreams": package_status("dreams"),
        "spec2vec": package_status("spec2vec"),
        "rdkit": package_status("rdkit"),
        "models": _asset_status(settings.models_dir, "needs_model"),
        "libraries": _asset_status(settings.libraries_dir, "needs_library"),
    }
