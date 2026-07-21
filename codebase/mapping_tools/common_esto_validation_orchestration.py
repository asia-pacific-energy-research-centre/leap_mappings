"""Run Common ESTO hierarchy validation with current-run status metadata."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pandas as pd

from codebase.mapping_tools.build_dataset_tree_structure import (
    COMMON_ESTO_VALIDATION_COLS,
    LEAP_VAR_BASE_YEAR,
    _common_esto_validation_children_map,
    _validate_common_esto_axis_recursive_sums,
)
from codebase.mapping_tools.non_expanding_rollups import (
    DETACHED_MODE,
    NON_EXPANDING_MODE,
    ROLLUP_SHEET_CONFIGS,
    _str,
    build_non_expanding_rollup_catalogue,
    get_rollup_mode,
    load_non_expanding_rollup_rules,
    load_rollup_mode_labels,
    non_expanding_rollup_id,
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


CHILD_DIAGNOSTIC_COLUMNS = [
    "run_id", "validation_axis", "comparison_scope", "source_system", "economy",
    "scenario", "other_axis_value", "year", "parent_code", "expected_child_code",
    "parent_value", "raw_child_value", "final_child_value", "final_descendant_value",
    "rollup_mode", "rollup_id", "replacement_label", "child_status", "diagnosis",
    "parent_difference", "parent_abs_error",
]

FRONTIER_COLUMNS = [
    "source_system", "parent_code", "child_code", "frontier_status", "frontier_reason",
]


PATTERN_COLUMNS = [
    "issue_pattern_id", "validation_axis", "comparison_scope", "source_system",
    "parent_code", "expected_child_code", "rollup_mode", "diagnosis", "child_status",
    "row_count", "economy_count", "other_axis_value_count", "year_count",
    "total_abs_error", "max_abs_error",
]


def _normalise_economy(value: object) -> str:
    text = _str(value)
    if len(text) > 2 and text[2] != "_":
        return f"{text[:2]}_{text[2:]}"
    return text


def _load_rollup_relationships(workbook_path: Path | None) -> tuple[dict[str, list[dict[str, str]]], dict[str, str]]:
    """Load exact input-to-replacement rollup metadata for diagnostics."""
    input_map: dict[str, list[dict[str, str]]] = {}
    label_modes: dict[str, str] = {}
    if workbook_path is None or not workbook_path.exists():
        return input_map, label_modes
    for sheet_name, config in ROLLUP_SHEET_CONFIGS.items():
        try:
            rules = pd.read_excel(workbook_path, sheet_name=sheet_name, dtype=object).fillna("")
        except Exception:
            continue
        if "include" in rules.columns:
            rules = rules[rules["include"].map(lambda value: _str(value).casefold() in {"true", "1", "yes", "y"})]
        for _, row in rules.iterrows():
            input_flow = _str(row.get(config["input_flow"], ""))
            rolled_flow = _str(row.get(config["rolled_flow"], ""))
            if not input_flow or not rolled_flow:
                continue
            mode = get_rollup_mode(row)
            label_modes[rolled_flow] = mode
            input_map.setdefault(input_flow, []).append({
                "rollup_mode": mode,
                "replacement_label": rolled_flow,
                "rollup_id": non_expanding_rollup_id(rolled_flow),
            })
    return input_map, label_modes


def build_source_comparison_frontier(
    tree_df: pd.DataFrame,
    workbook_path: Path | None,
) -> pd.DataFrame:
    """Infer source-specific comparable Common ESTO flow children.

    The Common tree remains canonical, but a source is only expected to
    reconcile children for which that source has an active ESTO target-flow
    mapping.  This makes lower-detail sources such as NINTH explicit without
    adding artificial unavailable mappings to the workbook.
    """
    rows: list[dict[str, str]] = []
    mapped_flows: dict[str, set[str]] = {"ESTO": set(), "LEAP": set(), "NINTH": set()}
    if workbook_path is not None and workbook_path.exists():
        sheet_sources = {
            "leap_combined_esto": "LEAP",
            "ninth_pairs_to_esto_pairs": "NINTH",
        }
        for sheet_name, source_system in sheet_sources.items():
            try:
                mapping = pd.read_excel(workbook_path, sheet_name=sheet_name, dtype=object).fillna("")
            except Exception:
                continue
            if "esto_flow" in mapping.columns:
                mapped_flows[source_system].update(
                    _str(value) for value in mapping["esto_flow"] if _str(value)
                )

        # Synthetic ESTO rollups define source-specific comparison aliases.
        # For example, NINTH's inclusive liquefaction row is represented by
        # the mapped 09.06.02 and 10.01.03 components, while the Common tree
        # also contains unavailable ESTO/LEAP leaves below that subtotal.
        try:
            rollups = pd.read_excel(workbook_path, sheet_name="esto_rollup_rules", dtype=object).fillna("")
            if "include" in rollups.columns:
                rollups = rollups[
                    rollups["include"].map(
                        lambda value: _str(value).casefold() in {"true", "1", "yes", "y"}
                    )
                ]
            for _, rule in rollups.iterrows():
                input_flow = _str(rule.get("input_esto_flow", ""))
                rolled_flow = _str(rule.get("rolled_esto_flow", ""))
                if not input_flow or not rolled_flow:
                    continue
                for source_system, source_flows in mapped_flows.items():
                    if input_flow in source_flows:
                        rows.append({
                            "source_system": source_system,
                            "parent_code": rolled_flow,
                            "child_code": input_flow,
                            "frontier_status": "comparable",
                            "frontier_reason": "active_esto_rollup_input",
                        })
        except Exception:
            pass

    flow_tree = tree_df[
        (tree_df["dataset"] == "common_esto") & (tree_df["axis"] == "flow")
    ].copy()
    children_by_parent = (
        flow_tree[flow_tree["parent_code"].notna()]
        .groupby("parent_code")["code"]
        .apply(list)
        .to_dict()
    )
    for parent_code, children in children_by_parent.items():
        for source_system, source_flows in mapped_flows.items():
            for child_code in children:
                if source_system == "ESTO" or child_code in source_flows:
                    status = "comparable"
                    reason = "active_source_to_esto_mapping"
                else:
                    status = "source_unavailable"
                    reason = "no_active_source_to_esto_mapping"
                rows.append({
                    "source_system": source_system,
                    "parent_code": _str(parent_code),
                    "child_code": _str(child_code),
                    "frontier_status": status,
                    "frontier_reason": reason,
                })
    return pd.DataFrame(rows, columns=FRONTIER_COLUMNS).drop_duplicates()


def _load_diagnostic_source_values(output_dir: Path) -> dict[str, pd.DataFrame]:
    """Load converted ESTO-shaped source rows used for child-level evidence."""
    relationship_dir = output_dir.parent / "mapping_relationships"
    paths = {
        "ESTO": relationship_dir / "esto_results_exact_rows.csv",
        "LEAP": relationship_dir / "leap_results_converted_to_esto.csv",
        "NINTH": relationship_dir / "ninth_results_converted_to_esto.csv",
    }
    result: dict[str, pd.DataFrame] = {}
    group_cols = ["economy", "scenario", "year", "esto_flow", "esto_product"]
    for system, path in paths.items():
        if not path.exists():
            continue
        columns = pd.read_csv(path, nrows=0).columns.tolist()
        required = set(group_cols + ["value"])
        if not required.issubset(columns):
            continue
        data = pd.read_csv(path, usecols=sorted(required), dtype=object)
        data["economy"] = data["economy"].map(_normalise_economy)
        data["year"] = pd.to_numeric(data["year"], errors="coerce").astype("Int64").astype(str)
        data["value"] = pd.to_numeric(data["value"], errors="coerce").fillna(0.0)
        result[system] = data.groupby(group_cols, dropna=False, as_index=False)["value"].sum()
    return result


def _descendants(code: str, children_map: dict[str, list[str]]) -> list[str]:
    output: list[str] = []
    for child in children_map.get(code, []):
        output.append(child)
        output.extend(_descendants(child, children_map))
    return output


def _diagnose_child_status(
    child_code: str,
    parent_code: str,
    direct_value: float,
    descendant_value: float,
    raw_value: float,
    rollup_inputs: dict[str, list[dict[str, str]]],
    rollup_modes: dict[str, str],
) -> tuple[str, str, str, str]:
    # Presence in the final output wins: a child that is actually emitted under
    # this parent is a legitimate present child, even if the same code happens to
    # be a contributor to a rollup in some other context. Diagnosing it as
    # "replaced" there produced false alarms on ordinary parents (e.g. 09.07 Oil
    # refineries present under 09 Total transformation sector).
    if abs(direct_value) > 0:
        return rollup_modes.get(child_code, ""), "", "", "present_in_final_output"
    if abs(descendant_value) > 0:
        return rollup_modes.get(child_code, ""), "", "", "represented_by_descendants"
    # The child is absent from the final output. Explain why.
    parent_mode = rollup_modes.get(parent_code, "")
    if parent_mode in {NON_EXPANDING_MODE, DETACHED_MODE}:
        return (
            parent_mode,
            non_expanding_rollup_id(parent_code),
            parent_code,
            "child_obscured_by_parent_rollup",
        )
    replacements = rollup_inputs.get(child_code, [])
    if replacements:
        replacement = replacements[0]
        mode = replacement["rollup_mode"]
        return mode, replacement["rollup_id"], replacement["replacement_label"], (
            "replaced_by_detached_rollup" if mode == DETACHED_MODE else "replaced_by_non_expanding_rollup"
        )
    if abs(raw_value) > 0:
        return rollup_modes.get(child_code, ""), "", "", "missing_nonzero_source_child"
    return rollup_modes.get(child_code, ""), "", "", "absent_zero_source_child"


def build_common_esto_child_diagnostics(
    validation_df: pd.DataFrame,
    tree_df: pd.DataFrame,
    comparison_data_path: Path,
    output_dir: Path,
    run_id: str,
    workbook_path: Path | None = None,
    source_frontier: pd.DataFrame | None = None,
    exclude_parents: set[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Expand parent checks into child evidence and recurring issue patterns."""
    if validation_df.empty:
        empty_detail = pd.DataFrame(columns=CHILD_DIAGNOSTIC_COLUMNS)
        empty_patterns = pd.DataFrame(columns=PATTERN_COLUMNS)
        return empty_detail, empty_patterns, empty_detail.copy()
    comparison = pd.read_csv(comparison_data_path, dtype=object)
    comparison["year"] = pd.to_numeric(comparison["year"], errors="coerce").astype("Int64").astype(str)
    comparison["value"] = pd.to_numeric(comparison["value"], errors="coerce").fillna(0.0)
    comparison["economy"] = comparison["economy"].map(_normalise_economy)
    comparison_lookups: dict[str, dict[tuple[str, ...], dict[str, float]]] = {}
    for axis_name, axis_column, other_column in [
        ("flow", "common_flow_label", "common_product_label"),
        ("product", "common_product_label", "common_flow_label"),
    ]:
        grouped = comparison.groupby(
            ["comparison_scope", "source_system", "economy", "scenario", other_column, "year", axis_column],
            dropna=False,
        )["value"].sum().reset_index()
        lookup: dict[tuple[str, ...], dict[str, float]] = {}
        for row in grouped.itertuples(index=False):
            values = row._asdict()
            prefix = tuple(str(values[column]) for column in ["comparison_scope", "source_system", "economy", "scenario", other_column, "year"])
            lookup.setdefault(prefix, {})[str(values[axis_column])] = float(values["value"])
        comparison_lookups[axis_name] = lookup
    source_values = _load_diagnostic_source_values(output_dir)
    raw_lookups: dict[str, dict[str, dict[tuple[str, ...], dict[str, float]]]] = {}
    for system, raw in source_values.items():
        raw_lookups[system] = {}
        for axis_name, value_column, other_column in [
            ("flow", "esto_flow", "esto_product"),
            ("product", "esto_product", "esto_flow"),
        ]:
            grouped = raw.groupby(
                ["economy", "scenario", "year", other_column, value_column], dropna=False
            )["value"].sum().reset_index()
            lookup: dict[tuple[str, ...], dict[str, float]] = {}
            for row in grouped.itertuples(index=False):
                values = row._asdict()
                prefix = tuple(str(values[column]) for column in ["economy", "scenario", "year", other_column])
                lookup.setdefault(prefix, {})[str(values[value_column])] = float(values["value"])
            raw_lookups[system][axis_name] = lookup
    rollup_inputs, rollup_modes = _load_rollup_relationships(workbook_path)
    detail_rows: list[dict[str, object]] = []
    for _, check in validation_df[validation_df["status"].eq("failed")].iterrows():
        axis = str(check["validation_axis"])
        axis_col = "common_product_label" if axis == "product" else "common_flow_label"
        other_col = "common_flow_label" if axis == "product" else "common_product_label"
        children_map = _common_esto_validation_children_map(tree_df, axis, exclude_parents)
        parent = str(check["parent_code"])
        expected_children = children_map.get(parent, [])
        if source_frontier is not None and axis == "flow":
            comparable = source_frontier[
                (source_frontier["source_system"] == str(check["source_system"]))
                & (source_frontier["parent_code"] == parent)
                & source_frontier["frontier_status"].eq("comparable")
            ]
            expected_children = comparable["child_code"].astype(str).tolist()
        comparison_prefix = (
            str(check["comparison_scope"]), str(check["source_system"]), _normalise_economy(check["economy"]),
            str(check["scenario"]), str(check["other_axis_value"]), str(check["year"]),
        )
        direct_values = comparison_lookups[axis].get(comparison_prefix, {})
        descendant_values = {
            child: sum(direct_values.get(descendant, 0.0) for descendant in _descendants(child, children_map))
            for child in expected_children
        }
        raw_prefix = (
            _normalise_economy(check["economy"]), str(check["scenario"]), str(check["year"]),
            str(check["other_axis_value"]),
        )
        raw_values = raw_lookups.get(str(check["source_system"]), {}).get(axis, {}).get(raw_prefix, {})
        for child in expected_children:
            direct_value = float(direct_values.get(child, 0.0))
            descendant_value = descendant_values.get(child, 0.0)
            raw_value = float(raw_values.get(child, 0.0))
            mode, rollup_id, replacement, diagnosis = _diagnose_child_status(
                child, parent, direct_value, descendant_value, raw_value, rollup_inputs, rollup_modes
            )
            detail_rows.append({
                "run_id": run_id, "validation_axis": axis, "comparison_scope": check["comparison_scope"],
                "source_system": check["source_system"], "economy": check["economy"], "scenario": check["scenario"],
                "other_axis_value": check["other_axis_value"], "year": check["year"], "parent_code": parent,
                "expected_child_code": child, "parent_value": check["parent_value"], "raw_child_value": raw_value,
                "final_child_value": direct_value, "final_descendant_value": descendant_value,
                "rollup_mode": mode, "rollup_id": rollup_id, "replacement_label": replacement,
                "child_status": "present" if child in direct_values else "missing",
                "diagnosis": diagnosis, "parent_difference": check["difference"], "parent_abs_error": check["abs_error"],
            })
    detail = pd.DataFrame(detail_rows, columns=CHILD_DIAGNOSTIC_COLUMNS)
    if detail.empty:
        return detail, pd.DataFrame(columns=PATTERN_COLUMNS), detail.copy()
    numeric_cols = ["parent_value", "raw_child_value", "final_child_value", "final_descendant_value", "parent_difference", "parent_abs_error"]
    detail[numeric_cols] = detail[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    pattern_keys = ["validation_axis", "comparison_scope", "source_system", "parent_code", "expected_child_code", "rollup_mode", "diagnosis", "child_status"]
    patterns = detail.groupby(pattern_keys, dropna=False).agg(
        row_count=("run_id", "size"), economy_count=("economy", "nunique"),
        other_axis_value_count=("other_axis_value", "nunique"), year_count=("year", "nunique"),
        total_abs_error=("parent_abs_error", "sum"), max_abs_error=("parent_abs_error", "max"),
    ).reset_index()
    patterns.insert(0, "issue_pattern_id", patterns[pattern_keys].astype(str).agg("|".join, axis=1).map(lambda value: "pattern_" + hashlib.md5(value.encode()).hexdigest()[:16]))
    rollup_detail = detail[detail["rollup_mode"].isin([NON_EXPANDING_MODE, DETACHED_MODE])].copy()
    return detail, patterns[PATTERN_COLUMNS], rollup_detail


ROLLUP_VALIDATION_COLUMNS = [
    "run_id", "comparison_scope", "source_system", "economy", "scenario",
    "common_product_label", "year", "rollup_label", "rollup_mode", "rollup_id",
    "rollup_value", "contributor_sum", "difference", "abs_error", "proportional_error",
    "declared_contributor_count", "present_contributor_count",
    "present_contributors", "missing_contributors", "status", "reason",
]

ROLLUP_VALIDATION_SUMMARY_COLUMNS = [
    "rollup_label", "rollup_mode", "rollup_id", "source_system",
    "checks", "passed", "failed", "incomplete_contributors",
    "no_contributors_available", "total_abs_error", "max_abs_error",
]


def _excluded_rollup_parents(workbook_path: Path | None) -> set[str]:
    """Return rolled flow labels that must not be validated as additive parents.

    A named ``NON_EXPANDING`` / ``DETACHED`` subtotal is registered as a tree
    node so it displays with its sub-parts, but it is an alternative view of its
    contributors, never an additive sum of its declared tree children. The
    ordinary recursive validator must skip these labels; the dedicated rollup
    validator reconciles them against their declared contributors instead.
    """
    if workbook_path is None or not Path(workbook_path).exists():
        return set()
    try:
        mode_labels = load_rollup_mode_labels(Path(workbook_path))
    except Exception:
        return set()
    return {
        label
        for label, mode in mode_labels.items()
        if mode in {NON_EXPANDING_MODE, DETACHED_MODE}
    }


def _esto_rollup_contributors(workbook_path: Path | None) -> dict[str, dict[str, object]]:
    """Map each ESTO-shaped rolled flow label to its declared contributor flows.

    The Common ESTO comparison rows are ESTO-shaped, so only ESTO-sheet rolled
    labels line up with ``common_flow_label`` values. Each entry records the
    contributor flow set, the rollup mode, the stable id, and the (optional)
    rolled product the subtotal is emitted under.
    """
    if workbook_path is None or not Path(workbook_path).exists():
        return {}
    try:
        rules_by_sheet = load_non_expanding_rollup_rules(Path(workbook_path))
    except Exception:
        return {}
    catalogue = build_non_expanding_rollup_catalogue(rules_by_sheet)
    if catalogue.empty:
        return {}
    esto = catalogue[catalogue["source_system"].astype(str) == "ESTO"]
    contributors: dict[str, dict[str, object]] = {}
    for rolled_label, group in esto.groupby("rolled_flow_label", dropna=False):
        rolled_label = _str(rolled_label)
        if not rolled_label:
            continue
        inputs = sorted({_str(value) for value in group["input_flow"] if _str(value)})
        if not inputs:
            continue
        rolled_products = sorted({_str(value) for value in group["rolled_product_label"] if _str(value)})
        contributors[rolled_label] = {
            "rollup_mode": _str(group["rollup_mode"].iloc[0]),
            "rollup_id": _str(group["non_expanding_rollup_id"].iloc[0]),
            "contributors": inputs,
            "rolled_product": rolled_products[0] if rolled_products else "",
        }
    return contributors


def validate_non_expanding_rollups(
    comparison_data_path: Path,
    workbook_path: Path | None,
    run_id: str,
    leap_var_base_year: int = LEAP_VAR_BASE_YEAR,
    tolerance: float = 0.01,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reconcile each named rollup subtotal against its declared contributors.

    For every source that emits a rolled label, the rolled value is compared with
    the sum of that source's declared contributor flows. This is the check the
    ordinary recursive validator must not perform (it would add the subtotal to
    its tree children); doing it here against declared contributors -- and only
    when the source actually reports them -- is the correct rollup boundary
    validation.

    Status values:

    - ``passed`` / ``failed`` -- every declared contributor is present for that
      source, so the reconciliation is complete.
    - ``incomplete_contributors`` -- the source reports some but not all
      contributors; recorded for diagnosis, not a failure.
    - ``no_contributors_available`` -- the source emits the rollup but none of
      its declared contributors (e.g. a lower-detail source), so there is nothing
      to reconcile against.
    """
    contributors = _esto_rollup_contributors(workbook_path)
    if not contributors or not comparison_data_path.exists():
        return (
            pd.DataFrame(columns=ROLLUP_VALIDATION_COLUMNS),
            pd.DataFrame(columns=ROLLUP_VALIDATION_SUMMARY_COLUMNS),
        )
    tracked_labels = set(contributors)
    contributor_flows = {flow for entry in contributors.values() for flow in entry["contributors"]}
    keep_labels = tracked_labels | contributor_flows

    data = pd.read_csv(comparison_data_path, dtype=object)
    required = {"comparison_scope", "source_system", "economy", "scenario", "year",
                "common_flow_label", "common_product_label", "value"}
    if not required.issubset(data.columns):
        return (
            pd.DataFrame(columns=ROLLUP_VALIDATION_COLUMNS),
            pd.DataFrame(columns=ROLLUP_VALIDATION_SUMMARY_COLUMNS),
        )
    data["value"] = pd.to_numeric(data["value"], errors="coerce").fillna(0.0)
    data["year"] = pd.to_numeric(data["year"], errors="coerce")
    data = data[data["year"] > int(leap_var_base_year)].copy()
    data = data[data["common_flow_label"].astype(str).isin(keep_labels)]
    if data.empty:
        return (
            pd.DataFrame(columns=ROLLUP_VALIDATION_COLUMNS),
            pd.DataFrame(columns=ROLLUP_VALIDATION_SUMMARY_COLUMNS),
        )
    data["year"] = data["year"].astype(int).astype(str)
    group_cols = ["comparison_scope", "source_system", "economy", "scenario",
                  "common_product_label", "year"]
    grouped = (
        data.groupby(group_cols + ["common_flow_label"], dropna=False)["value"]
        .sum()
        .reset_index()
    )
    values_by_group: dict[tuple[str, ...], dict[str, float]] = {}
    for row in grouped.itertuples(index=False):
        key = tuple(str(getattr(row, col)) for col in group_cols)
        values_by_group.setdefault(key, {})[str(row.common_flow_label)] = float(row.value)

    rows: list[dict[str, object]] = []
    for key, flow_values in values_by_group.items():
        scope, source_system, economy, scenario, product, year = key
        for rolled_label, entry in contributors.items():
            if rolled_label not in flow_values:
                continue
            declared = entry["contributors"]
            present = [flow for flow in declared if flow in flow_values]
            missing = [flow for flow in declared if flow not in flow_values]
            rolled_value = flow_values[rolled_label]
            contributor_sum = sum(flow_values[flow] for flow in present)
            diff = rolled_value - contributor_sum
            err = abs(diff)
            prop_err = diff / rolled_value if abs(rolled_value) > tolerance else None
            if not present:
                status, reason = "no_contributors_available", "source_emits_rollup_without_contributors"
            elif missing:
                status, reason = "incomplete_contributors", "source_reports_subset_of_contributors"
            else:
                failed = err > tolerance * max(abs(rolled_value), 1)
                status = "failed" if failed else "passed"
                reason = "contributor_sum_differs" if failed else "reconciles_with_contributors"
            rows.append({
                "run_id": run_id, "comparison_scope": scope, "source_system": source_system,
                "economy": economy, "scenario": scenario, "common_product_label": product, "year": year,
                "rollup_label": rolled_label, "rollup_mode": entry["rollup_mode"], "rollup_id": entry["rollup_id"],
                "rollup_value": rolled_value, "contributor_sum": contributor_sum, "difference": diff,
                "abs_error": err, "proportional_error": prop_err,
                "declared_contributor_count": len(declared), "present_contributor_count": len(present),
                "present_contributors": "|".join(present), "missing_contributors": "|".join(missing),
                "status": status, "reason": reason,
            })
    detail = pd.DataFrame(rows, columns=ROLLUP_VALIDATION_COLUMNS)
    if detail.empty:
        return detail, pd.DataFrame(columns=ROLLUP_VALIDATION_SUMMARY_COLUMNS)
    summary = detail.groupby(["rollup_label", "rollup_mode", "rollup_id", "source_system"], dropna=False).agg(
        checks=("status", "size"),
        passed=("status", lambda s: int((s == "passed").sum())),
        failed=("status", lambda s: int((s == "failed").sum())),
        incomplete_contributors=("status", lambda s: int((s == "incomplete_contributors").sum())),
        no_contributors_available=("status", lambda s: int((s == "no_contributors_available").sum())),
        total_abs_error=("abs_error", "sum"),
        max_abs_error=("abs_error", "max"),
    ).reset_index()
    return detail, summary[ROLLUP_VALIDATION_SUMMARY_COLUMNS]


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
    source_frontier: pd.DataFrame | None = None,
    exclude_parents: set[str] | None = None,
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

    for parent_code, children in _common_esto_validation_children_map(tree_df, axis, exclude_parents).items():
        parent_rows = data[data[axis_col] == parent_code]
        expected_children = children
        if source_frontier is not None and axis == "flow":
            comparable = source_frontier[
                (source_frontier["parent_code"] == parent_code)
                & source_frontier["frontier_status"].eq("comparable")
            ]
            children_by_source = {
                source: set(group["child_code"].astype(str))
                for source, group in comparable.groupby("source_system", dropna=False)
            }
        else:
            children_by_source = {}
        if parent_rows.empty:
            continue
        children_rows = data[data[axis_col].isin(expected_children)]
        if parent_rows.empty or children_rows.empty:
            continue
        parent_groups = parent_rows.groupby(group_cols, dropna=False).size().index
        child_groups = children_rows.groupby(group_cols, dropna=False).size().index
        for group_key in parent_groups.intersection(child_groups):
            source_system = str(group_key[1])
            if source_frontier is not None and axis == "flow":
                allowed = children_by_source.get(source_system, set())
                if not allowed:
                    continue
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
    workbook_path: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run Common ESTO validations and always replace current-run outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    source_frontier = build_source_comparison_frontier(tree_df, workbook_path)
    source_frontier.to_csv(output_dir / "common_esto_source_frontier.csv", index=False)
    excluded_rollup_parents = _excluded_rollup_parents(workbook_path)
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
                source_frontier=source_frontier,
                exclude_parents=excluded_rollup_parents,
            )
            metrics = _count_eligible_checks(
                tree_df,
                comparison_data_path,
                axis,
                leap_var_base_year,
                source_frontier=source_frontier,
                exclude_parents=excluded_rollup_parents,
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

    child_detail, issue_patterns, rollup_diagnosis = build_common_esto_child_diagnostics(
        validation_df=detail_df,
        tree_df=tree_df,
        comparison_data_path=comparison_data_path,
        output_dir=output_dir,
        run_id=run_id,
        workbook_path=workbook_path,
        source_frontier=source_frontier,
        exclude_parents=excluded_rollup_parents,
    )
    child_detail.to_csv(output_dir / "common_esto_validation_child_detail.csv", index=False)
    issue_patterns.to_csv(output_dir / "common_esto_validation_issue_patterns.csv", index=False)
    rollup_diagnosis.to_csv(output_dir / "common_esto_validation_rollup_diagnosis.csv", index=False)

    # Named non-expanding / detached subtotals are excluded from the ordinary
    # recursive validator above; reconcile them here against their declared
    # contributors and source availability instead.
    rollup_validation, rollup_validation_summary = validate_non_expanding_rollups(
        comparison_data_path=comparison_data_path,
        workbook_path=workbook_path,
        run_id=run_id,
        leap_var_base_year=leap_var_base_year,
        tolerance=tolerance,
    )
    rollup_validation.to_csv(output_dir / "common_esto_rollup_validation.csv", index=False)
    rollup_validation_summary.to_csv(
        output_dir / "common_esto_rollup_validation_summary.csv", index=False
    )

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
