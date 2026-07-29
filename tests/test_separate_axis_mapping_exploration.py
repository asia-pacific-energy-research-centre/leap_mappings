"""Focused tests for the isolated separate-axis mapping prototype."""

import os
from pathlib import Path

import pandas as pd
import pytest

from codebase.separate_axis_mapping_exploration_functions import (
    RELATIONSHIP_KEY_COLUMNS,
    add_ninth_pair_columns,
    analyse_axis_components,
    annotate_pair_universe_temporal_evidence,
    apply_generated_overrides,
    apply_source_once_fixture,
    build_compiled_mapping_sheet_frames,
    build_ninth_valid_pair_registry_bundle,
    build_common_graph_membership_in_memory,
    build_registry_scope_lookups,
    build_valid_pair_registry,
    compare_compiled_relationships,
    compare_registry_snapshots,
    compile_axis_relationships,
    derive_axis_mappings,
    select_alias_candidate,
)
from codebase.mapping_tools.leap_pair_registry import (
    build_source_manifest,
    derive_leap_balance_structure,
    parse_leap_branch_paths_to_pairs,
    source_manifest_changed,
)


def _relationship(
    source_flow: str,
    source_product: str,
    target_flow: str,
    target_product: str,
) -> dict[str, object]:
    return {
        "mapping_name": "leap_to_esto",
        "comparison_scope": "ESTO",
        "source_system": "LEAP",
        "source_flow": source_flow,
        "source_product": source_product,
        "target_system": "ESTO",
        "target_flow": target_flow,
        "target_product": target_product,
        "source_pair_is_subtotal": False,
        "target_pair_is_subtotal": False,
        "notes": "",
    }


def test_leap_pair_parser_uses_demand_leaves_and_transformation_fuel_roles() -> None:
    paths = [
        r"Demand\Industry",
        r"Demand\Industry\Iron and steel",
        r"Demand\Industry\Iron and steel\Natural gas",
        r"Demand\All demand aggregated",
        r"Demand\All demand aggregated\Industry",
        r"Demand\All demand aggregated\Industry\Electricity",
        r"Transformation\Electricity Generation",
        r"Transformation\Electricity Generation\Output Fuels",
        r"Transformation\Electricity Generation\Output Fuels\Electricity",
        r"Transformation\Electricity Generation\Processes",
        r"Transformation\Electricity Generation\Processes\Coal",
        r"Transformation\Electricity Generation\Processes\Coal\Feedstock Fuels",
        r"Transformation\Electricity Generation\Processes\Coal\Feedstock Fuels\Coal",
        r"Transformation\Electricity Generation\Processes\Battery",
        r"Transformation\Electricity Generation\Processes\Old_do not use",
        r"Transformation\Electricity Generation\Processes\Old_do not use\Feedstock Fuels\Coal",
    ]

    pairs, diagnostics = parse_leap_branch_paths_to_pairs(
        paths,
        source_kind="test",
        source_id="test.xlsx",
        source_sheet="Export",
    )

    assert set(pairs[["flow", "product"]].itertuples(index=False, name=None)) == {
        ("Industry/Iron and steel", "Natural gas"),
        ("All demand aggregated/Industry", "Electricity"),
        (r"Demand\All demand aggregated\Industry", "Electricity"),
        ("Electricity Generation", "Electricity"),
        ("Electricity Generation/Processes/Coal", "Coal"),
    }
    diagnostic_statuses = set(diagnostics["status"])
    assert "excluded_non_energy_or_unrecognised_leaf" in diagnostic_statuses
    assert "excluded_legacy_do_not_use" in diagnostic_statuses


