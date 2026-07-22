"""Build copy-ready mapping rows after non-zero source/target verification.

The candidate list is intentionally explicit. This keeps uncertain inferred
relationships out of the workbook while the audit functions verify that both
axes have actual data evidence.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.mapping_tools.audit_nonzero_mapping_evidence import (
    MAPPING_PATH,
    OUTPUT_DIR,
    _load_esto_evidence,
    _load_ninth_evidence,
)


OUTPUT_PATH = OUTPUT_DIR / "proposed_nonzero_mapping_rows.csv"
REQUIRED_COLUMNS = [
    "ninth_sector",
    "ninth_fuel",
    "esto_flow",
    "esto_product",
    "ninth_pair_is_subtotal",
    "esto_pair_is_subtotal",
    "duplicate_to_remove",
]

# These are the clear candidates found so far. Ambiguous product families and
# source rows with no ESTO counterpart are deliberately not included.
CANDIDATE_ROWS = [
    {"ninth_sector": "09_total_transformation_sector", "ninth_fuel": "16_09_other_sources", "esto_flow": "09 Total transformation sector", "esto_product": "16.09 Other sources", "ninth_pair_is_subtotal": True, "esto_pair_is_subtotal": True, "duplicate_to_remove": False},
    {"ninth_sector": "09_total_transformation_sector", "ninth_fuel": "16_others_unallocated", "esto_flow": "09 Total transformation sector", "esto_product": "16.09 Other sources", "ninth_pair_is_subtotal": True, "esto_pair_is_subtotal": True, "duplicate_to_remove": False},
    {"ninth_sector": "10_01_09_bkb_pb_plants", "ninth_fuel": "17_electricity", "esto_flow": "10.01.09 BKB/PB plants", "esto_product": "17 Electricity", "ninth_pair_is_subtotal": False, "esto_pair_is_subtotal": False, "duplicate_to_remove": False},
    {"ninth_sector": "10_01_13_pump_storage_plants", "ninth_fuel": "17_electricity", "esto_flow": "10.01.13 Pump storage plants", "esto_product": "17 Electricity", "ninth_pair_is_subtotal": False, "esto_pair_is_subtotal": False, "duplicate_to_remove": False},
    {"ninth_sector": "10_01_15_charcoal_production_plants", "ninth_fuel": "17_electricity", "esto_flow": "10.01.15 Charcoal production plants", "esto_product": "17 Electricity", "ninth_pair_is_subtotal": False, "esto_pair_is_subtotal": False, "duplicate_to_remove": False},
]


def build_candidates() -> pd.DataFrame:
    rows = pd.DataFrame(CANDIDATE_ROWS)
    existing = pd.read_excel(MAPPING_PATH, sheet_name="ninth_pairs_to_esto_pairs", dtype=str).fillna("")
    existing = existing[["ninth_sector", "ninth_fuel", "esto_flow", "esto_product"]].drop_duplicates()
    rows = rows.merge(
        existing.assign(_already_mapped=True),
        on=["ninth_sector", "ninth_fuel", "esto_flow", "esto_product"],
        how="left",
    )
    rows = rows[rows["_already_mapped"].ne(True)].drop(columns="_already_mapped")
    ninth = _load_ninth_evidence().groupby(["ninth_sector", "ninth_fuel"], dropna=False).agg(
        source_nonzero_rows=("nonzero_rows", "sum"),
        source_nonzero_economies=("nonzero_economies", "sum"),
        source_total_abs=("total_abs", "sum"),
    ).reset_index()
    esto = _load_esto_evidence().groupby(["flows", "products"], dropna=False).agg(
        target_nonzero_rows=("nonzero_rows", "sum"),
        target_nonzero_economies=("nonzero_economies", "sum"),
        target_total_abs=("total_abs", "sum"),
    ).reset_index().rename(columns={"flows": "esto_flow", "products": "esto_product"})
    checked = rows.merge(ninth, on=["ninth_sector", "ninth_fuel"], how="left").merge(
        esto, on=["esto_flow", "esto_product"], how="left"
    )
    for column in ["source_nonzero_rows", "target_nonzero_rows", "source_total_abs", "target_total_abs"]:
        checked[column] = pd.to_numeric(checked[column], errors="coerce").fillna(0.0)
    checked = checked[checked.source_nonzero_rows.gt(0) & checked.target_nonzero_rows.gt(0)].copy()
    return checked[REQUIRED_COLUMNS].drop_duplicates().sort_values(REQUIRED_COLUMNS[:4]).reset_index(drop=True)


def run() -> Path:
    result = build_candidates()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {len(result)} verified rows to {OUTPUT_PATH}")
    return OUTPUT_PATH


if __name__ == "__main__":
    run()
