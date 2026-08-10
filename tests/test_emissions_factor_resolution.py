"""Smoke test for the emissions factor resolution B1 publish (overnight work
program W5/Phase B, 2026-08-06/07).

The resolution logic itself (subfuel collapse, conflict resolution, the
common-axis join) is a verbatim relocation from
leap_dashboard/tests/test_emissions_page.py, which already covers it
thoroughly. This test only checks the publish entry point's shape and
provenance column, and that the published table matches the shape T5 (the
overnight plan's byte-identical-after-move gate) expects.
"""

from __future__ import annotations

from pathlib import Path

from codebase.mapping_tools.emissions_factor_resolution import (
    build_and_write_b1_factor_table,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_b1_factor_table_publishes_54_rows_with_provenance(tmp_path):
    output_path = tmp_path / "emissions_factor_resolution.csv"
    factors = build_and_write_b1_factor_table(output_path=output_path)

    assert output_path.exists()
    assert len(factors) == 54
    assert set(factors["derived_from"]) == {"ninth"}
    assert {
        "common_product_label",
        "emissions_factor",
        "esto_components",
        "factor_source_keys",
        "factor_set_key",
        "emissions_unit",
        "mapping_axis",
        "derived_from",
    }.issubset(set(factors.columns))
