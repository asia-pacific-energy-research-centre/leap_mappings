#%%
"""Regression checks for leaf-level coal-transformation own-use rollups."""

from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPING_WORKBOOK = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
AXIS_WORKBOOK = REPO_ROOT / "config" / "outlook_mappings_single_axis.xlsx"


def test_coke_and_blast_ninth_rollups_are_active_non_expanding_boundaries() -> None:
    rules = pd.read_excel(MAPPING_WORKBOOK, sheet_name="ninth_rollup_rules")
    expected = {
        "10_01_05_coke_ovens": "09_08_01_coke_ovens_incl_own_use",
        "09_08_01_coke_ovens": "09_08_01_coke_ovens_incl_own_use",
        "10_01_07_blast_furnaces": "09_08_02_blast_furnaces_incl_own_use",
        "09_08_02_blast_furnaces": "09_08_02_blast_furnaces_incl_own_use",
    }

    selected = rules[
        rules.apply(
            lambda row: expected.get(row["input_ninth_sector"])
            == row["rolled_ninth_sector"],
            axis=1,
        )
    ].copy()
    assert len(selected) == len(expected)
    assert selected["include"].astype(bool).all()
    assert selected["ROLLUP_MODE"].eq("NON_EXPANDING").all()
    assert selected.set_index("input_ninth_sector")["rolled_ninth_sector"].to_dict() == expected


def test_coke_and_blast_rolled_ninth_labels_have_inclusive_esto_targets() -> None:
    mappings = pd.read_excel(AXIS_WORKBOOK, sheet_name="ninth_sector_to_esto")
    expected = {
        "09_08_01_coke_ovens_incl_own_use": "09.08.01 Coke ovens (including own use)",
        "09_08_02_blast_furnaces_incl_own_use": "09.08.02 Blast furnaces (including own use)",
    }

    selected = mappings[
        mappings["ninth_sector"].astype(str).isin(expected)
    ].copy()
    assert len(selected) == len(expected)
    assert selected.set_index("ninth_sector")["esto_flow"].to_dict() == expected
    assert selected["esto_dataset_scope"].eq("BOTH").all()

#%%
