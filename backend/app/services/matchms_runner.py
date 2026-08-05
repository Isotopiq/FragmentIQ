from __future__ import annotations

from pathlib import Path
from typing import Any


def _ensure_matchms() -> Any:
    try:
        import matchms
        return matchms
    except ImportError as exc:
        raise RuntimeError("matchms is not installed. Install it via /system/packages/install.") from exc


def load_spectra(path: Path) -> list[Any]:
    """Load mzML/mzXML/MGF/MSP into matchms Spectrum objects."""
    matchms = _ensure_matchms()
    suffix = path.suffix.lower()
    if suffix == ".mgf":
        from matchms.importing import load_from_mgf
        return list(load_from_mgf(str(path)))
    if suffix == ".msp":
        from matchms.importing import load_from_msp
        return list(load_from_msp(str(path)))
    from matchms.importing import load_spectra as _load
    return list(_load(str(path)))


def run_matchms_library_search(
    query_spectra: list[Any],
    library_spectra: list[Any],
    cosine_threshold: float = 0.7,
    min_matched_peaks: int = 6,
    top_k: int = 5,
    use_modified_cosine: bool = True,
    precursor_mz_tolerance: float = 0.01,
) -> list[dict[str, Any]]:
    """
    For each query spectrum, score against the library using (modified) cosine,
    filter by precursor m/z, and return top-k hits.
    """
    _ensure_matchms()
    from matchms import calculate_scores
    from matchms.similarity import CosineGreedy, ModifiedCosine, PrecursorMzMatch

    similarity_function = ModifiedCosine() if use_modified_cosine else CosineGreedy()
    precursor_match = PrecursorMzMatch(tolerance=precursor_mz_tolerance, tolerance_type="Dalton")

    scores = calculate_scores(query_spectra, library_spectra, [similarity_function, precursor_match])

    results: list[dict[str, Any]] = []
    for qi, query in enumerate(query_spectra):
        q_id = query.get("spectrum_id") or f"Q{qi:04d}"
        q_mz = query.get("precursor_mz")
        q_rt = query.get("retention_time")
        hits = []
        for li, library in enumerate(library_spectra):
            sim, n_matches = scores.scores[qi, li][0]
            precursor_ok = scores.scores[qi, li][1]
            if not precursor_ok:
                continue
            if sim < cosine_threshold:
                continue
            if n_matches < min_matched_peaks:
                continue
            hits.append({
                "library_index": li,
                "score": float(sim),
                "matched_peaks": int(n_matches),
            })
        hits.sort(key=lambda x: x["score"], reverse=True)
        for rank, hit in enumerate(hits[:top_k], start=1):
            lib = library_spectra[hit["library_index"]]
            results.append({
                "feature_id": q_id,
                "mz": q_mz,
                "rt": q_rt,
                "candidate_name": lib.get("compound_name") or lib.get("name"),
                "smiles": lib.get("smiles"),
                "inchikey": lib.get("inchikey"),
                "matchms_cosine": round(hit["score"], 4),
                "matched_peaks": hit["matched_peaks"],
                "matchms_rank": rank,
                "annotation_source": "matchms",
            })
    return results
