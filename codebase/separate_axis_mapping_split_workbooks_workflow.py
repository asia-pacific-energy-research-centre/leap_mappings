#%%
"""Prepare the narrow tables used by the three separate-axis workbooks.

The editable workbook contains six axis relationship tables and four reviewed
extra-pair tables. Generated pair registries and compiled compatibility sheets
are written separately so their workbooks can be clearly marked read-only.
"""

#%%
from __future__ import annotations

import json
import traceback
from pathlib import Path

import pandas as pd


# --- Stable paths -----------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE_SOURCE_ROOT = (
    REPO_ROOT
    / "outputs"
    / "separate_axis_mapping_refresh"
    / "compiler"
    / "data"
)
OUTPUT_ROOT = (
    REPO_ROOT / "outputs" / "separate_axis_mapping_refresh" / "workbooks"
)
OUTPUT_DATA_ROOT = OUTPUT_ROOT / "data"

CANONICAL_MASTER_PATH = (
    REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
)
EDITABLE_AXIS_WORKBOOK_PATH = (
    REPO_ROOT / "config" / "outlook_mappings_single_axis.xlsx"
)
GENERATED_PAIR_WORKBOOK_PATH = (
    REPO_ROOT
    / "config"
    / "outlook_mappings_key_pairs_generated.xlsx"
)
GENERATED_MASTER_WORKBOOK_PATH = (
    OUTPUT_ROOT / "outlook_mappings_master_candidate.xlsx"
)

HISTORICAL_BOUNDARY_YEAR = 2023

AXIS_SOURCE_FILES = {
    "sector": PROTOTYPE_SOURCE_ROOT / "sector_flow_axis_mappings.csv",
    "fuel": PROTOTYPE_SOURCE_ROOT / "fuel_product_axis_mappings.csv",
}
PAIR_SOURCE_FILES = {
    "LEAP key pairs": (
        PROTOTYPE_SOURCE_ROOT / "pair_universe_leap.csv"
    ),
    "ESTO key pairs": (
        PROTOTYPE_SOURCE_ROOT / "pair_universe_esto.csv"
    ),
    "ESTO Extended key pairs": (
        PROTOTYPE_SOURCE_ROOT / "pair_universe_esto_extended.csv"
    ),
    "Ninth key pairs": (
        PROTOTYPE_SOURCE_ROOT / "pair_universe_ninth.csv"
    ),
}
COMPILED_SOURCE_FILES = {
    "leap_combined_esto": (
        PROTOTYPE_SOURCE_ROOT / "compiled_leap_combined_esto.csv"
    ),
    "leap_combined_ninth": (
        PROTOTYPE_SOURCE_ROOT / "compiled_leap_combined_ninth.csv"
    ),
    "ninth_pairs_to_esto_pairs": (
        PROTOTYPE_SOURCE_ROOT
        / "compiled_ninth_pairs_to_esto_pairs.csv"
    ),
}
EXTRA_PAIR_SOURCE_FILES = {
    "extra_leap_key_pairs": (
        PROTOTYPE_SOURCE_ROOT / "editable_extra_leap_key_pairs.csv"
    ),
    "extra_esto_key_pairs": (
        PROTOTYPE_SOURCE_ROOT / "editable_extra_esto_key_pairs.csv"
    ),
    "extra_esto_extended_pairs": (
        PROTOTYPE_SOURCE_ROOT
        / "editable_extra_esto_extended_pairs.csv"
    ),
    "extra_ninth_key_pairs": (
        PROTOTYPE_SOURCE_ROOT / "editable_extra_ninth_key_pairs.csv"
    ),
}


# --- Helpers ----------------------------------------------------------------

def _assert_inputs() -> None:
    """Fail once with every missing prerequisite."""
    required = [
        CANONICAL_MASTER_PATH,
        *AXIS_SOURCE_FILES.values(),
        *PAIR_SOURCE_FILES.values(),
        *COMPILED_SOURCE_FILES.values(),
        *EXTRA_PAIR_SOURCE_FILES.values(),
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing separate-axis prototype inputs:\n- "
            + "\n- ".join(missing)
        )


