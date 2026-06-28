#%%
"""Build paste-ready zero rows for mapped ESTO pairs missing from source CSVs.

This module never edits an ESTO source file.  It compares the canonical mapping
workbook with an ESTO CSV and returns only the missing economy/flow/product rows
using the source CSV's exact column order.
"""

#%%
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


#%%
MAPPING_SHEETS = ("leap_combined_esto", "ninth_pairs_to_esto_pairs")
REQUIRED_ESTO_COLUMNS = ("economy", "flows", "products")
SIMPLE_ESTO_CODE_PATTERN = re.compile(r"\d+(?:\.\d+)*")


#%%
def _truthy(value: object) -> bool:
    """Return True only for explicit true-like values."""
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def extract_simple_esto_code(label: object) -> str:
    """Return a single dot-notation ESTO code, or blank for generated codes.

    Generated ranges and lists such as ``09.01.01,09.02.01`` and
    ``16.01-16.02`` are deliberately rejected because they are comparison
    categories, not physical rows that belong in an ESTO source dataset.
    """
    if pd.isna(label):
        return ""
    text = str(label).strip()
    if not text:
        return ""
    code = text.split(" ", 1)[0]
    return code if SIMPLE_ESTO_CODE_PATTERN.fullmatch(code) else ""


def _preferred_label(values: pd.Series) -> str:
    """Choose the most frequent nonblank label, with a stable tie break."""
    clean = values.dropna().astype(str).str.strip()
    clean = clean[clean.ne("")]
    if clean.empty:
        return ""
    counts = clean.value_counts()
    highest_count = int(counts.max())
    return sorted(counts[counts.eq(highest_count)].index)[0]


def load_expected_mapped_esto_pairs(
    mapping_workbook_path: Path,
    mapping_sheets: tuple[str, ...] = MAPPING_SHEETS,
) -> pd.DataFrame:
    """Return canonical, simple ESTO pairs required by active mapping rows."""
    frames: list[pd.DataFrame] = []
    for sheet_name in mapping_sheets:
        sheet = pd.read_excel(mapping_workbook_path, sheet_name=sheet_name, dtype=object)
        for column in ["esto_flow", "esto_product"]:
            if column not in sheet.columns:
                raise ValueError(f"Sheet {sheet_name!r} is missing required column {column!r}.")

        remove_mask = sheet.get("remove_row", pd.Series(False, index=sheet.index)).map(_truthy)
        duplicate_mask = sheet.get("duplicate_to_remove", pd.Series(False, index=sheet.index)).map(_truthy)
        active = sheet[~(remove_mask | duplicate_mask)].copy()
        active["flow_code"] = active["esto_flow"].map(extract_simple_esto_code)
        active["product_code"] = active["esto_product"].map(extract_simple_esto_code)
        active = active[active["flow_code"].ne("") & active["product_code"].ne("")].copy()
        active["mapping_sheet"] = sheet_name
        frames.append(
            active[[
                "flow_code",
                "product_code",
                "esto_flow",
                "esto_product",
                "esto_pair_is_subtotal",
                "mapping_sheet",
            ]]
        )

    if not frames:
        return pd.DataFrame(columns=[
            "flow_code",
            "product_code",
            "esto_flow",
            "esto_product",
            "mapping_subtotal_flag",
            "mapping_sheets",
        ])

    combined = pd.concat(frames, ignore_index=True)
    grouped = (
        combined.groupby(["flow_code", "product_code"], as_index=False)
        .agg(
            esto_flow=("esto_flow", _preferred_label),
            esto_product=("esto_product", _preferred_label),
            mapping_subtotal_flag=("esto_pair_is_subtotal", lambda values: any(_truthy(value) for value in values)),
            mapping_sheets=("mapping_sheet", lambda values: "; ".join(sorted(set(map(str, values))))),
        )
        .sort_values(["flow_code", "product_code"])
        .reset_index(drop=True)
    )
    return grouped


def _label_lookup_by_code(df: pd.DataFrame, label_column: str, code_column: str) -> dict[str, str]:
    """Build a stable code-to-label lookup from an ESTO source dataset."""
    return (
        df[df[code_column].ne("")]
        .groupby(code_column)[label_column]
        .agg(_preferred_label)
        .to_dict()
    )


def _parent_codes(codes: set[str]) -> set[str]:
    """Return codes that have at least one dot-notation descendant."""
    return {
        code
        for code in codes
        if any(other.startswith(code + ".") for other in codes if other != code)
    }


