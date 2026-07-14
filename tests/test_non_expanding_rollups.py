"""Tests for NON_EXPANDING_ROLLUP handling across Stage 1 and Stage 2 helpers."""

import pandas as pd

from codebase.mapping_tools.build_common_esto_structure import (
    apply_non_expanding_flags,
    build_manual_override_edges,
    build_non_expanding_frontier_check,
    build_source_aggregate_edges,
)
from codebase.mapping_tools.build_energy_balance_relationships import build_esto_overrides
from codebase.mapping_tools.non_expanding_rollups import (
    build_esto_non_expanding_subtotal_rows,
    build_non_expanding_rollup_catalogue,
    build_unresolved_non_expanding_qa,
    is_non_expanding_rule_row,
    non_expanding_rollup_id,
    split_non_expanding_rules,
)


def _esto_rules(non_expanding_marker: dict[str, object]) -> pd.DataFrame:
    """Two-group ESTO rollup rule sheet: one marked non-expanding, one ordinary."""
    rows = [
        {
            "input_esto_flow": "16.03 Agriculture",
            "input_esto_product": "",
            "rolled_esto_flow": "16.03-16.04 Agriculture and fishing",
            "rolled_esto_product": "",
            "include": "True",
            "Note": "",
            "parent_flow_label": "16 Other sector",
            "child_flow_labels": "16.03 Agriculture; 16.04 Fishing",
            "rollup_reason": "",
            "NON_EXPANDING_ROLLUP": "",
        },
        {
            "input_esto_flow": "16.04 Fishing",
            "input_esto_product": "",
            "rolled_esto_flow": "16.03-16.04 Agriculture and fishing",
            "rolled_esto_product": "",
            "include": "True",
            "Note": "",
            "parent_flow_label": "16 Other sector",
            "child_flow_labels": "16.03 Agriculture; 16.04 Fishing",
            "rollup_reason": "",
            "NON_EXPANDING_ROLLUP": "",
        },
        {
            "input_esto_flow": "09.01.01 Electricity plants",
            "input_esto_product": "",
            "rolled_esto_flow": "09.01.01,09.02.01 Electricity plants",
            "rolled_esto_product": "",
            "include": "True",
            "Note": "",
            "parent_flow_label": "09.01-09.02 Power sector",
            "child_flow_labels": "09.01.01 Electricity plants; 09.02.01 Electricity plants",
            "rollup_reason": "",
            "NON_EXPANDING_ROLLUP": "False",
        },
        {
            "input_esto_flow": "09.02.01 Electricity plants",
            "input_esto_product": "",
            "rolled_esto_flow": "09.01.01,09.02.01 Electricity plants",
            "rolled_esto_product": "",
            "include": "True",
            "Note": "",
            "parent_flow_label": "09.01-09.02 Power sector",
            "child_flow_labels": "09.01.01 Electricity plants; 09.02.01 Electricity plants",
            "rollup_reason": "",
            "NON_EXPANDING_ROLLUP": "False",
        },
    ]
    df = pd.DataFrame(rows)
    for column, value in non_expanding_marker.items():
        df.loc[df["rolled_esto_flow"] == "16.03-16.04 Agriculture and fishing", column] = value
    return df


class TestRuleMarkers:
    def test_rollup_reason_marker(self) -> None:
        assert is_non_expanding_rule_row({"rollup_reason": "NON_EXPANDING_ROLLUP"})
        assert is_non_expanding_rule_row({"rollup_reason": "non_expanding_rollup"})

    def test_boolean_column_marker(self) -> None:
        assert is_non_expanding_rule_row({"NON_EXPANDING_ROLLUP": "True"})
        assert is_non_expanding_rule_row({"NON_EXPANDING_ROLLUP": True})

    def test_ordinary_rule_not_marked(self) -> None:
        assert not is_non_expanding_rule_row({"rollup_reason": "", "NON_EXPANDING_ROLLUP": "False"})
        assert not is_non_expanding_rule_row({})

    def test_split_by_reason_and_flag(self) -> None:
        rules = _esto_rules({"rollup_reason": "NON_EXPANDING_ROLLUP"})
        ordinary, non_expanding = split_non_expanding_rules(rules)
        assert set(non_expanding["rolled_esto_flow"]) == {"16.03-16.04 Agriculture and fishing"}
        assert set(ordinary["rolled_esto_flow"]) == {"09.01.01,09.02.01 Electricity plants"}

    def test_stable_id(self) -> None:
        assert (
            non_expanding_rollup_id("16.03-16.04 Agriculture and fishing")
            == "nonexp_16_03_16_04_agriculture_and_fishing"
        )


