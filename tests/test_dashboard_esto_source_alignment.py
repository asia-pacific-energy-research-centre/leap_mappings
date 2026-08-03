"""Keep the dashboard-producing ESTO source aligned with leap_initialisation."""

from pathlib import Path

import pandas as pd

from codebase import run_mapping_pipeline


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ESTO_SOURCE = "data/00APEC_2024_low_with_subtotals.csv"


def test_pipeline_and_adapter_registry_use_the_2024_esto_base_table() -> None:
    registry = pd.read_csv(
        REPO_ROOT / "config" / "datasets" / "value_adapter_registry.csv",
        dtype=str,
        keep_default_na=False,
    ).set_index("dataset_id")

    assert run_mapping_pipeline.ESTO_CSV_PATH == REPO_ROOT / EXPECTED_ESTO_SOURCE
    assert registry.loc["ESTO", "input_relative_path"] == EXPECTED_ESTO_SOURCE
