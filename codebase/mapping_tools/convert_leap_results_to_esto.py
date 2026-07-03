#%%
"""
Convert raw LEAP balance results to ESTO-style flow/product rows.

This script consumes energy_balance_relationships rows for the
leap_to_esto_balance_conversion use case. It expects raw LEAP results with
LEAP flow/product columns and writes grouped ESTO flow/product results.
"""

#%%
from pathlib import Path

import pandas as pd

from codebase.mapping_tools.source_rollups import apply_source_rollups

#%%
REQUIRED_LEAP_COLUMNS = ["leap_flow", "leap_product", "value"]
GROUP_COLUMNS = ["economy", "scenario", "year", "target_flow", "target_product"]

#%%
def _find_repo_root(start_path: Path) -> Path:
    """Find the leap_utilities repo root from a nested workflow path."""
    for candidate in [start_path, *start_path.parents]:
        if (candidate / "AGENTS.md").exists() and (candidate / "config" / "outlook_mappings_master.xlsx").exists():
            return candidate
    raise FileNotFoundError(f"Could not find repo root above: {start_path}")


def read_table(path: Path) -> pd.DataFrame:
    """Read CSV or Excel input."""
    if path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def load_leap_to_esto_relationships(relationships_path: Path) -> pd.DataFrame:
    """Load included LEAP-to-ESTO conversion relationships."""
    relationships_df = pd.read_csv(relationships_path)
    mapping_df = relationships_df[
        (relationships_df["use_case"] == "leap_to_esto_balance_conversion")
        & relationships_df["include_in_use_case"]
        & (relationships_df["source_system"] == "LEAP")
        & relationships_df["target_system"].isin(["ESTO", "ESTO_COMBINED"])
    ].copy()

    unsafe_one_to_many_df = mapping_df[
        mapping_df["cardinality"].fillna("").astype(str).str.lower().str.contains("one_to_many")
        & mapping_df["allocation_method"].fillna("").astype(str).str.lower().isin(["", "direct", "none"])
    ]
    if not unsafe_one_to_many_df.empty:
        print(
            "Warning: included one_to_many relationships without allocation rules: "
            f"{len(unsafe_one_to_many_df):,}"
        )
    return mapping_df


