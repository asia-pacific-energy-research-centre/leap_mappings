"""Opt-in real-data smoke test for the mapping pipeline.

This test exercises the notebook-style stage sequence against the checked-in
inputs and writes the standard outputs under ``results/``. It is skipped by
default; run it explicitly with ``RUN_MAPPING_PIPELINE_SMOKE=1``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest


if os.environ.get("RUN_MAPPING_PIPELINE_SMOKE") != "1":
    pytest.skip(
        "Set RUN_MAPPING_PIPELINE_SMOKE=1 to run the real-data mapping pipeline smoke test.",
        allow_module_level=True,
    )


from codebase.run_mapping_pipeline import (  # noqa: E402
    COMMON_ESTO_DIR,
    COMMON_ROWS_PATH,
    ESTO_ROWS_PATH,
    LEAP_ESTO_PATH,
    NINTH_ESTO_PATH,
    RAW_LEAP_PATH,
    RELATIONSHIPS_PATH,
    run_data_convert,
    run_leap_parse,
    run_stage_0,
    run_stage_1,
    run_stage_2,
    run_stage_3,
)
import codebase.outlook_mapping_maintenance_workflow as maintenance_workflow  # noqa: E402


TREE_DIR = Path(r"C:\Users\Work\github\leap_mappings\results\tree_structure")


def _assert_csv_has_rows(path: Path) -> pd.DataFrame:
    assert path.exists(), f"Missing expected CSV: {path}"
    df = pd.read_csv(path, low_memory=False)
    assert not df.empty, f"Expected non-empty CSV: {path}"
    return df


def _assert_exists(path: Path) -> None:
    assert path.exists(), f"Missing expected output: {path}"


def test_real_pipeline_smoke_run() -> None:
    original_generate_missing_rows = maintenance_workflow.GENERATE_MISSING_MAPPED_ESTO_ROWS
    maintenance_workflow.GENERATE_MISSING_MAPPED_ESTO_ROWS = False
    try:
        run_stage_0()
    finally:
        maintenance_workflow.GENERATE_MISSING_MAPPED_ESTO_ROWS = original_generate_missing_rows

    stage0_outputs = [
        Path(r"C:\Users\Work\github\leap_mappings\results\maintenance\maintenance_summary.csv"),
        Path(r"C:\Users\Work\github\leap_mappings\results\maintenance\cardinality_leap_esto.csv"),
        Path(r"C:\Users\Work\github\leap_mappings\results\maintenance\cardinality_leap_ninth.csv"),
        Path(r"C:\Users\Work\github\leap_mappings\results\maintenance\cardinality_ninth_esto.csv"),
        Path(r"C:\Users\Work\github\leap_mappings\results\maintenance\subtotal_mismatches.csv"),
        Path(r"C:\Users\Work\github\leap_mappings\results\maintenance\unmapped_esto_pairs.csv"),
        Path(r"C:\Users\Work\github\leap_mappings\results\maintenance\unmapped_ninth_pairs.csv"),
    ]
    for path in stage0_outputs:
        _assert_exists(path)
    _assert_csv_has_rows(stage0_outputs[0])

    run_stage_1()
    relationships_df = _assert_csv_has_rows(RELATIONSHIPS_PATH)
    _assert_exists(RELATIONSHIPS_PATH.with_suffix(".xlsx"))
    assert {"relationship_id", "source_system", "target_system"}.issubset(relationships_df.columns)

    run_stage_2()
    common_rows_df = _assert_csv_has_rows(COMMON_ROWS_PATH)
    _assert_exists(COMMON_ESTO_DIR / "esto_to_common_esto_map.csv")
    assert {"common_row_id", "common_flow_label", "common_product_label"}.issubset(common_rows_df.columns)

    run_leap_parse()
    _assert_exists(RAW_LEAP_PATH)

    run_data_convert()
    for path in [LEAP_ESTO_PATH, NINTH_ESTO_PATH, ESTO_ROWS_PATH]:
        _assert_csv_has_rows(path)

    run_stage_3()
    comparison_df = _assert_csv_has_rows(COMMON_ESTO_DIR / "common_esto_comparison_data.csv")
    _assert_exists(TREE_DIR / "common_esto_validation.csv")
    validation_summary_df = _assert_csv_has_rows(TREE_DIR / "common_esto_validation_summary.csv")
    status_df = _assert_csv_has_rows(COMMON_ESTO_DIR / "common_esto_output_status.csv")

    assert "common_row_id" in comparison_df.columns
    assert "status" in validation_summary_df.columns
    assert "artifact_name" in status_df.columns
    assert "common_esto_comparison_data" in set(status_df["artifact_name"].astype(str))