def test_leap_balance_structure_derives_report_rows_and_fuel_catalogue() -> None:
    paths = [
        r"Demand\All demand aggregated",
        r"Demand\All demand aggregated\Natural gas",
        r"Demand\Industry",
        r"Demand\Industry\Iron and steel",
        r"Demand\Industry\Iron and steel\Electricity",
        r"Transformation\Electricity Generation",
        r"Transformation\Electricity Generation\Processes",
        r"Transformation\Electricity Generation\Processes\Coal",
        r"Transformation\Electricity Generation\Processes\Coal\Feedstock Fuels",
        r"Transformation\Electricity Generation\Processes\Coal\Feedstock Fuels\Coal",
    ]

    flows, catalogue = derive_leap_balance_structure(
        paths,
        source_kind="export_template",
        source_id="template.xlsx",
        source_sheet="Export",
        include_fixed_flows=True,
    )

    assert {
        "Production",
        "Total Transformation",
        "All demand aggregated",
        "All demand aggregated/Natural gas",
        "Industry",
        "Industry/Iron and steel",
        "Electricity Generation",
        "Electricity Generation/Coal",
    }.issubset(set(flows["flow"]))
    assert set(catalogue["product"]) == {"Natural gas"}


def test_leap_source_manifest_detects_content_and_timestamp_updates(
    tmp_path: Path,
) -> None:
    source = tmp_path / "template.xlsx"
    source.write_bytes(b"first")
    source_definition = [
        {
            "source_kind": "export_template",
            "source_id": source.name,
            "path": source,
        }
    ]
    first = build_source_manifest(source_definition)
    unchanged = build_source_manifest(source_definition)
    changed, reason = source_manifest_changed(unchanged, first)
    assert not changed
    assert reason == "source_workbooks_unchanged"

    stat = source.stat()
    os.utime(
        source,
        ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000),
    )
    timestamp_only = build_source_manifest(source_definition)
    changed, reason = source_manifest_changed(timestamp_only, first)
    assert changed
    assert reason == "source_workbook_set_or_fingerprint_changed"

    source.write_bytes(b"second")
    second = build_source_manifest(source_definition)
    changed, reason = source_manifest_changed(second, first)
    assert changed
    assert reason == "source_workbook_set_or_fingerprint_changed"


def test_est_o_registry_distinguishes_data_valid_and_zero_only(tmp_path: Path) -> None:
    source = tmp_path / "esto_2025.csv"
    pd.DataFrame(
        [
            {
                "economy": "01AUS",
                "flows": "01 Production",
                "products": "01 Coal",
                "is_subtotal": False,
                "2022": 0,
                "2023": 5,
            },
            {
                "economy": "20USA",
                "flows": "01 Production",
                "products": "01 Coal",
                "is_subtotal": False,
                "2022": 4,
                "2023": 0,
            },
            {
                "economy": "01AUS",
                "flows": "02 Imports",
                "products": "02 Oil",
                "is_subtotal": True,
                "2022": 0,
                "2023": 0,
            },
        ]
    ).to_csv(source, index=False)

    registry, manifest = build_valid_pair_registry(source, "ESTO", chunk_size=1)

    coal = registry[
        registry["flow"].eq("01 Production")
        & registry["product"].eq("01 Coal")
    ].iloc[0]
    oil = registry[
        registry["flow"].eq("02 Imports")
        & registry["product"].eq("02 Oil")
    ].iloc[0]
    assert coal["pair_status"] == "data_valid"
    assert coal["first_observed_year"] == 2022
    assert coal["last_observed_year"] == 2023
    assert coal["economy_support_count"] == 2
    assert oil["pair_status"] == "zero_only"
    assert bool(oil["pair_is_subtotal"])
    assert manifest["data_valid_pair_count"] == 1
    assert manifest["zero_only_pair_count"] == 1


def test_ninth_registry_uses_most_specific_pair_and_scenario_scope(tmp_path: Path) -> None:
    source = tmp_path / "ninth_20251106.csv"
    rows = []
    for scenario, value in [("reference", 3), ("target", 7)]:
        rows.append(
            {
                "economy": "01_AUS",
                "scenarios": scenario,
                "sectors": "09_total_transformation_sector",
                "sub1sectors": "09_01_electric_power",
                "sub2sectors": "x",
                "sub3sectors": "x",
                "sub4sectors": "x",
                "fuels": "17_electricity",
                "subfuels": "x",
                "subtotal_layout": False,
                "subtotal_results": False,
                "2023": value,
            }
        )
    pd.DataFrame(rows).to_csv(source, index=False)

    registry, _ = build_valid_pair_registry(
        source,
        "NINTH",
        scenario_scope="reference",
        chunk_size=1,
    )

    assert len(registry) == 1
    assert registry.iloc[0]["flow"] == "09_01_electric_power"
    assert registry.iloc[0]["product"] == "17_electricity"
    assert registry.iloc[0]["scenarios_observed"] == "reference"


