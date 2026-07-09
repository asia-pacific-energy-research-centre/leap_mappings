"""Tests for opt-in target-dataset share allocation."""

import pandas as pd

from codebase.mapping_tools.apply_ninth_to_esto_conversion import convert_ninth_results_to_esto
from codebase.mapping_tools.target_share_allocation import apply_target_dataset_allocation


def _relationship_rows() -> pd.DataFrame:
    base = {
        "use_case": "ninth_to_esto_balance_conversion",
        "include_in_use_case": True,
        "source_system": "NINTH",
        "source_flow": "combined_source",
        "source_product": "fuel",
        "target_system": "ESTO",
        "target_product": "Fuel",
        "allocation_method": "direct",
        "allocation_source": "target_dataset_share",
        "allocation_share": 0.5,
    }
    return pd.DataFrame([
        {**base, "target_flow": "Component A"},
        {**base, "target_flow": "Component B"},
    ])


def _target_values(component_a: float, component_b: float) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "economy": "01AUS",
            "scenario": "historical",
            "year": 2023,
            "esto_flow": "Component A",
            "esto_product": "Fuel",
            "value": component_a,
        },
        {
            "economy": "01AUS",
            "scenario": "historical",
            "year": 2023,
            "esto_flow": "Component B",
            "esto_product": "Fuel",
            "value": component_b,
        },
    ])


def test_target_dataset_share_uses_target_component_values() -> None:
    merged = pd.DataFrame([
        {
            "economy": "01_AUS",
            "scenario": "reference",
            "year": 2023,
            "source_flow": "combined_source",
            "source_product": "fuel",
            "target_flow": "Component A",
            "target_product": "Fuel",
            "allocation_source": "target_dataset_share",
            "allocation_share": 0.5,
            "value": 100.0,
        },
        {
            "economy": "01_AUS",
            "scenario": "reference",
            "year": 2023,
            "source_flow": "combined_source",
            "source_product": "fuel",
            "target_flow": "Component B",
            "target_product": "Fuel",
            "allocation_source": "target_dataset_share",
            "allocation_share": 0.5,
            "value": 100.0,
        },
    ])

    result = apply_target_dataset_allocation(merged, _target_values(70, 30))

    assert result["allocation_share"].round(6).tolist() == [0.7, 0.3]


def test_target_dataset_share_falls_back_to_equal_when_basis_is_zero() -> None:
    merged = pd.DataFrame([
        {
            "economy": "01_AUS",
            "scenario": "reference",
            "year": 2023,
            "source_flow": "combined_source",
            "source_product": "fuel",
            "target_flow": "Component A",
            "target_product": "Fuel",
            "allocation_source": "target_dataset_share",
            "allocation_share": "",
            "value": 100.0,
        },
        {
            "economy": "01_AUS",
            "scenario": "reference",
            "year": 2023,
            "source_flow": "combined_source",
            "source_product": "fuel",
            "target_flow": "Component B",
            "target_product": "Fuel",
            "allocation_source": "target_dataset_share",
            "allocation_share": "",
            "value": 100.0,
        },
    ])

    result = apply_target_dataset_allocation(merged, _target_values(0, 0))

    assert result["allocation_share"].tolist() == [0.5, 0.5]


def test_ninth_converter_applies_target_dataset_share() -> None:
    ninth_results = pd.DataFrame([
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

    result = convert_ninth_results_to_esto(
        ninth_results,
        _relationship_rows(),
        target_values_df=_target_values(70, 30),
    )

    values = result.set_index("target_flow")["value"].to_dict()
    assert values == {"Component A": 70.0, "Component B": 30.0}

