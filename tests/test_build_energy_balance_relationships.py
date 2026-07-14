"""Tests for build_energy_balance_relationships.

Focused on the strict boolean parser for esto_pair_is_subtotal and on
verifying that relationship output preserves the intended flag counts.
"""
import math
from typing import Any

import numpy as np
import pandas as pd
import pytest

from codebase.mapping_tools.build_energy_balance_relationships import (
    RELATIONSHIP_COLUMNS,
    SHEET_CONFIGS,
    _apply_leap_rollup_rules,
    _apply_ninth_rollup_rules,
    _build_rolled_ninth_sector_to_components,
    build_relationship_rows,
    build_unknown_esto_target_qa,
    build_unknown_ninth_target_qa,
    expand_combined_esto_targets,
    expand_esto_rollup_targets,
    expand_ninth_rollup_targets,
    parse_esto_pair_is_subtotal,
)


# ---------------------------------------------------------------------------
# parse_esto_pair_is_subtotal unit tests
# ---------------------------------------------------------------------------


class TestParseEstoPairIsSubtotal:
    """Strict boolean parser semantics."""

    # --- True ---
    def test_bool_true_returns_true(self) -> None:
        assert parse_esto_pair_is_subtotal(True) is True

    def test_integer_one_returns_true(self) -> None:
        assert parse_esto_pair_is_subtotal(1) is True

    def test_string_one_returns_true(self) -> None:
        assert parse_esto_pair_is_subtotal("1") is True

    def test_string_true_lower_returns_true(self) -> None:
        assert parse_esto_pair_is_subtotal("true") is True

    def test_string_true_mixed_case_returns_true(self) -> None:
        assert parse_esto_pair_is_subtotal("True") is True

    def test_string_yes_returns_true(self) -> None:
        assert parse_esto_pair_is_subtotal("yes") is True

    # --- False ---
    def test_bool_false_returns_false(self) -> None:
        assert parse_esto_pair_is_subtotal(False) is False

    def test_integer_zero_returns_false(self) -> None:
        assert parse_esto_pair_is_subtotal(0) is False

    def test_string_zero_returns_false(self) -> None:
        assert parse_esto_pair_is_subtotal("0") is False

    def test_string_false_lower_returns_false(self) -> None:
        assert parse_esto_pair_is_subtotal("false") is False

    def test_string_false_mixed_case_does_not_become_true(self) -> None:
        # Regression: "False" must NOT be interpreted as truthy.
        assert parse_esto_pair_is_subtotal("False") is False

    def test_string_no_returns_false(self) -> None:
        assert parse_esto_pair_is_subtotal("no") is False

    def test_blank_string_returns_false(self) -> None:
        assert parse_esto_pair_is_subtotal("") is False

    def test_whitespace_string_returns_false(self) -> None:
        assert parse_esto_pair_is_subtotal("   ") is False

    def test_none_returns_false(self) -> None:
        assert parse_esto_pair_is_subtotal(None) is False

    # --- Blank Excel / pandas NA values ---
    def test_float_nan_returns_false(self) -> None:
        """bool(float('nan')) is True — the parser must return False instead."""
        assert parse_esto_pair_is_subtotal(float("nan")) is False

    def test_numpy_nan_returns_false(self) -> None:
        """bool(np.nan) is True — the parser must return False instead."""
        assert parse_esto_pair_is_subtotal(np.nan) is False

    def test_pandas_na_returns_false(self) -> None:
        assert parse_esto_pair_is_subtotal(pd.NA) is False

    def test_pandas_nat_returns_false(self) -> None:
        assert parse_esto_pair_is_subtotal(pd.NaT) is False

    def test_math_nan_returns_false(self) -> None:
        assert parse_esto_pair_is_subtotal(math.nan) is False

    # --- Unexpected non-empty values raise ValueError ---
    def test_unexpected_string_raises(self) -> None:
        with pytest.raises(ValueError, match="esto_pair_is_subtotal"):
            parse_esto_pair_is_subtotal("maybe")

    def test_unexpected_numeric_raises(self) -> None:
        with pytest.raises(ValueError, match="esto_pair_is_subtotal"):
            parse_esto_pair_is_subtotal(2)

    def test_unexpected_negative_number_raises(self) -> None:
        with pytest.raises(ValueError, match="esto_pair_is_subtotal"):
            parse_esto_pair_is_subtotal(-1)


