"""Flag mapping rows in the three base mapping sheets whose key pairs have no data.

Checks ``leap_combined_esto``, ``leap_combined_ninth``, and
``ninth_pairs_to_esto_pairs`` in ``config/outlook_mappings_master.xlsx`` against
the raw ESTO and 9th Outlook source data. A row is flagged when neither side of
the mapping has any non-zero value anywhere in the source data (any economy,
scenario, or year) — i.e. the mapping connects two rows that both look dead.

LEAP source data is not yet available in a comparable output-sheet form, so the
LEAP side of ``leap_combined_esto`` and ``leap_combined_ninth`` is always
treated as "no data" for now. Both of those sheets are therefore flagged
whenever their non-LEAP side alone has no data. See
``docs/improvement_todo.md`` item 8 for the follow-up to check the LEAP side
directly once full LEAP output sheets are available.
"""

#%%
from __future__ import annotations

from pathlib import Path

import pandas as pd

from codebase.functions.ninth_projection_mapping import add_ninth_pair_columns

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKBOOK_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
ESTO_CSV_PATH = REPO_ROOT / "data" / "00APEC_2025_low_with_subtotals.csv"
NINTH_CSV_PATH = REPO_ROOT / "data" / "merged_file_energy_ALL_20251106.csv"
OUTPUT_DIR = REPO_ROOT / "results" / "mapping_relationships"


#%%
def _year_columns(df: pd.DataFrame) -> list[str]:
    return [col for col in df.columns if str(col).strip().isdigit()]