class TestScenario1AgricultureFishing:
    """Scenario 1: rows stay separate, subtotal exists, products come from contributors."""

    def test_non_expanding_group_excluded_from_overrides(self) -> None:
        rules = _esto_rules({"NON_EXPANDING_ROLLUP": "True"})
        ordinary, _ = split_non_expanding_rules(rules)
        overrides = build_esto_overrides(ordinary)
        assert "16.03-16.04 Agriculture and fishing" not in set(overrides["preferred_common_flow_label"])
        # The ordinary group still produces override entries (scenario 2 support).
        assert "09.01.01,09.02.01 Electricity plants" in set(overrides["preferred_common_flow_label"])

    def test_derived_subtotal_products_are_union_of_contributors(self) -> None:
        rules = _esto_rules({"NON_EXPANDING_ROLLUP": "True"})
        _, non_expanding = split_non_expanding_rules(rules)
        esto_wide = pd.DataFrame(
            [
                {"economy": "01AUS", "flows": "16.03 Agriculture", "products": "07.07 Gas/diesel oil", "2020": 5.0, "2021": 7.0},
                {"economy": "01AUS", "flows": "16.03 Agriculture", "products": "08.01 Natural gas", "2020": 2.0, "2021": 0.0},
                {"economy": "01AUS", "flows": "16.04 Fishing", "products": "07.07 Gas/diesel oil", "2020": 1.0, "2021": 1.5},
                {"economy": "01AUS", "flows": "16.05 Other", "products": "07.07 Gas/diesel oil", "2020": 99.0, "2021": 99.0},
            ]
        )
        derived = build_esto_non_expanding_subtotal_rows(esto_wide, non_expanding, ["2020", "2021"])
        assert set(derived["esto_flow"]) == {"16.03-16.04 Agriculture and fishing"}
        # Products are the union actually present in contributors, nothing more.
        assert set(derived["esto_product"]) == {"07.07 Gas/diesel oil", "08.01 Natural gas"}
        diesel_2020 = derived[
            (derived["esto_product"] == "07.07 Gas/diesel oil") & (derived["year"] == 2020)
        ]["value"].iloc[0]
        assert diesel_2020 == 6.0
        assert (derived["non_expanding_rollup_id"] == "nonexp_16_03_16_04_agriculture_and_fishing").all()

    def test_flagged_common_rows(self) -> None:
        common_rows = pd.DataFrame(
            [
                {
                    "common_row_id": "row_subtotal",
                    "component_esto_flow": "16.03-16.04 Agriculture and fishing",
                    "component_esto_product": "07.07 Gas/diesel oil",
                    "is_non_expanding_rollup": False,
                    "non_expanding_rollup_id": "",
                    "common_row_basis": "exact_esto_row",
                },
                {
                    "common_row_id": "row_detail",
                    "component_esto_flow": "16.03 Agriculture",
                    "component_esto_product": "07.07 Gas/diesel oil",
                    "is_non_expanding_rollup": False,
                    "non_expanding_rollup_id": "",
                    "common_row_basis": "exact_esto_row",
                },
            ]
        )
        labels = {"16.03-16.04 Agriculture and fishing": "nonexp_16_03_16_04_agriculture_and_fishing"}
        flagged = apply_non_expanding_flags(common_rows, labels)
        subtotal = flagged[flagged["common_row_id"] == "row_subtotal"].iloc[0]
        detail = flagged[flagged["common_row_id"] == "row_detail"].iloc[0]
        assert bool(subtotal["is_non_expanding_rollup"])
        assert subtotal["non_expanding_rollup_id"] == "nonexp_16_03_16_04_agriculture_and_fishing"
        assert subtotal["common_row_basis"] == "non_expanding_rollup"
        assert not bool(detail["is_non_expanding_rollup"])
        assert detail["common_row_basis"] == "exact_esto_row"


