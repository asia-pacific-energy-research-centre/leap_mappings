#%%
"""Regression checks for maintained balance-flow axis relationships."""

from pathlib import Path

import pandas as pd

from codebase.mapping_tools.leap_pair_registry import (
    FIXED_BALANCE_PRODUCTS,
    derive_leap_balance_structure,
)
from codebase.mapping_tools.build_energy_balance_relationships import (
    build_default_coverage_exclusions,
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


def test_balancing_flows_are_not_default_coverage_exclusions() -> None:
    exclusions = build_default_coverage_exclusions()

    assert exclusions.empty


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


def test_generated_balance_registry_includes_report_only_products() -> None:
    _, catalogue = derive_leap_balance_structure(
        [],
        source_kind="test",
        source_id="test",
        source_sheet="Export",
        include_fixed_flows=True,
    )

    assert set(catalogue["product"]) == FIXED_BALANCE_PRODUCTS


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


def test_ninth_agriculture_and_fishing_maps_only_to_combined_flow() -> None:
    ninth_to_esto = pd.read_excel(
        SINGLE_AXIS_PATH,
        sheet_name="ninth_sector_to_esto",
        dtype=str,
    ).fillna("")
    mapped_flows = set(
        ninth_to_esto.loc[
            ninth_to_esto["ninth_sector"].eq("16_02_agriculture_and_fishing"),
            "esto_flow",
        ]
    )

    assert mapped_flows == {"16.03-16.04 Agriculture and fishing"}


def test_leap_refining_maps_only_to_inclusive_comparison_boundary() -> None:
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

    assert (
        "Oil Refining/Oil Refining",
        "09.07 Oil refineries (including own use)",
        "BOTH",
    ) in esto_rows
    assert (
        "Oil Refining/Oil Refining",
        "09_07_oil_refineries_incl_own_use",
    ) in ninth_rows
    assert not any(row[0] == "Other loss and own use/Oil refineries" for row in esto_rows)
    assert not any(row[0] == "Other loss and own use/Oil refineries" for row in ninth_rows)


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
        "BOTH",
    ) in product_rows


def test_electricity_generation_processes_map_to_stable_esto_extended_flows() -> None:
    leap_to_esto_flow = pd.read_excel(
        SINGLE_AXIS_PATH,
        sheet_name="leap_sector_to_esto",
        dtype=str,
    ).fillna("")
    rows = set(
        leap_to_esto_flow[
            ["leap_sector", "esto_flow", "esto_dataset_scope"]
        ].itertuples(index=False, name=None)
    )

    expected_processes = {
        "Coal": ("01", "Coal power"),
        "Coal_CCUS": ("02", "Coal power CCS"),
        "Coal_H2_blended": ("03", "Coal hydrogen blended"),
        "Gas": ("04", "Gas power"),
        "Gas_CCUS": ("05", "Gas power CCS"),
        "Geothermal": ("06", "Geothermal"),
        "Hydro": ("07", "Hydro"),
        "Nuclear": ("08", "Nuclear"),
        "Others": ("09", "Others"),
        "Petroleum products": ("10", "Oil"),
        "Solar": ("11", "Solar"),
        "Solar CSP": ("12", "Solar CSP"),
        "Solar PV": ("13", "Solar utility PV"),
        "Solar rooftop": ("14", "Solar rooftop"),
        "Solid biomass": ("15", "Solid biomass"),
        "Battery": ("16", "Storage"),
        "Wind": ("17", "Wind"),
        "Wind offshore": ("18", "Wind offshore"),
    }
    expected_rows = {
        (
            f"Electricity Generation/{branch}",
            f"{prefix}.{suffix} {label}",
            "ESTO_EXTENDED",
        )
        for branch, (suffix, label) in expected_processes.items()
        for prefix in ("09.01.01", "09.02.01")
    }

    assert expected_rows <= rows

    alias_rows = {
        (
            "Electricity Generation/Solar_rooftop",
            f"{prefix}.14 Solar rooftop",
            "ESTO_EXTENDED",
        )
        for prefix in ("09.01.01", "09.02.01")
    } | {
        (
            f"Electricity Generation/{branch}",
            f"{prefix}.16 Storage",
            "ESTO_EXTENDED",
        )
        for branch in ("Batteries", "Distributed storage")
        for prefix in ("09.01.01", "09.02.01")
    }
    assert alias_rows <= rows

    extended_pairs = pd.read_excel(
        SINGLE_AXIS_PATH,
        sheet_name="extra_esto_extended_pairs",
        dtype=str,
    ).fillna("")
    registered_flows = set(extended_pairs["esto_flow"])
    assert {row[1] for row in expected_rows | alias_rows} <= registered_flows


#%%
