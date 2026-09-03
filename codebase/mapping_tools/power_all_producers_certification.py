"""Focused, reproducible certification checks for Power all-producers mappings."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


POWER_CONTEXT = "power_process_comparison"
POWER_ROLLUP_COLUMNS = [
    "input_esto_flow",
    "rolled_esto_flow",
    "rollup_group_id",
]
SOURCE_GROUP_COLUMNS = [
    "source_system", "economy", "scenario", "year", "source_flow", "source_product"
]
VALUE_GROUP_COLUMNS = ["economy", "scenario", "year"]
EXPECTED_POWER_COMPONENT_COUNT = 2


def _truthy(values: pd.Series) -> pd.Series:
    return values.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def registered_power_rollups(esto_rules: pd.DataFrame) -> pd.DataFrame:
    """Return the reviewed two-component producer rollups, one row per group."""
    rules = esto_rules.copy().fillna("")
    selected = rules.loc[
        _truthy(rules["include"])
        & rules["rollup_context"].eq(POWER_CONTEXT)
        & rules["ROLLUP_MODE"].eq("EXPANDING"),
        POWER_ROLLUP_COLUMNS,
    ].drop_duplicates()
    grouped = (
        selected.groupby(["rolled_esto_flow", "rollup_group_id"], as_index=False)
        .agg(component_count=("input_esto_flow", "nunique"), components=("input_esto_flow", lambda x: "|".join(sorted(x))))
        .sort_values("rolled_esto_flow")
        .reset_index(drop=True)
    )
    return grouped


def audit_source_once_delivery(
    source_lineage: pd.DataFrame,
    power_targets: Iterable[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Check observed non-zero LEAP/Ninth Power observations reach one target."""
    targets = set(power_targets)
    frame = source_lineage.copy()
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce").fillna(0.0)
    frame = frame.loc[
        frame["source_system"].isin(["LEAP", "NINTH"])
        & frame["target_flow"].isin(targets)
        & frame["value"].ne(0.0)
    ]
    if frame.empty:
        return (
            pd.DataFrame(columns=[*SOURCE_GROUP_COLUMNS, "target_flow_count", "target_flows", "status"]),
            pd.DataFrame(columns=["source_system", "observations", "failures"]),
        )
    detail = (
        frame.groupby(SOURCE_GROUP_COLUMNS, as_index=False)
        .agg(
            target_flow_count=("target_flow", "nunique"),
            target_flows=("target_flow", lambda x: "|".join(sorted(set(x)))),
        )
    )
    detail["status"] = detail["target_flow_count"].eq(1).map({True: "passed", False: "failed"})
    summary = (
        detail.groupby("source_system", as_index=False)
        .agg(observations=("status", "size"), failures=("status", lambda x: int((x == "failed").sum())))
    )
    return detail, summary


def audit_structural_component_definitions(
    common_rows: pd.DataFrame,
    rollups: pd.DataFrame,
    expected_component_count: int = EXPECTED_POWER_COMPONENT_COUNT,
) -> pd.DataFrame:
    """Certify reviewed targets and their independently registered components.

    This validates definitions only.  It never compares a target against an
    ESTO Extended numeric series and does not infer missing components.
    """
    required = rollups[["rolled_esto_flow", "components"]].copy()
    required["components"] = required["components"].fillna("").astype(str)
    required["registered_component_count"] = required["components"].map(
        lambda value: len({item.strip() for item in value.split("|") if item.strip()})
    )
    targets = (
        common_rows[["comparison_scope", "component_esto_flow"]]
        .drop_duplicates()
        .groupby("component_esto_flow")["comparison_scope"]
        .agg(lambda values: "|".join(sorted(set(values.astype(str)))))
        .reset_index()
        .rename(columns={"component_esto_flow": "rolled_esto_flow"})
    )
    audit = required.merge(targets, on="rolled_esto_flow", how="left")
    audit["comparison_scope"] = audit["comparison_scope"].fillna("")
    audit["expected_component_count"] = expected_component_count
    audit["target_status"] = audit["comparison_scope"].ne("").map(
        {True: "passed", False: "missing_structural_target"}
    )
    audit["component_set_status"] = audit["registered_component_count"].eq(
        expected_component_count
    ).map({True: "passed", False: "incomplete_component_set"})
    audit["status"] = (
        audit["target_status"].eq("passed")
        & audit["component_set_status"].eq("passed")
    ).map({True: "passed", False: "failed"})
    return audit[[
        "comparison_scope", "rolled_esto_flow", "components",
        "expected_component_count", "registered_component_count",
        "target_status", "component_set_status", "status",
    ]]


