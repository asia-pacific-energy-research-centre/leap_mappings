#%%
"""Apply workbook rollup rules to source result rows before mapping joins."""

#%%
from __future__ import annotations

import pandas as pd


ROLLUP_AUDIT_COLUMNS = [
    "issue_type",
    "input_flow",
    "input_product",
    "rolled_flow",
    "rolled_product",
    "rule_count",
    "reason",
]


def _truthy(values: pd.Series) -> pd.Series:
    """Return a boolean mask for common spreadsheet truth values."""
    return values.apply(
        lambda value: value is True or str(value).strip().casefold() in {"true", "1", "yes"}
    )


def prepare_source_rollup_rules(
    rules_df: pd.DataFrame,
    input_flow_column: str,
    input_product_column: str,
    rolled_flow_column: str,
    rolled_product_column: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Normalize active rules and report exact duplicates.

    One input may intentionally feed several nested aggregate rows. That is not
    classified as a duplicate here. Only repeated rules with the same complete
    input and rolled pair are collapsed and reported.
    """
    required = [input_flow_column, rolled_flow_column]
    missing = [column for column in required if column not in rules_df.columns]
    if missing:
        raise ValueError(f"Rollup rules are missing required columns: {missing}")

    rules = rules_df.copy()
    if "include" in rules.columns:
        rules = rules[_truthy(rules["include"])]

    for column in [
        input_flow_column,
        input_product_column,
        rolled_flow_column,
        rolled_product_column,
    ]:
        if column not in rules.columns:
            rules[column] = ""
        rules[column] = rules[column].fillna("").astype(str).str.strip()

    rules = rules[
        rules[input_flow_column].ne("") & rules[rolled_flow_column].ne("")
    ].copy()
    key_columns = [
        input_flow_column,
        input_product_column,
        rolled_flow_column,
        rolled_product_column,
    ]
    duplicate_counts = (
        rules.groupby(key_columns, dropna=False)
        .size()
        .rename("rule_count")
        .reset_index()
    )
    duplicate_counts = duplicate_counts[duplicate_counts["rule_count"] > 1]
    if duplicate_counts.empty:
        audit = pd.DataFrame(columns=ROLLUP_AUDIT_COLUMNS)
    else:
        audit = duplicate_counts.rename(columns={
            input_flow_column: "input_flow",
            input_product_column: "input_product",
            rolled_flow_column: "rolled_flow",
            rolled_product_column: "rolled_product",
        })
        audit.insert(0, "issue_type", "exact_duplicate_rule")
        audit["reason"] = "Identical active rollup rule occurs more than once; applied once."
        audit = audit[ROLLUP_AUDIT_COLUMNS]

    return rules.drop_duplicates(key_columns).reset_index(drop=True), audit


def apply_source_rollups(
    source_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    source_flow_column: str,
    source_product_column: str,
    value_column: str,
    input_flow_column: str,
    input_product_column: str,
    rolled_flow_column: str,
    rolled_product_column: str,
    allowed_rolled_pairs: set[tuple[str, str]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return original source rows plus rule-derived aggregate rows.

    Blank input products match every product. Blank rolled products preserve the
    source product. Several inputs assigned to the same rolled pair are summed
    naturally by downstream grouping. Original rows remain available as a
    separate detailed view.
    """
    required_source = [source_flow_column, source_product_column, value_column]
    missing = [column for column in required_source if column not in source_df.columns]
    if missing:
        raise ValueError(f"Source data are missing required columns: {missing}")

    source = source_df.copy()
    source[value_column] = pd.to_numeric(source[value_column], errors="coerce").fillna(0.0)
    rules, audit = prepare_source_rollup_rules(
        rules_df=rules_df,
        input_flow_column=input_flow_column,
        input_product_column=input_product_column,
        rolled_flow_column=rolled_flow_column,
        rolled_product_column=rolled_product_column,
    )
    derived_frames: list[pd.DataFrame] = []
    for rule in rules.to_dict("records"):
        mask = source[source_flow_column].astype(str).str.strip().eq(rule[input_flow_column])
        input_product = rule[input_product_column]
        if input_product:
            mask &= source[source_product_column].astype(str).str.strip().eq(input_product)
        matched = source[mask].copy()
        if matched.empty:
            continue

        rolled_product = rule[rolled_product_column]
        matched[source_flow_column] = rule[rolled_flow_column]
        if rolled_product:
            matched[source_product_column] = rolled_product

        if allowed_rolled_pairs is not None:
            pair_mask = [
                (str(flow).strip(), str(product).strip()) in allowed_rolled_pairs
                for flow, product in zip(
                    matched[source_flow_column], matched[source_product_column]
                )
            ]
            matched = matched[pair_mask]
        if not matched.empty:
            derived_frames.append(matched)

    if not derived_frames:
        return source, audit
    return pd.concat([source, *derived_frames], ignore_index=True), audit

#%%
