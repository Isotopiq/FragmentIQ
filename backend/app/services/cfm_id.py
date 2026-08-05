from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.core.config import settings


class CfmIdRunner:
    """CFM-ID spectrum prediction, compound identification, and model training."""

    def __init__(self, predict_binary: str, identify_binary: str, train_binary: str, model_dir: Path) -> None:
        self.predict_binary = predict_binary
        self.identify_binary = identify_binary
        self.train_binary = train_binary
        self.model_dir = Path(model_dir)

    def _param_files(self, ion_mode: str) -> tuple[Path, Path]:
        """Pick pre-trained CFM param_output*.log and param_config.txt for the ion mode."""
        candidates = sorted(self.model_dir.glob("**/param_output*.log"))
        if not candidates:
            raise RuntimeError(f"No CFM model param_output*.log files found in {self.model_dir}")
        param_file = candidates[0]
        # Look for config in the same directory
        config_files = list(param_file.parent.glob("param_config*.txt"))
        config_file = config_files[0] if config_files else self.model_dir / "param_config.txt"
        if not config_file.exists():
            raise RuntimeError(f"CFM config file not found for {param_file}")
        return param_file, config_file

    def predict_spectrum(
        self,
        smiles_or_inchi: str,
        output_file: Path,
        ion_mode: str = "+",
        prob_thresh: float = 0.001,
        apply_postproc: bool = True,
    ) -> Path:
        """Run cfm-predict and return the predicted spectra file."""
        executable = shutil.which(self.predict_binary) or self.predict_binary
        param_file, config_file = self._param_files(ion_mode)
        args = [
            executable,
            smiles_or_inchi,
            str(prob_thresh),
            str(param_file),
            str(config_file),
            "0",  # annotate_fragments
            str(output_file),
            "1" if apply_postproc else "0",
            "1",  # suppress_exceptions
        ]
        subprocess.run(args, check=True, text=True, capture_output=True)
        return output_file

    def identify_compound(
        self,
        spectrum_file: Path,
        candidate_file: Path,
        output_file: Path,
        ion_mode: str = "+",
        score_type: str = "DotProduct",
        num_highest: int = 10,
        ppm_mass_tol: float = 10.0,
        abs_mass_tol: float = 0.01,
    ) -> list[dict[str, Any]]:
        """Run cfm-id and parse ranked candidates."""
        executable = shutil.which(self.identify_binary) or self.identify_binary
        param_file, config_file = self._param_files(ion_mode)
        args = [
            executable,
            str(spectrum_file),
            "query",
            str(candidate_file),
            str(num_highest),
            str(ppm_mass_tol),
            str(abs_mass_tol),
            "0.001",
            str(param_file),
            str(config_file),
            score_type,
            "1",  # apply_postprocessing
            str(output_file),
        ]
        completed = subprocess.run(args, check=True, text=True, capture_output=True)
        return self._parse_identify_output(output_file, completed.stdout)

    def _parse_identify_output(self, output_file: Path, stdout: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        text = output_file.read_text(encoding="utf-8") if output_file.exists() else stdout
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for rank, line in enumerate(lines[:50], start=1):
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            score, _id, smiles = parts[0], parts[1], parts[2]
            rows.append({
                "feature_id": "query",
                "cfm_score": float(score),
                "cfm_rank": rank,
                "candidate_id": _id,
                "smiles": smiles,
                "annotation_source": "cfm_id",
            })
        return rows

    def train_model(
        self,
        input_filename: Path,
        feature_filename: Path,
        config_filename: Path,
        spec_dir: Path,
        output_dir: Path,
        group: int | None = None,
    ) -> Path:
        """Run cfm-train and return the directory containing trained model files."""
        executable = shutil.which(self.train_binary) or self.train_binary
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        status_file = output_dir / "cfm_train_status.log"
        args = [
            executable,
            str(input_filename),
            str(feature_filename),
            str(config_filename),
            str(spec_dir),
            str(group) if group is not None else "-1",
            str(status_file),
            "0",  # no_train = False
            "0",  # start_energy
        ]
        subprocess.run(args, check=True, text=True, capture_output=True)
        return output_dir
