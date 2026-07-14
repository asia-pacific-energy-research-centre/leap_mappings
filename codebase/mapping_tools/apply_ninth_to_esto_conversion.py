#%%
"""
Convert raw 9th Outlook rows to ESTO-style flow/product rows.

This script consumes energy_balance_relationships rows for the
ninth_to_esto_balance_conversion use case and writes grouped ESTO rows.
"""

#%%
from pathlib import Path

import pandas as pd

from codebase.mapping_tools.target_share_allocation import apply_target_dataset_allocation

#%%
REQUIRED_NINTH_COLUMNS = ["ninth_sector", "ninth_fuel", "value"]
GROUP_COLUMNS = ["source_system", "economy", "scenario", "year", "target_flow", "target_product"]
SOURCE_LINEAGE_COLUMNS = [
    "source_system",
    "economy",
    "scenario",
    "year",
    "source_flow",
    "source_product",
    "target_flow",
    "target_product",
    "relationship_id",
    "allocation_share",
    "allocation_source",
    "value",
]

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


def prepare_ninth_long_format(
    ninth_csv_path: Path,
    scenario_filter: str | list[str] | None = None,
    mapped_pairs: set[tuple[str, str]] | None = None,
) -> pd.DataFrame:
    """
    Reshape the 9th Outlook wide-format CSV to long format with ninth_sector
    and ninth_fuel columns suitable for the conversion join.

    ninth_sector = the most specific available sector hierarchy level
    ninth_fuel   = subfuels value, or fuels where subfuels == 'x'

    ``scenario_filter`` optionally restricts rows to one or more scenario
    values (case-insensitive). Leave as ``None`` (the default) to pass through
    every scenario present in the source data (e.g. both "reference" and
    "target").

    ``mapped_pairs`` optionally restricts the wide frame to
    ``(ninth_sector, ninth_fuel)`` pairs that have an included ESTO mapping
    *before* melting across every year column. This is purely a performance
    filter: the downstream :func:`convert_ninth_results_to_esto` left-merges on
    the same pair and drops unmapped rows anyway, so pre-filtering removes only
    rows that would be discarded, leaving the converted output unchanged while
    avoiding the expansion of ~85% unmapped sector/fuel combos across all years.
    """
    df = pd.read_csv(ninth_csv_path, dtype=object)

    if "scenarios" in df.columns and scenario_filter:
        allowed = {scenario_filter} if isinstance(scenario_filter, str) else set(scenario_filter)
        allowed = {value.lower() for value in allowed}
        df = df[df["scenarios"].str.lower().isin(allowed)]

    df = df.copy()
    # Resolve ninth_sector to the most specific hierarchy level present.
    sub2 = df["sub2sectors"].astype(str).str.strip()
    sub1 = df["sub1sectors"].astype(str).str.strip()
    sectors = df["sectors"].astype(str).str.strip()
    df["ninth_sector"] = sectors
    df.loc[sub1 != "x", "ninth_sector"] = sub1[sub1 != "x"]
    df.loc[sub2 != "x", "ninth_sector"] = sub2[sub2 != "x"]

    # Resolve fuel: subfuels if not 'x', else fuels
    df["ninth_fuel"] = df["subfuels"].astype(str).str.strip()
    mask_x = df["ninth_fuel"] == "x"
    df.loc[mask_x, "ninth_fuel"] = df.loc[mask_x, "fuels"].astype(str).str.strip()
    df["source_system"] = "NINTH"

    # Filter-before-melt: keep only sector/fuel pairs with an included mapping.
    # Uses string-key membership, which is a superset of what the downstream
    # merge would match (equal raw values always share a string form), so no
    # matchable row is dropped and the converted output is byte-for-byte identical.
    if mapped_pairs is not None:
        mapped_keys = {f"{str(flow)}\x1f{str(product)}" for flow, product in mapped_pairs}
        pair_key = df["ninth_sector"].astype(str) + "\x1f" + df["ninth_fuel"].astype(str)
        df = df[pair_key.isin(mapped_keys)].copy()

    # Identify year columns
    year_cols = [c for c in df.columns if str(c).isdigit()]
    for col in year_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    id_cols = ["source_system", "economy", "scenarios", "ninth_sector", "ninth_fuel"]
    id_cols = [c for c in id_cols if c in df.columns]

    long_df = df[id_cols + year_cols].melt(
        id_vars=id_cols,
        value_vars=year_cols,
        var_name="year",
        value_name="value",
    ).dropna(subset=["value"])

    long_df = long_df.rename(columns={"scenarios": "scenario"})
    long_df["year"] = long_df["year"].astype(int)
    return long_df.reset_index(drop=True)


def load_ninth_to_esto_relationships(relationships_path: Path) -> pd.DataFrame:
    """Load included 9th-to-ESTO conversion relationships."""
    relationships_df = pd.read_csv(relationships_path)
    relationships_df["include_in_use_case"] = relationships_df["include_in_use_case"].astype(str).str.lower().isin(["true", "1", "yes"])
    mapping_df = relationships_df[
        (relationships_df["use_case"] == "ninth_to_esto_balance_conversion")
        & relationships_df["include_in_use_case"]
        & (relationships_df["source_system"] == "NINTH")
        & (relationships_df["target_system"] == "ESTO")
    ].copy()
    return mapping_df


