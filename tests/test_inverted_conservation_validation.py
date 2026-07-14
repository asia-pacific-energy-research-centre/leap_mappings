"""Small 20USA base-year tests for Flavor-A ESTO-to-LEAP conservation."""

import pandas as pd

from codebase.mapping_tools.inverted_conservation_validation import (
    _build_alias_map,
    build_variant_coverage_audit,
    build_no_counterpart_audit,
    compose_direction_edges,
    partition_edges_by_target_variant,
    validate_direction_partition,
)


def _structural() -> pd.DataFrame:
    rows = []

    def add(system, flow, product, common_row):
        rows.append({
            "comparison_scope": "esto_leap",
            "source_system": system,
            "original_source_flow": flow,
            "original_source_product": product,
            "common_row_id": common_row,
        })

    # Clean one-to-one pair.
    add("ESTO", "01.01 Production A", "06.01 Fuel A", "common_a")
    add("LEAP", "Supply/Production A", "Fuel A", "common_a")

    # One ESTO pair connects to two LEAP branches. No split is available.
    add("ESTO", "01.02 Production B", "06.02 Fuel B", "common_b")
    add("LEAP", "Supply/Branch B1", "Fuel B", "common_b")
    add("LEAP", "Supply/Branch B2", "Fuel B", "common_b")

    # Source and target rows which have no counterpart.
    add("ESTO", "01.03 Production C", "06.03 Fuel C", "esto_only_common")
    add("LEAP", "Supply/Hydrogen", "Hydrogen", "leap_only_common")
    return pd.DataFrame(rows)


def _tree() -> pd.DataFrame:
    return pd.DataFrame([
        {"dataset": "esto", "axis": "flow", "code": "01 Production", "parent_code": ""},
        {"dataset": "esto", "axis": "flow", "code": "01.01 Production A", "parent_code": "01 Production"},
        {"dataset": "esto", "axis": "flow", "code": "01.02 Production B", "parent_code": "01 Production"},
        {"dataset": "esto", "axis": "flow", "code": "01.03 Production C", "parent_code": "01 Production"},
        {"dataset": "esto", "axis": "product", "code": "06 Fuels", "parent_code": "", "is_subtotal": True},
        {"dataset": "esto", "axis": "product", "code": "06.01 Fuel A", "parent_code": "06 Fuels"},
        {"dataset": "esto", "axis": "product", "code": "06.02 Fuel B", "parent_code": "06 Fuels"},
        {"dataset": "esto", "axis": "product", "code": "06.03 Fuel C", "parent_code": "06 Fuels"},
    ])


def _raw() -> pd.DataFrame:
    base = {
        "source_system": "ESTO", "economy": "20USA",
        "scenario": "historical", "year": 2023,
    }
    return pd.DataFrame([
        {**base, "source_flow": "01.01 Production A", "source_product": "06.01 Fuel A", "value": 40.0},
        {**base, "source_flow": "01.02 Production B", "source_product": "06.02 Fuel B", "value": 100.0},
        {**base, "source_flow": "01.03 Production C", "source_product": "06.03 Fuel C", "value": 25.0},
    ])


def _run():
    edges, source_gaps, target_gaps = compose_direction_edges(
        _structural(), "ESTO", "LEAP", "esto_leap"
    )
    contributions, summary = validate_direction_partition(
        _raw(), edges, _tree(), "ESTO", "LEAP", "ESTO_TO_LEAP"
    )
    audit = build_no_counterpart_audit(
        _raw(), source_gaps, target_gaps, "ESTO_TO_LEAP", "ESTO", "LEAP",
        "esto_leap",
    )
    return contributions, summary, audit


def test_bijective_pair_resolves_without_changing_value():
    contributions, _, _ = _run()
    row = contributions[
        contributions["source_flow"].eq("01.01 Production A")
        & contributions["validation_axis"].eq("flow")
    ].iloc[0]
    assert row["counting_role"] == "resolved_pair"
    assert row["mapping_status"] == "resolved"
    assert row["value_quality"] == "exact_direct"
    assert row["raw_value"] == 40.0
    assert row["converted_value"] == 40.0


