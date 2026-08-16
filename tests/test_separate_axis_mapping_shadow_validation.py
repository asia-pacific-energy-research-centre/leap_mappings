"""Tests for separate-axis shadow source-once and gate evidence."""

import json

import pandas as pd

import codebase.separate_axis_mapping_stage3_shadow_workflow as stage3_shadow
from codebase.mapping_tools import typed_output
from codebase.separate_axis_mapping_shadow_validation_workflow import (
    _build_structural_source_once_diagnostic,
)


def test_protected_parent_detail_split_is_not_unsafe_fanout() -> None:
    relationships = pd.DataFrame(
        [
            {
                "include_in_use_case": True,
                "use_case": "ninth_to_esto_balance_conversion",
                "source_system": "NINTH",
                "source_flow": "16_02_agriculture_and_fishing",
                "source_product": "01_05_lignite",
                "target_flow": target_flow,
                "target_product": "01.05 Lignite",
            }
            for target_flow in [
                "16.03-16.04 Agriculture and fishing",
                "16.03 Agriculture",
            ]
        ]
    )
    common_map = pd.DataFrame(
        [
            {
                "comparison_scope": "esto_leap_ninth",
                "component_esto_flow": target_flow,
                "component_esto_product": "01.05 Lignite",
                "common_row_id": common_row_id,
            }
            for target_flow, common_row_id in [
                (
                    "16.03-16.04 Agriculture and fishing",
                    "subtotal_row",
                ),
                ("16.03 Agriculture", "detail_row"),
            ]
        ]
    )
    expected_splits = pd.DataFrame(
        [
            {
                "comparison_scope": "esto_leap_ninth",
                "source_system": "NINTH",
                "source_flow": "16_02_agriculture_and_fishing",
                "source_product": "01_05_lignite",
            }
        ]
    )

    diagnostic = _build_structural_source_once_diagnostic(
        relationships,
        common_map,
        "generated",
        expected_splits,
    )

    assert diagnostic.iloc[0]["common_row_count"] == 2
    assert diagnostic.iloc[0]["source_once_status"] == (
        "protected_parent_detail_alternative"
    )


def test_unexplained_two_row_delivery_remains_unsafe() -> None:
    relationships = pd.DataFrame(
        [
            {
                "include_in_use_case": True,
                "use_case": "leap_to_esto_balance_conversion",
                "source_system": "LEAP",
                "source_flow": "Industry",
                "source_product": "Electricity",
                "target_flow": target_flow,
                "target_product": "17 Electricity",
            }
            for target_flow in [
                "14 Industry sector",
                "16.01-16.02 Agriculture, forestry and fishing",
            ]
        ]
    )
    common_map = pd.DataFrame(
        [
            {
                "comparison_scope": "esto_leap",
                "component_esto_flow": target_flow,
                "component_esto_product": "17 Electricity",
                "common_row_id": common_row_id,
            }
            for target_flow, common_row_id in [
                ("14 Industry sector", "industry_row"),
                (
                    "16.01-16.02 Agriculture, forestry and fishing",
                    "agriculture_row",
                ),
            ]
        ]
    )

    diagnostic = _build_structural_source_once_diagnostic(
        relationships,
        common_map,
        "generated",
    )

    assert diagnostic.iloc[0]["source_once_status"] == (
        "unsafe_multiple_common_rows"
    )


