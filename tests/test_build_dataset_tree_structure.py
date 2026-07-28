#%%
"""Focused tests for exact-context Stage A source validation."""

#%%
import io
from pathlib import Path

import pandas as pd

from codebase.mapping_tools.build_dataset_tree_structure import (
    OUTLOOK_MAPPINGS_PATH,
    _build_esto_axis_tree,
    _build_source_inconsistency_lookup,
    _resolve_to_comparison_data,
    build_common_esto_tree,
    build_esto_tree,
    build_ninth_tree,
    build_ninth_subtotal_esto_flow_labels,
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


def test_ninth_structural_parenthood_does_not_depend_on_subtotal_results() -> None:
    """Declared 09.06/09.08 parents remain subtotals when value flags are false."""
    rows = []
    for parent, child in [
        ("09_06_gas_processing_plants", "09_06_01_gas_processing"),
        ("09_08_coal_transformation", "09_08_01_coke_ovens"),
    ]:
        rows.append({
            "sectors": parent,
            "sub1sectors": child,
            "sub2sectors": "x",
            "sub3sectors": "x",
            "sub4sectors": "x",
            "fuels": "08_gas",
            "subfuels": "x",
            "subtotal_layout": False,
            "subtotal_results": False,
        })

    tree = build_ninth_tree(data_df=pd.DataFrame(rows))
    sectors = tree[tree["axis"].eq("sector")].set_index("code")

    for parent in ["09_06_gas_processing_plants", "09_08_coal_transformation"]:
        assert bool(sectors.loc[parent, "is_subtotal"])


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


def test_esto_axis_tree_attaches_descendants_to_composite_rollup_parent() -> None:
    """Composite rollups attach declared member-parent descendants."""
    tree = _build_esto_axis_tree(
        codes=[
            "09.01-09.02 Power sector",
            "09.01.02,09.02.02 CHP plants",
            "09.01.02.01 Coal CHP",
            "09.02.02.01 Coal CHP",
        ],
        axis="flow",
        dataset="common_esto",
        subtotal_codes=set(),
        synthetic_nodes={
            "09.01.02,09.02.02 CHP plants": {
                "parent_label": "09.01-09.02 Power sector",
                "children": ["09.01.02 CHP plants", "09.02.02 CHP plants"],
                "rollup_mode": "EXPANDING",
            }
        },
    )

    parent_by_code = tree.set_index("code")["parent_code"].to_dict()
    assert parent_by_code["09.01.02.01 Coal CHP"] == "09.01.02,09.02.02 CHP plants"
    assert parent_by_code["09.02.02.01 Coal CHP"] == "09.01.02,09.02.02 CHP plants"


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
        "rollup_mode": "",
    }
    assert hierarchy["Blank hierarchy"] == {
        "parent_label": "",
        "children": ["10.01.11 Oil refineries"],
        "rollup_mode": "",
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


def test_build_esto_tree_keeps_natural_children_under_an_expanding_rollup_branch(
    tmp_path: Path,
) -> None:
    """The raw ESTO tree ignores esto_rollup_rules entirely.

    ``09.01 Main activity producer`` and ``09.02 Autoproducers`` each keep
    their own genuine raw ESTO children even though an EXPANDING rollup
    ("09.01-09.02 Power sector") also declares a cross-branch merge of their
    plant-type children -- see
    docs/prompts/anchor_validator_fixes_findings_20260722.md for the real-data
    bug this rollup splicing caused (both branches went structurally
    childless, at fixed, unmoved failure counts, before this fix). None of
    esto_rollup_rules' synthetic labels ever appear in ESTO's own raw
    flows/products columns -- ESTO's own identity self-mapping always keys
    on its own literal raw labels -- so the raw tree ignores the rollup
    workbook entirely; build_esto_tree doesn't even take a workbook_path.
    """
    data_path = tmp_path / "esto.csv"
    pd.DataFrame([
        {"economy": "20_USA", "flows": "09 Total transformation sector", "products": "01 Coal", "2022": 100},
        {"economy": "20_USA", "flows": "09.01 Main activity producer", "products": "01 Coal", "2022": 60},
        {"economy": "20_USA", "flows": "09.01.01 Electricity plants", "products": "01 Coal", "2022": 60},
        {"economy": "20_USA", "flows": "09.02 Autoproducers", "products": "01 Coal", "2022": 40},
        {"economy": "20_USA", "flows": "09.02.01 Electricity plants", "products": "01 Coal", "2022": 40},
    ]).to_csv(data_path, index=False)

    tree = build_esto_tree(data_path)
    flows = tree[tree["axis"].eq("flow")].set_index("code")

    assert flows.loc["09.01.01 Electricity plants", "parent_code"] == "09.01 Main activity producer"
    assert flows.loc["09.02.01 Electricity plants", "parent_code"] == "09.02 Autoproducers"
    assert "09.01.01,09.02.01 Electricity plants" not in flows.index
    assert "09.01-09.02 Power sector" not in flows.index


def test_build_esto_tree_keeps_natural_children_under_a_non_expanding_reattribution() -> None:
    """A NON_EXPANDING reattribution must not orphan the raw branch it moves a leaf out of.

    ``10.01 Own Use``'s own raw total is exactly the sum of ALL of its
    original raw-tree children, including ones esto_rollup_rules reattributes
    to flow 09 for Common ESTO comparison purposes (e.g. own-use gas/coal/oil
    plants) -- the reattribution is a comparison-boundary relabel, not a
    redefinition of what "10.01 Own Use" itself measures, so it must keep its
    real children in the raw tree regardless of what esto_rollup_rules
    declares (which the raw tree ignores entirely -- see the EXPANDING test
    above).
    """
    csv_text = (
        "economy,flows,products,2022\n"
        "20_USA,10 Losses & own use,08.01 Natural gas,-400\n"
        "20_USA,10.01 Own Use,08.01 Natural gas,-380\n"
        "20_USA,10.01.02 Gas works plants,08.01 Natural gas,-300\n"
        "20_USA,10.01.12 Oil and gas extraction,08.01 Natural gas,-80\n"
    )
    tree = build_esto_tree(io.StringIO(csv_text))
    flows = tree[tree["axis"].eq("flow")].set_index("code")

    assert flows.loc["10.01.02 Gas works plants", "parent_code"] == "10.01 Own Use"
    assert flows.loc["10.01.12 Oil and gas extraction", "parent_code"] == "10.01 Own Use"


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
        {"dataset": "esto", "axis": "flow", "code": "09.06.02 Liquefaction/regasification plants", "parent_code": "09.06 Gas processing plants (including own use)"},
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


def test_common_flow_validation_resolves_second_level_rollup_leaf_via_inclusive_sibling(tmp_path: Path) -> None:
    """A second-level rollup leaf whose real value lives only under its own
    inclusive sibling label must still be summed into the parent total --
    not silently dropped -- when another sibling child resolves directly.

    Reproduces the real ESTO ``09.06 Gas processing plants`` residual
    exactly: ``09.06.01 Gas works plants`` (a leaf, no further tree children
    of its own) is registered in the tree only as a child of
    ``09.06 Gas processing plants (including own use)`` -- the prefix-based
    edge-restoration in ``_common_esto_validation_children_map`` correctly
    re-parents it under the bare ``09.06 Gas processing plants`` too, but its
    own real value for this comparison scope is only present in the data
    under its *own* inclusive sibling label,
    ``09.06.01 Gas works plants (including own use)``, not the bare leaf
    code. Without falling back to that sibling, this leaf is silently
    dropped (it has no further children map entry, so it isn't a leaf
    "expand into descendants" case), understating children_sum and
    producing a spurious mismatch on the real parent,
    ``09 Total transformation sector``, exactly as seen in production.
    """
    comparison_path = tmp_path / "comparison.csv"
    tree_rows = [
        {"code": "09 Total transformation sector", "parent_code": ""},
        {"code": "09.06 Gas processing plants", "parent_code": "09 Total transformation sector"},
        {"code": "09.01-09.02 Power sector", "parent_code": "09 Total transformation sector"},
        {"code": "09.06 Gas processing plants (including own use)", "parent_code": ""},
        {"code": "09.06.01 Gas works plants", "parent_code": "09.06 Gas processing plants (including own use)"},
        {"code": "09.06.01 Gas works plants (including own use)", "parent_code": "09.06 Gas processing plants (including own use)"},
    ]
    tree = pd.DataFrame(
        [{"dataset": d, "axis": "flow", **row} for d in ("esto", "common_esto") for row in tree_rows]
    )
    pd.DataFrame([
        {"comparison_scope": "esto_leap", "source_system": "ESTO", "economy": "05_PRC", "scenario": "historical", "year": 2023, "common_flow_label": "09 Total transformation sector", "common_product_label": "07.16 Petroleum coke", "value": 860},
        {"comparison_scope": "esto_leap", "source_system": "ESTO", "economy": "05_PRC", "scenario": "historical", "year": 2023, "common_flow_label": "09.01-09.02 Power sector", "common_product_label": "07.16 Petroleum coke", "value": 903},
        {"comparison_scope": "esto_leap", "source_system": "ESTO", "economy": "05_PRC", "scenario": "historical", "year": 2023, "common_flow_label": "09.06.01 Gas works plants (including own use)", "common_product_label": "07.16 Petroleum coke", "value": -43},
    ]).to_csv(comparison_path, index=False)

    result = validate_common_esto_recursive_sums(
        tree,
        comparison_path,
        leap_var_base_year=2022,
        rollup_modes={
            "09.06.01 Gas works plants (including own use)": "NON_EXPANDING",
        },
    )

    # The default (failures-only) view must show no mismatch: the leaf's
    # real value is folded in via its own inclusive sibling, so parent_value
    # (860) equals the true children_sum (903 + -43 = 860).
    total_check = result[result["parent_code"] == "09 Total transformation sector"]
    assert total_check.empty


def test_common_flow_validation_excludes_detached_rollup_leaf_from_ancestor_sum(tmp_path: Path) -> None:
    """A DETACHED rollup's own-use contributors must NOT fold into an ancestor's
    ordinary additive sum, unlike a NON_EXPANDING rollup's.

    Reproduces the real ESTO 09.08 Coal transformation residual exactly:
    09.08.01 Coke ovens (a leaf under 09.08 Coal transformation) is itself
    NON_EXPANDING at its own level, but its true tree parent,
    09.08 Coal transformation (including own use), is DETACHED -- meaning its
    own-use contributors are an intentionally separate accounting boundary,
    never additive into 09 Total transformation sector. Without
    detached_labels, the inclusive-sibling fallback (added for the
    NON_EXPANDING case above) incorrectly folds this leaf's value in anyway,
    producing a spurious mismatch on the real parent.
    """
    comparison_path = tmp_path / "comparison.csv"
    tree_rows = [
        {"code": "09 Total transformation sector", "parent_code": ""},
        {"code": "09.08 Coal transformation", "parent_code": "09 Total transformation sector"},
        {"code": "09.01-09.02 Power sector", "parent_code": "09 Total transformation sector"},
        {"code": "09.08 Coal transformation (including own use)", "parent_code": ""},
        {"code": "09.08.01 Coke ovens", "parent_code": "09.08 Coal transformation"},
        {"code": "09.08.01 Coke ovens (including own use)", "parent_code": "09.08 Coal transformation (including own use)"},
    ]
    common_rows = [dict(row) for row in tree_rows]
    common_rows[4]["parent_code"] = "09.08 Coal transformation (including own use)"
    tree = pd.DataFrame(
        [
            {"dataset": "esto", "axis": "flow", **row}
            for row in tree_rows
            if "including own use" not in row["code"]
        ]
        + [
            {"dataset": "common_esto", "axis": "flow", **row}
            for row in common_rows
        ]
    )
    pd.DataFrame([
        {"comparison_scope": "esto_leap", "source_system": "ESTO", "economy": "05_PRC", "scenario": "historical", "year": 2023, "common_flow_label": "09 Total transformation sector", "common_product_label": "08.03 Gas works gas", "value": -95.158148},
        {"comparison_scope": "esto_leap", "source_system": "ESTO", "economy": "05_PRC", "scenario": "historical", "year": 2023, "common_flow_label": "09.01-09.02 Power sector", "common_product_label": "08.03 Gas works gas", "value": -95.158148},
        {"comparison_scope": "esto_leap", "source_system": "ESTO", "economy": "05_PRC", "scenario": "historical", "year": 2023, "common_flow_label": "09.08.01 Coke ovens (including own use)", "common_product_label": "08.03 Gas works gas", "value": -12.744965},
    ]).to_csv(comparison_path, index=False)

    # Without detached_labels: the bug reproduces -- the DETACHED leaf's value
    # incorrectly folds in (children_sum = -95.158148 + -12.744965), producing
    # a spurious mismatch against the true parent_value (-95.158148).
    buggy_result = validate_common_esto_recursive_sums(
        tree,
        comparison_path,
        leap_var_base_year=2022,
        rollup_modes={
            "09.08.01 Coke ovens (including own use)": "NON_EXPANDING",
        },
    )
    buggy_check = buggy_result[buggy_result["parent_code"] == "09 Total transformation sector"]
    assert len(buggy_check) == 1
    assert buggy_check.iloc[0]["status"] == "failed"

    # With detached_labels correctly identifying the DETACHED rollup: the
    # leaf is dropped, not folded in, and parent_value (-95.158148) equals
    # the true children_sum (-95.158148, Power sector only).
    fixed_result = validate_common_esto_recursive_sums(
        tree,
        comparison_path,
        leap_var_base_year=2022,
        detached_labels={"09.08 Coal transformation"},
        rollup_modes={
            "09.08.01 Coke ovens (including own use)": "NON_EXPANDING",
        },
    )
    fixed_check = fixed_result[fixed_result["parent_code"] == "09 Total transformation sector"]
    assert fixed_check.empty


def test_rollup_resolution_non_expanding_leaf_breaks_base_inclusive_cycle() -> None:
    """A declared inclusive fallback resolves once and never follows its back edge."""
    base = "09.06.01 Gas works plants"
    inclusive = f"{base} (including own use)"
    children_map = {
        base: [inclusive],
        inclusive: [base],
    }

    assert _resolve_to_comparison_data(
        [base],
        {inclusive},
        children_map,
        rollup_modes={inclusive: "NON_EXPANDING"},
    ) == [inclusive]
    assert _resolve_to_comparison_data(
        [base],
        {inclusive},
        children_map,
    ) == []


def test_rollup_resolution_non_expanding_parent_retains_extended_children() -> None:
    """Detailed ESTO Extended children win over the alternative inclusive view."""
    base = "09.06.02 Liquefaction/regasification plants"
    inclusive = f"{base} (including own use)"
    liquefaction = "09.06.02.01 Liquefaction"
    regasification = "09.06.02.02 Regasification"
    children_map = {
        base: [inclusive, liquefaction, regasification],
        inclusive: [base],
    }

    assert _resolve_to_comparison_data(
        [base],
        {inclusive, liquefaction, regasification},
        children_map,
        rollup_modes={inclusive: "NON_EXPANDING"},
    ) == [liquefaction, regasification]


def test_rollup_resolution_detached_boundary_excludes_direct_contributors() -> None:
    """A direct data hit below a detached parent is not part of an ordinary sum."""
    detached_parent = "09.08 Coal transformation"
    contributor = "09.08.01 Coke ovens"

    assert _resolve_to_comparison_data(
        [contributor],
        {contributor},
        {},
        detached_labels={detached_parent},
        parent_of={contributor: detached_parent},
    ) == []


def test_rollup_resolution_detached_boundary_wins_over_descendant_mode() -> None:
    """NON_EXPANDING metadata below a detached parent cannot restore the branch."""
    detached_parent = "09.08 Coal transformation"
    base = "09.08.01 Coke ovens"
    inclusive = f"{base} (including own use)"

    assert _resolve_to_comparison_data(
        [base],
        {inclusive},
        {base: [inclusive], inclusive: [base]},
        detached_labels={detached_parent},
        parent_of={base: detached_parent},
        rollup_modes={inclusive: "NON_EXPANDING"},
    ) == []


def test_build_ninth_subtotal_esto_flow_labels_maps_subtotal_sectors_to_esto_flows(tmp_path: Path) -> None:
    """A NINTH sector tree marked is_subtotal maps to its converted ESTO flow label.

    Reproduces the real 14_03_manufacturing shape: it is flagged
    is_subtotal=True in the NINTH sector tree (its raw value is exactly the
    sum of its own named children), and the mapping workbook converts it to
    ESTO flow "14.03 Manufacturing" -- exactly the label that must not be
    validated as an ordinary additive NINTH parent, since doing so double
    -counts the same NINTH total under a different allocation split than its
    own children use.
    """
    workbook_path = tmp_path / "mappings.xlsx"
    _write_mapping_workbook(
        workbook_path,
        ninth_rows=[
            {"ninth_sector": "14_03_manufacturing", "ninth_fuel": "02_coal_products",
             "esto_flow": "14.03 Manufacturing", "esto_product": "02.01 Coke oven coke"},
            {"ninth_sector": "14_03_01_iron_and_steel", "ninth_fuel": "02_coal_products",
             "esto_flow": "14.03.01 Iron and steel", "esto_product": "02.01 Coke oven coke"},
        ],
    )
    tree_df = pd.DataFrame([
        {"dataset": "ninth", "axis": "sector", "code": "14_industry_sector/14_03_manufacturing",
         "label": "14_03_manufacturing", "level": 2, "parent_code": "14_industry_sector", "is_subtotal": True},
        {"dataset": "ninth", "axis": "sector",
         "code": "14_industry_sector/14_03_manufacturing/14_03_01_iron_and_steel",
         "label": "14_03_01_iron_and_steel", "level": 3,
         "parent_code": "14_industry_sector/14_03_manufacturing", "is_subtotal": False},
    ])

    labels = build_ninth_subtotal_esto_flow_labels(tree_df, workbook_path)

    assert labels == {"14.03 Manufacturing"}


def test_common_flow_validation_excludes_ninth_subtotal_parent_but_keeps_esto_check(tmp_path: Path) -> None:
    """A NINTH is_subtotal parent must be excluded for NINTH only -- ESTO's own,
    independently-differentiated check on the same flow label must still run.

    Reproduces the real 14.03 Manufacturing shape: NINTH's raw
    14_03_manufacturing total is fully redundant with its own named
    sub-flows (converted via a different, equal-share allocation basis, so
    naive comparison against the same sub-flows produces a spurious
    mismatch) -- but ESTO's own data for "14.03 Manufacturing" genuinely
    differentiates its own children, so an ESTO-side mismatch on the same
    parent must still be reported, not silently dropped.
    """
    comparison_path = tmp_path / "comparison.csv"
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "flow", "code": "14.03 Manufacturing", "parent_code": ""},
        {"dataset": "esto", "axis": "flow", "code": "14.03.01 Iron and steel", "parent_code": "14.03 Manufacturing"},
        {"dataset": "common_esto", "axis": "flow", "code": "14.03 Manufacturing", "parent_code": ""},
        {"dataset": "common_esto", "axis": "flow", "code": "14.03.01 Iron and steel", "parent_code": "14.03 Manufacturing"},
    ])
    pd.DataFrame([
        # NINTH: parent and child disagree (the allocation-split mismatch) -- must be excluded, not reported.
        {"comparison_scope": "scope", "source_system": "NINTH", "economy": "01_AUS", "scenario": "reference", "year": 2023, "common_flow_label": "14.03 Manufacturing", "common_product_label": "02.01 Coke oven coke", "value": 16.71},
        {"comparison_scope": "scope", "source_system": "NINTH", "economy": "01_AUS", "scenario": "reference", "year": 2023, "common_flow_label": "14.03.01 Iron and steel", "common_product_label": "02.01 Coke oven coke", "value": 19.10},
        # ESTO: parent and child genuinely disagree -- a real mismatch that must still be reported.
        {"comparison_scope": "scope", "source_system": "ESTO", "economy": "01_AUS", "scenario": "reference", "year": 2023, "common_flow_label": "14.03 Manufacturing", "common_product_label": "02.01 Coke oven coke", "value": 100.0},
        {"comparison_scope": "scope", "source_system": "ESTO", "economy": "01_AUS", "scenario": "reference", "year": 2023, "common_flow_label": "14.03.01 Iron and steel", "common_product_label": "02.01 Coke oven coke", "value": 50.0},
    ]).to_csv(comparison_path, index=False)

    result = validate_common_esto_recursive_sums(
        tree,
        comparison_path,
        leap_var_base_year=2022,
        source_specific_exclude_parents={"NINTH": {"14.03 Manufacturing"}},
    )

    ninth_check = result[(result["source_system"] == "NINTH") & (result["parent_code"] == "14.03 Manufacturing")]
    assert ninth_check.empty

    esto_check = result[(result["source_system"] == "ESTO") & (result["parent_code"] == "14.03 Manufacturing")]
    assert len(esto_check) == 1
    assert esto_check.iloc[0]["status"] == "failed"


# Minimal columns used by the lookup for an empty LEAP frame.
LEAP_LOOKUP_COLUMNS = [
    "source_issue_id", "source_system", "economy", "scenario", "year",
    "esto_parent_flow", "esto_parent_product", "source_issue_class",
    "inheritance_eligible",
]

#%%