def test_fanout_lists_both_leap_branches_without_splitting_value():
    contributions, _, _ = _run()
    parent_rows = contributions[
        contributions["parent_code"].eq("01 Production")
        & contributions["validation_axis"].eq("flow")
    ]
    source = parent_rows[parent_rows["source_flow"].eq("01.02 Production B")]
    targets = parent_rows[parent_rows["target_flow"].isin([
        "Supply/Branch B1", "Supply/Branch B2"
    ])]
    assert len(source) == 1
    assert source.iloc[0]["raw_value"] == 100.0
    assert pd.isna(source.iloc[0]["contribution_difference"])
    assert source.iloc[0]["mapping_status"] == "unsafe_unallocated_fanout"
    assert set(targets["target_flow"]) == {"Supply/Branch B1", "Supply/Branch B2"}
    assert set(targets["mapping_status"]) == {"unsafe_unallocated_fanout"}
    assert targets["converted_value"].isna().all()
    assert source.iloc[0]["combined_source_value"] == 100.0
    assert source.iloc[0]["involved_target_pairs"] == "Supply/Branch B1 / Fuel B | Supply/Branch B2 / Fuel B"
    assert bool(source.iloc[0]["individual_target_values_available"]) is False
    assert source.iloc[0]["relationship_group_id"] == targets.iloc[0]["relationship_group_id"]


def test_no_counterpart_rows_are_unanchorable_accounting_not_failures():
    _, _, audit = _run()
    source_gap = audit[audit["counterpart_state"].eq("source_without_target")].iloc[0]
    target_gap = audit[audit["counterpart_state"].eq("target_without_source")].iloc[0]
    assert source_gap["source_flow"] == "01.03 Production C"
    assert source_gap["source_value"] == 25.0
    assert target_gap["target_flow"] == "Supply/Hydrogen"
    assert pd.isna(target_gap["source_value"])


def test_breakdown_reproduces_check_and_ids_include_direction():
    _, summary, _ = _run()
    check = summary[
        summary["parent_code"].eq("01 Production")
        & summary["validation_axis"].eq("flow")
    ].iloc[0]
    assert check["check_difference"] == 100.0
    assert abs(check["breakdown_remainder"]) <= 1e-9
    assert bool(check["fully_attributed"]) is False
    assert check["check_id"].startswith("dirchk_")


def test_subtotal_exception_uses_existing_tree_validation_result():
    raw = pd.DataFrame([{
        "source_system": "NINTH", "economy": "20USA", "scenario": "reference",
        "year": 2023, "source_flow": "12_total_final_consumption",
        "source_product": "15_solid_biomass", "value": 1901.0,
    }])
    source_gap = pd.DataFrame([{
        "source_flow": "12_total_final_consumption",
        "source_product": "15_solid_biomass", "common_row_id": "common_biomass",
    }])
    target_gap = pd.DataFrame(columns=["target_flow", "target_product", "common_row_id"])
    tree = pd.DataFrame([{
        "dataset": "ninth", "axis": "fuel", "code": "15_solid_biomass",
        "is_subtotal": True,
    }])

    verified = build_no_counterpart_audit(
        raw, source_gap, target_gap, "NINTH_TO_LEAP", "NINTH", "LEAP",
        "esto_leap_ninth", tree, pd.DataFrame(),
    ).iloc[0]
    assert verified["exception_classification"] == "verified_subtotal_represented_by_children"

    mismatch_validation = pd.DataFrame([{
        "economy": "20_USA", "scenario": "reference", "year": 2023,
        "ninth_sector": "12_total_final_consumption", "ninth_fuel": "15_solid_biomass",
        "difference": 12.5,
    }])
    mismatch = build_no_counterpart_audit(
        raw, source_gap, target_gap, "NINTH_TO_LEAP", "NINTH", "LEAP",
        "esto_leap_ninth", tree, mismatch_validation,
    ).iloc[0]
    assert mismatch["exception_classification"] == "subtotal_children_mismatch"
    assert mismatch["subtotal_validation_difference"] == 12.5


def test_alternative_target_variants_are_checked_separately_and_not_summed():
    edges, _, _ = compose_direction_edges(
        _structural(), "ESTO", "LEAP", "esto_leap"
    )
    config = {
        "target_system": "LEAP",
        "families": {
            "production_b": {
                "variants": {
                    "standard": ["Supply/Branch B1"],
                    "interim": ["Supply/Branch B2"],
                }
            }
        },
    }
    partitions = partition_edges_by_target_variant(edges, "LEAP", config)
    variants = {(family, variant): part for family, variant, part in partitions if family}
    assert set(variants) == {("production_b", "standard"), ("production_b", "interim")}
    assert set(variants[("production_b", "standard")]["target_flow"]) == {"Supply/Branch B1"}
    assert set(variants[("production_b", "interim")]["target_flow"]) == {"Supply/Branch B2"}

    audit = build_variant_coverage_audit(
        partitions, "ESTO_TO_LEAP", "ESTO", "LEAP"
    )
    assert set(audit["variant_coverage_status"]) == {"complete_equivalent_coverage"}
    assert not audit["safe_to_sum_across_variants"].any()

    contributions, summary = validate_direction_partition(
        _raw(), variants[("production_b", "standard")], _tree(),
        "ESTO", "LEAP", "ESTO_TO_LEAP", "production_b", "standard",
    )
    assert set(contributions["target_variant_family"]) == {"production_b"}
    assert set(summary["variant_status"]) == {"verified_alternative_target_variant"}
    assert set(summary["effective_validation_status"]) == {"verified_alternative_target_variant"}
    assert not summary["safe_to_sum_across_variants"].any()


