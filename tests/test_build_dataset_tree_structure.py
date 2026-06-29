#%%
"""Focused tests for exact-context Stage A source validation."""

#%%
from pathlib import Path

import pandas as pd

from codebase.mapping_tools.build_dataset_tree_structure import (
    _build_source_inconsistency_lookup,
    validate_common_esto_recursive_sums,
    validate_leap_recursive_sums,
    validate_ninth_recursive_sums,
)


#%%
def _write_mapping_workbook(
    path: Path,
    ninth_rows: list[dict] | None = None,
    leap_rows: list[dict] | None = None,
) -> None:
    """Write the two mapping sheets required by Stage A tests."""
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(ninth_rows or [], columns=[
            "9th_sector", "9th_fuel", "esto_flow", "esto_product",
        ]).to_excel(writer, sheet_name="ninth_pairs_to_esto_pairs", index=False)
        pd.DataFrame(leap_rows or [], columns=[
            "leap_sector_name_full_path", "raw_leap_fuel_name",
            "esto_flow", "esto_product",
        ]).to_excel(writer, sheet_name="leap_combined_esto", index=False)


def _ninth_row(
    scenario: str,
    sector: str,
    fuel: str,
    subfuel: str,
    subtotal_layout: bool,
    subtotal_results: bool,
    value_2022: float,
    value_2023: float,
) -> dict:
    """Return one compact Ninth hierarchy fixture row."""
    return {
        "scenarios": scenario,
        "economy": "20_USA",
        "sectors": sector,
        "sub1sectors": "x",
        "sub2sectors": "x",
        "sub3sectors": "x",
        "sub4sectors": "x",
        "fuels": fuel,
        "subfuels": subfuel,
        "subtotal_layout": subtotal_layout,
        "subtotal_results": subtotal_results,
        "2022": value_2022,
        "2023": value_2023,
    }


#%%
def test_ninth_validation_is_projection_only_and_preserves_exact_context(tmp_path: Path) -> None:
    """Projection validation uses subtotal_results and retains sector/scenario context."""
    data_path = tmp_path / "ninth.csv"
    workbook_path = tmp_path / "mappings.xlsx"
    rows = [
        _ninth_row("reference", "12_total_final_consumption", "16_others", "x", False, True, 20, 10),
        _ninth_row("reference", "12_total_final_consumption", "16_others", "16_01_biogas", False, False, 8, 3),
        _ninth_row("reference", "12_total_final_consumption", "16_others", "16_02_waste", False, False, 7, 2),
        # Historical-only subtotal metadata must not create a projected check.
        _ninth_row("reference", "13_total_final_energy_consumption", "16_others", "x", True, False, 20, 10),
        _ninth_row("reference", "13_total_final_energy_consumption", "16_others", "16_01_biogas", False, False, 8, 1),
        # Target is outside the production conversion boundary.
        _ninth_row("target", "12_total_final_consumption", "16_others", "x", False, True, 20, 100),
        _ninth_row("target", "12_total_final_consumption", "16_others", "16_01_biogas", False, False, 8, 0),
    ]
    pd.DataFrame(rows).to_csv(data_path, index=False)
    _write_mapping_workbook(
        workbook_path,
        ninth_rows=[
            {"9th_sector": "12_total_final_consumption", "9th_fuel": "16_others", "esto_flow": "12 Total final consumption", "esto_product": "16 Others"},
            {"9th_sector": "12_total_final_consumption", "9th_fuel": "16_01_biogas", "esto_flow": "12 Total final consumption", "esto_product": "16.01 Biogas"},
            {"9th_sector": "12_total_final_consumption", "9th_fuel": "16_02_waste", "esto_flow": "12 Total final consumption", "esto_product": "16.02 Industrial waste"},
        ],
    )

    result = validate_ninth_recursive_sums(
        data_csv_path=data_path,
        workbook_path=workbook_path,
        leap_var_base_year=2022,
    )

    assert len(result) == 1
    row = result.iloc[0]
    assert row["year"] == "2023"
    assert row["scenario"] == "reference"
    assert row["ninth_sector"] == "12_total_final_consumption"
    assert row["esto_parent_flow"] == "12 Total final consumption"
    assert row["source_issue_class"] == "sum_mismatch"
    assert bool(row["inheritance_eligible"])


