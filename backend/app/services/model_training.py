from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.storage import safe_child
from app.models.domain import Job, ModelAsset
from app.services.cfm_id import CfmIdRunner


class ModelTrainingPayload:
    name: str
    engine: str
    base_model_id: int | None
    training_file_id: int | None
    parameters: dict[str, Any]


def train_dreams(
    dataset_hdf5: Path,
    pretrained_pth: Path | None,
    params: dict[str, Any],
    output_dir: Path,
) -> Path:
    """Wrap DreaMS training/train.py for fine-tuning or pre-training."""
    try:
        import dreams
    except ImportError as exc:
        raise RuntimeError("DreaMS is not installed. Install 'dreams' via /system/packages/install.") from exc
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    import subprocess
    import sys

    command = [
        sys.executable,
        "-m",
        "dreams.training.train",
        "--project_name", params.get("project_name", "FragmentIQ"),
        "--job_key", params.get("job_key", "dreams_train"),
        "--run_name", params.get("run_name", "dreams_run"),
        "--train_objective", params.get("train_objective", "mol_props"),
        "--train_regime", params.get("train_regime", "fine-tuning"),
        "--dataset_pth", str(dataset_hdf5),
        "--dformat", params.get("dformat", "A"),
        "--model", params.get("model", "DreaMS"),
        "--lr", str(params.get("lr", 3e-5)),
        "--batch_size", str(params.get("batch_size", 64)),
        "--max_epochs", str(params.get("max_epochs", 10)),
        "--log_every_n_steps", str(params.get("log_every_n_steps", 5)),
        "--seed", str(params.get("seed", 3407)),
        "--save_top_k", str(params.get("save_top_k", -1)),
        "--output_dir", str(output_dir),
    ]
    if pretrained_pth:
        command.extend(["--pre_trained_pth", str(pretrained_pth)])
    subprocess.run(command, check=True, text=True, capture_output=True)
    return output_dir


def train_ms2query(
    spectrum_file: Path,
    ion_mode: str,
    output_dir: Path,
) -> Path:
    """Wrap MS2Query custom library/model training."""
    try:
        from ms2query.create_new_library.train_models import clean_and_train_models
    except ImportError as exc:
        raise RuntimeError("ms2query is not installed.") from exc
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    clean_and_train_models(
        spectrum_file=str(spectrum_file),
        ion_mode=ion_mode,
        output_folder=str(output_dir),
    )
    return output_dir


def train_cfm(
    input_filename: Path,
    feature_filename: Path,
    config_filename: Path,
    spec_dir: Path,
    output_dir: Path,
    group: int | None = None,
) -> Path:
    """Wrap CFM-ID model training."""
    runner = CfmIdRunner(
        predict_binary=settings.cfm_binary,
        identify_binary=settings.cfm_id_binary,
        train_binary=settings.cfm_train_binary,
        model_dir=Path(settings.models_dir) / "cfm",
    )
    return runner.train_model(input_filename, feature_filename, config_filename, spec_dir, output_dir, group)


def run_model_training_job(job: Job, run_dir: Path) -> None:
    """Dispatch model training based on job.parameters['engine']."""
    params = job.parameters or {}
    engine = params.get("engine")
    output_dir = safe_child(run_dir, "model")
    training_file_id = params.get("training_file_id")
    base_model_id = params.get("base_model_id")

    if engine == "dreams":
        from app.core.storage import project_dir
        dataset = Path(params.get("dataset_path") or project_dir(job.project_id) / f"training_{training_file_id}.hdf5")
        pretrained = None
        if base_model_id:
            # Locate base model path
            pretrained = Path(params.get("base_model_path"))
        train_dreams(dataset, pretrained, params, output_dir)
    elif engine == "ms2query":
        spectrum_file = Path(params.get("spectrum_path"))
        train_ms2query(spectrum_file, params.get("ion_mode", "positive"), output_dir)
    elif engine == "cfm-id":
        input_filename = Path(params["input_filename"])
        feature_filename = Path(params["feature_filename"])
        config_filename = Path(params["config_filename"])
        spec_dir = Path(params["spec_dir"])
        train_cfm(input_filename, feature_filename, config_filename, spec_dir, output_dir, params.get("group"))
    else:
        raise ValueError(f"Unsupported model training engine: {engine}")

    # Persist a ModelAsset for the newly trained model
    import os
    import shutil
    from sqlmodel import Session
    from app.core.database import engine as db_engine
    from app.models.domain import ModelAsset

    model_asset_dir = safe_child(Path(settings.models_dir) / engine, f"job_{job.id}")
    if model_asset_dir.exists():
        shutil.rmtree(model_asset_dir)
    shutil.copytree(output_dir, model_asset_dir)

    with Session(db_engine) as session:
        model = session.get(ModelAsset, params.get("model_asset_id"))
        if model:
            model.status = "ready"
            model.path = str(model_asset_dir)
            model.size_bytes = sum(f.stat().st_size for f in model_asset_dir.rglob("*") if f.is_file())
            session.add(model)
            session.commit()
