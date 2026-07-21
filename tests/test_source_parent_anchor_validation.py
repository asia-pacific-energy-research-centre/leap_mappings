"""Focused synthetic tests for original-source parent anchor validation."""

import pandas as pd

from codebase.mapping_tools.source_parent_anchor_validation import (
    summarise_source_parent_anchors,
    validate_source_parent_anchors,
)


def _fixture(child_b_value: float = 6, include_child_b_mapping: bool = True):
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "P", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "P.1", "parent_code": "P"},
        {"dataset": "esto", "axis": "product", "code": "P.2", "parent_code": "P"},
    ])
    source = pd.DataFrame([
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P", "value": 10},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P.1", "value": 4},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P.2", "value": child_b_value},
    ])
    mapping_rows = [
        {"source_system": "ESTO", "source_flow": "F", "source_product": "P.1", "component_esto_flow": "F", "component_esto_product": "P.1"},
    ]
    if include_child_b_mapping:
        mapping_rows.append({"source_system": "ESTO", "source_flow": "F", "source_product": "P.2", "component_esto_flow": "F", "component_esto_product": "P.2"})
    mappings = pd.DataFrame(mapping_rows)
    common = pd.DataFrame([
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "P.1", "common_row_id": "c1"},
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "P.2", "common_row_id": "c2"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "c1", "value": 4},
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "c2", "value": child_b_value},
    ])
    return source, tree, mappings, common, comparison


def test_exact_parent_children_match_without_double_counting() -> None:
    detail = validate_source_parent_anchors(*_fixture())
    row = detail.iloc[0]
    assert row["status"] == "passed"
    assert row["frontier_sum"] == 10
    assert row["frontier_row_count"] == 2


def test_missing_child_fails_and_is_reported() -> None:
    # Genuine gap: parent 10 but mapped frontier only explains 4 -> failed.
    detail = validate_source_parent_anchors(*_fixture(include_child_b_mapping=False))
    row = detail.iloc[0]
    assert row["status"] == "failed"
    assert row["reason"] == "incomplete_frontier"
    assert row["missing_expected_children"] == "P.2"


def test_incomplete_frontier_that_reconciles_is_passed() -> None:
    # Parent reconciles to its mapped leaf exactly, but one leaf child is
    # unmapped (an intentional placeholder). "Reconciles wins" -> passed.
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "P", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "P.1", "parent_code": "P"},
        {"dataset": "esto", "axis": "product", "code": "P.2", "parent_code": "P"},
    ])
    source = pd.DataFrame([
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P", "value": 4},
    ])
    mappings = pd.DataFrame([
        {"source_system": "ESTO", "source_flow": "F", "source_product": "P.1", "component_esto_flow": "F", "component_esto_product": "P.1"},
    ])
    common = pd.DataFrame([
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "P.1", "common_row_id": "c1"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "c1", "value": 4},
    ])
    row = validate_source_parent_anchors(source, tree, mappings, common, comparison).iloc[0]
    assert row["status"] == "passed"
    assert row["reason"] == "within_tolerance_incomplete_frontier"
    assert row["missing_expected_children"] == "P.2"  # still reported for lineage
    assert row["frontier_sum"] == 4


def test_tolerance_boundary_and_summary() -> None:
    source, tree, mappings, common, comparison = _fixture(child_b_value=6.01)
    comparison.loc[comparison["common_row_id"] == "c2", "value"] = 6
    detail = validate_source_parent_anchors(
        source, tree, mappings, common, comparison, tolerance=0.001
    )
    assert detail.iloc[0]["status"] == "passed"
    summary = summarise_source_parent_anchors(detail)
    assert summary.iloc[0][["eligible", "passed", "failed", "skipped"]].tolist() == [1, 1, 0, 0]


def test_missing_intermediate_resolves_to_grandchildren() -> None:
    source, tree, mappings, common, comparison = _fixture()
    tree = pd.concat([tree, pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "P.I", "parent_code": "P"},
        {"dataset": "esto", "axis": "product", "code": "P.1", "parent_code": "P.I"},
        {"dataset": "esto", "axis": "product", "code": "P.2", "parent_code": "P.I"},
    ])], ignore_index=True)
    tree = tree[~((tree["code"].isin(["P.1", "P.2"])) & (tree["parent_code"] == "P"))]
    detail = validate_source_parent_anchors(source, tree, mappings, common, comparison)
    parent = detail[detail["parent_code"] == "P"].iloc[0]
    assert parent["status"] == "passed"
    assert parent["frontier_row_count"] == 2


def test_zero_eligible_summary_is_not_passed() -> None:
    summary = summarise_source_parent_anchors(pd.DataFrame())
    assert summary.empty


# --- Focused tests for the vectorized restructure of the anchor loop ---

def _multi_partition_fixture():
    """Parent P over two economies and two years; comparison only for E1."""
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "P", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "P.1", "parent_code": "P"},
        {"dataset": "esto", "axis": "product", "code": "P.2", "parent_code": "P"},
    ])
    source = pd.DataFrame([
        {"source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P", "value": 10},
        {"source_system": "ESTO", "economy": "E2", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P", "value": 20},
        {"source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2023, "source_flow": "F", "source_product": "P", "value": 5},
    ])
    mappings = pd.DataFrame([
        {"source_system": "ESTO", "source_flow": "F", "source_product": "P.1", "component_esto_flow": "F", "component_esto_product": "P.1"},
        {"source_system": "ESTO", "source_flow": "F", "source_product": "P.2", "component_esto_flow": "F", "component_esto_product": "P.2"},
    ])
    common = pd.DataFrame([
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "P.1", "common_row_id": "c1"},
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "P.2", "common_row_id": "c2"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2022, "common_row_id": "c1", "value": 4},
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2022, "common_row_id": "c2", "value": 6},
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2023, "common_row_id": "c1", "value": 2},
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2023, "common_row_id": "c2", "value": 3},
    ])
    return source, tree, mappings, common, comparison