def test_ninth_ambiguous_parent_mapping_is_not_confirmed(tmp_path: Path) -> None:
    """Multiple parent targets remain visible and cannot become inherited truth."""
    data_path = tmp_path / "ninth.csv"
    workbook_path = tmp_path / "mappings.xlsx"
    pd.DataFrame([
        _ninth_row("reference", "12_total_final_consumption", "16_others", "x", False, True, 0, 10),
        _ninth_row("reference", "12_total_final_consumption", "16_others", "16_01_biogas", False, False, 0, 2),
    ]).to_csv(data_path, index=False)
    _write_mapping_workbook(
        workbook_path,
        ninth_rows=[
            {"9th_sector": "12_total_final_consumption", "9th_fuel": "16_others", "esto_flow": "12 Total final consumption", "esto_product": "16 Others"},
            {"9th_sector": "12_total_final_consumption", "9th_fuel": "16_others", "esto_flow": "13 Total final energy consumption", "esto_product": "16 Others"},
            {"9th_sector": "12_total_final_consumption", "9th_fuel": "16_01_biogas", "esto_flow": "12 Total final consumption", "esto_product": "16.01 Biogas"},
        ],
    )

    result = validate_ninth_recursive_sums(data_path, workbook_path)

    assert len(result) == 1
    assert result.iloc[0]["mapping_status"] == "ambiguous_parent_mapping"
    assert not bool(result.iloc[0]["inheritance_eligible"])


#%%
def test_leap_validation_excludes_base_year_and_uses_full_paths(tmp_path: Path) -> None:
    """LEAP checks preserve product/path context and exclude years through base year."""
    data_path = tmp_path / "leap.csv"
    esto_path = tmp_path / "esto.csv"
    workbook_path = tmp_path / "mappings.xlsx"
    pd.DataFrame([
        {"economy": "20_USA", "scenario": "Reference", "year": 2022, "leap_flow": "Parent", "leap_product": "Fuel", "value": 10},
        {"economy": "20_USA", "scenario": "Reference", "year": 2022, "leap_flow": "Parent/Child A", "leap_product": "Fuel", "value": 1},
        {"economy": "20_USA", "scenario": "Reference", "year": 2022, "leap_flow": "Parent/Child B", "leap_product": "Fuel", "value": 1},
        {"economy": "20_USA", "scenario": "Reference", "year": 2023, "leap_flow": "Parent", "leap_product": "Fuel", "value": 10},
        {"economy": "20_USA", "scenario": "Reference", "year": 2023, "leap_flow": "Parent/Child A", "leap_product": "Fuel", "value": 2},
        {"economy": "20_USA", "scenario": "Reference", "year": 2023, "leap_flow": "Parent/Child B", "leap_product": "Fuel", "value": 3},
    ]).to_csv(data_path, index=False)
    pd.DataFrame({"flows": ["09 Parent", "09.01 Child A", "09.02 Child B"]}).to_csv(esto_path, index=False)
    _write_mapping_workbook(
        workbook_path,
        leap_rows=[
            {"leap_sector_name_full_path": "Parent", "raw_leap_fuel_name": "Fuel", "esto_flow": "09 Parent", "esto_product": "01 Fuel"},
            {"leap_sector_name_full_path": "Parent/Child A", "raw_leap_fuel_name": "Fuel", "esto_flow": "09.01 Child A", "esto_product": "01 Fuel"},
            {"leap_sector_name_full_path": "Parent/Child B", "raw_leap_fuel_name": "Fuel", "esto_flow": "09.02 Child B", "esto_product": "01 Fuel"},
        ],
    )

    result = validate_leap_recursive_sums(
        leap_data_paths=[data_path],
        workbook_path=workbook_path,
        esto_data_path=esto_path,
        leap_var_base_year=2022,
    )

    assert len(result) == 1
    row = result.iloc[0]
    assert row["year"] == "2023"
    assert row["parent_leap_sector_path"] == "Parent"
    assert row["leap_product"] == "Fuel"
    assert row["source_context_status"] == "full_path"
    assert bool(row["inheritance_eligible"])