def test_placeholder_alias_buckets_can_collapse_to_one_canonical_target():
    structural = pd.DataFrame([
        {
            "comparison_scope": "esto_leap",
            "source_system": "ESTO",
            "original_source_flow": "01.01 Production A",
            "original_source_product": "06.01 Fuel A",
            "common_row_id": "common_alias",
        },
        {
            "comparison_scope": "esto_leap",
            "source_system": "ESTO",
            "original_source_flow": "01.02 Production B",
            "original_source_product": "06.02 Fuel B",
            "common_row_id": "common_alias",
        },
        {
            "comparison_scope": "esto_leap",
            "source_system": "LEAP",
            "original_source_flow": "Heat plant interim/Heat plant interim",
            "original_source_product": "Electricity",
            "common_row_id": "common_alias",
        },
        {
            "comparison_scope": "esto_leap",
            "source_system": "LEAP",
            "original_source_flow": "Heat plants",
            "original_source_product": "Electricity",
            "common_row_id": "common_alias",
        },
    ])
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "flow", "code": "01 Production", "parent_code": ""},
        {"dataset": "esto", "axis": "flow", "code": "01.01 Production A", "parent_code": "01 Production"},
        {"dataset": "esto", "axis": "flow", "code": "01.02 Production B", "parent_code": "01 Production"},
        {"dataset": "esto", "axis": "product", "code": "06 Fuels", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "06.01 Fuel A", "parent_code": "06 Fuels"},
        {"dataset": "esto", "axis": "product", "code": "06.02 Fuel B", "parent_code": "06 Fuels"},
    ])
    raw = pd.DataFrame([
        {
            "source_system": "ESTO", "economy": "20USA", "scenario": "historical",
            "year": 2023, "source_flow": "01.01 Production A",
            "source_product": "06.01 Fuel A", "value": 40.0,
        },
        {
            "source_system": "ESTO", "economy": "20USA", "scenario": "historical",
            "year": 2023, "source_flow": "01.02 Production B",
            "source_product": "06.02 Fuel B", "value": 60.0,
        },
    ])
    alias_map = _build_alias_map({
        "aliases": [
            {
                "canonical_target_flow": "Heat plants",
                "canonical_target_product": "Electricity",
                "aliases": [
                    {
                        "target_flow": "Heat plant interim/Heat plant interim",
                        "target_product": "Electricity",
                    }
                ],
            }
        ]
    })

    edges, _, _ = compose_direction_edges(
        structural, "ESTO", "LEAP", "esto_leap", alias_map
    )
    contributions, summary = validate_direction_partition(
        raw, edges, tree, "ESTO", "LEAP", "ESTO_TO_LEAP", alias_map=alias_map
    )

    alias_rows = contributions[contributions["counting_role"].eq("resolved_alias_group")]
    assert len(alias_rows) == 2
    assert set(alias_rows["validation_axis"]) == {"flow", "product"}
    assert set(alias_rows["target_flow"]) == {"Heat plants"}
    assert set(alias_rows["target_product"]) == {"Electricity"}
    assert set(alias_rows["raw_value"]) == {100.0}
    assert set(alias_rows["converted_value"]) == {100.0}
    assert set(alias_rows["mapping_status"]) == {"resolved_alias"}

    flow_checks = summary[
        summary["validation_axis"].eq("flow")
        & summary["parent_code"].eq("01 Production")
    ]
    product_checks = summary[
        summary["validation_axis"].eq("product")
        & summary["parent_code"].eq("06 Fuels")
    ]
    assert len(flow_checks) == 1
    assert len(product_checks) == 1
    assert bool(flow_checks.iloc[0]["fully_attributed"]) is True
    assert bool(product_checks.iloc[0]["fully_attributed"]) is True
    assert bool(flow_checks.iloc[0]["lineage_complete"]) is True
    assert bool(product_checks.iloc[0]["lineage_complete"]) is True
    assert flow_checks.iloc[0]["unresolved_source_count"] == 0
    assert product_checks.iloc[0]["unresolved_source_count"] == 0
    assert flow_checks.iloc[0]["unresolved_component_count"] == 0
    assert product_checks.iloc[0]["unresolved_component_count"] == 0