def test_ninth_single_pass_bundle_matches_individual_scope(tmp_path: Path) -> None:
    source = tmp_path / "ninth_20251106.csv"
    pd.DataFrame(
        [
            {
                "economy": "01_AUS",
                "scenarios": scenario,
                "sectors": "09",
                "sub1sectors": "09_01",
                "sub2sectors": "x",
                "sub3sectors": "x",
                "sub4sectors": "x",
                "fuels": "17",
                "subfuels": "x",
                "subtotal_layout": False,
                "subtotal_results": False,
                "2023": value,
            }
            for scenario, value in [("reference", 3), ("target", 0)]
        ]
    ).to_csv(source, index=False)
    individual, _ = build_valid_pair_registry(
        source,
        "NINTH",
        scenario_scope="reference",
        chunk_size=1,
    )
    bundled, _ = build_ninth_valid_pair_registry_bundle(
        source,
        chunk_size=1,
    )["reference"]
    compare_columns = [
        "flow",
        "product",
        "pair_status",
        "first_observed_year",
        "last_observed_year",
        "economy_support_count",
        "nonzero_observation_count",
        "scenarios_observed",
    ]
    pd.testing.assert_frame_equal(
        individual[compare_columns].reset_index(drop=True),
        bundled[compare_columns].reset_index(drop=True),
    )


def test_add_ninth_pair_columns_ignores_x_placeholders() -> None:
    frame = pd.DataFrame(
        [
            {
                "sectors": "09",
                "sub1sectors": "09_01",
                "sub2sectors": "x",
                "fuels": "17",
                "subfuels": "x",
            }
        ]
    )
    result = add_ninth_pair_columns(frame)
    assert result.iloc[0]["flow"] == "09_01"
    assert result.iloc[0]["product"] == "17"


def test_registry_delta_retains_one_vintage_disappearance() -> None:
    common = {
        "pair_is_subtotal": False,
        "flow_is_parent": False,
        "product_is_parent": False,
        "source_fingerprint": "old",
        "source_vintage": "2024",
    }
    previous = pd.DataFrame(
        [
            {"flow": "A", "product": "X", "pair_status": "data_valid", **common},
            {"flow": "B", "product": "Y", "pair_status": "data_valid", **common},
        ]
    )
    current = pd.DataFrame(
        [
            {
                "flow": "A",
                "product": "X",
                "pair_status": "zero_only",
                **{**common, "source_fingerprint": "new", "source_vintage": "2025"},
            },
            {
                "flow": "C",
                "product": "Z",
                "pair_status": "data_valid",
                **{**common, "source_fingerprint": "new", "source_vintage": "2025"},
            },
        ]
    )
    delta = compare_registry_snapshots(previous, current)
    by_pair = delta.set_index(["flow", "product"])
    assert by_pair.loc[("A", "X"), "delta_status"] == "status_changed"
    assert by_pair.loc[("B", "Y"), "recommended_mapping_action"] == (
        "retain_mapping_and_mark_pair_pending"
    )
    assert by_pair.loc[("C", "Z"), "delta_status"] == "added"