def build_missing_mapped_esto_rows(
    esto_csv_path: Path,
    mapping_workbook_path: Path,
    expected_pairs: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return paste-ready zero rows and a compact missing-pair audit.

    A row is required for every economy and every simple mapped ESTO pair that
    is not already present for that economy.  Existing source labels are reused
    by code where possible, so harmless name punctuation differences do not
    create duplicate keys.
    """
    esto = pd.read_csv(esto_csv_path, low_memory=False)
    source_columns = list(esto.columns)
    missing_columns = [column for column in REQUIRED_ESTO_COLUMNS if column not in esto.columns]
    if missing_columns:
        raise ValueError(f"ESTO file {esto_csv_path} is missing columns: {missing_columns}")

    if expected_pairs is None:
        expected = load_expected_mapped_esto_pairs(mapping_workbook_path)
    else:
        expected = expected_pairs.copy()
    esto["_flow_code"] = esto["flows"].map(extract_simple_esto_code)
    esto["_product_code"] = esto["products"].map(extract_simple_esto_code)

    flow_labels = _label_lookup_by_code(esto, "flows", "_flow_code")
    product_labels = _label_lookup_by_code(esto, "products", "_product_code")
    expected["output_flow"] = expected.apply(
        lambda row: flow_labels.get(str(row["flow_code"]), str(row["esto_flow"])),
        axis=1,
    )
    expected["output_product"] = expected.apply(
        lambda row: product_labels.get(str(row["product_code"]), str(row["esto_product"])),
        axis=1,
    )

    economies = sorted(esto["economy"].dropna().astype(str).str.strip().loc[lambda values: values.ne("")].unique())
    expected = expected.reset_index(drop=True).reset_index(names="_expected_index")
    required = pd.MultiIndex.from_product(
        [economies, expected["_expected_index"].tolist()],
        names=["economy", "_expected_index"],
    ).to_frame(index=False)
    required = required.merge(expected, on="_expected_index", how="left")

    existing_keys = esto[["economy", "_flow_code", "_product_code"]].drop_duplicates().rename(
        columns={"_flow_code": "flow_code", "_product_code": "product_code"}
    )
    missing = required.merge(
        existing_keys,
        on=["economy", "flow_code", "product_code"],
        how="left",
        indicator=True,
    )
    missing = missing[missing["_merge"].eq("left_only")].copy()

    all_flow_codes = set(esto["_flow_code"].loc[lambda values: values.ne("")]) | set(expected["flow_code"])
    all_product_codes = set(esto["_product_code"].loc[lambda values: values.ne("")]) | set(expected["product_code"])
    parent_flow_codes = _parent_codes(all_flow_codes)
    parent_product_codes = _parent_codes(all_product_codes)
    missing["inferred_is_subtotal"] = missing.apply(
        lambda row: bool(row["mapping_subtotal_flag"])
        or str(row["flow_code"]) in parent_flow_codes
        or str(row["product_code"]) in parent_product_codes,
        axis=1,
    )

    paste_ready = pd.DataFrame(index=missing.index, columns=source_columns)
    paste_ready["economy"] = missing["economy"].values
    paste_ready["flows"] = missing["output_flow"].values
    paste_ready["products"] = missing["output_product"].values
    if "is_subtotal" in paste_ready.columns:
        paste_ready["is_subtotal"] = missing["inferred_is_subtotal"].astype(bool).values
    for column in paste_ready.columns:
        if str(column).isdigit():
            paste_ready[column] = 0.0
    paste_ready = paste_ready.sort_values(["economy", "flows", "products"]).reset_index(drop=True)

    audit = missing[[
        "flow_code",
        "product_code",
        "output_flow",
        "output_product",
        "inferred_is_subtotal",
        "mapping_sheets",
    ]].drop_duplicates().rename(
        columns={
            "output_flow": "flows",
            "output_product": "products",
            "inferred_is_subtotal": "is_subtotal",
        }
    ).sort_values(["flow_code", "product_code"]).reset_index(drop=True)
    audit["missing_economy_count"] = audit.apply(
        lambda row: int(
            missing[
                missing["flow_code"].eq(row["flow_code"])
                & missing["product_code"].eq(row["product_code"])
            ]["economy"].nunique()
        ),
        axis=1,
    )
    return paste_ready, audit


def write_missing_mapped_esto_rows(
    esto_csv_paths: list[Path],
    mapping_workbook_path: Path,
    output_dir: Path,
) -> pd.DataFrame:
    """Write one paste-ready CSV per ESTO source and return a run summary."""
    output_dir.mkdir(parents=True, exist_ok=True)
    expected_pairs = load_expected_mapped_esto_pairs(mapping_workbook_path)
    summary_rows: list[dict[str, object]] = []
    for esto_csv_path in esto_csv_paths:
        if not esto_csv_path.exists():
            summary_rows.append({
                "source_file": esto_csv_path.name,
                "status": "missing_source_file",
                "missing_pair_count": 0,
                "paste_ready_row_count": 0,
                "output_file": "",
            })
            continue

        paste_ready, audit = build_missing_mapped_esto_rows(
            esto_csv_path=esto_csv_path,
            mapping_workbook_path=mapping_workbook_path,
            expected_pairs=expected_pairs,
        )
        output_path = output_dir / f"{esto_csv_path.stem}_missing_mapped_rows.csv"
        paste_ready.to_csv(output_path, index=False)
        summary_rows.append({
            "source_file": esto_csv_path.name,
            "status": "rows_required" if not paste_ready.empty else "complete",
            "missing_pair_count": len(audit),
            "paste_ready_row_count": len(paste_ready),
            "output_file": str(output_path),
        })
        print(
            f"  {esto_csv_path.name}: {len(audit):,} missing mapped pairs, "
            f"{len(paste_ready):,} paste-ready rows -> {output_path}"
        )

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_dir / "missing_mapped_esto_rows_summary.csv", index=False)
    return summary


#%%
