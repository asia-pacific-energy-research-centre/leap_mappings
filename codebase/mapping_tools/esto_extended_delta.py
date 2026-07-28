#%%
"""Exact row-overlay helpers for representing ESTO Extended from ESTO base rows."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.api.types import infer_dtype


BASE_SOURCE_SYSTEM = "ESTO"
EXTENDED_SOURCE_SYSTEM = "ESTO_EXTENDED"
DELTA_OPERATION_COLUMN = "delta_operation"
DELETE_OPERATION = "delete"
UPSERT_OPERATION = "upsert"
DEFAULT_PARTITION_ROW_TARGET = 100_000
DELTA_CONTRACT_VERSION = "esto_extended_exact_row_delta_v1"
REQUIRED_EXACT_ROW_COLUMNS = [
    "source_system",
    "economy",
    "scenario",
    "year",
    "esto_flow",
    "esto_product",
    "value",
]


def _require_exact_row_schema(frame: pd.DataFrame, table_name: str) -> None:
    """Require the finalized long-format schema consumed by Stage 3."""
    missing = [
        column for column in REQUIRED_EXACT_ROW_COLUMNS
        if column not in frame.columns
    ]
    if missing:
        raise ValueError(f"{table_name} is missing required exact-row columns: {missing}")


def _row_identity_columns(columns: list[str]) -> list[str]:
    """Use every non-value field except source identity as the row identity."""
    return [
        column for column in columns
        if column not in {"source_system", "value"}
    ]


def _partition_count(
    row_counts: list[int],
    requested_partition_count: int | None,
) -> int:
    """Choose small partitions while retaining a one-partition small-frame path."""
    if requested_partition_count is not None:
        if requested_partition_count < 1:
            raise ValueError("partition_count must be at least 1.")
        return requested_partition_count
    largest_row_count = max(row_counts, default=0)
    return max(1, math.ceil(largest_row_count / DEFAULT_PARTITION_ROW_TARGET))


def _identity_partition_ids(
    frame: pd.DataFrame,
    identity_columns: list[str],
    partition_count: int,
) -> np.ndarray:
    """Hash identities only to route equal rows into the same bounded partition."""
    if frame.empty:
        return np.array([], dtype=np.int64)
    # Hash one object-normalized column at a time. This keeps transient memory
    # bounded to one column and ensures equal Python scalar identities route to
    # the same partition even when equivalent frames inferred different dtypes.
    hashes = np.full(len(frame), np.uint64(1469598103934665603))
    for column in identity_columns:
        column_hashes = pd.util.hash_pandas_object(
            frame[column].astype(object),
            index=False,
            categorize=True,
        ).to_numpy(dtype=np.uint64, copy=False)
        hashes = np.bitwise_xor(
            hashes * np.uint64(1099511628211),
            column_hashes,
        )
    return np.remainder(hashes, partition_count).astype(np.int64, copy=False)


def _canonical_type_names(series: pd.Series, null_mask: pd.Series) -> pd.Series:
    """Return the Python-scalar type identity used by the former record path."""
    non_null = series[~null_mask]
    if non_null.empty:
        return pd.Series("null", index=series.index, dtype="string")

    inferred = infer_dtype(non_null, skipna=True)
    simple_types = {
        "string": "str",
        "bytes": "bytes",
        "integer": "int",
        "floating": "float",
        "boolean": "bool",
        "datetime": "Timestamp",
        "date": "date",
        "timedelta": "Timedelta",
        "decimal": "Decimal",
    }
    simple_type = simple_types.get(inferred)
    if simple_type is not None:
        type_names = pd.Series(simple_type, index=series.index, dtype="string")
    else:
        # Mixed object columns are uncommon in exact rows. Keep the fallback
        # partition-local so it cannot create a multi-million-record copy.
        type_names = series.map(
            lambda value: "null" if pd.isna(value) else type(value).__name__
        ).astype("string")
    type_names.loc[null_mask] = "null"
    return type_names


def _canonical_identity_projection(
    frame: pd.DataFrame,
    positions: np.ndarray,
    identity_columns: list[str],
    position_column: str,
    value_column: str,
) -> pd.DataFrame:
    """Build exact, null-safe join keys for one bounded row partition."""
    partition = frame.iloc[positions]
    projection = pd.DataFrame(index=partition.index)
    for column_number, column in enumerate(identity_columns):
        series = partition[column]
        null_mask = series.isna()
        type_names = _canonical_type_names(series, null_mask)
        values = series.astype("string").fillna("")
        projection[f"_identity_{column_number}"] = (
            type_names + ":" + values
        ).astype(object)
    projection[position_column] = positions
    projection[value_column] = partition["value"].to_numpy(copy=False)
    return projection.reset_index(drop=True)


def _duplicate_identity_example(
    frame: pd.DataFrame,
    projection: pd.DataFrame,
    identity_columns: list[str],
    position_column: str,
    table_name: str,
) -> None:
    """Reject duplicate exact identities within one hash partition."""
    key_columns = [
        column for column in projection.columns
        if column.startswith("_identity_")
    ]
    duplicate_mask = projection.duplicated(key_columns, keep=False)
    if not duplicate_mask.any():
        return
    position = int(projection.loc[duplicate_mask, position_column].iloc[0])
    example = frame.iloc[position][identity_columns].to_dict()
    raise ValueError(f"{table_name} contains a duplicate row identity: {example}")


def _partition_join(
    left_frame: pd.DataFrame,
    right_frame: pd.DataFrame,
    left_positions: np.ndarray,
    right_positions: np.ndarray,
    identity_columns: list[str],
    left_table_name: str,
    right_table_name: str,
) -> pd.DataFrame:
    """Outer-join one pair of bounded identity partitions."""
    left = _canonical_identity_projection(
        left_frame,
        left_positions,
        identity_columns,
        "_left_position",
        "_left_value",
    )
    right = _canonical_identity_projection(
        right_frame,
        right_positions,
        identity_columns,
        "_right_position",
        "_right_value",
    )
    _duplicate_identity_example(
        left_frame,
        left,
        identity_columns,
        "_left_position",
        left_table_name,
    )
    _duplicate_identity_example(
        right_frame,
        right,
        identity_columns,
        "_right_position",
        right_table_name,
    )
    key_columns = [
        column for column in left.columns
        if column.startswith("_identity_")
    ]
    return left.merge(
        right,
        on=key_columns,
        how="outer",
        validate="one_to_one",
        indicator=True,
    )


def _matching_values(merged: pd.DataFrame) -> pd.Series:
    """Compare values with the existing null-equals-null overlay semantics."""
    both_null = merged["_left_value"].isna() & merged["_right_value"].isna()
    equal = merged["_left_value"].eq(merged["_right_value"]).fillna(False)
    return both_null | equal


def _validate_source_identity(
    frame: pd.DataFrame,
    expected_source_system: str,
    table_name: str,
) -> None:
    invalid = (
        frame["source_system"].isna()
        | frame["source_system"].ne(expected_source_system)
    )
    if invalid.any():
        observed = sorted(set(frame["source_system"].dropna().astype(str)))
        raise ValueError(
            f"{table_name} must contain only source_system={expected_source_system!r}; "
            f"observed {observed}"
        )


def build_esto_extended_exact_row_delta(
    esto_base_rows: pd.DataFrame,
    esto_extended_rows: pd.DataFrame,
    partition_count: int | None = None,
) -> pd.DataFrame:
    """Build an exact add/change/delete overlay from finalized exact-row artifacts.

    Base rows are first relabelled from ``ESTO`` to ``ESTO_EXTENDED``. Unchanged
    relabelled rows are inherited and omitted from the delta. New or value-
    changed rows are ``upsert`` records; base rows absent from Extended are
    ``delete`` records. This handles former ESTO leaves that become subtotals
    after Extended introduces children.
    """
    _require_exact_row_schema(esto_base_rows, "ESTO base rows")
    _require_exact_row_schema(esto_extended_rows, "ESTO Extended rows")
    if list(esto_base_rows.columns) != list(esto_extended_rows.columns):
        raise ValueError(
            "ESTO base and Extended exact-row schemas must have identical ordered columns."
        )
    _validate_source_identity(esto_base_rows, BASE_SOURCE_SYSTEM, "ESTO base rows")
    _validate_source_identity(
        esto_extended_rows,
        EXTENDED_SOURCE_SYSTEM,
        "ESTO Extended rows",
    )

    columns = esto_extended_rows.columns.tolist()
    identity_columns = _row_identity_columns(columns)
    selected_partition_count = _partition_count(
        [len(esto_base_rows), len(esto_extended_rows)],
        partition_count,
    )
    base_partitions = _identity_partition_ids(
        esto_base_rows,
        identity_columns,
        selected_partition_count,
    )
    extended_partitions = _identity_partition_ids(
        esto_extended_rows,
        identity_columns,
        selected_partition_count,
    )

    delete_positions: list[np.ndarray] = []
    upsert_positions: list[np.ndarray] = []
    for partition_number in range(selected_partition_count):
        base_positions = np.flatnonzero(base_partitions == partition_number)
        extended_positions = np.flatnonzero(
            extended_partitions == partition_number
        )
        merged = _partition_join(
            esto_base_rows,
            esto_extended_rows,
            base_positions,
            extended_positions,
            identity_columns,
            "ESTO base rows",
            "ESTO Extended rows",
        )
        left_only = merged["_merge"].eq("left_only")
        right_only = merged["_merge"].eq("right_only")
        changed = merged["_merge"].eq("both") & ~_matching_values(merged)
        delete_positions.append(
            merged.loc[left_only, "_left_position"].astype(np.int64).to_numpy()
        )
        upsert_positions.append(
            merged.loc[right_only | changed, "_right_position"]
            .astype(np.int64)
            .to_numpy()
        )

    delete_index = (
        np.concatenate(delete_positions)
        if delete_positions
        else np.array([], dtype=np.int64)
    )
    upsert_index = (
        np.concatenate(upsert_positions)
        if upsert_positions
        else np.array([], dtype=np.int64)
    )
    delete_rows = esto_base_rows.iloc[delete_index].copy()
    delete_rows["source_system"] = EXTENDED_SOURCE_SYSTEM
    delete_rows.insert(0, DELTA_OPERATION_COLUMN, DELETE_OPERATION)
    upsert_rows = esto_extended_rows.iloc[upsert_index].copy()
    upsert_rows.insert(0, DELTA_OPERATION_COLUMN, UPSERT_OPERATION)
    return pd.concat(
        [delete_rows, upsert_rows],
        ignore_index=True,
    ).reindex(columns=[DELTA_OPERATION_COLUMN, *columns])


def reconstruct_esto_extended_exact_rows(
    esto_base_rows: pd.DataFrame,
    delta_rows: pd.DataFrame,
    partition_count: int | None = None,
) -> pd.DataFrame:
    """Apply an exact-row delta to ESTO base rows and return ESTO Extended rows."""
    _require_exact_row_schema(esto_base_rows, "ESTO base rows")
    _validate_source_identity(esto_base_rows, BASE_SOURCE_SYSTEM, "ESTO base rows")
    expected_delta_columns = [DELTA_OPERATION_COLUMN, *esto_base_rows.columns.tolist()]
    if list(delta_rows.columns) != expected_delta_columns:
        raise ValueError(
            "ESTO Extended delta schema must be delta_operation followed by the "
            "ordered base exact-row columns."
        )
    _validate_source_identity(
        delta_rows,
        EXTENDED_SOURCE_SYSTEM,
        "ESTO Extended delta",
    )

    columns = esto_base_rows.columns.tolist()
    identity_columns = _row_identity_columns(columns)
    unsupported_operations = sorted(
        set(delta_rows[DELTA_OPERATION_COLUMN].astype(str))
        - {DELETE_OPERATION, UPSERT_OPERATION}
    )
    if unsupported_operations:
        raise ValueError(
            "Unsupported ESTO Extended delta operation: "
            f"{unsupported_operations[0]!r}"
        )

    delta_payload = delta_rows.drop(columns=DELTA_OPERATION_COLUMN)
    selected_partition_count = _partition_count(
        [len(esto_base_rows), len(delta_payload)],
        partition_count,
    )
    base_partitions = _identity_partition_ids(
        esto_base_rows,
        identity_columns,
        selected_partition_count,
    )
    delta_partitions = _identity_partition_ids(
        delta_payload,
        identity_columns,
        selected_partition_count,
    )

    replaced_base_positions: list[np.ndarray] = []
    upsert_delta_positions: list[np.ndarray] = []
    for partition_number in range(selected_partition_count):
        base_positions = np.flatnonzero(base_partitions == partition_number)
        delta_positions = np.flatnonzero(delta_partitions == partition_number)
        merged = _partition_join(
            esto_base_rows,
            delta_payload,
            base_positions,
            delta_positions,
            identity_columns,
            "ESTO base rows",
            "ESTO Extended delta",
        )
        right_positions = merged["_right_position"].dropna().astype(np.int64)
        if right_positions.empty:
            continue
        operations = delta_rows.iloc[right_positions.to_numpy()][
            DELTA_OPERATION_COLUMN
        ].reset_index(drop=True)
        matched_delta = merged.loc[
            merged["_right_position"].notna(),
            ["_left_position", "_right_position", "_merge"],
        ].reset_index(drop=True)
        delete_mask = operations.eq(DELETE_OPERATION)
        unknown_delete = delete_mask & matched_delta["_merge"].eq("right_only")
        if unknown_delete.any():
            raise ValueError(
                "ESTO Extended delta cannot delete a row absent from the base."
            )
        matched_base = matched_delta["_left_position"].dropna().astype(np.int64)
        if not matched_base.empty:
            replaced_base_positions.append(matched_base.to_numpy())
        upsert_delta_positions.append(
            matched_delta.loc[
                operations.eq(UPSERT_OPERATION),
                "_right_position",
            ].astype(np.int64).to_numpy()
        )

    keep_base = np.ones(len(esto_base_rows), dtype=bool)
    if replaced_base_positions:
        keep_base[np.concatenate(replaced_base_positions)] = False
    inherited_rows = esto_base_rows.iloc[np.flatnonzero(keep_base)].copy()
    inherited_rows["source_system"] = EXTENDED_SOURCE_SYSTEM
    upsert_index = (
        np.concatenate(upsert_delta_positions)
        if upsert_delta_positions
        else np.array([], dtype=np.int64)
    )
    upsert_rows = delta_payload.iloc[upsert_index]
    return pd.concat(
        [inherited_rows, upsert_rows],
        ignore_index=True,
    ).reindex(columns=columns)


#%%
def _sha256(path: Path) -> str:
    """Return a streaming SHA-256 digest for one artifact."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_exact_rows(path: Path) -> pd.DataFrame:
    """Read a finalized exact-row artifact with bounded dimension memory."""
    path = Path(path)
    header = pd.read_csv(path, nrows=0).columns.tolist()
    dtypes = {
        column: ("float64" if column == "value" else "category")
        for column in header
    }
    return pd.read_csv(
        path,
        dtype=dtypes,
        keep_default_na=False,
        float_precision="round_trip",
    )


