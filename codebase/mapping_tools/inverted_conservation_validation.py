#%%
"""Validate Flavor-A conservation when ESTO or Ninth is expressed in LEAP.

Values are never read from LEAP.  Source values are projected through shared
Common-ESTO rows.  Only exclusive one-to-one pairs receive a projected value;
fan-out and many-to-one relationships remain unresolved and are reported with
all involved pairs.
"""

#%%
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.mapping_tools.reconcile_anchor_validation import (
    SYSTEM_SCOPE,
    _edge_topology,
    build_anchor_contributions,
    build_parent_boundaries,
    iter_raw_partitions,
)


DIRECTION_CONFIG = {
    "ESTO_TO_LEAP": {
        "source_system": "ESTO",
        "target_system": "LEAP",
        "comparison_scope": "leap_vs_esto",
        "source_scenario": "historical",
    },
    "NINTH_TO_LEAP": {
        "source_system": "NINTH",
        "target_system": "LEAP",
        "comparison_scope": "leap_vs_esto_vs_ninth",
        "source_scenario": None,
    },
}

DEFAULT_STRUCTURAL_PATH = REPO_ROOT / "results/common_esto/structural_artifacts/source_pair_to_common_row.csv"
DEFAULT_TREE_PATH = REPO_ROOT / "results/tree_structure/all_dataset_trees.csv"
DEFAULT_NINTH_FUEL_VALIDATION_PATH = REPO_ROOT / "results/tree_structure/ninth_fuel_validation.csv"
DEFAULT_TARGET_VARIANTS_PATH = REPO_ROOT / "config/inverted_conservation_target_variants.json"
DEFAULT_TARGET_ALIASES_PATH = REPO_ROOT / "config/inverted_conservation_target_aliases.json"
DEFAULT_RAW_PATHS = {
    "ESTO": REPO_ROOT / "data/00APEC_2025_low_with_subtotals.csv",
    "NINTH": REPO_ROOT / "data/merged_file_energy_ALL_20251106.csv",
}

NO_COUNTERPART_COLUMNS = [
    "direction", "counterpart_state", "source_system", "target_system",
    "comparison_scope", "common_row_id", "source_flow", "source_product",
    "target_flow", "target_product", "economy", "scenario", "year", "source_value",
    "exception_classification", "exception_reason", "subtotal_validation_difference",
]

VARIANT_COVERAGE_COLUMNS = [
    "direction", "source_system", "target_system", "target_variant_family",
    "target_variant", "reference_variant", "source_pair_count",
    "reference_source_pair_count", "missing_source_pairs", "extra_source_pairs",
    "variant_coverage_status", "safe_to_sum_across_variants",
]


def load_target_variants(path: Path | None) -> dict[str, Any]:
    """Load optional validation-only alternative target branch definitions."""
    if path is None or not Path(path).exists():
        return {"families": {}}
    config = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(config.get("families", {}), dict):
        raise ValueError("Target variant config 'families' must be an object.")
    return config


def load_target_aliases(path: Path | None) -> dict[str, Any]:
    """Load optional placeholder-alias normalization rules for target branches."""
    if path is None or not Path(path).exists():
        return {"aliases": []}
    config = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    aliases = config.get("aliases", [])
    if not isinstance(aliases, list):
        raise ValueError("Target alias config 'aliases' must be an array.")
    return config


def _build_alias_map(alias_config: dict[str, Any]) -> dict[tuple[str, str], tuple[str, str]]:
    """Return alias->canonical target pair mappings."""
    alias_map: dict[tuple[str, str], tuple[str, str]] = {}
    for entry in alias_config.get("aliases", []):
        canonical_flow = str(entry.get("canonical_target_flow", "")).strip()
        canonical_product = str(entry.get("canonical_target_product", "")).strip()
        if not canonical_flow or not canonical_product:
            continue
        canonical_pair = (canonical_flow, canonical_product)
        raw_aliases = entry.get("aliases", [])
        if not isinstance(raw_aliases, list):
            raise ValueError("Each target alias entry must contain an 'aliases' list.")
        for alias in raw_aliases:
            alias_flow = str(alias.get("target_flow", "")).strip()
            alias_product = str(alias.get("target_product", canonical_product)).strip()
            if not alias_flow:
                continue
            alias_pair = (alias_flow, alias_product)
            existing = alias_map.get(alias_pair)
            if existing is not None and existing != canonical_pair:
                raise ValueError(
                    f"Alias pair {alias_pair} maps to multiple canonical targets: "
                    f"{existing} and {canonical_pair}"
                )
            alias_map[alias_pair] = canonical_pair
    return alias_map


