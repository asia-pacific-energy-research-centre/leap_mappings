"""Run Common ESTO hierarchy validation with current-run status metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from codebase.mapping_tools.build_dataset_tree_structure import (
    COMMON_ESTO_VALIDATION_COLS,
    LEAP_VAR_BASE_YEAR,
    _common_esto_validation_children_map,
    _validate_common_esto_axis_recursive_sums,
)


VALIDATION_SUMMARY_COLUMNS = [
    "run_id",
    "run_timestamp_utc",
    "validation_name",
    "validation_axis",
    "source_system",
    "status",
    "checks_performed",
    "eligible_parent_count",
    "mismatch_count",
    "reason",
    "input_path",
    "input_mtime_ns",
    "input_mtime_utc",
    "input_size_bytes",
    "output_path",
]


_AGGREGATION_ID_COLS = [
    "validation_axis",
    "comparison_scope",
    "source_system",
    "scenario",
    "other_axis_value",
    "parent_code",
    "child_count",
]


def _aggregate_validation(detail_df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """Sum parent_value and children_sum over group_cols, then recompute derived columns."""
    if detail_df.empty:
        return pd.DataFrame()
    grp = detail_df.groupby(group_cols, dropna=False)
    agg = grp[["parent_value", "children_sum"]].sum().reset_index()
    agg["economy_count"] = grp["economy"].nunique().values
    agg["difference"] = agg["parent_value"] - agg["children_sum"]
    agg["abs_error"] = agg["difference"].abs()
    agg["proportional_error"] = agg.apply(
        lambda r: r["difference"] / r["parent_value"] if abs(r["parent_value"]) > 0 else None,
        axis=1,
    )
    return agg


def _empty_validation_detail() -> pd.DataFrame:
    return pd.DataFrame(columns=COMMON_ESTO_VALIDATION_COLS)


def _input_provenance(path: Path) -> dict[str, object]:
    """Return stable file provenance fields used by validation status records."""
    stat = path.stat()
    return {
        "input_path": str(path.resolve()),
        "input_mtime_ns": stat.st_mtime_ns,
        "input_mtime_utc": datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat(),
        "input_size_bytes": stat.st_size,
    }


def _count_eligible_checks(
    tree_df: pd.DataFrame,
    comparison_data_path: Path,
    axis: str,
    leap_var_base_year: int,
) -> pd.DataFrame:
    """Count data groups eligible for the existing hierarchy validator."""
    data = pd.read_csv(comparison_data_path, dtype=object)
    data["year"] = pd.to_numeric(data["year"], errors="coerce")
    data = data[data["year"] > int(leap_var_base_year)].copy()
    axis_col = "common_product_label" if axis == "product" else "common_flow_label"
    other_axis_col = "common_flow_label" if axis == "product" else "common_product_label"
    group_cols = [
        "comparison_scope",
        "source_system",
        "economy",
        "scenario",
        other_axis_col,
        "year",
    ]
    checks_by_source: dict[str, int] = {}
    parents_by_source: dict[str, set[str]] = {}

    for parent_code, children in _common_esto_validation_children_map(tree_df, axis).items():
        parent_rows = data[data[axis_col] == parent_code]
        children_rows = data[data[axis_col].isin(children)]
        if parent_rows.empty or children_rows.empty:
            continue
        parent_groups = parent_rows.groupby(group_cols, dropna=False).size().index
        child_groups = children_rows.groupby(group_cols, dropna=False).size().index
        for group_key in parent_groups.intersection(child_groups):
            source_system = str(group_key[1])
            checks_by_source[source_system] = checks_by_source.get(source_system, 0) + 1
            parents_by_source.setdefault(source_system, set()).add(parent_code)

    return pd.DataFrame([
        {
            "source_system": source_system,
            "checks_performed": checks,
            "eligible_parent_count": len(parents_by_source[source_system]),
        }
        for source_system, checks in sorted(checks_by_source.items())
    ])


def run_common_esto_validation_workflow(
    tree_df: pd.DataFrame,
    comparison_data_path: Path,
    output_dir: Path,
    run_id: str,
    run_timestamp_utc: str,
    expected_input_mtime_ns: int | None = None,
    skip_reason: str = "",
    tolerance: float = 0.01,
    source_inconsistencies: dict[
        tuple[str, str, str, str, str, str, str], dict[str, str]
    ] | None = None,
    leap_var_base_year: int = LEAP_VAR_BASE_YEAR,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run Common ESTO validations and always replace current-run outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_path = output_dir / "common_esto_validation.csv"
    summary_path = output_dir / "common_esto_validation_summary.csv"
    detail_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, object]] = []
    provenance: dict[str, object] = {
        "input_path": str(comparison_data_path.resolve()),
        "input_mtime_ns": "",
        "input_mtime_utc": "",
        "input_size_bytes": "",
    }
    source_systems = ["ALL"]
    effective_skip_reason = skip_reason
    input_error_reason = ""

    if not effective_skip_reason and not comparison_data_path.exists():
        effective_skip_reason = "Stage 3 comparison input is missing."
    if not effective_skip_reason:
        provenance = _input_provenance(comparison_data_path)
        if (
            expected_input_mtime_ns is not None
            and provenance["input_mtime_ns"] != expected_input_mtime_ns
        ):
            effective_skip_reason = (
                "Stage 3 comparison input modification time does not match the current run."
            )
        else:
            try:
                source_systems = sorted(
                    pd.read_csv(comparison_data_path, usecols=["source_system"])[
                        "source_system"
                    ].dropna().astype(str).unique().tolist()
                ) or ["ALL"]
            except Exception as exc:
                input_error_reason = f"{type(exc).__name__}: {exc}"

    for axis in ["product", "flow"]:
        validation_name = f"common_esto_{axis}_hierarchy"
        if input_error_reason:
            summary_rows.append({
                "validation_name": validation_name,
                "validation_axis": axis,
                "source_system": "ALL",
                "status": "error",
                "checks_performed": 0,
                "eligible_parent_count": 0,
                "mismatch_count": 0,
                "reason": input_error_reason,
            })
            continue
        if effective_skip_reason:
            for source_system in source_systems:
                summary_rows.append({
                    "validation_name": validation_name,
                    "validation_axis": axis,
                    "source_system": source_system,
                    "status": "skipped",
                    "checks_performed": 0,
                    "eligible_parent_count": 0,
                    "mismatch_count": 0,
                    "reason": effective_skip_reason,
                })
            continue

        try:
            axis_detail = _validate_common_esto_axis_recursive_sums(
                tree_df=tree_df,
                comparison_data_path=comparison_data_path,
                axis=axis,
                tolerance=tolerance,
                source_inconsistencies=source_inconsistencies,
                leap_var_base_year=leap_var_base_year,
                record_all_checks=True,
            )
            metrics = _count_eligible_checks(
                tree_df,
                comparison_data_path,
                axis,
                leap_var_base_year,
            )
            detail_frames.append(axis_detail)
            mismatch_counts = (
                axis_detail[axis_detail["status"] == "failed"].groupby("source_system").size().to_dict()
                if not axis_detail.empty
                else {}
            )
            metrics_by_source = (
                metrics.set_index("source_system").to_dict("index")
                if not metrics.empty
                else {}
            )
            for source_system in source_systems:
                metric = metrics_by_source.get(source_system, {})
                checks = int(metric.get("checks_performed", 0))
                eligible_parents = int(metric.get("eligible_parent_count", 0))
                mismatches = int(mismatch_counts.get(source_system, 0))
                if checks == 0 or eligible_parents == 0:
                    status = "skipped"
                    reason = "No eligible parent/child checks were found."
                elif mismatches:
                    status = "failed"
                    reason = "One or more parent/child checks mismatched."
                else:
                    status = "passed"
                    reason = "All eligible parent/child checks matched."
                summary_rows.append({
                    "validation_name": validation_name,
                    "validation_axis": axis,
                    "source_system": source_system,
                    "status": status,
                    "checks_performed": checks,
                    "eligible_parent_count": eligible_parents,
                    "mismatch_count": mismatches,
                    "reason": reason,
                })
        except Exception as exc:
            for source_system in source_systems:
                summary_rows.append({
                    "validation_name": validation_name,
                    "validation_axis": axis,
                    "source_system": source_system,
                    "status": "error",
                    "checks_performed": 0,
                    "eligible_parent_count": 0,
                    "mismatch_count": 0,
                    "reason": f"{type(exc).__name__}: {exc}",
                })

    detail_df = (
        pd.concat(detail_frames, ignore_index=True)
        if detail_frames
        else _empty_validation_detail()
    )
    detail_df.insert(0, "run_id", run_id)
    detail_df.to_csv(detail_path, index=False)

    by_year_path = output_dir / "common_esto_validation_by_year.csv"
    totals_path = output_dir / "common_esto_validation_totals.csv"
    if not detail_df.empty:
        by_year_cols = _AGGREGATION_ID_COLS + ["year"]
        by_year_df = _aggregate_validation(detail_df, by_year_cols)
        by_year_df.insert(0, "run_id", run_id)
        by_year_df.to_csv(by_year_path, index=False)

        totals_df = _aggregate_validation(detail_df, _AGGREGATION_ID_COLS)
        totals_df.insert(0, "run_id", run_id)
        totals_df.to_csv(totals_path, index=False)
    else:
        pd.DataFrame().to_csv(by_year_path, index=False)
        pd.DataFrame().to_csv(totals_path, index=False)

    for row in summary_rows:
        row.update({
            "run_id": run_id,
            "run_timestamp_utc": run_timestamp_utc,
            **provenance,
            "output_path": str(detail_path.resolve()),
        })
    summary_df = pd.DataFrame(summary_rows, columns=VALIDATION_SUMMARY_COLUMNS)
    summary_df.to_csv(summary_path, index=False)
    return detail_df, summary_df
