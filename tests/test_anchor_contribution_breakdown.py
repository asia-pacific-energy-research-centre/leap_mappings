"""Tests for the Phase 1 anchor contributor breakdown.

The breakdown decomposes a single reconcile ``difference`` into per-ESTO-pair
contributor rows. It must add no new numeric observation: the per-check sum of
contributions has to reproduce reconcile's own ``difference`` exactly
(``breakdown_remainder`` ~ 0), and it must name *which* pairs are present on the
raw side but missing on the converted side -- the pattern behind the two real
ESTO oil-family failures.
"""

import pandas as pd

from codebase.mapping_tools.reconcile_anchor_validation import (
    CONTRIBUTION_COLUMNS,
    CONTRIBUTION_SUMMARY_COLUMNS,
    build_anchor_contributions,
    build_parent_boundaries,
    check_id,
    normalize_converted_output,
)


# --------------------------------------------------------------------------- #
# ESTO-style fixtures mirroring the oil-family failure shape: a parent whose
# raw membership includes a "Transfers" row that the converted exact-row surface
# drops, so raw > converted and the anchor fails.
# --------------------------------------------------------------------------- #

def _tree() -> pd.DataFrame:
    return pd.DataFrame([
        # product axis: "06 Crude" rolls up two leaf products.
        {"dataset": "esto", "axis": "product", "code": "06 Crude", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "06.01 Crude oil", "parent_code": "06 Crude"},
        {"dataset": "esto", "axis": "product", "code": "06.02 NGL", "parent_code": "06 Crude"},
        # flow axis (needed so both axes enumerate; unused parent here).
        {"dataset": "esto", "axis": "flow", "code": "01 Production", "parent_code": ""},
        {"dataset": "esto", "axis": "flow", "code": "08 Transfers", "parent_code": ""},
    ])


def _structural() -> pd.DataFrame:
    """ESTO exact identity rows: source pair == component pair."""
    base = {"source_system": "ESTO", "comparison_scope": "esto_only", "is_exact_row": "True"}
    rows = [
        ("01 Production", "06.01 Crude oil"),
        ("01 Production", "06.02 NGL"),
        ("08 Transfers", "06.02 NGL"),
    ]
    return pd.DataFrame([
        {**base, "original_source_flow": flow, "original_source_product": product,
         "component_esto_flow": flow, "component_esto_product": product,
         "common_row_id": f"cr_{flow}_{product}"}
        for flow, product in rows
    ])


def _raw() -> pd.DataFrame:
    base = {"source_system": "ESTO", "economy": "20USA", "scenario": "historical", "year": 2023}
    return pd.DataFrame([
        {**base, "source_flow": "01 Production", "source_product": "06.01 Crude oil", "value": 100.0},
        {**base, "source_flow": "01 Production", "source_product": "06.02 NGL", "value": 40.0},
        # Transfers row present in raw parent membership...
        {**base, "source_flow": "08 Transfers", "source_product": "06.02 NGL", "value": -7.0},
    ])


def _converted() -> pd.DataFrame:
    """...but the exact-row surface drops the Transfers row entirely."""
    base = {"economy": "20USA", "scenario": "historical", "year": 2023, "source_system": "ESTO"}
    return normalize_converted_output(pd.DataFrame([
        {**base, "esto_flow": "01 Production", "esto_product": "06.01 Crude oil", "value": 100.0},
        {**base, "esto_flow": "01 Production", "esto_product": "06.02 NGL", "value": 40.0},
    ]), "ESTO")


def _boundaries():
    tree, structural = _tree(), _structural()
    return {
        axis: build_parent_boundaries(structural, tree, "ESTO", axis)
        for axis in ["flow", "product"]
    }


def _components_by_axis(converted):
    return {
        axis: set(zip(converted["esto_flow"], converted["esto_product"]))
        for axis in ["flow", "product"]
    }


def _run():
    converted = _converted()
    return build_anchor_contributions(
        _raw(), converted, _boundaries(), _components_by_axis(converted), "ESTO",
    )


# --------------------------------------------------------------------------- #
# Tests.
# --------------------------------------------------------------------------- #

def test_breakdown_reproduces_reconcile_difference_exactly():
    contributions, summary = _run()
    crude = summary[summary["parent_code"] == "06 Crude"].iloc[0]
    # raw 100 + 40 - 7 = 133; converted 140; difference = -7.
    assert crude["check_status"] == "failed"
    assert abs(crude["check_difference"] - (-7.0)) < 1e-9
    assert abs(crude["breakdown_difference"] - crude["check_difference"]) < 1e-9
    assert abs(crude["breakdown_remainder"]) < 1e-9
    assert bool(crude["lineage_complete"]) is True


def test_failing_contributor_is_named_with_exclusion_reason():
    contributions, _ = _run()
    crude = contributions[contributions["parent_code"] == "06 Crude"]
    # The one explaining contributor is the Transfers row missing on the
    # converted side; the two clean production rows contribute zero.
    explaining = crude[crude["contribution_difference"].abs() > 1e-9]
    assert len(explaining) == 1
    row = explaining.iloc[0]
    assert (row["esto_flow"], row["esto_product"]) == ("08 Transfers", "06.02 NGL")
    assert abs(row["raw_value"] - (-7.0)) < 1e-9
    assert row["converted_value"] == 0.0
    assert row["exclusion_reason"] == "raw_present_converted_row_missing"


def test_contributions_sum_to_the_two_boundary_totals():
    contributions, summary = _run()
    crude_rows = contributions[contributions["parent_code"] == "06 Crude"]
    crude_summary = summary[summary["parent_code"] == "06 Crude"].iloc[0]
    assert abs(crude_rows["raw_value"].sum() - crude_summary["breakdown_raw_total"]) < 1e-9
    assert abs(crude_rows["converted_value"].sum() - crude_summary["breakdown_converted_total"]) < 1e-9
    # Every boundary member appears exactly once (raw counted once under fan-out).
    assert crude_rows[["esto_flow", "esto_product"]].duplicated().sum() == 0


def test_explaining_rows_are_sorted_first():
    contributions, _ = _run()
    crude = contributions[contributions["parent_code"] == "06 Crude"].reset_index(drop=True)
    # Largest |difference| first: the Transfers row leads its check.
    assert (crude.iloc[0]["esto_flow"], crude.iloc[0]["esto_product"]) == ("08 Transfers", "06.02 NGL")


def test_only_failed_checks_are_broken_down_by_default():
    contributions, summary = _run()
    # The flow-axis production parents pass/are unanchorable; only the failing
    # product parent is decomposed.
    assert set(summary["check_status"]) == {"failed"}
    assert set(summary["parent_code"]) == {"06 Crude"}


def test_check_id_is_deterministic_and_schema_scoped():
    a = check_id("ESTO", "20USA", "historical", 2023, "product", "06 Crude")
    b = check_id("ESTO", "20USA", "historical", 2023, "product", "06 Crude")
    c = check_id("ESTO", "20USA", "historical", 2023, "product", "07 Petroleum")
    assert a == b and a != c
    assert a.startswith("chk_")


def test_output_schemas_are_stable():
    contributions, summary = _run()
    assert list(contributions.columns) == CONTRIBUTION_COLUMNS
    assert list(summary.columns) == CONTRIBUTION_SUMMARY_COLUMNS
