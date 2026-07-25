#%%
"""Focused tests for the non-destructive ESTO Extended prototype."""

#%%
import pandas as pd

from codebase.mapping_tools.build_esto_extended_test import (
    DEMO_RESIDUAL_RULE,
    _esto_code,
    _normalise_path,
    apply_parent_minus_children_rule,
    build_rollup_tree_edges,
    build_transport_tree_candidates,
    build_tree_based_extension_candidates,
    build_template_driven_child_candidates,
    load_esto_flow_tree,
    load_rollup_catalogue,
    summarise_extension_candidate_sets,
)


#%%
def test_normalisation_helpers_keep_hierarchy_stable():
    assert _normalise_path(r"Transformation\CHP plants\Coal CHP") == "Transformation/CHP plants/Coal CHP"
    assert _esto_code("16.01.99 Commercial and public services unallocated") == "16.01.99"


def test_parent_minus_children_generates_named_residual_with_provenance():
    source = pd.DataFrame(
        [
            {
                "economy": "20USA",
                "flows": "16.01 Commercial and public services",
                "products": "17 Electricity",
                "is_subtotal": True,
                "2022": 100.0,
            },
            {
                "economy": "20USA",
                "flows": "16.01.01 Datacentres",
                "products": "17 Electricity",
                "is_subtotal": False,
                "2022": 25.0,
            },
        ]
    )
    generated, summary = apply_parent_minus_children_rule(
        source,
        DEMO_RESIDUAL_RULE,
        source_leap_paths="Demand/Buildings/Commercial and public services",
    )

    assert len(generated) == 1
    row = generated.iloc[0]
    assert row["flows"] == "16.01.99 Commercial and public services unallocated"
    assert row["2022"] == 75.0
    assert row["esto_extended_row_origin"] == "generated"
    assert row["esto_extended_rule_id"] == "demo_parent_minus_children"
    assert row["esto_extended_source_leap_paths"] == "Demand/Buildings/Commercial and public services"
    assert summary.iloc[0]["generated_rows"] == 1


def test_tree_matcher_identifies_a_candidate_extension_set():
    unmapped = pd.DataFrame(
        [
            {
                "branch_path": "Transformation/CHP plants/Coal CHP",
                "parent_path": "Transformation/CHP plants",
                "leaf_label": "Coal CHP",
                "proposed_extension_label": "Coal CHP",
                "exact_active_esto_mapping": False,
            },
            {
                "branch_path": "Transformation/CHP plants/Gas CHP",
                "parent_path": "Transformation/CHP plants",
                "leaf_label": "Gas CHP",
                "proposed_extension_label": "Gas CHP",
                "exact_active_esto_mapping": False,
            },
        ]
    )
    esto_flows = pd.DataFrame(
        [
            {"esto_flow": "09.01.02 CHP plants", "esto_flow_code": "09.01.02"},
            {"esto_flow": "09.02.02 CHP plants", "esto_flow_code": "09.02.02"},
        ]
    )
    candidates = build_tree_based_extension_candidates(unmapped, esto_flows)
    sets = summarise_extension_candidate_sets(candidates)

    assert len(candidates) == 2
    assert set(candidates["candidate_status"]) == {"review_possible_new_child"}
    assert (sets["candidate_count"] == 2).any()


def test_established_lng_names_take_precedence_over_combined_parent_match():
    unmapped = pd.DataFrame(
        [
            {
                "branch_path": "Transformation/NG Liquefaction",
                "parent_path": "Transformation",
                "leaf_label": "NG Liquefaction",
                "proposed_extension_label": "NG Liquefaction",
                "exact_active_esto_mapping": False,
            },
            {
                "branch_path": "Transformation/LNG regasification",
                "parent_path": "Transformation",
                "leaf_label": "LNG regasification",
                "proposed_extension_label": "LNG regasification",
                "exact_active_esto_mapping": False,
            },
        ]
    )
    esto_flows = pd.DataFrame(
        [
            {"esto_flow": "09.06.02 Liquefaction/regasification plants", "esto_flow_code": "09.06.02"},
        ]
    )
    candidates = build_tree_based_extension_candidates(unmapped, esto_flows)

    assert set(candidates["candidate_status"]) == {"review_existing_established_target"}
    assert set(candidates["esto_parent_code"]) == {"09.06.02.01", "09.06.02.02"}


