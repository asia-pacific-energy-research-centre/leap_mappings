"""Regression tests for manually configured Common ESTO rollups."""

import pandas as pd

from codebase.mapping_tools.build_common_esto_structure import (
    COMPARISON_SCOPES,
    DEFAULT_ENABLED_COMPARISON_SCOPES,
    build_manual_override_edges,
    build_source_aggregate_edges,
    included_esto_relationships,
)


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
        comparison_scope="esto_leap_ninth",
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
        comparison_scope="esto_leap",
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


def test_esto_leap_scope_excludes_ninth_relationships_and_aggregate_edges() -> None:
    relationships_df = pd.DataFrame(
        [
            {
                "include_in_use_case": True,
                "use_case": "leap_to_esto_balance_conversion",
                "source_system": "LEAP",
                "target_system": "ESTO",
                "source_flow": "LEAP branch",
                "source_product": "Fuel",
                "target_flow": "F1",
                "target_product": "P1",
                "esto_pair_is_subtotal": False,
                "is_rollup_derived": False,
                "allocation_method": "direct",
            },
            {
                "include_in_use_case": True,
                "use_case": "ninth_to_esto_balance_conversion",
                "source_system": "NINTH",
                "target_system": "ESTO",
                "source_flow": "Ninth sector",
                "source_product": "Fuel",
                "target_flow": "F2",
                "target_product": "P2",
                "esto_pair_is_subtotal": False,
                "is_rollup_derived": False,
                "allocation_method": "direct",
            },
        ]
    )

    scope_config = COMPARISON_SCOPES["esto_leap"]
    included_df, excluded_df = included_esto_relationships(
        relationships_df,
        pd.DataFrame(),
        "esto_leap",
        scope_config["use_cases"],
    )
    edges, _, _ = build_source_aggregate_edges(
        included_df,
        "esto_leap",
        scope_config["aggregate_source_systems"],
    )

    assert DEFAULT_ENABLED_COMPARISON_SCOPES == [
        "esto_leap",
        "esto_extended_leap",
        "esto_leap_ninth",
        "esto_extended_leap_ninth",
    ]
    assert included_df["source_system"].tolist() == ["LEAP"]
    assert excluded_df.empty
    assert edges == []


def test_direct_subtotal_targets_form_source_once_aggregate_edges() -> None:
    """Direct sibling subtotal targets must not receive the source twice."""
    relationships_df = pd.DataFrame(
        [
            {
                "include_in_use_case": True,
                "use_case": "leap_to_esto_balance_conversion",
                "source_system": "LEAP",
                "target_system": "ESTO",
                "source_flow": "Agriculture and fishing",
                "source_product": "Anthracite",
                "target_flow": "16.03-16.04 Agriculture and fishing",
                "target_product": "01.03 Sub-bituminous coal",
                "esto_pair_is_subtotal": True,
                "is_rollup_derived": False,
                "allocation_method": "direct",
            },
            {
                "include_in_use_case": True,
                "use_case": "leap_to_esto_balance_conversion",
                "source_system": "LEAP",
                "target_system": "ESTO",
                "source_flow": "Agriculture and fishing",
                "source_product": "Anthracite",
                "target_flow": "16.03-16.04 Agriculture and fishing",
                "target_product": "01.04 Anthracite",
                "esto_pair_is_subtotal": True,
                "is_rollup_derived": False,
                "allocation_method": "direct",
            },
        ]
    )

    edges, aggregate_groups, suppressed = build_source_aggregate_edges(
        relationships_df,
        "esto_leap",
        ["LEAP"],
        allow_direct_subtotal_edges=True,
    )

    assert edges == [
        (
            (
                "16.03-16.04 Agriculture and fishing",
                "01.03 Sub-bituminous coal",
            ),
            (
                "16.03-16.04 Agriculture and fishing",
                "01.04 Anthracite",
            ),
        )
    ]
    assert len(aggregate_groups) == 1
    assert suppressed.empty


def test_direct_subtotal_edges_remain_opt_in() -> None:
    """Merging the feature must not change the canonical graph by default."""
    relationships_df = pd.DataFrame(
        [
            {
                "include_in_use_case": True,
                "use_case": "leap_to_esto_balance_conversion",
                "source_system": "LEAP",
                "target_system": "ESTO",
                "source_flow": "Agriculture and fishing",
                "source_product": "Anthracite",
                "target_flow": "16.03-16.04 Agriculture and fishing",
                "target_product": product,
                "esto_pair_is_subtotal": True,
                "is_rollup_derived": False,
                "allocation_method": "direct",
            }
            for product in [
                "01.03 Sub-bituminous coal",
                "01.04 Anthracite",
            ]
        ]
    )

    edges, aggregate_groups, suppressed = build_source_aggregate_edges(
        relationships_df,
        "esto_leap",
        ["LEAP"],
    )

    assert edges == []
    assert aggregate_groups.empty
    assert len(suppressed) == 2
    assert set(suppressed["exclusion_reason"]) == {
        "esto_pair_is_subtotal",
    }


def test_rollup_derived_targets_remain_suppressed() -> None:
    """Synthetic rollups must not merge a parent flow with its descendants."""
    relationships_df = pd.DataFrame(
        [
            {
                "include_in_use_case": True,
                "use_case": "leap_to_esto_balance_conversion",
                "source_system": "LEAP",
                "target_system": "ESTO",
                "source_flow": "Industry",
                "source_product": "Electricity",
                "target_flow": "14 Industry sector",
                "target_product": "17 Electricity",
                "esto_pair_is_subtotal": False,
                "is_rollup_derived": False,
                "allocation_method": "direct",
            },
            {
                "include_in_use_case": True,
                "use_case": "leap_to_esto_balance_conversion",
                "source_system": "LEAP",
                "target_system": "ESTO",
                "source_flow": "Industry",
                "source_product": "Electricity",
                "target_flow": "12 Total final consumption",
                "target_product": "17 Electricity",
                "esto_pair_is_subtotal": True,
                "is_rollup_derived": True,
                "allocation_method": "direct",
            },
        ]
    )

    edges, _, suppressed = build_source_aggregate_edges(
        relationships_df,
        "esto_leap",
        ["LEAP"],
        allow_direct_subtotal_edges=True,
    )

    assert edges == []
    assert len(suppressed) == 1
    assert suppressed.iloc[0]["exclusion_reason"] == "is_rollup_derived"