# ---------------------------------------------------------------------------
# Integration: flag counts in relationship output
# ---------------------------------------------------------------------------

_NINTH_SHEET_CONFIG = next(
    c for c in SHEET_CONFIGS if c["sheet_name"] == "ninth_pairs_to_esto_pairs"
)


def _make_ninth_source_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Minimal DataFrame mimicking a ninth_pairs_to_esto_pairs sheet slice."""
    base = {
        "ninth_sector": "12_total_final_consumption",
        "ninth_fuel": "15_solid_biomass",
        "esto_flow": "12 Total final consumption",
        "esto_product": "15 Solid biomass",
        "esto_pair_is_subtotal": False,
    }
    return pd.DataFrame([{**base, **r} for r in rows])


class TestSubtotalFlagCountsInRelationshipOutput:
    """Verify that the relationship builder preserves the correct flag values."""

    def test_explicit_false_stays_false(self, tmp_path: Any) -> None:
        source_df = _make_ninth_source_df([{"esto_pair_is_subtotal": False}])
        mapping_path = tmp_path / "mappings.xlsx"
        source_df.to_excel(mapping_path, index=False)
        result = build_relationship_rows(source_df, mapping_path, _NINTH_SHEET_CONFIG)
        assert result["esto_pair_is_subtotal"].eq(False).all()

    def test_explicit_true_stays_true(self, tmp_path: Any) -> None:
        source_df = _make_ninth_source_df([{"esto_pair_is_subtotal": True}])
        mapping_path = tmp_path / "mappings.xlsx"
        source_df.to_excel(mapping_path, index=False)
        result = build_relationship_rows(source_df, mapping_path, _NINTH_SHEET_CONFIG)
        assert result["esto_pair_is_subtotal"].eq(True).all()

    def test_blank_nan_becomes_false_not_true(self, tmp_path: Any) -> None:
        """Regression: blank Excel cell (np.nan) must NOT become True."""
        source_df = _make_ninth_source_df([{"esto_pair_is_subtotal": np.nan}])
        mapping_path = tmp_path / "mappings.xlsx"
        source_df.to_excel(mapping_path, index=False)
        result = build_relationship_rows(source_df, mapping_path, _NINTH_SHEET_CONFIG)
        assert result["esto_pair_is_subtotal"].eq(False).all(), (
            "Blank esto_pair_is_subtotal cell must be False, not True. "
            "bool(np.nan) is True — use parse_esto_pair_is_subtotal instead."
        )

    def test_mixed_flags_preserve_correct_counts(self, tmp_path: Any) -> None:
        """Three rows: explicit True, explicit False, blank. Only one should be True."""
        source_df = _make_ninth_source_df(
            [
                {"esto_pair_is_subtotal": True},
                {"esto_pair_is_subtotal": False},
                {"esto_pair_is_subtotal": np.nan},
            ]
        )
        mapping_path = tmp_path / "mappings.xlsx"
        source_df.to_excel(mapping_path, index=False)
        # Each source row generates one row per use_case; collect unique source rows by source_row_number
        result = build_relationship_rows(source_df, mapping_path, _NINTH_SHEET_CONFIG)
        # Deduplicate to one row per source row (use first use_case)
        per_row = result.drop_duplicates("source_row_number").set_index("source_row_number")
        assert per_row.loc[2, "esto_pair_is_subtotal"] == True   # noqa: E712
        assert per_row.loc[3, "esto_pair_is_subtotal"] == False  # noqa: E712
        assert per_row.loc[4, "esto_pair_is_subtotal"] == False  # noqa: E712

    def test_string_false_does_not_become_true(self, tmp_path: Any) -> None:
        """'False' as a string must produce False, not True."""
        source_df = _make_ninth_source_df([{"esto_pair_is_subtotal": "False"}])
        mapping_path = tmp_path / "mappings.xlsx"
        source_df.to_excel(mapping_path, index=False)
        result = build_relationship_rows(source_df, mapping_path, _NINTH_SHEET_CONFIG)
        assert result["esto_pair_is_subtotal"].eq(False).all()


# ---------------------------------------------------------------------------
# _apply_leap_rollup_rules: rolled aggregates that already have a direct
# mapping must not have their component branches' relationships cloned onto
# them (see docs/prompts/investigate_demand_sector_parent_child_mismatches_FINDINGS.md #2/#3).
# ---------------------------------------------------------------------------


def _make_leap_row(
    source_flow: str,
    target_flow: str,
    is_rollup_derived: bool = False,
    source_product: str = "08.01 Natural gas",
) -> dict[str, Any]:
    row = {c: "" for c in RELATIONSHIP_COLUMNS}
    row.update(
        source_system="LEAP",
        source_flow=source_flow,
        source_product=source_product,
        source_sector_path=source_flow,
        source_fuel=source_product,
        target_system="ESTO",
        target_flow=target_flow,
        target_product=source_product,
        is_rollup_derived=is_rollup_derived,
        include_in_use_case=True,
        relationship_id=f"id::{source_flow}::{target_flow}",
        relationship_key=f"id::{source_flow}::{target_flow}::use_case",
        use_case="use_case",
    )
    return row


def _make_leap_to_ninth_row(
    source_flow: str = "Transformation/Power sector",
    target_flow: str = "09_01-09_02,09_x Power sector",
    target_product: str = "17_electricity",
) -> dict[str, Any]:
    row = {c: "" for c in RELATIONSHIP_COLUMNS}
    row.update(
        source_system="LEAP",
        source_flow=source_flow,
        source_product=target_product,
        source_sector_path=source_flow,
        source_fuel=target_product,
        target_system="NINTH",
        target_flow=target_flow,
        target_product=target_product,
        is_rollup_derived=False,
        include_in_use_case=True,
        relationship_id=f"id::{source_flow}::{target_flow}",
        relationship_key=f"id::{source_flow}::{target_flow}::leap_to_ninth_comparison",
        use_case="leap_to_ninth_comparison",
        source_sheet="leap_combined_ninth",
    )
    return row


def _make_ninth_source_row(
    source_flow: str,
    target_flow: str,
    source_product: str = "17_electricity",
) -> dict[str, Any]:
    row = {c: "" for c in RELATIONSHIP_COLUMNS}
    row.update(
        source_system="NINTH",
        source_flow=source_flow,
        source_product=source_product,
        source_sector_path=source_flow,
        source_fuel=source_product,
        target_system="ESTO",
        target_flow=target_flow,
        target_product=source_product,
        is_rollup_derived=False,
        include_in_use_case=True,
        relationship_id=f"id::{source_flow}::{target_flow}",
        relationship_key=f"id::{source_flow}::{target_flow}::ninth_to_esto_balance_conversion",
        use_case="ninth_to_esto_balance_conversion",
    )
    return row


def _make_leap_rule(input_flow: str, rolled_flow: str) -> dict[str, Any]:
    return {
        "input_leap_sector_name_full_path": input_flow,
        "input_raw_leap_fuel_name": "",
        "rolled_leap_sector_name_full_path": rolled_flow,
        "rolled_raw_leap_fuel_name": "",
    }


class TestApplyLeapRollupRulesSkipsAlreadyDirectlyMappedAggregates:
    """Regression for the 14 Industry sector / 15 Transport sector inflation bug."""

    def test_component_with_direct_target_not_cloned_onto_rolled_aggregate(self) -> None:
        """'Industry' already maps directly to '14 Industry sector'; the rollup rule
        that folds 'Industry' into 'Total final consumption' must not clone that
        row, since 'Total final consumption' already has its own direct mapping."""
        relationship_df = pd.DataFrame(
            [
                _make_leap_row("Industry", "14 Industry sector"),
                _make_leap_row("Total final consumption", "12 Total final consumption"),
            ],
            columns=RELATIONSHIP_COLUMNS,
        )
        leap_rules = pd.DataFrame([_make_leap_rule("Industry", "Total final consumption")])

        result = _apply_leap_rollup_rules(relationship_df, leap_rules)

        assert not (
            (result["source_flow"] == "Total final consumption")
            & (result["target_flow"] == "14 Industry sector")
        ).any(), "Total final consumption must not be cloned onto 14 Industry sector's target"

    def test_transport_children_not_doubled_by_rolled_transport(self) -> None:
        """'Transport' already maps directly to '15 Transport sector'; rollup rules
        folding its non-road children into 'Transport' must not clone those
        children's targets, which would double-count into 15.05/15.06."""
        relationship_df = pd.DataFrame(
            [
                _make_leap_row("Transport", "15 Transport sector"),
                _make_leap_row(
                    "Transport non road/Pipeline transport", "15.05 Pipeline transport"
                ),
                _make_leap_row(
                    "Transport non road/Nonspecified transport",
                    "15.06 Non-specified transport",
                ),
            ],
            columns=RELATIONSHIP_COLUMNS,
        )
        leap_rules = pd.DataFrame(
            [
                _make_leap_rule("Transport non road/Pipeline transport", "Transport"),
                _make_leap_rule("Transport non road/Nonspecified transport", "Transport"),
            ]
        )

        result = _apply_leap_rollup_rules(relationship_df, leap_rules)

        assert not (result["source_flow"] == "Transport").any(), (
            "Transport already has a direct mapping; its component branches must not "
            "be cloned onto it"
        )

    def test_rollup_still_applies_when_aggregate_has_no_direct_mapping(self) -> None:
        """Sanity check: legitimate rollups (no pre-existing direct row for the
        rolled aggregate) must still be cloned as before."""
        relationship_df = pd.DataFrame(
            [
                _make_leap_row("Freight road", "15.02 Road"),
                _make_leap_row("Passenger road", "15.02 Road"),
            ],
            columns=RELATIONSHIP_COLUMNS,
        )
        leap_rules = pd.DataFrame(
            [
                _make_leap_rule("Freight road", "Road"),
                _make_leap_rule("Passenger road", "Road"),
            ]
        )

        result = _apply_leap_rollup_rules(relationship_df, leap_rules)

        assert (result["source_flow"] == "Road").sum() == 2
        assert set(result["target_flow"]) == {"15.02 Road"}
        assert result["is_rollup_derived"].all()


