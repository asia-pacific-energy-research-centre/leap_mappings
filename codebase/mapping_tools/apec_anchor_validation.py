#%%
"""Run source-parent anchor validation APEC-first, then attribute failures.

The mapping structure is common across economies.  This module therefore sums
the numeric source and Common ESTO inputs to one ``00APEC`` balance, validates
that balance once, and only runs economy-granular checks for branch contexts
that failed at APEC level.
"""

#%%
from __future__ import annotations

import pandas as pd

from codebase.mapping_tools.source_parent_anchor_validation import (
    validate_source_parent_anchors,
)


APEC_ECONOMY = "00APEC"
APEC_ABSOLUTE_TOLERANCE_PJ = 0.01
APEC_ISSUE_COLUMNS = [
    "validation_axis",
    "comparison_scope",
    "source_system",
    "scenario",
    "year",
    "other_axis_value",
    "parent_code",
]
APEC_TARGET_FILTER_COLUMNS = [
    "validation_axis",
    "source_system",
    "scenario",
    "year",
    "other_axis_value",
    "parent_code",
]


#%%
def aggregate_anchor_inputs_to_apec(
    source_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sum only the economy axis while preserving validation context."""
    source_columns = [
        "source_system", "scenario", "year", "source_flow", "source_product",
    ]
    comparison_columns = [
        "comparison_scope", "source_system", "scenario", "year", "common_row_id",
    ]
    missing_source = set(source_columns + ["economy", "value"]).difference(source_df.columns)
    missing_comparison = set(comparison_columns + ["economy", "value"]).difference(
        comparison_df.columns
    )
    if missing_source:
        raise ValueError(f"APEC source aggregation is missing columns: {sorted(missing_source)}")
    if missing_comparison:
        raise ValueError(
            f"APEC comparison aggregation is missing columns: {sorted(missing_comparison)}"
        )

    source = source_df[source_columns + ["value"]].copy()
    source["value"] = pd.to_numeric(source["value"], errors="coerce").fillna(0.0)
    source = source.groupby(source_columns, dropna=False, as_index=False)["value"].sum()
    source.insert(1, "economy", APEC_ECONOMY)

    comparison = comparison_df[comparison_columns + ["value"]].copy()
    comparison["value"] = pd.to_numeric(comparison["value"], errors="coerce").fillna(0.0)
    comparison = comparison.groupby(
        comparison_columns, dropna=False, as_index=False
    )["value"].sum()
    comparison.insert(2, "economy", APEC_ECONOMY)
    return source, comparison


def select_apec_anchor_issues(apec_detail: pd.DataFrame) -> pd.DataFrame:
    """Return the unique failed APEC signatures used for attribution."""
    if apec_detail.empty or "status" not in apec_detail.columns:
        return pd.DataFrame(columns=APEC_ISSUE_COLUMNS)
    missing = set(APEC_ISSUE_COLUMNS).difference(apec_detail.columns)
    if missing:
        raise ValueError(f"APEC anchor output is missing issue columns: {sorted(missing)}")
    return (
        apec_detail[apec_detail["status"].astype(str).eq("failed")]
        [APEC_ISSUE_COLUMNS]
        .drop_duplicates()
        .reset_index(drop=True)
    )


def select_economy_examples_for_apec_issues(
    economy_detail: pd.DataFrame,
    apec_issues: pd.DataFrame,
) -> pd.DataFrame:
    """Keep exact economy checks related to failed APEC signatures."""
    if economy_detail.empty or apec_issues.empty:
        return economy_detail.iloc[0:0].copy()
    issue_keys = apec_issues[APEC_ISSUE_COLUMNS].drop_duplicates()
    examples = economy_detail.merge(issue_keys, on=APEC_ISSUE_COLUMNS, how="inner")
    examples = examples[examples["economy"].astype(str).ne(APEC_ECONOMY)].copy()
    if examples.empty:
        return examples
    examples["is_failed_economy_example"] = examples["status"].astype(str).eq("failed")
    examples["apec_issue_has_failed_economy_example"] = examples.groupby(
        APEC_ISSUE_COLUMNS, dropna=False
    )["is_failed_economy_example"].transform("any")
    examples["attribution_status"] = examples[
        "apec_issue_has_failed_economy_example"
    ].map({True: "economy_examples_found", False: "no_economy_example_found"})
    return examples.sort_values(
        [*APEC_ISSUE_COLUMNS, "is_failed_economy_example", "abs_error"],
        ascending=[True] * len(APEC_ISSUE_COLUMNS) + [False, False],
        kind="mergesort",
    ).reset_index(drop=True)


def add_apec_attribution_status(
    apec_detail: pd.DataFrame,
    economy_examples: pd.DataFrame,
) -> pd.DataFrame:
    """Attach economy-example availability to every failed APEC check."""
    result = apec_detail.copy()
    result["attribution_status"] = "not_required"
    failed = result["status"].astype(str).eq("failed")
    result.loc[failed, "attribution_status"] = "no_economy_example_found"
    if economy_examples.empty:
        return result
    found = (
        economy_examples[economy_examples["status"].astype(str).eq("failed")]
        [APEC_ISSUE_COLUMNS]
        .drop_duplicates()
        .assign(attribution_status="economy_examples_found")
    )
    result = result.merge(found, on=APEC_ISSUE_COLUMNS, how="left", suffixes=("", "_found"))
    found_mask = result["attribution_status_found"].notna()
    result.loc[found_mask, "attribution_status"] = result.loc[
        found_mask, "attribution_status_found"
    ]
    return result.drop(columns=["attribution_status_found"])


def validate_source_parent_anchors_apec_first(
    source_df: pd.DataFrame,
    source_tree_df: pd.DataFrame,
    source_mapping_df: pd.DataFrame,
    common_rows_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
    tolerance: float = 0.01,
    apec_absolute_tolerance: float = APEC_ABSOLUTE_TOLERANCE_PJ,
    years_by_system: dict[str, set[int]] | None = None,
    unmodelled_source_codes: dict[str, set[int]] | None = None,
    exclude_parents: set[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Validate APEC, then calculate only economy contexts for APEC failures."""
    apec_source, apec_comparison = aggregate_anchor_inputs_to_apec(
        source_df, comparison_df
    )
    apec_detail = validate_source_parent_anchors(
        source_df=apec_source,
        source_tree_df=source_tree_df,
        source_mapping_df=source_mapping_df,
        common_rows_df=common_rows_df,
        comparison_df=apec_comparison,
        tolerance=tolerance,
        absolute_tolerance=apec_absolute_tolerance,
        economies={APEC_ECONOMY},
        years_by_system=years_by_system,
        unmodelled_source_codes=unmodelled_source_codes,
        exclude_parents=exclude_parents,
    )
    apec_issues = select_apec_anchor_issues(apec_detail)
    if apec_issues.empty:
        economy_examples = apec_detail.iloc[0:0].copy()
    else:
        economy_detail = validate_source_parent_anchors(
            source_df=source_df,
            source_tree_df=source_tree_df,
            source_mapping_df=source_mapping_df,
            common_rows_df=common_rows_df,
            comparison_df=comparison_df,
            tolerance=tolerance,
            absolute_tolerance=None,
            years_by_system=years_by_system,
            unmodelled_source_codes=unmodelled_source_codes,
            exclude_parents=exclude_parents,
            issue_filter=apec_issues[APEC_TARGET_FILTER_COLUMNS],
        )
        economy_examples = select_economy_examples_for_apec_issues(
            economy_detail, apec_issues
        )
    apec_detail = add_apec_attribution_status(apec_detail, economy_examples)
    return {
        "apec_detail": apec_detail,
        "apec_issues": apec_issues,
        "economy_examples": economy_examples,
        "apec_source": apec_source,
        "apec_comparison": apec_comparison,
    }


#%%
