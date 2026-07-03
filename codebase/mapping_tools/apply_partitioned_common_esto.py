#%%
"""Apply compiled Common ESTO mappings partition by partition with lineage."""

#%%
from __future__ import annotations

import gc
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

from codebase.mapping_tools.structural_resolver import build_tree_index


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PARTITION_COLUMNS = ["source_system", "economy", "scenario", "year"]
SOURCE_COLUMNS = [*PARTITION_COLUMNS, "source_flow", "source_product", "value"]
LINEAGE_COLUMNS = [
    *PARTITION_COLUMNS, "original_source_flow", "original_source_product",
    "source_parent_flow", "source_parent_product", "effective_source_flow",
    "effective_source_product", "mapping_view", "rule_id", "rollup_context",
    "relationship_id", "evidence_type", "component_esto_flow",
    "component_esto_product", "comparison_scope", "common_row_id", "component_sign", "value",
    "common_flow_code", "common_flow_name", "common_flow_label", "common_product_code",
    "common_product_name", "common_product_label", "common_row_basis", "is_exact_row",
    "requires_rollup", "source_aggregate_labels", "source_aggregate_group_ids",
]
FINAL_COLUMNS = [
    "comparison_scope", "source_system", "economy", "scenario", "year",
    "common_flow_code", "common_flow_name", "common_flow_label", "common_product_code",
    "common_product_name", "common_product_label", "common_row_id", "common_row_basis",
    "is_exact_row", "requires_rollup", "source_aggregate_labels",
    "source_aggregate_group_ids", "mapping_view", "value",
]
ACCOUNTING_COLUMNS = [
    *PARTITION_COLUMNS, "comparison_scope", "mapping_view", "input_total", "mapped_total", "unmatched_total",
    "excluded_total", "input_row_count", "mapped_row_count", "unmatched_row_count",
]


def _source_identity(path: Path) -> dict[str, Any]:
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path.resolve()), "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns, "sha256": digest.hexdigest(),
    }


def _partition_key(values: tuple[Any, ...]) -> str:
    text = "||".join(str(value) for value in values)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _normalise_source_chunk(chunk: pd.DataFrame, default_source_system: str = "") -> pd.DataFrame:
    rename_candidates = {
        "flows": "source_flow", "esto_flow": "source_flow", "leap_flow": "source_flow",
        "products": "source_product", "esto_product": "source_product", "leap_product": "source_product",
        "scenarios": "scenario", "value_pj": "value",
    }
    rename = {source: target for source, target in rename_candidates.items() if source in chunk and target not in chunk}
    result = chunk.rename(columns=rename).copy()
    if "source_system" not in result:
        result["source_system"] = default_source_system
    missing = set(SOURCE_COLUMNS).difference(result.columns)
    if missing:
        raise ValueError(f"Source values are missing required columns: {sorted(missing)}")
    result = result[SOURCE_COLUMNS]
    for column in ["source_system", "economy", "scenario", "source_flow", "source_product"]:
        result[column] = result[column].fillna("").astype(str).str.strip()
    result["source_system"] = result["source_system"].str.upper()
    result["year"] = pd.to_numeric(result["year"], errors="raise").astype("int32")
    result["value"] = pd.to_numeric(result["value"], errors="coerce").fillna(0.0).astype("float64")
    return result