class TestScenario2NormalRollupStillUnions:
    def test_ordinary_override_group_still_creates_edges(self) -> None:
        rules = _esto_rules({"NON_EXPANDING_ROLLUP": "True"})
        ordinary, _ = split_non_expanding_rules(rules)
        overrides = build_esto_overrides(ordinary)
        required = pd.DataFrame(
            [
                {"component_esto_flow": "09.01.01 Electricity plants", "component_esto_product": "01.05 Lignite"},
                {"component_esto_flow": "09.02.01 Electricity plants", "component_esto_product": "01.05 Lignite"},
            ]
        )
        edges, groups = build_manual_override_edges(overrides, "leap_vs_esto", required)
        assert edges == [
            (
                ("09.01.01 Electricity plants", "01.05 Lignite"),
                ("09.02.01 Electricity plants", "01.05 Lignite"),
            )
        ]
        assert len(groups) == 1


class TestScenario3FrontierCheck:
    def test_standalone_subtotal_passes(self) -> None:
        common_rows = pd.DataFrame(
            [
                {"common_row_id": "row_subtotal", "component_esto_flow": "16.03-16.04 Agriculture and fishing", "component_esto_product": "p"},
                {"common_row_id": "row_detail_a", "component_esto_flow": "16.03 Agriculture", "component_esto_product": "p"},
                {"common_row_id": "row_detail_b", "component_esto_flow": "16.04 Fishing", "component_esto_product": "p"},
            ]
        )
        labels = {"16.03-16.04 Agriculture and fishing": "nonexp_16_03_16_04_agriculture_and_fishing"}
        children = {"16.03-16.04 Agriculture and fishing": ["16.03 Agriculture", "16.04 Fishing"]}
        result = build_non_expanding_frontier_check(common_rows, labels, children, "leap_vs_esto")
        assert list(result["check_status"]) == ["ok"]

    def test_subtotal_sharing_row_with_child_is_violation(self) -> None:
        common_rows = pd.DataFrame(
            [
                {"common_row_id": "row_merged", "component_esto_flow": "16.03-16.04 Agriculture and fishing", "component_esto_product": "p"},
                {"common_row_id": "row_merged", "component_esto_flow": "16.03 Agriculture", "component_esto_product": "p"},
            ]
        )
        labels = {"16.03-16.04 Agriculture and fishing": "nonexp_16_03_16_04_agriculture_and_fishing"}
        children = {"16.03-16.04 Agriculture and fishing": ["16.03 Agriculture", "16.04 Fishing"]}
        result = build_non_expanding_frontier_check(common_rows, labels, children, "leap_vs_esto")
        row = result.iloc[0]
        assert row["check_status"] == "violation"
        assert "subtotal_shares_common_row_with_declared_child" in row["violation_reason"]
        assert "row_merged" in row["violating_common_row_ids"]


