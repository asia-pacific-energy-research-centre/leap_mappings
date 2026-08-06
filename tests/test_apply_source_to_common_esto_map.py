"""Tests for the importable merger (D4, overnight work program W6, 2026-08-06/07)."""

from __future__ import annotations

import pandas as pd

from codebase.mapping_tools.apply_source_to_common_esto_map import (
    apply_source_to_common_esto_map,
)


def _sample_map() -> pd.DataFrame:
    return pd.DataFrame(
        [
            # Two native LEAP pairs collapse onto the same common row -
            # exactly the many-to-one shape the aggregation half must handle.
            {
                "comparison_scope": "esto_leap_ninth", "source_system": "LEAP",
                "source_flow": "Residential", "source_product": "Natural gas",
                "common_row_id": "row_1", "common_flow_label": "16.02 Residential",
                "common_product_label": "08.01 Natural gas",
            },
            {
                "comparison_scope": "esto_leap_ninth", "source_system": "LEAP",
                "source_flow": "Residential", "source_product": "Piped natural gas",
                "common_row_id": "row_1", "common_flow_label": "16.02 Residential",
                "common_product_label": "08.01 Natural gas",
            },
            {
                "comparison_scope": "esto_leap_ninth", "source_system": "LEAP",
                "source_flow": "Residential", "source_product": "Electricity",
                "common_row_id": "row_2", "common_flow_label": "16.02 Residential",
                "common_product_label": "17 Electricity",
            },
        ]
    )


def test_many_native_pairs_sum_onto_one_common_row():
    values = pd.DataFrame(
        [
            {"source_flow": "Residential", "source_product": "Natural gas", "economy": "20_USA", "scenario": "Target", "year": 2022, "value": 60.0},
            {"source_flow": "Residential", "source_product": "Piped natural gas", "economy": "20_USA", "scenario": "Target", "year": 2022, "value": 40.0},
            {"source_flow": "Residential", "source_product": "Electricity", "economy": "20_USA", "scenario": "Target", "year": 2022, "value": 15.0},
        ]
    )
    result = apply_source_to_common_esto_map(
        values, _sample_map(), comparison_scope="esto_leap_ninth", source_system="LEAP"
    )
    row_1 = result[result["common_row_id"] == "row_1"]
    assert len(row_1) == 1
    assert row_1["value"].iloc[0] == 100.0
    row_2 = result[result["common_row_id"] == "row_2"]
    assert row_2["value"].iloc[0] == 15.0


def test_native_pair_outside_the_map_is_silently_absent_not_raised():
    values = pd.DataFrame(
        [{"source_flow": "Not In The Map", "source_product": "Nothing", "economy": "20_USA", "scenario": "Target", "year": 2022, "value": 5.0}]
    )
    result = apply_source_to_common_esto_map(
        values, _sample_map(), comparison_scope="esto_leap_ninth", source_system="LEAP"
    )
    assert result.empty


def test_scope_and_source_system_are_stamped_on_every_row():
    values = pd.DataFrame(
        [{"source_flow": "Residential", "source_product": "Electricity", "economy": "20_USA", "scenario": "Target", "year": 2022, "value": 15.0}]
    )
    result = apply_source_to_common_esto_map(
        values, _sample_map(), comparison_scope="esto_leap_ninth", source_system="LEAP"
    )
    assert set(result["comparison_scope"]) == {"esto_leap_ninth"}
    assert set(result["source_system"]) == {"LEAP"}
