"""Shared row filters for sheets in config/outlook_mappings_master.xlsx."""
from __future__ import annotations

import pandas as pd

# Column marking rows excluded from LEAP entirely. Explicit False excludes the
# row; blank/NaN or True keep it (blank is the common case and means "not
# reviewed / not flagged for exclusion", not "excluded").
USED_IN_LEAP_INITIALISATION_COLUMN = "USED_IN_LEAP_INITIALISATION"


def filter_used_in_leap_initialisation(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop rows explicitly excluded from LEAP via ``USED_IN_LEAP_INITIALISATION``.

    Only an explicit ``False`` (or falsy string equivalent) excludes a row;
    blank/NaN and ``True`` both keep it. Frames without the column are
    returned unchanged.
    """
    if frame.empty or USED_IN_LEAP_INITIALISATION_COLUMN not in frame.columns:
        return frame
    col = frame[USED_IN_LEAP_INITIALISATION_COLUMN]

    def _excluded(value: object) -> bool:
        if pd.isna(value):
            return False
        text = str(value).strip().lower()
        return text in {"false", "0", "0.0", "f", "no", "n"}

    mask = ~col.map(_excluded)
    return frame.loc[mask].copy()
