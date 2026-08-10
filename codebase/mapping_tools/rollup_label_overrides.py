#%%
"""Load and validate display-only overrides for explicit rollup groups."""

#%%
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd


#%%
ROLLUP_LABEL_OVERRIDE_COLUMNS = [
    "rollup_group_id",
    "auto_rollup_code",
    "auto_rollup_name",
    "auto_rollup_label",
    "preferred_rollup_code",
    "preferred_rollup_name",
    "preferred_rollup_label",
    "Note",
]

ROLLUP_RULE_SHEETS = {
    "leap_rollup_rules": {
        "input_flow": "input_leap_sector_name_full_path",
        "input_product": "input_raw_leap_fuel_name",
        "rolled_flow": "rolled_leap_sector_name_full_path",
        "rolled_product": "rolled_raw_leap_fuel_name",
    },
    "esto_rollup_rules": {
        "input_flow": "input_esto_flow",
        "input_product": "input_esto_product",
        "rolled_flow": "rolled_esto_flow",
        "rolled_product": "rolled_esto_product",
    },
    "ninth_rollup_rules": {
        "input_flow": "input_ninth_sector",
        "input_product": "input_ninth_fuel",
        "rolled_flow": "rolled_ninth_sector",
        "rolled_product": "rolled_ninth_fuel",
    },
}

NORMALISED_OVERRIDE_COLUMNS = [
    *ROLLUP_LABEL_OVERRIDE_COLUMNS,
    "rule_sheet",
    "rollup_axis",
    "structural_rollup_label",
]


#%%
def _text(value: Any) -> str:
    """Return a whitespace-normalised string."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).casefold() in {"true", "1", "yes", "y"}


def _split_code_name(label: Any) -> tuple[str, str]:
    """Split a generated label into its leading code and readable name."""
    text = _text(label)
    if not text:
        return "", ""
    code_token = r"[0-9][0-9A-Za-z_.-]*(?:\.[0-9A-Za-z_.-]+)*"
    match = re.match(rf"^({code_token}(?:,{code_token})*)\s+(.+)$", text)
    if not match:
        return "", text
    return match.group(1).strip(), match.group(2).strip()


def _make_label(code: Any, name: Any) -> str:
    code_text = _text(code)
    name_text = _text(name)
    return " ".join(value for value in [code_text, name_text] if value)


def _active_rules(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    if "include" not in frame.columns:
        return frame.copy()
    return frame[frame["include"].map(_truthy)].copy()


def load_rollup_rule_sheets(workbook_path: Path) -> dict[str, pd.DataFrame]:
    """Read the active rule rows needed to validate label overrides."""
    rules: dict[str, pd.DataFrame] = {}
    for sheet_name in ROLLUP_RULE_SHEETS:
        try:
            frame = pd.read_excel(workbook_path, sheet_name=sheet_name, dtype=object).fillna("")
        except Exception:
            frame = pd.DataFrame()
        rules[sheet_name] = _active_rules(frame)
    return rules


def build_rollup_group_catalogue(
    rules_by_sheet: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Return one display-axis record per active ``rollup_group_id``.

    The current override sheet contains one preferred code/name/label set, so a
    group that rolls both axes at once is intentionally rejected as ambiguous.
    """
    records: list[dict[str, str]] = []
    for sheet_name, config in ROLLUP_RULE_SHEETS.items():
        rules_df = _active_rules(rules_by_sheet.get(sheet_name, pd.DataFrame()))
        if rules_df.empty or "rollup_group_id" not in rules_df.columns:
            continue
        grouping_columns = [
            "rollup_group_id",
            config["rolled_flow"],
            config["rolled_product"],
        ]
        for group_values, group_df in rules_df.groupby(
            grouping_columns,
            dropna=False,
        ):
            group_id, grouped_rolled_flow, grouped_rolled_product = group_values
            clean_group_id = _text(group_id)
            if not clean_group_id:
                continue

            input_flows = {_text(value) for value in group_df.get(config["input_flow"], pd.Series(dtype=object)) if _text(value)}
            input_products = {
                _text(value)
                for value in group_df.get(config["input_product"], pd.Series(dtype=object))
                if _text(value)
            }
            rolled_flow = _text(grouped_rolled_flow)
            rolled_product = _text(grouped_rolled_product)
            flow_changed = bool(rolled_flow) and (
                len(input_flows) > 1 or any(value != rolled_flow for value in input_flows)
            )
            product_changed = bool(rolled_product) and (
                len(input_products) > 1 or any(value != rolled_product for value in input_products)
            )
            if flow_changed and product_changed:
                rollup_axis = "both"
                structural_label = ""
            elif product_changed:
                rollup_axis = "product"
                structural_label = rolled_product
            else:
                # Flow is the default for groups with wildcard or unchanged
                # products, which covers the current explicit power rollups.
                rollup_axis = "flow"
                structural_label = rolled_flow
            auto_code, auto_name = _split_code_name(structural_label)
            records.append(
                {
                    "rollup_group_id": clean_group_id,
                    "rule_sheet": sheet_name,
                    "rollup_axis": rollup_axis,
                    "structural_rollup_label": structural_label,
                    "auto_rollup_code": auto_code,
                    "auto_rollup_name": auto_name,
                    "auto_rollup_label": structural_label,
                }
            )

    if not records:
        return pd.DataFrame(
            columns=[
                "rollup_group_id",
                "rule_sheet",
                "rollup_axis",
                "structural_rollup_label",
                "auto_rollup_code",
                "auto_rollup_name",
                "auto_rollup_label",
            ]
        )
    catalogue = pd.DataFrame(records)
    return catalogue.drop_duplicates().sort_values(
        ["rule_sheet", "rollup_group_id", "structural_rollup_label"]
    ).reset_index(drop=True)