def _nonzero_key_pairs(df: pd.DataFrame, key_cols: list[str]) -> set[tuple[str, str]]:
    """Return the set of key pairs with at least one non-zero value in any year."""
    year_cols = _year_columns(df)
    numeric = df[year_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    has_value = (numeric.abs() > 1e-9).any(axis=1)
    keys = df.loc[has_value, key_cols].astype(str).apply(lambda s: s.str.strip())
    return set(map(tuple, keys.drop_duplicates().values))


def load_nonzero_esto_pairs(esto_csv_path: Path = ESTO_CSV_PATH) -> set[tuple[str, str]]:
    """(esto_flow, esto_product) pairs with non-zero data in any economy or year."""
    esto_df = pd.read_csv(esto_csv_path, dtype=str, low_memory=False)
    return _nonzero_key_pairs(esto_df, ["flows", "products"])


def load_nonzero_ninth_pairs(ninth_csv_path: Path = NINTH_CSV_PATH) -> set[tuple[str, str]]:
    """(ninth_sector, ninth_fuel) pairs with non-zero data in any economy, scenario, or year."""
    ninth_df = pd.read_csv(ninth_csv_path, dtype=str, low_memory=False)
    ninth_df = add_ninth_pair_columns(ninth_df)
    return _nonzero_key_pairs(ninth_df, ["ninth_sector", "ninth_fuel"])


#%%
def _load_mapping_sheet(sheet_name: str, workbook_path: Path = WORKBOOK_PATH) -> pd.DataFrame:
    df = pd.read_excel(workbook_path, sheet_name=sheet_name, dtype=str).fillna("")
    df.insert(0, "workbook_row_number", df.index + 2)  # +2 = header row + 1-based row
    return df


def flag_leap_combined_esto(
    nonzero_esto_pairs: set[tuple[str, str]],
    workbook_path: Path = WORKBOOK_PATH,
) -> pd.DataFrame:
    df = _load_mapping_sheet("leap_combined_esto", workbook_path)
    keys = df[["esto_flow", "esto_product"]].apply(lambda s: s.str.strip())
    df["esto_side_has_data"] = list(map(tuple, keys.values))
    df["esto_side_has_data"] = df["esto_side_has_data"].isin(nonzero_esto_pairs)
    df["leap_side_has_data"] = pd.NA  # not yet checkable; see docs/improvement_todo.md item 8
    flagged = df[~df["esto_side_has_data"]].copy()
    flagged["flag_reason"] = "esto_side_no_data (leap_side not yet checked, assumed no data)"
    return flagged


def flag_leap_combined_ninth(
    nonzero_ninth_pairs: set[tuple[str, str]],
    workbook_path: Path = WORKBOOK_PATH,
) -> pd.DataFrame:
    df = _load_mapping_sheet("leap_combined_ninth", workbook_path)
    keys = df[["ninth_sector", "ninth_fuel"]].apply(lambda s: s.str.strip())
    df["ninth_side_has_data"] = list(map(tuple, keys.values))
    df["ninth_side_has_data"] = df["ninth_side_has_data"].isin(nonzero_ninth_pairs)
    df["leap_side_has_data"] = pd.NA  # not yet checkable; see docs/improvement_todo.md item 8
    flagged = df[~df["ninth_side_has_data"]].copy()
    flagged["flag_reason"] = "ninth_side_no_data (leap_side not yet checked, assumed no data)"
    return flagged


def flag_ninth_pairs_to_esto(
    nonzero_ninth_pairs: set[tuple[str, str]],
    nonzero_esto_pairs: set[tuple[str, str]],
    workbook_path: Path = WORKBOOK_PATH,
) -> pd.DataFrame:
    df = _load_mapping_sheet("ninth_pairs_to_esto_pairs", workbook_path)
    ninth_keys = df[["ninth_sector", "ninth_fuel"]].apply(lambda s: s.str.strip())
    esto_keys = df[["esto_flow", "esto_product"]].apply(lambda s: s.str.strip())
    df["ninth_side_has_data"] = list(map(tuple, ninth_keys.values))
    df["ninth_side_has_data"] = df["ninth_side_has_data"].isin(nonzero_ninth_pairs)
    df["esto_side_has_data"] = list(map(tuple, esto_keys.values))
    df["esto_side_has_data"] = df["esto_side_has_data"].isin(nonzero_esto_pairs)
    flagged = df[~df["ninth_side_has_data"] & ~df["esto_side_has_data"]].copy()
    flagged["flag_reason"] = "both_sides_no_data"
    return flagged


#%%
def run_no_data_mapping_row_check(
    workbook_path: Path = WORKBOOK_PATH,
    esto_csv_path: Path = ESTO_CSV_PATH,
    ninth_csv_path: Path = NINTH_CSV_PATH,
    output_dir: Path = OUTPUT_DIR,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)

    nonzero_esto_pairs = load_nonzero_esto_pairs(esto_csv_path)
    nonzero_ninth_pairs = load_nonzero_ninth_pairs(ninth_csv_path)

    leap_esto_flagged = flag_leap_combined_esto(nonzero_esto_pairs, workbook_path)
    leap_ninth_flagged = flag_leap_combined_ninth(nonzero_ninth_pairs, workbook_path)
    ninth_esto_flagged = flag_ninth_pairs_to_esto(
        nonzero_ninth_pairs, nonzero_esto_pairs, workbook_path
    )

    leap_esto_path = output_dir / "no_data_rows_leap_combined_esto.csv"
    leap_ninth_path = output_dir / "no_data_rows_leap_combined_ninth.csv"
    ninth_esto_path = output_dir / "no_data_rows_ninth_pairs_to_esto.csv"
    summary_path = output_dir / "no_data_rows_summary.csv"

    leap_esto_flagged.to_csv(leap_esto_path, index=False)
    leap_ninth_flagged.to_csv(leap_ninth_path, index=False)
    ninth_esto_flagged.to_csv(ninth_esto_path, index=False)

    summary = pd.DataFrame(
        [
            {
                "sheet": "leap_combined_esto",
                "total_rows": len(pd.read_excel(workbook_path, sheet_name="leap_combined_esto")),
                "flagged_rows": len(leap_esto_flagged),
                "basis": "esto_side_no_data (leap_side assumed no data for now)",
                "output_file": str(leap_esto_path),
            },
            {
                "sheet": "leap_combined_ninth",
                "total_rows": len(pd.read_excel(workbook_path, sheet_name="leap_combined_ninth")),
                "flagged_rows": len(leap_ninth_flagged),
                "basis": "ninth_side_no_data (leap_side assumed no data for now)",
                "output_file": str(leap_ninth_path),
            },
            {
                "sheet": "ninth_pairs_to_esto_pairs",
                "total_rows": len(
                    pd.read_excel(workbook_path, sheet_name="ninth_pairs_to_esto_pairs")
                ),
                "flagged_rows": len(ninth_esto_flagged),
                "basis": "both_sides_no_data",
                "output_file": str(ninth_esto_path),
            },
        ]
    )
    summary.to_csv(summary_path, index=False)

    print(f"leap_combined_esto: {len(leap_esto_flagged):,} rows flagged -> {leap_esto_path}")
    print(f"leap_combined_ninth: {len(leap_ninth_flagged):,} rows flagged -> {leap_ninth_path}")
    print(f"ninth_pairs_to_esto_pairs: {len(ninth_esto_flagged):,} rows flagged -> {ninth_esto_path}")
    print(f"Summary written to {summary_path}")

    return {
        "leap_combined_esto_csv": str(leap_esto_path),
        "leap_combined_ninth_csv": str(leap_ninth_path),
        "ninth_pairs_to_esto_csv": str(ninth_esto_path),
        "summary_csv": str(summary_path),
        "summary": summary,
    }


#%%
if __name__ == "__main__":
    run_no_data_mapping_row_check()
