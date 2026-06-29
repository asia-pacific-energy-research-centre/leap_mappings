#%%
"""Append a reviewed set of ESTO rows to matching data files across repositories.

The workflow is deliberately dry-run by default. It appends only missing
``economy/flows/products`` keys, preserves each target CSV's exact schema and
column order, and never replaces an existing row. Use the dedicated update
outputs from Stage 0 when an existing row's values must be changed.
"""

#%%
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


#%%
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPOSITORY_ROOTS = [
    REPO_ROOT,
    REPO_ROOT.parent / "leap_initialisation",
    REPO_ROOT.parent / "leap_dashboard",
    REPO_ROOT.parent / "leap_utilities",
]
ESTO_FILE_PATTERN = "00APEC_*_low_with_subtotals.csv"
KEY_COLUMNS = ["economy", "flows", "products"]


#%%
def _normalise_text(value: object) -> str:
    """Normalize comparison text without changing written output labels."""
    if pd.isna(value):
        return ""
    return " ".join(str(value).split())


def _normalise_economy(value: object) -> str:
    """Treat compact and underscored economy codes as the same key."""
    return _normalise_text(value).replace("_", "")


def _normalised_keys(df: pd.DataFrame) -> pd.Series:
    """Return normalized uniqueness keys for an ESTO-shaped table."""
    return pd.Series(
        list(zip(
            df["economy"].map(_normalise_economy),
            df["flows"].map(_normalise_text),
            df["products"].map(_normalise_text),
        )),
        index=df.index,
    )


def read_chosen_esto_rows(
    chosen_rows_path: Path,
    sheet_name: str | None = None,
) -> pd.DataFrame:
    """Read chosen rows from CSV or Excel and validate their keys."""
    if not chosen_rows_path.exists():
        raise FileNotFoundError(f"Chosen rows file not found: {chosen_rows_path}")
    if chosen_rows_path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        workbook = pd.ExcelFile(chosen_rows_path)
        selected_sheet = sheet_name or (
            "All economies rows" if "All economies rows" in workbook.sheet_names else workbook.sheet_names[0]
        )
        rows = pd.read_excel(chosen_rows_path, sheet_name=selected_sheet, dtype=object)
    else:
        rows = pd.read_csv(chosen_rows_path, dtype=object, low_memory=False)
    rows.columns = [str(column) for column in rows.columns]
    missing = [column for column in KEY_COLUMNS if column not in rows.columns]
    if missing:
        raise ValueError(f"Chosen rows file is missing columns: {missing}")
    rows = rows[rows[KEY_COLUMNS].notna().all(axis=1)].copy()
    rows["_key"] = _normalised_keys(rows)
    duplicate_keys = rows[rows.duplicated("_key", keep=False)]
    if not duplicate_keys.empty:
        conflicting = duplicate_keys.groupby("_key").filter(
            lambda group: len(group.drop(columns="_key").drop_duplicates()) > 1
        )
        if not conflicting.empty:
            raise ValueError("Chosen rows contain conflicting duplicate economy/flow/product keys.")
        rows = rows.drop_duplicates("_key", keep="first")
    return rows.drop(columns="_key").reset_index(drop=True)


def find_target_esto_files(
    repository_roots: list[Path],
    file_pattern: str = ESTO_FILE_PATTERN,
) -> list[Path]:
    """Find matching ESTO source files only in each repository's data folder."""
    targets: list[Path] = []
    for repository_root in repository_roots:
        data_dir = repository_root / "data"
        if data_dir.exists():
            targets.extend(path.resolve() for path in data_dir.glob(file_pattern) if path.is_file())
    return sorted(set(targets))


def _rows_for_target_schema(chosen_rows: pd.DataFrame, target_columns: list[str]) -> pd.DataFrame:
    """Adapt chosen rows to one target's exact columns and order."""
    output = pd.DataFrame(index=chosen_rows.index, columns=target_columns)
    for column in target_columns:
        if column in chosen_rows.columns:
            output[column] = chosen_rows[column].values
        elif column.isdigit():
            output[column] = 0.0
        elif column == "is_subtotal":
            output[column] = "FALSE"
        else:
            output[column] = pd.NA
    return output


