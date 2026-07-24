"""Tests for the generic manual-exception row-matching helpers.

Covers codebase/mapping_issue_exceptions.py's matching_exception_row and
split_allowed_rows, including the numeric_tolerance_columns option used to
require an exact (within-tolerance) value match on top of code/label
matching -- so a stale exception (source data since corrected, or a
different bug landing on the same code/label key) stops matching instead of
silently continuing to apply.
"""

import pandas as pd

from codebase.mapping_issue_exceptions import matching_exception_row, split_allowed_rows


def _exception_df(**overrides) -> pd.DataFrame:
    base = {
        "enabled": True,
        "source_system": "NINTH",
        "parent_code": "16_others",
        "parent_value": "-12.37876",
        "notes": "known NINTH self-inconsistency, reviewed 2026-07-24",
    }
    base.update(overrides)
    return pd.DataFrame([base])


def test_matching_exception_row_requires_exact_string_match_without_tolerance() -> None:
    exception_df = _exception_df()
    candidate = pd.Series({"source_system": "NINTH", "parent_code": "16_others", "parent_value": "-12.37876"})

    assert matching_exception_row(candidate, exception_df) is not None


def test_numeric_tolerance_column_matches_within_tolerance() -> None:
    exception_df = _exception_df()
    # Same value to floating-point noise -- should still match.
    candidate = pd.Series({
        "source_system": "NINTH", "parent_code": "16_others", "parent_value": "-12.378761",
    })

    match = matching_exception_row(
        candidate, exception_df, numeric_tolerance_columns=frozenset({"parent_value"})
    )
    assert match is not None


def test_numeric_tolerance_column_rejects_a_different_value() -> None:
    """A different parent_value must not inherit an old exception's sign-off."""
    exception_df = _exception_df()
    candidate = pd.Series({
        "source_system": "NINTH", "parent_code": "16_others", "parent_value": "-50.0",
    })

    match = matching_exception_row(
        candidate, exception_df, numeric_tolerance_columns=frozenset({"parent_value"})
    )
    assert match is None


def test_without_numeric_tolerance_column_a_different_value_still_matches_by_default() -> None:
    """Baseline: without opting in, parent_value is matched as an exact string
    like any other column -- demonstrating why the opt-in flag matters."""
    exception_df = _exception_df(parent_value="")  # blank column is simply not a match constraint
    candidate = pd.Series({
        "source_system": "NINTH", "parent_code": "16_others", "parent_value": "-999.0",
    })

    match = matching_exception_row(candidate, exception_df)
    assert match is not None


def test_split_allowed_rows_passes_through_numeric_tolerance_columns() -> None:
    exception_df = _exception_df()
    candidates = pd.DataFrame([
        {"source_system": "NINTH", "parent_code": "16_others", "parent_value": "-12.37876"},
        {"source_system": "NINTH", "parent_code": "16_others", "parent_value": "-999.0"},
    ])

    import codebase.mapping_issue_exceptions as mie
    original_loader = mie.load_exception_sheet
    mie.load_exception_sheet = lambda *a, **k: exception_df
    try:
        needs_review, allowed = split_allowed_rows(
            candidates, "irrelevant_sheet", "status", "reason",
            numeric_tolerance_columns=frozenset({"parent_value"}),
        )
    finally:
        mie.load_exception_sheet = original_loader

    assert len(allowed) == 1
    assert allowed.iloc[0]["parent_value"] == "-12.37876"
    assert len(needs_review) == 1
    assert needs_review.iloc[0]["parent_value"] == "-999.0"