def _artifact_identity(
    path: Path,
    frame: pd.DataFrame,
) -> dict[str, object]:
    """Describe one exact artifact without relying on mutable timestamps."""
    path = Path(path)
    return {
        "file": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "row_count": len(frame),
        "schema": frame.columns.tolist(),
    }


def assert_exact_row_frames_equal(
    actual: pd.DataFrame,
    expected: pd.DataFrame,
    partition_count: int | None = None,
) -> None:
    """Require exact identity/value equivalence without a full-frame sort."""
    if list(actual.columns) != list(expected.columns):
        raise AssertionError("Exact-row schemas differ.")
    identity_columns = _row_identity_columns(expected.columns.tolist())
    selected_partition_count = _partition_count(
        [len(actual), len(expected)],
        partition_count,
    )
    actual_partitions = _identity_partition_ids(
        actual,
        identity_columns,
        selected_partition_count,
    )
    expected_partitions = _identity_partition_ids(
        expected,
        identity_columns,
        selected_partition_count,
    )
    for partition_number in range(selected_partition_count):
        merged = _partition_join(
            actual,
            expected,
            np.flatnonzero(actual_partitions == partition_number),
            np.flatnonzero(expected_partitions == partition_number),
            identity_columns,
            "reconstructed ESTO Extended rows",
            "expected ESTO Extended rows",
        )
        if (
            not merged["_merge"].eq("both").all()
            or not _matching_values(merged).all()
        ):
            raise AssertionError(
                "Reconstructed ESTO Extended rows differ from the exact-row artifact."
            )


