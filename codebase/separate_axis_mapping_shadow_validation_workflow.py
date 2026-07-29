#%%
"""Shadow-compare the canonical and generated mapping masters through Stages 1-2.

The workflow writes each variant to its own output directory, compares semantic
relationship rows and Common ESTO membership, and never changes either mapping
workbook. Stage 3 remains a separate full-data gate because it is much slower.
"""

#%%
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

import pandas as pd


# --- Stable paths -----------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.mapping_tools.build_common_esto_structure import (  # noqa: E402
    COMMON_ESTO_LABEL_OVERRIDES_PATH,
    DEFAULT_ENABLED_COMPARISON_SCOPES,
    run_common_esto_structure_workflow,
)
from codebase.mapping_tools.build_energy_balance_relationships import (  # noqa: E402
    FALLBACK_WORKBOOK_PATH,
    SHEET_CONFIGS,
    run_relationship_workflow,
)
from codebase.separate_axis_mapping_exploration_functions import (  # noqa: E402
    RELATIONSHIP_KEY_COLUMNS,
    load_active_mapping_contract,
)

CANONICAL_WORKBOOK_PATH = (
    REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
)
GENERATED_WORKBOOK_PATH = (
    REPO_ROOT
    / "config"
    / "outlook_mappings_master_generated_prototype.xlsx"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "outputs"
    / "separate_axis_mapping_shadow_validation_20260729"
)

PAIR_SHEETS = [
    "leap_combined_esto",
    "leap_combined_ninth",
    "ninth_pairs_to_esto_pairs",
]


# --- Helpers ----------------------------------------------------------------

def _assert_inputs() -> None:
    """Fail with the complete missing-input list."""
    missing = [
        str(path)
        for path in [CANONICAL_WORKBOOK_PATH, GENERATED_WORKBOOK_PATH]
        if not path.exists()
    ]
    if missing:
        raise FileNotFoundError(
            "Missing shadow-validation inputs:\n- " + "\n- ".join(missing)
        )


def _normalise_for_set_comparison(
    frame: pd.DataFrame,
    excluded_columns: set[str],
) -> pd.DataFrame:
    """Return stable semantic rows without workbook-location provenance."""
    columns = [
        column
        for column in frame.columns
        if column not in excluded_columns
    ]
    result = frame[columns].copy()
    for column in result.columns:
        result[column] = result[column].fillna("").astype(str)
    return result.drop_duplicates().sort_values(columns, kind="stable")


def _outer_difference(
    canonical: pd.DataFrame,
    generated: pd.DataFrame,
) -> pd.DataFrame:
    """Return rows present in only one of two already-normalised frames."""
    columns = list(canonical.columns)
    if columns != list(generated.columns):
        raise ValueError("Comparison frames do not have identical columns.")
    difference = canonical.merge(
        generated,
        on=columns,
        how="outer",
        indicator=True,
    )
    difference["shadow_status"] = difference["_merge"].map(
        {
            "left_only": "canonical_only",
            "right_only": "generated_only",
            "both": "both",
        }
    )
    return (
        difference.loc[difference["_merge"].ne("both")]
        .drop(columns="_merge")
        .sort_values(["shadow_status", *columns], kind="stable")
        .reset_index(drop=True)
    )


def _write_csv(frame: pd.DataFrame, filename: str) -> Path:
    """Write one human-inspectable shadow diagnostic."""
    path = OUTPUT_ROOT / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def _pair_sheet_headers(workbook_path: Path) -> dict[str, list[str]]:
    """Read the exact pair-sheet header contracts."""
    return {
        sheet_name: list(
            pd.read_excel(
                workbook_path,
                sheet_name=sheet_name,
                nrows=0,
            ).columns
        )
        for sheet_name in PAIR_SHEETS
    }


