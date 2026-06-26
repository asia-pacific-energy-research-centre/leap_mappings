import pandas as pd

from codebase.outlook_mapping_maintenance_workflow import _split_allowed_many_to_many


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

    assert len(allowed) == 4
    assert set(allowed["many_to_many_review_status"]) == {"allowed"}
    assert allowed["many_to_many_review_reason"].str.contains("placeholder overlap").all()
    assert len(conflicts) == 1
    assert conflicts.loc[0, "sheet"] == "leap_combined_esto"
    assert "many_to_many_review_status" not in conflicts.columns
