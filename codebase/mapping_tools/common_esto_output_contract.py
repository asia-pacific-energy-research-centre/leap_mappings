#%%
"""Build and atomically publish the additive Common ESTO output contract."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


CONTRACT_VERSION = "common_esto_output_contract_v1"
FACT_FILENAME = "common_esto_comparison_fact.csv.gz"
METADATA_FILENAME = "common_esto_row_metadata.csv"
MANIFEST_FILENAME = "common_esto_output_contract.json"

FACT_COLUMNS = [
    "comparison_scope",
    "source_system",
    "economy",
    "scenario",
    "year",
    "common_row_id",
    "value",
]
FACT_KEY_COLUMNS = FACT_COLUMNS[:-1]

METADATA_COLUMNS = [
    "comparison_scope",
    "common_row_id",
    "common_flow_code",
    "common_flow_name",
    "common_flow_label",
    "common_product_code",
    "common_product_name",
    "common_product_label",
    "common_row_basis",
    "is_exact_row",
    "requires_rollup",
    "is_non_expanding_rollup",
    "non_expanding_rollup_id",
    "rollup_mode",
    "source_aggregate_labels",
    "source_aggregate_group_ids",
]
METADATA_KEY_COLUMNS = METADATA_COLUMNS[:2]
BOOLEAN_METADATA_COLUMNS = [
    "is_exact_row",
    "requires_rollup",
    "is_non_expanding_rollup",
]

LEGACY_COMPARISON_COLUMNS = [
    "comparison_scope",
    "source_system",
    "economy",
    "scenario",
    "year",
    "common_flow_code",
    "common_flow_name",
    "common_flow_label",
    "common_product_code",
    "common_product_name",
    "common_product_label",
    "common_row_id",
    "common_row_basis",
    "is_exact_row",
    "requires_rollup",
    "is_non_expanding_rollup",
    "non_expanding_rollup_id",
    "rollup_mode",
    "source_aggregate_labels",
    "source_aggregate_group_ids",
    "value",
]


def _require_columns(frame: pd.DataFrame, columns: list[str], table_name: str) -> None:
    """Raise a useful error when an input table does not match the contract."""
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{table_name} is missing required columns: {missing}")


def _duplicate_key_examples(frame: pd.DataFrame, key_columns: list[str]) -> list[dict[str, object]]:
    """Return a small set of duplicate-key examples for an error message."""
    duplicate_mask = frame.duplicated(key_columns, keep=False)
    return frame.loc[duplicate_mask, key_columns].drop_duplicates().head(10).to_dict("records")


def _validate_publication_identity(run_id: str, run_timestamp_utc: str) -> None:
    """Certify the run identity fields required by strict consumers."""
    if not str(run_id).strip():
        raise ValueError("Common ESTO output contract run_id must be nonempty.")
    timestamp_text = str(run_timestamp_utc).strip()
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "Common ESTO output contract run_timestamp_utc must be a valid ISO timestamp."
        ) from exc
    if parsed_timestamp.tzinfo is None or parsed_timestamp.utcoffset() is None:
        raise ValueError(
            "Common ESTO output contract run_timestamp_utc must be timezone-aware."
        )


def _validate_nonempty_keys(frame: pd.DataFrame, key_columns: list[str], table_name: str) -> None:
    """Reject null, blank, or whitespace-only public key values."""
    for column in key_columns:
        if column == "year":
            continue
        invalid = frame[column].isna() | frame[column].astype(str).str.strip().eq("")
        if invalid.any():
            raise ValueError(f"{table_name} key column {column!r} contains empty values.")


def _strict_boolean(value: object, column: str) -> bool:
    """Normalize only genuine booleans and canonical CSV boolean strings."""
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise ValueError(
        f"Common ESTO metadata column {column!r} must contain strict boolean values."
    )


def _certify_legacy_comparison(legacy_comparison_df: pd.DataFrame) -> pd.DataFrame:
    """Return a dashboard-safe normalized copy of the legacy comparison."""
    _require_columns(
        legacy_comparison_df,
        LEGACY_COMPARISON_COLUMNS,
        "Legacy Common ESTO comparison",
    )
    certified = legacy_comparison_df[LEGACY_COMPARISON_COLUMNS].copy()
    _validate_nonempty_keys(certified, FACT_KEY_COLUMNS, "Common ESTO fact")

    numeric_years = pd.to_numeric(certified["year"], errors="coerce")
    invalid_years = (
        numeric_years.isna()
        | numeric_years.mod(1).ne(0)
        | numeric_years.lt(1000)
        | numeric_years.gt(9999)
    )
    if invalid_years.any():
        raise ValueError("Common ESTO fact year must contain integer four-digit years.")
    certified["year"] = numeric_years.astype("int64")

    boolean_values = certified["value"].map(lambda value: isinstance(value, (bool, np.bool_)))
    numeric_values = pd.to_numeric(certified["value"], errors="coerce")
    if not np.isfinite(numeric_values.to_numpy(dtype="float64")).all():
        raise ValueError("Common ESTO fact value must contain finite numeric values.")
    if boolean_values.any():
        raise ValueError("Common ESTO fact value must contain finite numeric values, not booleans.")
    certified["value"] = numeric_values.astype("float64")

    for column in BOOLEAN_METADATA_COLUMNS:
        certified[column] = certified[column].map(
            lambda value, column=column: _strict_boolean(value, column)
        ).astype(bool)
    return certified


def build_common_esto_output_tables(
    legacy_comparison_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split the denormalized legacy comparison into fact and metadata tables."""
    certified = _certify_legacy_comparison(legacy_comparison_df)

    metadata_candidates = certified[METADATA_COLUMNS].drop_duplicates()
    _validate_nonempty_keys(
        metadata_candidates,
        METADATA_KEY_COLUMNS,
        "Common ESTO metadata",
    )
    if metadata_candidates.duplicated(METADATA_KEY_COLUMNS, keep=False).any():
        examples = _duplicate_key_examples(metadata_candidates, METADATA_KEY_COLUMNS)
        raise ValueError(
            "Common ESTO metadata conflicts within (comparison_scope, common_row_id). "
            f"Examples: {examples}"
        )

    fact_df = certified[FACT_COLUMNS].copy()
    if fact_df.duplicated(FACT_KEY_COLUMNS, keep=False).any():
        examples = _duplicate_key_examples(fact_df, FACT_KEY_COLUMNS)
        raise ValueError(
            "Common ESTO fact rows are not unique on the six-column fact key. "
            f"Examples: {examples}"
        )

    metadata_df = metadata_candidates.reset_index(drop=True)
    return fact_df.reset_index(drop=True), metadata_df