def write_esto_extended_delta_contract(
    esto_base_path: Path,
    esto_extended_path: Path,
    delta_path: Path,
    manifest_path: Path,
) -> dict[str, object]:
    """Atomically publish a verified base-bound ESTO Extended delta contract."""
    esto_base_path = Path(esto_base_path)
    esto_extended_path = Path(esto_extended_path)
    delta_path = Path(delta_path)
    manifest_path = Path(manifest_path)
    if delta_path.parent != manifest_path.parent:
        raise ValueError("Delta and manifest must share one publication directory.")

    base = _read_exact_rows(esto_base_path)
    extended = _read_exact_rows(esto_extended_path)
    delta = build_esto_extended_exact_row_delta(base, extended)
    reconstructed = reconstruct_esto_extended_exact_rows(base, delta)
    assert_exact_row_frames_equal(reconstructed, extended)

    output_dir = delta_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".esto_extended_delta_staging_",
        dir=output_dir,
    ) as staging_name:
        staging_dir = Path(staging_name)
        staged_delta = staging_dir / delta_path.name
        staged_manifest = staging_dir / manifest_path.name
        delta.to_csv(
            staged_delta,
            index=False,
            compression={"method": "gzip", "mtime": 0},
        )
        operation_counts = (
            delta[DELTA_OPERATION_COLUMN].value_counts(dropna=False).to_dict()
        )
        manifest = {
            "version": DELTA_CONTRACT_VERSION,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "exact_reconstruction_verified": True,
            "base": _artifact_identity(esto_base_path, base),
            "full_extended": _artifact_identity(esto_extended_path, extended),
            "delta": {
                **_artifact_identity(staged_delta, delta),
                "operation_counts": {
                    str(operation): int(count)
                    for operation, count in operation_counts.items()
                },
            },
        }
        staged_manifest.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(staged_delta, delta_path)
        os.replace(staged_manifest, manifest_path)
    return manifest


