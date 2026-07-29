#%%
"""Run the isolated separate-axis mapping contract exploration.

The workflow generates review-only evidence under
``results/separate_axis_mapping_exploration``. It never edits either mapping
workbook and keeps the production Stage-1/Stage-2 modules unchanged.
"""

#%%
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any

import pandas as pd


# --- Stable paths -----------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.separate_axis_mapping_exploration_functions import (  # noqa: E402
    RELATIONSHIP_KEY_COLUMNS,
    add_target_pair_metadata,
    analyse_product_context_dependence,
    apply_generated_overrides,
    build_added_esto_pair_review,
    build_common_graph_membership_in_memory,
    build_power_process_case_evidence,
    build_ninth_valid_pair_registry_bundle,
    build_registry_scope_lookups,
    build_stage1_relationships_in_memory,
    build_valid_pair_registry,
    build_observed_leap_pair_evidence,
    compare_common_structure_membership,
    compare_compiled_relationships,
    compare_raw_target_components,
    compare_registry_snapshots,
    compile_axis_relationships,
    derive_axis_mappings,
    inventory_leap_templates,
    load_active_mapping_contract,
    write_manifest,
)

WORKBOOK_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
ESTO_2024_PATH = REPO_ROOT / "data" / "00APEC_2024_low_with_subtotals.csv"
ESTO_2025_PATH = REPO_ROOT / "data" / "00APEC_2025_low_with_subtotals.csv"
ESTO_EXTENDED_PATH = REPO_ROOT / "data" / "esto_extended.csv"
NINTH_PATH = REPO_ROOT / "data" / "merged_file_energy_ALL_20251106.csv"
OUTPUT_ROOT = REPO_ROOT / "results" / "separate_axis_mapping_exploration"


def _find_github_root(repo_root: Path) -> Path:
    """Find the shared ``github`` directory above a repo or worktree."""
    for candidate in [repo_root, *repo_root.parents]:
        if candidate.name.casefold() == "github":
            return candidate
    raise FileNotFoundError(f"Could not locate github root above {repo_root}")


GITHUB_ROOT = _find_github_root(REPO_ROOT)
LEAP_INITIALISATION_ROOT = GITHUB_ROOT / "leap_initialisation"
LEAP_TEMPLATE_DIR = LEAP_INITIALISATION_ROOT / "data" / "leap_export_templates"
LEAP_EXPORT_ROOT = (
    LEAP_INITIALISATION_ROOT / "data" / "leap balances exports"
)
POWER_REVIEW_WORKBOOK_PATH = (
    GITHUB_ROOT
    / "leap_mappings"
    / "config"
    / "outlook_mappings_master todo.xlsx"
)


# --- Output helpers ---------------------------------------------------------

def _write_csv(frame: pd.DataFrame, relative_path: str) -> Path:
    """Write one review-only CSV below the exploration output root."""
    path = OUTPUT_ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def _manifest_path(path: Path) -> str:
    """Prefer a stable repo-relative path in generated manifests."""
    path = Path(path)
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _summarise_status(
    frame: pd.DataFrame,
    status_column: str,
    category: str,
) -> pd.DataFrame:
    """Return narrow metric rows for one status table."""
    if frame.empty or status_column not in frame:
        return pd.DataFrame(
            [{"category": category, "metric": "empty", "value": 0}]
        )
    summary = (
        frame.groupby(status_column, dropna=False)
        .size()
        .reset_index(name="value")
        .rename(columns={status_column: "metric"})
    )
    summary.insert(0, "category", category)
    return summary


def _common_structure_summary(
    comparison: pd.DataFrame,
    category: str,
) -> pd.DataFrame:
    """Summarise component membership comparison rows."""
    return _summarise_status(comparison, "membership_status", category)


def _assert_required_sources() -> None:
    """Fail early with every missing configured source."""
    required = [
        WORKBOOK_PATH,
        ESTO_2024_PATH,
        ESTO_2025_PATH,
        ESTO_EXTENDED_PATH,
        NINTH_PATH,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Configured exploration sources are missing:\n- "
            + "\n- ".join(missing)
        )


