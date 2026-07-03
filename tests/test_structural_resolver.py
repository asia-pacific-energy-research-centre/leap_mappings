"""Focused tests for explicit pair rollup and tree hierarchy resolution."""

import pandas as pd

from codebase.mapping_tools.structural_resolver import (
    build_tree_index,
    prepare_pair_rollup_rules,
    resolve_ancestry,
    resolve_nearest_mapped_pair,
    resolve_pair_rollups,
)


def test_ninth_and_esto_ancestry_uses_parent_code() -> None:
    tree = pd.DataFrame([
        {"dataset": "ninth", "axis": "sector", "code": "Transport", "parent_code": ""},
        {"dataset": "ninth", "axis": "sector", "code": "Road", "parent_code": "Transport"},
        {"dataset": "ninth", "axis": "sector", "code": "Passenger", "parent_code": "Road"},
        {"dataset": "esto", "axis": "flow", "code": "15", "parent_code": ""},
        {"dataset": "esto", "axis": "flow", "code": "15.02", "parent_code": "15"},
    ])
    ninth, _ = build_tree_index(tree, "ninth", "sector")
    esto, _ = build_tree_index(tree, "esto", "flow")
    assert resolve_ancestry("Passenger", ninth)["ancestors"] == ["Road", "Transport"]
    assert resolve_ancestry("15.02", esto)["ancestors"] == ["15"]


def test_prefix_looking_text_without_edge_is_unresolved() -> None:
    tree = pd.DataFrame([{"dataset": "ninth", "axis": "sector", "code": "A/B", "parent_code": ""}])
    index, _ = build_tree_index(tree, "ninth", "sector")
    result = resolve_nearest_mapped_pair("A/B/C", "Fuel", {("A/B", "Fuel")}, "flow", index)
    assert result["status"] == "unresolved"


def test_pair_sensitive_and_blank_product_rules() -> None:
    rules = pd.DataFrame([
        {"in_flow": "Passenger", "in_product": "Oil", "out_flow": "Oil road", "out_product": "", "include": True},
        {"in_flow": "Passenger", "in_product": "Electricity", "out_flow": "Electric road", "out_product": "Power", "include": True},
        {"in_flow": "Freight", "in_product": "", "out_flow": "Road", "out_product": "", "include": True},
    ])
    index, issues = prepare_pair_rollup_rules(rules, "in_flow", "in_product", "out_flow", "out_product")
    assert issues.empty
    assert resolve_pair_rollups("Passenger", "Oil", index)["resolutions"][0]["output_pair"] == ("Oil road", "Oil")
    assert resolve_pair_rollups("Passenger", "Electricity", index)["resolutions"][0]["output_pair"] == ("Electric road", "Power")
    assert resolve_pair_rollups("Freight", "Hydrogen", index)["resolutions"][0]["output_pair"] == ("Road", "Hydrogen")


def test_duplicate_missing_parent_and_cycle_are_reported() -> None:
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "flow", "code": "A", "parent_code": "B"},
        {"dataset": "esto", "axis": "flow", "code": "B", "parent_code": "A"},
        {"dataset": "esto", "axis": "flow", "code": "C", "parent_code": "MISSING"},
    ])
    _, tree_issues = build_tree_index(tree, "esto", "flow")
    assert {"cycle", "missing_parent"}.issubset(set(tree_issues["issue_type"]))
    rules = pd.DataFrame([
        {"i": "Passenger", "ip": "", "o": "Road", "op": "", "include": True},
        {"i": "Passenger", "ip": "", "o": "Road", "op": "", "include": True},
    ])
    _, rule_issues = prepare_pair_rollup_rules(rules, "i", "ip", "o", "op")
    assert rule_issues["issue_type"].tolist() == ["exact_duplicate_rule"]


def test_passenger_and_freight_roll_to_road_without_false_duplicate() -> None:
    rules = pd.DataFrame([
        {"i": "Passenger road", "ip": "", "o": "Road", "op": "", "include": True},
        {"i": "Freight road", "ip": "", "o": "Road", "op": "", "include": True},
    ])
    index, issues = prepare_pair_rollup_rules(rules, "i", "ip", "o", "op")
    assert issues.empty
    assert resolve_pair_rollups("Passenger road", "Oil", index)["resolutions"][0]["output_pair"] == ("Road", "Oil")
    assert resolve_pair_rollups("Freight road", "Oil", index)["resolutions"][0]["output_pair"] == ("Road", "Oil")


def test_nested_aggregate_reuse_is_not_a_conflict_but_unrelated_targets_are() -> None:
    rules = pd.DataFrame([
        {"i": "Passenger", "ip": "Oil", "o": "Road", "op": "Oil"},
        {"i": "Passenger", "ip": "Oil", "o": "Transport", "op": "Oil"},
    ])
    _, nested_issues = prepare_pair_rollup_rules(
        rules, "i", "ip", "o", "op", flow_parent_index={"Road": "Transport", "Transport": "TFC", "TFC": ""}
    )
    assert nested_issues.empty
    unrelated = rules.copy()
    unrelated.loc[1, "o"] = "Industry"
    _, conflict_issues = prepare_pair_rollup_rules(
        unrelated, "i", "ip", "o", "op", flow_parent_index={"Road": "Transport", "Industry": "TFC"}
    )
    assert conflict_issues["issue_type"].tolist() == ["conflicting_assignment"]


def test_indirect_rule_cycle_is_reported() -> None:
    rules = pd.DataFrame([
        {"i": "A", "ip": "P", "o": "B", "op": "P"},
        {"i": "B", "ip": "P", "o": "A", "op": "P"},
    ])
    _, issues = prepare_pair_rollup_rules(rules, "i", "ip", "o", "op")
    assert "cycle" in set(issues["issue_type"])