def prepare_partition_cache(
    source_path: Path,
    cache_dir: Path,
    default_source_system: str = "",
    chunksize: int = 250_000,
) -> dict[str, Any]:
    """Normalize a source CSV to complete group-partition Parquet directories."""
    source_path, cache_dir = Path(source_path), Path(cache_dir)
    identity = _source_identity(source_path)
    manifest_path = cache_dir / "cache_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") == "complete" and manifest.get("source_identity") == identity:
            return {**manifest, "cache_reused": True}

    staging = cache_dir.with_name(cache_dir.name + ".building")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    partition_records: dict[str, dict[str, Any]] = {}
    for chunk_number, chunk in enumerate(pd.read_csv(source_path, dtype=object, chunksize=chunksize)):
        normalized = _normalise_source_chunk(chunk, default_source_system)
        for values, group in normalized.groupby(PARTITION_COLUMNS, dropna=False, sort=False):
            values = tuple(values) if isinstance(values, tuple) else (values,)
            key = _partition_key(values)
            directory = staging / "partitions" / key
            directory.mkdir(parents=True, exist_ok=True)
            part_path = directory / f"part_{chunk_number:06d}.parquet"
            group.to_parquet(part_path, index=False)
            record = partition_records.setdefault(key, {column: value for column, value in zip(PARTITION_COLUMNS, values)})
            record["partition_key"] = key
            record["row_count"] = int(record.get("row_count", 0)) + len(group)
    manifest = {
        "status": "complete", "source_identity": identity,
        "partition_count": len(partition_records),
        "partitions": sorted(partition_records.values(), key=lambda row: tuple(str(row[column]) for column in PARTITION_COLUMNS)),
    }
    (staging / "cache_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    staging.replace(cache_dir)
    return {**manifest, "cache_reused": False}


def _preferred_mapping_view(mapping_df: pd.DataFrame) -> pd.DataFrame:
    """Label detailed and rolled boundaries as separate non-additive views."""
    mapping = mapping_df.copy()
    rolled = mapping["evidence_type"].eq("rollup_rule")
    mapping["mapping_view"] = "detailed"
    mapping.loc[rolled, "mapping_view"] = (
        "rolled:"
        + mapping.loc[rolled, "rollup_context"].fillna("").astype(str).replace("", "general")
        + ":"
        + mapping.loc[rolled, "effective_source_flow"].fillna("").astype(str)
        + "|"
        + mapping.loc[rolled, "effective_source_product"].fillna("").astype(str)
    )
    return mapping


def apply_partition_frame(
    source_df: pd.DataFrame,
    source_to_common_df: pd.DataFrame,
    source_tree_df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Apply compiled membership to one complete validation partition."""
    source = _normalise_source_chunk(source_df)
    source["_source_row_id"] = range(len(source))
    mapping = _preferred_mapping_view(source_to_common_df)
    join_columns = ["source_system", "source_flow", "source_product"]
    mapping = mapping.rename(columns={
        "original_source_flow": "source_flow", "original_source_product": "source_product",
    })
    joined = source.merge(mapping, on=join_columns, how="left", indicator=True, suffixes=("", "_mapping"))
    matched = joined[joined["_merge"] == "both"].copy()
    matched["value"] = matched["value"] * pd.to_numeric(matched["component_sign"], errors="coerce").fillna(1.0)
    matched["original_source_flow"] = matched["source_flow"]
    matched["original_source_product"] = matched["source_product"]
    matched["source_parent_flow"] = ""
    matched["source_parent_product"] = ""
    if source_tree_df is not None and not source_tree_df.empty and not matched.empty:
        system = str(source["source_system"].iloc[0]).casefold()
        flow_axis = "sector" if system in {"leap", "ninth"} else "flow"
        product_axis = "fuel" if system in {"leap", "ninth"} else "product"
        flow_parents, _ = build_tree_index(source_tree_df, system, flow_axis)
        product_parents, _ = build_tree_index(source_tree_df, system, product_axis)
        matched["source_parent_flow"] = matched["original_source_flow"].astype(str).map(flow_parents).fillna("")
        matched["source_parent_product"] = matched["original_source_product"].astype(str).map(product_parents).fillna("")
    for column in LINEAGE_COLUMNS:
        if column not in matched:
            matched[column] = ""
    lineage = matched[LINEAGE_COLUMNS].copy() if not matched.empty else pd.DataFrame(columns=LINEAGE_COLUMNS)
    final = (
        lineage.groupby(FINAL_COLUMNS[:-1], dropna=False, as_index=False)["value"].sum()
        if not lineage.empty else pd.DataFrame(columns=FINAL_COLUMNS)
    )
    unmatched = joined[joined["_merge"] == "left_only"][SOURCE_COLUMNS].copy()
    first = source.iloc[0] if not source.empty else pd.Series(dtype=object)
    accounting_records: list[dict[str, Any]] = []
    for (scope, view), group in matched.groupby(["comparison_scope", "mapping_view"], dropna=False, sort=True):
        mapped_source = group.drop_duplicates("_source_row_id")
        mapped_total = float(mapped_source["value"].sum())
        accounting_records.append({
            **{column: first.get(column, "") for column in PARTITION_COLUMNS},
            "comparison_scope": scope, "mapping_view": view,
            "input_total": float(source["value"].sum()), "mapped_total": mapped_total,
            "unmatched_total": float(source["value"].sum() - mapped_total), "excluded_total": 0.0,
            "input_row_count": len(source), "mapped_row_count": mapped_source["_source_row_id"].nunique(),
            "unmatched_row_count": len(source) - mapped_source["_source_row_id"].nunique(),
        })
    if not accounting_records:
        accounting_records.append({
            **{column: first.get(column, "") for column in PARTITION_COLUMNS},
            "comparison_scope": "", "mapping_view": "unmatched",
            "input_total": float(source["value"].sum()), "mapped_total": 0.0,
            "unmatched_total": float(source["value"].sum()), "excluded_total": 0.0,
            "input_row_count": len(source), "mapped_row_count": 0, "unmatched_row_count": len(source),
        })
    accounting = pd.DataFrame(accounting_records, columns=ACCOUNTING_COLUMNS)
    return lineage, final, unmatched, accounting


def _append_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, mode="a", header=not path.exists(), index=False, float_format="%.12g")


def apply_partitioned_common_esto(
    cache_dir: Path,
    source_to_common_path: Path,
    output_dir: Path,
    source_tree_path: Path | None = None,
) -> dict[str, Any]:
    """Process cached partitions and atomically publish CSV outputs."""
    started = time.perf_counter()
    cache_dir, output_dir = Path(cache_dir), Path(output_dir)
    manifest = json.loads((cache_dir / "cache_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "complete":
        raise ValueError("Partition cache is not complete.")
    mapping = pd.read_csv(source_to_common_path, dtype=object)
    source_tree = pd.read_csv(source_tree_path, dtype=object) if source_tree_path is not None else None
    staging = output_dir.with_name(output_dir.name + ".building")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    lineage_dir = staging / "contribution_lineage_parquet"
    lineage_dir.mkdir()
    status_records: list[dict[str, Any]] = []
    try:
        for number, partition in enumerate(manifest["partitions"], start=1):
            key = partition["partition_key"]
            source = pd.concat(
                [pd.read_parquet(path) for path in sorted((cache_dir / "partitions" / key).glob("*.parquet"))],
                ignore_index=True,
            )
            lineage, final, unmatched, accounting = apply_partition_frame(source, mapping, source_tree)
            lineage.to_parquet(lineage_dir / f"{key}.parquet", index=False)
            _append_csv(lineage, staging / "contribution_lineage.csv")
            _append_csv(final, staging / "common_esto_comparison_data.csv")
            _append_csv(unmatched, staging / "unmatched_source_rows.csv")
            _append_csv(accounting, staging / "value_accounting.csv")
            status_records.append({**partition, "status": "complete", "lineage_rows": len(lineage), "final_rows": len(final)})
            print(f"Partition {number}/{len(manifest['partitions'])} complete: {key}")
            del source, lineage, final, unmatched, accounting
            gc.collect()
        status = pd.DataFrame(status_records)
        status.to_csv(staging / "partition_status.csv", index=False)
        # Re-aggregate across partitions only for deterministic ordering. Since
        # each partition key is a complete final group, no cross-partition sum is required.
        final_path = staging / "common_esto_comparison_data.csv"
        final = pd.read_csv(final_path)
        final = final.sort_values(FINAL_COLUMNS[:-1], kind="stable").reset_index(drop=True)
        final.to_csv(final_path, index=False, float_format="%.12g")
        run_manifest = {
            "status": "complete", "partition_count": len(status_records),
            "runtime_seconds": time.perf_counter() - started,
            "source_cache_identity": manifest["source_identity"],
        }
        (staging / "application_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")
        if output_dir.exists():
            shutil.rmtree(output_dir)
        staging.replace(output_dir)
        return run_manifest
    except Exception as error:
        pd.DataFrame([*status_records, {"status": "failed", "error": str(error)}]).to_csv(
            staging / "partition_status.csv", index=False
        )
        raise


# --- Notebook run blocks ---

PREPARE_SOURCE_CACHE = False
APPLY_PARTITIONED_VALUES = False

SOURCE_PATH = REPO_ROOT / "results" / "mapping_relationships" / "raw_leap_results.csv"
CACHE_DIR = REPO_ROOT / "results" / "common_esto" / "partition_cache" / "leap"
STRUCTURAL_MAP_PATH = REPO_ROOT / "results" / "common_esto" / "structural_artifacts" / "source_pair_to_common_row.csv"
OUTPUT_DIR = REPO_ROOT / "results" / "common_esto" / "partitioned_application"

if PREPARE_SOURCE_CACHE:
    CACHE_MANIFEST = prepare_partition_cache(SOURCE_PATH, CACHE_DIR, default_source_system="LEAP")

if APPLY_PARTITIONED_VALUES:
    APPLICATION_MANIFEST = apply_partitioned_common_esto(CACHE_DIR, STRUCTURAL_MAP_PATH, OUTPUT_DIR)

#%%