def test_axis_compiler_filters_cartesian_pairs_and_overrides_restore_exact_set() -> None:
    current = pd.DataFrame(
        [
            _relationship("F1", "P1", "T1", "Q1"),
            _relationship("F1", "P2", "T1", "Q2"),
            _relationship("F2", "P1", "T2", "Q2"),
        ]
    )
    flow, product = derive_axis_mappings(current)
    registry = pd.DataFrame(
        [
            {"flow": "T1", "product": "Q1", "pair_status": "data_valid"},
            {"flow": "T1", "product": "Q2", "pair_status": "data_valid"},
            {"flow": "T2", "product": "Q2", "pair_status": "data_valid"},
            # T2/Q1 is the Cartesian combination that strict filtering rejects.
        ]
    )
    lookups = build_registry_scope_lookups(registry, pd.DataFrame())
    candidates = compile_axis_relationships(current, flow, product, lookups)
    comparison, source_summary, overrides = compare_compiled_relationships(
        current,
        candidates,
    )
    restored = apply_generated_overrides(candidates, overrides)

    assert set(restored.itertuples(index=False, name=None)) == set(
        current[RELATIONSHIP_KEY_COLUMNS].itertuples(index=False, name=None)
    )
    assert comparison["relationship_status"].eq("extra_factorised_relationship").sum() == 1
    assert source_summary["extra_target_count"].sum() == 1
    assert overrides["override_action"].eq("exclude").sum() == 1


def test_axis_component_contract_rejects_only_connected_many_to_many() -> None:
    common = {
        "mapping_name": "leap_to_esto",
        "comparison_scope": "ESTO",
        "source_system": "LEAP",
        "target_system": "ESTO",
        "relationship_semantics": "",
        "notes": "",
    }
    flow_axis = pd.DataFrame(
        [
            {**common, "source_flow": "A", "target_flow": "X"},
            {**common, "source_flow": "A", "target_flow": "Y"},
            {**common, "source_flow": "B", "target_flow": "Z"},
            {**common, "source_flow": "C", "target_flow": "Z"},
            {**common, "source_flow": "D", "target_flow": "U"},
            {**common, "source_flow": "D", "target_flow": "V"},
            {**common, "source_flow": "E", "target_flow": "V"},
        ]
    )
    annotated, inventory = analyse_axis_components(flow_axis, "flow")

    counts = inventory["axis_component_cardinality"].value_counts().to_dict()
    assert counts == {
        "one_to_many": 1,
        "many_to_one": 1,
        "many_to_many": 1,
    }
    blocking = inventory[
        inventory["axis_contract_status"].eq(
            "blocking_many_to_many_axis_component"
        )
    ]
    assert len(blocking) == 1
    assert blocking.iloc[0]["source_keys"] == "D|E"
    assert blocking.iloc[0]["target_keys"] == "U|V"
    assert annotated["axis_component_id"].nunique() == 3


def test_pair_universe_retains_structure_and_labels_temporal_evidence() -> None:
    registry = pd.DataFrame(
        [
            {
                "dataset": "ESTO",
                "flow": "F1",
                "product": "P1",
                "first_observed_year": 2020,
                "last_observed_year": 2023,
                "pair_status": "data_valid",
            },
            {
                "dataset": "NINTH",
                "flow": "S1",
                "product": "Q1",
                "first_observed_year": 2024,
                "last_observed_year": 2050,
                "pair_status": "data_valid",
            },
            {
                "dataset": "NINTH",
                "flow": "S2",
                "product": "Q2",
                "first_observed_year": pd.NA,
                "last_observed_year": pd.NA,
                "pair_status": "zero_only",
            },
        ]
    )
    result = annotate_pair_universe_temporal_evidence(registry, 2023)

    by_pair = result.set_index(["flow", "product"])
    assert bool(by_pair.loc[("F1", "P1"), "historical_boundary_active"])
    assert bool(by_pair.loc[("S1", "Q1"), "projection_future_active"])
    assert (
        by_pair.loc[("S2", "Q2"), "temporal_evidence_status"]
        == "structural_zero_only"
    )
    assert result["pair_universe_member"].all()