def normalise_rollup_label_overrides(
    overrides_df: pd.DataFrame,
    rollup_catalogue_df: pd.DataFrame,
) -> pd.DataFrame:
    """Validate workbook overrides and attach their structural rollup metadata."""
    if overrides_df is None or overrides_df.empty:
        return pd.DataFrame(columns=NORMALISED_OVERRIDE_COLUMNS)
    missing_columns = [
        column for column in ROLLUP_LABEL_OVERRIDE_COLUMNS if column not in overrides_df.columns
    ]
    if missing_columns:
        raise ValueError(
            "rollup_label_overrides is missing required columns: "
            + ", ".join(missing_columns)
        )

    overrides = overrides_df[ROLLUP_LABEL_OVERRIDE_COLUMNS].fillna("").copy()
    overrides = overrides[
        overrides.apply(lambda row: any(_text(value) for value in row), axis=1)
    ].copy()
    if overrides.empty:
        return pd.DataFrame(columns=NORMALISED_OVERRIDE_COLUMNS)
    for column in ROLLUP_LABEL_OVERRIDE_COLUMNS:
        overrides[column] = overrides[column].map(_text)

    blank_ids = overrides["rollup_group_id"].eq("")
    if blank_ids.any():
        raise ValueError("rollup_label_overrides contains a non-empty row with blank rollup_group_id.")
    duplicate_ids = sorted(
        overrides.loc[
            overrides["rollup_group_id"].duplicated(keep=False), "rollup_group_id"
        ].unique()
    )
    if duplicate_ids:
        raise ValueError(
            "rollup_label_overrides contains duplicate rollup_group_id values: "
            + ", ".join(duplicate_ids)
        )

    catalogue = rollup_catalogue_df.copy()
    if catalogue.empty:
        raise ValueError("rollup_label_overrides has rows but no active rollup groups were found.")
    unmatched = sorted(set(overrides["rollup_group_id"]) - set(catalogue["rollup_group_id"]))
    if unmatched:
        raise ValueError(
            "rollup_label_overrides references unknown or inactive rollup_group_id values: "
            + ", ".join(unmatched)
        )

    match_counts = catalogue.groupby("rollup_group_id", dropna=False).size()
    ambiguous_ids = sorted(
        group_id
        for group_id in overrides["rollup_group_id"]
        if int(match_counts.get(group_id, 0)) != 1
    )
    if ambiguous_ids:
        raise ValueError(
            "Each overridden rollup_group_id must identify exactly one rolled category. "
            "Assign a category-specific rollup_group_id before overriding: "
            + ", ".join(ambiguous_ids)
        )
    catalogue = catalogue[
        catalogue["rollup_group_id"].isin(overrides["rollup_group_id"])
    ].copy()
    merged = overrides.merge(
        catalogue,
        on="rollup_group_id",
        how="left",
        suffixes=("_workbook", ""),
        validate="one_to_one",
    )
    ambiguous = merged[merged["rollup_axis"].eq("both")]
    if not ambiguous.empty:
        raise ValueError(
            "The current rollup_label_overrides schema cannot label groups that roll both "
            "axes: "
            + ", ".join(sorted(ambiguous["rollup_group_id"]))
        )

    for field in ["auto_rollup_code", "auto_rollup_name", "auto_rollup_label"]:
        workbook_field = f"{field}_workbook"
        mismatch = (
            merged[workbook_field].ne("")
            & merged[workbook_field].ne(merged[field])
        )
        if mismatch.any():
            examples = merged.loc[
                mismatch, ["rollup_group_id", workbook_field, field]
            ].to_dict("records")
            raise ValueError(
                f"Stale {field} guard values in rollup_label_overrides: {examples}"
            )
        merged[field] = merged[workbook_field].where(
            merged[workbook_field].ne(""), merged[field]
        )

    no_preference = merged[
        ["preferred_rollup_code", "preferred_rollup_name", "preferred_rollup_label"]
    ].eq("").all(axis=1)
    if no_preference.any():
        raise ValueError(
            "Every rollup_label_overrides row must supply at least one preferred value: "
            + ", ".join(sorted(merged.loc[no_preference, "rollup_group_id"]))
        )

    generated_preferred_label = merged.apply(
        lambda row: _make_label(
            row["preferred_rollup_code"] or row["auto_rollup_code"],
            row["preferred_rollup_name"] or row["auto_rollup_name"],
        ),
        axis=1,
    )
    # The visible label may intentionally omit the structural code while the
    # separate code field retains it for traceability.
    merged["preferred_rollup_label"] = merged["preferred_rollup_label"].where(
        merged["preferred_rollup_label"].ne(""), generated_preferred_label
    )
    merged["preferred_rollup_code"] = merged["preferred_rollup_code"].where(
        merged["preferred_rollup_code"].ne(""), merged["auto_rollup_code"]
    )
    merged["preferred_rollup_name"] = merged["preferred_rollup_name"].where(
        merged["preferred_rollup_name"].ne(""), merged["auto_rollup_name"]
    )
    return merged[NORMALISED_OVERRIDE_COLUMNS].sort_values(
        ["rule_sheet", "rollup_group_id"]
    ).reset_index(drop=True)


