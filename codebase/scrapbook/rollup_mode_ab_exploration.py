#%%
"""Compare ESTO rollup-mode effects without loading the ESTO Extended dataset.

This notebook-safe exploration reuses the current Common ESTO output, filters it
to ESTO 09-transformation rows, and runs the recursive validator against two
copied mapping workbooks. It never edits the canonical workbook or runs ESTO
Extended.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


#%%
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.chdir(REPO_ROOT)

from codebase.mapping_tools.build_dataset_tree_structure import (  # noqa: E402
    _validate_common_esto_axis_recursive_sums,
    build_common_esto_tree,
    build_esto_tree,
)
from codebase.mapping_tools.common_esto_validation_orchestration import (  # noqa: E402
    _detached_rollup_parents,
    _excluded_rollup_parents,
)


#%%
COMMON_ROWS_PATH = REPO_ROOT / "results" / "common_esto" / "common_esto_comparison_data.csv"
CANONICAL_WORKBOOK_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
VARIANT_WORKBOOKS = {
    "baseline": CANONICAL_WORKBOOK_PATH,
    "09_08_non_expanding": REPO_ROOT / "results" / "rollup_mode_ab_exploration" / "outlook_mappings_master_09_08_non_expanding.xlsx",
    "09_06_detached": REPO_ROOT / "results" / "rollup_mode_ab_exploration" / "outlook_mappings_master_09_06_detached.xlsx",
}
OUTPUT_ROOT = REPO_ROOT / "results" / "rollup_mode_ab_exploration"
CHUNK_SIZE = 100_000


#%%
def build_esto_transformation_slice(
    comparison_data_path: Path,
    output_path: Path,
) -> pd.DataFrame:
    """Write 09-transformation rows while excluding ESTO Extended entirely."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    summary_rows: list[dict[str, object]] = []
    wrote_header = False
    for chunk in pd.read_csv(comparison_data_path, chunksize=CHUNK_SIZE, dtype=object):
        source_mask = chunk["source_system"].fillna("").ne("ESTO_EXTENDED")
        scope_mask = ~chunk["comparison_scope"].fillna("").astype(str).str.contains(
            "esto_extended", case=False, regex=False
        )
        flow_mask = chunk["common_flow_code"].fillna("").astype(str).str.startswith("09")
        selected = chunk[source_mask & scope_mask & flow_mask].copy()
        if selected.empty:
            continue
        selected.to_csv(output_path, mode="a", index=False, header=not wrote_header)
        wrote_header = True
        summary_rows.append({
            "rows": len(selected),
            "economies": selected["economy"].nunique(),
            "years": selected["year"].nunique(),
        })

    if not wrote_header:
        raise ValueError("No ESTO 09-transformation rows were found in Common ESTO comparison data.")

    return pd.DataFrame(summary_rows)


def build_esto_only_validation_tree(workbook_path: Path) -> pd.DataFrame:
    """Build the ESTO/Common ESTO 09-flow hierarchy used by the validator."""
    common_tree = build_common_esto_tree(COMMON_ROWS_PATH, workbook_path)
    common_tree = common_tree[
        (common_tree["axis"] == "flow")
        & common_tree["code"].astype(str).str.startswith("09")
    ].copy()
    esto_tree = build_esto_tree(REPO_ROOT / "data" / "00APEC_2025_low_with_subtotals.csv")
    esto_tree = esto_tree[
        (esto_tree["axis"] == "flow")
        & esto_tree["code"].astype(str).str.startswith(("09", "10.01"))
    ].copy()
    return pd.concat([esto_tree, common_tree], ignore_index=True)