def _write_csv(frame: pd.DataFrame, filename: str) -> Path:
    """Write one workbook-source CSV."""
    path = OUTPUT_DATA_ROOT / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def _relative_output_path(path: Path) -> str:
    """Return an output path relative to the split-workbook root."""
    return path.resolve().relative_to(OUTPUT_ROOT.resolve()).as_posix()


def _build_axis_sheet(
    axis: pd.DataFrame,
    mapping_name: str,
    source_column: str,
    target_column: str,
    output_source_column: str,
    output_target_column: str,
    include_esto_scope: bool,
) -> pd.DataFrame:
    """Return one minimal, user-editable axis relationship table."""
    columns = [source_column, target_column]
    rename = {
        source_column: output_source_column,
        target_column: output_target_column,
    }
    if include_esto_scope:
        columns.append("comparison_scope")
        rename["comparison_scope"] = "esto_dataset_scope"
    result = (
        axis.loc[axis["mapping_name"].eq(mapping_name), columns]
        .drop_duplicates()
        .rename(columns=rename)
        .sort_values(list(rename.values()), kind="stable")
        .reset_index(drop=True)
    )
    return result


def build_editable_axis_sheets() -> dict[str, pd.DataFrame]:
    """Build every narrow sheet that people are expected to edit."""
    sector_axis = pd.read_csv(AXIS_SOURCE_FILES["sector"])
    fuel_axis = pd.read_csv(AXIS_SOURCE_FILES["fuel"])
    sheets = {
        "leap_sector_to_esto": _build_axis_sheet(
            sector_axis,
            mapping_name="leap_to_esto",
            source_column="source_flow",
            target_column="target_flow",
            output_source_column="leap_sector",
            output_target_column="esto_flow",
            include_esto_scope=True,
        ),
        "leap_fuel_to_esto": _build_axis_sheet(
            fuel_axis,
            mapping_name="leap_to_esto",
            source_column="source_product",
            target_column="target_product",
            output_source_column="leap_fuel",
            output_target_column="esto_product",
            include_esto_scope=True,
        ),
        "leap_sector_to_ninth": _build_axis_sheet(
            sector_axis,
            mapping_name="leap_to_ninth",
            source_column="source_flow",
            target_column="target_flow",
            output_source_column="leap_sector",
            output_target_column="ninth_sector",
            include_esto_scope=False,
        ),
        "leap_fuel_to_ninth": _build_axis_sheet(
            fuel_axis,
            mapping_name="leap_to_ninth",
            source_column="source_product",
            target_column="target_product",
            output_source_column="leap_fuel",
            output_target_column="ninth_fuel",
            include_esto_scope=False,
        ),
        "ninth_sector_to_esto": _build_axis_sheet(
            sector_axis,
            mapping_name="ninth_to_esto",
            source_column="source_flow",
            target_column="target_flow",
            output_source_column="ninth_sector",
            output_target_column="esto_flow",
            include_esto_scope=True,
        ),
        "ninth_fuel_to_esto": _build_axis_sheet(
            fuel_axis,
            mapping_name="ninth_to_esto",
            source_column="source_product",
            target_column="target_product",
            output_source_column="ninth_fuel",
            output_target_column="esto_product",
            include_esto_scope=True,
        ),
    }
    for sheet_name, source_path in EXTRA_PAIR_SOURCE_FILES.items():
        sheets[sheet_name] = pd.read_csv(source_path)
    return sheets