def build_source_to_esto_lineage(merged_df: pd.DataFrame, source_system: str) -> pd.DataFrame:
    """Return post-allocation source-to-ESTO contribution rows."""
    mapped_df = merged_df.dropna(subset=["target_flow", "target_product"]).copy()
    if mapped_df.empty:
        return pd.DataFrame(columns=SOURCE_LINEAGE_COLUMNS)
    mapped_df["source_system"] = source_system
    if "relationship_id" not in mapped_df.columns:
        mapped_df["relationship_id"] = ""
    if "allocation_share" not in mapped_df.columns:
        mapped_df["allocation_share"] = 1.0
    mapped_df["allocation_share"] = pd.to_numeric(mapped_df["allocation_share"], errors="coerce").fillna(1.0)
    if "allocation_source" not in mapped_df.columns:
        mapped_df["allocation_source"] = ""
    for column in SOURCE_LINEAGE_COLUMNS:
        if column not in mapped_df.columns:
            mapped_df[column] = ""
    return mapped_df[SOURCE_LINEAGE_COLUMNS].copy()


def convert_ninth_results_to_esto(
    ninth_results_df: pd.DataFrame,
    relationships_df: pd.DataFrame,
    target_values_df: pd.DataFrame | None = None,
    return_lineage: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]:
    """Join raw 9th rows to ESTO targets and aggregate values."""
    missing_columns = [column for column in REQUIRED_NINTH_COLUMNS if column not in ninth_results_df.columns]
    if missing_columns:
        raise ValueError(f"9th results are missing required columns: {missing_columns}")

    merged_df = ninth_results_df.merge(
        relationships_df,
        left_on=["ninth_sector", "ninth_fuel"],
        right_on=["source_flow", "source_product"],
        how="left",
    )
    missing_mapping_df = merged_df[merged_df["target_flow"].isna() | merged_df["target_product"].isna()]
    if not missing_mapping_df.empty:
        print(f"Warning: 9th result rows without included ESTO mapping: {len(missing_mapping_df):,}")

    if target_values_df is not None:
        merged_df = apply_target_dataset_allocation(merged_df, target_values_df)

    if "allocation_share" in merged_df.columns:
        allocation_share = pd.to_numeric(merged_df["allocation_share"], errors="coerce").fillna(1.0)
        merged_df["value"] = merged_df["value"] * allocation_share

    merged_df["source_system"] = "NINTH"
    lineage_df = build_source_to_esto_lineage(merged_df, source_system="NINTH") if return_lineage else None
    keep_group_columns = [column for column in GROUP_COLUMNS if column in merged_df.columns]
    converted_df = (
        merged_df.dropna(subset=["target_flow", "target_product"])
        .groupby(keep_group_columns, as_index=False)["value"]
        .sum()
    )
    if return_lineage:
        return converted_df, lineage_df
    return converted_df


def relationships_need_target_dataset_share(relationships_df: pd.DataFrame) -> bool:
    """Return True when conversion needs target ESTO basis values."""
    if "allocation_source" not in relationships_df.columns:
        return False
    return relationships_df["allocation_source"].fillna("").astype(str).str.strip().str.casefold().eq(
        "target_dataset_share"
    ).any()


def run_conversion(
    ninth_results_path: Path,
    relationships_path: Path,
    output_path: Path,
    target_values_path: Path | None = None,
    lineage_output_path: Path | None = None,
) -> pd.DataFrame:
    """Run 9th-to-ESTO conversion."""
    ninth_results_df = read_table(ninth_results_path)
    relationships_df = load_ninth_to_esto_relationships(relationships_path)
    target_values_df = None
    if target_values_path is not None and relationships_need_target_dataset_share(relationships_df):
        target_values_df = read_table(target_values_path)
    if lineage_output_path is not None:
        converted_df, lineage_df = convert_ninth_results_to_esto(
            ninth_results_df,
            relationships_df,
            target_values_df,
            return_lineage=True,
        )
    else:
        converted_df = convert_ninth_results_to_esto(ninth_results_df, relationships_df, target_values_df)
        lineage_df = None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    converted_df.to_csv(output_path, index=False)
    if lineage_output_path is not None and lineage_df is not None:
        lineage_output_path.parent.mkdir(parents=True, exist_ok=True)
        lineage_df.to_csv(lineage_output_path, index=False)
        print(f"Source-to-ESTO lineage rows written: {len(lineage_df):,}")
        print(f"Wrote lineage: {lineage_output_path}")
    print(f"Raw 9th rows read: {len(ninth_results_df):,}")
    print(f"Conversion relationships used: {len(relationships_df):,}")
    print(f"Converted ESTO rows written: {len(converted_df):,}")
    print(f"Wrote converted results: {output_path}")
    return converted_df

#%%
# User-tuned constants / flags.
SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = _find_repo_root(SCRIPT_PATH.parent)

RELATIONSHIP_DIR = REPO_ROOT / "results" / "mapping_relationships"
NINTH_RESULTS_PATH = RELATIONSHIP_DIR / "raw_ninth_results_placeholder.csv"
RELATIONSHIPS_PATH = RELATIONSHIP_DIR / "energy_balance_relationships.csv"
OUTPUT_PATH = RELATIONSHIP_DIR / "ninth_results_converted_to_esto.csv"

RUN_NINTH_TO_ESTO_CONVERSION = False

#%%
if __name__ == "__main__":
    try:
        if RUN_NINTH_TO_ESTO_CONVERSION:
            run_conversion(
                ninth_results_path=NINTH_RESULTS_PATH,
                relationships_path=RELATIONSHIPS_PATH,
                output_path=OUTPUT_PATH,
            )
        else:
            print("Set RUN_NINTH_TO_ESTO_CONVERSION = True after setting NINTH_RESULTS_PATH.")
    except Exception as exc:
        print("9th-to-ESTO conversion failed.")
        print(f"Error: {exc}")
        raise

#%%