def _functional_relationship_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Exclude incomplete and explicitly removed workbook diagnostics."""
    key_columns = [
        "source_flow",
        "source_product",
        "target_flow",
        "target_product",
    ]
    complete = frame[key_columns].notna().all(axis=1)
    for column in key_columns:
        complete &= frame[column].astype(str).str.strip().ne("")
    removed = frame["remove_row"].map(
        lambda value: (
            value is True
            or str(value).strip().casefold()
            in {"true", "1", "1.0", "yes", "y", "t", "on"}
        )
    )
    retained = ~removed
    return frame.loc[complete & retained].copy()


def _run_stage_1_and_2_variant(
    label: str,
    workbook_path: Path,
    *,
    allow_direct_subtotal_edges: bool = False,
) -> dict[str, Any]:
    """Run Stages 1 and 2 into an isolated variant directory."""
    variant_root = OUTPUT_ROOT / label
    relationship_dir = variant_root / "mapping_relationships"
    common_dir = variant_root / "common_esto"
    relationship_dir.mkdir(parents=True, exist_ok=True)
    common_dir.mkdir(parents=True, exist_ok=True)

    relationships, stage_1_qa = run_relationship_workflow(
        mapping_workbook_path=workbook_path,
        fallback_workbook_path=FALLBACK_WORKBOOK_PATH,
        sheet_configs=SHEET_CONFIGS,
        output_csv_path=relationship_dir / "energy_balance_relationships.csv",
        output_xlsx_path=relationship_dir / "energy_balance_relationships.xlsx",
        compact_catalogue_csv_path=(
            relationship_dir / "relationship_catalogue_compact.csv"
        ),
        qa_dir=relationship_dir,
    )
    common_rows, common_map, stage_2_qa = (
        run_common_esto_structure_workflow(
            relationships_path=(
                relationship_dir / "energy_balance_relationships.csv"
            ),
            coverage_exclusions_path=(
                relationship_dir / "coverage_exclusions.csv"
            ),
            common_esto_overrides_path=(
                relationship_dir / "common_esto_overrides.csv"
            ),
            common_esto_label_overrides_path=(
                COMMON_ESTO_LABEL_OVERRIDES_PATH
            ),
            outlook_mappings_path=workbook_path,
            output_dir=common_dir,
            enabled_scopes=DEFAULT_ENABLED_COMPARISON_SCOPES,
            allow_direct_subtotal_edges=allow_direct_subtotal_edges,
        )
    )
    return {
        "relationships": relationships,
        "common_rows": common_rows,
        "common_map": common_map,
        "stage_1_qa": stage_1_qa,
        "stage_2_qa": stage_2_qa,
        "relationship_dir": relationship_dir,
        "common_dir": common_dir,
    }


def _load_stage_1_and_2_variant(label: str) -> dict[str, Any]:
    """Load a previously completed isolated variant."""
    variant_root = OUTPUT_ROOT / label
    relationship_dir = variant_root / "mapping_relationships"
    common_dir = variant_root / "common_esto"
    required = [
        relationship_dir / "energy_balance_relationships.csv",
        common_dir / "common_esto_rows.csv",
        common_dir / "esto_to_common_esto_map.csv",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            f"Cannot reuse incomplete {label} shadow outputs:\n- "
            + "\n- ".join(missing)
        )
    return {
        "relationships": pd.read_csv(
            required[0],
            low_memory=False,
        ),
        "common_rows": pd.read_csv(required[1], low_memory=False),
        "common_map": pd.read_csv(required[2], low_memory=False),
        "stage_1_qa": {},
        "stage_2_qa": {},
        "relationship_dir": relationship_dir,
        "common_dir": common_dir,
    }


def _stage_2_qa_frame(
    variant: dict[str, Any],
    qa_name: str,
) -> pd.DataFrame:
    """Read one Stage 2 QA frame from memory or its isolated CSV."""
    in_memory = variant.get("stage_2_qa", {}).get(qa_name)
    if in_memory is not None:
        return in_memory
    qa_path = variant["common_dir"] / f"{qa_name}.csv"
    if not qa_path.exists():
        return pd.DataFrame()
    return pd.read_csv(qa_path, low_memory=False)


def run_stage_2_from_existing_relationships(
    *,
    relationship_variant_label: str,
    output_variant_label: str,
    workbook_path: Path,
) -> dict[str, Any]:
    """Rerun Stage 2 without paying the cost of rebuilding Stage 1.

    This is useful for testing graph and rollup rules against an already
    generated relationship catalogue. The new outputs are kept in a separate
    variant directory so earlier shadow evidence remains unchanged.
    """
    relationship_dir = (
        OUTPUT_ROOT / relationship_variant_label / "mapping_relationships"
    )
    relationships_path = (
        relationship_dir / "energy_balance_relationships.csv"
    )
    if not relationships_path.exists():
        raise FileNotFoundError(
            "Stage 1 relationship catalogue does not exist: "
            f"{relationships_path}"
        )

    common_dir = OUTPUT_ROOT / output_variant_label / "common_esto"
    common_dir.mkdir(parents=True, exist_ok=True)
    common_rows, common_map, stage_2_qa = (
        run_common_esto_structure_workflow(
            relationships_path=relationships_path,
            coverage_exclusions_path=(
                relationship_dir / "coverage_exclusions.csv"
            ),
            common_esto_overrides_path=(
                relationship_dir / "common_esto_overrides.csv"
            ),
            common_esto_label_overrides_path=(
                COMMON_ESTO_LABEL_OVERRIDES_PATH
            ),
            outlook_mappings_path=workbook_path,
            output_dir=common_dir,
            enabled_scopes=DEFAULT_ENABLED_COMPARISON_SCOPES,
            allow_direct_subtotal_edges=True,
        )
    )
    return {
        "common_rows": common_rows,
        "common_map": common_map,
        "stage_2_qa": stage_2_qa,
        "relationship_dir": relationship_dir,
        "common_dir": common_dir,
    }


def _subtotal_flag_difference() -> pd.DataFrame:
    """Compare subtotal metadata for relationships shared by both masters."""
    canonical, _ = load_active_mapping_contract(CANONICAL_WORKBOOK_PATH)
    generated, _ = load_active_mapping_contract(GENERATED_WORKBOOK_PATH)
    flag_columns = [
        "source_pair_is_subtotal",
        "target_pair_is_subtotal",
    ]
    shared = canonical[
        RELATIONSHIP_KEY_COLUMNS + flag_columns
    ].merge(
        generated[RELATIONSHIP_KEY_COLUMNS + flag_columns],
        on=RELATIONSHIP_KEY_COLUMNS,
        how="inner",
        suffixes=("_canonical", "_generated"),
    )
    differs = pd.Series(False, index=shared.index)
    for column in flag_columns:
        differs |= (
            shared[f"{column}_canonical"].fillna(False).astype(bool)
            != shared[f"{column}_generated"].fillna(False).astype(bool)
        )
    return shared.loc[differs].reset_index(drop=True)


def _build_structural_source_once_diagnostic(
    relationships: pd.DataFrame,
    common_map: pd.DataFrame,
    variant: str,
    expected_split_groups: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Count common rows reached by each conversion source pair and scope.

    A split explicitly reported by Stage 2 after isolating a non-expanding
    subtotal frontier is an alternative parent/detail view, not an unrelated
    double delivery. It remains visible but is classified separately from
    unsafe fan-out.
    """
    conversion_use_cases = {
        "leap_to_esto_balance_conversion",
        "ninth_to_esto_balance_conversion",
    }
    included = relationships["include_in_use_case"].map(
        lambda value: (
            value is True
            or str(value).strip().casefold()
            in {"true", "1", "1.0", "yes", "y", "t", "on"}
        )
    )
    conversion = relationships.loc[
        included
        & relationships["use_case"].isin(conversion_use_cases)
    ].dropna(
        subset=[
            "source_flow",
            "source_product",
            "target_flow",
            "target_product",
        ]
    )
    joined = conversion.merge(
        common_map,
        left_on=["target_flow", "target_product"],
        right_on=[
            "component_esto_flow",
            "component_esto_product",
        ],
        how="inner",
    )
    relevant_scope = (
        joined["source_system"].eq("LEAP")
        | joined["comparison_scope"].str.contains(
            "ninth",
            case=False,
            na=False,
        )
    )
    joined = joined.loc[relevant_scope].copy()
    joined["target_pair"] = (
        joined["target_flow"].astype(str)
        + " | "
        + joined["target_product"].astype(str)
    )
    diagnostic = (
        joined.groupby(
            [
                "source_system",
                "source_flow",
                "source_product",
                "comparison_scope",
            ],
            dropna=False,
            as_index=False,
        )
        .agg(
            target_pair_count=("target_pair", "nunique"),
            common_row_count=("common_row_id", "nunique"),
        )
    )
    diagnostic.insert(0, "variant", variant)
    diagnostic["source_once_status"] = "one_common_row"
    expected_keys: set[tuple[Any, ...]] = set()
    if expected_split_groups is not None and not expected_split_groups.empty:
        expected_keys = {
            tuple(row)
            for row in (
                expected_split_groups[
                    [
                        "source_system",
                        "source_flow",
                        "source_product",
                        "comparison_scope",
                    ]
                ]
                .drop_duplicates()
                .itertuples(index=False, name=None)
            )
        }
    diagnostic_keys = diagnostic[
        [
            "source_system",
            "source_flow",
            "source_product",
            "comparison_scope",
        ]
    ].itertuples(index=False, name=None)
    diagnostic["is_protected_parent_detail_alternative"] = [
        tuple(key) in expected_keys
        for key in diagnostic_keys
    ]
    diagnostic.loc[
        diagnostic["common_row_count"].gt(1)
        & diagnostic["is_protected_parent_detail_alternative"],
        "source_once_status",
    ] = "protected_parent_detail_alternative"
    diagnostic.loc[
        diagnostic["common_row_count"].gt(1)
        & ~diagnostic["is_protected_parent_detail_alternative"],
        "source_once_status",
    ] = "unsafe_multiple_common_rows"
    return diagnostic