def test_compiler_can_use_exact_source_universe_and_zero_only_target_pairs() -> None:
    current = pd.DataFrame([_relationship("S1", "P1", "T1", "Q1")])
    flow = pd.DataFrame(
        [
            {
                "mapping_name": "leap_to_esto",
                "comparison_scope": "ESTO",
                "source_system": "LEAP",
                "source_flow": "S1",
                "target_system": "ESTO",
                "target_flow": "T1",
            },
            {
                "mapping_name": "leap_to_esto",
                "comparison_scope": "ESTO",
                "source_system": "LEAP",
                "source_flow": "S2",
                "target_system": "ESTO",
                "target_flow": "T2",
            },
        ]
    )
    product = pd.DataFrame(
        [
            {
                "mapping_name": "leap_to_esto",
                "comparison_scope": "ESTO",
                "source_system": "LEAP",
                "source_product": "P1",
                "target_system": "ESTO",
                "target_product": "Q1",
            }
        ]
    )
    source_universe = pd.DataFrame(
        [
            {
                "dataset": "LEAP",
                "flow": "S1",
                "product": "P1",
                "pair_exists_in_dataset": True,
                "pair_universe_authority": "fixture",
            },
            {
                "dataset": "LEAP",
                "flow": "S2",
                "product": "P1",
                "pair_exists_in_dataset": True,
                "pair_universe_authority": "fixture",
            },
        ]
    )
    target_registry = pd.DataFrame(
        [
            {"flow": "T1", "product": "Q1", "pair_status": "data_valid"},
            {"flow": "T2", "product": "Q1", "pair_status": "zero_only"},
        ]
    )
    compiled = compile_axis_relationships(
        current,
        flow,
        product,
        build_registry_scope_lookups(target_registry, pd.DataFrame()),
        source_pair_universes={"LEAP": source_universe},
        allowed_target_pair_statuses=("data_valid", "zero_only"),
    )

    assert set(
        compiled.loc[
            compiled["registry_allowed"],
            ["source_flow", "target_flow"],
        ].itertuples(index=False, name=None)
    ) == {("S1", "T1"), ("S2", "T2")}
    assert compiled["target_pair_exists_in_dataset"].all()


def test_compiled_sheet_frames_match_maintained_pair_sheet_columns() -> None:
    current = pd.DataFrame([_relationship("S1", "P1", "T1", "Q1")])
    registry = pd.DataFrame(
        [
            {
                "flow": "T1",
                "product": "Q1",
                "pair_is_subtotal": True,
            }
        ]
    )
    outputs = build_compiled_mapping_sheet_frames(
        current,
        current,
        {("ESTO", "ESTO"): registry},
    )
    leap_esto = outputs["leap_combined_esto"]

    assert list(leap_esto.columns) == [
        "leap_sector_name_full_path",
        "raw_leap_fuel_name",
        "esto_flow",
        "esto_product",
        "leap_is_subtotal",
        "esto_pair_is_subtotal",
        "duplicate_to_remove",
        "esto_dataset_scope",
    ]
    assert not bool(leap_esto.iloc[0]["leap_is_subtotal"])
    assert not bool(leap_esto.iloc[0]["duplicate_to_remove"])


def test_source_once_delivery_handles_many_to_one_recombine_and_allocation() -> None:
    source = pd.DataFrame(
        [
            {"source_id": "direct", "value": 4.0},
            {"source_id": "many", "value": 6.0},
            {"source_id": "recombine", "value": 10.0},
            {"source_id": "allocate", "value": 8.0},
        ]
    )
    membership = pd.DataFrame(
        [
            {
                "source_id": "direct",
                "common_row_id": "C1",
                "relationship_semantics": "direct",
                "component_flow": "A",
            },
            {
                "source_id": "many",
                "common_row_id": "C1",
                "relationship_semantics": "many_to_one",
                "component_flow": "B",
            },
            {
                "source_id": "recombine",
                "common_row_id": "C2",
                "relationship_semantics": "recombine_to_common_row",
                "component_flow": "C",
            },
            {
                "source_id": "recombine",
                "common_row_id": "C2",
                "relationship_semantics": "recombine_to_common_row",
                "component_flow": "D",
            },
            {
                "source_id": "allocate",
                "common_row_id": "C3",
                "relationship_semantics": "allocate_across_common_rows",
                "allocation_share": 0.25,
            },
            {
                "source_id": "allocate",
                "common_row_id": "C4",
                "relationship_semantics": "allocate_across_common_rows",
                "allocation_share": 0.75,
            },
        ]
    )
    delivered, lineage = apply_source_once_fixture(source, membership)
    values = delivered.set_index("common_row_id")["delivered_value"].to_dict()

    assert values == {"C1": 10.0, "C2": 10.0, "C3": 2.0, "C4": 6.0}
    assert len(lineage[lineage["source_id"].eq("recombine")]) == 2
    assert delivered["delivered_value"].sum() == source["value"].sum()


