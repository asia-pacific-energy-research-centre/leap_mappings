#%%
"""Validate source parent anchors from exact contribution lineage partitions."""

#%%
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from codebase.mapping_tools.apply_partitioned_common_esto import PARTITION_COLUMNS
from codebase.mapping_tools.structural_resolver import build_tree_index


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

VALIDATION_MODES = {"structural", "slice", "full"}
DETAIL_COLUMNS = [
    "validation_axis", "comparison_scope", "mapping_view", *PARTITION_COLUMNS,
    "other_axis_value", "parent_code", "status", "reason", "parent_value",
    "descendant_lineage_sum", "difference", "abs_error", "expected_children",
    "missing_children", "common_row_ids", "evidence_types",
]


def _axis_names(source_system: str, axis: str) -> tuple[str, str, str]:
    dataset = source_system.casefold()
    tree_axis = axis
    if dataset in {"leap", "ninth"}:
        tree_axis = "sector" if axis == "flow" else "fuel"
    source_column = "source_flow" if axis == "flow" else "source_product"
    lineage_column = "original_source_flow" if axis == "flow" else "original_source_product"
    return tree_axis, source_column, lineage_column


def _children(tree_df: pd.DataFrame, dataset: str, axis: str) -> tuple[dict[str, list[str]], pd.DataFrame]:
    index, issues = build_tree_index(tree_df, dataset, axis)
    result: dict[str, list[str]] = {}
    for child, parent in index.items():
        if parent:
            result.setdefault(parent, []).append(child)
    return {parent: sorted(values) for parent, values in result.items()}, issues


def validate_partition_lineage(
    source_df: pd.DataFrame,
    lineage_df: pd.DataFrame,
    tree_df: pd.DataFrame,
    tolerance: float = 0.01,
) -> pd.DataFrame:
    """Validate both source axes for one complete source partition."""
    if source_df.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)
    source = source_df.copy()
    source["value"] = pd.to_numeric(source["value"], errors="coerce").fillna(0.0)
    lineage = lineage_df.copy()
    if not lineage.empty:
        lineage["value"] = pd.to_numeric(lineage["value"], errors="coerce").fillna(0.0)
    source_system = str(source["source_system"].iloc[0]).upper()
    dataset = source_system.casefold()
    partition_values = {column: source[column].iloc[0] for column in PARTITION_COLUMNS}
    records: list[dict[str, Any]] = []

    for axis in ["flow", "product"]:
        tree_axis, source_axis, lineage_axis = _axis_names(source_system, axis)
        other_source = "source_product" if axis == "flow" else "source_flow"
        other_lineage = "original_source_product" if axis == "flow" else "original_source_flow"
        children, tree_issues = _children(tree_df, dataset, tree_axis)
        if not tree_issues.empty and tree_issues["issue_type"].isin(["cycle", "ambiguous_parent"]).any():
            for issue in tree_issues.to_dict("records"):
                records.append({
                    "validation_axis": axis, "comparison_scope": "", "mapping_view": "",
                    **partition_values, "other_axis_value": "", "parent_code": issue["code"],
                    "status": "failed", "reason": "source_tree_inconsistency", "parent_value": 0.0,
                    "descendant_lineage_sum": 0.0, "difference": 0.0, "abs_error": 0.0,
                    "expected_children": "", "missing_children": issue["related_code"],
                    "common_row_ids": "", "evidence_types": "tree",
                })
            continue
        lineage_by_other = {
            str(key): group
            for key, group in lineage.groupby(other_lineage, dropna=False, sort=False)
        } if not lineage.empty else {}
        for parent, direct_children in children.items():
            parent_rows = source[source[source_axis].astype(str).eq(parent)]
            for other_value, parent_group in parent_rows.groupby(other_source, dropna=False, sort=True):
                parent_value = float(parent_group["value"].sum())
                child_source = source[
                    source[source_axis].astype(str).isin(direct_children)
                    & source[other_source].astype(str).eq(str(other_value))
                ]
                absent = sorted(set(direct_children).difference(child_source[source_axis].astype(str)))
                relevant_lineage = lineage_by_other.get(str(other_value), lineage.iloc[0:0])
                descendant_candidates = relevant_lineage[
                    relevant_lineage[lineage_axis].astype(str).isin(direct_children)
                ] if not relevant_lineage.empty else relevant_lineage
                views = (
                    descendant_candidates[["comparison_scope", "mapping_view"]].drop_duplicates().itertuples(index=False, name=None)
                    if not descendant_candidates.empty else [("", "")]
                )
                for scope, view in views:
                    view_lineage = relevant_lineage[
                        relevant_lineage["comparison_scope"].astype(str).eq(str(scope))
                        & relevant_lineage["mapping_view"].astype(str).eq(str(view))
                    ] if not relevant_lineage.empty else relevant_lineage
                    descendants = view_lineage[view_lineage[lineage_axis].astype(str).isin(direct_children)]
                    mapped_children = set(descendants[lineage_axis].astype(str))
                    missing_mapped = sorted(set(direct_children).difference(mapped_children))
                    common_ids = set(descendants["common_row_id"].dropna().astype(str))
                    contamination = view_lineage[
                        view_lineage["common_row_id"].astype(str).isin(common_ids)
                        & ~view_lineage[lineage_axis].astype(str).isin(direct_children)
                    ]
                    descendant_sum = float(descendants["value"].sum())
                    difference = parent_value - descendant_sum
                    if absent:
                        status, reason = "unanchorable", "rows_absent"
                    elif missing_mapped:
                        status, reason = "failed", "missing_mapped_child"
                    elif not common_ids:
                        status, reason = "unanchorable", "no_anchorable_boundary"
                    elif not contamination.empty:
                        status, reason = "failed", "common_boundary_contamination"
                    elif abs(difference) > tolerance * max(abs(parent_value), 1.0):
                        status, reason = "failed", "difference_outside_tolerance"
                    else:
                        status, reason = "passed", "within_tolerance"
                    records.append({
                        "validation_axis": axis, "comparison_scope": scope, "mapping_view": view,
                        **partition_values, "other_axis_value": other_value, "parent_code": parent,
                        "status": status, "reason": reason, "parent_value": parent_value,
                        "descendant_lineage_sum": descendant_sum, "difference": difference,
                        "abs_error": abs(difference), "expected_children": "|".join(direct_children),
                        "missing_children": "|".join(absent or missing_mapped),
                        "common_row_ids": "|".join(sorted(common_ids)),
                        "evidence_types": "|".join(sorted(set(descendants.get("evidence_type", pd.Series(dtype=str)).astype(str)))),
                    })
    return pd.DataFrame(records, columns=DETAIL_COLUMNS)


