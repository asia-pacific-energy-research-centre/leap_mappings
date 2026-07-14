#%%
"""Build a small colleague-facing Common ESTO export folder.

This script copies the final wide comparison output and writes a simplified
source-to-common membership file with only the columns useful for quick review.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

RESULTS_ROOT = REPO_ROOT / "results"
COMMON_ESTO_ROOT = RESULTS_ROOT / "common_esto"
STRUCTURAL_ARTIFACTS_ROOT = COMMON_ESTO_ROOT / "structural_artifacts"
FOR_COLLEAGUES_ROOT = RESULTS_ROOT / "for_colleagues"
MAPPING_WORKBOOK_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"

COMMON_WIDE_PATH = COMMON_ESTO_ROOT / "common_esto_comparison_wide.csv"
SOURCE_COMMON_PATH = STRUCTURAL_ARTIFACTS_ROOT / "source_pair_to_common_row.csv"
ESTO_SOURCE_PATH = REPO_ROOT / "data" / "00APEC_2025_low_with_subtotals.csv"

OUTPUT_WIDE_PATH = FOR_COLLEAGUES_ROOT / "common_esto_comparison_wide.csv"
OUTPUT_SOURCE_PATH = FOR_COLLEAGUES_ROOT / "source_pair_to_common_row.csv"

KEEP_COLUMNS = [
    "comparison_scope",
    "source_system",
    "effective_source_flow",
    "effective_source_product",
    "common_flow_name",
    "common_product_name",
    "common_row_is_subtotal",
    "source_row_is_subtotal",
]


def _clean(value: object) -> str:
    text = str(value if value is not None else "").strip()
    return "" if text.lower() in {"", "nan", "none"} else text


def _truthy(value: object) -> bool:
    text = _clean(value).lower()
    return text in {"true", "1", "yes", "y", "t"}


def _resolve(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = REPO_ROOT / resolved
    return resolved


def _load_source_row_is_subtotal_lookup() -> pd.DataFrame:
    """Build a compact source-level subtotal lookup for LEAP and ESTO rows."""
    leap = pd.read_excel(MAPPING_WORKBOOK_PATH, sheet_name="leap_combined_esto", dtype=object)
    leap_lookup = leap.rename(
        columns={
            "leap_sector_name_full_path": "effective_source_flow",
            "raw_leap_fuel_name": "effective_source_product",
        }
    )
    if "leap_is_subtotal" not in leap_lookup.columns:
        leap_lookup["leap_is_subtotal"] = False
    leap_lookup = leap_lookup[[
        "effective_source_flow",
        "effective_source_product",
        "leap_is_subtotal",
    ]].copy()
    leap_lookup["source_system"] = "LEAP"
    leap_lookup["source_row_is_subtotal"] = leap_lookup["leap_is_subtotal"].map(_truthy)

    esto = pd.read_csv(ESTO_SOURCE_PATH, dtype=object)
    if "is_subtotal" not in esto.columns:
        esto["is_subtotal"] = False
    esto_lookup = esto.rename(
        columns={"flows": "effective_source_flow", "products": "effective_source_product"}
    )[["effective_source_flow", "effective_source_product", "is_subtotal"]].copy()
    esto_lookup["source_system"] = "ESTO"
    esto_lookup["source_row_is_subtotal"] = esto_lookup["is_subtotal"].map(_truthy)

    lookup = pd.concat(
        [
            leap_lookup[["source_system", "effective_source_flow", "effective_source_product", "source_row_is_subtotal"]],
            esto_lookup[["source_system", "effective_source_flow", "effective_source_product", "source_row_is_subtotal"]],
        ],
        ignore_index=True,
    )
    lookup = lookup.drop_duplicates(
        subset=["source_system", "effective_source_flow", "effective_source_product"],
        keep="first",
    )
    return lookup


def build_for_colleagues_export() -> dict[str, Path]:
    """Write a simplified Common ESTO export folder for quick sharing."""
    FOR_COLLEAGUES_ROOT.mkdir(parents=True, exist_ok=True)

    wide_df = pd.read_csv(_resolve(COMMON_WIDE_PATH), dtype=object)
    wide_lookup = wide_df[["flow", "product", "is_subtotal"]].copy()
    wide_lookup = wide_lookup.rename(
        columns={
            "flow": "common_flow_label",
            "product": "common_product_label",
            "is_subtotal": "common_row_is_subtotal",
        }
    ).drop_duplicates()
    wide_df.to_csv(OUTPUT_WIDE_PATH, index=False)

    source_df = pd.read_csv(_resolve(SOURCE_COMMON_PATH), dtype=object)
    source_df = source_df[source_df["comparison_scope"].astype(str).eq("leap_vs_esto")].copy()

    lookup = _load_source_row_is_subtotal_lookup()
    source_df = source_df.merge(
        lookup,
        on=["source_system", "effective_source_flow", "effective_source_product"],
        how="left",
    )
    source_df = source_df.merge(
        wide_lookup,
        on=["common_flow_label", "common_product_label"],
        how="left",
    )
    source_df["common_row_is_subtotal"] = source_df["common_row_is_subtotal"].fillna(False).map(_truthy)
    source_df["source_row_is_subtotal"] = source_df["source_row_is_subtotal"].fillna(False).map(_truthy)

    output = source_df[KEEP_COLUMNS].copy()
    output = output.sort_values(
        ["source_system", "effective_source_flow", "effective_source_product", "common_flow_name", "common_product_name"],
        kind="stable",
    ).reset_index(drop=True)
    output.to_csv(OUTPUT_SOURCE_PATH, index=False)

    return {
        "common_esto_comparison_wide": OUTPUT_WIDE_PATH,
        "source_pair_to_common_row": OUTPUT_SOURCE_PATH,
    }


#%%
RUN_FOR_COLLEAGUES_EXPORT = True

if __name__ == "__main__" and RUN_FOR_COLLEAGUES_EXPORT:
    RESULT_PATHS = build_for_colleagues_export()
    for name, path in RESULT_PATHS.items():
        print(f"{name}: {path}")
#%%