class TestRegisteredEstoRollupTargets:
    """Registered rollup tree nodes must stay as full-value relationship rows."""

    def test_combined_registered_rollup_target_is_not_expanded(self) -> None:
        relationship_df = pd.DataFrame(
            [
                _make_leap_row(
                    source_flow="Other sector/Agriculture and fishing",
                    target_flow="16.03-16.04 Agriculture and fishing",
                )
            ],
            columns=RELATIONSHIP_COLUMNS,
        )

        result = expand_combined_esto_targets(
            relationship_df,
            prefix_to_label={
                "16.03": "16.03 Agriculture",
                "16.04": "16.04 Fishing",
            },
            registered_rollup_flows={"16.03-16.04 Agriculture and fishing"},
        )

        assert len(result) == 1
        assert result.iloc[0]["target_flow"] == "16.03-16.04 Agriculture and fishing"

    def test_registered_rollup_target_is_not_split_to_components(self) -> None:
        relationship_df = pd.DataFrame(
            [_make_leap_row("Power sector", "09.01-09.02 Power sector")],
            columns=RELATIONSHIP_COLUMNS,
        )

        result = expand_esto_rollup_targets(
            relationship_df,
            rolled_flow_to_components={
                "09.01-09.02 Power sector": [
                    "09.01 Main activity producer",
                    "09.02 Autoproducers",
                ]
            },
            registered_rollup_flows={"09.01-09.02 Power sector"},
        )

        assert len(result) == 1
        assert result.iloc[0]["target_flow"] == "09.01-09.02 Power sector"
        assert result.iloc[0]["allocation_share"] == ""

    def test_unregistered_rollup_target_keeps_fallback_split_behavior(self) -> None:
        relationship_df = pd.DataFrame(
            [_make_leap_row("Source", "Synthetic split target")],
            columns=RELATIONSHIP_COLUMNS,
        )

        result = expand_esto_rollup_targets(
            relationship_df,
            rolled_flow_to_components={
                "Synthetic split target": ["09.01 Main activity producer", "09.02 Autoproducers"]
            },
            registered_rollup_flows=set(),
        )

        assert len(result) == 2
        assert set(result["target_flow"]) == {"09.01 Main activity producer", "09.02 Autoproducers"}
        assert result["allocation_share"].astype(float).tolist() == [0.5, 0.5]
        assert set(result["allocation_source"]) == {"target_dataset_share"}

    def test_registered_rollup_target_is_known_for_unknown_target_qa(self) -> None:
        relationship_df = pd.DataFrame(
            [_make_leap_row("Power sector", "09.01-09.02 Power sector")],
            columns=RELATIONSHIP_COLUMNS,
        )

        qa_df = build_unknown_esto_target_qa(
            relationship_df,
            known_esto_flows={"09.01 Main activity producer", "09.01-09.02 Power sector"},
        )

        assert qa_df.empty


