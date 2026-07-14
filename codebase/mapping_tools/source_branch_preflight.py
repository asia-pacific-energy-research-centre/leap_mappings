#%%
"""Early LEAP source-branch preflight checks and adjustments.

Runs on parsed raw LEAP balance rows after parsing but before
``apply_source_rollups``, conversion, or Common ESTO application.

Two configuration-owned checks:

1. ``config/source_branch_fallback_rules.csv`` — standard/interim alternative
   branch pairs. When both branches have any non-zero energy for one
   economy/scenario/year, all interim values for that branch and period are
   set to zero in the downstream working data (``warn_and_zero_interim``) and
   an audit row is written. The parsed raw input file is never altered.
   Interim-only periods are retained unchanged.

2. ``config/all_demand_aggregated_components.json`` — the human-owned record of
   which LEAP demand sectors are included in ``All demand aggregated``. When
   the aggregate and any configured included sector are both non-zero in the
   same period, a highly visible warning is recorded without changing values.
   Each component has an ``include_by_default`` flag applied to every economy,
   plus an optional ``economy_overrides`` map keyed by economy code
   (``{"include": bool, "note": str}``) that overrides the default for that
   economy only, so a specific economy can be marked as no longer
   aggregate-only once it gains detailed source data.
   ``load_all_demand_aggregated_components()`` flattens this into the same
   long-form table used internally (columns: economy, aggregated_branch,
   component_branch, include, note), with ``economy == ""`` meaning the
   wildcard default row. ``get_demand_sectors_without_detail()`` exposes the
   resolved per-economy list to downstream consumers (e.g. the dashboard
   workflow, to skip rendering demand-sector pages that have no LEAP detail).
"""

#%%
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

#%%
WARN_AND_ZERO_INTERIM = "warn_and_zero_interim"

FALLBACK_RULE_COLUMNS = ["rule_id", "standard_branch", "interim_branch", "action", "include", "note"]
FALLBACK_AUDIT_COLUMNS = [
    "rule_id",
    "standard_branch",
    "interim_branch",
    "economy",
    "scenario",
    "year",
    "action",
    "status",
    "standard_total",
    "interim_total_original",
    "interim_total_suppressed",
    "interim_total_retained",
    "interim_rows_zeroed",
]

ALL_DEMAND_COMPONENT_COLUMNS = ["economy", "aggregated_branch", "component_branch", "include", "note"]
ALL_DEMAND_WARNING_COLUMNS = [
    "economy",
    "scenario",
    "year",
    "aggregated_branch",
    "aggregated_total",
    "component_branch",
    "component_total",
    "nonzero_configured_components",
    "configured_components",
    "reminder",
]

ALL_DEMAND_REMINDER = (
    "All demand aggregated and a configured included demand sector are both non-zero. "
    "Confirm config/all_demand_aggregated_components.json still reflects which values "
    "are actually attributed to All demand aggregated; values were NOT changed."
)

PERIOD_COLUMNS = ["economy", "scenario", "year"]


