"""Structural catalogue and coverage checks for ESTO Extended.

ESTO Extended declares comparison categories. It is not an independent
historical fact source: observed history always comes from ordinary ESTO.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


CATALOGUE_COLUMNS = [
    "flows", "products", "is_subtotal", "structural_origin",
    "structural_rule_ids", "structural_parent_flow",
    "structural_parent_product", "rollup_modes", "rollup_group_ids",
]
PAIR_COLUMNS = ["flows", "products"]
NUMERIC_FACT_COLUMNS = {"economy", "scenario", "year", "value"}


def _text(value: object) -> str:
    return "" if pd.isna(value) else str(value).strip()


def _truthy(value: object) -> bool:
    return _text(value).casefold() in {"true", "1", "yes", "y"}


def _active(frame: pd.DataFrame) -> pd.DataFrame:
    duplicate = frame.get("duplicate_to_remove", pd.Series(False, index=frame.index))
    return frame.loc[~duplicate.map(_truthy)].copy()


def _extended_scope(value: object) -> bool:
    return _text(value).upper() in {"BOTH", "ESTO_EXTENDED"}


def _code(label: object) -> str:
    return _text(label).split(" ", 1)[0]


def _parent_code(label: object) -> str:
    code = _code(label)
    return code.rsplit(".", 1)[0] if "." in code else ""


def _required_rows(mapping_workbook_path: Path) -> pd.DataFrame:
    """Return active Extended mapping and rollup pairs with their metadata."""
    rows: list[dict[str, str]] = []
    for sheet_name in ("leap_combined_esto", "ninth_pairs_to_esto_pairs"):
        frame = _active(pd.read_excel(mapping_workbook_path, sheet_name=sheet_name, dtype=object))
        frame = frame.loc[frame["esto_dataset_scope"].map(_extended_scope)]
        for row in frame.itertuples(index=False):
            flow, product = _text(getattr(row, "esto_flow")), _text(getattr(row, "esto_product"))
            if flow and product:
                rows.append({
                    "flows": flow, "products": product,
                    "structural_origin": "active_mapping",
                    "structural_rule_id": sheet_name,
                    "rollup_mode": "", "rollup_group_id": "",
                })
    rules = pd.read_excel(mapping_workbook_path, sheet_name="esto_rollup_rules", dtype=object)
    rules = rules.loc[rules["include"].map(_truthy) & rules["esto_dataset_scope"].map(_extended_scope)]
    for row_number, row in rules.iterrows():
        for flow_column, product_column in (
            ("input_esto_flow", "input_esto_product"),
            ("rolled_esto_flow", "rolled_esto_product"),
        ):
            flow, product = _text(row.get(flow_column)), _text(row.get(product_column))
            if flow and product:
                rows.append({
                    "flows": flow, "products": product,
                    "structural_origin": "active_rollup",
                    "structural_rule_id": f"esto_rollup_rules:{row_number + 2}",
                    "rollup_mode": _text(row.get("ROLLUP_MODE")),
                    "rollup_group_id": _text(row.get("rollup_group_id")),
                })
    return pd.DataFrame(rows)


def required_extended_pairs(mapping_workbook_path: Path) -> pd.DataFrame:
    """Return one deterministic structural requirement per active pair."""
    rows = _required_rows(Path(mapping_workbook_path))
    if rows.empty:
        return pd.DataFrame(columns=CATALOGUE_COLUMNS)
    grouped = rows.groupby(PAIR_COLUMNS, as_index=False, dropna=False).agg(
        structural_origin=("structural_origin", lambda values: "|".join(sorted(set(values)))),
        structural_rule_ids=("structural_rule_id", lambda values: "|".join(sorted(value for value in set(values) if value))),
        rollup_modes=("rollup_mode", lambda values: "|".join(sorted(value for value in set(values) if value))),
        rollup_group_ids=("rollup_group_id", lambda values: "|".join(sorted(value for value in set(values) if value))),
    )
    flow_codes = {_code(flow): flow for flow in grouped["flows"]}
    product_codes = {_code(product): product for product in grouped["products"]}
    grouped["structural_parent_flow"] = grouped["flows"].map(lambda flow: flow_codes.get(_parent_code(flow), ""))
    grouped["structural_parent_product"] = grouped["products"].map(lambda product: product_codes.get(_parent_code(product), ""))
    flow_parent_codes = {code for code in flow_codes if any(other.startswith(code + ".") for other in flow_codes)}
    product_parent_codes = {code for code in product_codes if any(other.startswith(code + ".") for other in product_codes)}
    grouped["is_subtotal"] = grouped.apply(
        lambda row: _code(row["flows"]) in flow_parent_codes or _code(row["products"]) in product_parent_codes,
        axis=1,
    )
    return grouped[CATALOGUE_COLUMNS].sort_values(PAIR_COLUMNS).reset_index(drop=True)


def catalogue_diagnostics(catalogue: pd.DataFrame, required_pairs: pd.DataFrame) -> pd.DataFrame:
    """Return deterministic diagnostics without generating or changing values."""
    diagnostics: list[dict[str, str]] = []
    numeric_columns = sorted(column for column in catalogue.columns if str(column).isdigit() or str(column) in NUMERIC_FACT_COLUMNS)
    diagnostics.extend({"status": "invalid_numeric_column", "flows": "", "products": "", "detail": column} for column in numeric_columns)
    missing_columns = [column for column in CATALOGUE_COLUMNS if column not in catalogue.columns]
    diagnostics.extend({"status": "missing_column", "flows": "", "products": "", "detail": column} for column in missing_columns)
    if missing_columns:
        return pd.DataFrame(diagnostics, columns=["status", "flows", "products", "detail"])
    catalogue_pairs, required = catalogue[PAIR_COLUMNS].drop_duplicates(), required_pairs[PAIR_COLUMNS].drop_duplicates()
    missing = required.merge(catalogue_pairs, on=PAIR_COLUMNS, how="left", indicator=True)
    stale = catalogue_pairs.merge(required, on=PAIR_COLUMNS, how="left", indicator=True)
    diagnostics.extend(
        {"status": "missing_required_pair", "flows": row.flows, "products": row.products, "detail": "active Extended mapping or rollup"}
        for row in missing.loc[missing["_merge"].eq("left_only")].sort_values(PAIR_COLUMNS).itertuples(index=False)
    )
    diagnostics.extend(
        {"status": "stale_catalogue_pair", "flows": row.flows, "products": row.products, "detail": "not required by an active Extended mapping or rollup"}
        for row in stale.loc[stale["_merge"].eq("left_only")].sort_values(PAIR_COLUMNS).itertuples(index=False)
    )
    duplicate_mask = catalogue.duplicated(PAIR_COLUMNS, keep=False)
    diagnostics.extend(
        {"status": "duplicate_catalogue_pair", "flows": row.flows, "products": row.products, "detail": "catalogue pair must be unique"}
        for row in catalogue.loc[duplicate_mask, PAIR_COLUMNS].drop_duplicates().sort_values(PAIR_COLUMNS).itertuples(index=False)
    )
    return pd.DataFrame(diagnostics, columns=["status", "flows", "products", "detail"])


def assert_valid_catalogue(catalogue: pd.DataFrame, required_pairs: pd.DataFrame) -> pd.DataFrame:
    """Raise with stable diagnostics when structural coverage is incomplete."""
    diagnostics = catalogue_diagnostics(catalogue, required_pairs)
    if not diagnostics.empty:
        raise ValueError(f"ESTO Extended structural catalogue is invalid: {diagnostics.head(10).to_dict('records')}")
    return diagnostics


def build_structural_catalogue(mapping_workbook_path: Path, output_path: Path) -> pd.DataFrame:
    """Build the production structural catalogue; this function never handles facts."""
    catalogue = required_extended_pairs(Path(mapping_workbook_path))
    assert_valid_catalogue(catalogue, catalogue)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    catalogue.to_csv(output_path, index=False)
    return catalogue
