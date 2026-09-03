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
) -> pd.DataFrame:
    """Certify that each all-producer target declares its registered components."""
    required = rollups[["rolled_esto_flow", "components"]].copy()
    required["component_esto_flow_registered"] = required["components"].str.split("|")
    required = required.explode("component_esto_flow_registered").drop(columns="components")
    available = common_rows[["comparison_scope", "component_esto_flow"]].drop_duplicates()
    observed = required.merge(
        available,
        left_on="rolled_esto_flow",
        right_on="component_esto_flow",
        how="left",
    )
    observed["status"] = observed["comparison_scope"].notna().map(
        {True: "passed", False: "missing_structural_target"}
    )
    return observed[[
        "comparison_scope", "rolled_esto_flow", "component_esto_flow_registered", "status",
    ]]


def audit_ordinary_esto_component_coverage(
    esto_exact_rows: pd.DataFrame,
    rollups: pd.DataFrame,
) -> pd.DataFrame:
    """Report ordinary-ESTO component coverage without manufacturing Extended facts."""
    components = rollups[["rolled_esto_flow", "components"]].copy()
    components["component_esto_flow"] = components["components"].str.split("|")
    components = components.explode("component_esto_flow").drop(columns="components")
    raw = esto_exact_rows.copy()
    raw["value"] = pd.to_numeric(raw["value"], errors="coerce").fillna(0.0)
    raw = raw.loc[raw["esto_flow"].isin(set(components["component_esto_flow"]))]
    raw = raw.merge(
        components,
        left_on="esto_flow",
        right_on="component_esto_flow",
        how="inner",
    )
    raw = (
        raw.groupby(["rolled_esto_flow", "esto_product", *VALUE_GROUP_COLUMNS], as_index=False)["value"]
        .sum()
        .rename(columns={"esto_product": "component_esto_product", "value": "component_total"})
    )
    raw["status"] = raw["component_total"].ne(0.0).map(
        {True: "observed_ordinary_esto_component_coverage", False: "no_data"}
    )
    return raw[[
        "rolled_esto_flow", "component_esto_product", *VALUE_GROUP_COLUMNS,
        "component_total", "status",
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
