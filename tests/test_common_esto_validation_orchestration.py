"""Tests for current-run Common ESTO validation status and provenance."""

from pathlib import Path

import pandas as pd

from codebase.mapping_tools import common_esto_validation_orchestration as validation_module
from codebase.mapping_tools.apply_common_esto_structure import save_outputs


RUN_ID = "common_esto_20260628T120000000000Z"
RUN_TIMESTAMP = "2026-06-28T12:00:00+00:00"


def _tree() -> pd.DataFrame:
    rows = []
    for dataset in ["esto", "common_esto"]:
        rows.extend([
            {
                "dataset": dataset,
                "axis": "product",
                "code": "01 Parent product",
                "parent_code": "",
            },
            {
                "dataset": dataset,
                "axis": "product",
                "code": "01.01 Child A",
                "parent_code": "01 Parent product",
            },
            {
                "dataset": dataset,
                "axis": "product",
                "code": "01.02 Child B",
                "parent_code": "01 Parent product",
            },
        ])
    return pd.DataFrame(rows)


def test_source_frontier_infers_unavailable_ninth_child(tmp_path: Path) -> None:
    """NINTH coverage stops at mapped children while ESTO keeps the tree."""
    workbook_path = tmp_path / "mappings.xlsx"
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        pd.DataFrame([
            {"ninth_sector": "parent", "ninth_fuel": "fuel", "esto_flow": "Parent", "esto_product": "Fuel"},
            {"ninth_sector": "child_a", "ninth_fuel": "fuel", "esto_flow": "Child A", "esto_product": "Fuel"},
        ]).to_excel(writer, sheet_name="ninth_pairs_to_esto_pairs", index=False)
        pd.DataFrame([
            {"leap_sector_name_full_path": "Parent", "raw_leap_fuel_name": "Fuel", "esto_flow": "Parent", "esto_product": "Fuel"},
            {"leap_sector_name_full_path": "Child A", "raw_leap_fuel_name": "Fuel", "esto_flow": "Child A", "esto_product": "Fuel"},
        ]).to_excel(writer, sheet_name="leap_combined_esto", index=False)
        pd.DataFrame(columns=["input_esto_flow", "rolled_esto_flow", "include"]).to_excel(
            writer, sheet_name="esto_rollup_rules", index=False
        )
    tree = pd.DataFrame([
        {"dataset": "common_esto", "axis": "flow", "code": "Parent", "parent_code": ""},
        {"dataset": "common_esto", "axis": "flow", "code": "Child A", "parent_code": "Parent"},
        {"dataset": "common_esto", "axis": "flow", "code": "Child B", "parent_code": "Parent"},
    ])

    frontier = validation_module.build_source_comparison_frontier(tree, workbook_path)

    ninth = frontier[frontier["source_system"].eq("NINTH")].set_index("child_code")
    assert ninth.loc["Child A", "frontier_status"] == "comparable"
    assert ninth.loc["Child B", "frontier_status"] == "source_unavailable"


def _rollup_workbook(path: Path) -> None:
    """Workbook with one NON_EXPANDING ESTO rollup: rollup = base + own use."""
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame([
            {
                "input_esto_flow": "09.07 Oil refineries",
                "rolled_esto_flow": "09.07 Oil refineries (including own use)",
                "ROLLUP_MODE": "NON_EXPANDING",
                "include": True,
            },
            {
                "input_esto_flow": "10.01.11 Oil refineries",
                "rolled_esto_flow": "09.07 Oil refineries (including own use)",
                "ROLLUP_MODE": "NON_EXPANDING",
                "include": True,
            },
        ]).to_excel(writer, sheet_name="esto_rollup_rules", index=False)


def _rollup_tree() -> pd.DataFrame:
    """Register the inclusive rollup as a standalone parent node in both trees."""
    rows = []
    for dataset in ["esto", "common_esto"]:
        rows.extend([
            {"dataset": dataset, "axis": "flow",
             "code": "09.07 Oil refineries (including own use)", "parent_code": ""},
            {"dataset": dataset, "axis": "flow",
             "code": "09.07 Oil refineries",
             "parent_code": "09.07 Oil refineries (including own use)"},
        ])
    return pd.DataFrame(rows)


def test_rollup_label_excluded_from_ordinary_parent_validation() -> None:
    """A NON_EXPANDING rollup label must not be an additive validation parent."""
    from codebase.mapping_tools.build_dataset_tree_structure import (
        _common_esto_validation_children_map,
    )

    tree = _rollup_tree()
    included = _common_esto_validation_children_map(tree, "flow")
    excluded = _common_esto_validation_children_map(
        tree, "flow", {"09.07 Oil refineries (including own use)"}
    )

    assert "09.07 Oil refineries (including own use)" in included
    assert "09.07 Oil refineries (including own use)" not in excluded