def test_stage3_shadow_summary_records_pass_and_review_findings(
    tmp_path,
    monkeypatch,
) -> None:
    relationship_dir = tmp_path / "relationships"
    common_dir = tmp_path / "common"
    diagnostics_dir = common_dir / "diagnostics"
    relationship_dir.mkdir()
    diagnostics_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "include_in_use_case": True,
                "use_case": "leap_to_esto_balance_conversion",
                "source_system": "LEAP",
                "source_flow": "Industry",
                "source_product": "Electricity",
                "target_flow": "14 Industry sector",
                "target_product": "17 Electricity",
            }
        ]
    ).to_csv(
        relationship_dir / "energy_balance_relationships.csv",
        index=False,
    )
    pd.DataFrame(
        [
            {
                "comparison_scope": "esto_leap",
                "component_esto_flow": "14 Industry sector",
                "component_esto_product": "17 Electricity",
                "common_row_id": "common_industry_electricity",
            }
        ]
    ).to_csv(
        common_dir / "esto_to_common_esto_map.csv",
        index=False,
    )
    pd.DataFrame(
        columns=[
            "source_system",
            "source_flow",
            "source_product",
            "comparison_scope",
        ]
    ).to_csv(
        common_dir / "qa_common_esto_source_aggregates_split.csv",
        index=False,
    )
    pd.DataFrame(
        [
            {
                "comparison_scope": "esto_leap",
                "source_system": "LEAP",
                "source_total": 1.0,
                "common_total": 1.0,
                "difference": 0.0,
            }
        ]
    ).to_csv(common_dir / "common_esto_total_check.csv", index=False)
    pd.DataFrame(
        [{"record_type": "stage3_output", "status": "passed"}]
    ).to_csv(common_dir / "common_esto_output_status.csv", index=False)
    pd.DataFrame(
        [{"source_system": "ESTO"}]
    ).to_csv(
        common_dir / "common_esto_source_rows_missing_common_map.csv",
        index=False,
    )
    typed_output.write_manifested_parquet(
        pd.DataFrame([{"exact_component_count": 55}]),
        diagnostics_dir / "broad_common_row_summary.parquet",
        artifact_type="broad_common_row_summary",
    )
    for filename in [
        "qa_common_esto_unresolved_partial_coverage.csv",
        "qa_nonzero_unmapped_leap_branches.csv",
        "highly_recommended_mapping_candidates.csv",
    ]:
        pd.DataFrame(columns=["qa_status"]).to_csv(
            common_dir / filename,
            index=False,
        )
    (common_dir / "stage3_run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "test-run",
                "status": "completed_skip_deep_validation",
            }
        ),
        encoding="utf-8",
    )
    (common_dir / "common_esto_output_contract.json").write_text(
        json.dumps(
            {
                "contract_version": "common_esto_output_contract_v1",
                "fact": {"row_count": 1},
                "metadata": {"row_count": 1},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        stage3_shadow,
        "RELATIONSHIP_DIR",
        relationship_dir,
    )
    monkeypatch.setattr(stage3_shadow, "COMMON_ESTO_DIR", common_dir)
    monkeypatch.setattr(
        stage3_shadow,
        "GENERATED_WORKBOOK_PATH",
        tmp_path / "generated.xlsx",
    )
    monkeypatch.setattr(
        stage3_shadow,
        "STAGE_2_COMMON_VARIANT",
        "test_variant",
    )

    summary = stage3_shadow.write_stage3_shadow_gate_summary()

    assert summary["status"] == "passed_with_review_findings"
    assert (
        summary["structural_source_once"][
            "unsafe_multiple_common_rows"
        ]
        == 0
    )
    assert summary["mapped_value_delivery"]["passed"] is True
    assert summary["review_findings"]["broad_common_rows"] == 1
    assert summary["review_findings"][
        "source_rows_without_exact_common_map"
    ] == 1
    persisted = json.loads(
        (
            common_dir / "separate_axis_stage3_shadow_gate.json"
        ).read_text(encoding="utf-8")
    )
    assert persisted["stage3_run_id"] == "test-run"


def test_shadow_stage3_source_paths_use_isolated_pipeline_cache(
    tmp_path,
    monkeypatch,
) -> None:
    expected = {
        "LEAP": tmp_path / "leap.csv",
        "NINTH": tmp_path / "ninth.csv.gz",
        "ESTO": tmp_path / "esto.csv.gz",
        "ESTO_EXTENDED": tmp_path / "esto_extended.csv.gz",
    }
    monkeypatch.setattr(
        stage3_shadow.pipeline,
        "LEAP_ESTO_PATH",
        expected["LEAP"],
    )
    monkeypatch.setattr(
        stage3_shadow.pipeline,
        "NINTH_ESTO_PATH",
        expected["NINTH"],
    )
    monkeypatch.setattr(
        stage3_shadow.pipeline,
        "ESTO_ROWS_PATH",
        expected["ESTO"],
    )
    monkeypatch.setattr(
        stage3_shadow.pipeline,
        "ESTO_EXTENDED_ROWS_PATH",
        expected["ESTO_EXTENDED"],
    )

    assert stage3_shadow.shadow_stage3_source_paths() == expected
