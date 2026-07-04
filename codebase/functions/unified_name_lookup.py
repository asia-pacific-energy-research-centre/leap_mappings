"""
unified_name_lookup.py

Resolve ESTO/9th-edition codes to display names from leap_display_names in
outlook_mappings_master.xlsx. For codes not found there, fall back to the
derived auto-name.

Key types:
    ninth_fuel     – 9th-edition fuel/subfuel codes  (e.g. 01_01_coking_coal)
    ninth_sector   – 9th-edition sector codes        (e.g. 14_03_01_iron_and_steel)
    esto_product   – ESTO product labels             (e.g. "01.01 Coking coal")
    esto_flow      – ESTO flow labels                (e.g. "09.07 Oil refineries")

Source
------
outlook_mappings_master.xlsx
    leap_display_names : code_type, code, leap_display_name, Note,
                         USED_IN_LEAP_INITIALISATION, IS_LEAP_ROLLUP_NAME

Rows whose display name differs from the derived auto-name are treated as
genuine overrides and are stored in the lookup; all other codes use the
fallback name.

Public API
----------
    load_source_records()       → long-form DataFrame (key_type, code, name, source_sheet)
    build_unified_name_lookup() → summary DataFrame   (key_type, code, name, is_conflict)
    resolve_name(key_type, code, *, prefer_source=None) → str | None
    invalidate_cache()          → None
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.utilities.outlook_mappings_filters import filter_used_in_leap_initialisation

OUTLOOK_MAPPINGS_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"

_NUMERIC_PREFIX_RE = re.compile(r"^[\d.]+\s+")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(value: object) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in {"", "nan", "none"} else text


def _strip_numeric_prefix(code: str) -> str:
    """Strip leading numeric prefix (e.g. '09.01.01 ') from a code string."""
    return _NUMERIC_PREFIX_RE.sub("", code).strip()


def _auto_name_for_code(code: str) -> str:
    """Return the default display name used when no override exists."""
    stripped = _strip_numeric_prefix(code)
    return stripped if stripped and stripped != code else code


# ---------------------------------------------------------------------------
# Core loader: genuine overrides from leap_display_names
# ---------------------------------------------------------------------------

def _load_display_name_overrides() -> list[dict]:
    """
    Read leap_display_names sheet and return records where the display name
    differs from the derived auto-name.
    """
    df = pd.read_excel(
        OUTLOOK_MAPPINGS_PATH,
        sheet_name="leap_display_names",
        dtype=object,
    )
    df = filter_used_in_leap_initialisation(df).fillna("")

    records = []
    for _, row in df.iterrows():
        key_type = _clean(row.get("code_type", ""))
        code = _clean(row.get("code", ""))
        name = _clean(row.get("leap_display_name", ""))
        if not key_type or not code or not name:
            continue
        if name == _auto_name_for_code(code):
            continue
        records.append({
            "key_type": key_type,
            "code": code,
            "name": name,
            "source_sheet": "leap_display_names",
        })
    return records


# ---------------------------------------------------------------------------
# Public: raw long-form records
# ---------------------------------------------------------------------------

def load_source_records() -> pd.DataFrame:
    """
    Return all override (key_type, code, name, source_sheet) records from
    leap_display_names. Only genuine overrides (display name differs from the
    derived auto-name) are included; fallback names are not listed.
    """
    records = _load_display_name_overrides()
    df = pd.DataFrame(records, columns=["key_type", "code", "name", "source_sheet"])
    return df.drop_duplicates().reset_index(drop=True)


# ---------------------------------------------------------------------------
# Public: consolidated summary
# ---------------------------------------------------------------------------

def build_unified_name_lookup() -> pd.DataFrame:
    """
    Build a consolidated name-lookup table from override records.

    Each row has: key_type, code, name, is_conflict.
    Since there is one source, is_conflict is always False.
    """
    raw = load_source_records()
    if raw.empty:
        return pd.DataFrame(columns=["key_type", "code", "name", "is_conflict"])

    result = raw[["key_type", "code", "name"]].drop_duplicates()
    result = result.assign(is_conflict=False)
    return result.sort_values(
        ["key_type", "code"],
        key=lambda col: col.str.lower(),
    ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Public: convenience resolver with cache
# ---------------------------------------------------------------------------

_OVERRIDE_CACHE: dict[tuple[str, str], str] | None = None


def _get_overrides() -> dict[tuple[str, str], str]:
    global _OVERRIDE_CACHE
    if _OVERRIDE_CACHE is None:
        records = _load_display_name_overrides()
        _OVERRIDE_CACHE = {(r["key_type"], r["code"]): r["name"] for r in records}
    return _OVERRIDE_CACHE


def invalidate_cache() -> None:
    """Force reload of lookup on next call to resolve_name()."""
    global _OVERRIDE_CACHE
    _OVERRIDE_CACHE = None


def resolve_name(
    key_type: str,
    code: str,
    *,
    prefer_source: str | None = None,  # noqa: ARG001 — kept for API compatibility
) -> str | None:
    """
    Resolve a single code to a display name.

    Checks the leap_display_names override table first; falls back to
    the derived auto-name for the code string.
    Returns None if neither produces a non-empty result.
    """
    overrides = _get_overrides()
    override = overrides.get((key_type, code))
    if override:
        return override

    auto_name = _auto_name_for_code(code)
    return auto_name if auto_name else None


# ---------------------------------------------------------------------------
# Script entry-point: write outputs to CSV for inspection
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    out_dir = REPO_ROOT / "outputs" / "mappings" / "unified_name_lookup"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading source records …")
    records = load_source_records()
    records_path = out_dir / "unified_name_lookup_records.csv"
    records.to_csv(records_path, index=False)
    print(f"  {len(records)} override records -> {records_path.relative_to(REPO_ROOT)}")

    print("Building unified lookup …")
    lookup = build_unified_name_lookup()
    lookup_path = out_dir / "unified_name_lookup.csv"
    lookup.to_csv(lookup_path, index=False)
    print(f"  {len(lookup)} (key_type, code, name) rows -> {lookup_path.relative_to(REPO_ROOT)}")

    print("\nBreakdown:")
    for key_type, grp in lookup.groupby("key_type"):
        print(f"  {key_type}: {grp['code'].nunique()} override codes")

    print("\nDone.")
