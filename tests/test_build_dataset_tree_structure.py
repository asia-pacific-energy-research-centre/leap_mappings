#%%
"""Focused tests for exact-context Stage A source validation."""

#%%
from pathlib import Path

import pandas as pd

from codebase.mapping_tools.build_dataset_tree_structure import (
    OUTLOOK_MAPPINGS_PATH,
    _build_esto_axis_tree,
    _build_source_inconsistency_lookup,
    build_common_esto_tree,
    _load_rollup_hierarchy,
    validate_common_esto_recursive_sums,
    validate_leap_recursive_sums,
    validate_ninth_recursive_sums,
    validate_ninth_sector_recursive_sums,
)
from codebase.mapping_tools.structural_resolver import build_tree_index


#%%
def _write_mapping_workbook(
    path: Path,
    ninth_rows: list[dict] | None = None,
    leap_rows: list[dict] | None = None,
) -> None:
    """Write the two mapping sheets required by Stage A tests."""
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(ninth_rows or [], columns=[
            "ninth_sector", "ninth_fuel", "esto_flow", "esto_product",
        ]).to_excel(writer, sheet_name="ninth_pairs_to_esto_pairs", index=False)
        pd.DataFrame(leap_rows or [], columns=[
            "leap_sector_name_full_path", "raw_leap_fuel_name",
            "esto_flow", "esto_product",
        ]).to_excel(writer, sheet_name="leap_combined_esto", index=False)


def test_esto_axis_tree_splices_synthetic_rollup_node() -> None:
    """Declared rollup labels become real tree nodes and take their children."""
    tree = _build_esto_axis_tree(
        codes=[
            "16 Other sector",
            "16.01 Commercial and public services",
            "16.02 Residential",
            "16.03 Agriculture",
        ],
        axis="flow",
        dataset="esto",
        subtotal_codes={"16 Other sector"},
        synthetic_nodes={
            "16.01-16.02 Buildings": {
                "parent_label": "16 Other sector",
                "children": [
                    "16.01 Commercial and public services",
                    "16.02 Residential",
                ],
            }
        },
    )

    parent_by_code = tree.set_index("code")["parent_code"].to_dict()
    assert parent_by_code["16.01-16.02 Buildings"] == "16 Other sector"
    assert parent_by_code["16.01 Commercial and public services"] == "16.01-16.02 Buildings"
    assert parent_by_code["16.02 Residential"] == "16.01-16.02 Buildings"
    assert parent_by_code["16.03 Agriculture"] == "16 Other sector"
    assert bool(tree.set_index("code").loc["16.01-16.02 Buildings", "is_subtotal"])


def test_common_esto_subtotal_status_uses_the_new_tree_not_esto_prefixes(tmp_path: Path) -> None:
    """A graph-generated Common ESTO leaf is not a subtotal by source-code shape."""
    common_rows_path = tmp_path / "common_esto_rows.csv"
    pd.DataFrame({
        "common_flow_label": [
            "16 Other sector",
            "16.01 Commercial and public services",
            "09.01.01,09.02.01 Electricity plants",
        ],
        "common_product_label": ["01.01 Product", "01.01 Product", "01.01 Product"],
    }).to_csv(common_rows_path, index=False)

    tree = build_common_esto_tree(common_rows_path, tmp_path / "missing_workbook.xlsx")
    flows = tree[tree["axis"].eq("flow")].set_index("code")

    assert "is_leaf" not in tree.columns
    assert not bool(flows.loc["09.01.01,09.02.01 Electricity plants", "is_subtotal"])
    assert bool(flows.loc["16 Other sector", "is_subtotal"])


def test_load_rollup_hierarchy_keeps_declared_parent_and_children(tmp_path: Path) -> None:
    """The workbook loader keeps declared and standalone rollup boundaries."""
    workbook_path = tmp_path / "mappings.xlsx"
    pd.DataFrame([
        {
            "include": True,
            "rolled_esto_flow": "16.01-16.02 Buildings",
            "parent_flow_label": "16 Other sector",
            "child_flow_labels": "16.01 Commercial and public services; 16.02 Residential",
        },
        {
            "include": True,
            "rolled_esto_flow": "16.01-16.02 Buildings",
            "parent_flow_label": "ignored duplicate",
            "child_flow_labels": "ignored duplicate",
        },
        {
            "include": True,
            "rolled_esto_flow": "Blank hierarchy",
            "parent_flow_label": "",
            "child_flow_labels": "10.01.11 Oil refineries",
        },
    ]).to_excel(workbook_path, sheet_name="esto_rollup_rules", index=False)

    hierarchy = _load_rollup_hierarchy(workbook_path)

    assert list(hierarchy) == ["16.01-16.02 Buildings", "Blank hierarchy"]
    assert hierarchy["16.01-16.02 Buildings"] == {
        "parent_label": "16 Other sector",
        "children": ["16.01 Commercial and public services", "16.02 Residential"],
    }
    assert hierarchy["Blank hierarchy"] == {
        "parent_label": "",
        "children": ["10.01.11 Oil refineries"],
    }


