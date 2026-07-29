#%%
"""Tests for reusable mapping subtotal verification and workbook annotation."""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pandas as pd

from codebase.subtotal_mapping_master_review_workflow import (
    classify_suggestion_actions,
    load_mapping_sheets_as_dataframes,
    verify_exported_workbook,
    write_review_workbook,
)


def _affected_cell(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "mapping_sheet": "leap_combined_ninth",
        "excel_row": 2,
        "flag_column": "ninth_pair_is_subtotal",
        "dataset_id": "ninth",
        "axis_1_hierarchy_status": "complete_declared_schema",
        "axis_2_hierarchy_status": "complete_declared_schema",
        "every_node_resolved": True,
        "current_value": False,
        "proposed_value": True,
        "subtotal_label_override": False,
        "subtotal_label_exception": False,
        "subtotal_mismatch_exception": False,
    }
    row.update(overrides)
    return row


def _write_mapping_fixture(path: Path) -> None:
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    sheets = {
        "leap_combined_esto": [
            "leap_sector_name_full_path",
            "raw_leap_fuel_name",
            "esto_flow",
            "esto_product",
            "leap_is_subtotal",
            "esto_pair_is_subtotal",
            "duplicate_to_remove",
            "esto_dataset_scope",
        ],
        "leap_combined_ninth": [
            "leap_sector_name_full_path",
            "raw_leap_fuel_name",
            "ninth_sector",
            "ninth_fuel",
            "leap_is_subtotal",
            "ninth_pair_is_subtotal",
            "duplicate_to_remove",
        ],
        "ninth_pairs_to_esto_pairs": [
            "ninth_sector",
            "ninth_fuel",
            "esto_flow",
            "esto_product",
            "ninth_pair_is_subtotal",
            "esto_pair_is_subtotal",
            "duplicate_to_remove",
            "esto_dataset_scope",
        ],
    }
    for sheet_name, headers in sheets.items():
        sheet = workbook.create_sheet(sheet_name)
        sheet.append(headers)
        if sheet_name == "leap_combined_esto":
            sheet.append(["Branch", "Fuel", "01 Production", "01 Coal", False, False, False, "BOTH"])
        elif sheet_name == "leap_combined_ninth":
            sheet.append(["Branch", "Fuel", "16_other", "01_coal", False, False, False])
        else:
            sheet.append(["16_other", "01_coal", "01 Production", "01 Coal", False, False, False, "BOTH"])
    workbook.save(path)


def test_action_requires_complete_evidence_and_no_prior_label_decision() -> None:
    affected = pd.DataFrame(
        [
            _affected_cell(),
            _affected_cell(
                excel_row=3,
                axis_1_hierarchy_status="partial_inventory",
            ),
            _affected_cell(
                excel_row=4,
                subtotal_label_override=True,
            ),
        ]
    )

    result = classify_suggestion_actions(affected)

    assert result["suggestion_action"].tolist() == [
        "apply_complete_source_evidence",
        "review_partial_or_unresolved_source",
        "review_conflicts_with_prior_label_exception",
    ]


def test_review_workbook_is_dataframe_readable_and_preserves_review_only_value(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.xlsx"
    output = tmp_path / "review.xlsx"
    _write_mapping_fixture(source)
    affected = classify_suggestion_actions(
        pd.DataFrame(
            [
                _affected_cell(),
                _affected_cell(
                    flag_column="leap_is_subtotal",
                    dataset_id="leap",
                    current_value=False,
                    proposed_value=True,
                    axis_1_hierarchy_status="partial_inventory",
                    axis_2_hierarchy_status="unresolved_fuel_taxonomy",
                ),
            ]
        )
    )

    result = write_review_workbook(
        source_workbook_path=source,
        output_workbook_path=output,
        affected_cells=affected,
    )
    verify_exported_workbook(
        output_workbook_path=output,
        affected_cells=affected,
    )
    frames = load_mapping_sheets_as_dataframes(output)

    assert result == {"updated_cells": 1, "annotated_rows": 1}
    row = frames["leap_combined_ninth"].iloc[0]
    assert bool(row["ninth_pair_is_subtotal"])
    assert not bool(row["leap_is_subtotal"])
    assert "UPDATED" in row["CHANGED"]
    assert "REVIEW REQUIRED" in row["CHANGED"]


#%%
