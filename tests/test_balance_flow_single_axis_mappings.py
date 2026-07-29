#%%
"""Regression checks for maintained balance-flow axis relationships."""

from pathlib import Path

import pandas as pd

from codebase.mapping_tools.leap_pair_registry import (
    derive_leap_balance_structure,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SINGLE_AXIS_PATH = REPO_ROOT / "config" / "outlook_mappings_single_axis.xlsx"


def test_stock_and_statistical_flows_are_maintained_on_both_sector_axes() -> None:
    leap_to_esto = pd.read_excel(
        SINGLE_AXIS_PATH,
        sheet_name="leap_sector_to_esto",
        dtype=str,
    ).fillna("")
    leap_to_ninth = pd.read_excel(
        SINGLE_AXIS_PATH,
        sheet_name="leap_sector_to_ninth",
        dtype=str,
    ).fillna("")

    esto_rows = set(
        leap_to_esto[
            ["leap_sector", "esto_flow", "esto_dataset_scope"]
        ].itertuples(index=False, name=None)
    )
    ninth_rows = set(
        leap_to_ninth[
            ["leap_sector", "ninth_sector"]
        ].itertuples(index=False, name=None)
    )

    assert ("Stock Changes", "06 Stock changes", "BOTH") in esto_rows
    assert (
        "Statistical Differences",
        "11 Statistical discrepancy",
        "BOTH",
    ) in esto_rows
    assert ("Stock Changes", "06_stock_changes") in ninth_rows
    assert (
        "Statistical Differences",
        "11_statistical_discrepancy",
    ) in ninth_rows


def test_generated_balance_registry_uses_canonical_stock_flow_name() -> None:
    flows, _ = derive_leap_balance_structure(
        [],
        source_kind="test",
        source_id="test",
        source_sheet="Export",
        include_fixed_flows=True,
    )

    assert "Stock Changes" in set(flows["flow"])
    assert "From Stocks" not in set(flows["flow"])


#%%
