"""Tests for the any-dataset -> common ESTO map (overnight work program W6,
2026-08-06/07).

The expected counts follow the promoted mapping-generation manifest. They were
refreshed after the domestic-demand TFC boundary added source pairs, the
registry refresh added structural links, MAPQ-048 retained components
supported by the endpoint year of any maintained ESTO vintage, and the LNG
inclusive-rollup refresh removed one obsolete direct LEAP pair.
"""

from __future__ import annotations

from codebase.mapping_tools.build_source_to_common_esto_map import (
    MAP_COLUMNS,
    _participating_source_systems,
    build_source_to_common_esto_map,
)


def test_zero_fan_out_across_every_scope():
    source_to_common_map, _coverage = build_source_to_common_esto_map()
    assert list(source_to_common_map.columns) == MAP_COLUMNS
    for (scope, source_system, flow, product), group in source_to_common_map.groupby(
        ["scope", "system", "source_flow", "source_product"]
    ):
        assert group["common_row_id"].nunique() == 1, (
            f"Fan-out: {(scope, source_system, flow, product)} resolves to "
            f"{group['common_row_id'].nunique()} common rows"
        )


def test_esto_leap_ninth_scope_matches_the_promoted_mapping_manifest():
    source_to_common_map, coverage = build_source_to_common_esto_map()
    scope_map = source_to_common_map[source_to_common_map["scope"] == "esto_leap_ninth"]
    scope_coverage = coverage[coverage["comparison_scope"] == "esto_leap_ninth"]

    leap_mapped = scope_map[scope_map["system"] == "LEAP"][
        ["source_flow", "source_product"]
    ].drop_duplicates()
    leap_unmapped = scope_coverage[scope_coverage["source_system"] == "LEAP"]

    assert len(leap_mapped) == 2991
    assert len(leap_unmapped) == 3777

    ninth_mapped = scope_map[scope_map["system"] == "NINTH"][
        ["source_flow", "source_product"]
    ].drop_duplicates()
    ninth_unmapped = scope_coverage[scope_coverage["source_system"] == "NINTH"]
    assert len(ninth_mapped) == 1943
    assert len(ninth_unmapped) == 6
    assert set(ninth_unmapped["target_flow"]) == {"09.01.02.01 Coal CHP"}


def test_each_scope_includes_its_canonical_esto_source():
    source_to_common_map, coverage = build_source_to_common_esto_map()
    base = source_to_common_map[source_to_common_map["scope"] == "esto_leap"]
    extended = source_to_common_map[
        source_to_common_map["scope"] == "esto_extended_leap"
    ]
    assert set(base["system"]) == {"ESTO", "LEAP"}
    assert set(extended["system"]) == {"ESTO_EXTENDED", "LEAP"}
    assert "ESTO" not in set(coverage["source_system"])


def test_leap_placeholder_and_expected_detail_both_survive_publication():
    source_to_common_map, _coverage = build_source_to_common_esto_map()
    leap_flows = set(
        source_to_common_map.loc[
            source_to_common_map["system"].eq("LEAP"), "source_flow"
        ]
    )
    assert {
        "All demand aggregated/Buildings",
        "Buildings",
        "All demand aggregated/Road",
        "Freight road",
        "Passenger road",
    }.issubset(leap_flows)


def test_participating_source_systems_reads_scope_name():
    assert _participating_source_systems("esto_leap") == {"ESTO", "LEAP"}
    assert _participating_source_systems("esto_leap_ninth") == {"ESTO", "LEAP", "NINTH"}
    assert _participating_source_systems("esto_extended_leap_ninth") == {
        "ESTO_EXTENDED", "LEAP", "NINTH"
    }


def test_participating_source_systems_rejects_unknown_scope_name():
    try:
        _participating_source_systems("esto_only")
    except ValueError:
        return
    raise AssertionError("expected ValueError for a scope naming no known source")
