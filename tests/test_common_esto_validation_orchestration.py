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


def _write_comparison(path: Path, parent_value: float, include_children: bool = True) -> None:
    products = [("01 Parent product", parent_value)]
    if include_children:
        products.extend([("01.01 Child A", 4.0), ("01.02 Child B", 6.0)])
    pd.DataFrame([
        {
            "comparison_scope": "all_sources",
            "source_system": "ESTO",
            "economy": "20_USA",
            "scenario": "historical",
            "year": 2022,
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

    assert detail.empty
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
        missing_map_df=empty,
        output_dir=tmp_path / "stage3",
        error_occurred=False,
        run_id=RUN_ID,
        run_timestamp_utc=RUN_TIMESTAMP,
    )
    _, validation_status = _run(tmp_path, comparison_path)

    assert set(stage3_status["run_id"]) == {RUN_ID}
    assert set(validation_status["run_id"]) == {RUN_ID}
