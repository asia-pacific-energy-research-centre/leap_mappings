import pandas as pd

from codebase.outlook_mapping_maintenance_workflow import (
    _compute_leap_subtotals,
    _mapping_style_sector_path_from_export_segments,
    _split_allowed_crosswalk_conflicts,
    _split_allowed_many_to_many,
)


def test_split_allowed_many_to_many_keeps_placeholder_rows_out_of_conflicts() -> None:
    many_to_many = pd.DataFrame(
        [
            {
                "sheet": "leap_combined_ninth",
                "leap_sector_name_full_path": "Electricity Generation",
                "raw_leap_fuel_name": "Solar nonspecified",
                "ninth_sector": "09_01_electricity_plants",
                "ninth_fuel": "12_solar_unallocated",
                "cardinality": "many_to_many",
            },
            {
                "sheet": "leap_combined_ninth",
                "leap_sector_name_full_path": "Electricity Generation",
                "raw_leap_fuel_name": "Solar nonspecified",
                "ninth_sector": "09_01_electricity_plants",
                "ninth_fuel": "12_x_other_solar",
                "cardinality": "many_to_many",
            },
            {
                "sheet": "leap_combined_ninth",
                "leap_sector_name_full_path": "Electricity interim/Electricity interim",
                "raw_leap_fuel_name": "Solar nonspecified",
                "ninth_sector": "09_01_electricity_plants",
                "ninth_fuel": "12_solar_unallocated",
                "cardinality": "many_to_many",
            },
            {
                "sheet": "leap_combined_ninth",
                "leap_sector_name_full_path": "Electricity interim/Electricity interim",
                "raw_leap_fuel_name": "Solar nonspecified",
                "ninth_sector": "09_01_electricity_plants",
                "ninth_fuel": "12_x_other_solar",
                "cardinality": "many_to_many",
            },
            {
                "sheet": "ninth_pairs_to_esto_pairs",
                "esto_flow": "09.01.01 Electricity plants",
                "esto_product": "15.05 Other biomass",
                "9th_sector": "09_01_electricity_plants",
                "9th_fuel": "15_05_other_biomass",
                "cardinality": "many_to_many",
            },
            {
                "sheet": "ninth_pairs_to_esto_pairs",
                "esto_flow": "09.01.02 CHP plants",
                "esto_product": "15.05 Other biomass",
                "9th_sector": "09_02_chp_plants",
                "9th_fuel": "15_05_other_biomass",
                "cardinality": "many_to_many",
            },
            {
                "sheet": "ninth_pairs_to_esto_pairs",
                "esto_flow": "09.02.02 CHP plants",
                "esto_product": "15.05 Other biomass",
                "9th_sector": "09_02_chp_plants",
                "9th_fuel": "15_05_other_biomass",
                "cardinality": "many_to_many",
            },
            {
                "sheet": "ninth_pairs_to_esto_pairs",
                "esto_flow": "09.01.02 CHP plants",
                "esto_product": "15.05 Other biomass",
                "9th_sector": "09_02_chp_plants",
                "9th_fuel": "15_solid_biomass_unallocated",
                "cardinality": "many_to_many",
            },
            {
                "sheet": "ninth_pairs_to_esto_pairs",
                "esto_flow": "09.02.02 CHP plants",
                "esto_product": "15.05 Other biomass",
                "9th_sector": "09_02_chp_plants",
                "9th_fuel": "15_solid_biomass_unallocated",
                "cardinality": "many_to_many",
            },
            {
                "sheet": "ninth_pairs_to_esto_pairs",
                "esto_flow": "09.01.02 CHP plants",
                "esto_product": "16.09 Other sources",
                "9th_sector": "09_02_chp_plants",
                "9th_fuel": "16_others_unallocated",
                "cardinality": "many_to_many",
            },
            {
                "sheet": "ninth_pairs_to_esto_pairs",
                "esto_flow": "09.01.03 Heat plants",
                "esto_product": "15.05 Other biomass",
                "9th_sector": "09_x_heat_plants",
                "9th_fuel": "15_05_other_biomass",
                "cardinality": "many_to_many",
            },
            {
                "sheet": "ninth_pairs_to_esto_pairs",
                "esto_flow": "09.01.03 Heat plants",
                "esto_product": "16.09 Other sources",
                "9th_sector": "09_x_heat_plants",
                "9th_fuel": "16_09_other_sources",
                "cardinality": "many_to_many",
            },
            {
                "sheet": "ninth_pairs_to_esto_pairs",
                "esto_flow": "18.01 MAP electricity plants",
                "esto_product": "15.05 Other biomass",
                "9th_sector": "18_01_electricity_plants",
                "9th_fuel": "15_05_other_biomass",
                "cardinality": "many_to_many",
            },
            {
                "sheet": "ninth_pairs_to_esto_pairs",
                "esto_flow": "18.02 MAP CHP plants",
                "esto_product": "15.05 Other biomass",
                "9th_sector": "18_01_electricity_plants",
                "9th_fuel": "15_05_other_biomass",
                "cardinality": "many_to_many",
            },
            {
                "sheet": "ninth_pairs_to_esto_pairs",
                "esto_flow": "18.01 MAP electricity plants",
                "esto_product": "15.05 Other biomass",
                "9th_sector": "18_01_electricity_plants",
                "9th_fuel": "15_solid_biomass_unallocated",
                "cardinality": "many_to_many",
            },
            {
                "sheet": "ninth_pairs_to_esto_pairs",
                "esto_flow": "18.02 MAP CHP plants",
                "esto_product": "15.05 Other biomass",
                "9th_sector": "18_01_electricity_plants",
                "9th_fuel": "15_solid_biomass_unallocated",
                "cardinality": "many_to_many",
            },
            {
                "sheet": "leap_combined_esto",
                "leap_sector_name_full_path": "Other loss and own use/Liquefaction and regasification plants",
                "raw_leap_fuel_name": "Electricity",
                "esto_flow": "09.06 Gas processing plants",
                "esto_product": "17 Electricity",
                "cardinality": "many_to_many",
            },
        ]
    ).fillna("")

    conflicts, allowed = _split_allowed_many_to_many(many_to_many)

    assert len(allowed) == 16
    assert set(allowed["many_to_many_review_status"]) == {"allowed"}
    assert allowed["many_to_many_review_reason"].str.contains("placeholder overlap").all()
    assert len(conflicts) == 1
    assert conflicts.loc[0, "sheet"] == "leap_combined_esto"
    assert "many_to_many_review_status" not in conflicts.columns


