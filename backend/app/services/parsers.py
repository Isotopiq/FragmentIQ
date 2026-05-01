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
