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
