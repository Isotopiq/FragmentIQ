from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd


def detect_delimiter_from_text(text: str, fallback: str | None = None) -> str:
    if fallback:
        return "\t" if fallback in {"tab", "\\t", "tsv"} else fallback
    sample = text[:4096]
    return "\t" if sample.count("\t") > sample.count(",") else ","


def parse_metadata_text(text: str, delimiter: str | None = None) -> dict[str, Any]:
    sep = detect_delimiter_from_text(text, delimiter)
    reader = csv.DictReader(StringIO(text), delimiter=sep)
    rows = [{key: (value or "") for key, value in row.items()} for row in reader]
    columns = reader.fieldnames or []
    return {"columns": columns, "rows": rows, "delimiter": sep}


def validate_metadata_rows(columns: list[str], rows: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    normalized = {column.lower() for column in columns}
    if "sample_name" not in normalized and "sample" not in normalized and "filename" not in normalized:
        warnings.append("Metadata should include a sample_name, sample, or filename column.")
    sample_column = next((column for column in columns if column.lower() in {"sample_name", "sample", "filename"}), None)
    if sample_column:
        names = [str(row.get(sample_column, "")).strip() for row in rows]
        missing = [idx + 1 for idx, name in enumerate(names) if not name]
        duplicates = sorted({name for name in names if name and names.count(name) > 1})
        if missing:
            warnings.append(f"Missing sample names in rows: {', '.join(map(str, missing[:10]))}")
        if duplicates:
            warnings.append(f"Duplicated sample names: {', '.join(duplicates[:10])}")
    if rows and not any(column.lower() in {"condition", "treatment", "group"} for column in columns):
        warnings.append("No condition/treatment/group column detected; define at least one grouping factor before statistics.")
    return warnings


def parse_feature_table(path: Path, max_rows: int | None = None) -> dict[str, Any]:
    sep = "\t" if path.suffix.lower() == ".tsv" else None
    if sep is None:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            sep = detect_delimiter_from_text(handle.read(4096))
    warnings: list[str] = []
    try:
        frame = pd.read_csv(path, sep=sep, nrows=max_rows)
    except Exception as exc:
        return {"columns": [], "rows": [], "warnings": [f"Unable to parse table: {exc}"]}
    if frame.empty:
        warnings.append("Parsed table is empty.")
    return {"columns": list(frame.columns), "rows": frame.fillna("").to_dict(orient="records"), "warnings": warnings}


def parse_table(path: Path, max_rows: int | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    parsed = parse_feature_table(path, max_rows=max_rows)
    return parsed["rows"], parsed["warnings"]


def normalize_feature_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aliases = {
        "feature_id": ["feature_id", "id", "row id", "peak_id", "feature"],
        "mz": ["mz", "m/z", "row mz", "mass"],
        "rt": ["rt", "retention_time", "row retention time", "retention time"],
        "intensity": ["intensity", "area", "height", "sample_control_mean"],
    }
    normalized: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        lowered = {str(key).strip().lower(): value for key, value in row.items()}
        item: dict[str, Any] = {"feature_id": str(idx), "original": row}
        for target, names in aliases.items():
            for name in names:
                if name in lowered and lowered[name] not in ("", None):
                    item[target] = lowered[name]
                    break
        normalized.append(item)
    return normalized


def parse_mzmine_outputs(output_dir: Path) -> dict[str, Any]:
    """Parse common MZmine table exports without assuming a specific desktop module set."""
    warnings: list[str] = []
    candidates = [
        *output_dir.glob("*feature*.csv"),
        *output_dir.glob("*feature*.tsv"),
        *output_dir.glob("*quant*.csv"),
        *output_dir.glob("*quant*.tsv"),
        *output_dir.glob("*.mztab"),
    ]
    if not candidates:
        return {"features": [], "warnings": ["No supported MZmine feature/quant table export was found."]}
    parsed = parse_feature_table(candidates[0])
    warnings.extend(parsed["warnings"])
    rows = normalize_feature_records(parsed["rows"])
    features = [
        {
            **row.get("original", {}),
            "feature_id": row.get("feature_id"),
            "mz": row.get("mz", ""),
            "rt": row.get("rt", ""),
            "intensity": row.get("intensity", ""),
        }
        for row in rows
    ]
    return {"features": features, "warnings": warnings}


def parse_sirius_outputs(output_dir: Path) -> dict[str, Any]:
    """Parse supported SIRIUS TSV exports into the unified annotation shape."""
    warnings: list[str] = []
    files = [
        "formula_identifications.tsv",
        "structure_identifications.tsv",
        "canopus_formula_summary.tsv",
        "canopus_structure_summary.tsv",
        "denovo_structure_identifications.tsv",
        "spectral_matches.tsv",
        "spectral_matches_analog.tsv",
    ]
    by_feature: dict[str, dict[str, Any]] = {}
    for filename in files:
        path = output_dir / filename
        if not path.exists():
            continue
        parsed = parse_feature_table(path)
        warnings.extend(parsed["warnings"])
        source = filename.removesuffix(".tsv")
        for idx, row in enumerate(parsed["rows"], start=1):
            lowered = {str(key).strip().lower(): value for key, value in row.items()}
            feature_id = lowered.get("id") or lowered.get("feature_id") or lowered.get("mappingfeatureid") or str(idx)
            current = by_feature.setdefault(
                str(feature_id),
                {
                    "feature_id": str(feature_id),
                    "annotation_source": "sirius",
                    "original": {},
                    "parse_sources": [],
                },
            )
            current["formula"] = current.get("formula") or lowered.get("molecularformula") or lowered.get("formula") or ""
            current["candidate_name"] = current.get("candidate_name") or lowered.get("name") or lowered.get("compoundname") or ""
            current["smiles"] = current.get("smiles") or lowered.get("smiles") or ""
            current["inchikey"] = current.get("inchikey") or lowered.get("inchikey") or lowered.get("inchikey2d") or ""
            current["sirius_formula_score"] = current.get("sirius_formula_score") or lowered.get("siriusscore") or lowered.get("score") or ""
            current["sirius_structure_score"] = current.get("sirius_structure_score") or lowered.get("csiscore") or lowered.get("csi:fingeridscore") or lowered.get("confidencescore") or ""
            current["zodiac_score"] = current.get("zodiac_score") or lowered.get("zodiacscore") or ""
            current["canopus_class"] = current.get("canopus_class") or lowered.get("class") or lowered.get("npc#class") or ""
            current["parse_sources"].append(source)
            current["original"] = {**current.get("original", {}), source: row}
    annotations = list(by_feature.values())
    if not annotations:
        warnings.append("No supported SIRIUS TSV result files were found.")
    return {"annotations": annotations, "warnings": warnings}
