"""Tests for exact ESTO-base plus ESTO-Extended row overlays."""

import gzip

import pandas as pd
import pytest

from codebase.mapping_tools.esto_extended_delta import (
    DELTA_OPERATION_COLUMN,
    build_esto_extended_exact_row_delta,
    load_esto_extended_delta_contract,
    materialize_esto_extended_delta_contract,
    prepare_esto_extended_stage3_path,
    reconstruct_esto_extended_exact_rows,
    write_esto_extended_delta_contract,
)


COLUMNS = [
    "economy",
    "esto_flow",
    "esto_product",
    "year",
    "value",
    "source_system",
    "scenario",
    "non_expanding_rollup_id",
]


def _row(
    flow: str,
    value: float,
    source_system: str,
    product: str = "17 Electricity",
) -> dict[str, object]:
    return {
        "economy": "20USA",
        "esto_flow": flow,
        "esto_product": product,
        "year": 2022,
        "value": value,
        "source_system": source_system,
        "scenario": "historical",
        "non_expanding_rollup_id": "",
    }


def _sort(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values(
        ["economy", "esto_flow", "esto_product", "year"],
        kind="stable",
    ).reset_index(drop=True)


def test_delta_reconstructs_add_change_and_former_leaf_removal_exactly() -> None:
    base = pd.DataFrame(
        [
            _row("09.01 Unchanged", 10, "ESTO"),
            _row("09.02 Changed", 20, "ESTO"),
            _row("09.03 Former leaf", 30, "ESTO"),
        ],
        columns=COLUMNS,
    )
    extended = pd.DataFrame(
        [
            _row("09.01 Unchanged", 10, "ESTO_EXTENDED"),
            _row("09.02 Changed", 22, "ESTO_EXTENDED"),
            _row("09.03.01 New child", 30, "ESTO_EXTENDED"),
        ],
        columns=COLUMNS,
    )

    delta = build_esto_extended_exact_row_delta(
        base,
        extended,
        partition_count=3,
    )
    reconstructed = reconstruct_esto_extended_exact_rows(
        base,
        delta,
        partition_count=3,
    )

    assert delta[DELTA_OPERATION_COLUMN].value_counts().to_dict() == {
        "upsert": 2,
        "delete": 1,
    }
    assert "09.01 Unchanged" not in set(delta["esto_flow"])
    pd.testing.assert_frame_equal(_sort(reconstructed), _sort(extended))


def test_identical_dataset_needs_no_delta_beyond_source_relabelling() -> None:
    base = pd.DataFrame([_row("09.01 Unchanged", 10, "ESTO")], columns=COLUMNS)
    extended = base.copy()
    extended["source_system"] = "ESTO_EXTENDED"

    delta = build_esto_extended_exact_row_delta(base, extended)
    reconstructed = reconstruct_esto_extended_exact_rows(base, delta)

    assert delta.empty
    pd.testing.assert_frame_equal(_sort(reconstructed), _sort(extended))


def test_delta_preserves_rollup_identity_as_part_of_the_row_key() -> None:
    base = pd.DataFrame([_row("09 Rollup", 10, "ESTO")], columns=COLUMNS)
    extended = pd.DataFrame(
        [
            _row("09 Rollup", 10, "ESTO_EXTENDED"),
            {
                **_row("09 Rollup", 4, "ESTO_EXTENDED"),
                "non_expanding_rollup_id": "rollup_1",
            },
        ],
        columns=COLUMNS,
    )

    delta = build_esto_extended_exact_row_delta(base, extended)

    assert len(delta) == 1
    assert delta.loc[0, DELTA_OPERATION_COLUMN] == "upsert"
    assert delta.loc[0, "non_expanding_rollup_id"] == "rollup_1"


def test_null_and_literal_string_identities_remain_distinct() -> None:
    identities = [None, "", "nan", "<null>"]
    base = pd.DataFrame(
        [
            {
                **_row("09 Rollup", index + 1, "ESTO"),
                "non_expanding_rollup_id": identity,
            }
            for index, identity in enumerate(identities)
        ],
        columns=COLUMNS,
    )
    extended = base.copy()
    extended["source_system"] = "ESTO_EXTENDED"
    extended.loc[
        extended["non_expanding_rollup_id"].eq(""),
        "value",
    ] = 20

    delta = build_esto_extended_exact_row_delta(
        base,
        extended,
        partition_count=3,
    )
    reconstructed = reconstruct_esto_extended_exact_rows(
        base,
        delta,
        partition_count=3,
    )

    assert len(delta) == 1
    assert delta.loc[0, "non_expanding_rollup_id"] == ""
    expected_by_identity = {
        "<NULL>" if pd.isna(row["non_expanding_rollup_id"]) else row["non_expanding_rollup_id"]: row["value"]
        for _, row in extended.iterrows()
    }
    actual_by_identity = {
        "<NULL>" if pd.isna(row["non_expanding_rollup_id"]) else row["non_expanding_rollup_id"]: row["value"]
        for _, row in reconstructed.iterrows()
    }
    assert actual_by_identity == expected_by_identity


def test_scalar_types_remain_part_of_identity_across_inferred_dtypes() -> None:
    base = pd.DataFrame(
        [
            {**_row("09 Typed", 1, "ESTO"), "year": 2022},
            {**_row("09 Typed", 2, "ESTO"), "year": "2022"},
        ],
        columns=COLUMNS,
    )
    extended = base.copy()
    extended["source_system"] = "ESTO_EXTENDED"

    delta = build_esto_extended_exact_row_delta(
        base,
        extended,
        partition_count=2,
    )
    reconstructed = reconstruct_esto_extended_exact_rows(
        base,
        delta,
        partition_count=2,
    )

    assert delta.empty
    assert {(type(value).__name__, value) for value in reconstructed["year"]} == {
        ("int", 2022),
        ("str", "2022"),
    }


def test_delta_rejects_schema_source_and_duplicate_identity_ambiguity() -> None:
    base = pd.DataFrame([_row("09.01 Row", 10, "ESTO")], columns=COLUMNS)
    extended = pd.DataFrame(
        [_row("09.01 Row", 10, "ESTO_EXTENDED")],
        columns=COLUMNS,
    )

    with pytest.raises(ValueError, match="identical ordered columns"):
        build_esto_extended_exact_row_delta(
            base,
            extended.drop(columns="non_expanding_rollup_id"),
        )
    wrong_source = extended.copy()
    wrong_source["source_system"] = "ESTO"
    with pytest.raises(ValueError, match="ESTO_EXTENDED"):
        build_esto_extended_exact_row_delta(base, wrong_source)
    with pytest.raises(ValueError, match="duplicate row identity"):
        build_esto_extended_exact_row_delta(
            pd.concat([base, base], ignore_index=True),
            extended,
        )
    with pytest.raises(ValueError, match="duplicate row identity"):
        build_esto_extended_exact_row_delta(
            base,
            pd.concat([extended, extended], ignore_index=True),
        )


def test_reconstruction_rejects_duplicate_delta_identities() -> None:
    base = pd.DataFrame([_row("09.01 Row", 10, "ESTO")], columns=COLUMNS)
    duplicate_delta = pd.DataFrame(
        [
            {
                DELTA_OPERATION_COLUMN: "upsert",
                **_row("09.01 Row", 11, "ESTO_EXTENDED"),
            },
            {
                DELTA_OPERATION_COLUMN: "upsert",
                **_row("09.01 Row", 12, "ESTO_EXTENDED"),
            },
        ],
        columns=[DELTA_OPERATION_COLUMN, *COLUMNS],
    )

    with pytest.raises(ValueError, match="duplicate row identity"):
        reconstruct_esto_extended_exact_rows(
            base,
            duplicate_delta,
            partition_count=2,
        )


def test_reconstruction_rejects_unknown_delete_and_operation() -> None:
    base = pd.DataFrame([_row("09.01 Row", 10, "ESTO")], columns=COLUMNS)
    unknown = pd.DataFrame(
        [
            {
                DELTA_OPERATION_COLUMN: "delete",
                **_row("09.99 Missing", 1, "ESTO_EXTENDED"),
            }
        ],
        columns=[DELTA_OPERATION_COLUMN, *COLUMNS],
    )
    with pytest.raises(ValueError, match="absent from the base"):
        reconstruct_esto_extended_exact_rows(base, unknown)

    unknown[DELTA_OPERATION_COLUMN] = "replace"
    with pytest.raises(ValueError, match="Unsupported"):
        reconstruct_esto_extended_exact_rows(base, unknown)


def test_delta_contract_binds_base_and_reconstructs_exactly(tmp_path) -> None:
    base = pd.DataFrame(
        [
            _row("09.01 Unchanged", 10, "ESTO"),
            _row("09.02 Changed", 20, "ESTO"),
            _row("09.03 Former leaf", 30, "ESTO"),
        ],
        columns=COLUMNS,
    )
    extended = pd.DataFrame(
        [
            _row("09.01 Unchanged", 10, "ESTO_EXTENDED"),
            _row("09.02 Changed", 22, "ESTO_EXTENDED"),
            _row("09.03.01 New child", 30, "ESTO_EXTENDED"),
        ],
        columns=COLUMNS,
    )
    base_path = tmp_path / "esto_results_exact_rows.csv.gz"
    extended_path = tmp_path / "esto_extended_results_exact_rows.csv.gz"
    delta_path = tmp_path / "esto_extended_results_exact_rows.delta.csv.gz"
    manifest_path = tmp_path / "esto_extended_results_exact_rows.delta.json"
    reconstructed_path = tmp_path / "reconstructed.csv.gz"
    base.to_csv(base_path, index=False)
    extended.to_csv(extended_path, index=False)

    manifest = write_esto_extended_delta_contract(
        esto_base_path=base_path,
        esto_extended_path=extended_path,
        delta_path=delta_path,
        manifest_path=manifest_path,
    )
    reconstructed, loaded_manifest = load_esto_extended_delta_contract(
        esto_base_path=base_path,
        delta_path=delta_path,
        manifest_path=manifest_path,
    )
    materialize_esto_extended_delta_contract(
        esto_base_path=base_path,
        delta_path=delta_path,
        manifest_path=manifest_path,
        output_path=reconstructed_path,
    )

    assert manifest == loaded_manifest
    assert manifest["exact_reconstruction_verified"] is True
    assert manifest["delta"]["operation_counts"] == {"upsert": 2, "delete": 1}
    assert len(reconstructed) == len(extended)
    pd.testing.assert_frame_equal(
        _sort(pd.read_csv(reconstructed_path)),
        _sort(pd.read_csv(extended_path)),
        check_dtype=False,
    )


def test_delta_contract_rejects_changed_base_and_delta(tmp_path) -> None:
    base = pd.DataFrame([_row("09.01 Row", 10, "ESTO")], columns=COLUMNS)
    extended = base.copy()
    extended["source_system"] = "ESTO_EXTENDED"
    base_path = tmp_path / "esto_results_exact_rows.csv.gz"
    extended_path = tmp_path / "esto_extended_results_exact_rows.csv.gz"
    delta_path = tmp_path / "esto_extended_results_exact_rows.delta.csv.gz"
    manifest_path = tmp_path / "esto_extended_results_exact_rows.delta.json"
    base.to_csv(base_path, index=False)
    extended.to_csv(extended_path, index=False)
    write_esto_extended_delta_contract(
        esto_base_path=base_path,
        esto_extended_path=extended_path,
        delta_path=delta_path,
        manifest_path=manifest_path,
    )
    original_base_bytes = base_path.read_bytes()

    changed_base = base.copy()
    changed_base.loc[0, "value"] = 99
    changed_base.to_csv(base_path, index=False)
    with pytest.raises(ValueError, match="base (size|hash)"):
        load_esto_extended_delta_contract(
            esto_base_path=base_path,
            delta_path=delta_path,
            manifest_path=manifest_path,
        )

    base_path.write_bytes(original_base_bytes)
    with delta_path.open("ab") as file_obj:
        file_obj.write(b"tamper")
    with pytest.raises(ValueError, match="delta (size|hash)"):
        load_esto_extended_delta_contract(
            esto_base_path=base_path,
            delta_path=delta_path,
            manifest_path=manifest_path,
        )


def test_stage3_delta_selection_uses_verified_contract_and_safe_fallback(
    tmp_path,
) -> None:
    base = pd.DataFrame([_row("09.01 Row", 10, "ESTO")], columns=COLUMNS)
    extended = base.copy()
    extended["source_system"] = "ESTO_EXTENDED"
    base_path = tmp_path / "esto_results_exact_rows.csv.gz"
    extended_path = tmp_path / "esto_extended_results_exact_rows.csv.gz"
    delta_path = tmp_path / "esto_extended_results_exact_rows.delta.csv.gz"
    manifest_path = tmp_path / "esto_extended_results_exact_rows.delta.json"
    base.to_csv(base_path, index=False)
    extended.to_csv(extended_path, index=False)
    write_esto_extended_delta_contract(
        esto_base_path=base_path,
        esto_extended_path=extended_path,
        delta_path=delta_path,
        manifest_path=manifest_path,
    )

    selected_path, temporary_dir, status = prepare_esto_extended_stage3_path(
        esto_base_path=base_path,
        full_extended_path=extended_path,
        delta_path=delta_path,
        manifest_path=manifest_path,
        use_delta=True,
    )
    assert status["mode"] == "delta"
    assert selected_path.exists()
    pd.testing.assert_frame_equal(
        pd.read_csv(selected_path),
        pd.read_csv(extended_path),
        check_dtype=False,
    )
    assert temporary_dir is not None
    temporary_dir.cleanup()

    changed_base = base.copy()
    changed_base.loc[0, "value"] = 99
    changed_base.to_csv(base_path, index=False)
    selected_path, temporary_dir, status = prepare_esto_extended_stage3_path(
        esto_base_path=base_path,
        full_extended_path=extended_path,
        delta_path=delta_path,
        manifest_path=manifest_path,
        use_delta=True,
    )
    assert selected_path == extended_path
    assert temporary_dir is None
    assert status["mode"] == "full_fallback"
    assert "base" in status["fallback_reason"]

    extended_path.unlink()
    with pytest.raises(RuntimeError, match="no full Extended"):
        prepare_esto_extended_stage3_path(
            esto_base_path=base_path,
            full_extended_path=extended_path,
            delta_path=delta_path,
            manifest_path=manifest_path,
            use_delta=True,
        )


def test_delta_contract_preserves_adjacent_float64_csv_values(tmp_path) -> None:
    """Round-trip parsing must not collapse adjacent float values into inheritance."""
    base_path = tmp_path / "esto_results_exact_rows.csv.gz"
    extended_path = tmp_path / "esto_extended_results_exact_rows.csv.gz"
    delta_path = tmp_path / "esto_extended_results_exact_rows.delta.csv.gz"
    manifest_path = tmp_path / "esto_extended_results_exact_rows.delta.json"
    header = ",".join(COLUMNS)
    identity = "20USA,09.01 Row,17 Electricity,2022"
    suffix_base = ",ESTO,historical,"
    suffix_extended = ",ESTO_EXTENDED,historical,"
    with gzip.open(base_path, "wt", encoding="utf-8", newline="") as file_obj:
        file_obj.write(f"{header}\n")
        file_obj.write(f"{identity},2.70685{suffix_base}\n")
    with gzip.open(extended_path, "wt", encoding="utf-8", newline="") as file_obj:
        file_obj.write(f"{header}\n")
        file_obj.write(f"{identity},2.7068499999999998{suffix_extended}\n")

    manifest = write_esto_extended_delta_contract(
        esto_base_path=base_path,
        esto_extended_path=extended_path,
        delta_path=delta_path,
        manifest_path=manifest_path,
    )
    reconstructed, _ = load_esto_extended_delta_contract(
        esto_base_path=base_path,
        delta_path=delta_path,
        manifest_path=manifest_path,
    )

    assert manifest["delta"]["operation_counts"] == {"upsert": 1}
    assert reconstructed.loc[0, "value"].hex() == float(
        "2.7068499999999998"
    ).hex()
