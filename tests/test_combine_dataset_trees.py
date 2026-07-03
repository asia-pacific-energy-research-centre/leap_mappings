"""Tests for the combined dataset-tree artifact consumed by lineage validation."""

import pandas as pd

from codebase.mapping_tools.build_dataset_tree_structure import (
    TREE_COLS,
    combine_dataset_trees,
)
from codebase.mapping_tools.structural_resolver import (
    TREE_REQUIRED_COLUMNS,
    build_tree_index,
)


def _tree(dataset: str, axis: str) -> pd.DataFrame:
    rows = [
        {"dataset": dataset, "axis": axis, "code": "Root", "parent_code": ""},
        {"dataset": dataset, "axis": axis, "code": "Child", "parent_code": "Root"},
    ]
    return pd.DataFrame(rows, columns=[c for c in TREE_COLS if c in rows[0]] + [])


def test_combine_keeps_all_datasets_and_required_columns() -> None:
    combined = combine_dataset_trees([
        _tree("esto", "flow"),
        _tree("ninth", "sector"),
        _tree("leap", "sector"),
    ])
    assert TREE_REQUIRED_COLUMNS.issubset(combined.columns)
    assert set(combined["dataset"]) == {"esto", "ninth", "leap"}
    # The combined frame must be directly consumable by the validator's index builder.
    index, issues = build_tree_index(combined, "leap", "sector")
    assert index.get("Child") == "Root"
    assert issues.empty


def test_combine_drops_empty_frames() -> None:
    combined = combine_dataset_trees([
        _tree("esto", "flow"),
        pd.DataFrame(columns=TREE_COLS),
    ])
    assert set(combined["dataset"]) == {"esto"}


def test_combine_all_empty_returns_typed_empty() -> None:
    combined = combine_dataset_trees([pd.DataFrame(columns=TREE_COLS)])
    assert combined.empty
    assert list(combined.columns) == TREE_COLS
