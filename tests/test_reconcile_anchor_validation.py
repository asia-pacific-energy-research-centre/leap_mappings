"""Tests for reconciling raw source parent totals against converted outputs.

These exercise the reconciliation *methodology* directly: the left (raw) and
right (converted) sides come from separate frames, boundaries are classified
from structural artifacts, and no check depends on string-prefix or
tree-reconstructed frontiers.
"""

import pandas as pd

from codebase.mapping_tools.reconcile_anchor_validation import (
    build_parent_boundaries,
    normalize_converted_output,
    parent_descendants,
    reconcile_partition,
    summarise_reconciliation,
)


# --------------------------------------------------------------------------- #
# Fixtures.
# --------------------------------------------------------------------------- #

def _tree() -> pd.DataFrame:
    """A LEAP-style tree. 'Road' bridges to passenger/freight via explicit edges;
    the mapped vocabulary ('Passenger road'/'Freight road') differs from any
    string prefix of 'Road', so descendant enumeration is edge-based only.
    """
    return pd.DataFrame([
        # sector (flow) axis
        {"dataset": "leap", "axis": "sector", "code": "Road", "parent_code": ""},
        {"dataset": "leap", "axis": "sector", "code": "Passenger road", "parent_code": "Road"},
        {"dataset": "leap", "axis": "sector", "code": "Freight road", "parent_code": "Road"},
        # a separate parent that lands in a rolled/combined common row
        {"dataset": "leap", "axis": "sector", "code": "Gas works", "parent_code": ""},
        {"dataset": "leap", "axis": "sector", "code": "Gas works plant", "parent_code": "Gas works"},
        # fuel (product) axis
        {"dataset": "leap", "axis": "fuel", "code": "Oil", "parent_code": ""},
        {"dataset": "leap", "axis": "fuel", "code": "Gasoline", "parent_code": "Oil"},
        {"dataset": "leap", "axis": "fuel", "code": "Diesel", "parent_code": "Oil"},
    ])


def _structural() -> pd.DataFrame:
    """source_pair_to_common_row rows for LEAP under its leap_vs_esto scope."""
    base = {"source_system": "LEAP", "comparison_scope": "leap_vs_esto"}
    return pd.DataFrame([
        # Road descendants -> exact ESTO rows, owned only by Road's children.
        {**base, "original_source_flow": "Passenger road", "original_source_product": "Gasoline",
         "component_esto_flow": "15 Transport", "component_esto_product": "Gasoline",
         "common_row_id": "cr_pass", "is_exact_row": "True"},
        {**base, "original_source_flow": "Freight road", "original_source_product": "Diesel",
         "component_esto_flow": "15 Transport", "component_esto_product": "Diesel",
         "common_row_id": "cr_freight", "is_exact_row": "True"},
        # Gas works plant -> a connected-component rollup shared with an unrelated
        # contributor ('Coke ovens'), so it is not cleanly separable.
        {**base, "original_source_flow": "Gas works plant", "original_source_product": "Gas",
         "component_esto_flow": "09 Transformation", "component_esto_product": "Gas",
         "common_row_id": "cr_rollup", "is_exact_row": "False"},
        {**base, "original_source_flow": "Coke ovens", "original_source_product": "Gas",
         "component_esto_flow": "09 Transformation", "component_esto_product": "Gas",
         "common_row_id": "cr_rollup", "is_exact_row": "False"},
    ])


def _raw(passenger_gasoline: float = 4.0) -> pd.DataFrame:
    """Raw LEAP partition. Note the *subtotal* rows ('Road', 'Oil') are present
    just like real data; the reconciler must ignore them and sum mapped leaves.
    """
    base = {"source_system": "LEAP", "economy": "20USA", "scenario": "Reference", "year": 2022}
    return pd.DataFrame([
        {**base, "source_flow": "Passenger road", "source_product": "Gasoline", "value": passenger_gasoline},
        {**base, "source_flow": "Freight road", "source_product": "Diesel", "value": 6.0},
        {**base, "source_flow": "Gas works plant", "source_product": "Gas", "value": 5.0},
        # subtotal rows that would double-count if summed naively:
        {**base, "source_flow": "Road", "source_product": "Oil", "value": 999.0},
        {**base, "source_flow": "Road", "source_product": "Gasoline", "value": 999.0},
    ])


