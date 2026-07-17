import pandas as pd

from codebase.mapping_tools.apply_ninth_to_esto_conversion import (
    convert_ninth_results_to_esto,
    prepare_ninth_long_format,
)


def _relationship_rows() -> pd.DataFrame:
    base = {
        "source_system": "NINTH",
        "source_flow": "combined_source",
        "source_product": "fuel",
        "target_system": "ESTO",
        "target_product": "Fuel",
        "relationship_id": "rel-combined-source",
        "allocation_method": "direct",
        "allocation_source": "target_dataset_share",
        "allocation_share": 0.5,
    }
    return pd.DataFrame([
        {**base, "target_flow": "Component A"},
        {**base, "target_flow": "Component B"},
    ])


def _ninth_results() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "source_system": "NINTH",
            "economy": "01_AUS",
            "scenario": "reference",
            "year": 2023,
            "ninth_sector": "combined_source",
            "ninth_fuel": "fuel",
            "value": 100.0,
        }
    ])


def _target_values() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "economy": "01AUS",
            "scenario": "historical",
            "year": 2023,
            "esto_flow": "Component A",
            "esto_product": "Fuel",
            "value": 70.0,
        },
        {
            "economy": "01AUS",
            "scenario": "historical",
            "year": 2023,
            "esto_flow": "Component B",
            "esto_product": "Fuel",
            "value": 30.0,
        },
    ])


def test_ninth_converter_default_returns_dataframe() -> None:
    result = convert_ninth_results_to_esto(_ninth_results(), _relationship_rows())

    assert isinstance(result, pd.DataFrame)


def test_ninth_lineage_sums_to_aggregated_values_and_keeps_allocation_share() -> None:
    converted_df, lineage_df = convert_ninth_results_to_esto(
        _ninth_results(),
        _relationship_rows(),
        target_values_df=_target_values(),
        return_lineage=True,
    )

    converted_values = converted_df.set_index("target_flow")["value"].to_dict()
    lineage_values = lineage_df.groupby("target_flow")["value"].sum().to_dict()

    assert converted_values == {"Component A": 70.0, "Component B": 30.0}
    assert lineage_values == converted_values
    assert lineage_df.set_index("target_flow")["allocation_share"].to_dict() == {
        "Component A": 0.7,
        "Component B": 0.3,
    }
    assert set(lineage_df["relationship_id"]) == {"rel-combined-source"}


def test_ninth_preparation_keeps_deeper_sector_detail_separate(tmp_path) -> None:
    """A sub3 row must not be relabelled as its mapped sub2 subtotal."""
    path = tmp_path / "ninth.csv"
    pd.DataFrame([
        {
            "scenarios": "reference", "economy": "20_USA",
            "sectors": "14_industry_sector", "sub1sectors": "14_03_manufacturing",
            "sub2sectors": "14_03_02_chemical_incl_petrochemical",
            "sub3sectors": "x", "sub4sectors": "x", "fuels": "01_coal",
            "subfuels": "01_x_thermal_coal", "2023": 5.0,
        },
        {
            "scenarios": "reference", "economy": "20_USA",
            "sectors": "14_industry_sector", "sub1sectors": "14_03_manufacturing",
            "sub2sectors": "14_03_02_chemical_incl_petrochemical",
            "sub3sectors": "14_03_02_01_fs", "sub4sectors": "x", "fuels": "01_coal",
            "subfuels": "01_x_thermal_coal", "2023": 5.0,
        },
    ]).to_csv(path, index=False)

    result = prepare_ninth_long_format(path)

    assert set(result["ninth_sector"]) == {
        "14_03_02_chemical_incl_petrochemical",
        "14_03_02_01_fs",
    }
