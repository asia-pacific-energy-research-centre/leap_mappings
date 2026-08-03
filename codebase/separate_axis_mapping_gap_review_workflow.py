#%%
"""Build review tables for temporal mapping gaps and subtotal inconsistencies.

This workflow keeps the canonical mapping workbook read-only. It enriches
missing generated relationships with direct dataset evidence and compares
maintained subtotal flags with generated structural metadata.
"""

#%%
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import pandas as pd

# Notebook and script runs may start from arbitrary working directories.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.separate_axis_mapping_exploration_functions import (
    load_active_mapping_contract,
)


# --- Stable paths -----------------------------------------------------------

PROTOTYPE_DATA_ROOT = (
    REPO_ROOT
    / "outputs"
    / "separate_axis_mapping_refresh"
    / "compiler"
    / "data"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "outputs"
    / "separate_axis_mapping_gap_review_20260729"
)
OUTPUT_DATA_ROOT = OUTPUT_ROOT / "data"

CANONICAL_MASTER_PATH = (
    REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
)
GENERATED_MASTER_PATH = (
    REPO_ROOT
    / "outputs"
    / "separate_axis_mapping_refresh"
    / "workbooks"
    / "outlook_mappings_master_candidate.xlsx"
)

RELATIONSHIP_KEYS = [
    "mapping_name",
    "comparison_scope",
    "source_system",
    "source_flow",
    "source_product",
    "target_system",
    "target_flow",
    "target_product",
]

PAIR_UNIVERSE_FILES = {
    "LEAP": PROTOTYPE_DATA_ROOT / "pair_universe_leap.csv",
    "ESTO": PROTOTYPE_DATA_ROOT / "pair_universe_esto.csv",
    "ESTO_EXTENDED": (
        PROTOTYPE_DATA_ROOT / "pair_universe_esto_extended.csv"
    ),
    "NINTH": PROTOTYPE_DATA_ROOT / "pair_universe_ninth.csv",
}


# --- Evidence helpers -------------------------------------------------------

def _load_pair_universes() -> dict[str, pd.DataFrame]:
    """Load generated pair universes and add a direct any-year indicator."""
    universes: dict[str, pd.DataFrame] = {}
    for dataset, path in PAIR_UNIVERSE_FILES.items():
        frame = pd.read_csv(path, low_memory=False)
        frame["nonzero_any_year"] = (
            pd.to_numeric(
                frame.get(
                    "nonzero_observation_count",
                    pd.Series(0, index=frame.index),
                ),
                errors="coerce",
            )
            .fillna(0)
            .gt(0)
        )
        universes[dataset] = frame
    return universes


def _merge_target_evidence(
    frame: pd.DataFrame,
    universe: pd.DataFrame,
    prefix: str,
) -> pd.DataFrame:
    """Attach exact target-pair evidence from one dataset."""
    evidence_columns = [
        "flow",
        "product",
        "pair_is_subtotal",
        "flow_is_parent",
        "product_is_parent",
        "historical_boundary_active",
        "projection_future_active",
        "nonzero_any_year",
        "first_observed_year",
        "last_observed_year",
        "year_support_count",
        "economy_support_count",
        "nonzero_observation_count",
        "temporal_evidence_status",
    ]
    evidence = universe[evidence_columns].copy()
    renamed = {
        "flow": "target_flow",
        "product": "target_product",
    }
    renamed.update(
        {
            column: f"{prefix}_{column}"
            for column in evidence_columns
            if column not in {"flow", "product"}
        }
    )
    evidence = evidence.rename(columns=renamed)
    return frame.merge(
        evidence,
        on=["target_flow", "target_product"],
        how="left",
        validate="many_to_one",
    )


def _classify_missing_relationship(row: object) -> str:
    """Assign the most useful first review reason to one missing row."""
    if not bool(row.source_pair_present_in_generated_registry):
        return "source_pair_absent_from_generated_registry"

    if row.target_system == "NINTH":
        if pd.isna(row.ninth_nonzero_any_year):
            return "ninth_target_pair_not_structurally_present"
        if bool(row.ninth_nonzero_any_year):
            return "ninth_nonzero_only_outside_future_window"
        return "ninth_structural_zero_all_years"

    base_missing = pd.isna(row.esto_nonzero_any_year)
    extended_missing = pd.isna(row.esto_extended_nonzero_any_year)
    if base_missing or extended_missing:
        return "esto_pair_missing_from_base_or_extended_scope"
    if bool(row.esto_nonzero_any_year) or bool(
        row.esto_extended_nonzero_any_year
    ):
        return "esto_nonzero_only_outside_final_year_or_one_scope"
    return "esto_structural_zero_all_years_in_both_scopes"


