"""Focused tests for source-data rollup application."""

import pandas as pd

from codebase.mapping_tools.convert_leap_results_to_esto import convert_leap_results_to_esto
from codebase.mapping_tools.source_rollups import apply_source_rollups


def _road_rules() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "input_leap_sector_name_full_path": "Passenger road",
            "input_raw_leap_fuel_name": "",
            "rolled_leap_sector_name_full_path": "Road",
            "rolled_raw_leap_fuel_name": "",
            "include": True,
        },
        {
            "input_leap_sector_name_full_path": "Freight road",
            "input_raw_leap_fuel_name": "",
            "rolled_leap_sector_name_full_path": "Road",
            "rolled_raw_leap_fuel_name": "",
            "include": True,
        },
    ])


def test_road_rollup_preserves_detail_and_aggregates_during_conversion() -> None:
    source = pd.DataFrame([
        {"economy": "20_USA", "scenario": "Reference", "year": 2024,
         "leap_flow": "Passenger road", "leap_product": "Electricity", "value": "3.0"},
        {"economy": "20_USA", "scenario": "Reference", "year": 2024,
         "leap_flow": "Freight road", "leap_product": "Electricity", "value": "2.0"},
    ])
    relationships = pd.DataFrame([{
        "source_flow": "Road",
        "source_product": "Electricity",
        "target_flow": "15.02 Road",
        "target_product": "17 Electricity",
    }])

    converted = convert_leap_results_to_esto(source, relationships, _road_rules())

    assert converted.iloc[0]["value"] == 5.0
    assert converted.iloc[0]["target_flow"] == "15.02 Road"


def test_exact_duplicate_rule_is_applied_once_and_audited() -> None:
    source = pd.DataFrame([
        {"leap_flow": "Passenger road", "leap_product": "Electricity", "value": 3.0},
    ])
    rules = pd.concat([_road_rules().iloc[[0]], _road_rules().iloc[[0]]], ignore_index=True)

    rolled, audit = apply_source_rollups(
        source_df=source,
        rules_df=rules,
        source_flow_column="leap_flow",
        source_product_column="leap_product",
        value_column="value",
        input_flow_column="input_leap_sector_name_full_path",
        input_product_column="input_raw_leap_fuel_name",
        rolled_flow_column="rolled_leap_sector_name_full_path",
        rolled_product_column="rolled_raw_leap_fuel_name",
    )

    assert rolled[rolled["leap_flow"] == "Road"]["value"].sum() == 3.0
    assert audit.iloc[0]["issue_type"] == "exact_duplicate_rule"
    assert audit.iloc[0]["rule_count"] == 2


def test_multiple_ancestor_aggregates_are_not_reported_as_duplicates() -> None:
    source = pd.DataFrame([
        {"leap_flow": "Passenger road", "leap_product": "Electricity", "value": 3.0},
    ])
    rules = _road_rules().iloc[[0]].copy()
    transport_rule = rules.copy()
    transport_rule["rolled_leap_sector_name_full_path"] = "Transport"
    rules = pd.concat([rules, transport_rule], ignore_index=True)

    rolled, audit = apply_source_rollups(
        source_df=source,
        rules_df=rules,
        source_flow_column="leap_flow",
        source_product_column="leap_product",
        value_column="value",
        input_flow_column="input_leap_sector_name_full_path",
        input_product_column="input_raw_leap_fuel_name",
        rolled_flow_column="rolled_leap_sector_name_full_path",
        rolled_product_column="rolled_raw_leap_fuel_name",
    )

    assert set(rolled["leap_flow"]) == {"Passenger road", "Road", "Transport"}
    assert audit.empty
