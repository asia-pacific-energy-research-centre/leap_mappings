#%%
"""Focused tests for the low-memory source-parent anchor rerun workflow."""

#%%
from pathlib import Path

import pandas as pd

from codebase.mapping_tools.anchor_validation_only_workflow import (
    ANCHOR_COMPARISON_COLUMNS,
    _read_anchor_comparison_slice,
)


def test_read_anchor_comparison_slice_filters_columns_systems_and_years(
    tmp_path: Path,
) -> None:
    comparison_path = tmp_path / "comparison.csv"
    pd.DataFrame(
        [
            {
                "comparison_scope": "esto_leap",
                "source_system": "LEAP",
                "economy": "20USA",
                "scenario": "Reference",
                "year": 2030,
                "common_row_id": "row_1",
                "value": 10,
                "unused_large_lineage": "not loaded",
            },
            {
                "comparison_scope": "esto_leap",
                "source_system": "LEAP",
                "economy": "20USA",
                "scenario": "Reference",
                "year": 2040,
                "common_row_id": "row_1",
                "value": 11,
                "unused_large_lineage": "not loaded",
            },
            {
                "comparison_scope": "esto_ninth",
                "source_system": "NINTH",
                "economy": "20USA",
                "scenario": "reference",
                "year": 2030,
                "common_row_id": "row_1",
                "value": 12,
                "unused_large_lineage": "not loaded",
            },
            {
                "comparison_scope": "esto_only",
                "source_system": "ESTO",
                "economy": "20USA",
                "scenario": "historical",
                "year": 2023,
                "common_row_id": "row_1",
                "value": 13,
                "unused_large_lineage": "not loaded",
            },
        ]
    ).to_csv(comparison_path, index=False)

    result = _read_anchor_comparison_slice(
        comparison_data_path=comparison_path,
        years_by_system={
            "LEAP": {2030},
            "NINTH": {2030},
            "ESTO": {2023},
        },
        chunk_size=2,
    )

    assert result.columns.tolist() == ANCHOR_COMPARISON_COLUMNS
    assert result[
        ["source_system", "year", "value"]
    ].to_dict("records") == [
        {"source_system": "LEAP", "year": 2030, "value": "10"},
        {"source_system": "NINTH", "year": 2030, "value": "12"},
        {"source_system": "ESTO", "year": 2023, "value": "13"},
    ]


def test_read_anchor_comparison_slice_returns_typed_empty_contract(
    tmp_path: Path,
) -> None:
    comparison_path = tmp_path / "comparison.csv.gz"
    pd.DataFrame(
        [
            {
                "comparison_scope": "esto_leap",
                "source_system": "LEAP",
                "economy": "20USA",
                "scenario": "Reference",
                "year": 2040,
                "common_row_id": "row_1",
                "value": 11,
            }
        ]
    ).to_csv(comparison_path, index=False)

    result = _read_anchor_comparison_slice(
        comparison_data_path=comparison_path,
        years_by_system={"LEAP": {2030}},
        chunk_size=1,
    )

    assert result.empty
    assert result.columns.tolist() == ANCHOR_COMPARISON_COLUMNS


#%%