def reconstruct_common_esto_comparison(
    fact_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
) -> pd.DataFrame:
    """Reconstruct the legacy denormalized comparison in its exact column order."""
    _require_columns(fact_df, FACT_COLUMNS, "Common ESTO fact")
    _require_columns(metadata_df, METADATA_COLUMNS, "Common ESTO metadata")
    _validate_nonempty_keys(fact_df, FACT_KEY_COLUMNS, "Common ESTO fact")
    _validate_nonempty_keys(metadata_df, METADATA_KEY_COLUMNS, "Common ESTO metadata")
    if fact_df.duplicated(FACT_KEY_COLUMNS, keep=False).any():
        examples = _duplicate_key_examples(fact_df, FACT_KEY_COLUMNS)
        raise ValueError(f"Common ESTO fact contains duplicate keys. Examples: {examples}")
    if metadata_df.duplicated(METADATA_KEY_COLUMNS, keep=False).any():
        examples = _duplicate_key_examples(metadata_df, METADATA_KEY_COLUMNS)
        raise ValueError(f"Common ESTO metadata contains duplicate keys. Examples: {examples}")

    reconstructed = fact_df.merge(
        metadata_df,
        on=METADATA_KEY_COLUMNS,
        how="left",
        validate="many_to_one",
        sort=False,
        indicator=True,
    )
    missing_metadata = reconstructed["_merge"].ne("both")
    if missing_metadata.any():
        examples = (
            reconstructed.loc[missing_metadata, METADATA_KEY_COLUMNS]
            .drop_duplicates()
            .head(10)
            .to_dict("records")
        )
        raise ValueError(f"Common ESTO fact rows are missing metadata. Examples: {examples}")
    return reconstructed.drop(columns="_merge")[LEGACY_COMPARISON_COLUMNS]