def test_source_once_delivery_rejects_unresolved_many_to_many() -> None:
    source = pd.DataFrame(
        [{"source_id": "A", "value": 1.0}, {"source_id": "B", "value": 2.0}]
    )
    membership = pd.DataFrame(
        [
            {
                "source_id": source_id,
                "common_row_id": common_row_id,
                "relationship_semantics": "unresolved",
            }
            for source_id in ["A", "B"]
            for common_row_id in ["C1", "C2"]
        ]
    )
    with pytest.raises(ValueError, match="Unresolved many-to-many"):
        apply_source_once_fixture(source, membership)


def test_alias_selection_prefers_nonzero_then_priority() -> None:
    candidates = pd.DataFrame(
        [
            {"alias_group_id": "g1", "source_id": "primary", "alias_priority": 1, "value": 0},
            {"alias_group_id": "g1", "source_id": "fallback", "alias_priority": 2, "value": 5},
            {"alias_group_id": "g2", "source_id": "first", "alias_priority": 1, "value": 3},
            {"alias_group_id": "g2", "source_id": "second", "alias_priority": 2, "value": 9},
        ]
    )
    selected = select_alias_candidate(candidates)
    assert set(selected["source_id"]) == {"fallback", "first"}


def test_vectorised_graph_membership_matches_production_edges() -> None:
    from codebase.mapping_tools.build_common_esto_structure import (
        COMPARISON_SCOPES,
        build_connected_components,
        build_required_components,
        build_source_aggregate_edges,
        included_esto_relationships,
    )
    from codebase.mapping_tools.build_energy_balance_relationships import (
        build_default_coverage_exclusions,
    )

    rows = []
    for source_id, target_flow, subtotal, allocation in [
        ("combine", "A", False, "direct"),
        ("combine", "B", False, "direct"),
        ("combine", "C", True, "direct"),
        ("split", "D", False, "equal_share"),
        ("split", "E", False, "equal_share"),
    ]:
        rows.append(
            {
                "include_in_use_case": True,
                "use_case": "leap_to_esto_balance_conversion",
                "source_system": "LEAP",
                "source_flow": source_id,
                "source_product": "P",
                "target_system": "ESTO",
                "target_flow": target_flow,
                "target_product": "X",
                "esto_dataset_scope": "BOTH",
                "esto_pair_is_subtotal": subtotal,
                "is_rollup_derived": False,
                "allocation_method": allocation,
            }
        )
    stage1 = pd.DataFrame(rows)
    workbook = Path(__file__).resolve().parents[1] / "config" / "outlook_mappings_master.xlsx"
    fast = build_common_graph_membership_in_memory(
        stage1,
        workbook,
        pd.DataFrame(),
    )
    fast = fast[fast["comparison_scope"].eq("esto_leap")]
    fast_signatures = {
        frozenset(
            group[["component_esto_flow", "component_esto_product"]]
            .itertuples(index=False, name=None)
        )
        for _, group in fast.groupby("common_row_id")
    }

    scope = "esto_leap"
    config = COMPARISON_SCOPES[scope]
    included, _ = included_esto_relationships(
        stage1,
        build_default_coverage_exclusions(),
        comparison_scope=scope,
        use_cases=config["use_cases"],
    )
    required = build_required_components(included)
    edges, _, _ = build_source_aggregate_edges(
        included,
        comparison_scope=scope,
        aggregate_source_systems=config["aggregate_source_systems"],
    )
    production_components = build_connected_components(required, edges)
    production_signatures = {
        frozenset(component)
        for component in production_components.values()
    }
    assert fast_signatures == production_signatures
