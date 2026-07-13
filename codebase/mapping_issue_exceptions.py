#%%
"""
Helpers for reading manual mapping QA exception sets.

The workbook in config/mapping_issue_exception_sets.xlsx is the source of truth
for reviewed QA exceptions. Workflows may read it and write matched diagnostics,
but should not update it automatically.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
EXCEPTION_WORKBOOK_PATH = REPO_ROOT / "config" / "mapping_issue_exception_sets.xlsx"
EXCEPTION_METADATA_COLUMNS = {"enabled", "notes"}
MATCH_PREFIX_SUFFIX = "*"
UNMODELLED_SOURCE_SHEET = "unmodelled_source_ignored"
_LEADING_CODE = re.compile(r"^\s*0*(\d+)")


def _norm(value: object) -> str:
    """Normalize values used for exception matching."""
    text = " ".join(str(value or "").split())
    return "" if text.lower() in {"nan", "none"} else text


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def leading_code_number(value: object) -> int | None:
    """Return the leading numeric code from an ESTO or 9th label."""
    match = _LEADING_CODE.match(str(value))
    return int(match.group(1)) if match else None


@lru_cache(maxsize=None)
def load_unmodelled_source_codes(
    workbook_path: Path = EXCEPTION_WORKBOOK_PATH,
    sheet_name: str = UNMODELLED_SOURCE_SHEET,
) -> dict[str, set[int]]:
    """Load enabled unmodelled ESTO/9th source codes from the exception workbook."""
    result: dict[str, set[int]] = {"sector": set(), "fuel": set()}
    try:
        source_df = pd.read_excel(workbook_path, sheet_name=sheet_name, dtype=object)
    except (FileNotFoundError, ValueError):
        return result

    if "enabled" in source_df.columns:
        source_df = source_df[source_df["enabled"].map(_truthy)]
    for axis, code in zip(source_df.get("axis", []), source_df.get("code", [])):
        axis_name = str(axis).strip().lower()
        code_number = leading_code_number(code)
        if axis_name in result and code_number is not None:
            result[axis_name].add(code_number)
    return result


def unmodelled_source_flow_mask(
    flows: pd.Series,
    workbook_path: Path = EXCEPTION_WORKBOOK_PATH,
) -> pd.Series:
    """Return rows whose flow belongs to an enabled unmodelled source code."""
    excluded_codes = load_unmodelled_source_codes(workbook_path).get("sector", set())
    if not excluded_codes:
        return pd.Series(False, index=flows.index)
    leading_codes = flows.map(leading_code_number)
    return leading_codes.isin(excluded_codes)


def filter_unmodelled_source_rows(
    source_df: pd.DataFrame,
    flow_column: str = "esto_flow",
    workbook_path: Path = EXCEPTION_WORKBOOK_PATH,
) -> pd.DataFrame:
    """Remove enabled unmodelled source flows from a normalized source table."""
    if source_df.empty or flow_column not in source_df.columns:
        return source_df.copy()
    excluded_mask = unmodelled_source_flow_mask(source_df[flow_column], workbook_path)
    return source_df.loc[~excluded_mask].copy()


@lru_cache(maxsize=None)
def load_exception_sheet(
    sheet_name: str,
    workbook_path: Path = EXCEPTION_WORKBOOK_PATH,
) -> pd.DataFrame:
    """Load enabled rows from one manual exception sheet."""
    if not workbook_path.exists():
        return pd.DataFrame()

    try:
        sheet = pd.read_excel(workbook_path, sheet_name=sheet_name, dtype=str).fillna("")
    except ValueError:
        return pd.DataFrame()

    if "enabled" not in sheet.columns:
        sheet.insert(0, "enabled", True)
    enabled = sheet["enabled"].map(_truthy)
    return sheet[enabled].copy()


def _exception_match_columns(exception_df: pd.DataFrame, candidate_df: pd.DataFrame) -> list[str]:
    """Return exception columns that can be matched against a candidate QA table."""
    return [
        col
        for col in exception_df.columns
        if col not in EXCEPTION_METADATA_COLUMNS and col in candidate_df.columns
    ]


def _row_matches_exception(
    candidate_row: pd.Series,
    exception_row: pd.Series,
    match_columns: list[str],
) -> bool:
    """Return True when all populated exception match columns match the candidate row."""
    populated_columns = [col for col in match_columns if _norm(exception_row.get(col, ""))]
    if not populated_columns:
        return False

    for col in populated_columns:
        expected = _norm(exception_row.get(col, ""))
        actual = _norm(candidate_row.get(col, ""))
        if expected.endswith(MATCH_PREFIX_SUFFIX):
            if not actual.startswith(expected[:-1]):
                return False
        elif actual != expected:
            return False
    return True


def matching_exception_notes(
    candidate_row: pd.Series,
    exception_df: pd.DataFrame,
) -> str:
    """Return notes from the first enabled exception row matching the candidate row."""
    matching_row = matching_exception_row(candidate_row, exception_df)
    if matching_row is None:
        return ""
    return _norm(matching_row.get("notes", ""))


def matching_exception_row(
    candidate_row: pd.Series,
    exception_df: pd.DataFrame,
) -> pd.Series | None:
    """Return the first enabled exception row matching the candidate row."""
    if exception_df.empty:
        return None

    match_columns = _exception_match_columns(exception_df, candidate_row.to_frame().T)
    if not match_columns:
        return None

    for _, exception_row in exception_df.iterrows():
        if _row_matches_exception(candidate_row, exception_row, match_columns):
            return exception_row
    return None


def split_allowed_rows(
    candidate_df: pd.DataFrame,
    sheet_name: str,
    status_column: str,
    reason_column: str,
    workbook_path: Path = EXCEPTION_WORKBOOK_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a QA table into review rows and rows matched by a manual exception sheet."""
    allowed_columns = [*list(candidate_df.columns), status_column, reason_column]
    if candidate_df.empty:
        return candidate_df.copy(), pd.DataFrame(columns=allowed_columns)

    exception_df = load_exception_sheet(sheet_name, workbook_path=workbook_path)
    reviewed = candidate_df.copy()
    matches = [
        matching_exception_row(row, exception_df)
        for _, row in reviewed.iterrows()
    ]
    reviewed[reason_column] = [
        "" if row is None else _norm(row.get("notes", ""))
        for row in matches
    ]
    reviewed[status_column] = [
        "needs_review" if row is None else "allowed"
        for row in matches
    ]

    allowed = reviewed[reviewed[status_column].eq("allowed")].copy()
    needs_review = reviewed[reviewed[status_column].eq("needs_review")].copy()
    needs_review = needs_review.drop(columns=[status_column, reason_column])
    return needs_review.reset_index(drop=True), allowed[allowed_columns].reset_index(drop=True)


def row_is_allowed(
    candidate_row: pd.Series,
    sheet_name: str,
    workbook_path: Path = EXCEPTION_WORKBOOK_PATH,
) -> bool:
    """Return True when a row matches an enabled exception sheet row."""
    return matching_exception_row(candidate_row, load_exception_sheet(sheet_name, workbook_path)) is not None
