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


INSTALLABLE_PACKAGES: dict[str, str] = {
    "matchms": "matchms",
    "ms2deepscore": "ms2deepscore",
    "ms2query": "ms2query",
    "spec2vec": "spec2vec",
    "rdkit": "rdkit",
}

_EXTRA_DEPS: dict[str, list[str]] = {
    "ms2query": ["onnxruntime", "h5py", "pyarrow", "skl2onnx"],
}

_CONSTRAINT_FILE = Path("/tmp/fragmentiq_pip_constraints.txt")


def _write_constraints() -> Path:
    _CONSTRAINT_FILE.write_text("setuptools<72\n", encoding="utf-8")
    return _CONSTRAINT_FILE


def _pip_install(packages: list[str], *, no_deps: bool = False) -> subprocess.CompletedProcess[str]:
    constraint = _write_constraints()
    env = {**__import__("os").environ, "PIP_CONSTRAINT": str(constraint)}
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--prefer-binary", "--quiet",
        *packages,
    ]
    if no_deps:
        cmd.insert(-len(packages), "--no-deps")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)


def install_package(package_name: str) -> dict[str, Any]:
    pip_name = INSTALLABLE_PACKAGES.get(package_name)
    if not pip_name:
        return {"status": "error", "message": f"Package '{package_name}' is not in the installable allowlist."}
    try:
        extras = _EXTRA_DEPS.get(package_name, [])
        if extras:
            _pip_install(extras)

        completed = _pip_install([pip_name])
        if completed.returncode != 0:
            fallback = _pip_install([pip_name], no_deps=True)
            if fallback.returncode != 0:
                stderr = completed.stderr.strip()
                short = stderr.split("\n")[-1] if stderr else "pip install failed"
                return {"status": "error", "message": short, "log": stderr}

        importlib.invalidate_caches()
        status = package_status(package_name)
        if status["status"] == "available":
            return {"status": "installed", "message": f"Successfully installed {pip_name}", "detail": status}
        return {"status": "installed", "message": f"Installed {pip_name} (may need restart to detect)", "detail": status}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": f"Installation of {pip_name} timed out after 5 minutes"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


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
        "matchms": {**package_status("matchms"), "installable": True},
        "ms2deepscore": {**package_status("ms2deepscore"), "installable": True},
        "ms2query": {**package_status("ms2query"), "installable": True},
        "dreams": package_status("dreams"),
        "spec2vec": {**package_status("spec2vec"), "installable": True},
        "rdkit": {**package_status("rdkit"), "installable": True},
        "models": _asset_status(settings.models_dir, "needs_model"),
        "libraries": _asset_status(settings.libraries_dir, "needs_library"),
    }