def _cached_registry_manifest(
    registry: pd.DataFrame,
    source_path: Path,
    dataset: str,
    scenario_scope: str,
) -> dict[str, Any]:
    """Reconstruct a reproducible manifest from a completed cached snapshot."""
    source_fingerprint = (
        str(registry["source_fingerprint"].iloc[0])
        if not registry.empty
        else ""
    )
    source_vintage = (
        str(registry["source_vintage"].iloc[0])
        if not registry.empty
        else ""
    )
    return {
        "dataset": dataset,
        "scenario_scope": scenario_scope,
        "zero_tolerance": 1e-9,
        "source_path": _manifest_path(source_path),
        "source_vintage": source_vintage,
        "source_fingerprint": source_fingerprint,
        "source_size_bytes": source_path.stat().st_size,
        "pair_count": len(registry),
        "data_valid_pair_count": int(
            registry["pair_status"].eq("data_valid").sum()
        ),
        "zero_only_pair_count": int(
            registry["pair_status"].eq("zero_only").sum()
        ),
        "review_status": "generated_unreviewed",
        "refresh_method": "reused_completed_snapshot",
    }


def _load_cached_registry_snapshots() -> dict[str, tuple[pd.DataFrame, dict[str, Any]]] | None:
    """Load the complete registry pack when every expected snapshot exists."""
    specs = {
        "esto_2024": (
            OUTPUT_ROOT / "valid_pairs" / "esto_2024.csv",
            ESTO_2024_PATH,
            "ESTO",
            "not_applicable",
        ),
        "esto_2025": (
            OUTPUT_ROOT / "valid_pairs" / "esto_2025.csv",
            ESTO_2025_PATH,
            "ESTO",
            "not_applicable",
        ),
        "esto_extended": (
            OUTPUT_ROOT / "valid_pairs" / "esto_extended.csv",
            ESTO_EXTENDED_PATH,
            "ESTO_EXTENDED",
            "not_applicable",
        ),
        "ninth_all": (
            OUTPUT_ROOT / "valid_pairs" / "ninth_all_scenarios.csv",
            NINTH_PATH,
            "NINTH",
            "all",
        ),
        "ninth_reference": (
            OUTPUT_ROOT / "valid_pairs" / "ninth_reference.csv",
            NINTH_PATH,
            "NINTH",
            "reference",
        ),
        "ninth_target": (
            OUTPUT_ROOT / "valid_pairs" / "ninth_target.csv",
            NINTH_PATH,
            "NINTH",
            "target",
        ),
    }
    if not all(path.exists() and path.stat().st_size > 0 for path, *_ in specs.values()):
        return None
    cached: dict[str, tuple[pd.DataFrame, dict[str, Any]]] = {}
    for name, (path, source_path, dataset, scope) in specs.items():
        registry = pd.read_csv(path, low_memory=False)
        cached[name] = (
            registry,
            _cached_registry_manifest(
                registry,
                source_path,
                dataset,
                scope,
            ),
        )
    return cached


# --- Main exploration -------------------------------------------------------

