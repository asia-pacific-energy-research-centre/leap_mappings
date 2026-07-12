import pandas as pd

from codebase.mapping_tools.convert_leap_results_to_esto import convert_leap_results_to_esto


def _relationship_rows() -> pd.DataFrame:
    base = {
        "source_system": "LEAP",
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


def _leap_results() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "economy": "01_AUS",
            "scenario": "reference",
            "year": 2023,
            "leap_flow": "combined_source",
            "leap_product": "fuel",
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


def test_leap_converter_default_returns_dataframe() -> None:
    result = convert_leap_results_to_esto(_leap_results(), _relationship_rows())

    assert isinstance(result, pd.DataFrame)


def test_leap_lineage_sums_to_aggregated_values_and_keeps_allocation_share() -> None:
    converted_df, lineage_df = convert_leap_results_to_esto(
        _leap_results(),
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
