"""Audit non-zero source and target evidence for proposed mapping rows.

This read-only, notebook-safe audit checks whether focused 9th source pairs and
their proposed ESTO counterparts occur with non-zero values in the current
reference datasets. It does not edit the mapping workbook or apply mappings.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.functions.ninth_projection_mapping import add_ninth_pair_columns


MAPPING_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
NINTH_PATH = REPO_ROOT / "data" / "merged_file_energy_ALL_20251106.csv"
ESTO_PATH = REPO_ROOT / "data" / "00APEC_2025_low_with_subtotals.csv"
OUTPUT_DIR = REPO_ROOT / "results" / "mapping_relationships"
SCENARIO = "reference"
# Current review scope: exclude historical-only activity through 2015.
NINTH_EVIDENCE_YEARS = tuple(range(2016, 2071))
ESTO_BASE_YEAR = 2022
NONZERO_TOLERANCE = 1e-12

# These are the source categories currently being investigated. The audit also
# includes every workbook row touching one of these categories.
FOCUS_SECTORS = {
    "09_total_transformation_sector",
    "14_03_manufacturing",
    "10_01_04_gastoliquids_plants",
    "10_01_08_patent_fuel_plants",
    "10_01_09_bkb_pb_plants",
    "10_01_10_liquefaction_plants_coal_to_oil",
    "10_01_13_pump_storage_plants",
    "10_01_14_nuclear_industry",
    "10_01_15_charcoal_production_plants",
    "10_01_16_gasification_plants_for_biogases",
    "10_01_18_ccs",
}
FOCUS_FUELS = {
    "08_gas",
    "07_petroleum_products",
    "15_solid_biomass",
    "16_others",
}

# Candidate rows are deliberately kept separate from the workbook. They are
# the high-signal gaps identified during investigation and are only evaluated
# here; a human must still copy approved rows into the workbook.
PROPOSED_ROWS = [
    {"ninth_sector": "09_total_transformation_sector", "ninth_fuel": "08_gas_unallocated", "esto_flow": "09 Total transformation sector", "esto_product": "08.99 Gas nonspecified"},
    {"ninth_sector": "09_total_transformation_sector", "ninth_fuel": "15_solid_biomass_unallocated", "esto_flow": "09 Total transformation sector", "esto_product": "15.05 Other biomass"},
    {"ninth_sector": "09_total_transformation_sector", "ninth_fuel": "16_05_biogasoline", "esto_flow": "09 Total transformation sector", "esto_product": "16.05 Biogasoline"},
    {"ninth_sector": "09_total_transformation_sector", "ninth_fuel": "16_07_bio_jet_kerosene", "esto_flow": "09 Total transformation sector", "esto_product": "16.07 Bio jet kerosene"},
    {"ninth_sector": "09_total_transformation_sector", "ninth_fuel": "16_09_other_sources", "esto_flow": "09 Total transformation sector", "esto_product": "16.09 Other sources"},
    {"ninth_sector": "09_total_transformation_sector", "ninth_fuel": "16_others_unallocated", "esto_flow": "09 Total transformation sector", "esto_product": "16.09 Other sources"},
]


def _year_columns(frame: pd.DataFrame, years: tuple[int, ...]) -> list[str | int]:
    return [year if year in frame.columns else str(year) for year in years if year in frame.columns or str(year) in frame.columns]


def _nonzero_stats(frame: pd.DataFrame, value_columns: list[str | int], group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=group_columns + ["nonzero_rows", "nonzero_economies", "nonzero_years", "total_abs", "max_abs"])
    values = frame[value_columns].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    nonzero_mask = values.abs().gt(NONZERO_TOLERANCE).any(axis=1)
    working = frame.loc[nonzero_mask, group_columns].copy()
    if working.empty:
        return pd.DataFrame(columns=group_columns + ["nonzero_rows", "nonzero_economies", "nonzero_years", "total_abs", "max_abs"])
    working["row_total_abs"] = values.loc[nonzero_mask].abs().sum(axis=1).to_numpy()
    working["row_max_abs"] = values.loc[nonzero_mask].abs().max(axis=1).to_numpy()
    year_counts = values.loc[nonzero_mask].abs().gt(NONZERO_TOLERANCE).sum(axis=0)
    stats = working.groupby(group_columns, dropna=False).agg(
        nonzero_rows=("row_total_abs", "size"),
        nonzero_economies=("economy", "nunique"),
        total_abs=("row_total_abs", "sum"),
        max_abs=("row_max_abs", "max"),
    ).reset_index()
    stats["nonzero_years"] = int((year_counts > 0).sum())
    return stats


def _load_ninth_evidence() -> pd.DataFrame:
    frame = pd.read_csv(NINTH_PATH, low_memory=False)
    # Keep subtotal rows: proposed rows often intentionally refer to an
    # aggregate 9th category, and the question here is whether any source
    # evidence exists, not whether the row is suitable for additive totals.
    frame = frame[
        frame["scenarios"].astype(str).str.strip().str.lower().eq(SCENARIO.lower())
    ].copy()
    frame = add_ninth_pair_columns(frame)
    years = _year_columns(frame, NINTH_EVIDENCE_YEARS)
    proposed_sectors = {row["ninth_sector"] for row in PROPOSED_ROWS}
    proposed_fuels = {row["ninth_fuel"] for row in PROPOSED_ROWS}
    frame = frame[
        frame["ninth_sector"].isin(FOCUS_SECTORS | proposed_sectors)
        | frame["ninth_fuel"].isin(FOCUS_FUELS | proposed_fuels)
    ].copy()
    return _nonzero_stats(frame, years, ["ninth_sector", "ninth_fuel", "economy"])


def _load_esto_evidence() -> pd.DataFrame:
    frame = pd.read_csv(ESTO_PATH, low_memory=False)
    year_columns = [column for column in frame.columns if str(column).isdigit()]
    # Include subtotal rows as evidence. Subtotal status is a separate review
    # question and must not hide a nonzero target counterpart.
    return _nonzero_stats(frame, year_columns, ["flows", "products", "economy"])


def run_audit() -> dict[str, Path]:
    mapping = pd.read_excel(MAPPING_PATH, sheet_name="ninth_pairs_to_esto_pairs", dtype=str).fillna("")
    required = ["ninth_sector", "ninth_fuel", "esto_flow", "esto_product"]
    mapping = mapping[required].drop_duplicates()
    focused = mapping[mapping["ninth_sector"].isin(FOCUS_SECTORS) | mapping["ninth_fuel"].isin(FOCUS_FUELS)].copy()
    proposed = pd.DataFrame(PROPOSED_ROWS)
    proposed["row_origin"] = "proposed_not_in_workbook"
    focused["row_origin"] = "currently_in_workbook"
    rows = pd.concat([focused, proposed], ignore_index=True).drop_duplicates(required).reset_index(drop=True)

    ninth = _load_ninth_evidence()
    esto = _load_esto_evidence()
    ninth_pair = ninth.groupby(["ninth_sector", "ninth_fuel"], dropna=False).agg(
        ninth_nonzero_rows=("nonzero_rows", "sum"),
        ninth_nonzero_economies=("nonzero_economies", "sum"),
        ninth_nonzero_years=("nonzero_years", "max"),
        ninth_total_abs=("total_abs", "sum"),
        ninth_max_abs=("max_abs", "max"),
    ).reset_index()
    rows = rows.merge(ninth_pair, on=["ninth_sector", "ninth_fuel"], how="left")
    esto_pair = esto.groupby(["flows", "products"], dropna=False).agg(
        esto_nonzero_rows=("nonzero_rows", "sum"),
        esto_nonzero_economies=("nonzero_economies", "sum"),
        esto_nonzero_years=("nonzero_years", "max"),
        esto_total_abs=("total_abs", "sum"),
        esto_max_abs=("max_abs", "max"),
    ).reset_index().rename(columns={"flows": "esto_flow", "products": "esto_product"})
    rows = rows.merge(esto_pair, on=["esto_flow", "esto_product"], how="left")
    for col in rows.columns:
        if col.endswith(("rows", "economies", "years", "total_abs", "max_abs")):
            rows[col] = pd.to_numeric(rows[col], errors="coerce").fillna(0)
    rows["source_nonzero"] = rows["ninth_nonzero_rows"].gt(0)
    rows["target_nonzero"] = rows["esto_nonzero_rows"].gt(0)
    rows["evidence_status"] = "both_nonzero"
    rows.loc[~rows.source_nonzero, "evidence_status"] = "source_zero_or_absent"
    rows.loc[rows.source_nonzero & ~rows.target_nonzero, "evidence_status"] = "target_zero_or_absent"
    rows = rows.sort_values(["evidence_status", "ninth_sector", "ninth_fuel", "esto_flow", "esto_product"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    detail_path = OUTPUT_DIR / "nonzero_mapping_evidence_audit.csv"
    source_path = OUTPUT_DIR / "nonzero_source_pair_evidence_audit.csv"
    rows.to_csv(detail_path, index=False)
    ninth.to_csv(source_path, index=False)
    return {"detail": detail_path, "source_pairs": source_path}


if __name__ == "__main__":
    outputs = run_audit()
    print("Wrote:")
    for path in outputs.values():
        print(path)