def _normalize_target_pair(
    flow: str,
    product: str,
    alias_map: dict[tuple[str, str], tuple[str, str]],
) -> tuple[str, str]:
    pair = (str(flow).strip(), str(product).strip())
    return alias_map.get(pair, pair)


def partition_edges_by_target_variant(
    edges: pd.DataFrame,
    target_system: str,
    variant_config: dict[str, Any],
) -> list[tuple[str, str, pd.DataFrame]]:
    """Separate alternative target structures so they are never summed."""
    if target_system != variant_config.get("target_system"):
        return [("", "", edges.copy())]

    configured_mask = pd.Series(False, index=edges.index)
    partitions: list[tuple[str, str, pd.DataFrame]] = []
    for family, family_config in variant_config.get("families", {}).items():
        for variant, target_flows in family_config.get("variants", {}).items():
            mask = edges["target_flow"].isin(target_flows)
            configured_mask |= mask
            subset = edges[mask].copy()
            if not subset.empty:
                partitions.append((family, variant, subset))
    ordinary = edges[~configured_mask].copy()
    if not ordinary.empty:
        partitions.insert(0, ("", "", ordinary))
    return partitions


def build_variant_coverage_audit(
    edge_partitions: list[tuple[str, str, pd.DataFrame]],
    direction: str,
    source_system: str,
    target_system: str,
) -> pd.DataFrame:
    """Verify that every configured variant covers the same source-pair set."""
    families: dict[str, dict[str, set[tuple[str, str]]]] = {}
    for family, variant, edges in edge_partitions:
        if not family:
            continue
        families.setdefault(family, {})[variant] = set(
            zip(edges["source_flow"], edges["source_product"])
        )
    rows: list[dict[str, Any]] = []
    for family, variants in families.items():
        reference_variant = sorted(variants)[0]
        reference_pairs = variants[reference_variant]
        for variant, pairs in sorted(variants.items()):
            missing = reference_pairs - pairs
            extra = pairs - reference_pairs
            rows.append({
                "direction": direction, "source_system": source_system,
                "target_system": target_system, "target_variant_family": family,
                "target_variant": variant, "reference_variant": reference_variant,
                "source_pair_count": len(pairs),
                "reference_source_pair_count": len(reference_pairs),
                "missing_source_pairs": " | ".join(
                    f"{flow} / {product}" for flow, product in sorted(missing)
                ),
                "extra_source_pairs": " | ".join(
                    f"{flow} / {product}" for flow, product in sorted(extra)
                ),
                "variant_coverage_status": (
                    "complete_equivalent_coverage" if not missing and not extra
                    else "coverage_mismatch"
                ),
                "safe_to_sum_across_variants": False,
            })
    return pd.DataFrame(rows, columns=VARIANT_COVERAGE_COLUMNS)