def test_flow_level_wildcard_alias_collapses_every_product_not_just_one():
    """A wildcard alias (no canonical_target_product) must normalize ALL
    fuels under the aliased flow pair, not only the one product an earlier,
    narrower config happened to list."""
    structural = pd.DataFrame([
        {
            "comparison_scope": "esto_leap",
            "source_system": "ESTO",
            "original_source_flow": "01.01 Production A",
            "original_source_product": "06.01 Fuel A",
            "common_row_id": "common_electricity",
        },
        {
            "comparison_scope": "esto_leap",
            "source_system": "ESTO",
            "original_source_flow": "01.02 Production B",
            "original_source_product": "06.01 Fuel A",
            "common_row_id": "common_electricity",
        },
        {
            "comparison_scope": "esto_leap",
            "source_system": "LEAP",
            "original_source_flow": "Heat plant interim/Heat plant interim",
            "original_source_product": "Electricity",
            "common_row_id": "common_electricity",
        },
        {
            "comparison_scope": "esto_leap",
            "source_system": "LEAP",
            "original_source_flow": "Heat plants",
            "original_source_product": "Electricity",
            "common_row_id": "common_electricity",
        },
        {
            "comparison_scope": "esto_leap",
            "source_system": "ESTO",
            "original_source_flow": "01.01 Production A",
            "original_source_product": "06.02 Fuel B",
            "common_row_id": "common_peat",
        },
        {
            "comparison_scope": "esto_leap",
            "source_system": "ESTO",
            "original_source_flow": "01.02 Production B",
            "original_source_product": "06.02 Fuel B",
            "common_row_id": "common_peat",
        },
        {
            "comparison_scope": "esto_leap",
            "source_system": "LEAP",
            "original_source_flow": "Heat plant interim/Heat plant interim",
            "original_source_product": "Peat",
            "common_row_id": "common_peat",
        },
        {
            "comparison_scope": "esto_leap",
            "source_system": "LEAP",
            "original_source_flow": "Heat plants",
            "original_source_product": "Peat",
            "common_row_id": "common_peat",
        },
    ])
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "flow", "code": "01 Production", "parent_code": ""},
        {"dataset": "esto", "axis": "flow", "code": "01.01 Production A", "parent_code": "01 Production"},
        {"dataset": "esto", "axis": "flow", "code": "01.02 Production B", "parent_code": "01 Production"},
        {"dataset": "esto", "axis": "product", "code": "06 Fuels", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "06.01 Fuel A", "parent_code": "06 Fuels"},
        {"dataset": "esto", "axis": "product", "code": "06.02 Fuel B", "parent_code": "06 Fuels"},
    ])
    raw = pd.DataFrame([
        {
            "source_system": "ESTO", "economy": "20USA", "scenario": "historical",
            "year": 2023, "source_flow": "01.01 Production A",
            "source_product": "06.01 Fuel A", "value": 40.0,
        },
        {
            "source_system": "ESTO", "economy": "20USA", "scenario": "historical",
            "year": 2023, "source_flow": "01.02 Production B",
            "source_product": "06.01 Fuel A", "value": 60.0,
        },
        {
            "source_system": "ESTO", "economy": "20USA", "scenario": "historical",
            "year": 2023, "source_flow": "01.01 Production A",
            "source_product": "06.02 Fuel B", "value": 5.0,
        },
        {
            "source_system": "ESTO", "economy": "20USA", "scenario": "historical",
            "year": 2023, "source_flow": "01.02 Production B",
            "source_product": "06.02 Fuel B", "value": 7.0,
        },
    ])
    alias_map = _build_alias_map({
        "aliases": [
            {
                "canonical_target_flow": "Heat plants",
                "aliases": [
                    {"target_flow": "Heat plant interim/Heat plant interim"},
                ],
            }
        ]
    })

    edges, _, _ = compose_direction_edges(
        structural, "ESTO", "LEAP", "esto_leap", alias_map
    )
    contributions, _ = validate_direction_partition(
        raw, edges, tree, "ESTO", "LEAP", "ESTO_TO_LEAP", alias_map=alias_map
    )

    alias_rows = contributions[contributions["counting_role"].eq("resolved_alias_group")]
    resolved_products = set(
        zip(alias_rows["target_flow"], alias_rows["target_product"])
    )
    assert ("Heat plants", "Electricity") in resolved_products
    assert ("Heat plants", "Peat") in resolved_products
