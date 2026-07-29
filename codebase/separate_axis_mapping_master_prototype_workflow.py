#%%
"""Build the review-only single-axis master-mapping workbook data pack.

The prototype bootstraps sector/flow and fuel/product axes from the maintained
pair sheets, validates the no-within-axis-many-to-many rule, combines the axes
only across exact source and target pair universes, and emits compatibility
views shaped like the three maintained pair sheets.

It never edits ``config/outlook_mappings_master.xlsx``. LEAP exact-pair
authority is generated from all current economy export templates plus the
temporary detailed demand/power branch inventory.
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
    analyse_axis_components,
    annotate_pair_universe_temporal_evidence,
    build_compiled_mapping_sheet_frames,
    build_registry_scope_lookups,
    compare_compiled_relationships,
    compile_axis_relationships,
    derive_required_reviewed_extra_pairs,
    expand_pair_universe_with_rollups,
    load_active_mapping_contract,
    load_or_bootstrap_editable_axis_contract,
    merge_reviewed_extra_pairs,
)
from codebase.mapping_tools.leap_pair_registry import (  # noqa: E402
    load_or_refresh_leap_pair_registry,
)

WORKBOOK_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
EDITABLE_AXIS_WORKBOOK_PATH = (
    REPO_ROOT / "config" / "outlook_mappings_single_axis_prototype.xlsx"
)
EXPLORATION_RESULTS_ROOT = (
    REPO_ROOT / "results" / "separate_axis_mapping_exploration"
)
OUTPUT_ROOT = (
    REPO_ROOT / "outputs" / "separate_axis_mapping_prototype_20260729"
)
OUTPUT_DATA_ROOT = OUTPUT_ROOT / "data"

REGISTRY_PATHS = {
    "ESTO": EXPLORATION_RESULTS_ROOT / "valid_pairs" / "esto_2025.csv",
    "ESTO_EXTENDED": (
        EXPLORATION_RESULTS_ROOT / "valid_pairs" / "esto_extended.csv"
    ),
    "NINTH": (
        EXPLORATION_RESULTS_ROOT
        / "valid_pairs"
        / "ninth_all_scenarios.csv"
    ),
}


def _github_checkout(repo_name: str) -> Path:
    """Resolve a main checkout from either a main repo or repo worktree."""
    candidates = [
        REPO_ROOT.parent / repo_name,
        REPO_ROOT.parent.parent / repo_name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


LEAP_INITIALISATION_ROOT = _github_checkout("leap_initialisation")
LEAP_MAPPINGS_MAIN_ROOT = _github_checkout("leap_mappings")
LEAP_TEMPLATE_DIR = (
    LEAP_INITIALISATION_ROOT / "data" / "leap_export_templates"
)
NEW_LEAP_ROWS_WORKBOOK_PATH = (
    LEAP_MAPPINGS_MAIN_ROOT / "data" / "temp" / "new leap rows.xlsx"
)
LEAP_REGISTRY_PATH = (
    EXPLORATION_RESULTS_ROOT / "valid_pairs" / "leap_layered.csv"
)
LEAP_REGISTRY_MANIFEST_PATH = (
    EXPLORATION_RESULTS_ROOT
    / "valid_pairs"
    / "leap_layered_manifest.json"
)
LEAP_REGISTRY_DIAGNOSTICS_PATH = (
    EXPLORATION_RESULTS_ROOT
    / "valid_pairs"
    / "leap_layered_excluded_leaves.csv"
)
OBSERVED_LEAP_PAIR_EVIDENCE_PATH = (
    EXPLORATION_RESULTS_ROOT
    / "leap_authority"
    / "observed_pair_evidence.csv"
)

EXTRA_PAIR_SHEET_SPECS = {
    "LEAP": {
        "sheet": "extra_leap_key_pairs",
        "flow_column": "leap_sector",
        "product_column": "leap_fuel",
    },
    "ESTO": {
        "sheet": "extra_esto_key_pairs",
        "flow_column": "esto_flow",
        "product_column": "esto_product",
    },
    "ESTO_EXTENDED": {
        "sheet": "extra_esto_extended_pairs",
        "flow_column": "esto_flow",
        "product_column": "esto_product",
    },
    "NINTH": {
        "sheet": "extra_ninth_key_pairs",
        "flow_column": "ninth_sector",
        "product_column": "ninth_fuel",
    },
}


# --- Helpers ----------------------------------------------------------------

def _write_csv(frame: pd.DataFrame, filename: str) -> Path:
    """Write one workbook-source table and return its path."""
    path = OUTPUT_DATA_ROOT / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def _relative_output_path(path: Path) -> str:
    """Return a stable path relative to the workbook output root."""
    return Path(path).resolve().relative_to(OUTPUT_ROOT.resolve()).as_posix()


def _assert_inputs() -> None:
    """Fail with every missing prerequisite rather than one at a time."""
    required = [
        WORKBOOK_PATH,
        LEAP_TEMPLATE_DIR,
        NEW_LEAP_ROWS_WORKBOOK_PATH,
        *REGISTRY_PATHS.values(),
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Run the completed separate-axis registry exploration first. "
            "Missing prototype inputs:\n- "
            + "\n- ".join(missing)
        )


def _load_pair_universes(
    historical_boundary_year: int,
    force_leap_registry_refresh: bool,
    current_relationships: pd.DataFrame,
) -> tuple[
    dict[str, pd.DataFrame],
    dict[str, Any],
    dict[str, pd.DataFrame],
]:
    """Load and annotate exact generated pair universes."""
    universes: dict[str, pd.DataFrame] = {}
    for dataset, path in REGISTRY_PATHS.items():
        registry = pd.read_csv(path, low_memory=False)
        universes[dataset] = annotate_pair_universe_temporal_evidence(
            registry,
            historical_boundary_year,
        )
    leap_registry, leap_manifest = load_or_refresh_leap_pair_registry(
        template_dir=LEAP_TEMPLATE_DIR,
        new_rows_workbook_path=NEW_LEAP_ROWS_WORKBOOK_PATH,
        registry_path=LEAP_REGISTRY_PATH,
        manifest_path=LEAP_REGISTRY_MANIFEST_PATH,
        diagnostics_path=LEAP_REGISTRY_DIAGNOSTICS_PATH,
        force_refresh=force_leap_registry_refresh,
    )
    universes["LEAP"] = leap_registry
    rollup_specs = {
        "LEAP": {
            "sheet": "leap_rollup_rules",
            "input_flow": "input_leap_sector_name_full_path",
            "input_product": "input_raw_leap_fuel_name",
            "rolled_flow": "rolled_leap_sector_name_full_path",
            "rolled_product": "rolled_raw_leap_fuel_name",
            "scope": None,
        },
        "ESTO": {
            "sheet": "esto_rollup_rules",
            "input_flow": "input_esto_flow",
            "input_product": "input_esto_product",
            "rolled_flow": "rolled_esto_flow",
            "rolled_product": "rolled_esto_product",
            "scope": "ESTO",
        },
        "ESTO_EXTENDED": {
            "sheet": "esto_rollup_rules",
            "input_flow": "input_esto_flow",
            "input_product": "input_esto_product",
            "rolled_flow": "rolled_esto_flow",
            "rolled_product": "rolled_esto_product",
            "scope": "ESTO_EXTENDED",
        },
        "NINTH": {
            "sheet": "ninth_rollup_rules",
            "input_flow": "input_ninth_sector",
            "input_product": "input_ninth_fuel",
            "rolled_flow": "rolled_ninth_sector",
            "rolled_product": "rolled_ninth_fuel",
            "scope": None,
        },
    }
    rollup_counts: dict[str, int] = {}
    for dataset, spec in rollup_specs.items():
        raw_count = len(universes[dataset])
        rules = pd.read_excel(WORKBOOK_PATH, sheet_name=spec["sheet"])
        universes[dataset] = expand_pair_universe_with_rollups(
            universes[dataset],
            rules,
            input_flow_column=spec["input_flow"],
            input_product_column=spec["input_product"],
            rolled_flow_column=spec["rolled_flow"],
            rolled_product_column=spec["rolled_product"],
            dataset_scope=spec["scope"],
        )
        rollup_counts[dataset] = len(universes[dataset]) - raw_count

    reviewed_extra_pairs = _load_or_bootstrap_reviewed_extra_pairs(
        current_relationships,
        universes,
    )
    for dataset, extra_pairs in reviewed_extra_pairs.items():
        universes[dataset] = merge_reviewed_extra_pairs(
            universes[dataset],
            extra_pairs,
            dataset=dataset,
        )

    leap_manifest = dict(leap_manifest)
    leap_manifest["rollup_pair_counts"] = rollup_counts
    leap_manifest["reviewed_extra_pair_counts"] = {
        dataset: len(frame)
        for dataset, frame in reviewed_extra_pairs.items()
    }
    return universes, leap_manifest, reviewed_extra_pairs


def _load_or_bootstrap_reviewed_extra_pairs(
    current_relationships: pd.DataFrame,
    pair_universes: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """Load editable extra pairs, or bootstrap them once from the master."""
    existing_sheets: set[str] = set()
    if EDITABLE_AXIS_WORKBOOK_PATH.exists():
        with pd.ExcelFile(EDITABLE_AXIS_WORKBOOK_PATH) as workbook:
            existing_sheets = set(workbook.sheet_names)
    required_sheets = {
        spec["sheet"] for spec in EXTRA_PAIR_SHEET_SPECS.values()
    }
    present = required_sheets & existing_sheets
    if present and present != required_sheets:
        missing = sorted(required_sheets - present)
        raise ValueError(
            "Editable extra-pair contract is incomplete. Missing sheets: "
            f"{missing}"
        )

    if present == required_sheets:
        result: dict[str, pd.DataFrame] = {}
        for dataset, spec in EXTRA_PAIR_SHEET_SPECS.items():
            frame = pd.read_excel(
                EDITABLE_AXIS_WORKBOOK_PATH,
                sheet_name=spec["sheet"],
                dtype=object,
            )
            required_columns = {
                spec["flow_column"],
                spec["product_column"],
            }
            missing_columns = required_columns - set(frame.columns)
            if missing_columns:
                raise ValueError(
                    f"{spec['sheet']} is missing columns: "
                    f"{sorted(missing_columns)}"
                )
            result[dataset] = frame[
                [spec["flow_column"], spec["product_column"]]
            ].rename(
                columns={
                    spec["flow_column"]: "flow",
                    spec["product_column"]: "product",
                }
            )
        return result

    return derive_required_reviewed_extra_pairs(
        current_relationships,
        pair_universes,
    )


def _build_both_esto_registry(
    esto_registry: pd.DataFrame,
    extended_registry: pd.DataFrame,
) -> pd.DataFrame:
    """Return exact ESTO pairs present in both base and extended registries."""
    keys = ["flow", "product"]
    base = esto_registry.drop_duplicates(keys).copy()
    extended = extended_registry.drop_duplicates(keys).copy()
    both = base.merge(
        extended[keys + ["pair_status", "pair_is_subtotal"]],
        on=keys,
        how="inner",
        suffixes=("_esto", "_extended"),
    )
    both["pair_status"] = "zero_only"
    both.loc[
        both["pair_status_esto"].eq("data_valid")
        & both["pair_status_extended"].eq("data_valid"),
        "pair_status",
    ] = "data_valid"
    both["pair_is_subtotal"] = (
        both["pair_is_subtotal_esto"].fillna(False).astype(bool)
        | both["pair_is_subtotal_extended"].fillna(False).astype(bool)
    )
    both["dataset"] = "ESTO_BOTH"
    return both


def _pair_universe_workbook_view(registry: pd.DataFrame) -> pd.DataFrame:
    """Keep the workbook pair-universe sheets narrow and human-readable."""
    preferred_columns = [
        "dataset",
        "flow",
        "product",
        "flow_is_parent",
        "product_is_parent",
        "pair_is_subtotal",
        "pair_exists_in_dataset",
        "pair_universe_member",
        "historical_boundary_year",
        "historical_boundary_active",
        "projection_future_active",
        "temporal_evidence_status",
        "first_observed_year",
        "last_observed_year",
        "economy_support_count",
        "year_support_count",
        "nonzero_observation_count",
        "source_vintage",
        "scenario_scope",
        "scenarios_observed",
        "pair_universe_authority",
        "pair_origin",
        "authority_layer",
        "source_kind",
        "template_support_count",
        "template_files",
        "new_rows_sheet_count",
        "new_rows_sheets",
        "source_path_count",
    ]
    return registry[
        [column for column in preferred_columns if column in registry.columns]
    ].copy()


def _compare_leap_registry_to_current_contract(
    registry: pd.DataFrame,
    current: pd.DataFrame,
) -> pd.DataFrame:
    """Compare structural model pairs with current LEAP mapping source keys."""
    current_pairs = (
        current.loc[
            current["source_system"].eq("LEAP"),
            ["source_flow", "source_product"],
        ]
        .drop_duplicates()
        .rename(
            columns={
                "source_flow": "flow",
                "source_product": "product",
            }
        )
    )
    registry_pairs = registry[["flow", "product"]].drop_duplicates()
    comparison = current_pairs.merge(
        registry_pairs.assign(in_structural_registry=True),
        on=["flow", "product"],
        how="outer",
    )
    comparison = comparison.merge(
        current_pairs.assign(in_current_mapping_contract=True),
        on=["flow", "product"],
        how="left",
    )
    comparison["in_structural_registry"] = (
        comparison["in_structural_registry"].fillna(False).astype(bool)
    )
    comparison["in_current_mapping_contract"] = (
        comparison["in_current_mapping_contract"].fillna(False).astype(bool)
    )
    comparison["comparison_status"] = "present_in_both"
    comparison.loc[
        comparison["in_current_mapping_contract"]
        & ~comparison["in_structural_registry"],
        "comparison_status",
    ] = "current_key_absent_from_layered_registry"
    comparison.loc[
        comparison["in_structural_registry"]
        & ~comparison["in_current_mapping_contract"],
        "comparison_status",
    ] = "generated_pair_not_in_current_mapping_contract"
    return comparison.sort_values(
        ["comparison_status", "flow", "product"],
        kind="stable",
    ).reset_index(drop=True)


def _compare_leap_registry_to_observed_exports(
    registry: pd.DataFrame,
) -> pd.DataFrame:
    """Verify the generated registry against current partial balance evidence."""
    if not OBSERVED_LEAP_PAIR_EVIDENCE_PATH.exists():
        return pd.DataFrame(
            columns=[
                "flow",
                "product",
                "observed_pair_status",
                "covered_by_generated_registry",
                "verification_status",
            ]
        )
    observed = pd.read_csv(
        OBSERVED_LEAP_PAIR_EVIDENCE_PATH,
        low_memory=False,
    )
    observed_pairs = observed[
        ["flow", "product", "pair_status"]
    ].drop_duplicates(["flow", "product"]).rename(
        columns={"pair_status": "observed_pair_status"}
    )
    comparison = observed_pairs.merge(
        registry[["flow", "product"]]
        .drop_duplicates()
        .assign(covered_by_generated_registry=True),
        on=["flow", "product"],
        how="left",
    )
    comparison["covered_by_generated_registry"] = (
        comparison["covered_by_generated_registry"]
        .fillna(False)
        .astype(bool)
    )
    comparison["verification_status"] = "covered"
    comparison.loc[
        ~comparison["covered_by_generated_registry"],
        "verification_status",
    ] = "missing_from_generated_registry"
    return comparison.sort_values(
        ["verification_status", "flow", "product"],
        kind="stable",
    ).reset_index(drop=True)


def _attach_axis_contract_status(
    compiled: pd.DataFrame,
    flow_axis: pd.DataFrame,
    product_axis: pd.DataFrame,
) -> pd.DataFrame:
    """Attach flow and product component gates to compiled candidate pairs."""
    context = [
        "mapping_name",
        "comparison_scope",
        "source_system",
        "target_system",
    ]
    flow_status = (
        flow_axis[
            context
            + [
                "source_flow",
                "target_flow",
                "axis_component_id",
                "axis_component_cardinality",
                "axis_contract_status",
            ]
        ]
        .drop_duplicates()
        .rename(
            columns={
                "axis_component_id": "flow_axis_component_id",
                "axis_component_cardinality": (
                    "flow_axis_component_cardinality"
                ),
                "axis_contract_status": "flow_axis_contract_status",
            }
        )
    )
    product_status = (
        product_axis[
            context
            + [
                "source_product",
                "target_product",
                "axis_component_id",
                "axis_component_cardinality",
                "axis_contract_status",
            ]
        ]
        .drop_duplicates()
        .rename(
            columns={
                "axis_component_id": "product_axis_component_id",
                "axis_component_cardinality": (
                    "product_axis_component_cardinality"
                ),
                "axis_contract_status": "product_axis_contract_status",
            }
        )
    )
    result = compiled.merge(
        flow_status,
        on=context + ["source_flow", "target_flow"],
        how="left",
        validate="many_to_one",
    )
    result = result.merge(
        product_status,
        on=context + ["source_product", "target_product"],
        how="left",
        validate="many_to_one",
    )
    blocking = (
        result["flow_axis_contract_status"].eq(
            "blocking_many_to_many_axis_component"
        )
        | result["product_axis_contract_status"].eq(
            "blocking_many_to_many_axis_component"
        )
    )
    result["axis_contract_allowed"] = ~blocking
    result["prototype_review_status"] = "compiled_pair_universe_member"
    result.loc[
        result["registry_allowed"] & blocking,
        "prototype_review_status",
    ] = "blocked_by_within_axis_many_to_many"
    result.loc[
        ~result["registry_allowed"],
        "prototype_review_status",
    ] = "rejected_by_target_pair_universe"
    return result


def _temporal_compiler_registry(
    registry: pd.DataFrame,
    active_column: str,
) -> pd.DataFrame:
    """Convert one pair universe into a named temporal compiler view."""
    result = registry.copy()
    active = result.get(
        active_column,
        pd.Series(False, index=result.index),
    ).fillna(False).astype(bool)
    reviewed_extra = result.get(
        "pair_origin",
        pd.Series("", index=result.index),
    ).fillna("").astype(str).eq("reviewed_extra")
    result["pair_status"] = "zero_only"
    result.loc[active | reviewed_extra, "pair_status"] = "data_valid"
    result["compiler_pair_policy"] = (
        active_column + "_or_reviewed_extra"
    )
    return result


def _mark_comparison_source_status(
    comparison: pd.DataFrame,
    current: pd.DataFrame,
) -> pd.DataFrame:
    """Distinguish new source-pair candidates from extras on current sources."""
    source_keys = [
        "mapping_name",
        "comparison_scope",
        "source_system",
        "source_flow",
        "source_product",
        "target_system",
    ]
    current_sources = current[source_keys].drop_duplicates().assign(
        source_pair_in_current_contract=True
    )
    result = comparison.merge(
        current_sources,
        on=source_keys,
        how="left",
        validate="many_to_one",
    )
    result["source_pair_in_current_contract"] = (
        result["source_pair_in_current_contract"].fillna(False).astype(bool)
    )
    result["comparison_interpretation"] = (
        result["relationship_status"].astype(str)
    )
    new_extra = (
        result["relationship_status"].eq("extra_factorised_relationship")
        & ~result["source_pair_in_current_contract"]
    )
    existing_extra = (
        result["relationship_status"].eq("extra_factorised_relationship")
        & result["source_pair_in_current_contract"]
    )
    result.loc[
        new_extra,
        "comparison_interpretation",
    ] = "new_source_pair_mapping_candidate"
    result.loc[
        existing_extra,
        "comparison_interpretation",
    ] = "extra_target_for_current_source_pair"
    return result


def _summary_rows(
    current: pd.DataFrame,
    flow_axis: pd.DataFrame,
    product_axis: pd.DataFrame,
    axis_components: pd.DataFrame,
    universe_compiled: pd.DataFrame,
    universe_comparison: pd.DataFrame,
    temporal_compiled: pd.DataFrame,
    temporal_comparison: pd.DataFrame,
    generated_overrides: pd.DataFrame,
) -> pd.DataFrame:
    """Build compact headline metrics for the workbook README and summary."""
    universe_allowed = universe_compiled["registry_allowed"]
    temporal_allowed = temporal_compiled["registry_allowed"]
    temporal_axis_allowed = (
        temporal_allowed & temporal_compiled["axis_contract_allowed"]
    )
    universe_counts = (
        universe_comparison["comparison_interpretation"]
        .value_counts()
        .to_dict()
    )
    temporal_counts = (
        temporal_comparison["comparison_interpretation"]
        .value_counts()
        .to_dict()
    )
    rows = [
        ("current_pair_relationship_rows", len(current)),
        ("sector_flow_axis_rows", len(flow_axis)),
        ("fuel_product_axis_rows", len(product_axis)),
        (
            "axis_rows_total",
            len(flow_axis) + len(product_axis),
        ),
        (
            "blocking_within_axis_many_to_many_components",
            int(
                axis_components["axis_contract_status"]
                .eq("blocking_many_to_many_axis_component")
                .sum()
            ),
        ),
        (
            "universe_compiled_relationship_rows",
            int(universe_allowed.sum()),
        ),
        (
            "universe_exact_current_relationship_matches",
            int(universe_counts.get("exact_relationship_match", 0)),
        ),
        (
            "universe_current_relationships_not_compiled",
            int(
                universe_counts.get(
                    "current_relationship_not_compiled",
                    0,
                )
            ),
        ),
        (
            "universe_extra_targets_for_current_sources",
            int(
                universe_counts.get(
                    "extra_target_for_current_source_pair",
                    0,
                )
            ),
        ),
        (
            "universe_new_source_pair_candidates",
            int(
                universe_counts.get(
                    "new_source_pair_mapping_candidate",
                    0,
                )
            ),
        ),
        (
            "temporal_compiled_relationship_rows",
            int(temporal_allowed.sum()),
        ),
        (
            "temporal_rows_after_axis_contract_gate",
            int(temporal_axis_allowed.sum()),
        ),
        (
            "temporal_exact_current_relationship_matches",
            int(temporal_counts.get("exact_relationship_match", 0)),
        ),
        (
            "temporal_current_relationships_not_compiled",
            int(
                temporal_counts.get(
                    "current_relationship_not_compiled",
                    0,
                )
            ),
        ),
        (
            "temporal_extra_targets_for_current_sources",
            int(
                temporal_counts.get(
                    "extra_target_for_current_source_pair",
                    0,
                )
            ),
        ),
        (
            "temporal_new_source_pair_candidates",
            int(
                temporal_counts.get(
                    "new_source_pair_mapping_candidate",
                    0,
                )
            ),
        ),
        (
            "generated_relationship_governance_rows",
            len(generated_overrides),
        ),
    ]
    return pd.DataFrame(rows, columns=["metric", "value"])


# --- Prototype workflow -----------------------------------------------------

def run_single_axis_master_prototype(
    *,
    historical_boundary_year: int = 2023,
    force_leap_registry_refresh: bool = False,
) -> dict[str, Any]:
    """Generate workbook-source tables for the single-axis master prototype."""
    _assert_inputs()
    OUTPUT_DATA_ROOT.mkdir(parents=True, exist_ok=True)

    current, incomplete = load_active_mapping_contract(WORKBOOK_PATH)
    (
        flow_axis_raw,
        product_axis_raw,
        axis_contract_bootstrapped_this_run,
    ) = load_or_bootstrap_editable_axis_contract(
        EDITABLE_AXIS_WORKBOOK_PATH,
        current,
    )
    flow_axis, flow_components = analyse_axis_components(
        flow_axis_raw,
        "flow",
    )
    product_axis, product_components = analyse_axis_components(
        product_axis_raw,
        "product",
    )
    axis_components = pd.concat(
        [flow_components, product_components],
        ignore_index=True,
    )

    (
        pair_universes,
        leap_registry_manifest,
        reviewed_extra_pairs,
    ) = _load_pair_universes(
        historical_boundary_year,
        force_leap_registry_refresh,
        current,
    )
    both_esto = _build_both_esto_registry(
        pair_universes["ESTO"],
        pair_universes["ESTO_EXTENDED"],
    )

    universe_target_lookups = build_registry_scope_lookups(
        pair_universes["ESTO"],
        pair_universes["NINTH"],
        pair_universes["ESTO_EXTENDED"],
    )
    universe_compiled = compile_axis_relationships(
        current,
        flow_axis_raw,
        product_axis_raw,
        universe_target_lookups,
        source_pair_universes={
            "LEAP": pair_universes["LEAP"],
            "NINTH": pair_universes["NINTH"],
        },
        allowed_target_pair_statuses=("data_valid", "zero_only"),
    )
    universe_compiled = _attach_axis_contract_status(
        universe_compiled,
        flow_axis,
        product_axis,
    )

    temporal_esto = _temporal_compiler_registry(
        pair_universes["ESTO"],
        "historical_boundary_active",
    )
    temporal_extended = _temporal_compiler_registry(
        pair_universes["ESTO_EXTENDED"],
        "historical_boundary_active",
    )
    temporal_ninth = _temporal_compiler_registry(
        pair_universes["NINTH"],
        "projection_future_active",
    )
    temporal_target_lookups = build_registry_scope_lookups(
        temporal_esto,
        temporal_ninth,
        temporal_extended,
    )
    temporal_source_universes = {
        "LEAP": pair_universes["LEAP"],
        "NINTH": pair_universes["NINTH"].loc[
            pair_universes["NINTH"]["projection_future_active"]
            .fillna(False)
            .astype(bool)
            | pair_universes["NINTH"]["pair_origin"]
            .fillna("")
            .astype(str)
            .eq("reviewed_extra")
        ].copy(),
    }
    temporal_compiled = compile_axis_relationships(
        current,
        flow_axis_raw,
        product_axis_raw,
        temporal_target_lookups,
        source_pair_universes=temporal_source_universes,
        allowed_target_pair_statuses=("data_valid",),
    )
    temporal_compiled = _attach_axis_contract_status(
        temporal_compiled,
        flow_axis,
        product_axis,
    )

    temporal_pair_compiled = temporal_compiled.loc[
        temporal_compiled["registry_allowed"],
        RELATIONSHIP_KEY_COLUMNS,
    ].drop_duplicates()
    (
        universe_relationship_comparison,
        universe_source_reproduction,
        _universe_generated_overrides,
    ) = compare_compiled_relationships(current, universe_compiled)
    universe_relationship_comparison = _mark_comparison_source_status(
        universe_relationship_comparison,
        current,
    )
    (
        temporal_relationship_comparison,
        source_reproduction,
        generated_overrides,
    ) = compare_compiled_relationships(current, temporal_compiled)
    temporal_relationship_comparison = _mark_comparison_source_status(
        temporal_relationship_comparison,
        current,
    )

    registries_by_scope = {
        ("ESTO", "ESTO"): pair_universes["ESTO"],
        ("ESTO", "ESTO_EXTENDED"): pair_universes["ESTO_EXTENDED"],
        ("ESTO", "BOTH"): both_esto,
        ("NINTH", "NINTH"): pair_universes["NINTH"],
        ("LEAP", "NINTH"): pair_universes["LEAP"],
    }
    compiled_sheets = build_compiled_mapping_sheet_frames(
        temporal_pair_compiled,
        current,
        registries_by_scope,
    )

    summary = _summary_rows(
        current,
        flow_axis,
        product_axis,
        axis_components,
        universe_compiled,
        universe_relationship_comparison,
        temporal_compiled,
        temporal_relationship_comparison,
        generated_overrides,
    )
    leap_contract_comparison = _compare_leap_registry_to_current_contract(
        pair_universes["LEAP"],
        current,
    )
    leap_observed_comparison = (
        _compare_leap_registry_to_observed_exports(
            pair_universes["LEAP"],
        )
    )
    leap_comparison_counts = (
        leap_contract_comparison["comparison_status"].value_counts()
    )
    summary = pd.concat(
        [
            summary,
            pd.DataFrame(
                [
                    (
                        "leap_layered_registry_pair_rows",
                        len(pair_universes["LEAP"]),
                    ),
                    (
                        "leap_current_source_pairs_present_in_registry",
                        int(
                            leap_comparison_counts.get(
                                "present_in_both",
                                0,
                            )
                        ),
                    ),
                    (
                        "leap_current_source_keys_absent_from_registry",
                        int(
                            leap_comparison_counts.get(
                                "current_key_absent_from_layered_registry",
                                0,
                            )
                        ),
                    ),
                    (
                        "leap_generated_pairs_not_in_current_mapping_contract",
                        int(
                            leap_comparison_counts.get(
                                (
                                    "generated_pair_not_in_current_"
                                    "mapping_contract"
                                ),
                                0,
                            )
                        ),
                    ),
                    (
                        "leap_observed_verification_pair_rows",
                        len(leap_observed_comparison),
                    ),
                    (
                        "leap_observed_pairs_missing_from_registry",
                        int(
                            leap_observed_comparison[
                                "verification_status"
                            ]
                            .eq("missing_from_generated_registry")
                            .sum()
                        ),
                    ),
                ],
                columns=["metric", "value"],
            ),
        ],
        ignore_index=True,
    )

    sheet_sources: dict[str, Path] = {}
    detail_sources: dict[str, Path] = {}
    sheet_sources["Summary"] = _write_csv(summary, "summary.csv")
    sheet_sources["Sector axis"] = _write_csv(
        flow_axis,
        "sector_flow_axis_mappings.csv",
    )
    sheet_sources["Fuel axis"] = _write_csv(
        product_axis,
        "fuel_product_axis_mappings.csv",
    )
    sheet_sources["Pairs LEAP"] = _write_csv(
        _pair_universe_workbook_view(pair_universes["LEAP"]),
        "pair_universe_leap.csv",
    )
    sheet_sources["Pairs ESTO"] = _write_csv(
        _pair_universe_workbook_view(pair_universes["ESTO"]),
        "pair_universe_esto.csv",
    )
    sheet_sources["Pairs ESTO Extended"] = _write_csv(
        _pair_universe_workbook_view(pair_universes["ESTO_EXTENDED"]),
        "pair_universe_esto_extended.csv",
    )
    sheet_sources["Pairs Ninth"] = _write_csv(
        _pair_universe_workbook_view(pair_universes["NINTH"]),
        "pair_universe_ninth.csv",
    )
    for dataset, spec in EXTRA_PAIR_SHEET_SPECS.items():
        editable_frame = reviewed_extra_pairs[dataset].rename(
            columns={
                "flow": spec["flow_column"],
                "product": spec["product_column"],
            }
        )
        sheet_sources[spec["sheet"]] = _write_csv(
            editable_frame,
            f"editable_{spec['sheet']}.csv",
        )
    sheet_sources["Compiled LEAP ESTO"] = _write_csv(
        compiled_sheets["leap_combined_esto"],
        "compiled_leap_combined_esto.csv",
    )
    sheet_sources["Compiled LEAP Ninth"] = _write_csv(
        compiled_sheets["leap_combined_ninth"],
        "compiled_leap_combined_ninth.csv",
    )
    sheet_sources["Compiled Ninth ESTO"] = _write_csv(
        compiled_sheets["ninth_pairs_to_esto_pairs"],
        "compiled_ninth_pairs_to_esto_pairs.csv",
    )
    sheet_sources["QA axis components"] = _write_csv(
        axis_components,
        "qa_axis_components.csv",
    )
    detail_sources["QA candidates universe"] = _write_csv(
        universe_compiled,
        "qa_compiled_candidates_pair_universe.csv",
    )
    detail_sources["QA candidates temporal"] = _write_csv(
        temporal_compiled,
        "qa_compiled_candidates_temporal.csv",
    )
    detail_sources["QA compare universe"] = _write_csv(
        universe_relationship_comparison,
        "qa_relationship_comparison_pair_universe.csv",
    )
    sheet_sources["QA compare temporal"] = _write_csv(
        temporal_relationship_comparison,
        "qa_relationship_comparison_temporal.csv",
    )
    detail_sources["QA source reproduction"] = _write_csv(
        source_reproduction,
        "qa_source_pair_reproduction.csv",
    )
    detail_sources["QA source universe"] = _write_csv(
        universe_source_reproduction,
        "qa_source_pair_reproduction_pair_universe.csv",
    )
    detail_sources["QA relationship governance"] = _write_csv(
        generated_overrides,
        "qa_generated_relationship_governance.csv",
    )
    legacy_override_path = (
        OUTPUT_DATA_ROOT / "qa_generated_overrides_review_only.csv"
    )
    if legacy_override_path.exists():
        legacy_override_path.unlink()
    detail_sources["QA LEAP layered coverage"] = _write_csv(
        leap_contract_comparison,
        "qa_leap_layered_registry_vs_current_contract.csv",
    )
    detail_sources["QA LEAP observed verification"] = _write_csv(
        leap_observed_comparison,
        "qa_leap_registry_vs_observed_exports.csv",
    )
    sheet_sources["QA incomplete current"] = _write_csv(
        incomplete,
        "qa_incomplete_current_rows.csv",
    )

    manifest = {
        "prototype_status": (
            "not_ready_blocking_axis_components"
            if summary.loc[
                summary["metric"].eq(
                    "blocking_within_axis_many_to_many_components"
                ),
                "value",
            ].iloc[0]
            > 0
            else "axis_contract_ready_for_semantic_review"
        ),
        "historical_boundary_year": int(historical_boundary_year),
        "canonical_workbook_was_modified": False,
        "canonical_workbook_path": str(WORKBOOK_PATH),
        "editable_axis_workbook_path": str(EDITABLE_AXIS_WORKBOOK_PATH),
        "axis_contract_authority": "editable_single_axis_workbook",
        "axis_contract_bootstrapped_this_run": (
            axis_contract_bootstrapped_this_run
        ),
        "leap_pair_authority": (
            "generated_from_model_branches_and_balance_report_contract"
        ),
        "leap_pair_registry_manifest": leap_registry_manifest,
        "rollup_sheets_included": True,
        "compiled_compatibility_policy": (
            "ESTO final-year nonzero or reviewed extra; Ninth any "
            "post-ESTO-year nonzero or reviewed extra"
        ),
        "sheet_sources": {
            sheet: _relative_output_path(path)
            for sheet, path in sheet_sources.items()
        },
        "detail_sources": {
            name: _relative_output_path(path)
            for name, path in detail_sources.items()
        },
        "summary": {
            row.metric: int(row.value)
            for row in summary.itertuples(index=False)
        },
    }
    manifest_path = OUTPUT_ROOT / "workbook_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))
    return manifest


# --- Frequently changed run flags ------------------------------------------

RUN_SINGLE_AXIS_MASTER_PROTOTYPE = True
HISTORICAL_BOUNDARY_YEAR = 2023
FORCE_LEAP_REGISTRY_REFRESH = False


#%%
if RUN_SINGLE_AXIS_MASTER_PROTOTYPE:
    try:
        PROTOTYPE_MANIFEST = run_single_axis_master_prototype(
            historical_boundary_year=HISTORICAL_BOUNDARY_YEAR,
            force_leap_registry_refresh=FORCE_LEAP_REGISTRY_REFRESH,
        )
    except Exception:
        print("Single-axis master prototype failed.")
        traceback.print_exc()
        raise

#%%
