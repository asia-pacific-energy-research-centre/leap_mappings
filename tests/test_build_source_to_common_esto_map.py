"""Tests for the any-dataset -> common ESTO map (overnight work program W6,
2026-08-06/07).

The expected counts follow the promoted mapping-generation manifest. They were
refreshed after the domestic-demand TFC boundary added source pairs, the
registry refresh added structural links, and MAPQ-048 retained components
supported by the endpoint year of any maintained ESTO vintage.
"""

from __future__ import annotations

from codebase.mapping_tools.build_source_to_common_esto_map import (
    _participating_source_systems,
    build_source_to_common_esto_map,
)


def test_zero_fan_out_across_every_scope():
    source_to_common_map, _coverage = build_source_to_common_esto_map()
    for (scope, source_system, flow, product), group in source_to_common_map.groupby(
        ["comparison_scope", "source_system", "source_flow", "source_product"]
    ):
        assert group["common_row_id"].nunique() == 1, (
            f"Fan-out: {(scope, source_system, flow, product)} resolves to "
            f"{group['common_row_id'].nunique()} common rows"
        )


def test_esto_leap_ninth_scope_matches_the_w1_finding():
    source_to_common_map, coverage = build_source_to_common_esto_map()
    scope_map = source_to_common_map[source_to_common_map["comparison_scope"] == "esto_leap_ninth"]
    scope_coverage = coverage[coverage["comparison_scope"] == "esto_leap_ninth"]

    leap_mapped = scope_map[scope_map["source_system"] == "LEAP"][
        ["source_flow", "source_product"]
    ].drop_duplicates()
    leap_unmapped = scope_coverage[scope_coverage["source_system"] == "LEAP"]

    assert len(leap_mapped) == 2992
    assert len(leap_unmapped) == 3417

    ninth_mapped = scope_map[scope_map["source_system"] == "NINTH"][
        ["source_flow", "source_product"]
    ].drop_duplicates()
    ninth_unmapped = scope_coverage[scope_coverage["source_system"] == "NINTH"]
    assert len(ninth_mapped) == 1980
    assert len(ninth_unmapped) == 0


def test_esto_source_system_is_never_included():
    source_to_common_map, coverage = build_source_to_common_esto_map()
    assert "ESTO" not in set(source_to_common_map["source_system"])
    assert "ESTO" not in set(coverage["source_system"])


def test_participating_source_systems_reads_scope_name():
    assert _participating_source_systems("esto_leap") == {"LEAP"}
    assert _participating_source_systems("esto_leap_ninth") == {"LEAP", "NINTH"}
    assert _participating_source_systems("esto_extended_leap_ninth") == {"LEAP", "NINTH"}


def test_participating_source_systems_rejects_unknown_scope_name():
    try:
        _participating_source_systems("esto_only")
    except ValueError:
        return
    raise AssertionError("expected ValueError for a scope naming no known source")
