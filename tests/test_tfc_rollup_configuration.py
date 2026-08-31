from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPING_WORKBOOK = REPO_ROOT / "config" / "outlook_mappings_single_axis.xlsx"

EXPECTED_TFC_CONTRIBUTORS = {
    "All demand aggregated/Buildings",
    "All demand aggregated/Industry",
    "All demand aggregated/Road",
    "All demand aggregated/Transport non road",
    "All demand aggregated/Other sector",
    "All demand aggregated/Non Energy Use",
}


def test_tfc_rollup_uses_only_domestic_all_demand_children() -> None:
    rules = pd.read_excel(
        MAPPING_WORKBOOK,
        sheet_name="leap_rollup_rules",
        dtype=str,
    ).fillna("")
    tfc_rules = rules[
        rules["rolled_leap_sector_name_full_path"].eq(
            "Total final consumption"
        )
        & rules["include"].astype(str).str.casefold().isin({"true", "1", "yes"})
    ]

    assert set(tfc_rules["input_leap_sector_name_full_path"]) == (
        EXPECTED_TFC_CONTRIBUTORS
    )
    assert "All demand aggregated" not in set(
        tfc_rules["input_leap_sector_name_full_path"]
    )
    assert "All demand aggregated/International transport" not in set(
        tfc_rules["input_leap_sector_name_full_path"]
    )


def test_russia_missing_demand_pairs_are_registered() -> None:
    pairs = pd.read_excel(
        MAPPING_WORKBOOK,
        sheet_name="extra_leap_key_pairs",
        dtype=str,
    ).fillna("")
    observed = set(
        zip(
            pairs["leap_sector"].astype(str),
            pairs["leap_fuel"].astype(str),
        )
    )

    assert (
        "All demand aggregated/Buildings",
        "Crude oil",
    ) in observed
    assert (
        "All demand aggregated/Other sector",
        "Hydrogen",
    ) in observed


def test_russia_missing_demand_targets_are_registered_for_esto_scopes() -> None:
    expected_targets = {
        ("16.01-16.02 Buildings", "06.01 Crude oil"),
        ("16.03-16.05 Other sector (all demand aggregate)", "16.12 Hydrogen"),
    }

    for sheet_name in ["extra_esto_key_pairs", "extra_esto_extended_pairs"]:
        pairs = pd.read_excel(
            MAPPING_WORKBOOK,
            sheet_name=sheet_name,
            dtype=str,
        ).fillna("")
        observed = set(zip(pairs.iloc[:, 0], pairs.iloc[:, 1]))
        assert expected_targets.issubset(observed), sheet_name


def test_combined_other_placeholder_retains_observed_ethane_and_petroleum_coke_pairs() -> None:
    pairs = pd.read_excel(
        MAPPING_WORKBOOK,
        sheet_name="extra_leap_key_pairs",
        dtype=str,
    ).fillna("")
    observed = set(
        pairs.loc[
            pairs["leap_sector"].eq("All demand aggregated/Other sector"),
            "leap_fuel",
        ]
    )
    assert {"Ethane", "Petroleum coke"}.issubset(observed)


def test_combined_other_placeholder_targets_are_approved_for_esto_scopes() -> None:
    expected_targets = {
        (
            "16.03-16.05 Other sector (all demand aggregate)",
            "07.11 Ethane",
        ),
        (
            "16.03-16.05 Other sector (all demand aggregate)",
            "07.16 Petroleum coke",
        ),
    }

    for sheet_name in ["extra_esto_key_pairs", "extra_esto_extended_pairs"]:
        pairs = pd.read_excel(
            MAPPING_WORKBOOK,
            sheet_name=sheet_name,
            dtype=str,
        ).fillna("")
        observed = set(zip(pairs.iloc[:, 0], pairs.iloc[:, 1]))
        assert expected_targets.issubset(observed), sheet_name
