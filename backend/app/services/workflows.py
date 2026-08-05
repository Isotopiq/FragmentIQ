from __future__ import annotations

from typing import Any

WORKFLOW_PRESETS: list[dict[str, Any]] = [
    {
        "id": "untargeted-positive",
        "name": "Untargeted positive mode",
        "category": "MZmine/SIRIUS",
        "description": "Batch-compatible MZmine feature detection with MGF/CSV export and SIRIUS annotation handoff.",
        "engines": ["mzmine", "sirius"],
        "parameters": {
            "ion_mode": "positive",
            "mz_tolerance_ppm": 10,
            "rt_tolerance_minutes": 0.2,
            "mass_detection_noise": 1000,
            "export_feature_table": True,
            "export_mgf": True,
        },
        "mzbatch_template": "example_workflows/untargeted_positive.mzbatch",
    },
    {
        "id": "untargeted-negative",
        "name": "Untargeted negative mode",
        "category": "MZmine/SIRIUS",
        "description": "Negative-mode batch workflow preserving the editable .mzbatch configuration.",
        "engines": ["mzmine", "sirius"],
        "parameters": {
            "ion_mode": "negative",
            "mz_tolerance_ppm": 10,
            "rt_tolerance_minutes": 0.25,
            "mass_detection_noise": 800,
            "export_feature_table": True,
            "export_mgf": True,
        },
        "mzbatch_template": "example_workflows/untargeted_negative.mzbatch",
    },
    {
        "id": "annotation-only",
        "name": "MS/MS annotation-only workflow",
        "category": "MZmine/SIRIUS",
        "description": "Use uploaded MGF/MSP spectra for SIRIUS and optional library/ML scoring.",
        "engines": ["sirius", "matchms", "ms2deepscore", "ms2query"],
        "parameters": {
            "input_source": "uploaded_spectra",
            "formula_candidate_limit": 50,
            "structure_candidate_limit": 20,
            "enable_canopus": True,
        },
    },
    {
        "id": "full-consensus-annotation",
        "name": "Full MS/MS consensus annotation workflow",
        "category": "ML-MS/MS",
        "description": "MZmine -> SIRIUS -> matchms cosine -> MS2DeepScore -> MS2Query -> DREAMS with unified ranking.",
        "engines": ["mzmine", "sirius", "matchms", "ms2deepscore", "ms2query", "dreams"],
        "parameters": {
            "top_n": 10,
            "matchms_min_cosine": 0.7,
            "ms2deepscore_threshold": 0.75,
            "ms2query_threshold": 0.6,
            "dreams_threshold": 0.6,
            "consensus_strategy": "weighted",
            "weights": {
                "sirius_structure_score": 0.3,
                "sirius_formula_score": 0.2,
                "matchms_cosine": 0.2,
                "ms2deepscore": 0.15,
                "ms2query_score": 0.1,
                "dreams_score": 0.05,
            },
        },
    },
    {
        "id": "two-group-statistics",
        "name": "Two-group differential feature analysis",
        "category": "Statistics/Visualization",
        "description": "Metadata-aware preprocessing, Welch test, BH-FDR, PCA, volcano, and heatmap outputs.",
        "engines": ["stats"],
        "parameters": {
            "normalization": "median",
            "transformation": "log2",
            "missing_value_imputation": "half-minimum",
            "test": "welch_t_test",
            "multiple_testing": "benjamini_hochberg",
        },
    },
    {
        "id": "molecular-networking-export",
        "name": "GNPS/molecular networking export workflow",
        "category": "MZmine/SIRIUS",
        "description": "Feature table, MGF, and edge-table oriented outputs for network visualization.",
        "engines": ["mzmine", "matchms"],
        "parameters": {
            "export_gnps": True,
            "edge_score": "matchms_cosine",
            "minimum_cosine": 0.65,
            "minimum_matched_peaks": 6,
        },
    },
]


def validate_workflow_payload(config: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    parameters = config.get("parameters", config)
    for key in ("mz_tolerance_ppm", "rt_tolerance_minutes", "top_n", "minimum_cosine"):
        if key in parameters and parameters[key] not in ("", None):
            try:
                if float(parameters[key]) < 0:
                    warnings.append(f"{key} must be non-negative.")
            except (TypeError, ValueError):
                warnings.append(f"{key} must be numeric.")
    raw_mzbatch = config.get("raw_mzbatch") or config.get("mzbatch_text")
    if raw_mzbatch and "<batch" not in str(raw_mzbatch).lower() and "<batchstep" not in str(raw_mzbatch).lower():
        warnings.append("The .mzbatch file is preserved, but its XML does not look like a batch workflow.")
    return warnings