def _build_cartesian_registry(
    exact_pairs: pd.DataFrame,
    flow_name: str,
    product_name: str,
    active_column: str,
    active_output_name: str,
    active_status: str,
) -> pd.DataFrame:
    """Label every discovered flow/product combination with source evidence."""
    flows = (
        exact_pairs[["flow"]]
        .drop_duplicates()
        .sort_values("flow", kind="stable")
    )
    products = (
        exact_pairs[["product"]]
        .drop_duplicates()
        .sort_values("product", kind="stable")
    )
    cartesian = flows.merge(products, how="cross")
    evidence_columns = [
        "flow",
        "product",
        "pair_is_subtotal",
        active_column,
        "pair_origin",
    ]
    if "pair_exists_in_dataset" in exact_pairs.columns:
        evidence_columns.append("pair_exists_in_dataset")
    evidence = (
        exact_pairs[evidence_columns]
        .drop_duplicates(["flow", "product"])
        .copy()
    )
    if "pair_exists_in_dataset" in evidence.columns:
        evidence["exists_in_dataset"] = (
            evidence.pop("pair_exists_in_dataset")
            .fillna(False)
            .astype(bool)
        )
    else:
        evidence["exists_in_dataset"] = True
    result = cartesian.merge(
        evidence,
        on=["flow", "product"],
        how="left",
        validate="one_to_one",
    )
    result["exists_in_dataset"] = (
        result["exists_in_dataset"].fillna(False).astype(bool)
    )
    result[active_column] = (
        result[active_column].fillna(False).astype(bool)
    )
    result["pair_is_subtotal"] = (
        result["pair_is_subtotal"].fillna(False).astype(bool)
    )
    reviewed_extra = (
        result["pair_origin"].fillna("").astype(str).eq("reviewed_extra")
    )
    result["eligible_for_compilation"] = (
        result[active_column] | reviewed_extra
    )
    result["registry_status"] = "possible_combination_not_observed"
    result.loc[
        result["exists_in_dataset"],
        "registry_status",
    ] = "exists_but_not_active_at_required_boundary"
    result.loc[
        result[active_column],
        "registry_status",
    ] = active_status
    result.loc[
        reviewed_extra,
        "registry_status",
    ] = "reviewed_extra_pair"
    result = result.rename(
        columns={
            "flow": flow_name,
            "product": product_name,
            active_column: active_output_name,
        }
    )
    return result[
        [
            flow_name,
            product_name,
            "pair_origin",
            "exists_in_dataset",
            active_output_name,
            "eligible_for_compilation",
            "pair_is_subtotal",
            "registry_status",
        ]
    ].sort_values(
        [flow_name, product_name],
        kind="stable",
    ).reset_index(drop=True)


def build_generated_pair_sheets() -> dict[str, pd.DataFrame]:
    """Build narrow generated key-pair registries for each dataset."""
    leap = pd.read_csv(PAIR_SOURCE_FILES["LEAP key pairs"])
    leap_result = (
        leap[
            [
                "flow",
                "product",
                "pair_exists_in_dataset",
                "pair_is_subtotal",
                "temporal_evidence_status",
                "pair_origin",
            ]
        ]
        .drop_duplicates(["flow", "product"])
        .rename(
            columns={
                "flow": "leap_sector",
                "product": "leap_fuel",
                "pair_exists_in_dataset": "exists_in_dataset",
                "temporal_evidence_status": "registry_status",
            }
        )
        .sort_values(["leap_sector", "leap_fuel"], kind="stable")
        .reset_index(drop=True)
    )
    leap_result["eligible_for_compilation"] = (
        leap_result["exists_in_dataset"].fillna(False).astype(bool)
        | leap_result["pair_origin"]
        .fillna("")
        .astype(str)
        .eq("reviewed_extra")
    )
    leap_result = leap_result[
        [
            "leap_sector",
            "leap_fuel",
            "pair_origin",
            "exists_in_dataset",
            "eligible_for_compilation",
            "pair_is_subtotal",
            "registry_status",
        ]
    ]

    esto = pd.read_csv(PAIR_SOURCE_FILES["ESTO key pairs"])
    esto_extended = pd.read_csv(
        PAIR_SOURCE_FILES["ESTO Extended key pairs"]
    )
    ninth = pd.read_csv(PAIR_SOURCE_FILES["Ninth key pairs"])
    return {
        "LEAP key pairs": leap_result,
        "ESTO key pairs": _build_cartesian_registry(
            esto,
            flow_name="esto_flow",
            product_name="esto_product",
            active_column="historical_boundary_active",
            active_output_name="active_in_final_esto_year",
            active_status="historical_boundary_active",
        ),
        "ESTO Extended key pairs": _build_cartesian_registry(
            esto_extended,
            flow_name="esto_flow",
            product_name="esto_product",
            active_column="historical_boundary_active",
            active_output_name="active_in_final_esto_year",
            active_status="historical_boundary_active",
        ),
        "Ninth key pairs": _build_cartesian_registry(
            ninth,
            flow_name="ninth_sector",
            product_name="ninth_fuel",
            active_column="projection_future_active",
            active_output_name="active_after_final_esto_year",
            active_status="projection_future_active",
        ),
    }


