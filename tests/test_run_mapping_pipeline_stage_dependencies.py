import hashlib
import json

import pandas as pd
import pytest

import codebase.run_mapping_pipeline as pipeline
from codebase.run_mapping_pipeline import (
    _ALL_STAGES,
    _DEFAULT_STAGES,
    _stage3_completion_status,
    build_registry_provenance,
    expand_requested_stages,
    load_active_mapping_generation_manifest,
)


def test_default_pipeline_excludes_retired_stage_zero() -> None:
    assert _ALL_STAGES == [
        "generate",
        "1",
        "2",
        "leap_parse",
        "data_convert",
        "3",
    ]


def test_colleague_default_uses_committed_mapping_configuration() -> None:
    assert _DEFAULT_STAGES == ["1", "2", "leap_parse", "data_convert", "3"]
    assert "generate" not in _DEFAULT_STAGES


def test_abbreviated_full_run_includes_conversion_dependencies() -> None:
    assert expand_requested_stages(["1", "2", "3"], set()) == [
        "1", "2", "leap_parse", "data_convert", "3"
    ]


def test_explicit_conversion_stage_is_not_duplicated() -> None:
    requested = ["1", "2", "leap_parse", "data_convert", "3"]
    assert expand_requested_stages(requested, set()) == requested


def test_explicit_skip_is_honoured() -> None:
    assert expand_requested_stages(["1", "2", "3"], {"data_convert"}) == [
        "1", "2", "leap_parse", "3"
    ]


def test_stage3_manifest_reports_validation_errors() -> None:
    summary = pd.DataFrame([
        {"validation_axis": "product", "status": "passed"},
        {"validation_axis": "flow", "status": "error"},
    ])

    assert _stage3_completion_status(summary) == "completed_with_validation_errors"


def test_stage3_manifest_keeps_completed_for_non_error_validation_results() -> None:
    summary = pd.DataFrame([
        {"validation_axis": "product", "status": "passed"},
        {"validation_axis": "flow", "status": "failed"},
    ])

    assert _stage3_completion_status(summary) == "completed"


def test_mapping_generation_manifest_must_match_active_workbook(
    tmp_path,
    monkeypatch,
) -> None:
    workbook_path = tmp_path / "outlook_mappings_master.xlsx"
    workbook_path.write_bytes(b"generated workbook")
    manifest_path = tmp_path / "outlook_mappings_generation_manifest.json"
    workbook_hash = hashlib.sha256(workbook_path.read_bytes()).hexdigest()
    manifest_path.write_text(
        json.dumps(
            {
                "status": "promoted_and_reopened",
                "hashes": {
                    "promoted_master_sha256": workbook_hash,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pipeline, "WORKBOOK_PATH", workbook_path)
    monkeypatch.setattr(
        pipeline,
        "MAPPING_GENERATION_MANIFEST_PATH",
        manifest_path,
    )

    manifest = load_active_mapping_generation_manifest()

    assert manifest is not None
    assert manifest["status"] == "promoted_and_reopened"


def test_stale_mapping_generation_manifest_fails_closed(
    tmp_path,
    monkeypatch,
) -> None:
    workbook_path = tmp_path / "outlook_mappings_master.xlsx"
    workbook_path.write_bytes(b"changed workbook")
    manifest_path = tmp_path / "outlook_mappings_generation_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "hashes": {
                    "promoted_master_sha256": "stale",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pipeline, "WORKBOOK_PATH", workbook_path)
    monkeypatch.setattr(
        pipeline,
        "MAPPING_GENERATION_MANIFEST_PATH",
        manifest_path,
    )

    with pytest.raises(ValueError, match="does not match"):
        load_active_mapping_generation_manifest()


def test_registry_provenance_records_all_contract_files_and_policies() -> None:
    provenance = build_registry_provenance()

    assert set(provenance["files"]) == {
        "dataset_registry",
        "value_adapter_registry",
        "mapping_sheet_registry",
        "rollup_sheet_registry",
        "diagnostic_adapter_registry",
        "comparison_scope_registry",
    }
    assert set(provenance["enabled_dataset_policies"]) == {
        "ESTO",
        "ESTO_EXTENDED",
        "NINTH",
        "LEAP",
        "COMMON_ESTO",
    }
    assert "SYNTH_BALANCE" not in provenance["enabled_dataset_policies"]
    assert set(provenance["default_scope_policies"]) == {
        "esto_leap",
        "esto_extended_leap",
        "esto_leap_ninth",
        "esto_extended_leap_ninth",
    }
