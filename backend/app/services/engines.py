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


class _InstallSpec:
    def __init__(
        self,
        pip_name: str,
        *,
        module_name: str | None = None,
        commands: list[str] | None = None,
        extras: list[str] | None = None,
        ignore_requires_python: bool = False,
    ):
        self.pip_name = pip_name
        self.module_name = module_name
        self.commands = commands or []
        self.extras = extras or []
        self.ignore_requires_python = ignore_requires_python


INSTALLABLE_PACKAGES: dict[str, _InstallSpec] = {
    "matchms": _InstallSpec("matchms", module_name="matchms"),
    "ms2deepscore": _InstallSpec("ms2deepscore", module_name="ms2deepscore"),
    "ms2query": _InstallSpec(
        "ms2query",
        module_name="ms2query",
        extras=["onnxruntime", "h5py", "pyarrow", "skl2onnx"],
    ),
    "spec2vec": _InstallSpec("spec2vec", module_name="spec2vec"),
    "rdkit": _InstallSpec("rdkit", module_name="rdkit"),
    "py-sirius-ms": _InstallSpec(
        "git+https://github.com/sirius-ms/sirius-client-openAPI.git#subdirectory=client-api_python/generated",
        module_name="PySirius",
    ),
    "dreams": _InstallSpec(
        "git+https://github.com/pluskal-lab/DreaMS.git",
        module_name="dreams",
        ignore_requires_python=True,
    ),
}

_CONSTRAINT_FILE = Path("/tmp/fragmentiq_pip_constraints.txt")


def _write_constraints() -> Path:
    _CONSTRAINT_FILE.write_text("setuptools<72\n", encoding="utf-8")
    return _CONSTRAINT_FILE


def _pip_install(packages: list[str], *, no_deps: bool = False, ignore_requires_python: bool = False) -> subprocess.CompletedProcess[str]:
    import os

    constraint = _write_constraints()
    env = {**os.environ, "PIP_CONSTRAINT": str(constraint)}
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--prefer-binary",
        *packages,
    ]
    if no_deps:
        cmd.insert(-len(packages), "--no-deps")
    if ignore_requires_python:
        cmd.insert(-len(packages), "--ignore-requires-python")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)


def install_package(package_name: str) -> dict[str, Any]:
    spec = INSTALLABLE_PACKAGES.get(package_name)
    if not spec:
        return {"status": "error", "message": f"Package '{package_name}' is not in the installable allowlist."}
    pip_name = spec.pip_name
    try:
        if spec.extras:
            _pip_install(spec.extras, ignore_requires_python=spec.ignore_requires_python)

        completed = _pip_install([pip_name], ignore_requires_python=spec.ignore_requires_python)
        stderr = completed.stderr.strip()
        if completed.returncode != 0:
            fallback = _pip_install([pip_name], no_deps=True, ignore_requires_python=spec.ignore_requires_python)
            if fallback.returncode != 0:
                short = stderr.split("\n")[-1] if stderr else "pip install failed"
                return {"status": "error", "message": short, "log": stderr}

        importlib.invalidate_caches()

        if spec.module_name and importlib.util.find_spec(spec.module_name):
            status = package_status(spec.module_name)
            if status["status"] == "available":
                return {"status": "installed", "message": f"Successfully installed {pip_name}", "detail": status}

        if spec.commands:
            for command in spec.commands:
                status = command_status(command, ["--version"])
                if status["status"] == "available":
                    return {"status": "installed", "message": f"Successfully installed {pip_name} ({command} available)", "detail": status}

        return {"status": "installed", "message": f"Installed {pip_name} (verify binary/module availability)", "detail": {"stderr": stderr}}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": f"Installation of {pip_name} timed out after 10 minutes"}
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
        "py-sirius-ms": {**package_status("PySirius"), "installable": package_name_in_allowlist("py-sirius-ms")},
        "matchms": {**package_status("matchms"), "installable": package_name_in_allowlist("matchms")},
        "ms2deepscore": {**package_status("ms2deepscore"), "installable": package_name_in_allowlist("ms2deepscore")},
        "ms2query": {**package_status("ms2query"), "installable": package_name_in_allowlist("ms2query")},
        "dreams": {**package_status("dreams"), "installable": package_name_in_allowlist("dreams")},
        "spec2vec": {**package_status("spec2vec"), "installable": package_name_in_allowlist("spec2vec")},
        "rdkit": {**package_status("rdkit"), "installable": package_name_in_allowlist("rdkit")},
        "models": _asset_status(settings.models_dir, "needs_model"),
        "libraries": _asset_status(settings.libraries_dir, "needs_library"),
    }


def package_name_in_allowlist(name: str) -> bool:
    return name in INSTALLABLE_PACKAGES
