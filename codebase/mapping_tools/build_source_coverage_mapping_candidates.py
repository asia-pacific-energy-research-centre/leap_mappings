"""Build copy-ready mapping candidates from source coverage audit results.

The output is review-only. This module never edits the canonical mapping
workbook. It creates candidate rows for the two LEAP combined sheets and a
9th-to-ESTO crosswalk, plus a separate unresolved file for source fuels whose
LEAP target is missing or ambiguous.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
import sys
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.mapping_tools.source_coverage_audit import (
    DEFAULT_MAPPING_PATH,
    DEFAULT_OUTPUT_DIR,
    STATUS_AMBIGUOUS,
    STATUS_MISSING_LEAP,
    STATUS_OK,
    STATUS_UNMAPPED,
    _load_mapping_sheet,
    load_scope_config,
)

DEFAULT_DETAIL_PATH = DEFAULT_OUTPUT_DIR / "all_demand_aggregated_coverage_detail.csv"
DEFAULT_CANDIDATE_OUTPUT_DIR = DEFAULT_OUTPUT_DIR / "mapping_candidates"

NINTH_SHEET_COLUMNS = [
    "leap_sector_name_full_path",
    "raw_leap_fuel_name",
    "ninth_sector",
    "ninth_fuel",
    "leap_is_subtotal",
    "ninth_pair_is_subtotal",
    "duplicate_to_remove",
]
ESTO_SHEET_COLUMNS = [
    "leap_sector_name_full_path",
    "raw_leap_fuel_name",
    "esto_flow",
    "esto_product",
    "leap_is_subtotal",
    "esto_pair_is_subtotal",
    "duplicate_to_remove",
]
NINTH_ESTO_SHEET_COLUMNS = [
    "ninth_sector",
    "ninth_fuel",
    "esto_flow",
    "esto_product",
    "ninth_pair_is_subtotal",
    "esto_pair_is_subtotal",
    "duplicate_to_remove",
]
NINTH_ESTO_IDENTITY_COLUMNS = ["ninth_sector", "ninth_fuel", "esto_flow", "esto_product"]


def _existing_keys(frame: pd.DataFrame, columns: list[str]) -> set[tuple[str, ...]]:
    if frame.empty:
        return set()
    return {tuple(str(row.get(column, "")).strip() for column in columns) for _, row in frame.iterrows()}


def _component_index(scope: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {component["name"]: component for component in scope["components"]}


def _target_products_by_fuel(mapping: pd.DataFrame, fuel_name: str, flow_names: list[str]) -> dict[str, set[str]]:
    matched = mapping[
        mapping["raw_leap_fuel_name"].eq(fuel_name)
        & mapping["esto_flow"].isin(flow_names)
        & ~mapping["duplicate_to_remove"].map(lambda value: str(value).strip().casefold() in {"true", "1", "yes", "y"})
    ]
    result: dict[str, set[str]] = {}
    for flow, product in matched[["esto_flow", "esto_product"]].itertuples(index=False, name=None):
        if flow and product:
            result.setdefault(flow, set()).add(product)
    return result


def _target_flows_by_ninth_sector(
    ninth_pairs: pd.DataFrame,
    component: dict[str, Any],
) -> dict[str, list[str]]:
    """Resolve each 9th sector to its existing ESTO flow axis.

    Do not use the union of all component flows for every 9th sector: that
    creates artificial cross-products and can turn valid one-axis mappings into
    many-to-many relationships.
    """
    active = ninth_pairs[
        ~ninth_pairs["duplicate_to_remove"].map(
            lambda value: str(value).strip().casefold() in {"true", "1", "yes", "y"}
        )
    ]
    configured = component.get("mapping_ninth_sector_to_esto_flows", {})
    result: dict[str, list[str]] = {}
    for ninth_sector in component.get("mapping_ninth_sectors", []):
        existing = sorted(
            set(active.loc[active["ninth_sector"].eq(ninth_sector), "esto_flow"])
            - {""}
        )
        fallback = [str(value) for value in configured.get(ninth_sector, []) if str(value).strip()]
        result[ninth_sector] = existing or fallback
    return result


def _mapping_flag_for_pair(
    mapping: pd.DataFrame,
    flow_column: str,
    product_column: str,
    flow: str,
    product: str,
    flag_column: str,
    default: bool,
) -> bool:
    matched = mapping[
        mapping[flow_column].eq(flow)
        & mapping[product_column].eq(product)
        & ~mapping["duplicate_to_remove"].map(
            lambda value: str(value).strip().casefold() in {"true", "1", "yes", "y"}
        )
    ]
    if matched.empty or flag_column not in matched.columns:
        return default
    values = matched[flag_column].map(
        lambda value: str(value).strip().casefold() in {"true", "1", "yes", "y"}
    )
    return bool(values.mean() >= 0.5)


def _ninth_pair_subtotal_flag(
    ninth_pairs: pd.DataFrame,
    component: dict[str, Any],
    ninth_sector: str,
    ninth_fuel: str,
) -> bool:
    exact = ninth_pairs[
        ninth_pairs["ninth_sector"].eq(ninth_sector)
        & ninth_pairs["ninth_fuel"].eq(ninth_fuel)
        & ~ninth_pairs["duplicate_to_remove"].map(
            lambda value: str(value).strip().casefold() in {"true", "1", "yes", "y"}
        )
    ]
    if not exact.empty:
        return bool(exact["ninth_pair_is_subtotal"].map(
            lambda value: str(value).strip().casefold() in {"true", "1", "yes", "y"}
        ).mean() >= 0.5)
    return bool(component.get("ninth_pair_is_subtotal_default", False))


def _annotate_cardinality(
    frame: pd.DataFrame,
    existing: pd.DataFrame,
    source_columns: list[str],
    target_columns: list[str],
) -> pd.DataFrame:
    """Classify candidates, including parent/child overlap conflicts."""
    active = existing[
        ~existing["duplicate_to_remove"].map(
            lambda value: str(value).strip().casefold() in {"true", "1", "yes", "y"}
        )
    ].copy()

    def keys(source: pd.DataFrame, columns: list[str]) -> set[tuple[str, ...]]:
        return {
            tuple(str(row.get(column, "")).strip() for column in columns)
            for _, row in source.iterrows()
        }

    existing_source_targets: dict[tuple[str, ...], set[tuple[str, ...]]] = {}
    existing_target_sources: dict[tuple[str, ...], set[tuple[str, ...]]] = {}
    for _, row in active.iterrows():
        source_key = tuple(str(row.get(column, "")).strip() for column in source_columns)
        target_key = tuple(str(row.get(column, "")).strip() for column in target_columns)
        existing_source_targets.setdefault(source_key, set()).add(target_key)
        existing_target_sources.setdefault(target_key, set()).add(source_key)

    candidate_source_targets: dict[tuple[str, ...], set[tuple[str, ...]]] = {}
    candidate_target_sources: dict[tuple[str, ...], set[tuple[str, ...]]] = {}
    for _, row in frame.iterrows():
        source_key = tuple(str(row.get(column, "")).strip() for column in source_columns)
        target_key = tuple(str(row.get(column, "")).strip() for column in target_columns)
        candidate_source_targets.setdefault(source_key, set()).add(target_key)
        candidate_target_sources.setdefault(target_key, set()).add(source_key)

    all_edges = [
        (
            tuple(str(row.get(column, "")).strip() for column in source_columns),
            tuple(str(row.get(column, "")).strip() for column in target_columns),
        )
        for _, row in pd.concat([active, frame], ignore_index=True).iterrows()
    ]

    def hierarchy_relation(left: str, right: str, column: str) -> str:
        """Return parent/child direction for LEAP paths or coded labels."""
        left = str(left).strip()
        right = str(right).strip()
        if not left or not right or left == right:
            return ""
        if "path" in column:
            left_parts = [part.casefold() for part in re.split(r"[/\\]", left) if part.strip()]
            right_parts = [part.casefold() for part in re.split(r"[/\\]", right) if part.strip()]
            if len(left_parts) < len(right_parts) and right_parts[: len(left_parts)] == left_parts:
                return "left_parent"
            if len(right_parts) < len(left_parts) and left_parts[: len(right_parts)] == right_parts:
                return "right_parent"
            return ""

        def numeric_parts(value: str) -> list[int]:
            # Codes such as 16_01_01, 16.01.99, and 07_x are hierarchical;
            # x denotes an aggregate level and therefore stops the prefix.
            code = value.split(maxsplit=1)[0].replace("-", "_")
            parts: list[int] = []
            for token in re.split(r"[._]", code):
                if token.casefold() == "x":
                    break
                if token.isdigit():
                    parts.append(int(token))
                else:
                    break
            return parts

        left_parts = numeric_parts(left)
        right_parts = numeric_parts(right)
        if len(left_parts) < len(right_parts) and right_parts[: len(left_parts)] == left_parts:
            return "left_parent"
        if len(right_parts) < len(left_parts) and left_parts[: len(right_parts)] == right_parts:
            return "right_parent"
        return ""

    def has_parent_child_overlap(
        source_key: tuple[str, ...], target_key: tuple[str, ...]
    ) -> tuple[bool, str]:
        for other_source, other_target in all_edges:
            if other_source == source_key and other_target == target_key:
                continue
            if other_target == target_key:
                for column, left, right in zip(source_columns, source_key, other_source):
                    relation = hierarchy_relation(left, right, column)
                    if relation:
                        return True, f"source_{column}_parent_child"
            if other_source == source_key:
                for column, left, right in zip(target_columns, target_key, other_target):
                    relation = hierarchy_relation(left, right, column)
                    if relation:
                        return True, f"target_{column}_parent_child"
        return False, ""

    statuses: list[str] = []
    overlap_flags: list[bool] = []
    overlap_axes: list[str] = []
    existing_to_target: list[str] = []
    existing_from_source: list[str] = []

    def format_key(key: tuple[str, ...]) -> str:
        return " | ".join(value for value in key if value)

    def format_keys(keys: set[tuple[str, ...]]) -> str:
        return "; ".join(sorted(format_key(key) for key in keys if format_key(key)))
    source_counts: list[int] = []
    target_counts: list[int] = []
    for _, row in frame.iterrows():
        source_key = tuple(str(row.get(column, "")).strip() for column in source_columns)
        target_key = tuple(str(row.get(column, "")).strip() for column in target_columns)
        source_target_count = len(
            existing_source_targets.get(source_key, set())
            | candidate_source_targets.get(source_key, set())
        )
        target_source_count = len(
            existing_target_sources.get(target_key, set())
            | candidate_target_sources.get(target_key, set())
        )
        existing_to_target.append(
            format_keys(existing_target_sources.get(target_key, set()))
        )
        existing_from_source.append(
            format_keys(existing_source_targets.get(source_key, set()))
        )
        has_overlap, overlap_axis = has_parent_child_overlap(source_key, target_key)
        if has_overlap:
            status = "PARENT_CHILD_OVERLAP_CONFLICT"
        elif source_target_count > 1 and target_source_count > 1:
            status = "MANY_TO_MANY_CONFLICT"
        elif source_target_count > 1:
            status = "ONE_TO_MANY_CONFLICT"
        elif target_source_count > 1:
            status = "MANY_TO_ONE_ADDITION"
        else:
            status = "ONE_TO_ONE_ADDITION"
        statuses.append(status)
        overlap_flags.append(has_overlap)
        overlap_axes.append(overlap_axis)
        source_counts.append(source_target_count)
        target_counts.append(target_source_count)
    output = frame.copy()
    output["existing_source_target_count"] = source_counts
    output["existing_target_source_count"] = target_counts
    output["cardinality_if_added"] = statuses
    output["candidate_status"] = statuses
    output["parent_child_overlap"] = overlap_flags
    output["parent_child_overlap_axis"] = overlap_axes
    output["existing_mappings_to_same_target"] = existing_to_target
    output["existing_mappings_from_same_source"] = existing_from_source
    return output


def build_candidates(
    detail: pd.DataFrame,
    scope: dict[str, Any],
    *,
    mapping_path: Path = DEFAULT_MAPPING_PATH,
) -> dict[str, pd.DataFrame]:
    """Return candidate rows and unresolved review rows without writing files."""
    ninth_mapping = _load_mapping_sheet(mapping_path, "leap_combined_ninth")
    esto_mapping = _load_mapping_sheet(mapping_path, "leap_combined_esto")
    ninth_pairs = _load_mapping_sheet(mapping_path, "ninth_pairs_to_esto_pairs")
    components = _component_index(scope)
    mapping_root = scope.get("mapping_root", "All demand aggregated").strip("/\\")
    ninth_sector_flows = {
        name: _target_flows_by_ninth_sector(ninth_pairs, component)
        for name, component in components.items()
    }

    ninth_rows: list[dict[str, Any]] = []
    esto_rows: list[dict[str, Any]] = []
    ninth_esto_rows: list[dict[str, Any]] = []
    unresolved_rows: list[dict[str, Any]] = []

    relevant = detail[detail["coverage_status"].ne(STATUS_OK)].copy()
    for _, row in relevant.iterrows():
        component = components[row["component"]]
        base = {
            "scope": row["scope"],
            "component": row["component"],
            "source": row["source"],
            "economy": row["economy"],
            "source_flow": row["source_flow"],
            "source_fuel": row["source_fuel"],
            "mapped_leap_fuel": row["mapped_leap_fuel"],
            "coverage_status": row["coverage_status"],
            "mapping_status": row["mapping_status"],
        }
        if row["mapping_status"] != "MAPPED":
            unresolved_rows.append({**base, "review_reason": row["mapping_status"]})
            continue

        leap_path = f"{mapping_root}/{component['name']}"
        if row["source"] == "9th":
            for ninth_sector in component.get("mapping_ninth_sectors", []):
                ninth_subtotal = _ninth_pair_subtotal_flag(
                    ninth_pairs, component, ninth_sector, row["source_fuel"]
                )
                ninth_rows.append(
                    {
                        "leap_sector_name_full_path": leap_path,
                        "raw_leap_fuel_name": row["mapped_leap_fuel"],
                        "ninth_sector": ninth_sector,
                        "ninth_fuel": row["source_fuel"],
                        "leap_is_subtotal": False,
                        "ninth_pair_is_subtotal": ninth_subtotal,
                        "duplicate_to_remove": False,
                        **base,
                        "candidate_status": "READY_FOR_MANUAL_REVIEW",
                    }
                )
            for ninth_sector in component.get("mapping_ninth_sectors", []):
                ninth_subtotal = _ninth_pair_subtotal_flag(
                    ninth_pairs, component, ninth_sector, row["source_fuel"]
                )
                target_products = _target_products_by_fuel(
                    esto_mapping,
                    row["mapped_leap_fuel"],
                    ninth_sector_flows[row["component"]].get(ninth_sector, []),
                )
                for esto_flow, products in target_products.items():
                    for esto_product in sorted(products):
                        ninth_esto_rows.append(
                            {
                                "ninth_sector": ninth_sector,
                                "ninth_fuel": row["source_fuel"],
                                "esto_flow": esto_flow,
                                "esto_product": esto_product,
                                "ninth_pair_is_subtotal": ninth_subtotal,
                                "esto_pair_is_subtotal": _mapping_flag_for_pair(
                                    esto_mapping,
                                    "esto_flow",
                                    "esto_product",
                                    esto_flow,
                                    esto_product,
                                    "esto_pair_is_subtotal",
                                    False,
                                ),
                                "duplicate_to_remove": False,
                                **base,
                                "candidate_status": "READY_FOR_MANUAL_REVIEW",
                            }
                        )
        else:
            for esto_flow in component.get("mapping_esto_flows", []):
                esto_rows.append(
                    {
                        "leap_sector_name_full_path": leap_path,
                        "raw_leap_fuel_name": row["mapped_leap_fuel"],
                        "esto_flow": esto_flow,
                        "esto_product": row["source_fuel"],
                        "leap_is_subtotal": False,
                        "esto_pair_is_subtotal": _mapping_flag_for_pair(
                            esto_mapping,
                            "esto_flow",
                            "esto_product",
                            esto_flow,
                            row["source_fuel"],
                            "esto_pair_is_subtotal",
                            False,
                        ),
                        "duplicate_to_remove": False,
                        **base,
                        "candidate_status": "READY_FOR_MANUAL_REVIEW",
                    }
                )

    candidate_specs = [
        ("leap_combined_ninth", ninth_rows, NINTH_SHEET_COLUMNS),
        ("leap_combined_esto", esto_rows, ESTO_SHEET_COLUMNS),
        ("ninth_pairs_to_esto_pairs", ninth_esto_rows, NINTH_ESTO_SHEET_COLUMNS),
    ]
    outputs: dict[str, pd.DataFrame] = {}
    for name, rows, sheet_columns in candidate_specs:
        frame = pd.DataFrame(rows)
        if frame.empty:
            outputs[name] = pd.DataFrame(columns=sheet_columns + ["candidate_status"])
            continue
        identity_columns = NINTH_ESTO_IDENTITY_COLUMNS if name == "ninth_pairs_to_esto_pairs" else sheet_columns[:4]
        keys = _existing_keys(
            {"leap_combined_ninth": ninth_mapping, "leap_combined_esto": esto_mapping, "ninth_pairs_to_esto_pairs": ninth_pairs}[name],
            identity_columns,
        )
        frame["_key"] = list(zip(*(frame[column].astype(str).str.strip() for column in identity_columns)))
        frame = frame[~frame["_key"].isin(keys)].drop_duplicates("_key").drop(columns="_key")
        existing_frame = {
            "leap_combined_ninth": ninth_mapping,
            "leap_combined_esto": esto_mapping,
            "ninth_pairs_to_esto_pairs": ninth_pairs,
        }[name]
        if name == "leap_combined_ninth" and not frame.empty:
            frame = _annotate_cardinality(
                frame,
                existing_frame,
                ["leap_sector_name_full_path", "raw_leap_fuel_name"],
                ["ninth_sector", "ninth_fuel"],
            )
        elif name == "leap_combined_esto" and not frame.empty:
            frame = _annotate_cardinality(
                frame,
                existing_frame,
                ["leap_sector_name_full_path", "raw_leap_fuel_name"],
                ["esto_flow", "esto_product"],
            )
        elif name == "ninth_pairs_to_esto_pairs" and not frame.empty:
            frame = _annotate_cardinality(
                frame,
                existing_frame,
                ["ninth_sector", "ninth_fuel"],
                ["esto_flow", "esto_product"],
            )
        outputs[name] = frame[sheet_columns + [column for column in ["candidate_status", "cardinality_if_added", "parent_child_overlap", "parent_child_overlap_axis", "existing_source_target_count", "existing_target_source_count", "existing_mappings_to_same_target", "existing_mappings_from_same_source", "economy", "component", "source", "source_flow", "source_fuel", "mapped_leap_fuel"] if column in frame.columns]]
        if name in {"leap_combined_ninth", "leap_combined_esto", "ninth_pairs_to_esto_pairs"} and not frame.empty:
            safe_name = f"{name}_safe"
            conflict_name = f"{name}_conflicts"
            outputs[safe_name] = frame[
                frame["cardinality_if_added"].isin({"ONE_TO_ONE_ADDITION", "MANY_TO_ONE_ADDITION"})
                & ~frame["parent_child_overlap"]
            ][sheet_columns + ["candidate_status", "cardinality_if_added", "parent_child_overlap", "parent_child_overlap_axis", "existing_source_target_count", "existing_target_source_count", "existing_mappings_to_same_target", "existing_mappings_from_same_source"]]
            outputs[conflict_name] = frame[
                ~frame["cardinality_if_added"].isin({"ONE_TO_ONE_ADDITION", "MANY_TO_ONE_ADDITION"})
                | frame["parent_child_overlap"]
            ][sheet_columns + ["candidate_status", "cardinality_if_added", "parent_child_overlap", "parent_child_overlap_axis", "existing_source_target_count", "existing_target_source_count", "existing_mappings_to_same_target", "existing_mappings_from_same_source"]]
    outputs["unresolved"] = pd.DataFrame(unresolved_rows)
    return outputs


def run(
    *,
    detail_path: Path = DEFAULT_DETAIL_PATH,
    scope_config_path: Path = REPO_ROOT / "config" / "source_coverage_scopes.json",
    mapping_path: Path = DEFAULT_MAPPING_PATH,
    output_dir: Path = DEFAULT_CANDIDATE_OUTPUT_DIR,
) -> dict[str, Path]:
    scope = load_scope_config(scope_config_path)
    detail = pd.read_csv(detail_path).fillna("")
    outputs = build_candidates(detail, scope, mapping_path=mapping_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, frame in outputs.items():
        path = output_dir / f"all_demand_aggregated_{name}_candidates.csv"
        frame.to_csv(path, index=False)
        paths[name] = path
    return paths


if __name__ == "__main__":
    for label, path in run().items():
        print(f"{label}: {path}")