def validate_structural_lineage(mapping_df: pd.DataFrame, tree_df: pd.DataFrame) -> pd.DataFrame:
    """Check the value-free lineage template and source trees."""
    required_mapping = {
        "source_system", "original_source_flow", "original_source_product",
        "comparison_scope", "common_row_id", "evidence_type",
    }
    missing = required_mapping.difference(mapping_df.columns)
    records: list[dict[str, Any]] = []
    if missing:
        records.append({"check": "mapping_schema", "status": "failed", "reason": f"missing_columns:{'|'.join(sorted(missing))}"})
    else:
        records.append({"check": "mapping_schema", "status": "passed", "reason": "required_columns_present"})
    for (dataset, axis), _ in tree_df.groupby(["dataset", "axis"], dropna=False):
        _, issues = build_tree_index(tree_df, str(dataset), str(axis))
        records.append({
            "check": f"tree:{dataset}:{axis}", "status": "failed" if not issues.empty else "passed",
            "reason": "|".join(sorted(set(issues["issue_type"]))) if not issues.empty else "explicit_parent_edges_valid",
        })
    return pd.DataFrame(records)


def summarise_validation(detail_df: pd.DataFrame) -> pd.DataFrame:
    """Summarize statuses; an empty validation is never a pass."""
    group_columns = ["validation_axis", "comparison_scope", "source_system"]
    if detail_df.empty:
        return pd.DataFrame([{"validation_axis": "", "comparison_scope": "", "source_system": "", "passed": 0, "failed": 0, "unanchorable": 0, "status": "failed", "reason": "empty_validation"}])
    summary = detail_df.groupby(group_columns + ["status"], dropna=False).size().unstack(fill_value=0)
    for status in ["passed", "failed", "unanchorable"]:
        if status not in summary:
            summary[status] = 0
    summary = summary.reset_index()
    summary["status"] = summary.apply(lambda row: "failed" if row["failed"] else "passed" if row["passed"] else "unanchorable", axis=1)
    summary["reason"] = ""
    return summary[[*group_columns, "passed", "failed", "unanchorable", "status", "reason"]]