def prepare_split_workbook_sources() -> dict[str, object]:
    """Write all narrow source tables and a workbook-build manifest."""
    _assert_inputs()
    OUTPUT_DATA_ROOT.mkdir(parents=True, exist_ok=True)

    editable_sources: dict[str, str] = {}
    editable_counts: dict[str, int] = {}
    for sheet_name, frame in build_editable_axis_sheets().items():
        path = _write_csv(frame, f"editable_{sheet_name}.csv")
        editable_sources[sheet_name] = _relative_output_path(path)
        editable_counts[sheet_name] = len(frame)

    pair_sources: dict[str, str] = {}
    pair_counts: dict[str, int] = {}
    for sheet_name, frame in build_generated_pair_sheets().items():
        filename = (
            "generated_"
            + sheet_name.lower().replace(" ", "_")
            + ".csv"
        )
        path = _write_csv(frame, filename)
        pair_sources[sheet_name] = _relative_output_path(path)
        pair_counts[sheet_name] = len(frame)

    compiled_sources: dict[str, str] = {}
    compiled_counts: dict[str, int] = {}
    compiled_columns: dict[str, list[str]] = {}
    for sheet_name, source_path in COMPILED_SOURCE_FILES.items():
        frame = pd.read_csv(source_path)
        path = _write_csv(frame, f"compiled_{sheet_name}.csv")
        compiled_sources[sheet_name] = _relative_output_path(path)
        compiled_counts[sheet_name] = len(frame)
        compiled_columns[sheet_name] = list(frame.columns)

    manifest: dict[str, object] = {
        "prototype_status": (
            "Production contract with explicit semantic review debt."
        ),
        "historical_boundary_year": HISTORICAL_BOUNDARY_YEAR,
        "canonical_master_path": str(CANONICAL_MASTER_PATH),
        "editable_axis_workbook_path": str(EDITABLE_AXIS_WORKBOOK_PATH),
        "generated_pair_workbook_path": str(
            GENERATED_PAIR_WORKBOOK_PATH
        ),
        "generated_master_workbook_path": str(
            GENERATED_MASTER_WORKBOOK_PATH
        ),
        "editable_sources": editable_sources,
        "editable_counts": editable_counts,
        "pair_sources": pair_sources,
        "pair_counts": pair_counts,
        "compiled_sources": compiled_sources,
        "compiled_counts": compiled_counts,
        "compiled_columns": compiled_columns,
        "leap_registry_authority": (
            "Layered authority generated from direct model-branch pairs and "
            "the deterministic LEAP balance-report grid. Report flows come "
            "from all current economy templates plus detailed demand/power "
            "rows; the 70 balance products come from the template fuel "
            "catalogue. Active canonical rollup rules then add deterministic "
            "rolled pairs. Source fingerprints control automatic refresh."
        ),
        "generated_master_contract": (
            "Copy every canonical sheet unchanged, then replace only the "
            "three pair-sheet data bodies while preserving their headers."
        ),
    }
    manifest_path = OUTPUT_ROOT / "split_workbook_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return manifest


# --- Frequently changed run flag -------------------------------------------

PREPARE_SPLIT_WORKBOOK_SOURCES = False


#%%
if __name__ == "__main__" and PREPARE_SPLIT_WORKBOOK_SOURCES:
    try:
        SPLIT_WORKBOOK_MANIFEST = prepare_split_workbook_sources()
        print(
            json.dumps(
                SPLIT_WORKBOOK_MANIFEST,
                indent=2,
            )
        )
    except Exception as error:
        print("Failed to prepare split-workbook source tables.")
        print(f"{type(error).__name__}: {error}")
        traceback.print_exc()
        raise


#%%
