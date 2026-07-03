"""Focused tests for exact lineage anchor validation."""

import pandas as pd

from codebase.mapping_tools.validate_lineage_anchors import (
    summarise_validation,
    validate_partition_lineage,
)


def _tree(dataset: str = "leap") -> pd.DataFrame:
    axes = ("sector", "fuel") if dataset in {"leap", "ninth"} else ("flow", "product")
    return pd.DataFrame([
        {"dataset": dataset, "axis": axes[0], "code": "Road", "parent_code": ""},
        {"dataset": dataset, "axis": axes[0], "code": "Passenger", "parent_code": "Road"},
        {"dataset": dataset, "axis": axes[0], "code": "Freight", "parent_code": "Road"},
        {"dataset": dataset, "axis": axes[1], "code": "Energy", "parent_code": ""},
        {"dataset": dataset, "axis": axes[1], "code": "Oil", "parent_code": "Energy"},
        {"dataset": dataset, "axis": axes[1], "code": "Power", "parent_code": "Energy"},
    ])


def _source(system: str = "LEAP") -> pd.DataFrame:
    base = {"source_system": system, "economy": "20_USA", "scenario": "Reference", "year": 2023}
    return pd.DataFrame([
        {**base, "source_flow": "Road", "source_product": "Oil", "value": 10},
        {**base, "source_flow": "Passenger", "source_product": "Oil", "value": 4},
        {**base, "source_flow": "Freight", "source_product": "Oil", "value": 6},
        {**base, "source_flow": "Passenger", "source_product": "Energy", "value": 7},
        {**base, "source_flow": "Passenger", "source_product": "Power", "value": 3},
    ])


def _lineage(system: str = "LEAP", include_freight: bool = True, contaminate: bool = False) -> pd.DataFrame:
    base = {"source_system": system, "economy": "20_USA", "scenario": "Reference", "year": 2023, "comparison_scope": "all", "mapping_view": "rolled:road", "evidence_type": "rollup_rule" if system == "LEAP" else "tree"}
    rows = [
        {**base, "original_source_flow": "Passenger", "original_source_product": "Oil", "common_row_id": "c_road", "value": 4},
        {**base, "original_source_flow": "Passenger", "original_source_product": "Power", "common_row_id": "c_power", "value": 3},
    ]
    if include_freight:
        rows.append({**base, "original_source_flow": "Freight", "original_source_product": "Oil", "common_row_id": "c_road", "value": 6})
    if contaminate:
        rows.append({**base, "original_source_flow": "Industry", "original_source_product": "Oil", "common_row_id": "c_road", "value": 2})
    return pd.DataFrame(rows)


def test_exact_children_pass_and_both_axes_are_checked() -> None:
    detail = validate_partition_lineage(_source(), _lineage(), _tree())
    flow = detail[(detail["validation_axis"] == "flow") & (detail["parent_code"] == "Road")].iloc[0]
    assert flow["status"] == "passed"
    assert set(detail["validation_axis"]) == {"flow", "product"}


def test_missing_child_and_contamination_are_actionable() -> None:
    missing = validate_partition_lineage(_source(), _lineage(include_freight=False), _tree())
    assert "missing_mapped_child" in set(missing["reason"])
    contaminated = validate_partition_lineage(_source(), _lineage(contaminate=True), _tree())
    assert "common_boundary_contamination" in set(contaminated["reason"])


def test_ninth_and_esto_use_tree_evidence() -> None:
    for system, dataset in [("NINTH", "ninth"), ("ESTO", "esto")]:
        detail = validate_partition_lineage(_source(system), _lineage(system), _tree(dataset))
        assert "passed" in set(detail["status"])


def test_empty_validation_is_not_passed() -> None:
    summary = summarise_validation(pd.DataFrame())
    assert summary.iloc[0]["status"] == "failed"
    assert summary.iloc[0]["reason"] == "empty_validation"