def _review_priority(primary_diagnostic: str) -> str:
    """Map evidence diagnostics to a compact review queue."""
    if "outside" in primary_diagnostic:
        return "boundary_policy_review"
    if "absent_from_generated_registry" in primary_diagnostic:
        return "source_authority_or_mapping_review"
    if "not_structurally_present" in primary_diagnostic:
        return "strong_mapping_review"
    if "missing_from_base_or_extended_scope" in primary_diagnostic:
        return "strong_mapping_review"
    return "zero_all_years_mapping_review"


def build_missing_mapping_review(
    current_relationships: pd.DataFrame,
    universes: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Return all current relationships omitted by the temporal compiler."""
    comparison = pd.read_csv(
        PROTOTYPE_DATA_ROOT
        / "qa_relationship_comparison_temporal.csv",
        low_memory=False,
    )
    missing = comparison.loc[
        comparison["relationship_status"].eq(
            "current_relationship_not_compiled"
        )
    ].copy()
    missing = missing.merge(
        current_relationships[
            RELATIONSHIP_KEYS
            + [
                "source_pair_is_subtotal",
                "target_pair_is_subtotal",
                "source_sheet",
                "workbook_row_number",
            ]
        ],
        on=RELATIONSHIP_KEYS,
        how="left",
        validate="one_to_one",
    )

    source_frames: list[pd.DataFrame] = []
    for source_system in ["LEAP", "NINTH"]:
        source = universes[source_system][
            ["flow", "product", "pair_is_subtotal"]
        ].drop_duplicates()
        source = source.rename(
            columns={
                "flow": "source_flow",
                "product": "source_product",
                "pair_is_subtotal": "generated_source_pair_is_subtotal",
            }
        )
        source["source_system"] = source_system
        source["source_pair_present_in_generated_registry"] = True
        source_frames.append(source)
    source_evidence = pd.concat(source_frames, ignore_index=True)
    missing = missing.merge(
        source_evidence,
        on=["source_system", "source_flow", "source_product"],
        how="left",
        validate="many_to_one",
    )
    missing["source_pair_present_in_generated_registry"] = (
        missing["source_pair_present_in_generated_registry"].eq(True)
    )

    for dataset, prefix in [
        ("ESTO", "esto"),
        ("ESTO_EXTENDED", "esto_extended"),
        ("NINTH", "ninth"),
    ]:
        missing = _merge_target_evidence(
            missing,
            universes[dataset],
            prefix,
        )

    missing["primary_diagnostic"] = [
        _classify_missing_relationship(row)
        for row in missing.itertuples(index=False)
    ]
    missing["review_queue"] = missing["primary_diagnostic"].map(
        _review_priority
    )
    missing["direct_evidence_note"] = missing["target_system"].map(
        {
            "ESTO": (
                "ESTO and ESTO Extended columns are direct. Ninth columns "
                "are not applicable without a reviewed cross-dataset mapping."
            ),
            "NINTH": (
                "Ninth columns are direct. ESTO columns are not applicable "
                "without a reviewed cross-dataset mapping."
            ),
        }
    )

    output_columns = [
        "review_queue",
        "primary_diagnostic",
        "mapping_name",
        "source_sheet",
        "workbook_row_number",
        "comparison_scope",
        "source_system",
        "source_flow",
        "source_product",
        "target_system",
        "target_flow",
        "target_product",
        "target_pair_registry_status",
        "source_pair_present_in_generated_registry",
        "source_pair_is_subtotal",
        "generated_source_pair_is_subtotal",
        "target_pair_is_subtotal",
        "esto_nonzero_any_year",
        "esto_historical_boundary_active",
        "esto_first_observed_year",
        "esto_last_observed_year",
        "esto_year_support_count",
        "esto_economy_support_count",
        "esto_nonzero_observation_count",
        "esto_temporal_evidence_status",
        "esto_pair_is_subtotal",
        "esto_extended_nonzero_any_year",
        "esto_extended_historical_boundary_active",
        "esto_extended_first_observed_year",
        "esto_extended_last_observed_year",
        "esto_extended_year_support_count",
        "esto_extended_economy_support_count",
        "esto_extended_nonzero_observation_count",
        "esto_extended_temporal_evidence_status",
        "esto_extended_pair_is_subtotal",
        "ninth_nonzero_any_year",
        "ninth_projection_future_active",
        "ninth_first_observed_year",
        "ninth_last_observed_year",
        "ninth_year_support_count",
        "ninth_economy_support_count",
        "ninth_nonzero_observation_count",
        "ninth_temporal_evidence_status",
        "ninth_pair_is_subtotal",
        "direct_evidence_note",
    ]
    return (
        missing[output_columns]
        .sort_values(
            [
                "review_queue",
                "mapping_name",
                "source_flow",
                "source_product",
                "target_flow",
                "target_product",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )


# --- Subtotal review --------------------------------------------------------

def _add_source_subtotal_registry(
    relationships: pd.DataFrame,
    universes: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Attach structural subtotal metadata for exact source pairs."""
    source_frames: list[pd.DataFrame] = []
    for source_system in ["LEAP", "NINTH"]:
        source = universes[source_system][
            ["flow", "product", "pair_is_subtotal"]
        ].drop_duplicates()
        source = source.rename(
            columns={
                "flow": "source_flow",
                "product": "source_product",
                "pair_is_subtotal": "registry_source_pair_is_subtotal",
            }
        )
        source["source_system"] = source_system
        source_frames.append(source)
    return relationships.merge(
        pd.concat(source_frames, ignore_index=True),
        on=["source_system", "source_flow", "source_product"],
        how="left",
        validate="many_to_one",
    )


def build_exact_subtotal_differences(
    current_relationships: pd.DataFrame,
    generated_relationships: pd.DataFrame,
) -> pd.DataFrame:
    """Compare subtotal flags on relationships present in both workbooks."""
    exact = current_relationships.merge(
        generated_relationships,
        on=RELATIONSHIP_KEYS,
        how="inner",
        suffixes=("_master", "_generated"),
        validate="one_to_one",
    )
    for side in ["source", "target"]:
        exact[f"{side}_subtotal_diff"] = exact[
            f"{side}_pair_is_subtotal_master"
        ].astype(bool).ne(
            exact[f"{side}_pair_is_subtotal_generated"].astype(bool)
        )
    difference = exact.loc[
        exact["source_subtotal_diff"] | exact["target_subtotal_diff"]
    ].copy()
    output_columns = (
        RELATIONSHIP_KEYS
        + [
            "source_sheet_master",
            "workbook_row_number_master",
            "source_pair_is_subtotal_master",
            "source_pair_is_subtotal_generated",
            "source_subtotal_diff",
            "target_pair_is_subtotal_master",
            "target_pair_is_subtotal_generated",
            "target_subtotal_diff",
        ]
    )
    return difference[output_columns].reset_index(drop=True)


def build_master_subtotal_review(
    current_relationships: pd.DataFrame,
    universes: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Return maintained rows with internal or registry subtotal conflicts."""
    review = current_relationships.copy()
    source_group_columns = [
        "mapping_name",
        "comparison_scope",
        "source_system",
        "source_flow",
        "source_product",
    ]
    target_group_columns = [
        "comparison_scope",
        "target_system",
        "target_flow",
        "target_product",
    ]
    review["source_flag_values_in_master"] = review.groupby(
        source_group_columns
    )["source_pair_is_subtotal"].transform("nunique")
    review["target_flag_values_in_master"] = review.groupby(
        target_group_columns
    )["target_pair_is_subtotal"].transform("nunique")
    review["source_flag_mixed_in_master"] = (
        review["source_flag_values_in_master"].gt(1)
    )
    review["target_flag_mixed_in_master"] = (
        review["target_flag_values_in_master"].gt(1)
    )

    review = _add_source_subtotal_registry(review, universes)
    review["source_registry_present"] = review[
        "registry_source_pair_is_subtotal"
    ].notna()
    review["source_flag_differs_from_registry"] = (
        review["source_registry_present"]
        & review["source_pair_is_subtotal"].astype(bool).ne(
            review["registry_source_pair_is_subtotal"]
            .fillna(False)
            .astype(bool)
        )
    )

    for dataset, prefix in [
        ("ESTO", "esto"),
        ("ESTO_EXTENDED", "esto_extended"),
        ("NINTH", "ninth"),
    ]:
        review = _merge_target_evidence(
            review,
            universes[dataset],
            prefix,
        )
        registry_column = f"{prefix}_pair_is_subtotal"
        mismatch_column = f"{prefix}_target_flag_differs_from_registry"
        review[mismatch_column] = (
            review[registry_column].notna()
            & review["target_pair_is_subtotal"].astype(bool).ne(
                review[registry_column].fillna(False).astype(bool)
            )
        )

    review["relevant_target_flag_differs_from_registry"] = (
        (
            review["target_system"].eq("NINTH")
            & review["ninth_target_flag_differs_from_registry"]
        )
        | (
            review["target_system"].eq("ESTO")
            & (
                review["esto_target_flag_differs_from_registry"]
                | review[
                    "esto_extended_target_flag_differs_from_registry"
                ]
            )
        )
    )
    issue_columns = [
        "source_flag_mixed_in_master",
        "target_flag_mixed_in_master",
        "source_flag_differs_from_registry",
        "relevant_target_flag_differs_from_registry",
    ]
    review["has_subtotal_review_issue"] = review[issue_columns].any(axis=1)

    def issue_summary(row: object) -> str:
        issues: list[str] = []
        if row.source_flag_mixed_in_master:
            issues.append("source_flag_mixed_within_master")
        if row.target_flag_mixed_in_master:
            issues.append("target_flag_mixed_within_master")
        if row.source_flag_differs_from_registry:
            issues.append("source_flag_differs_from_structural_registry")
        if row.relevant_target_flag_differs_from_registry:
            issues.append("target_flag_differs_from_structural_registry")
        return "|".join(issues)

    review["subtotal_review_reason"] = [
        issue_summary(row) for row in review.itertuples(index=False)
    ]
    review = review.loc[review["has_subtotal_review_issue"]].copy()
    output_columns = (
        [
            "subtotal_review_reason",
            "mapping_name",
            "source_sheet",
            "workbook_row_number",
            "comparison_scope",
            "source_system",
            "source_flow",
            "source_product",
            "target_system",
            "target_flow",
            "target_product",
            "source_pair_is_subtotal",
            "registry_source_pair_is_subtotal",
            "source_flag_mixed_in_master",
            "source_flag_differs_from_registry",
            "target_pair_is_subtotal",
            "esto_pair_is_subtotal",
            "esto_extended_pair_is_subtotal",
            "ninth_pair_is_subtotal",
            "target_flag_mixed_in_master",
            "relevant_target_flag_differs_from_registry",
        ]
    )
    return (
        review[output_columns]
        .sort_values(
            [
                "mapping_name",
                "subtotal_review_reason",
                "source_flow",
                "source_product",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )


# --- Summary and output -----------------------------------------------------

def build_summary(
    missing: pd.DataFrame,
    exact_subtotal_differences: pd.DataFrame,
    master_subtotal_review: pd.DataFrame,
    current_relationships: pd.DataFrame,
) -> pd.DataFrame:
    """Build a compact metric table for the workbook front page."""
    metrics: list[tuple[str, str, int | str]] = [
        (
            "Missing mappings",
            "current_relationships_not_generated",
            len(missing),
        ),
        (
            "Missing mappings",
            "reported_absent_status",
            int(missing["target_pair_registry_status"].eq("absent").sum()),
        ),
        (
            "Missing mappings",
            "reported_zero_only_status",
            int(
                missing["target_pair_registry_status"].eq("zero_only").sum()
            ),
        ),
        (
            "Interpretation",
            "boundary_policy_review_rows",
            int(missing["review_queue"].eq("boundary_policy_review").sum()),
        ),
        (
            "Interpretation",
            "source_authority_or_mapping_review_rows",
            int(
                missing["review_queue"]
                .eq("source_authority_or_mapping_review")
                .sum()
            ),
        ),
        (
            "Interpretation",
            "strong_mapping_review_rows",
            int(
                missing["review_queue"].eq("strong_mapping_review").sum()
            ),
        ),
        (
            "Interpretation",
            "zero_all_years_mapping_review_rows",
            int(
                missing["review_queue"]
                .eq("zero_all_years_mapping_review")
                .sum()
            ),
        ),
        (
            "Subtotals",
            "exact_relationship_subtotal_differences",
            len(exact_subtotal_differences),
        ),
        (
            "Subtotals",
            "master_relationships_with_subtotal_review_issue",
            len(master_subtotal_review),
        ),
        (
            "Subtotals",
            "total_current_master_relationships",
            len(current_relationships),
        ),
    ]
    summary = pd.DataFrame(
        metrics,
        columns=["section", "metric", "value"],
    )

    diagnostic_counts = (
        missing.groupby("primary_diagnostic")
        .size()
        .rename("value")
        .reset_index()
        .rename(columns={"primary_diagnostic": "metric"})
    )
    diagnostic_counts.insert(0, "section", "Primary diagnostics")
    return pd.concat([summary, diagnostic_counts], ignore_index=True)


def prepare_gap_review_sources() -> dict[str, object]:
    """Create CSV source tables and a small build manifest."""
    OUTPUT_DATA_ROOT.mkdir(parents=True, exist_ok=True)
    universes = _load_pair_universes()
    current_relationships, incomplete_current = load_active_mapping_contract(
        CANONICAL_MASTER_PATH
    )
    generated_relationships, incomplete_generated = (
        load_active_mapping_contract(GENERATED_MASTER_PATH)
    )
    if not incomplete_generated.empty:
        raise ValueError(
            "Generated master contains incomplete mapping rows: "
            f"{len(incomplete_generated)}"
        )

    missing = build_missing_mapping_review(
        current_relationships,
        universes,
    )
    exact_subtotal_differences = build_exact_subtotal_differences(
        current_relationships,
        generated_relationships,
    )
    master_subtotal_review = build_master_subtotal_review(
        current_relationships,
        universes,
    )
    summary = build_summary(
        missing,
        exact_subtotal_differences,
        master_subtotal_review,
        current_relationships,
    )

    outputs = {
        "summary": summary,
        "missing_mappings": missing,
        "exact_subtotal_differences": exact_subtotal_differences,
        "master_subtotal_review": master_subtotal_review,
        "incomplete_current_rows": incomplete_current,
    }
    output_paths: dict[str, str] = {}
    output_counts: dict[str, int] = {}
    for name, frame in outputs.items():
        path = OUTPUT_DATA_ROOT / f"{name}.csv"
        frame.to_csv(path, index=False)
        output_paths[name] = str(path.relative_to(OUTPUT_ROOT))
        output_counts[name] = len(frame)

    manifest: dict[str, object] = {
        "status": "Review-only. The canonical master was not edited.",
        "canonical_master_path": str(CANONICAL_MASTER_PATH),
        "generated_master_path": str(GENERATED_MASTER_PATH),
        "output_paths": output_paths,
        "output_counts": output_counts,
        "evidence_rule": (
            "Any-year evidence is direct exact-pair evidence within the "
            "coded target dataset. Cross-dataset evidence is intentionally "
            "not inferred."
        ),
    }
    (OUTPUT_ROOT / "gap_review_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return manifest


def run_gap_review_workflow() -> dict[str, object]:
    """Prepare review tables and build the formatted workbook in Python."""
    from codebase.separate_axis_mapping_gap_review_workbook_builder import (
        build_gap_review_workbook,
    )

    manifest = prepare_gap_review_sources()
    workbook_path = build_gap_review_workbook()
    manifest["workbook_path"] = str(workbook_path)
    return manifest


# --- Frequently changed run flag -------------------------------------------

PREPARE_GAP_REVIEW_SOURCES = True
BUILD_GAP_REVIEW_WORKBOOK = True


#%%
if PREPARE_GAP_REVIEW_SOURCES:
    try:
        if BUILD_GAP_REVIEW_WORKBOOK:
            GAP_REVIEW_MANIFEST = run_gap_review_workflow()
        else:
            GAP_REVIEW_MANIFEST = prepare_gap_review_sources()
        print(json.dumps(GAP_REVIEW_MANIFEST, indent=2))
    except Exception as error:
        print("Failed to prepare separate-axis gap review sources.")
        print(f"{type(error).__name__}: {error}")
        traceback.print_exc()
        raise


#%%
