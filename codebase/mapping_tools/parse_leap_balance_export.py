"""
parse_leap_balance_export.py

Parse LEAP "full model output" energy balance exports into long-format CSV.

LEAP exports use two different section layouts in the same file:

  Transformation section (rows before "Total Transformation"):
    - 3-space indent per level (max 1 level)
    - Children appear BEFORE their parent subtotal row
    - Path reconstruction: child → look ahead for the next level-0 row

  Demand section (rows after "Total Transformation"):
    - 2-space indent per level (up to 3 levels)
    - Parent appears BEFORE its children (standard tree order)
    - Path reconstruction: standard stack-based forward scan

Output columns:
    economy, scenario, year, leap_flow, leap_product, value

Where:
    leap_flow    — slash-separated sector path matching leap_sector_name_full_path
                   in outlook_mappings_master.xlsx (e.g. "Oil Refining/Oil Refining")
    leap_product — fuel column header, normalized to match raw_leap_fuel_name
                   in the mapping workbook
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from codebase.utilities.leap_balance_export_resolver import resolve_balance_exports_root

def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "config" / "outlook_mappings_master.xlsx").exists():
            return parent
    raise RuntimeError("Could not locate repo root.")

REPO_ROOT = _find_repo_root()

# ---------------------------------------------------------------------------
# Fuel name normalization: LEAP export column → raw_leap_fuel_name in workbook
# ---------------------------------------------------------------------------

_FUEL_NAME_MAP = {
    "Fuelwood and woodwaste": "Fuelwood & woodwaste",
    "Black liqour":           "Black liquor",        # typo in LEAP export
    "of which Photovoltaics": "Solar photovoltaics",
}

# Columns to drop — aggregates or "DO NOT USE" placeholders
_DROP_FUEL_COLS = {
    "Total",
    "Biomass",
    "Coal Bituminous DO NOT USE",
    "Municipal solid waste non and renewable DO NOT USE",
}

# ---------------------------------------------------------------------------
# Header parsing
# ---------------------------------------------------------------------------

def _parse_header(raw: pd.DataFrame) -> tuple[str, str, int]:
    """
    Extract (economy, scenario, year) from rows 0-1 of a LEAP export.

    Row 0: 'Energy Balance for Area "USA - ..."'
    Row 1: 'Scenario: Reference, Year: 2060, Units: Petajoule'
    """
    title = str(raw.iloc[0, 0] or "")
    meta  = str(raw.iloc[1, 0] or "")

    # Economy: text between the last space and the closing quote in the Area title
    economy_match = re.search(r'Area "([^"]+)"', title)
    economy = economy_match.group(1) if economy_match else ""

    scenario_match = re.search(r"Scenario:\s*([^,]+)", meta)
    year_match     = re.search(r"Year:\s*(\d+)", meta)

    scenario = scenario_match.group(1).strip() if scenario_match else ""
    year     = int(year_match.group(1))        if year_match     else 0

    return economy, scenario, year


def _fuel_columns(raw: pd.DataFrame) -> list[str]:
    """Return normalized fuel names from header row 2 (cols 1+)."""
    raw_names = [
        str(v) for v in raw.iloc[2, 1:].values
        if not (isinstance(v, float) and pd.isna(v))
    ]
    normalized = []
    for name in raw_names:
        name = _FUEL_NAME_MAP.get(name, name)
        if name not in _DROP_FUEL_COLS:
            normalized.append(name)
        else:
            normalized.append(None)     # placeholder; dropped later
    return normalized


# ---------------------------------------------------------------------------
# Sector path reconstruction
# ---------------------------------------------------------------------------

def _indentation(s: str) -> int:
    return len(s) - len(s.lstrip(" "))


def _reconstruct_transformation_paths(
    sector_col: pd.Series,
    start: int,
    end: int,
) -> dict[int, str]:
    """
    Transformation section: children (3-space indent) appear BEFORE their parent.

    Scan forward; when a level-0 row is encountered, assign it as parent to
    all immediately preceding level-1 rows.  Level-0 rows with no pending
    children are standalone (Production, Imports, etc.).
    """
    paths: dict[int, str] = {}
    pending: list[tuple[int, str]] = []  # (row_index, segment_name)

    for i in range(start, end + 1):
        raw_val = sector_col.iloc[i]
        if pd.isna(raw_val) or not str(raw_val).strip():
            continue

        s      = str(raw_val)
        indent = _indentation(s)
        name   = s.strip()

        if indent == 0:
            # Assign this row as parent to all pending children
            for pi, child_name in pending:
                paths[pi] = f"{name}/{child_name}"
            pending = []
            paths[i] = name
        else:
            # indent == 3 → level-1 child; parent will be seen later
            pending.append((i, name))

    # Orphaned children (no subsequent parent row seen) — store as-is
    for pi, child_name in pending:
        paths[pi] = child_name

    return paths


def _reconstruct_demand_paths(
    sector_col: pd.Series,
    start: int,
    end: int,
) -> dict[int, str]:
    """
    Demand section: parent appears BEFORE children (standard tree order).
    2-space indent per level.
    """
    paths: dict[int, str] = {}
    stack: dict[int, str] = {}  # level → segment name

    for i in range(start, end + 1):
        raw_val = sector_col.iloc[i]
        if pd.isna(raw_val) or not str(raw_val).strip():
            continue

        s      = str(raw_val)
        indent = _indentation(s)
        level  = indent // 2
        name   = s.strip()

        stack[level] = name
        # Drop deeper levels from previous branches
        for k in list(stack.keys()):
            if k > level:
                del stack[k]

        full_path = "/".join(stack[k] for k in sorted(stack.keys()))
        paths[i] = full_path

    return paths


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

def _parse_single_sheet(
    raw: pd.DataFrame,
    economy_override: str | None = None,
) -> pd.DataFrame:
    """Parse one sheet of a LEAP balance export into long-format rows."""
    economy_raw, scenario, year = _parse_header(raw)
    economy = economy_override or economy_raw

    fuel_names_norm = _fuel_columns(raw)

    sector_col = raw.iloc[:, 0]
    n_rows = len(raw)

    tx_end = None
    for i in range(3, n_rows):
        v = str(sector_col.iloc[i]) if not pd.isna(sector_col.iloc[i]) else ""
        if v.strip() == "Total Transformation":
            tx_end = i
            break

    if tx_end is None:
        tx_end = 2

    paths_tx  = _reconstruct_transformation_paths(sector_col, 3, tx_end)
    paths_dem = _reconstruct_demand_paths(sector_col, tx_end + 1, n_rows - 1)
    all_paths = {**paths_tx, **paths_dem}

    records = []
    for row_i, full_path in all_paths.items():
        row_values = raw.iloc[row_i, 1:]
        for fuel_name, raw_v in zip(fuel_names_norm, row_values):
            if fuel_name is None:
                continue
            try:
                value = float(raw_v)
            except (TypeError, ValueError):
                continue
            records.append({
                "economy":      economy,
                "scenario":     scenario,
                "year":         year,
                "leap_flow":    full_path,
                "leap_product": fuel_name,
                "value":        value,
            })

    return pd.DataFrame(records)


def parse_leap_balance_xlsx(
    xlsx_path: Path,
    economy_override: str | None = None,
) -> pd.DataFrame:
    """
    Parse a LEAP balance export file into long-format rows.

    Supports both single-sheet files and multi-sheet workbooks where each
    sheet represents one year (sheet names like 'EBal|2060', '2060', …).
    All matching year sheets are parsed and concatenated so the full
    projection time series is captured rather than just the first sheet.

    Parameters
    ----------
    xlsx_path       : Path to the .xlsx file.
    economy_override: If provided, use this as the economy code instead of
                      extracting it from the file header (the header embeds a
                      long model name; the directory name like '20_USA' is more
                      useful).

    Returns
    -------
    DataFrame with columns: economy, scenario, year, leap_flow, leap_product, value
    """
    xl = pd.ExcelFile(xlsx_path)
    sheet_names = xl.sheet_names

    # Detect multi-year workbooks (sheets named like 'EBal|2060' or '2060').
    ebal_sheets = [s for s in sheet_names if re.match(r"^(EBal\|)?\d{4}$", str(s))]

    if ebal_sheets:
        frames = []
        for sheet in ebal_sheets:
            raw = xl.parse(sheet, header=None, dtype=object)
            df = _parse_single_sheet(raw, economy_override=economy_override)
            if not df.empty:
                frames.append(df)
        if not frames:
            return pd.DataFrame(
                columns=["economy", "scenario", "year", "leap_flow", "leap_product", "value"]
            )
        return pd.concat(frames, ignore_index=True)

    # Single-sheet workbook: read first (and only) sheet as before
    raw = xl.parse(sheet_names[0], header=None, dtype=object)
    return _parse_single_sheet(raw, economy_override=economy_override)


# ---------------------------------------------------------------------------
# Directory runner
# ---------------------------------------------------------------------------

def parse_leap_balance_dir(
    export_dir: Path,
    output_path: Path,
    *,
    economy_code: str | None = None,
) -> pd.DataFrame:
    """
    Parse all LEAP balance xlsx files in *export_dir* and write a combined
    long-format CSV to *output_path*.

    Uses the parent directory name as the economy code if not provided
    (e.g. the directory '20_USA' → economy='20_USA').
    """
    # Excel creates ``~$`` lock files while a workbook is open. They are not
    # workbooks and pandas cannot read them, so never treat them as LEAP input.
    xlsx_files = sorted(
        path for path in export_dir.glob("*.xlsx")
        if not path.name.startswith("~$")
    )
    if not xlsx_files:
        raise FileNotFoundError(f"No .xlsx files found in {export_dir}")

    eco = economy_code or export_dir.name
    frames = []
    for f in xlsx_files:
        print(f"  Parsing {f.name} …")
        df = parse_leap_balance_xlsx(f, economy_override=eco)
        print(f"    {len(df):,} rows (year={df['year'].iloc[0] if len(df) else '?'}, "
              f"scenario={df['scenario'].iloc[0] if len(df) else '?'})")
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_path, index=False)
    try:
        display_path = output_path.relative_to(REPO_ROOT)
    except ValueError:
        display_path = output_path
    print(f"  Combined LEAP long-format: {len(combined):,} rows -> {display_path}")
    return combined


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    LEAP_EXPORT_DIR = resolve_balance_exports_root() / "20_USA"
    OUTPUT_PATH = REPO_ROOT / "results" / "mapping_relationships" / "raw_leap_results.csv"

    if not LEAP_EXPORT_DIR.exists():
        raise FileNotFoundError(
            f"No 20_USA LEAP export directory found under the canonical root: {LEAP_EXPORT_DIR}"
        )

    print(f"Parsing LEAP balance exports from: {LEAP_EXPORT_DIR}")
    parse_leap_balance_dir(LEAP_EXPORT_DIR, OUTPUT_PATH)
    print("Done.")
