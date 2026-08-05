from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


class Ms2QueryRunner:
    """MS2Query library search and optional custom-library creation."""

    def __init__(self, library_dir: Path, ion_mode: str) -> None:
        self.library_dir = Path(library_dir)
        self.ion_mode = ion_mode

    def _ensure_ms2query(self) -> Any:
        try:
            import ms2query
            return ms2query
        except ImportError as exc:
            raise RuntimeError("ms2query is not installed. Install it via /system/packages/install.") from exc

    def ensure_default_models(self) -> None:
        """Download default MS2Query models if none exist in library_dir."""
        ms2query = self._ensure_ms2query()
        from ms2query.run_ms2query import download_zenodo_files
        if not any(self.library_dir.glob("*")):
            self.library_dir.mkdir(parents=True, exist_ok=True)
            download_zenodo_files(self.ion_mode, self.library_dir)

    def build_custom_library_from_mgf(self, mgf_path: Path, output_dir: Path) -> Path:
        """Create a full MS2Query library from an annotated MGF/MSP."""
        ms2query = self._ensure_ms2query()
        from ms2query.clean_and_filter_spectra import clean_normalize_and_split_annotated_spectra
        from ms2query.create_new_library.library_files_creator import LibraryFilesCreator
        from ms2query.utils import load_matchms_spectrum_objects_from_file

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        spectra = load_matchms_spectrum_objects_from_file(str(mgf_path))
        cleaned, _ = clean_normalize_and_split_annotated_spectra(spectra, ion_mode_to_keep=self.ion_mode)
        # Default model files are looked up in library_dir
        model_files = self._select_model_files()
        creator = LibraryFilesCreator(
            cleaned,
            output_directory=str(output_dir),
            ms2ds_model_file_name=model_files["ms2ds"],
            s2v_model_file_name=model_files["s2v"],
        )
        creator.create_all_library_files()
        return output_dir

    def _select_model_files(self) -> dict[str, str]:
        self.ensure_default_models()
        files = {p.name: str(p) for p in self.library_dir.iterdir() if p.is_file()}
        s2v = next((f for name, f in files.items() if "spec2vec" in name.lower() and name.endswith(".model")), "")
        ms2ds = next((f for name, f in files.items() if "ms2deepscore" in name.lower() and name.endswith(".hdf5")), "")
        return {"s2v": s2v, "ms2ds": ms2ds}

    def search(self, query_dir: Path, output_dir: Path) -> Path:
        """Run MS2Query on a directory of query MGF files and return results dir."""
        ms2query = self._ensure_ms2query()
        from ms2query.run_ms2query import run_complete_folder
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        run_complete_folder(
            folder_path=str(query_dir),
            model_folder=str(self.library_dir),
            output_folder=str(output_dir),
            ionisation_mode=self.ion_mode,
        )
        return output_dir

    def parse_results(self, results_csv: Path) -> list[dict[str, Any]]:
        """Parse MS2Query results CSV into unified annotation rows."""
        import csv
        rows: list[dict[str, Any]] = []
        if not results_csv.exists():
            return rows
        with results_csv.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for idx, row in enumerate(reader, start=1):
                rows.append({
                    "feature_id": row.get("spectrum_id", row.get("query_spectrum_id", f"MS2Q{idx:04d}")),
                    "mz": row.get("precursor_mz"),
                    "rt": row.get("retention_time"),
                    "candidate_name": row.get("name") or row.get("compound_name"),
                    "smiles": row.get("smiles"),
                    "inchikey": row.get("inchikey"),
                    "ms2query_score": float(row.get("ms2query_score", 0) or 0),
                    "annotation_source": "ms2query",
                })
        return rows