class TestScenario7SuppressedEdges:
    def _relationships(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                # Ordinary leaf mappings: distinct source rows, one target each.
                {
                    "use_case": "leap_to_esto_balance_conversion",
                    "source_system": "LEAP",
                    "source_flow": "Freight road",
                    "source_product": "Diesel",
                    "target_flow": "15.02.02 Freight road",
                    "target_product": "07.07 Gas/diesel oil",
                    "esto_pair_is_subtotal": False,
                    "is_rollup_derived": False,
                    "allocation_method": "direct",
                },
                {
                    "use_case": "leap_to_esto_balance_conversion",
                    "source_system": "LEAP",
                    "source_flow": "Passenger road",
                    "source_product": "Diesel",
                    "target_flow": "15.02.01 Passenger road",
                    "target_product": "07.07 Gas/diesel oil",
                    "esto_pair_is_subtotal": False,
                    "is_rollup_derived": False,
                    "allocation_method": "direct",
                },
                # Duplicate-up rows share the rolled source label "Road": without
                # the exclusion they would union the two leaf targets.
                {
                    "use_case": "leap_to_esto_balance_conversion",
                    "source_system": "LEAP",
                    "source_flow": "Road",
                    "source_product": "Diesel",
                    "target_flow": "15.02.02 Freight road",
                    "target_product": "07.07 Gas/diesel oil",
                    "esto_pair_is_subtotal": False,
                    "is_rollup_derived": True,
                    "allocation_method": "direct",
                },
                {
                    "use_case": "leap_to_esto_balance_conversion",
                    "source_system": "LEAP",
                    "source_flow": "Road",
                    "source_product": "Diesel",
                    "target_flow": "15.02.01 Passenger road",
                    "target_product": "07.07 Gas/diesel oil",
                    "esto_pair_is_subtotal": False,
                    "is_rollup_derived": True,
                    "allocation_method": "direct",
                },
            ]
        )

    def test_rollup_derived_rows_do_not_create_edges_and_are_published(self) -> None:
        edges, aggregates, suppressed = build_source_aggregate_edges(
            self._relationships(),
            comparison_scope="leap_vs_esto",
            aggregate_source_systems=["LEAP", "NINTH"],
        )
        assert edges == []
        assert aggregates.empty
        assert len(suppressed) == 2
        assert set(suppressed["source_flow"]) == {"Road"}
        assert set(suppressed["exclusion_reason"]) == {"is_rollup_derived"}
        assert set(suppressed["suppressed_component_flow"]) == {
            "15.02.01 Passenger road",
            "15.02.02 Freight road",
        }


class TestUnresolvedQa:
    def test_missing_direct_mapping_is_flagged(self) -> None:
        catalogue = build_non_expanding_rollup_catalogue(
            {
                "leap_rollup_rules": pd.DataFrame(
                    [
                        {
                            "input_leap_sector_name_full_path": "CHP plants",
                            "input_raw_leap_fuel_name": "",
                            "rolled_leap_sector_name_full_path": "Power",
                            "rolled_raw_leap_fuel_name": "",
                            "parent_flow_label": "Total transformation sector",
                            "child_flow_labels": "CHP plants; Heat plants",
                            "Note": "",
                        }
                    ]
                ),
            }
        )
        relationships = pd.DataFrame(
            [
                {
                    "source_system": "LEAP",
                    "source_flow": "CHP plants",
                    "include_in_use_case": "True",
                    "is_rollup_derived": "False",
                }
            ]
        )
        unresolved = build_unresolved_non_expanding_qa(catalogue, relationships, known_esto_flows=set())
        assert list(unresolved["unresolved_reason"]) == ["rolled_label_has_no_direct_included_mapping"]

    def test_fully_mapped_rule_produces_no_rows(self) -> None:
        catalogue = build_non_expanding_rollup_catalogue(
            {
                "leap_rollup_rules": pd.DataFrame(
                    [
                        {
                            "input_leap_sector_name_full_path": "CHP plants",
                            "input_raw_leap_fuel_name": "",
                            "rolled_leap_sector_name_full_path": "Power",
                            "rolled_raw_leap_fuel_name": "",
                            "parent_flow_label": "",
                            "child_flow_labels": "",
                            "Note": "",
                        }
                    ]
                ),
            }
        )
        relationships = pd.DataFrame(
            [
                {"source_system": "LEAP", "source_flow": "CHP plants", "include_in_use_case": "True", "is_rollup_derived": "False"},
                {"source_system": "LEAP", "source_flow": "Power", "include_in_use_case": "True", "is_rollup_derived": "False"},
            ]
        )
        unresolved = build_unresolved_non_expanding_qa(catalogue, relationships, known_esto_flows=set())
        assert unresolved.empty
