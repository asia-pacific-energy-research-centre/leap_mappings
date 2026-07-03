"""Tests for value-free structural mapping compilation."""

from pathlib import Path

import pandas as pd

from codebase.mapping_tools.compile_structural_mapping_artifacts import (
    compile_structural_frames,
    compile_structural_mapping_artifacts,
)


def _relationships() -> pd.DataFrame:
    return pd.DataFrame([
        {"source_system": "LEAP", "source_flow": "Passenger", "source_product": "Oil", "target_system": "ESTO", "target_flow": "15.02 Road", "target_product": "07 Oil", "relationship_id": "l1", "include_in_use_case": True, "is_rollup_derived": False},
        {"source_system": "NINTH", "source_flow": "Road", "source_product": "Oil", "target_system": "ESTO", "target_flow": "15.02 Road", "target_product": "07 Oil", "relationship_id": "n1", "include_in_use_case": True, "is_rollup_derived": False},
    ])


def _common_map() -> pd.DataFrame:
    return pd.DataFrame([
        {"comparison_scope": "all", "component_esto_flow": "15.02 Road", "component_esto_product": "07 Oil", "common_row_id": "road_oil", "component_sign": 1},
        {"comparison_scope": "all", "component_esto_flow": "99 Graph A", "component_esto_product": "99 Graph fuel", "common_row_id": "graph_row", "component_sign": 1},
    ])


def _rules() -> dict[str, pd.DataFrame]:
    return {"LEAP": pd.DataFrame([{
        "input_leap_sector_name_full_path": "Passenger", "input_raw_leap_fuel_name": "",
        "rolled_leap_sector_name_full_path": "Road", "rolled_raw_leap_fuel_name": "",
        "include": True,
    }])}


def test_compiles_all_directions_and_membership_without_allocation() -> None:
    artifacts = compile_structural_frames(_relationships(), _common_map(), _rules(), "abc")
    forward = artifacts["source_pair_to_common_row"]
    assert set(forward["source_system"]) == {"LEAP", "NINTH", "ESTO"}
    rolled = forward[(forward["source_system"] == "LEAP") & (forward["evidence_type"] == "rollup_rule")].iloc[0]
    assert (rolled["original_source_flow"], rolled["effective_source_flow"]) == ("Passenger", "Road")
    reverse = artifacts["common_row_to_source_pairs"]
    assert "value" not in reverse.columns
    assert "allocation_share" not in reverse.columns
    assert "graph_row" in set(reverse["common_row_id"])


def test_output_is_deterministic_under_shuffled_inputs() -> None:
    first = compile_structural_frames(_relationships(), _common_map(), _rules(), "abc")
    second = compile_structural_frames(
        _relationships().sample(frac=1, random_state=2),
        _common_map().sample(frac=1, random_state=3), _rules(), "abc",
    )
    for name in first:
        pd.testing.assert_frame_equal(first[name].reset_index(drop=True), second[name].reset_index(drop=True))


def test_runner_reads_only_structural_inputs(monkeypatch, tmp_path: Path) -> None:
    relationships_path = tmp_path / "relationships.csv"
    common_path = tmp_path / "common.csv"
    workbook_path = tmp_path / "mapping.xlsx"
    _relationships().to_csv(relationships_path, index=False)
    _common_map().to_csv(common_path, index=False)
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        _rules()["LEAP"].to_excel(writer, sheet_name="leap_rollup_rules", index=False)
        pd.DataFrame(columns=["input_9th_sector", "rolled_9th_sector"]).to_excel(writer, sheet_name="ninth_rollup_rules", index=False)
    real_read_csv = pd.read_csv
    reads: list[Path] = []

    def guarded_read_csv(path, *args, **kwargs):
        reads.append(Path(path))
        return real_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", guarded_read_csv)
    compile_structural_mapping_artifacts(relationships_path, common_path, workbook_path, tmp_path / "out")
    assert reads == [relationships_path, common_path]
