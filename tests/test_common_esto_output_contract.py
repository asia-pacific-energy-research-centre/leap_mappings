"""Focused tests for the additive Common ESTO fact/metadata contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from codebase.mapping_tools import common_esto_output_contract as contract_module
from codebase.mapping_tools.apply_common_esto_structure import save_outputs
from codebase.mapping_tools.common_esto_output_contract import (
    FACT_COLUMNS,
    FACT_FILENAME,
    FACT_KEY_COLUMNS,
    LEGACY_COMPARISON_COLUMNS,
    MANIFEST_FILENAME,
    METADATA_COLUMNS,
    METADATA_FILENAME,
    build_common_esto_output_tables,
    reconstruct_common_esto_comparison,
    write_common_esto_output_contract,
)


def _legacy_comparison(value: float = 10.0) -> pd.DataFrame:
    rows = [
        {
            "comparison_scope": "esto_leap",
            "source_system": source_system,
            "economy": "20_USA",
            "scenario": scenario,
            "year": year,
            "common_flow_code": "09.01",
            "common_flow_name": "Electricity plants",
            "common_flow_label": "09.01 Electricity plants",
            "common_product_code": "17",
            "common_product_name": "Electricity",
            "common_product_label": "17 Electricity",
            "common_row_id": "common_row_1",
            "common_row_basis": "exact_esto_row",
            "is_exact_row": True,
            "requires_rollup": False,
            "is_non_expanding_rollup": False,
            "non_expanding_rollup_id": "",
            "rollup_mode": "",
            "source_aggregate_labels": "",
            "source_aggregate_group_ids": "",
            "value": row_value,
        }
        for source_system, scenario, year, row_value in [
            ("ESTO", "historical", 2022, value),
            ("LEAP", "Reference", 2060, value + 1),
        ]
    ]
    return pd.DataFrame(rows, columns=LEGACY_COMPARISON_COLUMNS)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def test_split_and_reconstruct_preserve_exact_legacy_order_and_values() -> None:
    legacy = _legacy_comparison()

    fact, metadata = build_common_esto_output_tables(legacy)
    reconstructed = reconstruct_common_esto_comparison(fact, metadata)

    assert fact.columns.tolist() == FACT_COLUMNS
    assert metadata.columns.tolist() == METADATA_COLUMNS
    assert len(metadata) == 1
    pd.testing.assert_frame_equal(reconstructed, legacy)


def test_metadata_uses_compound_key_and_rejects_conflicts() -> None:
    legacy = _legacy_comparison()
    second_scope = legacy.iloc[[0]].copy()
    second_scope["comparison_scope"] = "esto_leap_ninth"
    combined = pd.concat([legacy, second_scope], ignore_index=True)

    _, metadata = build_common_esto_output_tables(combined)

    assert len(metadata) == 2
    conflict = legacy.iloc[[0]].copy()
    conflict["common_flow_label"] = "conflicting label"
    with pytest.raises(ValueError, match="metadata conflicts"):
        build_common_esto_output_tables(pd.concat([legacy, conflict], ignore_index=True))


def test_duplicate_fact_key_is_rejected() -> None:
    legacy = _legacy_comparison()

    with pytest.raises(ValueError, match="six-column fact key"):
        build_common_esto_output_tables(pd.concat([legacy, legacy.iloc[[0]]], ignore_index=True))


@pytest.mark.parametrize(
    ("column", "invalid_value", "error_text"),
    [
        ("comparison_scope", " ", "contains empty values"),
        ("source_system", "", "contains empty values"),
        ("economy", None, "contains empty values"),
        ("scenario", "", "contains empty values"),
        ("common_row_id", "", "contains empty values"),
        ("year", 23, "integer four-digit years"),
        ("year", 2023.5, "integer four-digit years"),
        ("value", float("nan"), "finite numeric values"),
        ("value", float("inf"), "finite numeric values"),
        ("value", True, "not booleans"),
        ("is_exact_row", 1, "strict boolean values"),
        ("requires_rollup", "yes", "strict boolean values"),
        ("is_non_expanding_rollup", "", "strict boolean values"),
    ],
)
def test_contract_certification_rejects_invalid_public_values(
    column: str,
    invalid_value: object,
    error_text: str,
) -> None:
    legacy = _legacy_comparison()
    legacy[column] = legacy[column].astype(object)
    legacy.loc[0, column] = invalid_value

    with pytest.raises(ValueError, match=error_text):
        build_common_esto_output_tables(legacy)


def test_contract_certification_normalizes_year_values_and_csv_boolean_strings() -> None:
    legacy = _legacy_comparison()
    legacy["year"] = legacy["year"].astype(str)
    legacy["value"] = legacy["value"].astype(str)
    legacy["is_exact_row"] = "true"
    legacy["requires_rollup"] = "FALSE"
    legacy["is_non_expanding_rollup"] = "false"

    fact, metadata = build_common_esto_output_tables(legacy)

    assert fact["year"].tolist() == [2022, 2060]
    assert fact["value"].tolist() == [10.0, 11.0]
    assert bool(metadata.loc[0, "is_exact_row"]) is True
    assert bool(metadata.loc[0, "requires_rollup"]) is False
    assert bool(metadata.loc[0, "is_non_expanding_rollup"]) is False


@pytest.mark.parametrize(
    ("run_id", "timestamp", "error_text"),
    [
        ("", "2026-07-28T00:00:00+00:00", "run_id must be nonempty"),
        ("run_1", "2026-07-28T00:00:00", "must be timezone-aware"),
        ("run_1", "not-a-timestamp", "must be a valid ISO timestamp"),
    ],
)
def test_manifest_identity_requires_run_id_and_timezone_aware_timestamp(
    tmp_path: Path,
    run_id: str,
    timestamp: str,
    error_text: str,
) -> None:
    with pytest.raises(ValueError, match=error_text):
        write_common_esto_output_contract(
            _legacy_comparison(),
            tmp_path,
            run_id=run_id,
            run_timestamp_utc=timestamp,
        )
    assert list(tmp_path.iterdir()) == []


def test_manifest_matches_published_artifacts(tmp_path: Path) -> None:
    manifest, paths = write_common_esto_output_contract(
        legacy_comparison_df=_legacy_comparison(),
        output_dir=tmp_path,
        run_id="run_1",
        run_timestamp_utc="2026-07-28T00:00:00+00:00",
    )

    assert {path.name for path in paths} == {
        FACT_FILENAME,
        METADATA_FILENAME,
        MANIFEST_FILENAME,
    }
    on_disk = json.loads((tmp_path / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert on_disk == manifest
    assert manifest["contract_version"] == "common_esto_output_contract_v1"
    assert manifest["observed_rows_only"] is True
    assert manifest["fact"]["columns"] == FACT_COLUMNS
    assert manifest["fact"]["key_columns"] == FACT_KEY_COLUMNS
    assert manifest["metadata"]["columns"] == METADATA_COLUMNS
    for artifact_name in ["fact", "metadata"]:
        record = manifest[artifact_name]
        artifact_path = tmp_path / record["path"]
        assert artifact_path.parent == tmp_path
        assert record["row_count"] == len(pd.read_csv(artifact_path))
        assert record["size_bytes"] == artifact_path.stat().st_size
        assert record["sha256"] == _sha256(artifact_path)


def test_failed_atomic_promotion_restores_previous_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_common_esto_output_contract(
        _legacy_comparison(value=10),
        tmp_path,
        run_id="old",
        run_timestamp_utc="2026-07-28T00:00:00+00:00",
    )
    previous = {
        name: (tmp_path / name).read_bytes()
        for name in [FACT_FILENAME, METADATA_FILENAME, MANIFEST_FILENAME]
    }
    real_replace = contract_module._atomic_replace
    failed_once = False

    def _fail_metadata_once(source: Path, destination: Path) -> None:
        nonlocal failed_once
        if destination.name == METADATA_FILENAME and not failed_once:
            failed_once = True
            raise OSError("simulated promotion failure")
        real_replace(source, destination)

    monkeypatch.setattr(contract_module, "_atomic_replace", _fail_metadata_once)
    with pytest.raises(OSError, match="simulated promotion failure"):
        write_common_esto_output_contract(
            _legacy_comparison(value=99),
            tmp_path,
            run_id="new",
            run_timestamp_utc="2026-07-28T01:00:00+00:00",
        )

    assert {
        name: (tmp_path / name).read_bytes()
        for name in [FACT_FILENAME, METADATA_FILENAME, MANIFEST_FILENAME]
    } == previous


def test_normal_save_flow_emits_and_registers_additive_contract(tmp_path: Path) -> None:
    empty = pd.DataFrame()
    status = save_outputs(
        comparison_df=_legacy_comparison(),
        wide_year_df=empty,
        total_check_df=empty,
        source_coverage_check_df=empty,
        missing_map_df=empty,
        output_dir=tmp_path,
        error_occurred=False,
        run_id="normal_run",
        run_timestamp_utc="2026-07-28T00:00:00+00:00",
    )

    assert {FACT_FILENAME, METADATA_FILENAME, MANIFEST_FILENAME}.issubset(
        {path.name for path in tmp_path.iterdir()}
    )
    assert {
        "common_esto_comparison_fact",
        "common_esto_row_metadata",
        "common_esto_output_contract",
    }.issubset(set(status["artifact_name"]))


def test_qa_failed_save_preserves_prior_contract_and_canonical_legacy(tmp_path: Path) -> None:
    empty = pd.DataFrame()
    save_outputs(
        comparison_df=_legacy_comparison(value=10),
        wide_year_df=empty,
        total_check_df=empty,
        source_coverage_check_df=empty,
        missing_map_df=empty,
        output_dir=tmp_path,
        error_occurred=False,
        run_id="successful_run",
        run_timestamp_utc="2026-07-28T00:00:00+00:00",
    )
    preserved_names = [
        FACT_FILENAME,
        METADATA_FILENAME,
        MANIFEST_FILENAME,
        "common_esto_comparison_data.csv",
    ]
    previous = {name: (tmp_path / name).read_bytes() for name in preserved_names}

    status = save_outputs(
        comparison_df=_legacy_comparison(value=99),
        wide_year_df=empty,
        total_check_df=empty,
        source_coverage_check_df=empty,
        missing_map_df=empty,
        output_dir=tmp_path,
        error_occurred=True,
        run_id="failed_run",
        run_timestamp_utc="2026-07-28T01:00:00+00:00",
    )

    assert {name: (tmp_path / name).read_bytes() for name in preserved_names} == previous
    assert (tmp_path / "common_esto_comparison_data_needs_mapping_review.csv").exists()
    contract_status = status[status["record_type"].eq("output_contract_publication")].iloc[0]
    assert contract_status["status"] == "preserved_previous_contract"
    assert contract_status["current_output_file"] == MANIFEST_FILENAME


def test_qa_failed_save_without_prior_contract_does_not_publish_one(tmp_path: Path) -> None:
    empty = pd.DataFrame()

    status = save_outputs(
        comparison_df=_legacy_comparison(value=99),
        wide_year_df=empty,
        total_check_df=empty,
        source_coverage_check_df=empty,
        missing_map_df=empty,
        output_dir=tmp_path,
        error_occurred=True,
        run_id="failed_run",
        run_timestamp_utc="2026-07-28T01:00:00+00:00",
    )

    assert not (tmp_path / FACT_FILENAME).exists()
    assert not (tmp_path / METADATA_FILENAME).exists()
    assert not (tmp_path / MANIFEST_FILENAME).exists()
    contract_status = status[status["record_type"].eq("output_contract_publication")].iloc[0]
    assert contract_status["status"] == "not_published_needs_mapping_review"


def test_contract_construction_failure_cannot_replace_canonical_legacy(tmp_path: Path) -> None:
    empty = pd.DataFrame()
    save_outputs(
        comparison_df=_legacy_comparison(value=10),
        wide_year_df=empty,
        total_check_df=empty,
        source_coverage_check_df=empty,
        missing_map_df=empty,
        output_dir=tmp_path,
        error_occurred=False,
        run_id="successful_run",
        run_timestamp_utc="2026-07-28T00:00:00+00:00",
    )
    preserved_names = [
        FACT_FILENAME,
        METADATA_FILENAME,
        MANIFEST_FILENAME,
        "common_esto_comparison_data.csv",
    ]
    previous = {name: (tmp_path / name).read_bytes() for name in preserved_names}
    invalid = _legacy_comparison(value=99)
    invalid.loc[0, "year"] = 23

    with pytest.raises(ValueError, match="integer four-digit years"):
        save_outputs(
            comparison_df=invalid,
            wide_year_df=empty,
            total_check_df=empty,
            source_coverage_check_df=empty,
            missing_map_df=empty,
            output_dir=tmp_path,
            error_occurred=False,
            run_id="invalid_run",
            run_timestamp_utc="2026-07-28T01:00:00+00:00",
        )

    assert {name: (tmp_path / name).read_bytes() for name in preserved_names} == previous