def test_standalone_rollup_label_does_not_become_numeric_tree_child() -> None:
    """A standalone inclusive row is not a second child of its base parent."""
    hierarchy = {
        "09.07 Oil refineries (including own use)": {
            "parent_label": "",
            "children": ["10.01.11 Oil refineries"],
        },
    }
    tree = _build_esto_axis_tree(
        [
            "09 Total transformation sector",
            "09.07 Oil refineries",
            "09.07 Oil refineries (including own use)",
            "10.01.11 Oil refineries",
        ],
        "flow",
        "common_esto",
        set(),
        hierarchy,
    )
    flows = tree[tree["axis"].eq("flow")].set_index("code")

    assert flows.loc["09.07 Oil refineries", "parent_code"] == "09 Total transformation sector"
    assert flows.loc["09.07 Oil refineries (including own use)", "parent_code"] == ""
    assert flows.loc["10.01.11 Oil refineries", "parent_code"] == "09.07 Oil refineries (including own use)"


def test_in_scope_real_rollup_hierarchy_has_no_tree_index_issues() -> None:
    """The three demand/power rollup nodes should stay structurally unambiguous."""
    in_scope = {
        "16.01-16.02 Buildings",
        "16.03-16.04 Agriculture and fishing",
        "09.01-09.02 Power sector",
    }
    hierarchy = {
        key: value
        for key, value in _load_rollup_hierarchy(OUTLOOK_MAPPINGS_PATH).items()
        if key in in_scope
    }
    codes = _dedupe_for_test([
        "09 Total transformation sector",
        "09.01 Main activity producer",
        "09.02 Autoproducers",
        "16 Other sector",
        "16.01 Commercial and public services",
        "16.02 Residential",
        "16.03 Agriculture",
        "16.04 Fishing",
        *hierarchy.keys(),
    ])
    tree = _build_esto_axis_tree(codes, "flow", "esto", set(), hierarchy)

    _, issues = build_tree_index(tree, "esto", "flow")

    assert set(hierarchy) == in_scope
    assert issues.empty


def _dedupe_for_test(values: list[str]) -> list[str]:
    """Small local helper to keep the real-workbook fixture readable."""
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


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
            {"ninth_sector": "12_total_final_consumption", "ninth_fuel": "16_others", "esto_flow": "12 Total final consumption", "esto_product": "16 Others"},
            {"ninth_sector": "12_total_final_consumption", "ninth_fuel": "16_01_biogas", "esto_flow": "12 Total final consumption", "esto_product": "16.01 Biogas"},
            {"ninth_sector": "12_total_final_consumption", "ninth_fuel": "16_02_waste", "esto_flow": "12 Total final consumption", "esto_product": "16.02 Industrial waste"},
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
            {"ninth_sector": "12_total_final_consumption", "ninth_fuel": "16_others", "esto_flow": "12 Total final consumption", "esto_product": "16 Others"},
            {"ninth_sector": "12_total_final_consumption", "ninth_fuel": "16_others", "esto_flow": "13 Total final energy consumption", "esto_product": "16 Others"},
            {"ninth_sector": "12_total_final_consumption", "ninth_fuel": "16_01_biogas", "esto_flow": "12 Total final consumption", "esto_product": "16.01 Biogas"},
        ],
    )

    result = validate_ninth_recursive_sums(data_path, workbook_path)

    assert len(result) == 1
    assert result.iloc[0]["mapping_status"] == "ambiguous_parent_mapping"
    assert not bool(result.iloc[0]["inheritance_eligible"])