def _converted() -> pd.DataFrame:
    """Converted-to-ESTO output (the trusted right side). Road bridges here."""
    base = {"economy": "20_USA", "scenario": "Reference", "year": 2022}
    return normalize_converted_output(pd.DataFrame([
        {**base, "target_flow": "15 Transport", "target_product": "Gasoline", "value": 4.0},
        {**base, "target_flow": "15 Transport", "target_product": "Diesel", "value": 6.0},
        {**base, "target_flow": "09 Transformation", "target_product": "Gas", "value": 42.0},
    ]), "LEAP")


def _boundaries():
    tree, structural = _tree(), _structural()
    return {
        axis: build_parent_boundaries(structural, tree, "LEAP", axis)
        for axis in ["flow", "product"]
    }


def _components_by_axis(converted):
    return {
        axis: set(zip(converted["esto_flow"], converted["esto_product"]))
        for axis in ["flow", "product"]
    }


# --------------------------------------------------------------------------- #
# Tests.
# --------------------------------------------------------------------------- #

def test_parent_descendants_are_edge_based_not_prefix():
    desc = parent_descendants(_tree(), "leap", "sector")
    assert desc["Road"] == {"Road", "Passenger road", "Freight road"}
    # 'Gas works plant' is not a descendant of 'Road' despite no shared prefix
    assert "Gas works plant" not in desc["Road"]


def test_exact_parent_reconciles_and_both_axes_checked():
    converted = _converted()
    detail = reconcile_partition(
        _raw(), converted, _boundaries(), _components_by_axis(converted), "LEAP"
    )
    road = detail[(detail["validation_axis"] == "flow") & (detail["parent_code"] == "Road")].iloc[0]
    assert road["status"] == "passed"
    assert road["reason"] == "within_tolerance"
    # left is the mapped leaves (4 + 6 = 10), not the 999 subtotal rows
    assert road["raw_parent_total"] == 10.0
    assert road["converted_boundary_total"] == 10.0
    assert set(detail["validation_axis"]) == {"flow", "product"}


def test_injected_discrepancy_fails_with_totals_and_difference():
    converted = _converted()
    # Raw says 5 for Passenger road/Gasoline; converted still says 4 -> mismatch.
    detail = reconcile_partition(
        _raw(passenger_gasoline=5.0), converted, _boundaries(),
        _components_by_axis(converted), "LEAP",
    )
    road = detail[(detail["validation_axis"] == "flow") & (detail["parent_code"] == "Road")].iloc[0]
    assert road["status"] == "failed"
    assert road["reason"] == "difference_outside_tolerance"
    assert road["raw_parent_total"] == 11.0
    assert road["converted_boundary_total"] == 10.0
    assert abs(road["difference"] - 1.0) < 1e-9


def test_rollup_boundary_is_unanchorable_not_failed_or_passed():
    converted = _converted()
    detail = reconcile_partition(
        _raw(), converted, _boundaries(), _components_by_axis(converted), "LEAP"
    )
    gas = detail[(detail["validation_axis"] == "flow") & (detail["parent_code"] == "Gas works")].iloc[0]
    assert gas["status"] == "unanchorable"
    assert gas["reason"] == "rollup_boundary_not_separable"
    assert gas["boundary_kind"] == "rollup"


def test_tautology_guard_left_and_right_are_independent():
    # Fabricate a mismatch by corrupting only the converted (right) side; the
    # raw (left) side is unchanged, so the discrepancy must be detectable.
    converted = _converted()
    converted.loc[converted["esto_product"] == "Gasoline", "value"] = 400.0
    detail = reconcile_partition(
        _raw(), converted, _boundaries(), _components_by_axis(converted), "LEAP"
    )
    road = detail[(detail["validation_axis"] == "flow") & (detail["parent_code"] == "Road")].iloc[0]
    assert road["status"] == "failed"
    assert road["raw_parent_total"] == 10.0
    assert road["converted_boundary_total"] == 406.0