def test_validate_non_expanding_rollups_reconciles_contributors(tmp_path: Path) -> None:
    workbook_path = tmp_path / "mappings.xlsx"
    _rollup_workbook(workbook_path)
    comparison_path = tmp_path / "comparison.csv"
    # ESTO reconciles (base 4 + own use 6 == rollup 10); NINTH does not (12 != 10).
    pd.DataFrame([
        _row("ESTO", "09.07 Oil refineries (including own use)", 10.0),
        _row("ESTO", "09.07 Oil refineries", 4.0),
        _row("ESTO", "10.01.11 Oil refineries", 6.0),
        _row("NINTH", "09.07 Oil refineries (including own use)", 12.0),
        _row("NINTH", "09.07 Oil refineries", 4.0),
        _row("NINTH", "10.01.11 Oil refineries", 6.0),
    ]).to_csv(comparison_path, index=False)

    detail, summary = validation_module.validate_non_expanding_rollups(
        comparison_data_path=comparison_path,
        workbook_path=workbook_path,
        run_id=RUN_ID,
    )
    by_source = detail.set_index("source_system")
    assert by_source.loc["ESTO", "status"] == "passed"
    assert by_source.loc["NINTH", "status"] == "failed"
    assert not summary.empty


def test_validate_non_expanding_rollups_reports_source_availability(tmp_path: Path) -> None:
    workbook_path = tmp_path / "mappings.xlsx"
    _rollup_workbook(workbook_path)
    comparison_path = tmp_path / "comparison.csv"
    # LEAP emits only the rollup (no contributors) -> nothing to reconcile.
    # AUS-scoped NINTH emits the rollup plus one of two contributors -> incomplete.
    pd.DataFrame([
        _row("LEAP", "09.07 Oil refineries (including own use)", 10.0),
        _row("NINTH", "09.07 Oil refineries (including own use)", 10.0),
        _row("NINTH", "09.07 Oil refineries", 4.0),
    ]).to_csv(comparison_path, index=False)

    detail, _ = validation_module.validate_non_expanding_rollups(
        comparison_data_path=comparison_path,
        workbook_path=workbook_path,
        run_id=RUN_ID,
    )
    by_source = detail.set_index("source_system")
    assert by_source.loc["LEAP", "status"] == "no_contributors_available"
    assert by_source.loc["NINTH", "status"] == "incomplete_contributors"


def test_diagnose_child_present_is_not_flagged_as_replaced() -> None:
    """A rollup-input child that is present in the output is present, not replaced."""
    rollup_inputs = {
        "09.07 Oil refineries": [{
            "rollup_mode": validation_module.NON_EXPANDING_MODE,
            "replacement_label": "09.07 Oil refineries (including own use)",
            "rollup_id": "nonexp_09_07_oil_refineries_including_own_use",
        }],
    }
    present = validation_module._diagnose_child_status(
        "09.07 Oil refineries", "09 Total transformation sector",
        direct_value=5.0, descendant_value=0.0, raw_value=5.0,
        rollup_inputs=rollup_inputs, rollup_modes={},
    )
    absent = validation_module._diagnose_child_status(
        "09.07 Oil refineries", "09 Total transformation sector",
        direct_value=0.0, descendant_value=0.0, raw_value=5.0,
        rollup_inputs=rollup_inputs, rollup_modes={},
    )
    assert present[3] == "present_in_final_output"
    assert absent[3] == "replaced_by_non_expanding_rollup"


def _row(source_system: str, flow_label: str, value: float, year: int = 2023) -> dict:
    return {
        "comparison_scope": "all_sources",
        "source_system": source_system,
        "economy": "20_USA",
        "scenario": "historical",
        "year": year,
        "common_flow_label": flow_label,
        "common_product_label": "08.01 Natural gas",
        "value": value,
    }


def _write_comparison(
    path: Path,
    parent_value: float,
    include_children: bool = True,
    year: int = 2023,
) -> None:
    products = [("01 Parent product", parent_value)]
    if include_children:
        products.extend([("01.01 Child A", 4.0), ("01.02 Child B", 6.0)])
    pd.DataFrame([
        {
            "comparison_scope": "all_sources",
            "source_system": "ESTO",
            "economy": "20_USA",
            "scenario": "historical",
            "year": year,
            "common_flow_label": "14 Industry",
            "common_product_label": product,
            "value": value,
        }
        for product, value in products
    ]).to_csv(path, index=False)


