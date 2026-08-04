"""Extract ESTO exact rows for the Common ESTO comparison.

Split out of ``run_mapping_pipeline`` so the portable mapping-chain worker can
re-extract ESTO rows from a user-supplied base table without importing the
pipeline runner. Importing that runner pulls in the Stage 1 and Stage 2
builders, the separate-axis workbook workflows and Pillow - 24 extra modules to
reach one function, all of which PyInstaller would then bundle into the worker.

These three pieces depend on nothing else in the pipeline runner: two helpers
that call nothing in-module, and six constants. ``run_mapping_pipeline`` imports
them back from here, so it keeps its existing public surface.
"""

from __future__ import annotations

import gc
from pathlib import Path

import pandas as pd


# Aggregate comparisons that require the exact ESTO parent alongside the
# ordinary non-subtotal frontier. Other dashboard totals are currently built
# from their reviewed additive frontiers.
ESTO_REFERENCE_ROLLUP_LABELS = {"Total transformation - no transfers"}


# Some ESTO parent flows contain the published observations even though they
# are structurally marked as subtotals. In particular, 08 Transfers can be
# non-zero while its 08.01-08.99 detail rows are zero or incomplete, so the
# parent must survive the ordinary leaf-only extraction for Common ESTO.
ESTO_RETAINED_SUBTOTAL_FLOW_LABELS = {"08 Transfers"}


def configured_rollup_reference_pairs(
    relationships_df: pd.DataFrame,
    leap_rollup_rules_df: pd.DataFrame,
    retained_rollup_labels: set[str],
) -> set[tuple[str, str]]:
    """Return exact ESTO pairs explicitly targeted by configured LEAP rollups."""
    if relationships_df.empty or leap_rollup_rules_df.empty:
        return set()
    included_rules = leap_rollup_rules_df[
        leap_rollup_rules_df["include"].astype(str).str.strip().str.lower().isin({"true", "1", "yes"})
    ]
    rolled_flows = {
        str(value).strip()
        for value in included_rules["rolled_leap_sector_name_full_path"]
        if str(value).strip() in retained_rollup_labels
    }
    if not rolled_flows:
        return set()
    include_mask = relationships_df["include_in_use_case"].astype(str).str.strip().str.lower().isin(
        {"true", "1", "yes"}
    )
    reference_rows = relationships_df[
        include_mask
        & (relationships_df["source_system"].astype(str) == "LEAP")
        & (relationships_df["target_system"].astype(str) == "ESTO")
        & ~relationships_df["is_rollup_derived"].astype(str).str.strip().str.lower().isin({"true", "1", "yes"})
        & relationships_df["source_flow"].astype(str).isin(rolled_flows)
    ]
    return {
        (str(flow).strip(), str(product).strip())
        for flow, product in reference_rows[["target_flow", "target_product"]].itertuples(index=False, name=None)
        if str(flow).strip() and str(product).strip()
    }


def select_esto_comparison_rows(
    esto_df: pd.DataFrame,
    rollup_reference_pairs: set[tuple[str, str]],
    retained_flow_labels: set[str] | None = None,
) -> pd.DataFrame:
    """Keep ESTO leaves plus exact parent pairs required by configured rollups.

    rollup_reference_pairs: retain specific (flow, product) subtotal pairs
        needed by LEAP rollup comparisons (e.g. 'Total transformation - no transfers').
    """
    leaf_mask = esto_df["is_subtotal"].astype(str).str.strip().str.lower() == "false"
    retained_flow_labels = retained_flow_labels or set()
    if not rollup_reference_pairs and not retained_flow_labels:
        return esto_df[leaf_mask].copy()
    pair_mask = pd.Series(
        [
            (str(flow).strip(), str(product).strip()) in rollup_reference_pairs
            for flow, product in esto_df[["flows", "products"]].itertuples(index=False, name=None)
        ],
        index=esto_df.index,
    )
    flow_mask = esto_df["flows"].astype(str).str.strip().isin(retained_flow_labels)
    return esto_df[leaf_mask | pair_mask | flow_mask].copy()