def _str(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _str(value).casefold() in {"true", "1", "yes", "y"}


def load_source_branch_fallback_rules(path: Path) -> pd.DataFrame:
    """Load enabled standard/interim fallback rules from configuration."""
    if not Path(path).exists():
        return pd.DataFrame(columns=FALLBACK_RULE_COLUMNS)
    rules_df = pd.read_csv(path, dtype=object).fillna("")
    missing = [column for column in FALLBACK_RULE_COLUMNS if column not in rules_df.columns]
    if missing:
        raise ValueError(f"source_branch_fallback_rules is missing columns: {missing}")
    rules_df = rules_df[rules_df["include"].map(_truthy)].reset_index(drop=True)
    unknown_actions = sorted(
        {
            _str(action)
            for action in rules_df["action"]
            if _str(action) and _str(action) != WARN_AND_ZERO_INTERIM
        }
    )
    if unknown_actions:
        raise ValueError(
            f"Unsupported source-branch fallback actions: {unknown_actions}. "
            f"Only {WARN_AND_ZERO_INTERIM!r} is implemented."
        )
    return rules_df[FALLBACK_RULE_COLUMNS]


def branch_mask(flows: pd.Series, branch: str) -> pd.Series:
    """Whole-sector match: the branch itself plus every descendant path."""
    text = flows.astype(str).str.strip()
    return text.eq(branch) | text.str.startswith(f"{branch}/")


def _nonzero_periods(leap_df: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    """Return per-period any-nonzero flags and totals for the masked rows."""
    matched = leap_df[mask]
    if matched.empty:
        return pd.DataFrame(columns=PERIOD_COLUMNS + ["any_nonzero", "total"])
    working = matched[PERIOD_COLUMNS].copy()
    values = pd.to_numeric(matched["value"], errors="coerce").fillna(0.0)
    working["_nonzero"] = values.ne(0.0)
    working["_value"] = values
    grouped = working.groupby(PERIOD_COLUMNS, as_index=False).agg(
        any_nonzero=("_nonzero", "any"),
        total=("_value", "sum"),
    )
    return grouped


def apply_source_branch_fallbacks(
    leap_df: pd.DataFrame,
    rules_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply the ``warn_and_zero_interim`` policy to parsed LEAP working data.

    Returns the adjusted working frame plus one audit row per rule and period
    where the interim branch had non-zero energy. ``status`` is
    ``interim_zeroed`` when the standard branch was also non-zero (values were
    suppressed) and ``interim_only_retained`` when the interim branch was the
    only active branch (values kept).
    """
    if rules_df is None or rules_df.empty or leap_df is None or leap_df.empty:
        return leap_df, pd.DataFrame(columns=FALLBACK_AUDIT_COLUMNS)

    adjusted_df = leap_df.copy()
    flows = adjusted_df["leap_flow"]
    audit_rows: list[dict[str, Any]] = []
    for _, rule in rules_df.iterrows():
        standard_branch = _str(rule.get("standard_branch"))
        interim_branch = _str(rule.get("interim_branch"))
        rule_id = _str(rule.get("rule_id"))
        action = _str(rule.get("action")) or WARN_AND_ZERO_INTERIM
        if not standard_branch or not interim_branch:
            continue
        standard_mask = branch_mask(flows, standard_branch)
        interim_mask = branch_mask(flows, interim_branch)
        standard_periods = _nonzero_periods(adjusted_df, standard_mask)
        interim_periods = _nonzero_periods(adjusted_df, interim_mask)
        active_interim = interim_periods[interim_periods["any_nonzero"]]
        if active_interim.empty:
            continue
        standard_lookup = {
            tuple(row[column] for column in PERIOD_COLUMNS): (row["any_nonzero"], row["total"])
            for _, row in standard_periods.iterrows()
        }
        for _, period in active_interim.iterrows():
            key = tuple(period[column] for column in PERIOD_COLUMNS)
            standard_nonzero, standard_total = standard_lookup.get(key, (False, 0.0))
            interim_total = float(period["total"])
            if standard_nonzero:
                period_mask = interim_mask.copy()
                for column, value in zip(PERIOD_COLUMNS, key):
                    period_mask &= adjusted_df[column].eq(value)
                zeroed_rows = int(period_mask.sum())
                adjusted_df.loc[period_mask, "value"] = 0.0
                status = "interim_zeroed"
                suppressed = interim_total
                retained = 0.0
            else:
                zeroed_rows = 0
                status = "interim_only_retained"
                suppressed = 0.0
                retained = interim_total
            audit_rows.append(
                {
                    "rule_id": rule_id,
                    "standard_branch": standard_branch,
                    "interim_branch": interim_branch,
                    "economy": key[0],
                    "scenario": key[1],
                    "year": key[2],
                    "action": action,
                    "status": status,
                    "standard_total": float(standard_total),
                    "interim_total_original": interim_total,
                    "interim_total_suppressed": suppressed,
                    "interim_total_retained": retained,
                    "interim_rows_zeroed": zeroed_rows,
                }
            )
    audit_df = pd.DataFrame(audit_rows, columns=FALLBACK_AUDIT_COLUMNS)
    return adjusted_df, audit_df


def load_all_demand_aggregated_components(path: Path) -> pd.DataFrame:
    """Load and flatten ``config/all_demand_aggregated_components.json``.

    The JSON groups each component branch's default and per-economy override
    settings together for human editing; this flattens it into the long-form
    table used internally by ``resolve_components_for_economy`` (columns:
    economy, aggregated_branch, component_branch, include, note), with
    ``economy == ""`` marking the wildcard default row. Rows are returned
    unfiltered by ``include`` — an economy override with ``include: false`` is
    a live override that cancels the wildcard default for that economy, so it
    must survive loading; ``include`` filtering happens once resolution is
    complete.
    """
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=ALL_DEMAND_COMPONENT_COLUMNS)
    config = json.loads(path.read_text(encoding="utf-8"))
    aggregated_branch = _str(config.get("aggregated_branch"))
    rows: list[dict[str, Any]] = []
    for component in config.get("components", []):
        component_branch = _str(component.get("component_branch"))
        if not component_branch:
            continue
        rows.append(
            {
                "economy": "",
                "aggregated_branch": aggregated_branch,
                "component_branch": component_branch,
                "include": bool(component.get("include_by_default", True)),
                "note": _str(component.get("note")),
            }
        )
        for economy, override in component.get("economy_overrides", {}).items():
            rows.append(
                {
                    "economy": _str(economy),
                    "aggregated_branch": aggregated_branch,
                    "component_branch": component_branch,
                    "include": bool(override.get("include", True)),
                    "note": _str(override.get("note")),
                }
            )
    return pd.DataFrame(rows, columns=ALL_DEMAND_COMPONENT_COLUMNS)


def resolve_components_for_economy(components_df: pd.DataFrame, economy: str) -> pd.DataFrame:
    """Resolve the effective, ``include``-filtered component rows for one economy.

    A blank ``economy`` in the config is a wildcard default applied to every
    economy. A row with an explicit economy code overrides the wildcard for
    that same (aggregated_branch, component_branch) pair only — including an
    ``include=False`` override, which cancels the wildcard for that economy
    (e.g. once it gains detailed source data) without affecting others.
    """
    if components_df is None or components_df.empty:
        return pd.DataFrame(columns=ALL_DEMAND_COMPONENT_COLUMNS)
    economy = _str(economy)
    scoped_df = components_df[components_df["economy"].map(_str) == economy]
    wildcard_df = components_df[components_df["economy"].map(_str) == ""]
    overridden_keys = set(
        zip(scoped_df["aggregated_branch"].map(_str), scoped_df["component_branch"].map(_str))
    )
    wildcard_df = wildcard_df[
        ~wildcard_df.apply(
            lambda row: (_str(row["aggregated_branch"]), _str(row["component_branch"])) in overridden_keys,
            axis=1,
        )
    ]
    resolved = pd.concat([scoped_df, wildcard_df], ignore_index=True)
    resolved = resolved[resolved["include"].map(_truthy)].reset_index(drop=True)
    return resolved[ALL_DEMAND_COMPONENT_COLUMNS]


def get_demand_sectors_without_detail(components_df: pd.DataFrame, economy: str) -> list[str]:
    """Return LEAP demand branch names still only available via the aggregate.

    These are the ``component_branch`` values configured (for this economy,
    resolving any economy-specific override over the wildcard default) as
    included in ``All demand aggregated`` — i.e. sectors with no separately
    modelled LEAP detail yet. Downstream consumers (e.g. the dashboard
    workflow) can use this to skip rendering demand-sector pages that would
    otherwise be empty of LEAP data.
    """
    resolved = resolve_components_for_economy(components_df, economy)
    if resolved.empty:
        return []
    return sorted({_str(branch) for branch in resolved["component_branch"] if _str(branch)})


def check_all_demand_aggregated_overlap(
    leap_df: pd.DataFrame,
    components_df: pd.DataFrame,
) -> pd.DataFrame:
    """Warn when the aggregate and a configured included sector are both non-zero.

    This is a review warning only; no values are changed. One row is written
    per period and non-zero configured component so each observed sector total
    is visible beside the aggregate total. Configured components are resolved
    per economy (see ``resolve_components_for_economy``) before comparing
    against that economy's rows.
    """
    if (
        leap_df is None
        or leap_df.empty
        or components_df is None
        or components_df.empty
    ):
        return pd.DataFrame(columns=ALL_DEMAND_WARNING_COLUMNS)

    warning_rows: list[dict[str, Any]] = []
    for economy, economy_leap_df in leap_df.groupby("economy", dropna=False):
        economy_components_df = resolve_components_for_economy(components_df, economy)
        if economy_components_df.empty:
            continue
        flows = economy_leap_df["leap_flow"]
        for aggregated_branch, group_df in economy_components_df.groupby("aggregated_branch", dropna=False):
            aggregated_branch = _str(aggregated_branch)
            if not aggregated_branch:
                continue
            configured = [
                _str(component)
                for component in group_df["component_branch"]
                if _str(component)
            ]
            configured_text = "; ".join(configured)
            aggregate_periods = _nonzero_periods(economy_leap_df, branch_mask(flows, aggregated_branch))
            active_aggregate = {
                tuple(row[column] for column in PERIOD_COLUMNS): row["total"]
                for _, row in aggregate_periods.iterrows()
                if row["any_nonzero"]
            }
            if not active_aggregate:
                continue
            component_periods: dict[str, pd.DataFrame] = {
                component: _nonzero_periods(economy_leap_df, branch_mask(flows, component))
                for component in configured
            }
            nonzero_components_by_period: dict[tuple[Any, ...], list[tuple[str, float]]] = {}
            for component, periods in component_periods.items():
                for _, row in periods.iterrows():
                    if not row["any_nonzero"]:
                        continue
                    key = tuple(row[column] for column in PERIOD_COLUMNS)
                    if key in active_aggregate:
                        nonzero_components_by_period.setdefault(key, []).append(
                            (component, float(row["total"]))
                        )
            for key, observed in sorted(nonzero_components_by_period.items(), key=lambda item: str(item[0])):
                nonzero_names = "; ".join(name for name, _ in observed)
                for component, component_total in observed:
                    warning_rows.append(
                        {
                            "economy": key[0],
                            "scenario": key[1],
                            "year": key[2],
                            "aggregated_branch": aggregated_branch,
                            "aggregated_total": float(active_aggregate[key]),
                            "component_branch": component,
                            "component_total": component_total,
                            "nonzero_configured_components": nonzero_names,
                            "configured_components": configured_text,
                            "reminder": ALL_DEMAND_REMINDER,
                        }
                    )
    return pd.DataFrame(warning_rows, columns=ALL_DEMAND_WARNING_COLUMNS)


def run_leap_source_branch_preflight(
    leap_df: pd.DataFrame,
    fallback_rules_path: Path | None,
    all_demand_components_path: Path | None,
    audit_output_dir: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run both configuration-owned preflight checks on parsed LEAP rows.

    Returns (adjusted working frame, fallback audit, all-demand warnings) and
    optionally writes both audit tables to ``audit_output_dir``.
    """
    fallback_rules = (
        load_source_branch_fallback_rules(fallback_rules_path)
        if fallback_rules_path is not None
        else pd.DataFrame(columns=FALLBACK_RULE_COLUMNS)
    )
    adjusted_df, fallback_audit_df = apply_source_branch_fallbacks(leap_df, fallback_rules)
    components = (
        load_all_demand_aggregated_components(all_demand_components_path)
        if all_demand_components_path is not None
        else pd.DataFrame(columns=ALL_DEMAND_COMPONENT_COLUMNS)
    )
    all_demand_warnings_df = check_all_demand_aggregated_overlap(adjusted_df, components)

    zeroed = fallback_audit_df[fallback_audit_df["status"] == "interim_zeroed"] if not fallback_audit_df.empty else fallback_audit_df
    if zeroed is not None and not zeroed.empty:
        print(
            f"WARNING: {WARN_AND_ZERO_INTERIM}: zeroed interim branch values for "
            f"{len(zeroed):,} economy/scenario/year periods where the standard "
            "branch was also non-zero. See leap_source_branch_fallback_audit.csv"
        )
        for _, row in zeroed.head(10).iterrows():
            print(
                f"  {row['rule_id']}: {row['interim_branch']} zeroed for "
                f"{row['economy']}/{row['scenario']}/{row['year']} "
                f"(standard={row['standard_total']:.3f}, interim={row['interim_total_original']:.3f})"
            )
    if all_demand_warnings_df is not None and not all_demand_warnings_df.empty:
        periods = all_demand_warnings_df[PERIOD_COLUMNS].drop_duplicates()
        print(
            "WARNING: 'All demand aggregated' overlaps a configured included demand "
            f"sector in {len(periods):,} periods. No values were changed. "
            "Confirm config/all_demand_aggregated_components.json reflects the model. "
            "See leap_all_demand_aggregated_overlap_warnings.csv"
        )
        for _, row in all_demand_warnings_df.head(10).iterrows():
            print(
                f"  {row['economy']}/{row['scenario']}/{row['year']}: "
                f"All demand aggregated={row['aggregated_total']:.3f}, "
                f"{row['component_branch']}={row['component_total']:.3f}"
            )

    if audit_output_dir is not None:
        audit_output_dir = Path(audit_output_dir)
        audit_output_dir.mkdir(parents=True, exist_ok=True)
        fallback_audit_df.to_csv(audit_output_dir / "leap_source_branch_fallback_audit.csv", index=False)
        all_demand_warnings_df.to_csv(
            audit_output_dir / "leap_all_demand_aggregated_overlap_warnings.csv", index=False
        )
    return adjusted_df, fallback_audit_df, all_demand_warnings_df

#%%
