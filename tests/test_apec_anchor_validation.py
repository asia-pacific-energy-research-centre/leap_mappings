"""Tests for APEC-first anchor validation and targeted economy attribution."""

from __future__ import annotations

import pandas as pd

from codebase.mapping_tools import apec_anchor_validation as module


def _detail_row(economy: str, status: str, difference: float) -> dict[str, object]:
    return {
        "validation_axis": "flow",
        "comparison_scope": "esto_leap_ninth",
        "source_system": "NINTH",
        "economy": economy,
        "scenario": "reference",
        "year": 2030,
        "other_axis_value": "08_gas",
        "parent_code": "09_total",
        "status": status,
        "reason": "difference_exceeds_tolerance" if status == "failed" else "within_tolerance",
        "parent_value": 10.0,
        "frontier_sum": 10.0 - difference,
        "difference": difference,
        "abs_error": abs(difference),
    }


def test_aggregate_anchor_inputs_sums_only_economy() -> None:
    source = pd.DataFrame([
        {"source_system": "NINTH", "economy": "01AUS", "scenario": "reference", "year": 2030, "source_flow": "09_total", "source_product": "08_gas", "value": 4.0},
        {"source_system": "NINTH", "economy": "20USA", "scenario": "reference", "year": 2030, "source_flow": "09_total", "source_product": "08_gas", "value": 6.0},
        {"source_system": "NINTH", "economy": "20USA", "scenario": "target", "year": 2030, "source_flow": "09_total", "source_product": "08_gas", "value": 7.0},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_leap_ninth", "source_system": "NINTH", "economy": "01AUS", "scenario": "reference", "year": 2030, "common_row_id": "row-1", "value": 3.0},
        {"comparison_scope": "esto_leap_ninth", "source_system": "NINTH", "economy": "20USA", "scenario": "reference", "year": 2030, "common_row_id": "row-1", "value": 5.0},
    ])

    apec_source, apec_comparison = module.aggregate_anchor_inputs_to_apec(
        source, comparison
    )

    assert set(apec_source["economy"]) == {module.APEC_ECONOMY}
    assert set(apec_comparison["economy"]) == {module.APEC_ECONOMY}
    assert sorted(apec_source["value"].tolist()) == [7.0, 10.0]
    assert apec_comparison.iloc[0]["value"] == 8.0


