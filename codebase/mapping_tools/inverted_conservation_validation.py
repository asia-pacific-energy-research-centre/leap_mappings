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
DEFAULT_RAW_PATHS = {
    "ESTO": REPO_ROOT / "data/00APEC_2025_low_with_subtotals.csv",
    "NINTH": REPO_ROOT / "data/merged_file_energy_ALL_20251106.csv",
}

NO_COUNTERPART_COLUMNS = [
    "direction", "counterpart_state", "source_system", "target_system",
    "comparison_scope", "common_row_id", "source_flow", "source_product",
    "target_flow", "target_product", "economy", "scenario", "year", "source_value",
]


def compose_direction_edges(
    structural_df: pd.DataFrame,
    source_system: str,
    target_system: str,
    comparison_scope: str,
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


def project_bijective_values(raw_partition: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    """Project only exclusive one-to-one source values onto target pairs."""
    edge_tuples = tuple(
        edges[["source_flow", "source_product", "target_flow", "target_product", "relationship_id"]]
        .itertuples(index=False, name=None)
    )
    targets_of, sources_of, _ = _edge_topology(edge_tuples)
    raw_totals = raw_partition.groupby(["source_flow", "source_product"])["value"].sum()
    rows: list[dict[str, Any]] = []
    base = raw_partition.iloc[0]
    for source_pair, targets in targets_of.items():
        if len(targets) != 1:
            continue
        target_pair = next(iter(targets))
        if len(sources_of[target_pair]) != 1:
            continue
        rows.append({
            "source_system": str(base["source_system"]),
            "economy": str(base["economy"]),
            "scenario": str(base["scenario"]),
            "year": base["year"],
            "esto_flow": target_pair[0],
            "esto_product": target_pair[1],
            "value": float(raw_totals.get(source_pair, 0.0)),
        })
    return pd.DataFrame(rows, columns=[
        "source_system", "economy", "scenario", "year",
        "esto_flow", "esto_product", "value",
    ])


def validate_direction_partition(
    raw_partition: pd.DataFrame,
    edges: pd.DataFrame,
    tree_df: pd.DataFrame,
    source_system: str,
    target_system: str,
    direction: str,
    tolerance: float = 0.01,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the existing Option-A breakdown on one inverted direction slice."""
    adapted = _structural_edges_for_existing_boundary_builder(edges, source_system)
    boundaries = {
        axis: build_parent_boundaries(adapted, tree_df, source_system, axis)
        for axis in ["flow", "product"]
    }
    projected = project_bijective_values(raw_partition, edges)
    target_pairs = set(zip(edges["target_flow"], edges["target_product"]))
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

    # Keep legacy internal column names while adding explicit target labels.
    for frame in [contributions, summary]:
        frame.insert(1, "direction", direction)
        frame.insert(2, "target_system", target_system)
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
) -> pd.DataFrame:
    """Report unavailable counterparts without calling them failures."""
    raw_totals = raw_partition.groupby(["source_flow", "source_product"])["value"].sum()
    base = raw_partition.iloc[0]
    rows: list[dict[str, Any]] = []
    for row in source_without_target.to_dict("records"):
        source_pair = (row["source_flow"], row["source_product"])
        rows.append({
            "direction": direction, "counterpart_state": "source_without_target",
            "source_system": source_system, "target_system": target_system,
            "comparison_scope": comparison_scope, "common_row_id": row["common_row_id"],
            "source_flow": source_pair[0], "source_product": source_pair[1],
            "target_flow": "", "target_product": "",
            "economy": str(base["economy"]), "scenario": str(base["scenario"]),
            "year": base["year"], "source_value": float(raw_totals.get(source_pair, 0.0)),
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
        })
    return pd.DataFrame(rows, columns=NO_COUNTERPART_COLUMNS)


def run_inverted_conservation_validation(
    output_dir: Path,
    structural_path: Path = DEFAULT_STRUCTURAL_PATH,
    tree_path: Path = DEFAULT_TREE_PATH,
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
    output_dir = Path(output_dir)
    staging = output_dir.with_name(output_dir.name + ".building")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    contribution_frames: list[pd.DataFrame] = []
    summary_frames: list[pd.DataFrame] = []
    counterpart_frames: list[pd.DataFrame] = []
    for direction in directions:
        config = DIRECTION_CONFIG[direction]
        source_system = config["source_system"]
        target_system = config["target_system"]
        comparison_scope = config["comparison_scope"]
        edges, source_gaps, target_gaps = compose_direction_edges(
            structural, source_system, target_system, comparison_scope
        )
        years = years_by_system.get(source_system)
        for raw_partition in iter_raw_partitions(
            source_system, raw_paths[source_system], economies, years
        ):
            contributions, summary = validate_direction_partition(
                raw_partition, edges, tree, source_system, target_system,
                direction, tolerance,
            )
            contribution_frames.append(contributions)
            summary_frames.append(summary)
            counterpart_frames.append(build_no_counterpart_audit(
                raw_partition, source_gaps, target_gaps, direction,
                source_system, target_system, comparison_scope,
            ))

    contributions = pd.concat(contribution_frames, ignore_index=True) if contribution_frames else pd.DataFrame()
    summary = pd.concat(summary_frames, ignore_index=True) if summary_frames else pd.DataFrame()
    counterpart = pd.concat(counterpart_frames, ignore_index=True) if counterpart_frames else pd.DataFrame(columns=NO_COUNTERPART_COLUMNS)
    contributions.to_csv(staging / "inverted_conservation_contributors.csv", index=False)
    summary.to_csv(staging / "inverted_conservation_summary.csv", index=False)
    counterpart.to_csv(staging / "inverted_conservation_no_counterpart.csv", index=False)
    manifest = {
        "status": "complete", "directions": list(directions),
        "checks": int(len(summary)), "contributor_rows": int(len(contributions)),
        "no_counterpart_rows": int(len(counterpart)),
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