def test_split_allowed_crosswalk_conflicts_ignores_rollup_categories() -> None:
    crosswalk_conflicts = pd.DataFrame(
        [
            {
                "leap_sector_name_full_path": "Transfers",
                "raw_leap_fuel_name": "Petroleum coke",
                "ninth_sector": "08_transfers",
                "ninth_fuel": "07_x_other_petroleum_products",
                "implied_esto_targets": (
                    "08 Transfers || 07.12 White spirit SBP | "
                    "08 Transfers || 07.17 Other products"
                ),
                "active_esto_targets": (
                    "08 Transfers || 07.16 Petroleum coke | "
                    "08 Transfers || 07_x_other_petroleum_products"
                ),
                "conflict_reason": "implied_esto_target_not_active_for_leap_source",
                "conflict_classification": "target_mismatch_review",
            },
            {
                "leap_sector_name_full_path": "Other loss and own use/Liquefaction and regasification plants",
                "raw_leap_fuel_name": "Electricity",
                "ninth_sector": "09_06_gas_processing_plants",
                "ninth_fuel": "17_electricity",
                "implied_esto_targets": (
                    "09.06 Gas processing plants || 17 Electricity | "
                    "09.06.02 Liquefaction/regasification plants || 17 Electricity"
                ),
                "active_esto_targets": (
                    "10.01.03 Liquefaction/regasification plants || 17 Electricity"
                ),
                "conflict_reason": "implied_esto_target_not_active_for_leap_source",
                "conflict_classification": "target_mismatch_review",
            },
        ]
    )

    conflicts, allowed = _split_allowed_crosswalk_conflicts(crosswalk_conflicts)

    assert len(allowed) == 1
    assert allowed.loc[0, "leap_sector_name_full_path"] == "Transfers"
    assert allowed.loc[0, "crosswalk_review_status"] == "allowed"
    assert "rollup category overlap" in allowed.loc[0, "crosswalk_review_reason"]
    assert len(conflicts) == 1
    assert conflicts.loc[0, "leap_sector_name_full_path"].startswith("Other loss and own use")
    assert "crosswalk_review_status" not in conflicts.columns


def test_mapping_style_sector_path_from_export_segments_matches_workbook_paths() -> None:
    fuel_names = {"Electricity", "Natural gas", "Other bituminous coal"}

    assert (
        _mapping_style_sector_path_from_export_segments(
            ["Transformation", "Oil Refining", "Processes", "Oil Refining", "Feedstock Fuels", "Natural gas"],
            fuel_names,
        )
        == "Oil Refining/Oil Refining"
    )
    assert (
        _mapping_style_sector_path_from_export_segments(
            ["Transformation", "Electricity Generation", "Output Fuels", "Electricity"],
            fuel_names,
        )
        == "Electricity Generation"
    )
    assert (
        _mapping_style_sector_path_from_export_segments(
            ["Demand", "Industry", "Manufacturing", "Iron and steel", "Other bituminous coal"],
            fuel_names,
        )
        == "Industry/Manufacturing/Iron and steel"
    )
    assert _mapping_style_sector_path_from_export_segments(["Key", "Macro", "GDP"], fuel_names) == ""


def test_full_export_paths_make_power_parent_branches_subtotals() -> None:
    fuel_names = {"Electricity", "Natural gas", "Wind"}
    export_branch_segments = [
        ["Transformation", "Electricity Generation"],
        ["Transformation", "Electricity Generation", "Output Fuels", "Electricity"],
        ["Transformation", "Electricity Generation", "Processes", "Gas"],
        ["Transformation", "Electricity Generation", "Processes", "Gas", "Feedstock Fuels", "Natural gas"],
        ["Transformation", "Electricity Generation", "Processes", "Wind"],
        ["Transformation", "Electricity Generation", "Processes", "Wind", "Feedstock Fuels", "Wind"],
    ]
    export_paths = {
        _mapping_style_sector_path_from_export_segments(segments, fuel_names)
        for segments in export_branch_segments
    }
    export_paths.discard("")

    assert "Electricity Generation" in _compute_leap_subtotals(export_paths)
