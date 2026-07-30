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


def test_shifted_buildings_fuel_relations_are_not_global_axis_mappings() -> None:
    leap_to_esto = pd.read_excel(
        SINGLE_AXIS_PATH,
        sheet_name="leap_fuel_to_esto",
        dtype=str,
    ).fillna("")
    rows = set(
        leap_to_esto[
            ["leap_fuel", "esto_product", "esto_dataset_scope"]
        ].itertuples(index=False, name=None)
    )

    assert ("Natural gas", "08.01 Natural gas", "BOTH") in rows
    assert ("Natural gas", "07.09 LPG", "BOTH") not in rows
    assert ("Heat", "18 Heat", "BOTH") in rows
    assert ("Heat", "17 Electricity", "BOTH") not in rows
    assert ("Peat", "03 Peat", "BOTH") in rows
    assert ("Peat", "18 Heat", "BOTH") not in rows


def test_esto_extended_detail_axes_are_maintained_even_when_zero_only() -> None:
    leap_to_esto_flow = pd.read_excel(
        SINGLE_AXIS_PATH,
        sheet_name="leap_sector_to_esto",
        dtype=str,
    ).fillna("")
    leap_to_esto_product = pd.read_excel(
        SINGLE_AXIS_PATH,
        sheet_name="leap_fuel_to_esto",
        dtype=str,
    ).fillna("")
    flow_rows = set(
        leap_to_esto_flow[
            ["leap_sector", "esto_flow", "esto_dataset_scope"]
        ].itertuples(index=False, name=None)
    )
    product_rows = set(
        leap_to_esto_product[
            ["leap_fuel", "esto_product", "esto_dataset_scope"]
        ].itertuples(index=False, name=None)
    )

    assert (
        "Passenger road/LPVs/BEV small",
        "15.02.02.02.03 BEV small",
        "ESTO_EXTENDED",
    ) in flow_rows
    assert (
        "Hydrogen transformation/Processes/SMR with CCS",
        "09.13.02 SMR with CCS",
        "ESTO_EXTENDED",
    ) in flow_rows
    assert (
        "Natural gas",
        "08.01 Natural gas",
        "ESTO_EXTENDED",
    ) in product_rows


#%%
