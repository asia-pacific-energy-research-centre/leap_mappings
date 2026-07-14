#%%
"""Non-expanding rollup rule handling.

A ``NON_EXPANDING_ROLLUP`` rule declares a named derived subtotal: its
contributors are summed into one stable comparison row, but the rule must not
create Common ESTO graph edges between those contributors, and its
``parent_flow_label`` / ``child_flow_labels`` are display/tree metadata only.

Rules are marked either with ``rollup_reason = NON_EXPANDING_ROLLUP`` or with a
truthy value in the workbook's ``NON_EXPANDING_ROLLUP`` column. Both markers
are honoured because the maintained workbook currently uses the boolean column
while the documented contract is the ``rollup_reason`` value.
"""

#%%
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

#%%
NON_EXPANDING_REASON = "NON_EXPANDING_ROLLUP"
NON_EXPANDING_FLAG_COLUMN = "NON_EXPANDING_ROLLUP"

ROLLUP_SHEET_CONFIGS = {
    "leap_rollup_rules": {
        "source_system": "LEAP",
        "input_flow": "input_leap_sector_name_full_path",
        "input_product": "input_raw_leap_fuel_name",
        "rolled_flow": "rolled_leap_sector_name_full_path",
        "rolled_product": "rolled_raw_leap_fuel_name",
    },
    "esto_rollup_rules": {
        "source_system": "ESTO",
        "input_flow": "input_esto_flow",
        "input_product": "input_esto_product",
        "rolled_flow": "rolled_esto_flow",
        "rolled_product": "rolled_esto_product",
    },
    "ninth_rollup_rules": {
        "source_system": "NINTH",
        "input_flow": "input_ninth_sector",
        "input_product": "input_ninth_fuel",
        "rolled_flow": "rolled_ninth_sector",
        "rolled_product": "rolled_ninth_fuel",
    },
}

CATALOGUE_COLUMNS = [
    "rule_sheet",
    "source_system",
    "non_expanding_rollup_id",
    "rolled_flow_label",
    "rolled_product_label",
    "input_flow",
    "input_product",
    "parent_flow_label",
    "child_flow_labels",
    "note",
]

UNRESOLVED_COLUMNS = [
    "rule_sheet",
    "source_system",
    "non_expanding_rollup_id",
    "rolled_flow_label",
    "input_flow",
    "input_product",
    "unresolved_reason",
]


