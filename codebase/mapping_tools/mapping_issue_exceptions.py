#%%
"""Reusable exception sets for mapping/validation issue suppression.

Backed by ``config/mapping_issue_exception_sets.xlsx``. The
``unmodelled_source_ignored`` sheet lists ESTO/9th sectors and fuels we do not
model, so downstream validations should not treat them as issues (they never
need to reconcile). Matching is by the *leading code number* of a flow/product
label, scoped by axis, so a whole family is covered by one row:

    sector 18  ->  "18 Electricity output in GWh", "18.02 MAP CHP plants",
                   "18_electricity_output_in_gwh/18_01_electricity_plants", ...
    fuel   19  ->  "19 Total", "19_total"

Any process (in this repo or ``leap_initialisation``) can reuse this by loading
the code sets and calling :func:`excepted_code_mask` on its flow/product columns.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from codebase.mapping_issue_exceptions import (
    load_unmodelled_source_codes as _load_unmodelled_source_codes,
)

DEFAULT_WORKBOOK_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "mapping_issue_exception_sets.xlsx"
)
UNMODELLED_SOURCE_SHEET = "unmodelled_source_ignored"

_LEADING_CODE = re.compile(r"^\s*0*(\d+)")


def leading_code_number(value: object) -> int | None:
    """Return the leading top-level numeric code of a flow/product label.

    ``"18.02 MAP CHP plants"`` -> 18, ``"06_stock_changes"`` -> 6,
    ``"19 Total"`` -> 19, ``"Total final consumption"`` -> None.
    """
    match = _LEADING_CODE.match(str(value))
    return int(match.group(1)) if match else None


def load_unmodelled_source_codes(
    workbook_path: Path | str = DEFAULT_WORKBOOK_PATH,
    sheet_name: str = UNMODELLED_SOURCE_SHEET,
) -> dict[str, set[int]]:
    """Load enabled unmodelled-source code numbers, grouped by axis.

    Returns ``{"sector": {...}, "fuel": {...}}`` of leading code numbers. Missing
    workbook/sheet yields empty sets so callers degrade to "no suppression".
    """
    return _load_unmodelled_source_codes(Path(workbook_path), sheet_name=sheet_name)


def excepted_code_mask(codes: pd.Series, excepted_numbers: set[int]) -> pd.Series:
    """Vectorized boolean mask: which ``codes`` lead with an excepted number."""
    if not excepted_numbers:
        return pd.Series(False, index=codes.index)
    leading = codes.astype(str).str.extract(_LEADING_CODE.pattern, expand=False)
    leading = pd.to_numeric(leading, errors="coerce")
    return leading.isin(excepted_numbers)


def unmodelled_source_pair_mask(
    flow_codes: pd.Series,
    product_codes: pd.Series,
    codes: dict[str, set[int]],
) -> pd.Series:
    """Mask rows whose flow OR product is an unmodelled source (ignore as issue)."""
    return excepted_code_mask(flow_codes, codes.get("sector", set())) | excepted_code_mask(
        product_codes, codes.get("fuel", set())
    )

#%%
