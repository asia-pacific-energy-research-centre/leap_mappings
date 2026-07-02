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
    SHEET_CONFIGS,
    build_relationship_rows,
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
        "9th_sector": "12_total_final_consumption",
        "9th_fuel": "15_solid_biomass",
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
