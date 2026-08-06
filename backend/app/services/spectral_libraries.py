from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.models.domain import LibraryAsset


def _spectra_module() -> Any:
    try:
        from matchms import Spectrum
        from matchms.exporting import save_as_mgf
        from matchms.importing import load_from_mgf, load_from_msp
        return {"Spectrum": Spectrum, "save_as_mgf": save_as_mgf, "load_from_mgf": load_from_mgf, "load_from_msp": load_from_msp}
    except ImportError as exc:
        raise RuntimeError("matchms is required for spectral-library processing. Install it via /system/packages/install.") from exc


def parse_library_metadata(path: Path) -> dict[str, Any]:
    """Return format, spectrum count, guessed ion mode, and metadata keys."""
    suffix = path.suffix.lower()
    if suffix not in {".mgf", ".msp"}:
        raise ValueError(f"Unsupported spectral library format: {suffix}")
    mod = _spectra_module()
    loader = mod["load_from_mgf"] if suffix == ".mgf" else mod["load_from_msp"]
    spectra = list(loader(str(path)))
    keys: set[str] = set()
    ion_mode: str | None = None
    for spec in spectra:
        meta = spec.metadata if hasattr(spec, "metadata") else getattr(spec, "meta", {})
        if hasattr(spec, "metadata"):
            keys.update(spec.metadata.keys())
        if not ion_mode:
            for key in ("ion_mode", "ionmode", "ion_mode", "polarity"):
                val = meta.get(key)
                if val:
                    ion_mode = str(val).lower()
                    break
    return {
        "format": suffix.lstrip("."),
        "spectrum_count": len(spectra),
        "ion_mode": ion_mode or "unknown",
        "metadata_keys": sorted(keys),
    }


def ensure_normalized_mgf(path: Path, cache_dir: Path) -> Path:
    """Convert MSP -> MGF once, cache it, and return the MGF path used by matchms/DreaMS."""
    suffix = path.suffix.lower()
    if suffix == ".mgf":
        return path
    if suffix != ".msp":
        raise ValueError(f"Cannot normalize {suffix} to MGF")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{path.stem}.mgf"
    if cached.exists():
        return cached
    mod = _spectra_module()
    spectra = list(mod["load_from_msp"](str(path)))
    mod["save_as_mgf"](str(cached), spectra)
    return cached


def index_spectral_library(asset: LibraryAsset) -> dict[str, Any]:
    """Parse MGF/MSP, cache normalized MGF, and store summary in asset.extra_metadata."""
    path = Path(asset.path)
    suffix = path.suffix.lower()
    if suffix not in {".mgf", ".msp"}:
        raise ValueError(f"Library asset {asset.id} is not MGF/MSP: {suffix}")
    meta = parse_library_metadata(path)
    cache_dir = Path("./data/libraries/.cache")
    normalized = ensure_normalized_mgf(path, cache_dir)
    meta["normalized_mgf"] = str(normalized)
    asset.library_format = meta["format"]
    asset.ion_mode = meta["ion_mode"] if meta["ion_mode"] != "unknown" else asset.ion_mode
    asset.extra_metadata = {**asset.extra_metadata, "library_summary": meta}
    asset.indexed = True
    return meta