# --- Shadow workflow --------------------------------------------------------

def run_separate_axis_shadow_validation(
    *,
    run_variant_pipelines: bool = True,
) -> dict[str, Any]:
    """Run and compare the canonical and generated Stage 1-2 structures."""
    _assert_inputs()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    if run_variant_pipelines:
        canonical = _run_stage_1_and_2_variant(
            "canonical",
            CANONICAL_WORKBOOK_PATH,
            allow_direct_subtotal_edges=False,
        )
        generated = _run_stage_1_and_2_variant(
            "generated",
            GENERATED_WORKBOOK_PATH,
            allow_direct_subtotal_edges=True,
        )
    else:
        canonical = _load_stage_1_and_2_variant("canonical")
        generated = _load_stage_1_and_2_variant("generated")

    relationship_exclusions = {
        "relationship_id",
        "relationship_key",
        "source_mapping_file",
        "source_mapping_path",
        "source_row_number",
        "source_workbook_row",
        "workbook_row_number",
    }
    canonical_functional_relationships = _functional_relationship_rows(
        canonical["relationships"]
    )
    generated_functional_relationships = _functional_relationship_rows(
        generated["relationships"]
    )
    canonical_relationships = _normalise_for_set_comparison(
        canonical_functional_relationships,
        relationship_exclusions,
    )
    generated_relationships = _normalise_for_set_comparison(
        generated_functional_relationships,
        relationship_exclusions,
    )
    relationship_metadata_difference = _outer_difference(
        canonical_relationships,
        generated_relationships,
    )
    relationship_identity_columns = [
        "use_case",
        "include_in_use_case",
        "source_system",
        "esto_dataset_scope",
        "source_flow",
        "source_product",
        "target_system",
        "target_flow",
        "target_product",
        "relationship_source",
        "is_rollup_derived",
    ]
    canonical_relationship_identity = _normalise_for_set_comparison(
        canonical_functional_relationships[relationship_identity_columns],
        set(),
    )
    generated_relationship_identity = _normalise_for_set_comparison(
        generated_functional_relationships[relationship_identity_columns],
        set(),
    )
    relationship_identity_difference = _outer_difference(
        canonical_relationship_identity,
        generated_relationship_identity,
    )

    common_columns = sorted(
        set(canonical["common_map"].columns)
        & set(generated["common_map"].columns)
    )
    common_map_exclusions = {
        column
        for column in common_columns
        if "name" in column.casefold() or "label" in column.casefold()
    }
    canonical_map = _normalise_for_set_comparison(
        canonical["common_map"][common_columns],
        common_map_exclusions,
    )
    generated_map = _normalise_for_set_comparison(
        generated["common_map"][common_columns],
        common_map_exclusions,
    )
    common_map_difference = _outer_difference(
        canonical_map,
        generated_map,
    )
    subtotal_difference = _subtotal_flag_difference()
    canonical_source_once = _build_structural_source_once_diagnostic(
        canonical["relationships"],
        canonical["common_map"],
        "canonical",
        _stage_2_qa_frame(
            canonical,
            "qa_common_esto_source_aggregates_split",
        ),
    )
    generated_source_once = _build_structural_source_once_diagnostic(
        generated["relationships"],
        generated["common_map"],
        "generated",
        _stage_2_qa_frame(
            generated,
            "qa_common_esto_source_aggregates_split",
        ),
    )
    source_once_diagnostic = pd.concat(
        [canonical_source_once, generated_source_once],
        ignore_index=True,
    )
    unsafe_key_columns = [
        "source_system",
        "source_flow",
        "source_product",
        "comparison_scope",
    ]
    canonical_unsafe = canonical_source_once.loc[
        canonical_source_once["source_once_status"].eq(
            "unsafe_multiple_common_rows"
        ),
        unsafe_key_columns,
    ]
    generated_unsafe = generated_source_once.loc[
        generated_source_once["source_once_status"].eq(
            "unsafe_multiple_common_rows"
        ),
        unsafe_key_columns,
    ]
    unsafe_difference = canonical_unsafe.merge(
        generated_unsafe,
        on=unsafe_key_columns,
        how="outer",
        indicator=True,
    )
    unsafe_difference["shadow_status"] = unsafe_difference["_merge"].map(
        {
            "left_only": "resolved_in_generated",
            "right_only": "new_in_generated",
            "both": "unsafe_in_both",
        }
    )
    unsafe_difference = unsafe_difference.drop(columns="_merge")

    canonical_headers = _pair_sheet_headers(CANONICAL_WORKBOOK_PATH)
    generated_headers = _pair_sheet_headers(GENERATED_WORKBOOK_PATH)
    schema_matches = canonical_headers == generated_headers

    _write_csv(
        relationship_identity_difference,
        "stage1_relationship_identity_difference.csv",
    )
    _write_csv(
        relationship_metadata_difference,
        "stage1_relationship_metadata_difference.csv",
    )
    _write_csv(
        common_map_difference,
        "stage2_common_map_semantic_difference.csv",
    )
    _write_csv(
        subtotal_difference,
        "shared_relationship_subtotal_flag_difference.csv",
    )
    _write_csv(
        source_once_diagnostic,
        "stage3_structural_source_once_diagnostic.csv",
    )
    _write_csv(
        unsafe_difference,
        "stage3_structural_source_once_difference.csv",
    )

    relationship_identity_status_counts = (
        relationship_identity_difference["shadow_status"]
        .value_counts()
        .loc[lambda counts: counts.gt(0)]
        .to_dict()
        if not relationship_identity_difference.empty
        else {}
    )
    relationship_metadata_status_counts = (
        relationship_metadata_difference["shadow_status"]
        .value_counts()
        .loc[lambda counts: counts.gt(0)]
        .to_dict()
        if not relationship_metadata_difference.empty
        else {}
    )
    common_map_status_counts = (
        common_map_difference["shadow_status"]
        .value_counts()
        .loc[lambda counts: counts.gt(0)]
        .to_dict()
        if not common_map_difference.empty
        else {}
    )
    manifest = {
        "status": "completed",
        "canonical_workbook": str(CANONICAL_WORKBOOK_PATH),
        "generated_workbook": str(GENERATED_WORKBOOK_PATH),
        "pair_sheet_schema_matches": schema_matches,
        "pair_sheet_headers": generated_headers,
        "canonical_stage1_rows": len(canonical["relationships"]),
        "generated_stage1_rows": len(generated["relationships"]),
        "canonical_stage1_functional_rows": len(
            canonical_functional_relationships
        ),
        "generated_stage1_functional_rows": len(
            generated_functional_relationships
        ),
        "shared_stage1_identity_rows": (
            len(canonical_relationship_identity)
            - relationship_identity_status_counts.get(
                "canonical_only",
                0,
            )
        ),
        "stage1_identity_difference_counts": (
            relationship_identity_status_counts
        ),
        "stage1_metadata_difference_counts": (
            relationship_metadata_status_counts
        ),
        "canonical_stage2_common_rows": len(canonical["common_rows"]),
        "generated_stage2_common_rows": len(generated["common_rows"]),
        "canonical_stage2_map_rows": len(canonical["common_map"]),
        "generated_stage2_map_rows": len(generated["common_map"]),
        "shared_stage2_common_map_rows": (
            len(canonical_map)
            - common_map_status_counts.get("canonical_only", 0)
        ),
        "stage2_common_map_difference_counts": common_map_status_counts,
        "shared_relationship_subtotal_flag_differences": len(
            subtotal_difference
        ),
        "canonical_source_pairs_reaching_multiple_common_rows": int(
            canonical_source_once["common_row_count"].gt(1).sum()
        ),
        "generated_source_pairs_reaching_multiple_common_rows": int(
            generated_source_once["common_row_count"].gt(1).sum()
        ),
        "canonical_protected_parent_detail_alternatives": int(
            canonical_source_once["source_once_status"].eq(
                "protected_parent_detail_alternative"
            ).sum()
        ),
        "generated_protected_parent_detail_alternatives": int(
            generated_source_once["source_once_status"].eq(
                "protected_parent_detail_alternative"
            ).sum()
        ),
        "canonical_unsafe_source_once_failures": int(
            canonical_source_once["source_once_status"].eq(
                "unsafe_multiple_common_rows"
            ).sum()
        ),
        "generated_unsafe_source_once_failures": int(
            generated_source_once["source_once_status"].eq(
                "unsafe_multiple_common_rows"
            ).sum()
        ),
        "new_generated_source_once_failures": int(
            unsafe_difference["shadow_status"].eq(
                "new_in_generated"
            ).sum()
        ),
        "generated_max_common_rows_per_source_pair": int(
            generated_source_once["common_row_count"].max()
        ),
        "enabled_comparison_scopes": (
            DEFAULT_ENABLED_COMPARISON_SCOPES
        ),
        "stage3_status": (
            "run separately with "
            "separate_axis_mapping_stage3_shadow_workflow.py against the "
            "selected Stage 2 variant; this manifest records structural "
            "source-once evidence only"
        ),
    }
    manifest_path = OUTPUT_ROOT / "shadow_validation_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))
    return manifest