def load_rollup_label_overrides(workbook_path: Path) -> pd.DataFrame:
    """Load, validate and normalise the workbook's active display overrides."""
    try:
        overrides_df = pd.read_excel(
            workbook_path,
            sheet_name="rollup_label_overrides",
            dtype=object,
        ).fillna("")
    except ValueError:
        return pd.DataFrame(columns=NORMALISED_OVERRIDE_COLUMNS)
    rules_by_sheet = load_rollup_rule_sheets(workbook_path)
    catalogue_df = build_rollup_group_catalogue(rules_by_sheet)
    return normalise_rollup_label_overrides(overrides_df, catalogue_df)


def override_lookup(
    overrides_df: pd.DataFrame,
    *,
    rule_sheet: str | None = None,
    rollup_axis: str | None = None,
) -> dict[str, dict[str, str]]:
    """Return normalised override rows keyed by ``rollup_group_id``."""
    if overrides_df is None or overrides_df.empty:
        return {}
    selected = overrides_df.copy()
    if rule_sheet is not None:
        selected = selected[selected["rule_sheet"].eq(rule_sheet)]
    if rollup_axis is not None:
        selected = selected[selected["rollup_axis"].eq(rollup_axis)]
    return {
        _text(row["rollup_group_id"]): {
            column: _text(row.get(column, ""))
            for column in NORMALISED_OVERRIDE_COLUMNS
        }
        for _, row in selected.iterrows()
        if _text(row.get("rollup_group_id", ""))
    }


#%%