def compose_direction_edges(
    structural_df: pd.DataFrame,
    source_system: str,
    target_system: str,
    comparison_scope: str,
    alias_map: dict[tuple[str, str], tuple[str, str]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compose X-to-Y pairs by joining their existing shared common rows.

    Returns composed edges, source pairs without a target counterpart, and
    target pairs without a source counterpart.  No new mapping is inferred.
    """
    required = {
        "comparison_scope", "source_system", "original_source_flow",
        "original_source_product", "common_row_id",
    }
    missing = required.difference(structural_df.columns)
    if missing:
        raise ValueError(f"Structural artifact is missing columns: {sorted(missing)}")

    data = structural_df.copy()
    for column in required:
        data[column] = data[column].fillna("").astype(str).str.strip()
    data = data[data["comparison_scope"].eq(comparison_scope)].copy()

    pair_columns = ["original_source_flow", "original_source_product", "common_row_id"]
    source = data[data["source_system"].str.upper().eq(source_system)][pair_columns].drop_duplicates()
    target = data[data["source_system"].str.upper().eq(target_system)][pair_columns].drop_duplicates()
    source = source.rename(columns={
        "original_source_flow": "source_flow", "original_source_product": "source_product"
    })
    target = target.rename(columns={
        "original_source_flow": "target_flow", "original_source_product": "target_product"
    })

    edges = source.merge(target, on="common_row_id", how="inner")
    edges = edges.drop_duplicates(
        ["source_flow", "source_product", "target_flow", "target_product"]
    ).copy()
    if alias_map:
        normalized_targets = edges.apply(
            lambda row: _normalize_target_pair(row["target_flow"], row["target_product"], alias_map),
            axis=1,
            result_type="expand",
        )
        edges["target_flow"] = normalized_targets[0]
        edges["target_product"] = normalized_targets[1]
        edges = edges.drop_duplicates(
            ["source_flow", "source_product", "target_flow", "target_product"]
        ).copy()
    edges["relationship_id"] = edges.apply(
        lambda row: "dir_" + hashlib.sha1(
            "|".join([
                source_system, target_system, comparison_scope,
                row["source_flow"], row["source_product"],
                row["target_flow"], row["target_product"],
            ]).encode("utf-8")
        ).hexdigest()[:16],
        axis=1,
    )

    target_common_rows = set(target["common_row_id"])
    source_common_rows = set(source["common_row_id"])
    source_without_target = source[~source["common_row_id"].isin(target_common_rows)].copy()
    target_without_source = target[~target["common_row_id"].isin(source_common_rows)].copy()
    return edges, source_without_target, target_without_source


def _structural_edges_for_existing_boundary_builder(
    edges: pd.DataFrame,
    source_system: str,
) -> pd.DataFrame:
    """Adapt composed X-to-Y edges to the existing boundary builder contract."""
    adapted = edges.rename(columns={
        "source_flow": "original_source_flow",
        "source_product": "original_source_product",
        "target_flow": "component_esto_flow",
        "target_product": "component_esto_product",
    }).copy()
    adapted["source_system"] = source_system
    adapted["comparison_scope"] = SYSTEM_SCOPE[source_system]
    adapted["is_exact_row"] = "True"
    return adapted


def project_bijective_values(
    raw_partition: pd.DataFrame,
    edges: pd.DataFrame,
    alias_map: dict[tuple[str, str], tuple[str, str]] | None = None,
) -> pd.DataFrame:
    """Project only exclusive one-to-one source values onto target pairs."""
    edge_tuples = tuple(
        edges[["source_flow", "source_product", "target_flow", "target_product", "relationship_id"]]
        .itertuples(index=False, name=None)
    )
    targets_of, sources_of, _ = _edge_topology(edge_tuples)
    raw_totals = raw_partition.groupby(["source_flow", "source_product"])["value"].sum()
    rows: list[dict[str, Any]] = []
    base = raw_partition.iloc[0]
    emitted_targets: set[tuple[str, str]] = set()
    for source_pair, targets in targets_of.items():
        if len(targets) != 1:
            continue
        target_pair = next(iter(targets))
        if len(sources_of[target_pair]) != 1:
            continue
        emitted_targets.add(target_pair)
        rows.append({
            "source_system": str(base["source_system"]),
            "economy": str(base["economy"]),
            "scenario": str(base["scenario"]),
            "year": base["year"],
            "esto_flow": target_pair[0],
            "esto_product": target_pair[1],
            "value": float(raw_totals.get(source_pair, 0.0)),
        })
    if alias_map:
        canonical_targets = set(alias_map.values())
        grouped_sources: dict[tuple[str, str], set[tuple[str, str]]] = {}
        for source_pair, targets in targets_of.items():
            normalized_targets = {
                alias_map.get(target_pair, target_pair) for target_pair in targets
            }
            if len(normalized_targets) == 1:
                canonical_target = next(iter(normalized_targets))
                if canonical_target in canonical_targets:
                    grouped_sources.setdefault(canonical_target, set()).add(source_pair)
        for canonical_target, source_pairs in grouped_sources.items():
            if canonical_target in emitted_targets:
                continue
            if len(source_pairs) <= 1:
                continue
            rows.append({
                "source_system": str(base["source_system"]),
                "economy": str(base["economy"]),
                "scenario": str(base["scenario"]),
                "year": base["year"],
                "esto_flow": canonical_target[0],
                "esto_product": canonical_target[1],
                "value": float(sum(raw_totals.get(pair, 0.0) for pair in source_pairs)),
            })
    return pd.DataFrame(rows, columns=[
        "source_system", "economy", "scenario", "year",
        "esto_flow", "esto_product", "value",
    ])


def _collapse_alias_groups(
    contributions: pd.DataFrame,
    alias_map: dict[tuple[str, str], tuple[str, str]],
) -> pd.DataFrame:
    """Collapse placeholder-alias target groups into one canonical bucket."""
    if contributions.empty or not alias_map:
        return contributions
    working = contributions.copy()
    collapsed_rows: list[dict[str, Any]] = []
    collapsed_group_ids: set[str] = set()
    for group_id, group in working.groupby("relationship_group_id", dropna=False):
        if not group_id:
            continue
        canonical_pairs = {
            tuple(pair) for pair in group[["esto_flow", "esto_product"]]
            .dropna()
            .astype(str)
            .itertuples(index=False, name=None)
            if pair[0] or pair[1]
        }
        if len(canonical_pairs) != 1:
            continue
        canonical_pair = next(iter(canonical_pairs))
        if canonical_pair not in set(alias_map.values()):
            continue
        source_pairs = {
            (str(row["source_flow"]).strip(), str(row["source_product"]).strip())
            for _, row in group.iterrows()
            if str(row["source_flow"]).strip() or str(row["source_product"]).strip()
        }
        if len(source_pairs) <= 1:
            continue
        if group["counting_role"].eq("resolved_pair").any():
            continue

        canonical_flow, canonical_product = canonical_pair
        raw_total = pd.to_numeric(group["raw_value"], errors="coerce").fillna(0.0).sum()
        source_pairs = sorted(source_pairs)
        target_pairs = [(canonical_flow, canonical_product)]
        base = group.iloc[0].to_dict()
        base.update({
            "counting_role": "resolved_alias_group",
            "source_flow": " | ".join(f"{flow}" for flow, _ in source_pairs),
            "source_product": " | ".join(f"{product}" for _, product in source_pairs),
            "esto_flow": canonical_flow,
            "esto_product": canonical_product,
            "target_flow": canonical_flow,
            "target_product": canonical_product,
            "relationship_id": "alias_" + hashlib.sha1(
                "|".join([
                    str(group_id), canonical_flow, canonical_product,
                    ";".join(f"{flow}::{product}" for flow, product in source_pairs),
                    canonical_flow + "::" + canonical_product,
                ]).encode("utf-8")
            ).hexdigest()[:16],
            "raw_value": raw_total,
            "converted_value": raw_total,
            "contribution_difference": 0.0,
            "mapping_cardinality": "alias_bucket",
            "value_quality": "alias_normalized",
            "mapping_status": "resolved_alias",
            "exclusion_reason": "placeholder_alias_collapsed",
            "relationship_explanation": (
                "Placeholder alias rows were normalized to one canonical target bucket."
            ),
            "combined_source_value": raw_total,
            "individual_target_values_available": True,
            "involved_source_pairs": " | ".join(
                f"{flow} / {product}" for flow, product in source_pairs
            ),
            "involved_target_pairs": " | ".join(
                f"{flow} / {product}" for flow, product in target_pairs
            ),
        })
        collapsed_rows.append(base)
        collapsed_group_ids.add(str(group_id))

    if not collapsed_rows:
        return contributions

    remaining = working[~working["relationship_group_id"].astype(str).isin(collapsed_group_ids)].copy()
    collapsed_df = pd.DataFrame(collapsed_rows)
    return pd.concat([remaining, collapsed_df], ignore_index=True, sort=False)


def _recalculate_summary_from_contributions(
    contributions: pd.DataFrame,
    summary: pd.DataFrame,
) -> pd.DataFrame:
    """Refresh breakdown counts after alias groups have been collapsed."""
    if summary.empty:
        return summary
    metrics: list[dict[str, Any]] = []
    for check_id, group in contributions.groupby("check_id", dropna=False):
        resolved_mask = group["counting_role"].isin({"resolved_pair", "resolved_alias_group"})
        raw_mask = group["counting_role"].eq("raw_source")
        converted_mask = group["counting_role"].eq("converted_component")
        resolved_rows = group[resolved_mask]
        raw_rows = group[raw_mask]
        converted_rows = group[converted_mask]
        resolved_difference = pd.to_numeric(resolved_rows["contribution_difference"], errors="coerce").fillna(0.0).sum()
        unresolved_raw = pd.to_numeric(raw_rows["raw_value"], errors="coerce").fillna(0.0).sum()
        unresolved_converted = pd.to_numeric(converted_rows["converted_value"], errors="coerce").fillna(0.0).sum()
        breakdown_raw = pd.to_numeric(group["raw_value"], errors="coerce").fillna(0.0).sum()
        breakdown_converted = pd.to_numeric(group["converted_value"], errors="coerce").fillna(0.0).sum()
        breakdown_difference = breakdown_raw - breakdown_converted
        metrics.append({
            "check_id": check_id,
            "breakdown_raw_total": breakdown_raw,
            "breakdown_converted_total": breakdown_converted,
            "breakdown_difference": breakdown_difference,
            "breakdown_remainder": breakdown_difference - float(summary.loc[summary["check_id"].eq(check_id), "check_difference"].iloc[0]),
            "resolved_difference": resolved_difference,
            "resolved_contributor_count": int(resolved_rows.shape[0]),
            "unresolved_raw_total": unresolved_raw,
            "unresolved_converted_total": unresolved_converted,
            "unresolved_difference": unresolved_raw - unresolved_converted,
            "unresolved_source_count": int(raw_rows.shape[0]),
            "unresolved_component_count": int(converted_rows.shape[0]),
            "fully_attributed": bool(raw_rows.empty and converted_rows.empty),
            "lineage_complete": bool(
                abs(breakdown_difference - float(summary.loc[summary["check_id"].eq(check_id), "check_difference"].iloc[0]))
                <= 1e-9
            ),
        })
    metrics_df = pd.DataFrame(metrics)
    updated = summary.drop(columns=[
        "breakdown_raw_total", "breakdown_converted_total", "breakdown_difference",
        "breakdown_remainder", "resolved_difference", "resolved_contributor_count",
        "unresolved_raw_total", "unresolved_converted_total", "unresolved_difference",
        "unresolved_source_count", "unresolved_component_count", "fully_attributed",
        "lineage_complete",
    ], errors="ignore").merge(metrics_df, on="check_id", how="left")
    return updated


def validate_direction_partition(
    raw_partition: pd.DataFrame,
    edges: pd.DataFrame,
    tree_df: pd.DataFrame,
    source_system: str,
    target_system: str,
    direction: str,
    target_variant_family: str = "",
    target_variant: str = "",
    tolerance: float = 0.01,
    alias_map: dict[tuple[str, str], tuple[str, str]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the existing Option-A breakdown on one inverted direction slice."""
    adapted = _structural_edges_for_existing_boundary_builder(edges, source_system)
    boundaries = {
        axis: build_parent_boundaries(adapted, tree_df, source_system, axis)
        for axis in ["flow", "product"]
    }
    projected = project_bijective_values(raw_partition, edges, alias_map)
    target_pairs = set(zip(edges["target_flow"], edges["target_product"]))
    if alias_map:
        target_pairs = {
            _normalize_target_pair(flow, product, alias_map)
            for flow, product in target_pairs
        }
    target_pairs_by_axis = {"flow": target_pairs, "product": target_pairs}
    contributions, summary = build_anchor_contributions(
        raw_partition=raw_partition,
        converted=projected,
        boundaries_by_axis=boundaries,
        converted_components_by_axis=target_pairs_by_axis,
        source_system=source_system,
        tolerance=tolerance,
        statuses=("passed", "failed"),
    )

    # Existing check IDs intentionally remain unchanged in the legacy runner.
    # Directional outputs receive a new content ID that includes both ends.
    id_map: dict[str, str] = {}
    for row in summary.to_dict("records"):
        old_id = row["check_id"]
        key = "|".join([
            "inverted_conservation_v1", direction, source_system, target_system,
            target_variant_family, target_variant,
            str(row["economy"]), str(row["scenario"]), str(row["year"]),
            str(row["validation_axis"]), str(row["parent_code"]),
        ])
        id_map[old_id] = "dirchk_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    if id_map:
        summary["check_id"] = summary["check_id"].map(id_map)
        contributions["check_id"] = contributions["check_id"].map(id_map)

    # A zero is used internally so the existing reconciliation can calculate
    # unplaced mass. Do not publish that zero as a target-branch value: no
    # allocation was made, so the honest branch-level value is unknown.
    unresolved_target = contributions["counting_role"].eq("converted_component")
    contributions.loc[unresolved_target, "converted_value"] = pd.NA

    # Describe each connected source/target set as one relationship group. This
    # preserves the useful combined total even when individual target values
    # cannot be allocated.
    raw_totals = raw_partition.groupby(["source_flow", "source_product"])["value"].sum()
    group_details: dict[tuple[str, str, str], dict[str, Any]] = {}
    for axis, axis_boundaries in boundaries.items():
        for parent, boundary in axis_boundaries.items():
            targets_of, sources_of, _ = _edge_topology(boundary.edges)
            unseen = set(targets_of)
            group_number = 0
            while unseen:
                group_number += 1
                source_stack = [unseen.pop()]
                group_sources: set[tuple[str, str]] = set()
                group_targets: set[tuple[str, str]] = set()
                while source_stack:
                    source_pair = source_stack.pop()
                    if source_pair in group_sources:
                        continue
                    group_sources.add(source_pair)
                    for target_pair in targets_of[source_pair]:
                        if target_pair in group_targets:
                            continue
                        group_targets.add(target_pair)
                        for linked_source in sources_of[target_pair]:
                            if linked_source not in group_sources:
                                unseen.discard(linked_source)
                                source_stack.append(linked_source)
                group_key = "|".join([
                    direction, axis, parent,
                    ";".join(f"{f}::{p}" for f, p in sorted(group_sources)),
                    ";".join(f"{f}::{p}" for f, p in sorted(group_targets)),
                ])
                group_id = "relgrp_" + hashlib.sha1(group_key.encode("utf-8")).hexdigest()[:16]
                is_bijective = len(group_sources) == 1 and len(group_targets) == 1
                total = float(sum(raw_totals.get(pair, 0.0) for pair in group_sources))
                detail = {
                    "relationship_group_id": group_id,
                    "involved_source_pairs": " | ".join(
                        f"{flow} / {product}" for flow, product in sorted(group_sources)
                    ),
                    "involved_target_pairs": " | ".join(
                        f"{flow} / {product}" for flow, product in sorted(group_targets)
                    ),
                    "combined_source_value": total,
                    "individual_target_values_available": bool(is_bijective),
                    "relationship_explanation": (
                        "One source pair maps to one target pair."
                        if is_bijective else
                        f"{total:g} belongs to this combined target set; no individual target allocation is available."
                    ),
                }
                for source_pair in group_sources:
                    group_details[(axis, parent, "S:" + "\x1f".join(source_pair))] = detail
                for target_pair in group_targets:
                    group_details[(axis, parent, "T:" + "\x1f".join(target_pair))] = detail

    def _group_detail(row: pd.Series) -> dict[str, Any]:
        if row["counting_role"] in {"resolved_pair", "raw_source"}:
            key = "S:" + "\x1f".join([str(row["source_flow"]), str(row["source_product"])])
        else:
            key = "T:" + "\x1f".join([str(row["esto_flow"]), str(row["esto_product"])])
        return group_details.get((row["validation_axis"], row["parent_code"], key), {})

    if not contributions.empty:
        group_frame = pd.DataFrame(
            [_group_detail(row) for _, row in contributions.iterrows()],
            index=contributions.index,
        )
        contributions = pd.concat([contributions, group_frame], axis=1)
        contributions = _collapse_alias_groups(contributions, alias_map or {})
        summary = _recalculate_summary_from_contributions(contributions, summary)

    # Keep legacy internal column names while adding explicit target labels.
    for frame in [contributions, summary]:
        frame.insert(1, "direction", direction)
        frame.insert(2, "target_system", target_system)
        frame.insert(3, "target_variant_family", target_variant_family)
        frame.insert(4, "target_variant", target_variant)
        frame.insert(5, "safe_to_sum_across_variants", not bool(target_variant_family))
        frame.insert(6, "variant_status", (
            "verified_alternative_target_variant" if target_variant_family else "not_applicable"
        ))
        frame.insert(7, "effective_validation_status", (
            "verified_alternative_target_variant"
            if target_variant_family else frame["check_status"]
        ))
    if not contributions.empty:
        contributions["target_flow"] = contributions["esto_flow"]
        contributions["target_product"] = contributions["esto_product"]
    return contributions, summary


def build_no_counterpart_audit(
    raw_partition: pd.DataFrame,
    source_without_target: pd.DataFrame,
    target_without_source: pd.DataFrame,
    direction: str,
    source_system: str,
    target_system: str,
    comparison_scope: str,
    tree_df: pd.DataFrame | None = None,
    ninth_fuel_validation: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Report unavailable counterparts without calling them failures."""
    raw_totals = raw_partition.groupby(["source_flow", "source_product"])["value"].sum()
    base = raw_partition.iloc[0]
    subtotal_products: set[str] = set()
    if tree_df is not None and "is_subtotal" in tree_df:
        tree_sub = tree_df[
            tree_df["dataset"].astype(str).str.casefold().eq(source_system.casefold())
            & tree_df["axis"].astype(str).str.casefold().eq("fuel")
            & tree_df["is_subtotal"].astype(str).str.casefold().isin({"true", "1", "yes"})
        ]
        subtotal_products = set(tree_sub["code"].astype(str))

    validation = ninth_fuel_validation.copy() if ninth_fuel_validation is not None else pd.DataFrame()
    if not validation.empty:
        validation["_economy"] = validation["economy"].astype(str).str.replace("_", "", regex=False)
        validation["_year"] = pd.to_numeric(validation["year"], errors="coerce")
    rows: list[dict[str, Any]] = []
    for row in source_without_target.to_dict("records"):
        source_pair = (row["source_flow"], row["source_product"])
        classification = ""
        reason = ""
        validation_difference: Any = pd.NA
        if source_system == "NINTH" and source_pair[1] in subtotal_products:
            matches = validation
            if not matches.empty:
                matches = matches[
                    matches["_economy"].eq(str(base["economy"]).replace("_", ""))
                    & matches["scenario"].astype(str).str.casefold().eq(str(base["scenario"]).casefold())
                    & matches["_year"].eq(pd.to_numeric(base["year"], errors="coerce"))
                    & matches["ninth_sector"].astype(str).eq(source_pair[0])
                    & matches["ninth_fuel"].astype(str).eq(source_pair[1])
                ]
            if matches.empty:
                classification = "verified_subtotal_represented_by_children"
                reason = "Existing Ninth fuel-tree validation found no parent/children mismatch; do not map the subtotal into LEAP."
            else:
                classification = "subtotal_children_mismatch"
                reason = "Existing Ninth fuel-tree validation records a parent/children mismatch; retain the residual for review."
                validation_difference = pd.to_numeric(matches.iloc[0]["difference"], errors="coerce")
        rows.append({
            "direction": direction, "counterpart_state": "source_without_target",
            "source_system": source_system, "target_system": target_system,
            "comparison_scope": comparison_scope, "common_row_id": row["common_row_id"],
            "source_flow": source_pair[0], "source_product": source_pair[1],
            "target_flow": "", "target_product": "",
            "economy": str(base["economy"]), "scenario": str(base["scenario"]),
            "year": base["year"], "source_value": float(raw_totals.get(source_pair, 0.0)),
            "exception_classification": classification,
            "exception_reason": reason,
            "subtotal_validation_difference": validation_difference,
        })
    for row in target_without_source.to_dict("records"):
        rows.append({
            "direction": direction, "counterpart_state": "target_without_source",
            "source_system": source_system, "target_system": target_system,
            "comparison_scope": comparison_scope, "common_row_id": row["common_row_id"],
            "source_flow": "", "source_product": "",
            "target_flow": row["target_flow"], "target_product": row["target_product"],
            "economy": str(base["economy"]), "scenario": str(base["scenario"]),
            "year": base["year"], "source_value": pd.NA,
            "exception_classification": "", "exception_reason": "",
            "subtotal_validation_difference": pd.NA,
        })
    return pd.DataFrame(rows, columns=NO_COUNTERPART_COLUMNS)


def run_inverted_conservation_validation(
    output_dir: Path,
    structural_path: Path = DEFAULT_STRUCTURAL_PATH,
    tree_path: Path = DEFAULT_TREE_PATH,
    ninth_fuel_validation_path: Path = DEFAULT_NINTH_FUEL_VALIDATION_PATH,
    target_variants_path: Path | None = DEFAULT_TARGET_VARIANTS_PATH,
    target_aliases_path: Path | None = DEFAULT_TARGET_ALIASES_PATH,
    raw_paths: dict[str, Path] | None = None,
    economies: set[str] | None = None,
    years_by_system: dict[str, set[int]] | None = None,
    directions: tuple[str, ...] = ("ESTO_TO_LEAP", "NINTH_TO_LEAP"),
    tolerance: float = 0.01,
) -> dict[str, Any]:
    """Write Flavor-A direction summaries, contributors, and counterpart gaps."""
    raw_paths = raw_paths or DEFAULT_RAW_PATHS
    esto_columns = pd.read_csv(raw_paths["ESTO"], nrows=0).columns
    esto_years = sorted(int(column) for column in esto_columns if str(column).isdigit())
    if not esto_years:
        raise ValueError("ESTO source has no year columns; cannot identify its trusted base year.")
    esto_base_year = esto_years[-1]
    years_by_system = dict(years_by_system or {})
    requested_esto_years = years_by_system.get("ESTO")
    if requested_esto_years is not None and set(requested_esto_years) != {esto_base_year}:
        raise ValueError(
            f"ESTO_TO_LEAP is base-year-only: expected {esto_base_year}, "
            f"received {sorted(requested_esto_years)}."
        )
    years_by_system["ESTO"] = {esto_base_year}
    structural = pd.read_csv(structural_path, dtype=object)
    tree = pd.read_csv(tree_path, dtype=object)
    ninth_fuel_validation = pd.read_csv(ninth_fuel_validation_path, dtype=object)
    target_variants = load_target_variants(target_variants_path)
    target_aliases = load_target_aliases(target_aliases_path)
    alias_map = _build_alias_map(target_aliases)
    output_dir = Path(output_dir)
    staging = output_dir.with_name(output_dir.name + ".building")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    contribution_frames: list[pd.DataFrame] = []
    summary_frames: list[pd.DataFrame] = []
    counterpart_frames: list[pd.DataFrame] = []
    variant_coverage_frames: list[pd.DataFrame] = []
    for direction in directions:
        config = DIRECTION_CONFIG[direction]
        source_system = config["source_system"]
        target_system = config["target_system"]
        comparison_scope = config["comparison_scope"]
        edges, source_gaps, target_gaps = compose_direction_edges(
            structural, source_system, target_system, comparison_scope, alias_map
        )
        edge_partitions = partition_edges_by_target_variant(
            edges, target_system, target_variants
        )
        variant_coverage_frames.append(build_variant_coverage_audit(
            edge_partitions, direction, source_system, target_system
        ))
        years = years_by_system.get(source_system)
        for raw_partition in iter_raw_partitions(
            source_system, raw_paths[source_system], economies, years
        ):
            for variant_family, variant, variant_edges in edge_partitions:
                contributions, summary = validate_direction_partition(
                    raw_partition, variant_edges, tree, source_system, target_system,
                    direction, variant_family, variant, tolerance, alias_map,
                )
                contribution_frames.append(contributions)
                summary_frames.append(summary)
            counterpart_frames.append(build_no_counterpart_audit(
                raw_partition, source_gaps, target_gaps, direction,
                source_system, target_system, comparison_scope,
                tree, ninth_fuel_validation,
            ))

    contributions = pd.concat(contribution_frames, ignore_index=True) if contribution_frames else pd.DataFrame()
    summary = pd.concat(summary_frames, ignore_index=True) if summary_frames else pd.DataFrame()
    counterpart = pd.concat(counterpart_frames, ignore_index=True) if counterpart_frames else pd.DataFrame(columns=NO_COUNTERPART_COLUMNS)
    variant_coverage = pd.concat(variant_coverage_frames, ignore_index=True) if variant_coverage_frames else pd.DataFrame(columns=VARIANT_COVERAGE_COLUMNS)
    contributions.to_csv(staging / "inverted_conservation_contributors.csv", index=False)
    summary.to_csv(staging / "inverted_conservation_summary.csv", index=False)
    counterpart.to_csv(staging / "inverted_conservation_no_counterpart.csv", index=False)
    variant_coverage.to_csv(staging / "inverted_conservation_variant_coverage.csv", index=False)
    manifest = {
        "status": "complete", "directions": list(directions),
        "checks": int(len(summary)), "contributor_rows": int(len(contributions)),
        "no_counterpart_rows": int(len(counterpart)),
        "variant_coverage_rows": int(len(variant_coverage)),
        "variant_coverage_mismatches": int(
            variant_coverage["variant_coverage_status"].eq("coverage_mismatch").sum()
        ) if not variant_coverage.empty else 0,
        "esto_base_year": esto_base_year,
        "max_abs_breakdown_remainder": (
            float(summary["breakdown_remainder"].abs().max()) if not summary.empty else 0.0
        ),
        "ninth_to_esto": "reuses existing ESTO-base anchor reconciliation; no duplicate run",
        "leap_values_read": False,
    }
    (staging / "inverted_conservation_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.move(str(staging), str(output_dir))
    return manifest


#%%
RUN_20USA_BASE_YEAR = False

if RUN_20USA_BASE_YEAR:
    VALIDATION_RESULT = run_inverted_conservation_validation(
        output_dir=REPO_ROOT / "results/common_esto/inverted_conservation",
        economies={"20USA"},
        years_by_system={"ESTO": {2023}, "NINTH": {2023}},
    )

#%%
