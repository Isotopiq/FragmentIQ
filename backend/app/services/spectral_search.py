from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from app.core.config import settings


def _parse_peak_line(line: str) -> tuple[float, float] | None:
    """Parse a single 'm/z intensity' line from MGF or MSP formats."""
    parts = line.strip().split()
    if len(parts) < 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None


def _parse_meta_value(line: str) -> tuple[str, str] | None:
    """Parse MGF/MSP style key=value or key: value lines."""
    delimiter = None
    if "=" in line:
        delimiter = "="
    elif ":" in line:
        delimiter = ":"
    else:
        return None
    key, value = line.split(delimiter, 1)
    return key.strip().upper(), value.strip()


def _parse_mgf(path: Path) -> list[dict[str, Any]]:
    """Very small, dependency-free MGF parser for mock spectral search."""
    spectra = []
    current: dict[str, Any] = {"peaks": []}
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.upper().startswith("BEGIN IONS"):
                current = {"peaks": []}
                continue
            if line.upper().startswith("END IONS"):
                if current["peaks"]:
                    spectra.append(current)
                continue
            if not line[0].isdigit():
                meta = _parse_meta_value(line)
                if meta:
                    key, value = meta
                    if key in {"PEPMASS", "PRECURSORMZ", "PRECURSOR_MZ"}:
                        current["precursor_mz"] = float(value.split()[0])
                    if key in {"NAME", "TITLE", "COMPOUND_NAME"}:
                        current["candidate_name"] = value
                    if key == "FORMULA":
                        current["formula"] = value
                    if key == "SMILES":
                        current["smiles"] = value
                    if key == "INCHIKEY":
                        current["inchikey"] = value
                    continue
            peak = _parse_peak_line(line)
            if peak:
                current["peaks"].append(peak)
    return spectra


def _parse_msp(path: Path) -> list[dict[str, Any]]:
    """Very small, dependency-free MSP parser for mock spectral search."""
    spectra = []
    current: dict[str, Any] = {"peaks": []}
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                if current["peaks"]:
                    spectra.append(current)
                    current = {"peaks": []}
                continue
            if not line[0].isdigit():
                meta = _parse_meta_value(line)
                if meta:
                    key, value = meta
                    if key in {"PRECURSORMZ", "PRECURSOR_MZ", "PRECURSOR"}:
                        current["precursor_mz"] = float(re.split(r"[\s\t]", value, maxsplit=1)[0])
                    if key in {"NAME", "TITLE", "COMPOUND_NAME", "COMPOUND"}:
                        current["candidate_name"] = value
                    if key == "FORMULA":
                        current["formula"] = value
                    if key == "SMILES":
                        current["smiles"] = value
                    if key == "INCHIKEY":
                        current["inchikey"] = value
                    continue
            peak = _parse_peak_line(line)
            if peak:
                current["peaks"].append(peak)
    if current["peaks"]:
        spectra.append(current)
    return spectra


