#%%
"""Helpers for opt-in target-dataset share allocation."""

#%%
from __future__ import annotations

from pathlib import Path
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
    try:
        result["allocation_share"] = pd.to_numeric(
            result["allocation_share"],
            errors="raise",
        )
    except (TypeError, ValueError):
        # Mixed allocated and intentionally blank rows must retain object dtype.
        pass
    return result


def target_dataset_share_target_flows(relationships_df: pd.DataFrame) -> set[str]:
    """Return every ``target_flow`` that needs target-dataset-share allocation.

    A source pair needs it when every candidate relationship row for that
    pair has a blank ``allocation_share`` and there is more than one distinct
    target. Mirrors the grouping in :func:`apply_target_dataset_allocation`;
    kept side-effect free so callers can use the result to fetch exactly the
    ESTO basis rows required, without guessing.
    """
    required = {"source_flow", "source_product", "target_flow", "target_product", "allocation_share"}
    if not required.issubset(relationships_df.columns):
        return set()

    rows = relationships_df.copy()
    source_group_columns = ["source_flow", "source_product"]
    blank_share = rows["allocation_share"].fillna("").astype(str).str.strip().eq("")
    rows["_target_pair"] = (
        rows["target_flow"].fillna("").astype(str).str.strip()
        + "\x1f"
        + rows["target_product"].fillna("").astype(str).str.strip()
    )
    target_count = rows.groupby(source_group_columns, dropna=False)["_target_pair"].transform("nunique")
    all_shares_blank = blank_share.groupby(
        [rows[column] for column in source_group_columns], dropna=False
    ).transform("all")
    needs_share = all_shares_blank & target_count.gt(1)
    flows = rows.loc[needs_share, "target_flow"].fillna("").astype(str).str.strip()
    return set(flows) - {""}


def load_target_dataset_share_basis_rows(
    esto_csv_path: Path,
    needed_flows: set[str],
) -> pd.DataFrame:
    """
    Load ESTO's own reported subtotal rows for exactly the flow labels a
    target-dataset-share allocation needs as its basis.

    ``esto_results_exact_rows.csv`` (the usual ``target_values_df`` source)
    deliberately excludes every ``is_subtotal=True`` row, so Common ESTO
    structure-building never double-counts a subtotal against its own
    re-derived children. But a source-to-ESTO relationship can target an
    aggregate flow (e.g. ``"14.03 Manufacturing"``) that only the source
    dataset resolves at that coarse a granularity -- ESTO's own basis for
    splitting the source value across that aggregate's children genuinely
    exists, just one level lower, as ESTO's own reported subtotal, which the
    exact-rows file strips. This reads it back in from the raw ESTO source,
    scoped to only the flow labels actually needed and only their
    ``is_subtotal=True`` rows, so it never touches the shared exact-rows file
    or risks double-counting a leaf ESTO row already present there.
    """
    empty = pd.DataFrame(columns=["economy", "esto_flow", "esto_product", "year", "value"])
    if not needed_flows or not esto_csv_path.exists():
        return empty

    df = pd.read_csv(esto_csv_path, dtype=object)
    is_subtotal = df["is_subtotal"].astype(str).str.strip().str.lower().eq("true")
    is_needed_flow = df["flows"].astype(str).str.strip().isin(needed_flows)
    df = df[is_subtotal & is_needed_flow].copy()
    if df.empty:
        return empty

    year_cols = [column for column in df.columns if str(column).isdigit()]
    for column in year_cols:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    long_df = df[["economy", "flows", "products", *year_cols]].melt(
        id_vars=["economy", "flows", "products"],
        value_vars=year_cols,
        var_name="year",
        value_name="value",
    ).dropna(subset=["value"])
    long_df = long_df.rename(columns={"flows": "esto_flow", "products": "esto_product"})
    long_df["year"] = long_df["year"].astype(int).astype(str)
    return long_df[["economy", "esto_flow", "esto_product", "year", "value"]]

#%%