def test_ninth_sector_validation_uses_mapped_direct_child_frontier(tmp_path: Path) -> None:
    """Do not add sub3 detail to a mapped sub2 subtotal a second time."""
    workbook_path = tmp_path / "mappings.xlsx"
    common_rows_path = tmp_path / "common_rows.csv"
    rows = [
        {
            "scenarios": "reference", "economy": "20_USA",
            "sectors": "14_industry_sector", "sub1sectors": "14_03_manufacturing",
            "sub2sectors": "x", "sub3sectors": "x", "sub4sectors": "x",
            "fuels": "01_coal", "subfuels": "01_x_thermal_coal",
            "subtotal_results": True, "2023": 100.0,
        },
        {
            "scenarios": "reference", "economy": "20_USA",
            "sectors": "14_industry_sector", "sub1sectors": "14_03_manufacturing",
            "sub2sectors": "14_03_01_iron_and_steel", "sub3sectors": "x", "sub4sectors": "x",
            "fuels": "01_coal", "subfuels": "01_x_thermal_coal",
            "subtotal_results": False, "2023": 95.0,
        },
        {
            "scenarios": "reference", "economy": "20_USA",
            "sectors": "14_industry_sector", "sub1sectors": "14_03_manufacturing",
            "sub2sectors": "14_03_02_chemical_incl_petrochemical", "sub3sectors": "01_fs", "sub4sectors": "x",
            "fuels": "01_coal", "subfuels": "01_x_thermal_coal",
            "subtotal_results": False, "2023": 5.0,
        },
        {
            "scenarios": "reference", "economy": "20_USA",
            "sectors": "14_industry_sector", "sub1sectors": "14_03_manufacturing",
            "sub2sectors": "14_03_02_chemical_incl_petrochemical", "sub3sectors": "02_ccs", "sub4sectors": "x",
            "fuels": "01_coal", "subfuels": "01_x_thermal_coal",
            "subtotal_results": False, "2023": 0.0,
        },
        {
            "scenarios": "reference", "economy": "20_USA",
            "sectors": "14_industry_sector", "sub1sectors": "14_03_manufacturing",
            "sub2sectors": "14_03_02_chemical_incl_petrochemical", "sub3sectors": "x", "sub4sectors": "x",
            "fuels": "01_coal", "subfuels": "01_x_thermal_coal",
            "subtotal_results": True, "2023": 5.0,
        },
    ]
    pd.DataFrame(rows).to_csv(tmp_path / "ninth.csv", index=False)
    _write_mapping_workbook(
        workbook_path,
        ninth_rows=[
            {"ninth_sector": "14_03_manufacturing", "ninth_fuel": "01_x_thermal_coal", "esto_flow": "14.03 Manufacturing", "esto_product": "01.02 Other bituminous coal"},
            {"ninth_sector": "14_03_01_iron_and_steel", "ninth_fuel": "01_x_thermal_coal", "esto_flow": "14.03.01 Iron and steel", "esto_product": "01.02 Other bituminous coal"},
            {"ninth_sector": "14_03_02_chemical_incl_petrochemical", "ninth_fuel": "01_x_thermal_coal", "esto_flow": "14.03.02 Chemical", "esto_product": "01.02 Other bituminous coal"},
        ],
    )
    pd.DataFrame([
        {"comparison_scope": "esto_leap_ninth", "common_flow_label": "14.03 Manufacturing", "component_esto_product": "01.02 Other bituminous coal", "common_product_label": "01.02 Other bituminous coal"},
    ]).to_csv(common_rows_path, index=False)

    result = validate_ninth_sector_recursive_sums(
        data_csv_path=tmp_path / "ninth.csv",
        workbook_path=workbook_path,
        common_rows_path=common_rows_path,
        leap_var_base_year=2022,
    )

    assert result.empty


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


def test_common_flow_validation_expands_zero_base_rollup_placeholder(tmp_path: Path) -> None:
    """A zero base label must not hide a nonzero detailed rollup input."""
    comparison_path = tmp_path / "comparison.csv"
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "flow", "code": "09 Total transformation sector", "parent_code": ""},
        {"dataset": "esto", "axis": "flow", "code": "09.06 Gas processing plants", "parent_code": "09 Total transformation sector"},
        {"dataset": "esto", "axis": "flow", "code": "09.06.02 Liquefaction/regasification plants", "parent_code": "09.06 Gas processing plants"},
        {"dataset": "common_esto", "axis": "flow", "code": "09 Total transformation sector", "parent_code": ""},
        {"dataset": "common_esto", "axis": "flow", "code": "09.06 Gas processing plants", "parent_code": "09 Total transformation sector"},
        {"dataset": "common_esto", "axis": "flow", "code": "09.06.02 Liquefaction/regasification plants", "parent_code": "09.06 Gas processing plants (including own use)"},
        {"dataset": "common_esto", "axis": "flow", "code": "09.06 Gas processing plants (including own use)", "parent_code": ""},
    ])
    pd.DataFrame([
        {"comparison_scope": "scope", "source_system": "NINTH", "economy": "20_USA", "scenario": "target", "year": 2023, "common_flow_label": "09 Total transformation sector", "common_product_label": "08.01 Natural gas", "value": 100},
            {"comparison_scope": "scope", "source_system": "NINTH", "economy": "20_USA", "scenario": "target", "year": 2023, "common_flow_label": "09.06 Gas processing plants", "common_product_label": "08.01 Natural gas", "value": 0},
            {"comparison_scope": "scope", "source_system": "NINTH", "economy": "20_USA", "scenario": "target", "year": 2023, "common_flow_label": "09.06.02 Liquefaction/regasification plants", "common_product_label": "08.01 Natural gas", "value": 100},
            {"comparison_scope": "scope", "source_system": "NINTH", "economy": "20_USA", "scenario": "target", "year": 2023, "common_flow_label": "09.06 Gas processing plants (including own use)", "common_product_label": "08.01 Natural gas", "value": 0},
        ]).to_csv(comparison_path, index=False)

    result = validate_common_esto_recursive_sums(
        tree,
        comparison_path,
        leap_var_base_year=2022,
    )

    total_check = result[result["parent_code"] == "09 Total transformation sector"]
    assert total_check.empty


# Minimal columns used by the lookup for an empty LEAP frame.
LEAP_LOOKUP_COLUMNS = [
    "source_issue_id", "source_system", "economy", "scenario", "year",
    "esto_parent_flow", "esto_parent_product", "source_issue_class",
    "inheritance_eligible",
]

#%%