def test_rollup_tree_edges_keep_derived_parent_and_component_children_separate():
    catalogue = pd.DataFrame(
        [
            {
                "rule_sheet": "esto_rollup_rules",
                "source_system": "ESTO",
                "rollup_mode": "EXPANDING",
                "rollup_group_id": "",
                "rolled_flow": "09.01.02,09.02.02 CHP plants",
                "parent_flow_label": "09.01-09.02 Power sector",
                "child_flow_labels": "09.01.02 CHP plants; 09.02.02 CHP plants",
            }
        ]
    )
    edges = build_rollup_tree_edges(catalogue)

    assert set(edges["parent_flow"]) == {"09.01.02,09.02.02 CHP plants"}
    assert set(edges["child_flow"]) == {"09.01.02 CHP plants", "09.02.02 CHP plants"}
    assert set(edges["context_parent_flow"]) == {"09.01-09.02 Power sector"}


def test_transmission_electricity_is_not_proposed_as_a_new_child():
    from codebase.mapping_tools.build_esto_extended_test import (
        BASE_ESTO_PATH,
        MAPPING_WORKBOOK_PATH,
    )

    inventory = pd.DataFrame(
        [
            {
                "branch_path": "Transformation/Transmission and Distribution",
                "parent_path": "Transformation",
                "depth": 2,
                "leaf_label": "Transmission and Distribution",
                "template_count": 1,
                "template_files": "test",
                "observed_as_leaf": False,
            },
            {
                "branch_path": "Transformation/Transmission and Distribution/Processes",
                "parent_path": "Transformation/Transmission and Distribution",
                "depth": 3,
                "leaf_label": "Processes",
                "template_count": 1,
                "template_files": "test",
                "observed_as_leaf": False,
            },
            {
                "branch_path": "Transformation/Transmission and Distribution/Processes/Electricity",
                "parent_path": "Transformation/Transmission and Distribution/Processes",
                "depth": 4,
                "leaf_label": "Electricity",
                "template_count": 1,
                "template_files": "test",
                "observed_as_leaf": False,
            },
            {
                "branch_path": "Transformation/Transmission and Distribution/Processes/Electricity/Feedstock Fuels",
                "parent_path": "Transformation/Transmission and Distribution/Processes/Electricity",
                "depth": 5,
                "leaf_label": "Feedstock Fuels",
                "template_count": 1,
                "template_files": "test",
                "observed_as_leaf": False,
            },
            {
                "branch_path": "Transformation/Transmission and Distribution/Processes/Electricity/Feedstock Fuels/Electricity",
                "parent_path": "Transformation/Transmission and Distribution/Processes/Electricity/Feedstock Fuels",
                "depth": 6,
                "leaf_label": "Electricity",
                "template_count": 1,
                "template_files": "test",
                "observed_as_leaf": True,
            },
        ]
    )
    candidates, _evidence = build_template_driven_child_candidates(
        inventory,
        MAPPING_WORKBOOK_PATH,
        load_rollup_catalogue(MAPPING_WORKBOOK_PATH),
        set(load_esto_flow_tree(BASE_ESTO_PATH)["esto_flow"]),
    )

    assert candidates.empty or not candidates["flows"].astype(str).str.contains("10.02.01", na=False).any()


def test_transport_tree_builds_nested_road_children_from_demand_paths():
    from codebase.mapping_tools.build_esto_extended_test import MAPPING_WORKBOOK_PATH

    inventory = pd.DataFrame(
        [
            {"branch_path": "Demand/Freight road", "observed_as_leaf": False},
            {"branch_path": "Demand/Freight road/Trucks", "observed_as_leaf": False},
            {"branch_path": "Demand/Freight road/Trucks/ICE heavy", "observed_as_leaf": False},
            {"branch_path": "Demand/Freight road/Trucks/ICE heavy/Motor gasoline", "observed_as_leaf": True},
        ]
    )
    candidates, _evidence = build_transport_tree_candidates(
        inventory,
        MAPPING_WORKBOOK_PATH,
        set(),
    )

    assert set(candidates["flows"]) == {
        "15.02.01 Freight road",
        "15.02.01.01 Trucks",
        "15.02.01.01.01 ICE heavy",
    }
    assert set(candidates["products"]) == {"07.01 Motor gasoline"}


#%%
