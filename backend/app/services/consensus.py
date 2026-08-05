from __future__ import annotations

from typing import Any


DEFAULT_WEIGHTS = {
    "sirius_structure_score": 0.3,
    "sirius_formula_score": 0.2,
    "matchms_cosine": 0.2,
    "ms2deepscore": 0.15,
    "ms2query_score": 0.1,
    "dreams_score": 0.05,
    "cfm_score": 0.1,
}


def _normalize_score(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _match_key(row: dict[str, Any]) -> str:
    return f"{row.get('feature_id', '')}_{row.get('mz', '')}_{row.get('rt', '')}"


def merge_annotations(
    feature_rows: list[dict[str, Any]],
    sirius_rows: list[dict[str, Any]] | None = None,
    ms2query_rows: list[dict[str, Any]] | None = None,
    dreams_rows: list[dict[str, Any]] | None = None,
    matchms_rows: list[dict[str, Any]] | None = None,
    cfm_rows: list[dict[str, Any]] | None = None,
    weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """
    Join annotation rows by feature_id, normalize per-engine scores,
    compute weighted consensus score and confidence label.
    """
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    by_feature: dict[str, dict[str, Any]] = {}

    def ensure(feature_id: str, mz: Any = None, rt: Any = None) -> dict[str, Any]:
        key = f"{feature_id}_{mz}_{rt}"
        if key not in by_feature:
            by_feature[key] = {
                "feature_id": feature_id,
                "mz": mz,
                "rt": rt,
                "candidates": {},
                "scores": {},
                "sources": [],
            }
        return by_feature[key]

    def add_rows(rows: list[dict[str, Any]] | None, score_key: str, source: str) -> None:
        if not rows:
            return
        for row in rows:
            fid = row.get("feature_id") or "unknown"
            entry = ensure(fid, row.get("mz"), row.get("rt"))
            smiles = row.get("smiles")
            key = smiles or row.get("candidate_name") or row.get("formula") or f"{source}_{id(row)}"
            if key not in entry["candidates"]:
                entry["candidates"][key] = {
                    "smiles": smiles,
                    "candidate_name": row.get("candidate_name"),
                    "formula": row.get("formula"),
                    "inchikey": row.get("inchikey"),
                }
            score = _normalize_score(row.get(score_key, 0))
            entry["scores"][score_key] = max(entry["scores"].get(score_key, 0), score)
            entry["sources"].append(source)
            # Keep best candidate metadata per source
            if source == "sirius_api" or source == "sirius":
                entry["candidates"][key]["formula"] = row.get("formula") or entry["candidates"][key].get("formula")

    add_rows(sirius_rows, "sirius_structure_score", "sirius")
    add_rows(ms2query_rows, "ms2query_score", "ms2query")
    add_rows(dreams_rows, "dreams_score", "dreams")
    add_rows(matchms_rows, "matchms_cosine", "matchms")
    add_rows(cfm_rows, "cfm_score", "cfm_id")

    results: list[dict[str, Any]] = []
    for entry in by_feature.values():
        consensus = 0.0
        total_weight = 0.0
        for key, weight in weights.items():
            if key in entry["scores"]:
                consensus += entry["scores"][key] * weight
                total_weight += weight
        if total_weight:
            consensus = round(consensus / total_weight, 4)
        else:
            consensus = 0.0

        best_candidate = next(iter(entry["candidates"].values()), {}) if entry["candidates"] else {}
        confidence = "high" if consensus >= 0.8 else "medium" if consensus >= 0.55 else "low"
        results.append({
            **best_candidate,
            "feature_id": entry["feature_id"],
            "mz": entry["mz"],
            "rt": entry["rt"],
            **entry["scores"],
            "annotation_sources": sorted(set(entry["sources"])),
            "consensus_score": consensus,
            "confidence_level": confidence,
        })
    return sorted(results, key=lambda r: r["consensus_score"], reverse=True)