def _load_library_spectra(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".mgf":
        return _parse_mgf(path)
    if suffix == ".msp":
        return _parse_msp(path)
    raise ValueError(f"Unsupported spectral library format: {suffix}")


def _normalize_peaks(peaks: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not peaks:
        return []
    max_intensity = max(intensity for _, intensity in peaks) or 1.0
    return [(mz, intensity / max_intensity) for mz, intensity in peaks]


def _simple_cosine(
    query: list[tuple[float, float]],
    reference: list[tuple[float, float]],
    tolerance: float = 0.1,
) -> tuple[float, int]:
    """Greedy peak-matching cosine similarity with a fixed m/z tolerance."""
    matched = 0
    dot = 0.0
    used = set()
    for q_mz, q_int in query:
        best_idx = -1
        best_similarity = -1.0
        for idx, (r_mz, r_int) in enumerate(reference):
            if idx in used:
                continue
            if abs(q_mz - r_mz) <= tolerance:
                similarity = q_int * r_int
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_idx = idx
        if best_idx >= 0:
            used.add(best_idx)
            dot += best_similarity
            matched += 1

    q_norm = math.sqrt(sum(intensity * intensity for _, intensity in query)) or 1.0
    r_norm = math.sqrt(sum(intensity * intensity for _, intensity in reference)) or 1.0
    cosine = dot / (q_norm * r_norm)
    return float(cosine), matched


def _cosine_between_peaks(
    query: list[tuple[float, float]],
    reference: list[tuple[float, float]],
    tolerance: float = 0.1,
) -> tuple[float, int]:
    """Return (cosine, matched_peaks) using matchms when available."""
    try:
        import numpy as np
        from matchms import Spectrum
        from matchms.similarity import CosineGreedy

        q_mzs = np.array([p[0] for p in query], dtype=float)
        q_ints = np.array([p[1] for p in query], dtype=float)
        r_mzs = np.array([p[0] for p in reference], dtype=float)
        r_ints = np.array([p[1] for p in reference], dtype=float)
        q_spec = Spectrum(mz=q_mzs, intensities=q_ints)
        r_spec = Spectrum(mz=r_mzs, intensities=r_ints)
        sim, n_matches = CosineGreedy(tolerance=tolerance).pair(q_spec, r_spec)
        return float(sim), int(n_matches)
    except Exception:
        return _simple_cosine(query, reference, tolerance=tolerance)


def _precursor_match(q_mz: float | None, r_mz: float | None, tolerance: float) -> bool:
    if q_mz is None or r_mz is None:
        return True
    return abs(q_mz - r_mz) <= tolerance


def _matchms_search(
    query: dict[str, Any],
    library_spectra: list[dict[str, Any]],
    library_id: int,
    library_name: str,
    threshold: float,
    min_matched_peaks: int,
    top_k: int,
    precursor_tolerance: float,
    mz_tolerance: float,
) -> list[dict[str, Any]]:
    """Run matchms cosine search when available, otherwise use the simple matcher."""
    try:
        from matchms import calculate_scores
        from matchms import Spectrum
        from matchms.similarity import CosineGreedy, PrecursorMzMatch
        import numpy as np

        q_mzs = np.array([p[0] for p in query["peaks"]], dtype=float)
        q_ints = np.array([p[1] for p in query["peaks"]], dtype=float)
        q_spec = Spectrum(mz=q_mzs, intensities=q_ints, metadata={"precursor_mz": query.get("precursor_mz")})
        ref_specs = []
        for idx, ref in enumerate(library_spectra):
            r_mzs = np.array([p[0] for p in ref["peaks"]], dtype=float)
            r_ints = np.array([p[1] for p in ref["peaks"]], dtype=float)
            ref_specs.append(
                Spectrum(
                    mz=r_mzs,
                    intensities=r_ints,
                    metadata={
                        "precursor_mz": ref.get("precursor_mz"),
                        "compound_name": ref.get("candidate_name"),
                        "library_index": idx,
                    },
                )
            )
        similarity = CosineGreedy(tolerance=mz_tolerance)
        precursor_match = PrecursorMzMatch(tolerance=precursor_tolerance, tolerance_type="Dalton")
        scores = calculate_scores([q_spec], ref_specs, [similarity, precursor_match])

        hits = []
        for li, ref in enumerate(library_spectra):
            sim, n_matches = scores.scores[0, li][0]
            precursor_ok = scores.scores[0, li][1]
            if not precursor_ok:
                continue
            if sim < threshold:
                continue
            if n_matches < min_matched_peaks:
                continue
            hits.append({
                "score": float(sim),
                "matched_peaks": int(n_matches),
                "reference": ref,
                "library_index": li,
            })
        hits.sort(key=lambda x: x["score"], reverse=True)
        return _format_hits(query, hits[:top_k], library_id, library_name, "matchms")
    except Exception:
        return _simple_search(query, library_spectra, library_id, library_name, threshold, min_matched_peaks, top_k, precursor_tolerance, mz_tolerance)


def _simple_search(
    query: dict[str, Any],
    library_spectra: list[dict[str, Any]],
    library_id: int,
    library_name: str,
    threshold: float,
    min_matched_peaks: int,
    top_k: int,
    precursor_tolerance: float,
    mz_tolerance: float,
) -> list[dict[str, Any]]:
    """Dependency-free cosine search used in mock mode or as a fallback."""
    q_mz = query.get("precursor_mz")
    hits = []
    for idx, ref in enumerate(library_spectra):
        if not _precursor_match(q_mz, ref.get("precursor_mz"), precursor_tolerance):
            continue
        score, matched = _cosine_between_peaks(query["peaks"], ref["peaks"], tolerance=mz_tolerance)
        if score < threshold or matched < min_matched_peaks:
            continue
        hits.append({
            "score": score,
            "matched_peaks": matched,
            "reference": ref,
            "library_index": idx,
        })
    hits.sort(key=lambda x: x["score"], reverse=True)
    return _format_hits(query, hits[:top_k], library_id, library_name, "simple_cosine")


def _format_hits(
    query: dict[str, Any],
    hits: list[dict[str, Any]],
    library_id: int,
    library_name: str,
    source: str,
) -> list[dict[str, Any]]:
    results = []
    for rank, hit in enumerate(hits, start=1):
        ref = hit["reference"]
        results.append({
            "rank": rank,
            "candidate_name": ref.get("candidate_name") or f"library_{hit['library_index']}",
            "formula": ref.get("formula"),
            "smiles": ref.get("smiles"),
            "inchikey": ref.get("inchikey"),
            "precursor_mz": ref.get("precursor_mz"),
            "library_id": library_id,
            "library_name": library_name,
            "score": round(hit["score"], 4),
            "matched_peaks": hit["matched_peaks"],
            "annotation_source": source,
            "query_peaks": query["peaks"],
            "reference_peaks": ref["peaks"],
        })
    return results


def search_unknown_spectrum(payload: dict[str, Any]) -> dict[str, Any]:
    """Search a single query spectrum against selected MGF/MSP libraries."""
    from sqlmodel import Session

    from app.core.database import engine
    from app.models.domain import LibraryAsset

    engine_name = payload.get("engine", "matchms")
    library_ids = payload.get("library_ids", [])
    precursor_mz = payload.get("precursor_mz")
    peaks = payload.get("peaks", [])
    if not peaks:
        raise ValueError("'peaks' are required for spectral search")
    if not isinstance(peaks, list):
        raise ValueError("'peaks' must be a list of [m/z, intensity] tuples")

    # Normalize peak input to list of (mz, intensity) tuples
    normalized_peaks: list[tuple[float, float]] = []
    for item in peaks:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            normalized_peaks.append((float(item[0]), float(item[1])))
        elif isinstance(item, dict):
            mz = float(item.get("mz", item.get("m/z", 0)))
            intensity = float(item.get("intensity", item.get("i", 0)))
            normalized_peaks.append((mz, intensity))

    query = {
        "precursor_mz": float(precursor_mz) if precursor_mz is not None else None,
        "peaks": normalized_peaks,
    }

    threshold = float(payload.get("cosine_threshold", 0.7))
    min_matched_peaks = int(payload.get("min_matched_peaks", 3))
    top_k = int(payload.get("top_k", settings.matchms_top_k))
    precursor_tolerance = float(payload.get("precursor_tolerance", 0.01))
    mz_tolerance = float(payload.get("mz_tolerance", 0.1))

    all_candidates: list[dict[str, Any]] = []
    with Session(engine) as session:
        for library_id in library_ids:
            asset = session.get(LibraryAsset, library_id)
            if not asset:
                continue
            path = Path(asset.path)
            if not path.exists():
                continue
            try:
                library_spectra = _load_library_spectra(path)
            except Exception:
                continue
            if not library_spectra:
                continue

            if engine_name == "matchms":
                candidates = _matchms_search(
                    query,
                    library_spectra,
                    library_id,
                    asset.name,
                    threshold,
                    min_matched_peaks,
                    top_k,
                    precursor_tolerance,
                    mz_tolerance,
                )
            else:
                # MS2Query / DreaMS / generic engines fall back to simple cosine in this MVP;
                # a real deployment would call the respective engine runner.
                candidates = _simple_search(
                    query,
                    library_spectra,
                    library_id,
                    asset.name,
                    threshold,
                    min_matched_peaks,
                    top_k,
                    precursor_tolerance,
                    mz_tolerance,
                )
            all_candidates.extend(candidates)

    all_candidates.sort(key=lambda x: x["score"], reverse=True)
    final = all_candidates[:top_k]
    for rank, candidate in enumerate(final, start=1):
        candidate["rank"] = rank

    return {
        "engine": engine_name,
        "query": {
            "precursor_mz": query["precursor_mz"],
            "num_peaks": len(query["peaks"]),
            "peaks": query["peaks"],
        },
        "candidates": final,
    }


def search_spectra_against_libraries(
    queries: list[dict[str, Any]],
    engine_name: str,
    library_ids: list[int],
    threshold: float,
    min_matched_peaks: int,
    top_k: int,
    precursor_tolerance: float,
    mz_tolerance: float,
) -> list[dict[str, Any]]:
    """Search many query spectra against selected MGF/MSP libraries and return annotation rows."""
    from sqlmodel import Session

    from app.core.database import engine
    from app.models.domain import LibraryAsset

    annotations: list[dict[str, Any]] = []
    with Session(engine) as session:
        for library_id in library_ids:
            asset = session.get(LibraryAsset, library_id)
            if not asset:
                continue
            path = Path(asset.path)
            if not path.exists():
                continue
            try:
                library_spectra = _load_library_spectra(path)
            except Exception:
                continue
            if not library_spectra:
                continue

            for query in queries:
                if engine_name == "matchms":
                    hits = _matchms_search(
                        query,
                        library_spectra,
                        library_id,
                        asset.name,
                        threshold,
                        min_matched_peaks,
                        top_k,
                        precursor_tolerance,
                        mz_tolerance,
                    )
                else:
                    hits = _simple_search(
                        query,
                        library_spectra,
                        library_id,
                        asset.name,
                        threshold,
                        min_matched_peaks,
                        top_k,
                        precursor_tolerance,
                        mz_tolerance,
                    )
                for hit in hits:
                    annotations.append({
                        "feature_id": query.get("feature_id", "unknown"),
                        "mz": query.get("precursor_mz"),
                        "rt": query.get("retention_time"),
                        "candidate_name": hit["candidate_name"],
                        "formula": hit.get("formula"),
                        "smiles": hit.get("smiles"),
                        "inchikey": hit.get("inchikey"),
                        "matchms_cosine": hit["score"],
                        "matched_peaks": hit["matched_peaks"],
                        "annotation_source": hit["annotation_source"],
                        "library_id": library_id,
                        "library_name": asset.name,
                    })
    return annotations
