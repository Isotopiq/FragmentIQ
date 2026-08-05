from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    """Return BH-FDR adjusted p-values in the original row order."""
    n = len(p_values)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda idx: p_values[idx])
    adjusted = [1.0] * n
    running_min = 1.0
    for rank_from_end, idx in enumerate(reversed(order), start=1):
        rank = n - rank_from_end + 1
        value = min(running_min, p_values[idx] * n / rank)
        running_min = value
        adjusted[idx] = min(1.0, value)
    return adjusted


def half_minimum_impute(values: list[float | None]) -> list[float]:
    observed = [float(value) for value in values if value is not None and not math.isnan(float(value))]
    replacement = min(observed) / 2 if observed else 0.0
    return [float(value) if value is not None and not math.isnan(float(value)) else replacement for value in values]


def welch_test_rows(
    feature_rows: list[dict[str, Any]],
    group_a_columns: list[str],
    group_b_columns: list[str],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    p_values: list[float] = []
    for row in feature_rows:
        a = half_minimum_impute([_to_float(row.get(column)) for column in group_a_columns])
        b = half_minimum_impute([_to_float(row.get(column)) for column in group_b_columns])
        statistic, p_value = stats.ttest_ind(a, b, equal_var=False, nan_policy="omit")
        mean_a = float(np.mean(a)) if a else 0.0
        mean_b = float(np.mean(b)) if b else 0.0
        fold = mean_b / mean_a if mean_a else math.inf
        log2fc = math.log(fold, 2) if fold > 0 and math.isfinite(fold) else 0.0
        p_value_float = float(p_value) if not math.isnan(float(p_value)) else 1.0
        p_values.append(p_value_float)
        results.append(
            {
                "feature_id": row.get("feature_id") or row.get("id"),
                "mz": row.get("mz") or row.get("m/z"),
                "rt": row.get("rt") or row.get("retention_time"),
                "group_1_mean": round(mean_a, 6),
                "group_2_mean": round(mean_b, 6),
                "group_1_median": round(float(np.median(a)), 6),
                "group_2_median": round(float(np.median(b)), 6),
                "log2_fold_change": round(log2fc, 6),
                "fold_change": round(fold, 6) if math.isfinite(fold) else "inf",
                "test_name": "Welch t-test",
                "statistic": round(float(statistic), 6) if not math.isnan(float(statistic)) else 0.0,
                "p_value": round(p_value_float, 8),
            }
        )
    for row, adjusted in zip(results, benjamini_hochberg(p_values), strict=False):
        row["adjusted_p_value"] = round(adjusted, 8)
        row["q_value"] = round(adjusted, 8)
    return results


def welch_two_group(
    feature_id: str,
    group_a: list[float | int | None],
    group_b: list[float | int | None],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute one transparent two-group Welch row for UI previews and tests."""
    a = half_minimum_impute([_to_float(value) for value in group_a])
    b = half_minimum_impute([_to_float(value) for value in group_b])
    statistic, p_value = stats.ttest_ind(a, b, equal_var=False, nan_policy="omit")
    mean_a = float(np.mean(a)) if a else 0.0
    mean_b = float(np.mean(b)) if b else 0.0
    fold = mean_b / mean_a if mean_a else math.inf
    log2fc = math.log(fold, 2) if fold > 0 and math.isfinite(fold) else 0.0
    p_value_float = float(p_value) if not math.isnan(float(p_value)) else 1.0
    row = {
        "feature_id": feature_id,
        "group_1_mean": round(mean_a, 6),
        "group_2_mean": round(mean_b, 6),
        "group_1_median": round(float(np.median(a)), 6),
        "group_2_median": round(float(np.median(b)), 6),
        "log2_fold_change": round(log2fc, 6),
        "fold_change": round(fold, 6) if math.isfinite(fold) else "inf",
        "test_name": "Welch t-test",
        "statistic": round(float(statistic), 6) if not math.isnan(float(statistic)) else 0.0,
        "p_value": round(p_value_float, 8),
    }
    if metadata:
        row.update(metadata)
        row["feature_id"] = feature_id
    return row


def _to_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