def _run(tmp_path: Path, comparison_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    expected_mtime_ns = comparison_path.stat().st_mtime_ns if comparison_path.exists() else None
    return validation_module.run_common_esto_validation_workflow(
        tree_df=_tree(),
        comparison_data_path=comparison_path,
        output_dir=tmp_path,
        run_id=RUN_ID,
        run_timestamp_utc=RUN_TIMESTAMP,
        expected_input_mtime_ns=expected_mtime_ns,
    )


def test_eligible_checks_with_zero_mismatches_pass(tmp_path: Path) -> None:
    comparison_path = tmp_path / "comparison.csv"
    _write_comparison(comparison_path, parent_value=10.0)

    detail, summary = _run(tmp_path, comparison_path)
    product = summary[summary["validation_axis"] == "product"].iloc[0]

    assert detail["status"].tolist() == ["passed"]
    assert product["status"] == "passed"
    assert product["checks_performed"] == 1
    assert product["eligible_parent_count"] == 1
    assert product["mismatch_count"] == 0


def test_eligible_checks_with_mismatches_fail(tmp_path: Path) -> None:
    comparison_path = tmp_path / "comparison.csv"
    _write_comparison(comparison_path, parent_value=11.0)

    detail, summary = _run(tmp_path, comparison_path)
    product = summary[summary["validation_axis"] == "product"].iloc[0]

    assert len(detail) == 1
    assert product["status"] == "failed"
    assert product["mismatch_count"] == 1


def test_no_eligible_checks_are_skipped(tmp_path: Path) -> None:
    comparison_path = tmp_path / "comparison.csv"
    _write_comparison(comparison_path, parent_value=10.0, include_children=False)

    detail, summary = _run(tmp_path, comparison_path)

    assert detail.empty
    assert set(summary["status"]) == {"skipped"}
    assert set(summary["eligible_parent_count"]) == {0}


def test_base_year_checks_are_excluded(tmp_path: Path) -> None:
    comparison_path = tmp_path / "comparison.csv"
    _write_comparison(comparison_path, parent_value=11.0, year=2022)

    detail, summary = _run(tmp_path, comparison_path)

    assert detail.empty
    assert set(summary["status"]) == {"skipped"}
    assert set(summary["checks_performed"]) == {0}


def test_missing_input_is_skipped_and_replaces_old_detail(tmp_path: Path) -> None:
    detail_path = tmp_path / "common_esto_validation.csv"
    pd.DataFrame([{"stale": True}]).to_csv(detail_path, index=False)

    detail, summary = _run(tmp_path, tmp_path / "missing.csv")

    assert detail.empty
    assert set(summary["status"]) == {"skipped"}
    current_detail = pd.read_csv(detail_path)
    assert "stale" not in current_detail.columns
    assert current_detail["run_id"].empty


def test_validation_exception_is_recorded_as_error(tmp_path: Path, monkeypatch) -> None:
    comparison_path = tmp_path / "comparison.csv"
    _write_comparison(comparison_path, parent_value=10.0)

    def _raise(*args, **kwargs):
        raise RuntimeError("test validation failure")

    monkeypatch.setattr(validation_module, "_validate_common_esto_axis_recursive_sums", _raise)
    detail, summary = _run(tmp_path, comparison_path)

    assert detail.empty
    assert set(summary["status"]) == {"error"}
    assert summary["reason"].str.contains("test validation failure").all()


def test_stale_input_mtime_cannot_be_reported_as_current(tmp_path: Path) -> None:
    comparison_path = tmp_path / "comparison.csv"
    _write_comparison(comparison_path, parent_value=10.0)

    _, summary = validation_module.run_common_esto_validation_workflow(
        tree_df=_tree(),
        comparison_data_path=comparison_path,
        output_dir=tmp_path,
        run_id=RUN_ID,
        run_timestamp_utc=RUN_TIMESTAMP,
        expected_input_mtime_ns=comparison_path.stat().st_mtime_ns - 1,
    )

    assert set(summary["status"]) == {"skipped"}
    assert summary["reason"].str.contains("does not match the current run").all()


def test_stage3_and_validation_records_share_run_identifier(tmp_path: Path) -> None:
    comparison_path = tmp_path / "comparison.csv"
    _write_comparison(comparison_path, parent_value=10.0)
    empty = pd.DataFrame()
    stage3_status = save_outputs(
        comparison_df=pd.read_csv(comparison_path),
        wide_year_df=empty,
        total_check_df=empty,
        source_coverage_check_df=empty,
        missing_map_df=empty,
        output_dir=tmp_path / "stage3",
        error_occurred=False,
        run_id=RUN_ID,
        run_timestamp_utc=RUN_TIMESTAMP,
    )
    _, validation_status = _run(tmp_path, comparison_path)

    assert set(stage3_status["run_id"]) == {RUN_ID}
    assert set(validation_status["run_id"]) == {RUN_ID}