def load_esto_extended_delta_contract(
    esto_base_path: Path,
    delta_path: Path,
    manifest_path: Path,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Validate a delta contract and reconstruct exact ESTO Extended rows."""
    esto_base_path = Path(esto_base_path)
    delta_path = Path(delta_path)
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != DELTA_CONTRACT_VERSION:
        raise ValueError(
            f"Unsupported ESTO Extended delta contract: {manifest.get('version')!r}"
        )
    if manifest.get("exact_reconstruction_verified") is not True:
        raise ValueError("ESTO Extended delta manifest is not reconstruction-verified.")

    for label, path in [("base", esto_base_path), ("delta", delta_path)]:
        entry = manifest.get(label)
        if not isinstance(entry, dict):
            raise ValueError(f"ESTO Extended delta manifest is missing {label!r}.")
        if entry.get("file") != path.name:
            raise ValueError(f"ESTO Extended {label} filename does not match manifest.")
        if entry.get("size_bytes") != path.stat().st_size:
            raise ValueError(f"ESTO Extended {label} size does not match manifest.")
        if entry.get("sha256") != _sha256(path):
            raise ValueError(f"ESTO Extended {label} hash does not match manifest.")

    base = _read_exact_rows(esto_base_path)
    delta = _read_exact_rows(delta_path)
    base_entry = manifest["base"]
    delta_entry = manifest["delta"]
    if base_entry.get("schema") != base.columns.tolist():
        raise ValueError("ESTO Extended base schema does not match manifest.")
    if delta_entry.get("schema") != delta.columns.tolist():
        raise ValueError("ESTO Extended delta schema does not match manifest.")
    if base_entry.get("row_count") != len(base):
        raise ValueError("ESTO Extended base row count does not match manifest.")
    if delta_entry.get("row_count") != len(delta):
        raise ValueError("ESTO Extended delta row count does not match manifest.")

    operation_counts = {
        str(operation): int(count)
        for operation, count in (
            delta[DELTA_OPERATION_COLUMN].value_counts(dropna=False).to_dict()
        ).items()
    }
    if delta_entry.get("operation_counts") != operation_counts:
        raise ValueError("ESTO Extended delta operation counts do not match manifest.")
    return reconstruct_esto_extended_exact_rows(base, delta), manifest


def materialize_esto_extended_delta_contract(
    esto_base_path: Path,
    delta_path: Path,
    manifest_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """Validate and materialize a delta contract for path-based Stage 3 readers."""
    reconstructed, manifest = load_esto_extended_delta_contract(
        esto_base_path=esto_base_path,
        delta_path=delta_path,
        manifest_path=manifest_path,
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    reconstructed.to_csv(output_path, index=False)
    return manifest


#%%
def prepare_esto_extended_stage3_path(
    esto_base_path: Path,
    full_extended_path: Path,
    delta_path: Path,
    manifest_path: Path,
    use_delta: bool,
) -> tuple[Path, tempfile.TemporaryDirectory[str] | None, dict[str, object]]:
    """Choose full or verified delta-backed ESTO Extended input for Stage 3."""
    from codebase.mapping_tools.result_storage import prefer_compressed_csv_path

    full_extended_path = prefer_compressed_csv_path(full_extended_path)
    if not use_delta:
        return full_extended_path, None, {"mode": "full"}

    temporary_dir = tempfile.TemporaryDirectory(
        prefix="leap_mappings_esto_extended_delta_"
    )
    reconstructed_path = (
        Path(temporary_dir.name) / "esto_extended_results_exact_rows.csv.gz"
    )
    try:
        manifest = materialize_esto_extended_delta_contract(
            esto_base_path=prefer_compressed_csv_path(esto_base_path),
            delta_path=delta_path,
            manifest_path=manifest_path,
            output_path=reconstructed_path,
        )
        return reconstructed_path, temporary_dir, {
            "mode": "delta",
            "manifest_path": str(Path(manifest_path).resolve()),
            "base_sha256": manifest["base"]["sha256"],
            "delta_sha256": manifest["delta"]["sha256"],
        }
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        temporary_dir.cleanup()
        if full_extended_path.exists():
            return full_extended_path, None, {
                "mode": "full_fallback",
                "fallback_reason": str(exc),
            }
        raise RuntimeError(
            "The requested ESTO Extended delta contract is invalid and no full "
            "Extended exact-row fallback exists."
        ) from exc


#%%
