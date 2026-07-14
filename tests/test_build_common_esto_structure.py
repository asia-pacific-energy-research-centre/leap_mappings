"""Regression tests for manually configured Common ESTO rollups."""

import pandas as pd

from codebase.mapping_tools.build_common_esto_structure import build_manual_override_edges


def test_blank_product_override_rolls_shared_products_only() -> None:
    overrides = pd.DataFrame([
        {
            "comparison_scope": "",
            "override_group_id": "agriculture_and_fishing",
            "component_esto_flow": "16.03 Agriculture",
            "component_esto_product": "",
        },
        {
            "comparison_scope": "",
            "override_group_id": "agriculture_and_fishing",
            "component_esto_flow": "16.04 Fishing",
            "component_esto_product": "",
        },
    ])
    required_components = pd.DataFrame([
        {"component_esto_flow": "16.03 Agriculture", "component_esto_product": "07.07 Gas/diesel oil"},
        {"component_esto_flow": "16.03 Agriculture", "component_esto_product": "08.01 Natural gas"},
        {"component_esto_flow": "16.04 Fishing", "component_esto_product": "07.07 Gas/diesel oil"},
        {"component_esto_flow": "16.04 Fishing", "component_esto_product": "07.08 Fuel oil"},
    ])

    edges, aggregate_groups = build_manual_override_edges(
        overrides_df=overrides,
        comparison_scope="leap_vs_esto_vs_ninth",
        required_components_df=required_components,
    )

    assert edges == [
        (
            ("16.03 Agriculture", "07.07 Gas/diesel oil"),
            ("16.04 Fishing", "07.07 Gas/diesel oil"),
        )
    ]
    assert aggregate_groups.iloc[0]["component_pairs"] == (
        "16.03 Agriculture :: 07.07 Gas/diesel oil|"
        "16.04 Fishing :: 07.07 Gas/diesel oil"
    )


def test_override_with_multiple_shared_products_never_links_products() -> None:
    """Two shared products must produce two per-product merges, not one blob.

    A single star over all (flow, product) combinations would chain unlike
    products into one common row and fuse whole product families through the
    product-axis partition closure (the '01.02-...,17 Other bituminous coal'
    mega-partition regression).
    """
    overrides = pd.DataFrame([
        {
            "comparison_scope": "",
            "override_group_id": "oil_refineries_own_use",
            "component_esto_flow": "09.07 Oil refineries",
            "component_esto_product": "",
        },
        {
            "comparison_scope": "",
            "override_group_id": "oil_refineries_own_use",
            "component_esto_flow": "10.01.11 Oil refineries",
            "component_esto_product": "",
        },
    ])
    required_components = pd.DataFrame([
        {"component_esto_flow": "09.07 Oil refineries", "component_esto_product": "06.01 Crude oil"},
        {"component_esto_flow": "09.07 Oil refineries", "component_esto_product": "07.01 Motor gasoline"},
        {"component_esto_flow": "10.01.11 Oil refineries", "component_esto_product": "06.01 Crude oil"},
        {"component_esto_flow": "10.01.11 Oil refineries", "component_esto_product": "07.01 Motor gasoline"},
    ])

    edges, aggregate_groups = build_manual_override_edges(
        overrides_df=overrides,
        comparison_scope="leap_vs_esto",
        required_components_df=required_components,
    )

    assert all(left[1] == right[1] for left, right in edges), "no edge may span two products"
    assert edges == [
        (
            ("09.07 Oil refineries", "06.01 Crude oil"),
            ("10.01.11 Oil refineries", "06.01 Crude oil"),
        ),
        (
            ("09.07 Oil refineries", "07.01 Motor gasoline"),
            ("10.01.11 Oil refineries", "07.01 Motor gasoline"),
        ),
    ]
    assert len(aggregate_groups) == 2
