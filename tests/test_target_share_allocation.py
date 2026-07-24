"""Tests for opt-in target-dataset share allocation."""

import pandas as pd
import pytest

from codebase.mapping_tools.apply_ninth_to_esto_conversion import convert_ninth_results_to_esto
from codebase.mapping_tools.target_share_allocation import (
    apply_target_dataset_allocation,
    load_target_dataset_share_basis_rows,
    target_dataset_share_target_flows,
)


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


def test_target_dataset_share_counts_unique_targets_when_source_rows_repeat() -> None:
    merged = pd.DataFrame([
        {
            "economy": "01_AUS", "scenario": "reference", "year": 2023,
            "source_flow": "rolled_source", "source_product": "fuel",
            "target_flow": "Component A", "target_product": "Fuel",
            "allocation_source": "target_dataset_share", "allocation_share": "",
        },
        {
            "economy": "01_AUS", "scenario": "reference", "year": 2023,
            "source_flow": "rolled_source", "source_product": "fuel",
            "target_flow": "Component B", "target_product": "Fuel",
            "allocation_source": "target_dataset_share", "allocation_share": "",
        },
    ] * 3)

    result = apply_target_dataset_allocation(merged, _target_values(70, 30))

    assert result["allocation_share"].round(6).tolist() == [0.7, 0.3] * 3


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


def test_target_dataset_share_target_flows_identifies_unallocated_one_to_many() -> None:
    relationships = pd.DataFrame([
        {
            "source_flow": "combined_source", "source_product": "fuel",
            "target_flow": "Component A", "target_product": "Fuel",
            "allocation_share": "",
        },
        {
            "source_flow": "combined_source", "source_product": "fuel",
            "target_flow": "Component B", "target_product": "Fuel",
            "allocation_share": "",
        },
        {
            "source_flow": "direct_source", "source_product": "fuel",
            "target_flow": "Solo target", "target_product": "Fuel",
            "allocation_share": 1.0,
        },
    ])

    assert target_dataset_share_target_flows(relationships) == {"Component A", "Component B"}


def test_load_target_dataset_share_basis_rows_reads_only_subtotal_rows_for_needed_flows(tmp_path) -> None:
    # Reproduces the production bug shape: a NINTH source pair targets an
    # aggregate ESTO flow ("Manufacturing") that ESTO only reports as an
    # is_subtotal=True row -- esto_results_exact_rows.csv strips that row,
    # so the allocation basis must be recovered from the raw ESTO source.
    esto_csv = tmp_path / "esto_with_subtotals.csv"
    pd.DataFrame([
        {"economy": "01AUS", "flows": "Manufacturing", "products": "Coal products",
         "is_subtotal": "TRUE", "2023": 18.0},
        {"economy": "01AUS", "flows": "Manufacturing", "products": "Coke oven coke",
         "is_subtotal": "TRUE", "2023": 13.0},
        {"economy": "01AUS", "flows": "Manufacturing", "products": "Coal tar",
         "is_subtotal": "TRUE", "2023": 5.0},
        # Leaf rows for an unrelated flow must not leak into the basis.
        {"economy": "01AUS", "flows": "Iron and steel", "products": "Coke oven coke",
         "is_subtotal": "FALSE", "2023": 9.0},
    ]).to_csv(esto_csv, index=False)

    basis = load_target_dataset_share_basis_rows(esto_csv, {"Manufacturing"})

    assert set(basis["esto_flow"]) == {"Manufacturing"}
    assert set(basis["esto_product"]) == {"Coal products", "Coke oven coke", "Coal tar"}
    coke = basis.loc[basis["esto_product"] == "Coke oven coke", "value"].iloc[0]
    assert coke == 13.0


def test_load_target_dataset_share_basis_rows_empty_when_no_flows_needed(tmp_path) -> None:
    esto_csv = tmp_path / "esto_with_subtotals.csv"
    pd.DataFrame([
        {"economy": "01AUS", "flows": "Manufacturing", "products": "Coal products",
         "is_subtotal": "TRUE", "2023": 18.0},
    ]).to_csv(esto_csv, index=False)

    basis = load_target_dataset_share_basis_rows(esto_csv, set())

    assert basis.empty


def test_ninth_converter_recovers_subtotal_basis_for_aggregate_target_flow() -> None:
    """End-to-end reproduction of the coal-products duplicate-value bug.

    NINTH reports one undifferentiated value for a coal-products source pair
    that maps to two real ESTO products under the same aggregate ESTO flow.
    ESTO's own basis for splitting it only exists as an is_subtotal row, not
    in the usual leaf-only target_values frame -- without recovering that
    basis, the converter falls back to a flat 50/50 split; with it, the split
    matches ESTO's real 13:5 ratio.
    """
    relationship_rows = pd.DataFrame([
        {
            "use_case": "ninth_to_esto_balance_conversion",
            "include_in_use_case": True,
            "source_system": "NINTH",
            "source_flow": "14_03_manufacturing",
            "source_product": "02_coal_products",
            "target_system": "ESTO",
            "target_flow": "14.03 Manufacturing",
            "target_product": product,
            "allocation_method": "",
            "allocation_source": "target_dataset_share",
            "allocation_share": "",
        }
        for product in ["02.01 Coke oven coke", "02.07 Coal tar"]
    ])
    ninth_results = pd.DataFrame([
        {
            "source_system": "NINTH",
            "economy": "01_AUS",
            "scenario": "reference",
            "year": 2023,
            "ninth_sector": "14_03_manufacturing",
            "ninth_fuel": "02_coal_products",
            "value": 18.0,
        }
    ])

    # Leaf-only target values (what esto_results_exact_rows.csv provides):
    # no row for the aggregate "14.03 Manufacturing" flow at all.
    leaf_only_target_values = pd.DataFrame([
        {
            "economy": "01AUS", "scenario": "historical", "year": 2023,
            "esto_flow": "14.03.01 Iron and steel", "esto_product": "02.01 Coke oven coke",
            "value": 13.0,
        },
    ])

    without_basis = convert_ninth_results_to_esto(
        ninth_results, relationship_rows, target_values_df=leaf_only_target_values,
    )
    without_values = without_basis.set_index("target_product")["value"].to_dict()
    assert without_values == {"02.01 Coke oven coke": 9.0, "02.07 Coal tar": 9.0}

    needed_flows = target_dataset_share_target_flows(relationship_rows)
    assert needed_flows == {"14.03 Manufacturing"}

    subtotal_basis = pd.DataFrame([
        {
            "economy": "01AUS", "esto_flow": "14.03 Manufacturing",
            "esto_product": "02.01 Coke oven coke", "year": "2023", "value": 13.0,
        },
        {
            "economy": "01AUS", "esto_flow": "14.03 Manufacturing",
            "esto_product": "02.07 Coal tar", "year": "2023", "value": 5.0,
        },
    ])
    augmented_target_values = pd.concat(
        [leaf_only_target_values, subtotal_basis], ignore_index=True
    )

    with_basis = convert_ninth_results_to_esto(
        ninth_results, relationship_rows, target_values_df=augmented_target_values,
    )
    with_values = with_basis.set_index("target_product")["value"].to_dict()
    assert with_values["02.01 Coke oven coke"] == pytest.approx(18.0 * 13.0 / 18.0)
    assert with_values["02.07 Coal tar"] == pytest.approx(18.0 * 5.0 / 18.0)
    assert with_values["02.01 Coke oven coke"] != without_values["02.01 Coke oven coke"]