def test_source_lookup_requires_scenario_and_opposite_axis_match() -> None:
    """A source finding cannot leak into another scenario or flow/product context."""
    ninth = pd.DataFrame([{
        "source_issue_id": "ninth-1",
        "source_system": "NINTH",
        "economy": "20_USA",
        "scenario": "reference",
        "year": "2030",
        "esto_parent_flow": "12 Total final consumption",
        "esto_parent_product": "16 Others",
        "source_issue_class": "sum_mismatch",
        "inheritance_eligible": True,
    }])
    lookup = _build_source_inconsistency_lookup(
        ninth,
        pd.DataFrame(columns=LEAP_LOOKUP_COLUMNS),
    )

    exact_key = (
        "ninth", "20_USA", "reference", "2030", "product",
        "16 Others", "12 Total final consumption",
    )
    target_key = (
        "ninth", "20_USA", "target", "2030", "product",
        "16 Others", "12 Total final consumption",
    )
    other_flow_key = (
        "ninth", "20_USA", "reference", "2030", "product",
        "16 Others", "13 Total final energy consumption",
    )
    assert lookup[exact_key]["status"] == "confirmed_inherited"
    assert target_key not in lookup
    assert other_flow_key not in lookup


def test_common_validation_excludes_base_year_and_uses_exact_source_key(tmp_path: Path) -> None:
    """Stage B applies the projection boundary and exact inherited-source key."""
    comparison_path = tmp_path / "comparison.csv"
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "16 Others", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "16.01 Biogas", "parent_code": "16 Others"},
        {"dataset": "common_esto", "axis": "product", "code": "16 Others", "parent_code": ""},
        {"dataset": "common_esto", "axis": "product", "code": "16.01 Biogas", "parent_code": "16 Others"},
    ])
    rows = []
    for year in [2022, 2023]:
        rows.extend([
            {"comparison_scope": "scope", "source_system": "NINTH", "economy": "20_USA", "scenario": "reference", "year": year, "common_flow_label": "12 Total final consumption", "common_product_label": "16 Others", "value": 10},
            {"comparison_scope": "scope", "source_system": "NINTH", "economy": "20_USA", "scenario": "reference", "year": year, "common_flow_label": "12 Total final consumption", "common_product_label": "16.01 Biogas", "value": 5},
        ])
    pd.DataFrame(rows).to_csv(comparison_path, index=False)
    lookup = {
        (
            "ninth", "20_USA", "reference", "2023", "product",
            "16 Others", "12 Total final consumption",
        ): {"status": "confirmed_inherited", "source_issue_ids": "ninth-1"},
    }

    result = validate_common_esto_recursive_sums(
        tree,
        comparison_path,
        source_inconsistencies=lookup,
        leap_var_base_year=2022,
    )

    assert result["year"].tolist() == ["2023"]
    assert result.iloc[0]["source_inconsistency_status"] == "confirmed_inherited"
    assert bool(result.iloc[0]["inherited_source_inconsistency"])


# Minimal columns used by the lookup for an empty LEAP frame.
LEAP_LOOKUP_COLUMNS = [
    "source_issue_id", "source_system", "economy", "scenario", "year",
    "esto_parent_flow", "esto_parent_product", "source_issue_class",
    "inheritance_eligible",
]

#%%
