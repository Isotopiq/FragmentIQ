from pathlib import Path

from app.services.parsers import parse_mzmine_outputs, parse_sirius_outputs
from app.services.statistics import benjamini_hochberg, welch_two_group


def test_parse_mzmine_outputs_prefers_feature_table(tmp_path: Path):
    output = tmp_path / "feature_table.csv"
    output.write_text("feature_id,mz,rt,intensity\nF1,101.1,2.3,5000\n", encoding="utf-8")

    parsed = parse_mzmine_outputs(tmp_path)

    assert parsed["features"][0]["feature_id"] == "F1"
    assert parsed["features"][0]["mz"] == 101.1
    assert parsed["warnings"] == []


def test_parse_sirius_outputs_normalizes_formula_and_structure(tmp_path: Path):
    sirius_dir = tmp_path / "sirius"
    sirius_dir.mkdir()
    (sirius_dir / "formula_identifications.tsv").write_text(
        "feature_id\tmolecularFormula\tSiriusScore\tZodiacScore\nF1\tC10H20O2\t0.95\t0.88\n",
        encoding="utf-8",
    )
    (sirius_dir / "structure_identifications.tsv").write_text(
        "feature_id\tname\tsmiles\tInChIkey\tCSI:FingerIDScore\nF1\tCandidate A\tCCO\tAAAA\t0.91\n",
        encoding="utf-8",
    )

    parsed = parse_sirius_outputs(sirius_dir)

    assert parsed["annotations"][0]["formula"] == "C10H20O2"
    assert parsed["annotations"][0]["candidate_name"] == "Candidate A"
    assert parsed["annotations"][0]["annotation_source"] == "sirius"


def test_benjamini_hochberg_monotonic_adjustment():
    adjusted = benjamini_hochberg([0.01, 0.02, 0.5, 0.001])
    assert len(adjusted) == 4
    assert all(0 <= value <= 1 for value in adjusted)
    assert adjusted[3] <= adjusted[0] <= adjusted[2]


def test_welch_two_group_returns_expected_direction():
    result = welch_two_group(
        "F1",
        [10, 11, 12, 13],
        [20, 21, 22, 23],
        metadata={"mz": 100.1, "rt": 2.0, "annotation": "Example"},
    )

    assert result["feature_id"] == "F1"
    assert result["log2_fold_change"] > 0
    assert result["test_name"] == "Welch t-test"