# --- Frequently changed run flag ------------------------------------------

RUN_STAGE_2_EXISTING_RELATIONSHIPS = (
    os.environ.get("SEPARATE_AXIS_STAGE2_ONLY", "false")
    .strip()
    .casefold()
    in {"true", "1", "yes"}
)
RUN_SEPARATE_AXIS_SHADOW_VALIDATION = not RUN_STAGE_2_EXISTING_RELATIONSHIPS
RUN_VARIANT_PIPELINES = (
    os.environ.get("SEPARATE_AXIS_RUN_VARIANTS", "true")
    .strip()
    .casefold()
    not in {"false", "0", "no"}
)


#%%
if __name__ == "__main__" and RUN_STAGE_2_EXISTING_RELATIONSHIPS:
    try:
        STAGE_2_EXISTING_RELATIONSHIPS_RESULT = (
            run_stage_2_from_existing_relationships(
                relationship_variant_label=os.environ.get(
                    "SEPARATE_AXIS_STAGE2_RELATIONSHIP_LABEL",
                    "generated",
                ),
                output_variant_label=os.environ.get(
                    "SEPARATE_AXIS_STAGE2_OUTPUT_LABEL",
                    "generated_stage2_experiment",
                ),
                workbook_path=GENERATED_WORKBOOK_PATH,
            )
        )
    except Exception:
        print("Separate-axis Stage 2-only shadow validation failed.")
        traceback.print_exc()
        raise


#%%
if __name__ == "__main__" and RUN_SEPARATE_AXIS_SHADOW_VALIDATION:
    try:
        SHADOW_VALIDATION_MANIFEST = (
            run_separate_axis_shadow_validation(
                run_variant_pipelines=RUN_VARIANT_PIPELINES,
            )
        )
    except Exception:
        print("Separate-axis shadow validation failed.")
        traceback.print_exc()
        raise

#%%