def test_parent_absent_from_converted_output_is_unanchorable():
    # Drop Road's components from the converted output entirely.
    converted = _converted()
    converted = converted[converted["esto_flow"] != "15 Transport"]
    detail = reconcile_partition(
        _raw(), converted, _boundaries(), _components_by_axis(converted), "LEAP"
    )
    road = detail[(detail["validation_axis"] == "flow") & (detail["parent_code"] == "Road")].iloc[0]
    assert road["status"] == "unanchorable"
    assert road["reason"] == "parent_absent_from_converted_output"


def test_slice_matches_in_memory_reference():
    converted = _converted()
    detail = reconcile_partition(
        _raw(), converted, _boundaries(), _components_by_axis(converted), "LEAP"
    )
    # Deterministic reference for the flow-axis Road parent.
    road = detail[(detail["validation_axis"] == "flow") & (detail["parent_code"] == "Road")].iloc[0]
    assert (road["raw_parent_total"], road["converted_boundary_total"], road["status"]) == (10.0, 10.0, "passed")


def test_ninth_and_esto_reconcile_on_both_axes():
    for system, dataset in [("NINTH", "ninth"), ("ESTO", "esto")]:
        flow_axis, fuel_axis = ("sector", "fuel") if dataset in {"leap", "ninth"} else ("flow", "product")
        scope = {"NINTH": "leap_vs_esto_vs_ninth", "ESTO": "esto_only"}[system]
        tree = pd.DataFrame([
            {"dataset": dataset, "axis": flow_axis, "code": "P", "parent_code": ""},
            {"dataset": dataset, "axis": flow_axis, "code": "P_child", "parent_code": "P"},
            {"dataset": dataset, "axis": fuel_axis, "code": "F", "parent_code": ""},
            {"dataset": dataset, "axis": fuel_axis, "code": "F_child", "parent_code": "F"},
        ])
        structural = pd.DataFrame([{
            "source_system": system, "comparison_scope": scope,
            "original_source_flow": "P_child", "original_source_product": "F_child",
            "component_esto_flow": "EF", "component_esto_product": "EP",
            "common_row_id": "cr", "is_exact_row": "True",
        }])
        raw = pd.DataFrame([{
            "source_system": system, "economy": "20USA", "scenario": "s", "year": 2022,
            "source_flow": "P_child", "source_product": "F_child", "value": 7.0,
        }])
        converted = normalize_converted_output(pd.DataFrame([{
            "source_system": system, "economy": "20USA", "scenario": "s", "year": 2022,
            "esto_flow": "EF", "esto_product": "EP", "value": 7.0,
        }]), system)
        boundaries = {axis: build_parent_boundaries(structural, tree, system, axis) for axis in ["flow", "product"]}
        detail = reconcile_partition(raw, converted, boundaries, _components_by_axis(converted), system)
        passed = detail[detail["status"] == "passed"]
        assert set(passed["validation_axis"]) == {"flow", "product"}


def test_empty_validation_is_not_passed():
    summary = summarise_reconciliation(pd.DataFrame())
    assert summary.iloc[0]["status"] == "failed"
    assert summary.iloc[0]["reason"] == "empty_validation"


def test_normalize_converted_output_maps_each_schema():
    leap = normalize_converted_output(pd.DataFrame([
        {"economy": "20_USA", "scenario": "Reference", "year": "2022",
         "target_flow": "F", "target_product": "P", "value": "1.5"}
    ]), "LEAP")
    assert list(leap.columns) == [
        "source_system", "economy", "scenario", "year", "esto_flow", "esto_product", "value"
    ]
    assert leap.iloc[0]["source_system"] == "LEAP"
    assert leap.iloc[0]["economy"] == "20USA"
    esto = normalize_converted_output(pd.DataFrame([
        {"economy": "01AUS", "esto_flow": "F", "esto_product": "P", "year": "1990",
         "value": "2.0", "source_system": "ESTO", "scenario": "historical"}
    ]), "ESTO")
    assert esto.iloc[0]["esto_flow"] == "F"