def run_esto_exact_rows_for_path(
    data_path: Path,
    output_path: Path,
    source_system: str,
    *,
    relationships_path: Path,
    mapping_workbook_path: Path,
    qa_path: Path | None = None,
    repo_root: Path | None = None,
) -> None:
    """Extract exact source rows for the Common ESTO comparison.

    The four paths were module-level constants in the pipeline runner, derived
    from its repository root. They are parameters here because the portable
    worker has no repository: it passes the artifacts bundled with the release,
    and re-derives the exact rows from whichever ESTO table the user supplied.
    """
    print("\n" + "-" * 40)
    print(f"  {source_system} exact rows")
    if not data_path.exists():
        print(f"  WARNING: {data_path.name} not found.")
        return

    df = pd.read_csv(data_path, dtype=object)
    year_cols = [c for c in df.columns if str(c).isdigit()]
    for col in year_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    relationships_df = pd.read_csv(relationships_path, dtype=object).fillna("")
    if "is_rollup_derived" not in relationships_df.columns:
        relationships_df["is_rollup_derived"] = "False"
    leap_rollup_rules_df = pd.read_excel(
        mapping_workbook_path,
        sheet_name="leap_rollup_rules",
        dtype=object,
    ).fillna("")
    reference_pairs = configured_rollup_reference_pairs(
        relationships_df=relationships_df,
        leap_rollup_rules_df=leap_rollup_rules_df,
        retained_rollup_labels=ESTO_REFERENCE_ROLLUP_LABELS,
    )
    del relationships_df, leap_rollup_rules_df

    # Derived non-expanding subtotal rows are built from the full ESTO frame
    # (contributors may be real parent flows such as "09.06 Gas processing
    # plants" that the leaf filter below removes).
    from codebase.mapping_tools.non_expanding_rollups import (
        build_esto_non_expanding_subtotal_rows,
        guard_esto_exact_rows_source_identity,
        load_non_expanding_rollup_rules,
        split_rollup_rules,
    )
    esto_boundary_rules = load_non_expanding_rollup_rules(mapping_workbook_path).get(
        "esto_rollup_rules", pd.DataFrame()
    )
    esto_rollup_rules_raw = pd.read_excel(mapping_workbook_path, sheet_name="esto_rollup_rules", dtype=object).fillna("")
    expanding_esto_rules, _, detached_esto_rules = split_rollup_rules(esto_rollup_rules_raw)
    detached_esto_flows = {
        str(value).strip()
        for value in detached_esto_rules.get("input_esto_flow", pd.Series(dtype=object))
        if str(value).strip()
    }
    non_expanding_rows_df = build_esto_non_expanding_subtotal_rows(
        df,
        esto_boundary_rules,
        year_columns=year_cols,
        source_system=source_system,
    )
    # EXPANDING-mode rolled labels (e.g. "09.01-09.02 Power sector", created
    # because NINTH/LEAP can't distinguish 09.01 Main activity producer from
    # 09.02 Autoproducers) never got an ESTO-side value anywhere in the
    # pipeline: build_esto_non_expanding_subtotal_rows only ever ran against
    # NON_EXPANDING/DETACHED rules. Confirmed via real data that all 4
    # EXPANDING esto_rollup_rules labels had zero ESTO rows in
    # common_esto_comparison_data.csv, which is why ESTO's own recursive
    # validator ("09 Total transformation sector" vs. its Common ESTO
    # children) fails for these labels -- the merged child's ESTO
    # contribution was silently absent, not zero. The derivation logic is
    # identical (sum the declared contributor flows/products), so reuse the
    # same function against the EXPANDING split instead of writing a parallel
    # implementation. The 09.01/09.02 contributor flows themselves remain in
    # the raw/leaf ESTO rows below unchanged -- this only adds the merged
    # label as an additional derived row, since the EXPANDING reattribution
    # is additive, not a replacement (see bcb7caf/9b75628).
    expanding_rows_df = build_esto_non_expanding_subtotal_rows(
        df,
        expanding_esto_rules,
        year_columns=year_cols,
        source_system=source_system,
    )
    non_expanding_rows_df = pd.concat(
        [non_expanding_rows_df, expanding_rows_df], ignore_index=True
    )

    retained_esto_flows = detached_esto_flows | ESTO_RETAINED_SUBTOTAL_FLOW_LABELS
    df_leaf = select_esto_comparison_rows(df, reference_pairs, retained_esto_flows)
    del df
    gc.collect()

    id_cols = ["economy", "flows", "products"]
    long_df = df_leaf[id_cols + year_cols].melt(
        id_vars=id_cols,
        value_vars=year_cols,
        var_name="year",
        value_name="value",
    ).dropna(subset=["value"])

    long_df = long_df.rename(columns={"flows": "esto_flow", "products": "esto_product"})
    long_df["source_system"] = source_system
    long_df["scenario"] = "historical"
    long_df["year"] = long_df["year"].astype(int)

    exact_row_count = len(long_df)
    if not non_expanding_rows_df.empty:
        long_df["non_expanding_rollup_id"] = ""
        long_df = pd.concat([long_df, non_expanding_rows_df], ignore_index=True)

    # Regression guard: derived rollup rows are built here, not read from the
    # source CSV, so a hard-coded identity would land ESTO rows inside the
    # Extended artifact and double every affected flow downstream.
    # The identity guard always writes its QA table, so it needs a real path.
    # A caller with no configured location (the portable worker) gets one beside
    # the output rather than a skipped check: this guard is what stops ESTO rows
    # landing inside the Extended artifact and double-counting downstream, so it
    # must run in the worker exactly as it does in the pipeline.
    resolved_qa_path = (
        Path(qa_path)
        if qa_path is not None
        else output_path.parent / "qa_esto_exact_rows_source_identity.csv"
    )
    identity_summary = guard_esto_exact_rows_source_identity(
        long_df,
        output_path,
        source_system,
        qa_path=resolved_qa_path,
        repo_root=repo_root,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    long_df.to_csv(output_path, index=False)
    # A repo-relative label is friendlier in a pipeline run, but the portable
    # mapping-chain worker writes to a scratch directory outside the repository,
    # where relative_to raises. Fall back to the absolute path rather than
    # failing after the work is already done.
    display_output = output_path
    if repo_root is not None:
        try:
            display_output = output_path.relative_to(repo_root)
        except ValueError:
            display_output = output_path
    print(f"  {source_system} exact rows: {exact_row_count:,} -> {display_output}")
    for row in identity_summary.itertuples():
        print(
            f"  source_system={row.source_system}: {row.row_count:,} rows "
            f"({row.derived_rollup_row_count:,} derived rollup)"
        )
    print(f"  Derived non-expanding subtotal rows appended: {len(non_expanding_rows_df):,}")
    print(f"  Configured rollup reference pairs retained: {len(reference_pairs):,}")