def run_variant(
    variant_name: str,
    workbook_path: Path,
    comparison_slice_path: Path,
    output_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the direct flow validator without source-frontier or Extended inputs."""
    variant_dir = output_root / variant_name
    variant_dir.mkdir(parents=True, exist_ok=True)
    tree_df = build_esto_only_validation_tree(workbook_path)
    detail_df = _validate_common_esto_axis_recursive_sums(
        tree_df=tree_df,
        comparison_data_path=comparison_slice_path,
        axis="flow",
        record_all_checks=True,
        exclude_parents=_excluded_rollup_parents(workbook_path),
        detached_labels=_detached_rollup_parents(workbook_path),
    )
    detail_df["variant"] = variant_name
    summary_df = (
        detail_df.groupby(["source_system", "status"], dropna=False)
        .size()
        .rename("rows")
        .reset_index()
    )
    detail_df.to_csv(variant_dir / "validation_detail_returned.csv", index=False)
    summary_df.to_csv(variant_dir / "validation_summary_returned.csv", index=False)
    return detail_df, summary_df


def build_variant_summary(
    variant_name: str,
    detail_df: pd.DataFrame,
    summary_df: pd.DataFrame,
) -> dict[str, object]:
    """Create a compact comparable summary for one A/B run."""
    flow_rows = detail_df.copy()
    failed = flow_rows[flow_rows.get("status", "").eq("failed")].copy()
    return {
        "variant": variant_name,
        "flow_checks": len(flow_rows),
        "flow_failures": len(failed),
        "09_total_failures": int(
            failed.get("parent_code", pd.Series(dtype=object))
            .eq("09 Total transformation sector").sum()
        ),
        "09_06_related_failures": int(
            failed.get("parent_code", pd.Series(dtype=object))
            .astype(str).str.startswith("09.06").sum()
        ),
        "09_08_related_failures": int(
            failed.get("parent_code", pd.Series(dtype=object))
            .astype(str).str.startswith("09.08").sum()
        ),
        "summary_rows": len(summary_df),
    }


def write_variant_delta_reports(
    details_by_variant: dict[str, pd.DataFrame],
    output_root: Path,
) -> None:
    """Write the exact validation rows changed from the baseline per variant."""
    key_columns = [
        "validation_axis",
        "comparison_scope",
        "source_system",
        "economy",
        "scenario",
        "other_axis_value",
        "parent_code",
        "year",
    ]
    outcome_columns = [
        "child_count",
        "frontier_row_count",
        "missing_expected_children",
        "parent_value",
        "children_sum",
        "difference",
        "abs_error",
        "proportional_error",
        "status",
        "reason",
    ]
    baseline = details_by_variant["baseline"][key_columns + outcome_columns].copy()

    for variant_name, variant_detail in details_by_variant.items():
        if variant_name == "baseline":
            continue
        variant = variant_detail[key_columns + outcome_columns].copy()
        merged = baseline.merge(
            variant,
            on=key_columns,
            how="outer",
            suffixes=("_baseline", "_variant"),
            indicator=True,
        )
        changed = merged[
            (merged["_merge"] != "both")
            | (merged["status_baseline"] != merged["status_variant"])
            | (merged["children_sum_baseline"] != merged["children_sum_variant"])
            | (merged["difference_baseline"] != merged["difference_variant"])
        ].copy()
        changed.insert(0, "variant", variant_name)
        changed.to_csv(output_root / f"delta_from_baseline_{variant_name}.csv", index=False)

        summary = (
            changed.groupby(
                ["comparison_scope", "source_system", "parent_code", "_merge", "status_baseline", "status_variant"],
                dropna=False,
            )
            .size()
            .rename("changed_rows")
            .reset_index()
            .sort_values("changed_rows", ascending=False)
        )
        summary.insert(0, "variant", variant_name)
        summary.to_csv(
            output_root / f"delta_summary_from_baseline_{variant_name}.csv",
            index=False,
        )


def run_rollup_mode_ab_exploration() -> Path:
    """Run the two one-change mode tests and save comparison-ready outputs."""
    missing = [path for path in [COMMON_ROWS_PATH, *VARIANT_WORKBOOKS.values()] if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required exploration inputs: {missing}")

    run_dir = OUTPUT_ROOT / f"run_{datetime.now():%Y%m%d_%H%M%S}"
    run_dir.mkdir(parents=True, exist_ok=True)
    comparison_slice_path = run_dir / "esto_09_transformation_comparison_data.csv"
    slice_summary = build_esto_transformation_slice(COMMON_ROWS_PATH, comparison_slice_path)
    slice_summary.to_csv(run_dir / "comparison_slice_summary.csv", index=False)

    summaries: list[dict[str, object]] = []
    details_by_variant: dict[str, pd.DataFrame] = {}
    for variant_name, workbook_path in VARIANT_WORKBOOKS.items():
        detail_df, summary_df = run_variant(
            variant_name=variant_name,
            workbook_path=workbook_path,
            comparison_slice_path=comparison_slice_path,
            output_root=run_dir,
        )
        details_by_variant[variant_name] = detail_df
        summaries.append(build_variant_summary(variant_name, detail_df, summary_df))

    pd.DataFrame(summaries).to_csv(run_dir / "ab_summary.csv", index=False)
    write_variant_delta_reports(details_by_variant, run_dir)
    print(f"A/B exploration complete: {run_dir}")
    return run_dir


#%%
RUN_EXPLORATION = True

if __name__ == "__main__" and RUN_EXPLORATION:
    RUN_DIRECTORY = run_rollup_mode_ab_exploration()

#%%
