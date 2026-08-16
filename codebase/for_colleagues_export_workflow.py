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
FOR_COLLEAGUES_ROOT = RESULTS_ROOT / "for_colleagues"
COMMON_WIDE_PATH = COMMON_ESTO_ROOT / "common_esto_comparison_wide.csv"
SOURCE_COMMON_PATH = COMMON_ESTO_ROOT / "source_to_common_esto_map.csv"

OUTPUT_WIDE_PATH = FOR_COLLEAGUES_ROOT / "common_esto_comparison_wide.csv"
OUTPUT_SOURCE_PATH = FOR_COLLEAGUES_ROOT / "source_to_common_esto_map.csv"

KEEP_COLUMNS = [
    "scope",
    "system",
    "source_flow",
    "source_product",
    "common_row_id",
    "common_flow_label",
    "common_product_label",
]


def _resolve(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = REPO_ROOT / resolved
    return resolved


def write_csv_with_locked_fallback(df: pd.DataFrame, output_path: Path) -> Path:
    """Write a CSV, falling back to a rebuilt filename if the target is locked."""
    try:
        df.to_csv(output_path, index=False)
        return output_path
    except PermissionError:
        fallback_path = output_path.with_name(f"{output_path.stem}_rebuilt{output_path.suffix}")
        print(f"Could not overwrite locked CSV: {output_path}")
        print(f"Writing rebuilt CSV instead: {fallback_path}")
        df.to_csv(fallback_path, index=False)
        return fallback_path


def build_for_colleagues_export() -> dict[str, Path]:
    """Write a simplified Common ESTO export folder for quick sharing."""
    FOR_COLLEAGUES_ROOT.mkdir(parents=True, exist_ok=True)

    wide_df = pd.read_csv(_resolve(COMMON_WIDE_PATH), dtype=object)
    wide_output_path = write_csv_with_locked_fallback(wide_df, OUTPUT_WIDE_PATH)

    source_df = pd.read_csv(_resolve(SOURCE_COMMON_PATH), dtype=object)
    output = source_df[KEEP_COLUMNS].copy()
    output_path = write_csv_with_locked_fallback(output, OUTPUT_SOURCE_PATH)

    return {
        "common_esto_comparison_wide": wide_output_path,
        "source_to_common_esto_map": output_path,
    }


#%%
RUN_FOR_COLLEAGUES_EXPORT = True

if __name__ == "__main__" and RUN_FOR_COLLEAGUES_EXPORT:
    RESULT_PATHS = build_for_colleagues_export()
    for name, path in RESULT_PATHS.items():
        print(f"{name}: {path}")
#%%
