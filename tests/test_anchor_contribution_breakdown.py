"""Tests for the anchor contributor breakdown (Option A: honest, no allocation).

The breakdown decomposes a single reconcile ``difference`` into contributor
rows. It must add no new numeric observation: the per-check totals have to
reproduce reconcile's own ``difference`` (``breakdown_remainder`` ~ 0). Bijective
1:1 edges are netted per row; entangled fan-out / many-to-one members are listed
one-sided and flagged unresolved rather than split with a fabricated share.
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


def _components_by_axis(converted):
    return {
        axis: set(zip(converted["esto_flow"], converted["esto_product"]))
        for axis in ["flow", "product"]
    }


# --------------------------------------------------------------------------- #
# ESTO fixtures: identity rows (source pair == component), oil-family shape.
# A "Transfers" row is a member of the raw parent but dropped (zero) on the
# converted exact-row surface, so raw > converted and the anchor fails.
# --------------------------------------------------------------------------- #

def _esto_tree() -> pd.DataFrame:
    return pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "06 Crude", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "06.01 Crude oil", "parent_code": "06 Crude"},
        {"dataset": "esto", "axis": "product", "code": "06.02 NGL", "parent_code": "06 Crude"},
        {"dataset": "esto", "axis": "flow", "code": "01 Production", "parent_code": ""},
        {"dataset": "esto", "axis": "flow", "code": "08 Transfers", "parent_code": ""},
    ])


def _esto_structural() -> pd.DataFrame:
    base = {"source_system": "ESTO", "comparison_scope": "esto_only", "is_exact_row": "True"}
    rows = [
        ("01 Production", "06.01 Crude oil"),
        ("01 Production", "06.02 NGL"),
        ("08 Transfers", "06.02 NGL"),
    ]
    return pd.DataFrame([
        {**base, "original_source_flow": flow, "original_source_product": product,
         "component_esto_flow": flow, "component_esto_product": product,
         "common_row_id": f"cr_{flow}_{product}", "relationship_id": f"rel_{flow}_{product}"}
        for flow, product in rows
    ])


def _esto_raw() -> pd.DataFrame:
    base = {"source_system": "ESTO", "economy": "20USA", "scenario": "historical", "year": 2023}
    return pd.DataFrame([
        {**base, "source_flow": "01 Production", "source_product": "06.01 Crude oil", "value": 100.0},
        {**base, "source_flow": "01 Production", "source_product": "06.02 NGL", "value": 40.0},
        {**base, "source_flow": "08 Transfers", "source_product": "06.02 NGL", "value": -7.0},
    ])


def _esto_converted() -> pd.DataFrame:
    base = {"economy": "20USA", "scenario": "historical", "year": 2023, "source_system": "ESTO"}
    return normalize_converted_output(pd.DataFrame([
        {**base, "esto_flow": "01 Production", "esto_product": "06.01 Crude oil", "value": 100.0},
        {**base, "esto_flow": "01 Production", "esto_product": "06.02 NGL", "value": 40.0},
    ]), "ESTO")


def _run_esto():
    converted = _esto_converted()
    boundaries = {
        axis: build_parent_boundaries(_esto_structural(), _esto_tree(), "ESTO", axis)
        for axis in ["flow", "product"]
    }
    return build_anchor_contributions(
        _esto_raw(), converted, boundaries, _components_by_axis(converted), "ESTO",
    )


def test_esto_identity_rows_all_resolve_and_reproduce_difference():
    contributions, summary = _run_esto()
    crude = summary[summary["parent_code"] == "06 Crude"].iloc[0]
    assert crude["check_status"] == "failed"
    # raw 100 + 40 - 7 = 133; converted 140; difference = -7.
    assert abs(crude["check_difference"] - (-7.0)) < 1e-9
    assert abs(crude["breakdown_remainder"]) < 1e-9
    # ESTO is pure identity -> everything bijective, nothing entangled.
    assert bool(crude["fully_attributed"]) is True
    assert crude["unresolved_source_count"] == 0
    assert crude["unresolved_component_count"] == 0
    rows = contributions[contributions["parent_code"] == "06 Crude"]
    assert set(rows["counting_role"]) == {"resolved_pair"}


def test_esto_failing_row_named_with_exclusion_reason():
    contributions, _ = _run_esto()
    crude = contributions[contributions["parent_code"] == "06 Crude"]
    explaining = crude[crude["contribution_difference"].abs() > 1e-9]
    assert len(explaining) == 1
    row = explaining.iloc[0]
    assert (row["esto_flow"], row["esto_product"]) == ("08 Transfers", "06.02 NGL")
    assert (row["source_flow"], row["source_product"]) == ("08 Transfers", "06.02 NGL")
    assert abs(row["raw_value"] - (-7.0)) < 1e-9
    assert row["converted_value"] == 0.0
    assert row["mapping_cardinality"] == "direct"
    assert row["value_quality"] == "exact_direct"
    assert row["mapping_status"] == "resolved"
    assert row["exclusion_reason"] == "raw_present_converted_row_missing"


# --------------------------------------------------------------------------- #
# Ninth-style fan-out fixtures: one source pair fans out to three ESTO
# components (no allocation share applied), alongside one clean 1:1 pair.
# --------------------------------------------------------------------------- #

def _ninth_tree() -> pd.DataFrame:
    return pd.DataFrame([
        {"dataset": "ninth", "axis": "sector", "code": "08_transfers", "parent_code": ""},
        {"dataset": "ninth", "axis": "sector", "code": "08_transfers_leaf", "parent_code": "08_transfers"},
    ])


def _ninth_structural() -> pd.DataFrame:
    base = {"source_system": "NINTH", "comparison_scope": "esto_leap_ninth", "is_exact_row": "True"}
    # S1 fans out to three components; S2 is a clean 1:1.
    edges = [
        ("08_transfers", "06_02_ngl", "08 Transfers", "06.02 NGL"),
        ("08_transfers", "06_02_ngl", "08 Transfers", "06.01 Crude oil"),
        ("08_transfers", "06_02_ngl", "08 Transfers", "06.03 Refinery feedstocks"),
        ("08_transfers", "07_09_lpg", "08 Transfers", "07.09 LPG"),
    ]
    return pd.DataFrame([
        {**base, "original_source_flow": sf, "original_source_product": sp,
         "component_esto_flow": cf, "component_esto_product": cp,
         "common_row_id": f"cr_{cf}_{cp}", "relationship_id": f"rel_{sf}_{sp}_{cp}"}
        for sf, sp, cf, cp in edges
    ])


def _ninth_raw() -> pd.DataFrame:
    base = {"source_system": "NINTH", "economy": "20USA", "scenario": "reference", "year": 2024}
    return pd.DataFrame([
        {**base, "source_flow": "08_transfers", "source_product": "06_02_ngl", "value": 100.0},
        {**base, "source_flow": "08_transfers", "source_product": "07_09_lpg", "value": 50.0},
    ])


def _ninth_converted() -> pd.DataFrame:
    base = {"economy": "20USA", "scenario": "reference", "year": 2024, "source_system": "NINTH"}
    return normalize_converted_output(pd.DataFrame([
        {**base, "esto_flow": "08 Transfers", "esto_product": "06.02 NGL", "value": 100.0},
        {**base, "esto_flow": "08 Transfers", "esto_product": "06.01 Crude oil", "value": 100.0},
        {**base, "esto_flow": "08 Transfers", "esto_product": "06.03 Refinery feedstocks", "value": 100.0},
        {**base, "esto_flow": "08 Transfers", "esto_product": "07.09 LPG", "value": 50.0},
    ]), "NINTH")


def _run_ninth():
    converted = _ninth_converted()
    boundaries = {
        axis: build_parent_boundaries(_ninth_structural(), _ninth_tree(), "NINTH", axis)
        for axis in ["flow", "product"]
    }
    return build_anchor_contributions(
        _ninth_raw(), converted, boundaries, _components_by_axis(converted), "NINTH",
    )


def test_fanout_reproduces_difference_but_is_only_partially_attributed():
    contributions, summary = _run_ninth()
    t = summary[summary["parent_code"] == "08_transfers"].iloc[0]
    # raw 100 + 50 = 150; converted 100*3 + 50 = 350; difference = -200.
    assert abs(t["check_difference"] - (-200.0)) < 1e-9
    assert abs(t["breakdown_remainder"]) < 1e-9
    assert bool(t["fully_attributed"]) is False
    # resolved part = the clean LPG pair (0); unresolved = the fanned-out -200.
    assert abs(t["resolved_difference"] - 0.0) < 1e-9
    assert abs(t["unresolved_difference"] - (-200.0)) < 1e-9
    assert t["unresolved_source_count"] == 1        # the NGL source pair
    assert t["unresolved_component_count"] == 3      # its three targets


def test_fanout_source_is_flagged_not_split():
    contributions, _ = _run_ninth()
    rows = contributions[contributions["parent_code"] == "08_transfers"]
    fan_src = rows[(rows["counting_role"] == "raw_source")]
    assert len(fan_src) == 1
    row = fan_src.iloc[0]
    assert (row["source_flow"], row["source_product"]) == ("08_transfers", "06_02_ngl")
    assert abs(row["raw_value"] - 100.0) < 1e-9
    assert pd.isna(row["converted_value"])          # never fabricated
    assert pd.isna(row["contribution_difference"])
    assert row["mapping_cardinality"] == "fanout"
    assert row["value_quality"] == "unknown"
    assert row["mapping_status"] == "unsafe_unallocated_fanout"
    # Its three targets appear only as converted-side ledger rows.
    targets = rows[rows["counting_role"] == "converted_component"]
    assert len(targets) == 3
    assert set(targets["mapping_status"]) == {"unsafe_unallocated_fanout"}


def test_clean_pair_still_resolves_alongside_fanout():
    contributions, _ = _run_ninth()
    rows = contributions[contributions["parent_code"] == "08_transfers"]
    resolved = rows[rows["counting_role"] == "resolved_pair"]
    assert len(resolved) == 1
    row = resolved.iloc[0]
    assert (row["source_flow"], row["esto_product"]) == ("08_transfers", "07.09 LPG")
    assert abs(row["contribution_difference"] - 0.0) < 1e-9
    assert row["mapping_status"] == "resolved"


def test_each_source_and_component_counted_once():
    contributions, summary = _run_ninth()
    rows = contributions[contributions["parent_code"] == "08_transfers"]
    t = summary[summary["parent_code"] == "08_transfers"].iloc[0]
    # Every source pair appears once (resolved or raw ledger); same for targets.
    raw_side = rows[rows["counting_role"].isin(["resolved_pair", "raw_source"])]
    conv_side = rows[rows["counting_role"].isin(["resolved_pair", "converted_component"])]
    assert raw_side[["source_flow", "source_product"]].duplicated().sum() == 0
    assert conv_side[["esto_flow", "esto_product"]].duplicated().sum() == 0
    # Column sums equal reconcile's two sides.
    assert abs(raw_side["raw_value"].sum() - t["breakdown_raw_total"]) < 1e-9
    assert abs(conv_side["converted_value"].sum() - t["breakdown_converted_total"]) < 1e-9


# --------------------------------------------------------------------------- #
# Cross-cutting.
# --------------------------------------------------------------------------- #

def test_check_id_is_deterministic_and_schema_scoped():
    a = check_id("ESTO", "20USA", "historical", 2023, "product", "06 Crude")
    b = check_id("ESTO", "20USA", "historical", 2023, "product", "06 Crude")
    c = check_id("ESTO", "20USA", "historical", 2023, "product", "07 Petroleum")
    assert a == b and a != c
    assert a.startswith("chk_")


def test_output_schemas_are_stable():
    contributions, summary = _run_esto()
    assert list(contributions.columns) == CONTRIBUTION_COLUMNS
    assert list(summary.columns) == CONTRIBUTION_SUMMARY_COLUMNS