def audit_ordinary_esto_component_coverage(
    esto_exact_rows: pd.DataFrame,
    rollups: pd.DataFrame,
    expected_component_count: int = EXPECTED_POWER_COMPONENT_COUNT,
) -> pd.DataFrame:
    """Report full, partial, and absent ordinary-ESTO component coverage."""
    components = rollups[["rolled_esto_flow", "components"]].copy()
    components["component_esto_flow"] = components["components"].str.split("|")
    components = components.explode("component_esto_flow").drop(columns="components")
    components["component_esto_flow"] = components["component_esto_flow"].astype(str).str.strip()
    components = components.loc[components["component_esto_flow"].ne("")].drop_duplicates()
    raw = esto_exact_rows.copy()
    raw["value"] = pd.to_numeric(raw["value"], errors="coerce").fillna(0.0)
    raw = raw.loc[raw["esto_flow"].isin(set(components["component_esto_flow"]))]
    raw = raw.merge(
        components,
        left_on="esto_flow",
        right_on="component_esto_flow",
        how="inner",
    )
    raw = raw.groupby(
        ["rolled_esto_flow", "esto_product", *VALUE_GROUP_COLUMNS],
        as_index=False,
    ).agg(
        component_total=("value", "sum"),
        observed_component_count=("component_esto_flow", "nunique"),
        observed_components=(
            "component_esto_flow", lambda values: "|".join(sorted(set(values)))
        ),
    )
    raw = raw.rename(columns={"esto_product": "component_esto_product"})
    raw["expected_component_count"] = expected_component_count
    raw["status"] = raw["observed_component_count"].eq(
        expected_component_count
    ).map({
        True: "full_ordinary_esto_component_coverage",
        False: "partial_ordinary_esto_component_coverage",
    })
    no_data_targets = set(rollups["rolled_esto_flow"]) - set(raw["rolled_esto_flow"])
    no_data = pd.DataFrame([
        {
            "rolled_esto_flow": target,
            "component_esto_product": "",
            "economy": "",
            "scenario": "",
            "year": "",
            "component_total": 0.0,
            "expected_component_count": expected_component_count,
            "observed_component_count": 0,
            "observed_components": "",
            "status": "no_data",
        }
        for target in sorted(no_data_targets)
    ])
    coverage = pd.concat([raw, no_data], ignore_index=True)
    return coverage[[
        "rolled_esto_flow", "component_esto_product", *VALUE_GROUP_COLUMNS,
        "component_total", "expected_component_count", "observed_component_count",
        "observed_components", "status",
    ]]


def audit_alias_cooccurrence(raw_leap: pd.DataFrame) -> pd.DataFrame:
    """Inventory non-zero observations where fallback aliases coexist."""
    groups = {
        "storage": [
            "Electricity Generation/Battery",
            "Electricity Generation/Batteries",
            "Electricity Generation/Distributed storage",
        ],
        "solar_rooftop": [
            "Electricity Generation/Solar rooftop",
            "Electricity Generation/Solar_rooftop",
        ],
    }
    data = raw_leap.copy()
    data["value"] = pd.to_numeric(data["value"], errors="coerce").fillna(0.0)
    rows: list[pd.DataFrame] = []
    for alias_group, branches in groups.items():
        subset = data.loc[data["leap_flow"].isin(branches) & data["value"].ne(0.0)]
        if subset.empty:
            continue
        summary = (
            subset.groupby(["economy", "scenario", "year"], as_index=False)
            .agg(nonzero_aliases=("leap_flow", lambda x: "|".join(sorted(set(x)))),
                 alias_count=("leap_flow", "nunique"), total_value=("value", "sum"))
        )
        summary.insert(0, "alias_group", alias_group)
        summary["status"] = summary["alias_count"].gt(1).map({True: "double_count_risk", False: "single_alias_only"})
        rows.append(summary)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        columns=["alias_group", "economy", "scenario", "year", "nonzero_aliases", "alias_count", "total_value", "status"]
    )
