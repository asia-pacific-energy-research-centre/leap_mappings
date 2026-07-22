"""Build copy-ready LEAP-to-9th mapping rows for verified candidates."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


MAPPING_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
OUTPUT_PATH = REPO_ROOT / "results" / "mapping_relationships" / "proposed_leap_combined_ninth_rows.csv"
REQUIRED_COLUMNS = [
    "leap_sector_name_full_path",
    "raw_leap_fuel_name",
    "ninth_sector",
    "ninth_fuel",
    "leap_is_subtotal",
    "ninth_pair_is_subtotal",
    "duplicate_to_remove",
]

CANDIDATE_ROWS = [
    {
        "leap_sector_name_full_path": "Total transformation - no transfers",
        "raw_leap_fuel_name": "Other sources",
        "ninth_sector": "09_total_transformation_sector",
        "ninth_fuel": "16_09_other_sources",
        "leap_is_subtotal": True,
        "ninth_pair_is_subtotal": True,
        "duplicate_to_remove": False,
    },
    {
        "leap_sector_name_full_path": "Other loss and own use/Pump storage plants",
        "raw_leap_fuel_name": "Electricity",
        "ninth_sector": "10_01_13_pump_storage_plants",
        "ninth_fuel": "17_electricity",
        "leap_is_subtotal": False,
        "ninth_pair_is_subtotal": False,
        "duplicate_to_remove": False,
    },
]


def build_rows() -> pd.DataFrame:
    rows = pd.DataFrame(CANDIDATE_ROWS)
    existing = pd.read_excel(MAPPING_PATH, sheet_name="leap_combined_ninth", dtype=str).fillna("")
    existing = existing[REQUIRED_COLUMNS[:4]].drop_duplicates()
    rows = rows.merge(
        existing.assign(_already_mapped=True),
        on=REQUIRED_COLUMNS[:4],
        how="left",
    )
    rows = rows[rows["_already_mapped"].ne(True)].drop(columns="_already_mapped")

    esto = pd.read_excel(MAPPING_PATH, sheet_name="leap_combined_esto", dtype=str).fillna("")
    for row in rows.to_dict("records"):
        matching = esto[
            (esto.leap_sector_name_full_path == row["leap_sector_name_full_path"])
            & (esto.raw_leap_fuel_name == row["raw_leap_fuel_name"])
            & (esto.esto_flow.isin(["09 Total transformation sector", "10.01.13 Pump storage plants"]))
        ]
        if matching.empty:
            raise ValueError(f"No existing LEAP-to-ESTO evidence for candidate: {row}")
    return rows[REQUIRED_COLUMNS].sort_values(REQUIRED_COLUMNS[:4]).reset_index(drop=True)


def run() -> Path:
    result = build_rows()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {len(result)} rows to {OUTPUT_PATH}")
    return OUTPUT_PATH


if __name__ == "__main__":
    run()
