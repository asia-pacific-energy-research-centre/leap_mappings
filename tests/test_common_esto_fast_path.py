from pathlib import Path

import pandas as pd

from codebase.mapping_tools.apply_common_esto_structure import (
    run_common_esto_comparison_fast_path,
)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_fast_path_writes_final_outputs_without_qa_artifacts(tmp_path: Path) -> None:
    relationship_dir = tmp_path / "results" / "mapping_relationships"
    common_dir = tmp_path / "results" / "common_esto"
    source_paths = {
        "LEAP": relationship_dir / "leap_results_converted_to_esto.csv",
        "NINTH": relationship_dir / "ninth_results_converted_to_esto.csv",
        "ESTO": relationship_dir / "esto_results_exact_rows.csv",
    }
    common_rows_path = common_dir / "common_esto_rows.csv"

    source_rows = {
        "LEAP": [
            {
                "source_system": "LEAP",
                "economy": "20_USA",
                "scenario": "Reference",
                "year": 2060,
                "esto_flow": "F1",
                "esto_product": "P1",
                "value": 10,
            }
        ],
        "NINTH": [
            {
                "source_system": "NINTH",
                "economy": "20_USA",
                "scenario": "reference",
                "year": 2024,
                "esto_flow": "F1",
                "esto_product": "P1",
                "value": 2,
            }
        ],
        "ESTO": [
            {
                "source_system": "ESTO",
                "economy": "20_USA",
                "scenario": "historical",
                "year": 2022,
                "esto_flow": "F1",
                "esto_product": "P1",
                "value": 1,
            }
        ],
    }
    for source_system, rows in source_rows.items():
        _write_csv(source_paths[source_system], rows)

    _write_csv(
        common_rows_path,
        [
            {
                "comparison_scope": "leap_vs_esto_vs_ninth",
                "component_esto_flow": "F1",
                "component_esto_product": "P1",
                "common_row_id": "common_f1_p1",
                "common_flow_code": "F1",
                "common_flow_name": "Flow 1",
                "common_flow_label": "F1 Flow 1",
                "common_product_code": "P1",
                "common_product_name": "Product 1",
                "common_product_label": "P1 Product 1",
                "component_sign": 1,
            },
            {
                "comparison_scope": "leap_vs_esto_vs_ninth",
                "component_esto_flow": "F2",
                "component_esto_product": "P2",
                "common_row_id": "common_f2_p2",
                "common_flow_code": "F2",
                "common_flow_name": "Flow 2",
                "common_flow_label": "F2 Flow 2",
                "common_product_code": "P2",
                "common_product_name": "Product 2",
                "common_product_label": "P2 Product 2",
                "component_sign": 1,
            },
        ],
    )

    comparison_df, wide_df, missing_map_df = run_common_esto_comparison_fast_path(
        source_paths=source_paths,
        common_rows_path=common_rows_path,
        output_dir=common_dir,
        default_economy="20_USA",
        active_component_abs_tolerance=0.0,
        ninth_projection_start_year=2023,
        run_id="test_fast_path",
        run_timestamp_utc="2026-07-09T00:00:00+00:00",
    )

    assert len(comparison_df) == 3
    assert not wide_df.empty
    assert missing_map_df.empty
    assert (common_dir / "common_esto_comparison_data.csv").exists()
    assert (common_dir / "common_esto_comparison_wide.csv").exists()
    assert (common_dir / "common_esto_output_status.csv").exists()
    assert not (common_dir / "diagnostics").exists()
    assert not (common_dir / "qa_common_esto_total_check.csv").exists()

    status_df = pd.read_csv(common_dir / "common_esto_output_status.csv")
    assert status_df["record_type"].tolist() == ["fast_path_output", "fast_path_output"]
    assert set(status_df["artifact_name"]) == {
        "common_esto_comparison_data",
        "common_esto_comparison_wide",
    }