def _validate_reconstruction_in_chunks(
    legacy_comparison_df: pd.DataFrame,
    fact_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
    chunk_size: int,
) -> None:
    """Certify exact reconstruction without holding two full legacy copies."""
    if chunk_size <= 0:
        raise ValueError("Common ESTO reconstruction chunk_size must be positive.")
    for start in range(0, len(fact_df), chunk_size):
        stop = min(start + chunk_size, len(fact_df))
        reconstructed = reconstruct_common_esto_comparison(
            fact_df.iloc[start:stop],
            metadata_df,
        ).reset_index(drop=True)
        expected = _certify_legacy_comparison(
            legacy_comparison_df.iloc[start:stop]
        ).reset_index(drop=True)
        if not reconstructed.equals(expected):
            raise ValueError(
                "Fact and metadata reconstruction does not exactly match the "
                f"legacy comparison in rows {start}:{stop}."
            )


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of one file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_manifest(
    path: Path,
    relative_path: str,
    file_format: str,
    columns: list[str],
    key_columns: list[str],
    row_count: int,
) -> dict[str, object]:
    """Build the authoritative manifest entry for one staged artifact."""
    return {
        "path": relative_path,
        "format": file_format,
        "columns": columns,
        "key_columns": key_columns,
        "row_count": int(row_count),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _atomic_replace(source: Path, destination: Path) -> None:
    """Replace one destination atomically on the current filesystem."""
    os.replace(source, destination)


def write_common_esto_output_contract(
    legacy_comparison_df: pd.DataFrame,
    output_dir: Path,
    run_id: str,
    run_timestamp_utc: str,
    structural_contract_manifest_path: Path | None = None,
    reconstruction_chunk_size: int = 250_000,
) -> tuple[dict[str, object], list[Path]]:
    """Write the fact, metadata, and commit-marker manifest as one transaction.

    The manifest is promoted last. Consumers must treat it as authoritative and
    verify its hashes, so a partially promoted pair is never a valid generation.
    Existing files are restored if any promotion or final verification fails.
    """
    _validate_publication_identity(run_id, run_timestamp_utc)
    fact_df, metadata_df = build_common_esto_output_tables(legacy_comparison_df)
    _validate_reconstruction_in_chunks(
        legacy_comparison_df,
        fact_df,
        metadata_df,
        chunk_size=reconstruction_chunk_size,
    )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    targets = {
        "fact": output_dir / FACT_FILENAME,
        "metadata": output_dir / METADATA_FILENAME,
        "manifest": output_dir / MANIFEST_FILENAME,
    }
    staging_dir = Path(tempfile.mkdtemp(prefix=".common_esto_contract_", dir=output_dir))
    backup_dir = staging_dir / "previous"
    backup_dir.mkdir()
    staged_fact = staging_dir / FACT_FILENAME
    staged_metadata = staging_dir / METADATA_FILENAME
    staged_manifest = staging_dir / MANIFEST_FILENAME

    try:
        fact_df.to_csv(staged_fact, index=False, compression={"method": "gzip", "mtime": 0})
        metadata_df.to_csv(staged_metadata, index=False)
        manifest = {
            "contract_version": CONTRACT_VERSION,
            "run_id": run_id,
            "run_timestamp_utc": run_timestamp_utc,
            "observed_rows_only": True,
            "fact": _artifact_manifest(
                staged_fact,
                FACT_FILENAME,
                "csv.gz",
                FACT_COLUMNS,
                FACT_KEY_COLUMNS,
                len(fact_df),
            ),
            "metadata": _artifact_manifest(
                staged_metadata,
                METADATA_FILENAME,
                "csv",
                METADATA_COLUMNS,
                METADATA_KEY_COLUMNS,
                len(metadata_df),
            ),
        }
        if structural_contract_manifest_path is not None:
            structural_manifest_path = Path(structural_contract_manifest_path)
            if not structural_manifest_path.exists():
                raise FileNotFoundError(
                    "Selected hierarchy/subtotal contract manifest does not exist: "
                    f"{structural_manifest_path}"
                )
            structural_manifest = json.loads(
                structural_manifest_path.read_text(encoding="utf-8")
            )
            if structural_manifest.get("validation_result") != "passed":
                raise ValueError("Selected hierarchy/subtotal contract is invalid")
            manifest["hierarchy_subtotal_contract"] = {
                "contract_name": structural_manifest.get("contract_name", ""),
                "schema_version": structural_manifest.get("schema_version", ""),
                "build_id": structural_manifest.get("build_id", ""),
                "manifest_path": str(structural_manifest_path.resolve()),
                "manifest_sha256": _sha256(structural_manifest_path),
            }
        staged_manifest.write_text(
            json.dumps(manifest, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )

        existing_targets: set[str] = set()
        for name, target in targets.items():
            if target.exists():
                shutil.copy2(target, backup_dir / target.name)
                existing_targets.add(name)

        promoted: list[str] = []
        try:
            for name, staged_path in [
                ("fact", staged_fact),
                ("metadata", staged_metadata),
                ("manifest", staged_manifest),
            ]:
                _atomic_replace(staged_path, targets[name])
                promoted.append(name)

            if (
                _sha256(targets["fact"]) != manifest["fact"]["sha256"]
                or _sha256(targets["metadata"]) != manifest["metadata"]["sha256"]
            ):
                raise OSError("Published Common ESTO contract artifacts failed hash verification.")
        except Exception:
            for name in reversed(promoted):
                backup_path = backup_dir / targets[name].name
                if name in existing_targets:
                    _atomic_replace(backup_path, targets[name])
                elif targets[name].exists():
                    targets[name].unlink()
            raise

        return manifest, [targets["fact"], targets["metadata"], targets["manifest"]]
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


#%%