def test_apec_first_runs_economies_only_for_failed_apec_issue(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_validate_source_parent_anchors(**kwargs):
        calls.append(kwargs)
        economies = set(kwargs["source_df"]["economy"].astype(str))
        if economies == {module.APEC_ECONOMY}:
            return pd.DataFrame([_detail_row(module.APEC_ECONOMY, "failed", 3.0)])
        assert kwargs["issue_filter"] is not None
        return pd.DataFrame([
            _detail_row("01AUS", "failed", 2.0),
            _detail_row("20USA", "passed", 0.0),
            {**_detail_row("05PRC", "failed", 9.0), "parent_code": "unrelated"},
        ])

    monkeypatch.setattr(
        module, "validate_source_parent_anchors", fake_validate_source_parent_anchors
    )
    source = pd.DataFrame([
        {"source_system": "NINTH", "economy": economy, "scenario": "reference", "year": 2030, "source_flow": "09_total", "source_product": "08_gas", "value": value}
        for economy, value in [("01AUS", 4.0), ("20USA", 6.0)]
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_leap_ninth", "source_system": "NINTH", "economy": economy, "scenario": "reference", "year": 2030, "common_row_id": "row-1", "value": value}
        for economy, value in [("01AUS", 3.0), ("20USA", 5.0)]
    ])

    result = module.validate_source_parent_anchors_apec_first(
        source_df=source,
        source_tree_df=pd.DataFrame(),
        source_mapping_df=pd.DataFrame(),
        common_rows_df=pd.DataFrame(),
        comparison_df=comparison,
    )

    assert len(calls) == 2
    assert calls[0]["absolute_tolerance"] == module.APEC_ABSOLUTE_TOLERANCE_PJ
    assert calls[1]["absolute_tolerance"] is None
    assert result["apec_detail"].iloc[0]["attribution_status"] == "economy_examples_found"
    assert set(result["economy_examples"]["economy"]) == {"01AUS", "20USA"}
    assert "unrelated" not in set(result["economy_examples"]["parent_code"])


def test_failed_apec_issue_without_failed_economy_example_is_flagged() -> None:
    apec = pd.DataFrame([_detail_row(module.APEC_ECONOMY, "failed", 3.0)])
    examples = pd.DataFrame([_detail_row("01AUS", "passed", 0.0)])
    issues = module.select_apec_anchor_issues(apec)
    examples = module.select_economy_examples_for_apec_issues(examples, issues)

    result = module.add_apec_attribution_status(apec, examples)

    assert result.iloc[0]["attribution_status"] == "no_economy_example_found"
    assert examples.iloc[0]["attribution_status"] == "no_economy_example_found"


def test_raw_ninth_hierarchy_failure_survives_missing_common_boundary() -> None:
    """A mapped Ninth parent remains reviewable without a Common ESTO frontier."""
    tree = pd.DataFrame([
        {"dataset": "ninth", "axis": "sector", "code": "09_total", "parent_code": ""},
        {"dataset": "ninth", "axis": "sector", "code": "09_child", "parent_code": "09_total"},
        {"dataset": "ninth", "axis": "fuel", "code": "16_09_other_sources", "parent_code": ""},
        {"dataset": "ninth", "axis": "fuel", "code": "16_others_unallocated", "parent_code": ""},
    ])
    source = pd.DataFrame([
        {"source_system": "NINTH", "economy": "05PRC", "scenario": "reference", "year": 2030,
         "source_flow": "09_total", "source_product": "16_others_unallocated", "value": -10.0},
        {"source_system": "NINTH", "economy": "20USA", "scenario": "reference", "year": 2030,
         "source_flow": "09_total", "source_product": "16_others_unallocated", "value": -5.0},
        {"source_system": "NINTH", "economy": "20USA", "scenario": "reference", "year": 2030,
         "source_flow": "09_child", "source_product": "16_others_unallocated", "value": -5.0},
        *[
            {"source_system": "NINTH", "economy": economy, "scenario": "reference", "year": 2030,
             "source_flow": "09_total", "source_product": "16_09_other_sources", "value": 0.0}
            for economy in ["05PRC", "20USA"]
        ],
    ])
    mappings = pd.DataFrame([
        {"source_system": "NINTH", "source_flow": "09_total", "source_product": "16_others_unallocated",
         "component_esto_flow": "09 Total", "component_esto_product": "16.09 Other sources"},
        {"source_system": "NINTH", "source_flow": "09_total", "source_product": "16_09_other_sources",
         "component_esto_flow": "09 Total", "component_esto_product": "16.09 Other sources"},
    ])
    common = pd.DataFrame([
        {"comparison_scope": "esto_leap_ninth", "component_esto_flow": "unrelated",
         "component_esto_product": "unrelated", "common_row_id": "unrelated-row"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_leap_ninth", "source_system": "NINTH", "economy": economy,
         "scenario": "reference", "year": 2030, "common_row_id": "unrelated-row", "value": 0.0}
        for economy in ["05PRC", "20USA"]
    ])

    result = module.validate_source_parent_anchors_apec_first(
        source_df=source,
        source_tree_df=tree,
        source_mapping_df=mappings,
        common_rows_df=common,
        comparison_df=comparison,
    )

    apec_row = result["apec_detail"][
        result["apec_detail"]["parent_code"].eq("09_total")
        & result["apec_detail"]["other_axis_value"].eq(
            "16_09_other_sources + 16_others_unallocated"
        )
    ].iloc[0]
    assert apec_row["status"] == "failed"
    assert apec_row["reason"] == "parent_child_source_inconsistency"
    assert apec_row["parent_value"] == -15.0
    assert apec_row["raw_source_frontier_sum"] == -5.0
    assert apec_row["raw_source_difference"] == -10.0
    assert apec_row["attribution_status"] == "economy_examples_found"

    examples = result["economy_examples"]
    by_economy = {
        row["economy"]: row for _, row in examples[examples["parent_code"].eq("09_total")].iterrows()
    }
    assert by_economy["05PRC"]["status"] == "failed"
    assert by_economy["20USA"]["status"] == "skipped"
    assert by_economy["20USA"]["raw_source_difference"] == 0.0