def run_lineage_anchor_validation(
    mode: str,
    cache_dir: Path,
    lineage_dir: Path,
    tree_path: Path,
    mapping_path: Path,
    output_dir: Path,
    economies: set[str] | None = None,
    years: set[int] | None = None,
    tolerance: float = 0.01,
    include_pass_detail: bool = False,
    pass_sample_size: int = 100,
) -> dict[str, Any]:
    """Run structural, slice, or full validation with bounded detail output."""
    if mode not in VALIDATION_MODES:
        raise ValueError(f"Unknown validation mode {mode!r}; expected {sorted(VALIDATION_MODES)}")
    tree = pd.read_csv(tree_path, dtype=object)
    mapping = pd.read_csv(mapping_path, dtype=object)
    output_dir = Path(output_dir)
    staging = output_dir.with_name(output_dir.name + ".building")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    if mode == "structural":
        structural = validate_structural_lineage(mapping, tree)
        structural.to_csv(staging / "validation_summary.csv", index=False)
        pd.DataFrame(columns=DETAIL_COLUMNS).to_csv(staging / "validation_failures.csv", index=False)
        pd.DataFrame(columns=DETAIL_COLUMNS).to_csv(staging / "unmatched_unanchorable_boundaries.csv", index=False)
        pd.DataFrame([{"mode": mode, "status": "complete"}]).to_csv(staging / "partition_status_and_value_accounting.csv", index=False)
        manifest = {"mode": mode, "status": "complete", "checks": len(structural)}
    else:
        cache_manifest = json.loads((Path(cache_dir) / "cache_manifest.json").read_text(encoding="utf-8"))
        details: list[pd.DataFrame] = []
        statuses: list[dict[str, Any]] = []
        for partition in cache_manifest["partitions"]:
            if economies is not None and str(partition["economy"]) not in economies:
                continue
            if years is not None and int(partition["year"]) not in years:
                continue
            key = partition["partition_key"]
            source = pd.concat([pd.read_parquet(path) for path in sorted((Path(cache_dir) / "partitions" / key).glob("*.parquet"))], ignore_index=True)
            lineage_path = Path(lineage_dir) / f"{key}.parquet"
            lineage = pd.read_parquet(lineage_path) if lineage_path.exists() else pd.DataFrame()
            detail = validate_partition_lineage(source, lineage, tree, tolerance)
            details.append(detail)
            statuses.append({**partition, "status": "complete", "check_count": len(detail), "source_total": pd.to_numeric(source["value"], errors="coerce").fillna(0).sum(), "lineage_total": pd.to_numeric(lineage.get("value", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()})
        all_detail = pd.concat(details, ignore_index=True) if details else pd.DataFrame(columns=DETAIL_COLUMNS)
        summary = summarise_validation(all_detail)
        failures = all_detail[all_detail["status"] == "failed"]
        unanchorable = all_detail[all_detail["status"] == "unanchorable"]
        passes = all_detail[all_detail["status"] == "passed"]
        summary.to_csv(staging / "validation_summary.csv", index=False)
        failures.to_csv(staging / "validation_failures.csv", index=False)
        unanchorable.to_csv(staging / "unmatched_unanchorable_boundaries.csv", index=False)
        pd.DataFrame(statuses).to_csv(staging / "partition_status_and_value_accounting.csv", index=False)
        (passes if include_pass_detail else passes.sort_values(DETAIL_COLUMNS[:7]).head(pass_sample_size)).to_csv(staging / "validation_pass_sample.csv", index=False)
        manifest = {"mode": mode, "status": "complete", "partition_count": len(statuses), "check_count": len(all_detail), "failed": len(failures), "unanchorable": len(unanchorable), "passed": len(passes)}
    (staging / "validation_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.move(str(staging), str(output_dir))
    return manifest


# --- Notebook run block ---

RUN_VALIDATION = False
VALIDATION_MODE = "slice"

if RUN_VALIDATION:
    VALIDATION_RESULT = run_lineage_anchor_validation(
        mode=VALIDATION_MODE,
        cache_dir=REPO_ROOT / "results/common_esto/partition_cache/leap",
        lineage_dir=REPO_ROOT / "results/common_esto/partitioned_application/contribution_lineage_parquet",
        tree_path=REPO_ROOT / "results/tree_structure/all_dataset_trees.csv",
        mapping_path=REPO_ROOT / "results/common_esto/structural_artifacts/source_pair_to_common_row.csv",
        output_dir=REPO_ROOT / "results/common_esto/lineage_validation",
    )

#%%