def convert_leap_results_to_esto(
    leap_results_df: pd.DataFrame,
    relationships_df: pd.DataFrame,
    rollup_rules_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Join raw LEAP rows to ESTO targets and aggregate values."""
    missing_columns = [column for column in REQUIRED_LEAP_COLUMNS if column not in leap_results_df.columns]
    if missing_columns:
        raise ValueError(f"LEAP results are missing required columns: {missing_columns}")

    source_df = leap_results_df.copy()
    source_df["value"] = pd.to_numeric(source_df["value"], errors="coerce").fillna(0.0)
    if rollup_rules_df is not None and not rollup_rules_df.empty:
        allowed_pairs = set(
            relationships_df[["source_flow", "source_product"]]
            .fillna("")
            .astype(str)
            .apply(lambda row: (row.iloc[0].strip(), row.iloc[1].strip()), axis=1)
        )
        source_df, _ = apply_source_rollups(
            source_df=source_df,
            rules_df=rollup_rules_df,
            source_flow_column="leap_flow",
            source_product_column="leap_product",
            value_column="value",
            input_flow_column="input_leap_sector_name_full_path",
            input_product_column="input_raw_leap_fuel_name",
            rolled_flow_column="rolled_leap_sector_name_full_path",
            rolled_product_column="rolled_raw_leap_fuel_name",
            allowed_rolled_pairs=allowed_pairs,
        )

    merged_df = source_df.merge(
        relationships_df,
        left_on=["leap_flow", "leap_product"],
        right_on=["source_flow", "source_product"],
        how="left",
    )
    missing_mapping_df = merged_df[merged_df["target_flow"].isna() | merged_df["target_product"].isna()]
    if not missing_mapping_df.empty:
        print(f"Warning: LEAP result rows without included ESTO mapping: {len(missing_mapping_df):,}")

    keep_group_columns = [column for column in GROUP_COLUMNS if column in merged_df.columns]
    converted_df = (
        merged_df.dropna(subset=["target_flow", "target_product"])
        .groupby(keep_group_columns, as_index=False)["value"]
        .sum()
    )
    return converted_df


def run_conversion(
    leap_results_path: Path,
    relationships_path: Path,
    output_path: Path,
    mapping_workbook_path: Path | None = None,
    rollup_audit_path: Path | None = None,
) -> pd.DataFrame:
    """Run LEAP-to-ESTO conversion."""
    leap_results_df = read_table(leap_results_path)
    raw_row_count = len(leap_results_df)
    relationships_df = load_leap_to_esto_relationships(relationships_path)
    rollup_rules_df = None
    rollup_audit_df = None
    if mapping_workbook_path is not None:
        rollup_rules_df = pd.read_excel(
            mapping_workbook_path,
            sheet_name="leap_rollup_rules",
            dtype=object,
        )
        allowed_pairs = set(
            relationships_df[["source_flow", "source_product"]]
            .fillna("")
            .astype(str)
            .apply(lambda row: (row.iloc[0].strip(), row.iloc[1].strip()), axis=1)
        )
        leap_results_df, rollup_audit_df = apply_source_rollups(
            source_df=leap_results_df,
            rules_df=rollup_rules_df,
            source_flow_column="leap_flow",
            source_product_column="leap_product",
            value_column="value",
            input_flow_column="input_leap_sector_name_full_path",
            input_product_column="input_raw_leap_fuel_name",
            rolled_flow_column="rolled_leap_sector_name_full_path",
            rolled_product_column="rolled_raw_leap_fuel_name",
            allowed_rolled_pairs=allowed_pairs,
        )
    converted_df = convert_leap_results_to_esto(leap_results_df, relationships_df)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    converted_df.to_csv(output_path, index=False)
    if rollup_audit_path is not None and rollup_audit_df is not None:
        rollup_audit_path.parent.mkdir(parents=True, exist_ok=True)
        rollup_audit_df.to_csv(rollup_audit_path, index=False)
        print(f"Rollup rule issues written: {len(rollup_audit_df):,}")
        print(f"Wrote rollup audit: {rollup_audit_path}")
    print(f"Raw LEAP rows read: {raw_row_count:,}")
    print(f"Conversion relationships used: {len(relationships_df):,}")
    print(f"Converted ESTO rows written: {len(converted_df):,}")
    print(f"Wrote converted results: {output_path}")
    return converted_df

#%%
# User-tuned constants / flags.
SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = _find_repo_root(SCRIPT_PATH.parent)

LEAP_RESULTS_PATH = REPO_ROOT / "results" / "mapping_relationships" / "raw_leap_results_placeholder.csv"
RELATIONSHIPS_PATH = REPO_ROOT / "results" / "mapping_relationships" / "energy_balance_relationships.csv"
OUTPUT_PATH = REPO_ROOT / "results" / "mapping_relationships" / "leap_results_converted_to_esto.csv"
MAPPING_WORKBOOK_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
ROLLUP_AUDIT_PATH = REPO_ROOT / "results" / "mapping_relationships" / "leap_source_rollup_audit.csv"

RUN_LEAP_TO_ESTO_CONVERSION = False

#%%
if __name__ == "__main__":
    try:
        if RUN_LEAP_TO_ESTO_CONVERSION:
            run_conversion(
                leap_results_path=LEAP_RESULTS_PATH,
                relationships_path=RELATIONSHIPS_PATH,
                output_path=OUTPUT_PATH,
                mapping_workbook_path=MAPPING_WORKBOOK_PATH,
                rollup_audit_path=ROLLUP_AUDIT_PATH,
            )
        else:
            print("Set RUN_LEAP_TO_ESTO_CONVERSION = True after setting LEAP_RESULTS_PATH.")
    except Exception as exc:
        print("LEAP-to-ESTO conversion failed.")
        print(f"Error: {exc}")
        raise

#%%
