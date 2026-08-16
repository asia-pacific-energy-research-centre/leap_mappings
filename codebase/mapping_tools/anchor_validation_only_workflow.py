#%%
"""Rerun source-parent anchor validation against an existing Stage 3 output."""

#%%
from __future__ import annotations

from pathlib import Path

import pandas as pd

from codebase.mapping_tools.typed_output import write_manifested_parquet

from codebase.mapping_tools.mapping_issue_exceptions import (
    load_unmodelled_source_codes,
)
from codebase.mapping_tools.non_expanding_rollups import (
    DETACHED_MODE,
    NON_EXPANDING_MODE,
    load_rollup_mode_labels,
)
from codebase.mapping_tools.source_branch_preflight import (
    load_source_branch_fallback_rules,
)
from codebase.mapping_tools.source_parent_anchor_validation import (
    build_failed_anchor_mapped_component_context_values,
    build_failed_anchor_raw_child_context_values,
    build_leaf_reconciliation_exception_candidates,
    load_raw_source_anchor_inputs,
    select_source_parent_anchor_findings,
    summarise_failed_anchor_raw_child_context_values,
    summarise_source_parent_anchors,
)
from codebase.mapping_tools.apec_anchor_validation import (
    validate_source_parent_anchors_apec_first,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
ANCHOR_COMPARISON_COLUMNS = [
    "comparison_scope",
    "source_system",
    "economy",
    "scenario",
    "year",
    "common_row_id",
    "value",
]


def _anchor_years_by_system(
    source_df: pd.DataFrame,
    target_years: set[int],
) -> dict[str, set[int]]:
    """Intersect each source's available years with the reviewed test slice."""
    numeric_years = pd.to_numeric(source_df["year"], errors="coerce")
    return {
        source_system: (
            set(
                numeric_years[
                    source_df["source_system"].astype(str).eq(source_system)
                ]
                .dropna()
                .astype(int)
            )
            & target_years
        )
        for source_system in source_df["source_system"].dropna().astype(str).unique()
    }


def _anchor_exclude_parents(
    workbook_path: Path,
    source_branch_fallback_rules_path: Path,
) -> set[str]:
    """Return non-additive rollup and interim branch labels."""
    excluded = {
        label
        for label, mode in load_rollup_mode_labels(workbook_path).items()
        if mode in {NON_EXPANDING_MODE, DETACHED_MODE}
    }
    fallback_rules = load_source_branch_fallback_rules(
        source_branch_fallback_rules_path
    )
    excluded.update({
        str(branch).strip()
        for branch in fallback_rules.get("interim_branch", [])
        if str(branch).strip()
    })
    return excluded


def _read_anchor_comparison_slice(
    comparison_data_path: Path,
    years_by_system: dict[str, set[int]],
    chunk_size: int = 250_000,
) -> pd.DataFrame:
    """Read only the columns and source/year contexts used by the anchor pass."""
    selected_chunks: list[pd.DataFrame] = []
    for chunk in pd.read_csv(
        comparison_data_path,
        usecols=ANCHOR_COMPARISON_COLUMNS,
        dtype=object,
        chunksize=chunk_size,
    ):
        numeric_years = pd.to_numeric(chunk["year"], errors="coerce")
        source_systems = chunk["source_system"].astype(str)
        keep = pd.Series(False, index=chunk.index)
        for source_system, allowed_years in years_by_system.items():
            keep |= source_systems.eq(source_system) & numeric_years.isin(
                allowed_years
            )
        if keep.any():
            selected = chunk.loc[keep, ANCHOR_COMPARISON_COLUMNS].copy()
            selected["year"] = numeric_years.loc[keep]
            selected_chunks.append(selected)
    if not selected_chunks:
        return pd.DataFrame(columns=ANCHOR_COMPARISON_COLUMNS)
    return pd.concat(selected_chunks, ignore_index=True)


def run_anchor_validation_only(
    esto_data_path: Path,
    esto_extended_data_path: Path,
    ninth_data_path: Path,
    raw_leap_path: Path,
    workbook_path: Path,
    common_rows_path: Path,
    comparison_data_path: Path,
    validation_tree_path: Path,
    source_branch_fallback_rules_path: Path,
    output_dir: Path,
    run_id: str,
    leap_var_base_year: int = 2022,
    anchor_target_years: set[int] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the anchor phase alone and publish the normal diagnostic family."""
    target_years = (
        set(range(2030, 2071, 10))
        if anchor_target_years is None
        else set(anchor_target_years)
    )
    source_df, source_mapping = load_raw_source_anchor_inputs(
        esto_data_path=esto_data_path,
        esto_extended_data_path=esto_extended_data_path,
        ninth_data_path=ninth_data_path,
        raw_leap_path=raw_leap_path,
        workbook_path=workbook_path,
        leap_var_base_year=leap_var_base_year,
        anchor_target_years=target_years,
    )
    numeric_years = pd.to_numeric(source_df["year"], errors="coerce")
    esto_years = numeric_years[
        source_df["source_system"].astype(str).eq("ESTO")
    ].dropna()
    if not esto_years.empty:
        target_years.add(int(esto_years.max()))
    years_by_system = _anchor_years_by_system(source_df, target_years)

    validation_tree = pd.read_csv(validation_tree_path, dtype=object)
    common_rows = pd.read_csv(common_rows_path, dtype=object)
    comparison = _read_anchor_comparison_slice(
        comparison_data_path,
        years_by_system,
    )
    excluded_parents = _anchor_exclude_parents(
        workbook_path,
        source_branch_fallback_rules_path,
    )
    anchor_result = validate_source_parent_anchors_apec_first(
        source_df=source_df,
        source_tree_df=validation_tree,
        source_mapping_df=source_mapping,
        common_rows_df=common_rows,
        years_by_system=years_by_system,
        comparison_df=comparison,
        unmodelled_source_codes=load_unmodelled_source_codes(),
        exclude_parents=excluded_parents,
    )
    detail = anchor_result["apec_detail"]
    economy_examples = anchor_result["economy_examples"]

    child_context = build_failed_anchor_raw_child_context_values(
        detail,
        anchor_result["apec_source"],
        validation_tree,
    )
    child_values = summarise_failed_anchor_raw_child_context_values(
        child_context
    )
    mapped_component_context = (
        build_failed_anchor_mapped_component_context_values(
            detail,
            validation_tree,
            source_mapping,
            common_rows,
            anchor_result["apec_comparison"],
        )
    )
    economy_child_context = build_failed_anchor_raw_child_context_values(
        economy_examples,
        source_df,
        validation_tree,
    )
    economy_mapped_component_context = (
        build_failed_anchor_mapped_component_context_values(
            economy_examples,
            validation_tree,
            source_mapping,
            common_rows,
            comparison,
        )
    )
    leaf_candidates = build_leaf_reconciliation_exception_candidates(
        detail,
        anchor_result["apec_source"],
        validation_tree,
    )
    summary = summarise_source_parent_anchors(detail)

    output_dir.mkdir(parents=True, exist_ok=True)
    frames = {
        "source_parent_anchor_validation": select_source_parent_anchor_findings(
            detail
        ),
        "source_parent_anchor_validation_full": detail,
        "source_parent_anchor_validation_summary": summary,
        "source_parent_anchor_economy_examples": economy_examples,
        "source_parent_anchor_child_values": child_values,
        "source_parent_anchor_child_context_values": child_context,
        "source_parent_anchor_mapped_component_context_values": (
            mapped_component_context
        ),
        "source_parent_anchor_economy_child_context_values": economy_child_context,
        "source_parent_anchor_economy_mapped_component_context_values": (
            economy_mapped_component_context
        ),
        "source_parent_anchor_leaf_reconciliation_candidates": leaf_candidates,
    }
    parquet_detail_names = {
        "source_parent_anchor_validation_full",
        "source_parent_anchor_child_context_values",
        "source_parent_anchor_mapped_component_context_values",
        "source_parent_anchor_economy_child_context_values",
        "source_parent_anchor_economy_mapped_component_context_values",
    }
    for name, frame in frames.items():
        published = frame.copy()
        published.insert(0, "run_id", run_id)
        if name in parquet_detail_names:
            write_manifested_parquet(
                published,
                output_dir / f"{name}.parquet",
                artifact_type=f"{name}_detail",
            )
        else:
            published.to_csv(output_dir / f"{name}.csv", index=False)
    return detail, summary


#%%
RUN_ANCHOR_VALIDATION_ONLY = False

if RUN_ANCHOR_VALIDATION_ONLY:
    raise RuntimeError(
        "Set explicit paths in a notebook cell before running anchor validation."
    )

#%%
