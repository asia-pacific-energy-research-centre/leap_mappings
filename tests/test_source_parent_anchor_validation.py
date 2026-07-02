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
    detail = validate_source_parent_anchors(*_fixture(include_child_b_mapping=False))
    row = detail.iloc[0]
    assert row["status"] == "failed"
    assert row["reason"] == "incomplete_frontier"
    assert row["missing_expected_children"] == "P.2"


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