def run_separate_axis_exploration(
    *,
    include_leap_authority_evidence: bool = True,
    include_power_review_case: bool = True,
    reuse_existing_registry_snapshots: bool = True,
    reuse_existing_semantic_proof: bool = True,
) -> dict[str, Any]:
    """Generate the isolated evidence pack and return its manifest."""
    _assert_required_sources()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    cached = (
        _load_cached_registry_snapshots()
        if reuse_existing_registry_snapshots
        else None
    )
    if cached is not None:
        print("Reusing completed generated registry snapshots...")
        esto_2024, esto_2024_manifest = cached["esto_2024"]
        esto_2025, esto_2025_manifest = cached["esto_2025"]
        esto_extended, esto_extended_manifest = cached["esto_extended"]
        ninth_all, ninth_all_manifest = cached["ninth_all"]
        ninth_reference, ninth_reference_manifest = cached["ninth_reference"]
        ninth_target, ninth_target_manifest = cached["ninth_target"]
    else:
        print("Building ESTO valid-pair registries...")
        esto_2024, esto_2024_manifest = build_valid_pair_registry(
            ESTO_2024_PATH,
            "ESTO",
        )
        esto_2025, esto_2025_manifest = build_valid_pair_registry(
            ESTO_2025_PATH,
            "ESTO",
        )
        esto_extended, esto_extended_manifest = build_valid_pair_registry(
            ESTO_EXTENDED_PATH,
            "ESTO_EXTENDED",
        )

        print("Building Ninth valid-pair registries by scenario...")
        ninth_bundle = build_ninth_valid_pair_registry_bundle(NINTH_PATH)
        ninth_all, ninth_all_manifest = ninth_bundle["all"]
        ninth_reference, ninth_reference_manifest = ninth_bundle["reference"]
        ninth_target, ninth_target_manifest = ninth_bundle["target"]

    for source_path, registry_manifest in [
        (ESTO_2024_PATH, esto_2024_manifest),
        (ESTO_2025_PATH, esto_2025_manifest),
        (ESTO_EXTENDED_PATH, esto_extended_manifest),
        (NINTH_PATH, ninth_all_manifest),
        (NINTH_PATH, ninth_reference_manifest),
        (NINTH_PATH, ninth_target_manifest),
    ]:
        registry_manifest["source_path"] = _manifest_path(source_path)

    esto_delta = compare_registry_snapshots(esto_2024, esto_2025)
    ninth_scenario_delta = compare_registry_snapshots(
        ninth_reference,
        ninth_target,
    )
    _write_csv(esto_2024, "valid_pairs/esto_2024.csv")
    _write_csv(esto_2025, "valid_pairs/esto_2025.csv")
    _write_csv(esto_extended, "valid_pairs/esto_extended.csv")
    _write_csv(ninth_all, "valid_pairs/ninth_all_scenarios.csv")
    _write_csv(ninth_reference, "valid_pairs/ninth_reference.csv")
    _write_csv(ninth_target, "valid_pairs/ninth_target.csv")
    _write_csv(esto_delta, "deltas/esto_2024_to_2025.csv")
    _write_csv(
        ninth_scenario_delta,
        "deltas/ninth_reference_to_target.csv",
    )

    print("Factorising the accepted pair contract and compiling strict pairs...")
    current, incomplete = load_active_mapping_contract(WORKBOOK_PATH)
    flow_mappings, product_mappings = derive_axis_mappings(current)
    registry_lookups = build_registry_scope_lookups(
        esto_2025,
        ninth_all,
        esto_extended,
    )
    candidates = compile_axis_relationships(
        current,
        flow_mappings,
        product_mappings,
        registry_lookups,
    )
    relationship_comparison, source_summary, generated_overrides = (
        compare_compiled_relationships(current, candidates)
    )
    compiled_after_overrides = apply_generated_overrides(
        candidates,
        generated_overrides,
    )
    exact_set_reproduced = (
        set(
            compiled_after_overrides[RELATIONSHIP_KEY_COLUMNS].itertuples(
                index=False,
                name=None,
            )
        )
        == set(
            current[RELATIONSHIP_KEY_COLUMNS].itertuples(
                index=False,
                name=None,
            )
        )
    )

    product_context = analyse_product_context_dependence(current, source_summary)
    _write_csv(flow_mappings, "relationships/flow_axis_mappings.csv")
    _write_csv(product_mappings, "relationships/product_axis_mappings.csv")
    _write_csv(candidates, "relationships/compiled_candidates.csv")
    _write_csv(
        relationship_comparison,
        "relationships/current_vs_compiled.csv",
    )
    _write_csv(
        source_summary,
        "relationships/source_pair_reproduction.csv",
    )
    _write_csv(
        generated_overrides,
        "relationships/generated_pair_overrides_review_only.csv",
    )
    _write_csv(incomplete, "diagnostics/incomplete_active_mapping_rows.csv")
    _write_csv(
        product_context,
        "diagnostics/product_context_dependence.csv",
    )

    semantic_paths = {
        "raw_axis": OUTPUT_ROOT / "diagnostics" / "raw_components_axis_only.csv",
        "raw_lossless": OUTPUT_ROOT / "diagnostics" / "raw_components_after_overrides.csv",
        "common_axis": OUTPUT_ROOT / "diagnostics" / "common_membership_axis_only.csv",
        "common_lossless": OUTPUT_ROOT / "diagnostics" / "common_membership_after_overrides.csv",
    }
    semantic_cache_available = reuse_existing_semantic_proof and all(
        path.exists() and path.stat().st_size > 0
        for path in semantic_paths.values()
    )
    if semantic_cache_available:
        print("Reusing completed rollup-expanded semantic proof...")
        raw_axis_components = pd.read_csv(semantic_paths["raw_axis"], low_memory=False)
        raw_lossless_components = pd.read_csv(
            semantic_paths["raw_lossless"],
            low_memory=False,
        )
        common_axis_comparison = pd.read_csv(
            semantic_paths["common_axis"],
            low_memory=False,
        )
        common_lossless_comparison = pd.read_csv(
            semantic_paths["common_lossless"],
            low_memory=False,
        )
    else:
        print("Running current Stage 1 and Stage 2 in memory...")
        metadata_registries = {
            ("ESTO", "ESTO"): esto_2025,
            ("ESTO", "ESTO_EXTENDED"): esto_extended,
            ("ESTO", "BOTH"): pd.concat(
                [esto_2025, esto_extended],
                ignore_index=True,
            ),
            ("NINTH", "NINTH"): ninth_all,
        }
        current_with_metadata = add_target_pair_metadata(
            current[RELATIONSHIP_KEY_COLUMNS],
            current,
            metadata_registries,
        )
        axis_only = candidates.loc[
            candidates["registry_allowed"],
            RELATIONSHIP_KEY_COLUMNS,
        ].drop_duplicates()
        axis_only = add_target_pair_metadata(
            axis_only,
            current,
            metadata_registries,
        )
        compiled_lossless = add_target_pair_metadata(
            compiled_after_overrides,
            current,
            metadata_registries,
        )

        current_stage1, current_esto_overrides, _ = (
            build_stage1_relationships_in_memory(
                current_with_metadata,
                WORKBOOK_PATH,
            )
        )
        axis_stage1, axis_esto_overrides, _ = (
            build_stage1_relationships_in_memory(axis_only, WORKBOOK_PATH)
        )
        if exact_set_reproduced:
            lossless_stage1 = current_stage1
            lossless_esto_overrides = current_esto_overrides
        else:
            lossless_stage1, lossless_esto_overrides, _ = (
                build_stage1_relationships_in_memory(
                    compiled_lossless,
                    WORKBOOK_PATH,
                )
            )

        current_common = build_common_graph_membership_in_memory(
            current_stage1,
            WORKBOOK_PATH,
            current_esto_overrides,
        )
        axis_common = build_common_graph_membership_in_memory(
            axis_stage1,
            WORKBOOK_PATH,
            axis_esto_overrides,
        )
        lossless_common = (
            current_common.copy()
            if exact_set_reproduced
            else build_common_graph_membership_in_memory(
                lossless_stage1,
                WORKBOOK_PATH,
                lossless_esto_overrides,
            )
        )
        raw_axis_components = compare_raw_target_components(current, axis_only)
        raw_lossless_components = compare_raw_target_components(
            current,
            compiled_lossless,
        )
        common_axis_comparison = compare_common_structure_membership(
            current_common,
            axis_common,
        )
        common_lossless_comparison = compare_common_structure_membership(
            current_common,
            lossless_common,
        )
        _write_csv(
            raw_axis_components,
            "diagnostics/raw_components_axis_only.csv",
        )
        _write_csv(
            raw_lossless_components,
            "diagnostics/raw_components_after_overrides.csv",
        )
        _write_csv(
            common_axis_comparison,
            "diagnostics/common_membership_axis_only.csv",
        )
        _write_csv(
            common_lossless_comparison,
            "diagnostics/common_membership_after_overrides.csv",
        )

    added_review = build_added_esto_pair_review(
        esto_delta,
        current,
        candidates,
        ninth_all,
    )
    _write_csv(
        added_review,
        "deltas/new_esto_pair_mapping_review.csv",
    )

    leap_template_count = 0
    leap_observed_pair_count = 0
    if include_leap_authority_evidence:
        print("Collecting LEAP template and observed-export authority evidence...")
        template_inventory, template_branches = inventory_leap_templates(
            LEAP_TEMPLATE_DIR
        )
        observed_leap, observed_files = build_observed_leap_pair_evidence(
            LEAP_EXPORT_ROOT
        )
        leap_template_count = len(template_inventory)
        leap_observed_pair_count = len(observed_leap)
        _write_csv(
            template_inventory,
            "leap_authority/template_inventory.csv",
        )
        _write_csv(
            template_branches,
            "leap_authority/template_branch_support.csv",
        )
        _write_csv(
            observed_leap,
            "leap_authority/observed_pair_evidence.csv",
        )
        _write_csv(
            observed_files,
            "leap_authority/observed_export_inventory.csv",
        )

    power_group_count = 0
    if include_power_review_case:
        print("Testing the read-only 27-group power-process review case...")
        power_groups, power_mappings = build_power_process_case_evidence(
            POWER_REVIEW_WORKBOOK_PATH,
            esto_2025,
            esto_extended,
        )
        power_group_count = len(power_groups)
        _write_csv(
            power_groups,
            "power_process/power_process_group_evidence.csv",
        )
        _write_csv(
            power_mappings,
            "power_process/power_process_mapping_evidence.csv",
        )

    summaries = [
        _summarise_status(
            relationship_comparison,
            "relationship_status",
            "relationship_reproduction",
        ),
        _summarise_status(
            source_summary,
            "reproduction_status",
            "source_pair_reproduction",
        ),
        _summarise_status(
            esto_delta,
            "delta_status",
            "esto_vintage_delta",
        ),
        _summarise_status(
            ninth_scenario_delta,
            "delta_status",
            "ninth_scenario_delta",
        ),
        _summarise_status(
            product_context,
            "review_status",
            "product_context_dependence",
        ),
        _common_structure_summary(
            common_axis_comparison,
            "common_membership_axis_only",
        ),
        _common_structure_summary(
            common_lossless_comparison,
            "common_membership_after_overrides",
        ),
    ]
    summary = pd.concat(summaries, ignore_index=True)
    _write_csv(summary, "summary.csv")

    unresolved_product_context_count = int(
        product_context["review_status"]
        .eq("unresolved_flow_qualified_product_semantics")
        .sum()
        if not product_context.empty
        else 0
    )
    lossless_common_changes = int(
        (~common_lossless_comparison["membership_status"].eq("unchanged")).sum()
    )
    manifest = {
        "prototype_status": (
            "stop_condition_requires_decision"
            if unresolved_product_context_count > 0 or lossless_common_changes > 0
            else "representation_proof_complete"
        ),
        "canonical_workbook_path": _manifest_path(WORKBOOK_PATH),
        "canonical_workbook_was_modified": False,
        "exact_pair_relationship_set_reproduced_after_generated_overrides": (
            exact_set_reproduced
        ),
        "current_relationship_count": len(current),
        "compiled_registry_allowed_relationship_count": int(
            candidates["registry_allowed"].sum()
        ),
        "generated_pair_override_count": len(generated_overrides),
        "unresolved_product_context_count": unresolved_product_context_count,
        "common_membership_change_count_after_overrides": lossless_common_changes,
        "leap_template_count": leap_template_count,
        "leap_observed_pair_count": leap_observed_pair_count,
        "power_process_group_count": power_group_count,
        "registry_manifests": {
            "esto_2024": esto_2024_manifest,
            "esto_2025": esto_2025_manifest,
            "esto_extended": esto_extended_manifest,
            "ninth_all": ninth_all_manifest,
            "ninth_reference": ninth_reference_manifest,
            "ninth_target": ninth_target_manifest,
        },
    }
    write_manifest(OUTPUT_ROOT / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2))
    return manifest


# --- Frequently changed run flags ------------------------------------------

RUN_FULL_EXPLORATION = True
INCLUDE_LEAP_AUTHORITY_EVIDENCE = True
INCLUDE_POWER_REVIEW_CASE = True
REUSE_EXISTING_REGISTRY_SNAPSHOTS = True
REUSE_EXISTING_SEMANTIC_PROOF = True


#%%
if RUN_FULL_EXPLORATION:
    try:
        EXPLORATION_MANIFEST = run_separate_axis_exploration(
            include_leap_authority_evidence=INCLUDE_LEAP_AUTHORITY_EVIDENCE,
            include_power_review_case=INCLUDE_POWER_REVIEW_CASE,
            reuse_existing_registry_snapshots=REUSE_EXISTING_REGISTRY_SNAPSHOTS,
            reuse_existing_semantic_proof=REUSE_EXISTING_SEMANTIC_PROOF,
        )
    except Exception:
        traceback.print_exc()
        raise

#%%