def test_partitions_do_not_bleed_and_absent_frontier_fails() -> None:
    detail = validate_source_parent_anchors(*_multi_partition_fixture())
    by_key = {(r["economy"], r["year"]): r for _, r in detail.iterrows()}
    # Each (economy, year) keeps its own parent total — no cross-partition sum.
    assert by_key[("E1", 2022)]["parent_value"] == 10
    assert by_key[("E1", 2022)]["frontier_sum"] == 10
    assert by_key[("E1", 2022)]["status"] == "passed"
    assert by_key[("E1", 2023)]["parent_value"] == 5
    assert by_key[("E1", 2023)]["frontier_sum"] == 5
    assert by_key[("E1", 2023)]["status"] == "passed"
    # E2 has a resolvable frontier but no comparison rows -> frontier_rows_absent.
    assert by_key[("E2", 2022)]["parent_value"] == 20
    assert by_key[("E2", 2022)]["frontier_sum"] == 0
    assert by_key[("E2", 2022)]["status"] == "failed"
    assert by_key[("E2", 2022)]["reason"] == "frontier_rows_absent"


def test_zero_parent_without_source_frontier_is_unanchorable() -> None:
    source, tree, mappings, common, comparison = _multi_partition_fixture()
    source = source[(source["economy"] == "E2")].copy()
    source["value"] = 0.0
    detail = validate_source_parent_anchors(source, tree, mappings, common, comparison)

    row = detail.iloc[0]
    assert row["status"] == "skipped"
    assert row["reason"] == "no_observed_source_frontier"


def test_missing_common_boundary_is_unanchorable_even_when_source_value_is_nonzero() -> None:
    source, tree, mappings, common, comparison = _fixture()
    common = pd.DataFrame([
        {"comparison_scope": "esto_only", "component_esto_flow": "OTHER",
         "component_esto_product": "OTHER", "common_row_id": "cX"},
    ])
    comparison = comparison.iloc[0:0]

    row = validate_source_parent_anchors(source, tree, mappings, common, comparison).iloc[0]

    assert row["status"] == "skipped"
    assert row["reason"] == "no_anchorable_common_esto_boundary"


def test_signed_parent_and_frontier_sums() -> None:
    source, tree, mappings, common, comparison = _multi_partition_fixture()
    # Split E1/2022 parent into a positive and a negative row (nets to 10).
    source = pd.DataFrame([
        {"source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P", "value": 12},
        {"source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P", "value": -2},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2022, "common_row_id": "c1", "value": 13},
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2022, "common_row_id": "c2", "value": -3},
    ])
    row = validate_source_parent_anchors(source, tree, mappings, common, comparison).iloc[0]
    assert row["parent_value"] == 10
    assert row["parent_positive_value"] == 12
    assert row["parent_negative_value"] == -2
    assert row["frontier_sum"] == 10
    assert row["frontier_positive_sum"] == 13
    assert row["frontier_negative_sum"] == -3
    assert row["status"] == "passed"


def test_unmodelled_source_codes_are_dropped() -> None:
    # Parent product coded "19 ..." (an aggregate fuel) must be dropped when
    # fuel 19 is in the unmodelled-source set, regardless of its numeric outcome.
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "19 Total", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "19.01 A", "parent_code": "19 Total"},
    ])
    source = pd.DataFrame([
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "19 Total", "value": 10},
    ])
    mappings = pd.DataFrame([
        {"source_system": "ESTO", "source_flow": "F", "source_product": "19.01 A", "component_esto_flow": "F", "component_esto_product": "19.01 A"},
    ])
    common = pd.DataFrame([
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "19.01 A", "common_row_id": "c1"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "c1", "value": 999},
    ])
    without = validate_source_parent_anchors(source, tree, mappings, common, comparison)
    assert not without.empty  # normally evaluated and reported
    withx = validate_source_parent_anchors(
        source, tree, mappings, common, comparison,
        unmodelled_source_codes={"sector": set(), "fuel": {19}},
    )
    assert withx.empty  # excepted fuel 19 -> row dropped entirely
    # A non-excepted fuel code is unaffected.
    keep = validate_source_parent_anchors(
        source, tree, mappings, common, comparison,
        unmodelled_source_codes={"sector": set(), "fuel": {99}},
    )
    assert not keep.empty


def test_scope_without_anchorable_boundary_is_skipped() -> None:
    source, tree, mappings, common, comparison = _multi_partition_fixture()
    source = source[(source["economy"] == "E1") & (source["year"] == 2022)]
    # Add a second scope that ESTO participates in but whose common rows do NOT
    # cover P.1/P.2 -> frontier resolves to no common_row_id -> skipped.
    common = pd.concat([common, pd.DataFrame([
        {"comparison_scope": "esto_leap", "component_esto_flow": "F", "component_esto_product": "OTHER", "common_row_id": "cX"},
    ])], ignore_index=True)
    detail = validate_source_parent_anchors(source, tree, mappings, common, comparison)
    by_scope = {r["comparison_scope"]: r for _, r in detail.iterrows()}
    assert by_scope["esto_only"]["status"] == "passed"
    assert by_scope["esto_leap"]["status"] == "skipped"
    assert by_scope["esto_leap"]["reason"] == "no_anchorable_common_esto_boundary"