def _str(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _str(value).casefold() in {"true", "1", "yes", "y"}


def is_non_expanding_rule_row(row: pd.Series | dict[str, Any]) -> bool:
    """Return True when a rollup rule row is marked non-expanding."""
    getter = row.get if hasattr(row, "get") else lambda key, default=None: row[key] if key in row else default
    reason = _str(getter("rollup_reason", "")).casefold()
    if reason == NON_EXPANDING_REASON.casefold():
        return True
    return _truthy(getter(NON_EXPANDING_FLAG_COLUMN, ""))


def split_non_expanding_rules(rules_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split rollup rules into (ordinary, non_expanding) frames."""
    if rules_df is None or rules_df.empty:
        empty = pd.DataFrame(columns=rules_df.columns if rules_df is not None else [])
        return empty.copy(), empty.copy()
    mask = rules_df.apply(is_non_expanding_rule_row, axis=1)
    return rules_df[~mask].copy(), rules_df[mask].copy()


def non_expanding_rollup_id(rolled_flow_label: str, rolled_product_label: str = "") -> str:
    """Create a stable machine-safe ID for a named non-expanding subtotal."""
    text = _str(rolled_flow_label)
    if _str(rolled_product_label):
        text = f"{text} {_str(rolled_product_label)}"
    slug = re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    return f"nonexp_{slug}"


def load_non_expanding_rollup_rules(workbook_path: Path) -> dict[str, pd.DataFrame]:
    """Load enabled non-expanding rules per rollup sheet from the workbook."""
    result: dict[str, pd.DataFrame] = {}
    for sheet_name in ROLLUP_SHEET_CONFIGS:
        try:
            rules_df = pd.read_excel(workbook_path, sheet_name=sheet_name, dtype=object).fillna("")
        except Exception:
            result[sheet_name] = pd.DataFrame()
            continue
        if "include" in rules_df.columns:
            rules_df = rules_df[rules_df["include"].map(_truthy)].reset_index(drop=True)
        _, non_expanding_df = split_non_expanding_rules(rules_df)
        result[sheet_name] = non_expanding_df.reset_index(drop=True)
    return result


def non_expanding_rolled_labels(rules_df: pd.DataFrame, rolled_flow_column: str) -> dict[str, str]:
    """Map rolled flow labels of non-expanding rules to their stable IDs."""
    if rules_df is None or rules_df.empty or rolled_flow_column not in rules_df.columns:
        return {}
    labels: dict[str, str] = {}
    for _, rule in rules_df.iterrows():
        rolled_flow = _str(rule.get(rolled_flow_column))
        if rolled_flow:
            labels[rolled_flow] = non_expanding_rollup_id(rolled_flow)
    return labels


def load_non_expanding_flow_labels(workbook_path: Path) -> dict[str, str]:
    """Map every ESTO-target-shaped non-expanding rolled label to its stable ID.

    Common ESTO rows are ESTO-shaped, so the labels that can appear as Common
    ESTO components are the ESTO-sheet rolled flows plus any LEAP/NINTH-sheet
    rolled label reused verbatim as an ESTO mapping target.
    """
    rules_by_sheet = load_non_expanding_rollup_rules(workbook_path)
    labels: dict[str, str] = {}
    for sheet_name, config in ROLLUP_SHEET_CONFIGS.items():
        labels.update(
            non_expanding_rolled_labels(rules_by_sheet.get(sheet_name, pd.DataFrame()), config["rolled_flow"])
        )
    return labels


def build_non_expanding_rollup_catalogue(rules_by_sheet: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Compile one row per non-expanding rule contributor across all sheets."""
    rows: list[dict[str, Any]] = []
    for sheet_name, config in ROLLUP_SHEET_CONFIGS.items():
        rules_df = rules_by_sheet.get(sheet_name)
        if rules_df is None or rules_df.empty:
            continue
        for _, rule in rules_df.iterrows():
            rolled_flow = _str(rule.get(config["rolled_flow"]))
            if not rolled_flow:
                continue
            rows.append(
                {
                    "rule_sheet": sheet_name,
                    "source_system": config["source_system"],
                    "non_expanding_rollup_id": non_expanding_rollup_id(rolled_flow),
                    "rolled_flow_label": rolled_flow,
                    "rolled_product_label": _str(rule.get(config["rolled_product"])),
                    "input_flow": _str(rule.get(config["input_flow"])),
                    "input_product": _str(rule.get(config["input_product"])),
                    "parent_flow_label": _str(rule.get("parent_flow_label")),
                    "child_flow_labels": _str(rule.get("child_flow_labels")),
                    "note": _str(rule.get("Note")),
                }
            )
    return pd.DataFrame(rows, columns=CATALOGUE_COLUMNS)


def build_unresolved_non_expanding_qa(
    catalogue_df: pd.DataFrame,
    relationships_df: pd.DataFrame,
    known_esto_flows: set[str],
) -> pd.DataFrame:
    """Flag non-expanding rules whose expected contributor mapping cannot resolve.

    LEAP/NINTH rules need an included direct mapping for the rolled label (that
    mapping delivers the summed source value) and included mappings for each
    contributor. ESTO rules need each contributor to be a real ESTO flow or a
    known rolled flow, because the ESTO-side subtotal is summed from raw ESTO
    rows for exactly those contributor flows.
    """
    if catalogue_df is None or catalogue_df.empty:
        return pd.DataFrame(columns=UNRESOLVED_COLUMNS)

    included_source_flows_by_system: dict[str, set[str]] = {}
    direct_source_flows_by_system: dict[str, set[str]] = {}
    if relationships_df is not None and not relationships_df.empty:
        working = relationships_df.copy()
        include_mask = working["include_in_use_case"].astype(str).str.strip().str.casefold().isin({"true", "1", "yes"})
        rollup_derived_mask = working.get(
            "is_rollup_derived", pd.Series(False, index=working.index)
        ).astype(str).str.strip().str.casefold().isin({"true", "1", "yes"})
        included = working[include_mask]
        direct = working[include_mask & ~rollup_derived_mask]
        for system, group_df in included.groupby("source_system", dropna=False):
            included_source_flows_by_system[str(system)] = set(group_df["source_flow"].astype(str).str.strip())
        for system, group_df in direct.groupby("source_system", dropna=False):
            direct_source_flows_by_system[str(system)] = set(group_df["source_flow"].astype(str).str.strip())

    all_rolled_labels = set(catalogue_df["rolled_flow_label"].astype(str).str.strip())
    rows: list[dict[str, Any]] = []
    for _, entry in catalogue_df.iterrows():
        source_system = _str(entry.get("source_system"))
        rolled_flow = _str(entry.get("rolled_flow_label"))
        input_flow = _str(entry.get("input_flow"))
        reasons: list[str] = []
        if source_system in {"LEAP", "NINTH"}:
            direct_flows = direct_source_flows_by_system.get(source_system, set())
            included_flows = included_source_flows_by_system.get(source_system, set())
            if rolled_flow not in direct_flows:
                reasons.append("rolled_label_has_no_direct_included_mapping")
            # A contributor is resolvable when the branch itself or any of its
            # descendant paths has an included mapping: parent-level inputs are
            # summed from raw source rows while only their leaves are mapped.
            if input_flow and input_flow not in included_flows:
                descendant_prefix = f"{input_flow}/"
                if not any(flow.startswith(descendant_prefix) for flow in included_flows):
                    reasons.append("contributor_has_no_included_mapping")
        else:
            if input_flow and known_esto_flows and input_flow not in known_esto_flows and input_flow not in all_rolled_labels:
                reasons.append("contributor_not_a_known_esto_flow")
        for reason in reasons:
            rows.append(
                {
                    "rule_sheet": _str(entry.get("rule_sheet")),
                    "source_system": source_system,
                    "non_expanding_rollup_id": _str(entry.get("non_expanding_rollup_id")),
                    "rolled_flow_label": rolled_flow,
                    "input_flow": input_flow,
                    "input_product": _str(entry.get("input_product")),
                    "unresolved_reason": reason,
                }
            )
    return pd.DataFrame(rows, columns=UNRESOLVED_COLUMNS).drop_duplicates().reset_index(drop=True)


def build_esto_non_expanding_subtotal_rows(
    esto_wide_df: pd.DataFrame,
    esto_non_expanding_rules_df: pd.DataFrame,
    year_columns: list[str],
) -> pd.DataFrame:
    """Derive named ESTO subtotal rows for non-expanding ESTO rollup groups.

    For each enabled non-expanding ESTO rule group, sums the raw ESTO rows of
    exactly the declared contributor flows (and products where specified) into
    one derived row per economy/product/year. Products are automatic: only
    products actually present in the contributors appear in the output.
    """
    output_columns = [
        "economy",
        "esto_flow",
        "esto_product",
        "year",
        "value",
        "source_system",
        "scenario",
        "non_expanding_rollup_id",
    ]
    if (
        esto_wide_df is None
        or esto_wide_df.empty
        or esto_non_expanding_rules_df is None
        or esto_non_expanding_rules_df.empty
    ):
        return pd.DataFrame(columns=output_columns)

    flows = esto_wide_df["flows"].astype(str).str.strip()
    products = esto_wide_df["products"].astype(str).str.strip()
    derived_frames: list[pd.DataFrame] = []
    group_columns = ["rolled_esto_flow", "rolled_esto_product"]
    rules_df = esto_non_expanding_rules_df.fillna("")
    for (rolled_flow, rolled_product), group_df in rules_df.groupby(group_columns, dropna=False):
        rolled_flow = _str(rolled_flow)
        rolled_product = _str(rolled_product)
        if not rolled_flow:
            continue
        mask = pd.Series(False, index=esto_wide_df.index)
        for _, rule in group_df.iterrows():
            input_flow = _str(rule.get("input_esto_flow"))
            input_product = _str(rule.get("input_esto_product"))
            if not input_flow:
                continue
            rule_mask = flows.eq(input_flow)
            if input_product:
                rule_mask &= products.eq(input_product)
            mask |= rule_mask
        matched = esto_wide_df[mask]
        if matched.empty:
            continue
        long_df = matched[["economy", "products"] + year_columns].melt(
            id_vars=["economy", "products"],
            value_vars=year_columns,
            var_name="year",
            value_name="value",
        )
        long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce")
        long_df = long_df.dropna(subset=["value"])
        if long_df.empty:
            continue
        summed = (
            long_df.groupby(["economy", "products", "year"], as_index=False)["value"].sum()
        )
        summed = summed.rename(columns={"products": "esto_product"})
        if rolled_product:
            summed["esto_product"] = rolled_product
            summed = summed.groupby(["economy", "esto_product", "year"], as_index=False)["value"].sum()
        summed["esto_flow"] = rolled_flow
        summed["source_system"] = "ESTO"
        summed["scenario"] = "historical"
        summed["non_expanding_rollup_id"] = non_expanding_rollup_id(rolled_flow)
        summed["year"] = summed["year"].astype(int)
        derived_frames.append(summed[output_columns])
    if not derived_frames:
        return pd.DataFrame(columns=output_columns)
    return pd.concat(derived_frames, ignore_index=True)

#%%