def propagate_chosen_esto_rows(
    chosen_rows_path: Path,
    repository_roots: list[Path],
    write_to_source_files: bool = False,
    sheet_name: str | None = None,
    selected_flows: set[str] | None = None,
    selected_products: set[str] | None = None,
    summary_output_path: Path | None = None,
) -> pd.DataFrame:
    """Preview or append a reviewed row set to every matching ESTO data file."""
    chosen = read_chosen_esto_rows(chosen_rows_path, sheet_name=sheet_name)
    if selected_flows is not None:
        chosen = chosen[chosen["flows"].map(_normalise_text).isin(selected_flows)].copy()
    if selected_products is not None:
        chosen = chosen[chosen["products"].map(_normalise_text).isin(selected_products)].copy()

    summary_rows: list[dict[str, object]] = []
    for target_path in find_target_esto_files(repository_roots):
        target = pd.read_csv(target_path, dtype=object, low_memory=False)
        missing_columns = [column for column in KEY_COLUMNS if column not in target.columns]
        if missing_columns:
            summary_rows.append({
                "target_file": str(target_path),
                "status": "invalid_target_schema",
                "chosen_row_count": len(chosen),
                "append_row_count": 0,
                "existing_row_count": 0,
                "written": False,
                "detail": f"Missing columns: {missing_columns}",
            })
            continue

        existing_keys = set(_normalised_keys(target))
        chosen_keys = _normalised_keys(chosen)
        missing_mask = ~chosen_keys.isin(existing_keys)
        rows_to_append = _rows_for_target_schema(chosen.loc[missing_mask], list(target.columns))
        if write_to_source_files and not rows_to_append.empty:
            combined = pd.concat([target, rows_to_append], ignore_index=True)
            temporary_path = target_path.with_suffix(target_path.suffix + ".tmp")
            combined.to_csv(temporary_path, index=False)
            os.replace(temporary_path, target_path)
        summary_rows.append({
            "target_file": str(target_path),
            "status": "rows_appended" if write_to_source_files and not rows_to_append.empty else (
                "complete" if rows_to_append.empty else "dry_run"
            ),
            "chosen_row_count": len(chosen),
            "append_row_count": len(rows_to_append),
            "existing_row_count": int((~missing_mask).sum()),
            "written": bool(write_to_source_files and not rows_to_append.empty),
            "detail": "Existing keys are never replaced.",
        })

    summary = pd.DataFrame(summary_rows)
    if summary_output_path is not None:
        summary_output_path.parent.mkdir(parents=True, exist_ok=True)
        summary.to_csv(summary_output_path, index=False)
    return summary


#%%
# Frequently changed settings. Review the dry-run summary before enabling writes.
CHOSEN_ROWS_PATH = (
    REPO_ROOT
    / "results"
    / "maintenance"
    / "missing_mapped_esto_rows"
    / "00APEC_2025_low_with_subtotals_missing_mapped_rows.csv"
)
CHOSEN_ROWS_SHEET = None
SELECTED_FLOWS = None
SELECTED_PRODUCTS = None
WRITE_TO_SOURCE_FILES = False
RUN_PROPAGATION = False


#%%
if RUN_PROPAGATION:
    result = propagate_chosen_esto_rows(
        chosen_rows_path=CHOSEN_ROWS_PATH,
        repository_roots=DEFAULT_REPOSITORY_ROOTS,
        write_to_source_files=WRITE_TO_SOURCE_FILES,
        sheet_name=CHOSEN_ROWS_SHEET,
        selected_flows=SELECTED_FLOWS,
        selected_products=SELECTED_PRODUCTS,
        summary_output_path=(
            REPO_ROOT
            / "results"
            / "maintenance"
            / "esto_row_propagation_summary.csv"
        ),
    )
    print(result.to_string(index=False))

#%%
