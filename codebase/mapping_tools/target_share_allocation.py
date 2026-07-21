#%%
"""Helpers for opt-in target-dataset share allocation."""

#%%
from __future__ import annotations

from typing import Iterable

import pandas as pd


ALLOCATION_METHOD_TARGET_DATASET_SHARE = "target_dataset_share"


def normalize_economy_code(value: object) -> str:
    """Normalize compact and underscore economy codes to the same key."""
    text = "" if pd.isna(value) else str(value).strip()
    if len(text) == 5 and text[:2].isdigit() and text[2:].isalpha():
        return f"{text[:2]}_{text[2:]}"
    return text


def _string_key_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.Series:
    """Build a stable row key from stringified columns."""
    key = pd.Series("", index=df.index, dtype="object")
    for column in columns:
        key = key + "\x1f" + df[column].fillna("").astype(str).str.strip()
    return key


def _equal_share_for_group(row_count: pd.Series) -> pd.Series:
    counts = pd.to_numeric(row_count, errors="coerce").fillna(0.0)
    return 1.0 / counts.where(counts > 0, 1.0)


def apply_target_dataset_allocation(
    merged_df: pd.DataFrame,
    target_values_df: pd.DataFrame,
    allocation_source: str = ALLOCATION_METHOD_TARGET_DATASET_SHARE,
) -> pd.DataFrame:
    """
    Populate ``allocation_share`` for rows using target-dataset share allocation.

    The target basis is the absolute value in the target dataset for each
    candidate target component, matched by normalized economy, year, flow, and
    product. If the target basis sums to zero or is missing for a source group,
    the group falls back to equal shares so source totals are still conserved.
    """
    if merged_df.empty or target_values_df.empty:
        return merged_df

    result = merged_df.copy()
    if "allocation_share" not in result.columns:
        result["allocation_share"] = 1.0
    result["allocation_share"] = result["allocation_share"].astype("object")
    if "allocation_source" in result.columns:
        method_mask = (
            result["allocation_source"].fillna("").astype(str).str.strip().str.casefold()
            == allocation_source.casefold()
        )
    elif "allocation_method" in result.columns:
        method_mask = (
            result["allocation_method"].fillna("").astype(str).str.strip().str.casefold()
            == allocation_source.casefold()
        )
    else:
        return result
    if not method_mask.any():
        return result

    required_source = {"economy", "year", "target_flow", "target_product", "source_flow", "source_product"}
    missing_source = required_source.difference(result.columns)
    if missing_source:
        raise ValueError(f"Cannot allocate by target dataset share; missing columns: {sorted(missing_source)}")
    required_target = {"economy", "year", "esto_flow", "esto_product", "value"}
    missing_target = required_target.difference(target_values_df.columns)
    if missing_target:
        raise ValueError(f"Target values are missing required columns: {sorted(missing_target)}")

    target = target_values_df[list(required_target)].copy()
    target["economy_key"] = target["economy"].map(normalize_economy_code)
    target["year_key"] = target["year"].astype(str).str.strip()
    target["target_flow"] = target["esto_flow"].fillna("").astype(str).str.strip()
    target["target_product"] = target["esto_product"].fillna("").astype(str).str.strip()
    target["target_basis"] = pd.to_numeric(target["value"], errors="coerce").fillna(0.0).abs()
    basis = (
        target.groupby(["economy_key", "year_key", "target_flow", "target_product"], dropna=False)["target_basis"]
        .sum()
        .reset_index()
    )

    rows = result.loc[method_mask].copy()
    rows["_original_index"] = rows.index
    rows["economy_key"] = rows["economy"].map(normalize_economy_code)
    rows["year_key"] = rows["year"].astype(str).str.strip()
    rows["target_flow"] = rows["target_flow"].fillna("").astype(str).str.strip()
    rows["target_product"] = rows["target_product"].fillna("").astype(str).str.strip()
    rows = rows.merge(
        basis,
        on=["economy_key", "year_key", "target_flow", "target_product"],
        how="left",
    )
    rows["target_basis"] = pd.to_numeric(rows["target_basis"], errors="coerce").fillna(0.0)

    source_group_columns = ["economy", "scenario", "year", "source_flow", "source_product"]
    source_group_columns = [column for column in source_group_columns if column in rows.columns]
    rows["_source_group_key"] = _string_key_columns(rows, source_group_columns)
    # Source rollups can produce several rows for the same source pair before
    # the mapping join. Count each target pair once; otherwise the same target
    # basis is included once per derived source row and shares become too small.
    pair_basis = rows[
        ["_source_group_key", "target_flow", "target_product", "target_basis"]
    ].drop_duplicates(
        subset=["_source_group_key", "target_flow", "target_product"]
    )
    pair_totals = pair_basis.groupby("_source_group_key")["target_basis"].agg(
        _target_basis_total="sum",
        _row_count="size",
    ).reset_index()
    rows = rows.drop(columns=["_target_basis_total", "_row_count"], errors="ignore").merge(
        pair_totals,
        on="_source_group_key",
        how="left",
    )
    equal_share = _equal_share_for_group(rows["_row_count"])
    rows["_computed_allocation_share"] = rows["target_basis"] / rows["_target_basis_total"]
    rows.loc[rows["_target_basis_total"].le(0), "_computed_allocation_share"] = equal_share[
        rows["_target_basis_total"].le(0)
    ]

    result.loc[rows["_original_index"], "allocation_share"] = rows["_computed_allocation_share"].to_numpy()
    return result

#%%