class TestNinthRollupTargetExpansion:
    """NINTH target rollups in leap_combined_ninth expand to real NINTH sectors."""

    def test_build_rolled_ninth_sector_to_components_skips_fuel_specific_rules(self) -> None:
        rules = pd.DataFrame(
            [
                {
                    "input_ninth_sector": "09_01_01_electricity_plants",
                    "input_ninth_fuel": "",
                    "rolled_ninth_sector": "09_01-09_02,09_x Power sector",
                    "rolled_ninth_fuel": "",
                },
                {
                    "input_ninth_sector": "09_01_01_electricity_plants",
                    "input_ninth_fuel": "17_electricity",
                    "rolled_ninth_sector": "fuel_specific_rollup",
                    "rolled_ninth_fuel": "17_electricity",
                },
            ]
        )

        result = _build_rolled_ninth_sector_to_components(rules)

        assert result == {
            "09_01-09_02,09_x Power sector": ["09_01_01_electricity_plants"]
        }

    def test_parent_own_use_rollup_uses_child_frontier_when_available(self) -> None:
        rules = pd.DataFrame(
            [
                {
                    "input_ninth_sector": "09_08_coal_transformation",
                    "input_ninth_fuel": "",
                    "rolled_ninth_sector": "09_08_coal_transformation_incl_own_use",
                    "rolled_ninth_fuel": "",
                    "parent_flow_label": "09 Total transformation sector",
                },
                {
                    "input_ninth_sector": "10_01_05_coke_ovens",
                    "input_ninth_fuel": "",
                    "rolled_ninth_sector": "09_08_coal_transformation_incl_own_use",
                    "rolled_ninth_fuel": "",
                    "parent_flow_label": "09 Total transformation sector",
                },
                {
                    "input_ninth_sector": "09_08_01_coke_ovens",
                    "input_ninth_fuel": "",
                    "rolled_ninth_sector": "09_08_01_coke_ovens_incl_own_use",
                    "rolled_ninth_fuel": "",
                    "parent_flow_label": "09_08_coal_transformation_incl_own_use",
                },
                {
                    "input_ninth_sector": "10_01_05_coke_ovens",
                    "input_ninth_fuel": "",
                    "rolled_ninth_sector": "09_08_01_coke_ovens_incl_own_use",
                    "rolled_ninth_fuel": "",
                    "parent_flow_label": "09_08_coal_transformation_incl_own_use",
                },
                {
                    "input_ninth_sector": "09_08_02_blast_furnaces",
                    "input_ninth_fuel": "",
                    "rolled_ninth_sector": "09_08_02_blast_furnaces_incl_own_use",
                    "rolled_ninth_fuel": "",
                    "parent_flow_label": "09_08_coal_transformation_incl_own_use",
                },
                {
                    "input_ninth_sector": "10_01_07_blast_furnaces",
                    "input_ninth_fuel": "",
                    "rolled_ninth_sector": "09_08_02_blast_furnaces_incl_own_use",
                    "rolled_ninth_fuel": "",
                    "parent_flow_label": "09_08_coal_transformation_incl_own_use",
                },
            ]
        )

        result = _build_rolled_ninth_sector_to_components(rules)

        assert result["09_08_coal_transformation_incl_own_use"] == [
            "09_08_01_coke_ovens_incl_own_use",
            "09_08_02_blast_furnaces_incl_own_use",
        ]

    def test_ninth_target_rollup_expands_to_component_sectors(self) -> None:
        relationship_df = pd.DataFrame(
            [_make_leap_to_ninth_row()],
            columns=RELATIONSHIP_COLUMNS,
        )

        result = expand_ninth_rollup_targets(
            relationship_df,
            {
                "09_01-09_02,09_x Power sector": [
                    "09_01_01_electricity_plants",
                    "09_02_01_electricity_plants",
                ]
            },
        )

        assert len(result) == 2
        assert set(result["target_flow"]) == {
            "09_01_01_electricity_plants",
            "09_02_01_electricity_plants",
        }
        assert set(result["target_product"]) == {"17_electricity"}
        assert result["notes"].str.contains(
            "expanded_from_ninth_rollup: 09_01-09_02,09_x Power sector",
            regex=False,
        ).all()
        assert result["relationship_id"].nunique() == 2

    def test_ninth_target_rollup_supports_nested_rules(self) -> None:
        relationship_df = pd.DataFrame(
            [_make_leap_to_ninth_row(target_flow="nested_power")],
            columns=RELATIONSHIP_COLUMNS,
        )

        result = expand_ninth_rollup_targets(
            relationship_df,
            {
                "nested_power": ["09_01-09_02,09_x Power sector"],
                "09_01-09_02,09_x Power sector": [
                    "09_01_01_electricity_plants",
                    "09_02_01_electricity_plants",
                ],
            },
        )

        assert set(result["target_flow"]) == {
            "09_01_01_electricity_plants",
            "09_02_01_electricity_plants",
        }

    def test_unknown_ninth_target_qa_flags_only_non_real_targets_after_expansion(self) -> None:
        relationship_df = pd.DataFrame(
            [
                _make_leap_to_ninth_row(target_flow="09_01_01_electricity_plants"),
                _make_leap_to_ninth_row(target_flow="future_placeholder"),
            ],
            columns=RELATIONSHIP_COLUMNS,
        )

        qa_df = build_unknown_ninth_target_qa(
            relationship_df,
            known_ninth_sectors={"09_01_01_electricity_plants"},
        )

        assert qa_df["target_flow"].tolist() == ["future_placeholder"]
        assert qa_df["qa_status"].tolist() == ["ninth_target_sector_has_no_ninth_data"]

    def test_source_side_ninth_rollup_mechanics_remain_duplicate_up(self) -> None:
        relationship_df = pd.DataFrame(
            [_make_ninth_source_row("09_01_01_electricity_plants", "09.01.01 Electricity plants")],
            columns=RELATIONSHIP_COLUMNS,
        )
        ninth_rules = pd.DataFrame(
            [
                {
                    "input_ninth_sector": "09_01_01_electricity_plants",
                    "input_ninth_fuel": "",
                    "rolled_ninth_sector": "09_01-09_02,09_x Power sector",
                    "rolled_ninth_fuel": "",
                }
            ]
        )

        result = _apply_ninth_rollup_rules(relationship_df, ninth_rules)

        assert len(result) == 1
        assert result.iloc[0]["source_flow"] == "09_01-09_02,09_x Power sector"
        assert result.iloc[0]["target_flow"] == "09.01.01 Electricity plants"
        assert result.iloc[0]["is_rollup_derived"] == True  # noqa: E712
