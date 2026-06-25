#%%
"""
Maintenance workflow for config/outlook_mappings_master.xlsx.

Stage 0 of the mapping pipeline.  Run this before Stage 1 whenever the
workbook or the source data CSVs have been updated.

What it does
------------
1. Populates subtotal flags in the three base mapping sheets:
     leap_is_subtotal        — True when the LEAP branch is a parent of
                               another active mapping row (within-sheet check)
     esto_pair_is_subtotal   — from data/00APEC_2025_low_with_subtotals.csv
     ninth_pair_is_subtotal  — from data/merged_file_energy_ALL_20251106.csv
                               (subtotal_layout OR subtotal_results)

2. Produces QA CSV outputs in results/maintenance/:
     cardinality_leap_esto.csv      — (LEAP source, ESTO target) cardinality
     cardinality_leap_ninth.csv     — (LEAP source, 9th target) cardinality
     cardinality_ninth_esto.csv     — (9th source, ESTO target) cardinality
     unmapped_esto_pairs.csv        — ESTO (flow, product) pairs in data with
                                      no active mapping row
     unmapped_ninth_pairs.csv       — 9th (sector, fuel) pairs in data with
                                      no active mapping row
     subtotal_mismatches.csv        — M6 rule: leaf source → aggregate target
                                      when a more specific target exists

Usage:
    python codebase/outlook_mapping_maintenance_workflow.py
"""

from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
import openpyxl

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

WORKBOOK_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
ARCHIVE_DIR = REPO_ROOT / "config" / "archive"
QA_DIR = REPO_ROOT / "results" / "maintenance"

ESTO_CSV_PATH = REPO_ROOT / "data" / "00APEC_2025_low_with_subtotals.csv"
NINTH_CSV_PATH = REPO_ROOT / "data" / "merged_file_energy_ALL_20251106.csv"

# ── helpers ──────────────────────────────────────────────────────────────────

def _norm(value: object) -> str:
    """Normalize a cell value: strip, collapse internal whitespace."""
    text = " ".join(str(value or "").split())
    return "" if text.lower() in {"nan", "none"} else text


def _is_x(value: object) -> bool:
    """Return True if value is exactly the 9th-Outlook placeholder 'x'."""
    return str(value or "").strip() == "x"


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _active_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Filter out rows where remove_row or duplicate_to_remove is truthy."""
    remove = df.get("remove_row", pd.Series(False, index=df.index)).map(_truthy)
    duplicate = df.get("duplicate_to_remove", pd.Series(False, index=df.index)).map(_truthy)
    return df[~(remove | duplicate)].copy()


# ── subtotal lookups ─────────────────────────────────────────────────────────

def _build_esto_subtotal_lookup() -> Dict[Tuple[str, str], bool]:
    """
    Return a dict mapping (norm(esto_flow), norm(esto_product)) -> bool.

    True if any row in the ESTO CSV for that pair has is_subtotal=True.
    """
    df = pd.read_csv(ESTO_CSV_PATH)
    if "is_subtotal" not in df.columns:
        raise ValueError(f"is_subtotal column not found in {ESTO_CSV_PATH}")

    df["_flow"] = df["flows"].fillna("").map(_norm)
    df["_product"] = df["products"].fillna("").map(_norm)
    df["_is_sub"] = df["is_subtotal"].fillna(False).map(_truthy)

    grouped = (
        df[df["_flow"].ne("") & df["_product"].ne("")]
        .groupby(["_flow", "_product"])["_is_sub"]
        .max()
    )
    return {(flow, product): bool(flag) for (flow, product), flag in grouped.items()}


def _build_ninth_subtotal_lookup() -> Dict[Tuple[str, str], bool]:
    """
    Return a dict mapping (norm(ninth_sector), norm(ninth_fuel)) -> bool.

    ninth_sector = deepest non-'x' sector level (sub4 -> sub3 -> sub2 -> sub1 -> sector).
    ninth_fuel   = deepest non-'x' fuel level (subfuels -> fuels).

    True if subtotal_layout OR subtotal_results is True for that pair.
    """
    df = pd.read_csv(NINTH_CSV_PATH)

    sector_cols = ["sub4sectors", "sub3sectors", "sub2sectors", "sub1sectors", "sectors"]
    fuel_cols = ["subfuels", "fuels"]
    flag_cols = ["subtotal_layout", "subtotal_results"]

    for col in sector_cols + fuel_cols + flag_cols:
        if col not in df.columns:
            df[col] = ""

    for col in flag_cols:
        df[col] = df[col].fillna(False).map(_truthy)

    def _deepest_sector(row: pd.Series) -> str:
        for col in sector_cols:
            val = _norm(row[col])
            if val and not _is_x(val):
                return val
        return ""

    def _deepest_fuel(row: pd.Series) -> str:
        for col in fuel_cols:
            val = _norm(row[col])
            if val and not _is_x(val):
                return val
        return ""

    df["_sector"] = df.apply(_deepest_sector, axis=1)
    df["_fuel"] = df.apply(_deepest_fuel, axis=1)
    df["_is_sub"] = df["subtotal_layout"] | df["subtotal_results"]

    grouped = (
        df[df["_sector"].ne("") & df["_fuel"].ne("")]
        .groupby(["_sector", "_fuel"])["_is_sub"]
        .max()
    )
    return {(sector, fuel): bool(flag) for (sector, fuel), flag in grouped.items()}


def _compute_leap_subtotals(paths: set[str]) -> set[str]:
    """
    Return the subset of paths that are subtotals (i.e. have at least one
    child path in the active set).  A child path starts with 'parent/'.
    """
    subtotals: set[str] = set()
    sorted_paths = sorted(paths)
    for path in sorted_paths:
        prefix = path + "/"
        for other in sorted_paths:
            if other != path and other.startswith(prefix):
                subtotals.add(path)
                break
    return subtotals


# ── workbook helpers ──────────────────────────────────────────────────────────

def _archive_workbook(path: Path) -> Path:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = path.stem
    dest = ARCHIVE_DIR / f"{stem}.before_maintenance_{ts}{path.suffix}"
    shutil.copy2(path, dest)
    print(f"Archived: {dest}")
    return dest


def _col_index(ws, header_name: str) -> int | None:
    """Return the 1-based column index of header_name in row 1, or None."""
    for cell in ws[1]:
        if _norm(cell.value) == _norm(header_name):
            return cell.column
    return None


def _get_header_row(ws) -> list[str]:
    return [_norm(cell.value) for cell in ws[1]]


def _update_sheet_column(
    ws,
    col_name: str,
    key_col_names: list[str],
    lookup: Dict[Tuple[str, ...], bool],
) -> tuple[int, int, int]:
    """
    Write lookup results into col_name for each data row in ws.

    key_col_names: column headers whose normed values form the lookup key.
    Returns (updated, not_found, skipped_blank_key) counts.
    """
    target_col_idx = _col_index(ws, col_name)
    if target_col_idx is None:
        print(f"  WARNING: column '{col_name}' not found in sheet '{ws.title}' — skipping")
        return 0, 0, 0

    key_col_idxs = []
    for kname in key_col_names:
        idx = _col_index(ws, kname)
        if idx is None:
            print(f"  WARNING: key column '{kname}' not found in sheet '{ws.title}' — skipping")
            return 0, 0, 0
        key_col_idxs.append(idx)

    updated = not_found = skipped = 0
    for row in ws.iter_rows(min_row=2):
        key_parts = tuple(_norm(row[i - 1].value) for i in key_col_idxs)
        if any(part == "" for part in key_parts):
            skipped += 1
            continue
        flag = lookup.get(key_parts)
        if flag is None:
            not_found += 1
            row[target_col_idx - 1].value = None
        else:
            row[target_col_idx - 1].value = flag
            updated += 1

    return updated, not_found, skipped


def _update_sheet_leap_subtotals(ws, subtotal_paths: set[str]) -> tuple[int, int]:
    """Write leap_is_subtotal for each row based on precomputed subtotal_paths set."""
    target_col_idx = _col_index(ws, "leap_is_subtotal")
    if target_col_idx is None:
        print(f"  WARNING: column 'leap_is_subtotal' not found in sheet '{ws.title}' — skipping")
        return 0, 0

    path_col_idx = _col_index(ws, "leap_sector_name_full_path")
    if path_col_idx is None:
        print(f"  WARNING: column 'leap_sector_name_full_path' not found in sheet '{ws.title}' — skipping")
        return 0, 0

    updated = skipped = 0
    for row in ws.iter_rows(min_row=2):
        path = _norm(row[path_col_idx - 1].value)
        if not path:
            skipped += 1
            continue
        row[target_col_idx - 1].value = path in subtotal_paths
        updated += 1

    return updated, skipped


def _read_sheet_as_df(wb, sheet_name: str) -> pd.DataFrame:
    """Read a workbook sheet into a DataFrame using openpyxl (avoids re-read from disk)."""
    ws = wb[sheet_name]
    headers = [_norm(cell.value) for cell in ws[1]]
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        rows.append([_norm(v) for v in row])
    return pd.DataFrame(rows, columns=headers)


# ── cardinality helpers ───────────────────────────────────────────────────────

def _mapping_cardinality(n_targets: int, n_sources: int) -> str:
    if n_targets <= 0 or n_sources <= 0:
        return ""
    if n_targets == 1 and n_sources == 1:
        return "one_to_one"
    if n_targets > 1 and n_sources == 1:
        return "one_to_many"
    if n_targets == 1 and n_sources > 1:
        return "many_to_one"
    return "many_to_many"


def _compute_cardinality(
    df: pd.DataFrame,
    source_flow_col: str,
    source_product_col: str,
    target_flow_col: str,
    target_product_col: str,
) -> pd.DataFrame:
    """Return a cardinality summary DataFrame for (source, target) pairs."""
    active = _active_rows(df)
    valid = active[
        active[source_flow_col].ne("") & active[source_product_col].ne("")
        & active[target_flow_col].ne("") & active[target_product_col].ne("")
    ].copy()
    if valid.empty:
        return pd.DataFrame(columns=[
            source_flow_col, source_product_col,
            target_flow_col, target_product_col,
            "n_targets_for_source", "n_sources_for_target", "cardinality",
        ])
    valid["_src"] = valid[source_flow_col] + "|||" + valid[source_product_col]
    valid["_tgt"] = valid[target_flow_col] + "|||" + valid[target_product_col]
    pairs = valid[["_src", "_tgt"]].drop_duplicates()
    src_target_count = pairs.groupby("_src")["_tgt"].nunique()
    tgt_source_count = pairs.groupby("_tgt")["_src"].nunique()

    rows = []
    for _, pair_row in pairs.iterrows():
        src, tgt = pair_row["_src"], pair_row["_tgt"]
        sf, sp = src.split("|||", 1)
        tf, tp = tgt.split("|||", 1)
        n_targets = int(src_target_count.get(src, 0))
        n_sources = int(tgt_source_count.get(tgt, 0))
        rows.append({
            source_flow_col: sf,
            source_product_col: sp,
            target_flow_col: tf,
            target_product_col: tp,
            "n_targets_for_source": n_targets,
            "n_sources_for_target": n_sources,
            "cardinality": _mapping_cardinality(n_targets, n_sources),
        })
    return pd.DataFrame(rows).sort_values([source_flow_col, source_product_col, target_flow_col, target_product_col])


# ── unmapped pair detection ───────────────────────────────────────────────────

def _unmapped_esto_pairs(
    mapping_dfs: list[pd.DataFrame],
    esto_subtotal_lookup: Dict[Tuple[str, str], bool],
) -> pd.DataFrame:
    """Find ESTO (flow, product) pairs in the data that have no active mapping row."""
    active_esto: set[tuple[str, str]] = set()
    for df in mapping_dfs:
        active = _active_rows(df)
        for col_flow, col_product in [("esto_flow", "esto_product")]:
            if col_flow in active.columns and col_product in active.columns:
                for _, row in active.iterrows():
                    f, p = _norm(row.get(col_flow, "")), _norm(row.get(col_product, ""))
                    if f and p:
                        active_esto.add((f, p))

    rows = []
    for (flow, product), is_sub in esto_subtotal_lookup.items():
        if (flow, product) not in active_esto:
            rows.append({"esto_flow": flow, "esto_product": product, "is_subtotal": is_sub})
    return pd.DataFrame(rows).sort_values(["esto_flow", "esto_product"]) if rows else pd.DataFrame(
        columns=["esto_flow", "esto_product", "is_subtotal"]
    )


def _unmapped_ninth_pairs(
    mapping_dfs: list[pd.DataFrame],
    ninth_subtotal_lookup: Dict[Tuple[str, str], bool],
) -> pd.DataFrame:
    """Find 9th (sector, fuel) pairs in the data that have no active mapping row."""
    active_ninth: set[tuple[str, str]] = set()
    for df in mapping_dfs:
        active = _active_rows(df)
        for sector_col, fuel_col in [
            ("ninth_sector", "ninth_fuel"),
            ("9th_sector", "9th_fuel"),
        ]:
            if sector_col in active.columns and fuel_col in active.columns:
                for _, row in active.iterrows():
                    s, f = _norm(row.get(sector_col, "")), _norm(row.get(fuel_col, ""))
                    if s and f:
                        active_ninth.add((s, f))

    rows = []
    for (sector, fuel), is_sub in ninth_subtotal_lookup.items():
        if (sector, fuel) not in active_ninth:
            rows.append({"ninth_sector": sector, "ninth_fuel": fuel, "is_subtotal": is_sub})
    return pd.DataFrame(rows).sort_values(["ninth_sector", "ninth_fuel"]) if rows else pd.DataFrame(
        columns=["ninth_sector", "ninth_fuel", "is_subtotal"]
    )


# ── M6: subtotal mismatch detection ──────────────────────────────────────────

def _subtotal_mismatches(
    df: pd.DataFrame,
    source_flow_col: str,
    source_product_col: str,
    target_flow_col: str,
    target_product_col: str,
    source_subtotal_col: str,
    target_subtotal_col: str,
) -> pd.DataFrame:
    """
    Flag rows where a leaf-level source maps to an aggregate target AND a more
    specific (non-subtotal) target also exists for a different source.

    Rule (M6): only flag when:
      - source is NOT a subtotal (leaf level)
      - target IS a subtotal (aggregate)
      - at least one other active row maps to a non-subtotal target at the same
        flow-level (same target_flow_col prefix)
    """
    active = _active_rows(df)
    for col in [source_flow_col, source_product_col, target_flow_col, target_product_col,
                source_subtotal_col, target_subtotal_col]:
        if col not in active.columns:
            active[col] = ""
        active[col] = active[col].fillna("").astype(str).str.strip()

    # Rows where leaf source → aggregate target
    candidates = active[
        (active[source_subtotal_col].str.lower().isin(["false", "0", "no", ""]))
        & (active[target_subtotal_col].str.lower().isin(["true", "1", "yes"]))
    ].copy()

    if candidates.empty:
        return pd.DataFrame()

    # Build set of target flows that also have non-subtotal targets active
    non_subtotal_targets = set(
        active.loc[
            active[target_subtotal_col].str.lower().isin(["false", "0", "no", ""]),
            target_flow_col,
        ]
    )

    mismatch_rows = candidates[
        candidates[target_flow_col].isin(non_subtotal_targets)
    ].copy()
    if mismatch_rows.empty:
        return mismatch_rows

    mismatch_rows["mismatch_reason"] = (
        "leaf_source_maps_to_aggregate_target_and_more_specific_target_exists"
    )
    return mismatch_rows[[
        source_flow_col, source_product_col,
        target_flow_col, target_product_col,
        source_subtotal_col, target_subtotal_col,
        "mismatch_reason",
    ]]


# ── main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    print("Loading subtotal lookups …")
    esto_lookup = _build_esto_subtotal_lookup()
    ninth_lookup = _build_ninth_subtotal_lookup()
    print(f"  ESTO lookup: {len(esto_lookup):,} (flow, product) pairs")
    print(f"  9th lookup:  {len(ninth_lookup):,} (sector, fuel) pairs")

    _archive_workbook(WORKBOOK_PATH)

    print(f"\nOpening {WORKBOOK_PATH} …")
    wb = openpyxl.load_workbook(WORKBOOK_PATH)

    # ── Compute LEAP subtotal paths from both LEAP sheets combined ───────────
    print("\nComputing LEAP subtotals …")
    df_lcesto = _read_sheet_as_df(wb, "leap_combined_esto")
    df_lcninth = _read_sheet_as_df(wb, "leap_combined_ninth")
    active_esto_paths = set(
        _active_rows(df_lcesto)["leap_sector_name_full_path"].map(_norm)
        .loc[lambda s: s.ne("")]
    )
    active_ninth_paths = set(
        _active_rows(df_lcninth)["leap_sector_name_full_path"].map(_norm)
        .loc[lambda s: s.ne("")]
    )
    all_leap_paths = active_esto_paths | active_ninth_paths
    subtotal_paths = _compute_leap_subtotals(all_leap_paths)
    print(f"  Active LEAP paths: {len(all_leap_paths):,}  Subtotal paths: {len(subtotal_paths):,}")

    # ── leap_combined_esto ───────────────────────────────────────────────────
    sheet_name = "leap_combined_esto"
    ws = wb[sheet_name]
    print(f"\nSheet: {sheet_name}")
    u, sk = _update_sheet_leap_subtotals(ws, subtotal_paths)
    print(f"  leap_is_subtotal     -> updated={u}  skipped_blank_path={sk}")
    u, nf, sk = _update_sheet_column(
        ws,
        col_name="esto_pair_is_subtotal",
        key_col_names=["esto_flow", "esto_product"],
        lookup=esto_lookup,
    )
    print(f"  esto_pair_is_subtotal -> updated={u}  not_found={nf}  skipped_blank_key={sk}")

    # ── leap_combined_ninth ──────────────────────────────────────────────────
    sheet_name = "leap_combined_ninth"
    ws = wb[sheet_name]
    print(f"\nSheet: {sheet_name}")
    u, sk = _update_sheet_leap_subtotals(ws, subtotal_paths)
    print(f"  leap_is_subtotal      -> updated={u}  skipped_blank_path={sk}")
    u, nf, sk = _update_sheet_column(
        ws,
        col_name="ninth_pair_is_subtotal",
        key_col_names=["ninth_sector", "ninth_fuel"],
        lookup=ninth_lookup,
    )
    print(f"  ninth_pair_is_subtotal -> updated={u}  not_found={nf}  skipped_blank_key={sk}")

    # ── ninth_pairs_to_esto_pairs ────────────────────────────────────────────
    sheet_name = "ninth_pairs_to_esto_pairs"
    ws = wb[sheet_name]
    print(f"\nSheet: {sheet_name}")
    u, nf, sk = _update_sheet_column(
        ws,
        col_name="ninth_pair_is_subtotal",
        key_col_names=["9th_sector", "9th_fuel"],
        lookup=ninth_lookup,
    )
    print(f"  ninth_pair_is_subtotal -> updated={u}  not_found={nf}  skipped_blank_key={sk}")
    u, nf, sk = _update_sheet_column(
        ws,
        col_name="esto_pair_is_subtotal",
        key_col_names=["esto_flow", "esto_product"],
        lookup=esto_lookup,
    )
    print(f"  esto_pair_is_subtotal  -> updated={u}  not_found={nf}  skipped_blank_key={sk}")

    wb.save(WORKBOOK_PATH)
    print(f"\nSaved -> {WORKBOOK_PATH}")

    # ── Re-read updated sheets for QA ────────────────────────────────────────
    print("\nBuilding QA outputs …")
    df_lcesto = pd.read_excel(WORKBOOK_PATH, sheet_name="leap_combined_esto", dtype=object).fillna("")
    df_lcninth = pd.read_excel(WORKBOOK_PATH, sheet_name="leap_combined_ninth", dtype=object).fillna("")
    df_nesto = pd.read_excel(WORKBOOK_PATH, sheet_name="ninth_pairs_to_esto_pairs", dtype=object).fillna("")
    for df in [df_lcesto, df_lcninth, df_nesto]:
        for col in df.columns:
            df[col] = df[col].astype(str).map(_norm)

    QA_DIR.mkdir(parents=True, exist_ok=True)

    # Cardinality
    card_lcesto = _compute_cardinality(
        df_lcesto, "leap_sector_name_full_path", "raw_leap_fuel_name", "esto_flow", "esto_product"
    )
    card_lcninth = _compute_cardinality(
        df_lcninth, "leap_sector_name_full_path", "raw_leap_fuel_name", "ninth_sector", "ninth_fuel"
    )
    card_nesto = _compute_cardinality(
        df_nesto, "9th_sector", "9th_fuel", "esto_flow", "esto_product"
    )
    card_lcesto.to_csv(QA_DIR / "cardinality_leap_esto.csv", index=False)
    card_lcninth.to_csv(QA_DIR / "cardinality_leap_ninth.csv", index=False)
    card_nesto.to_csv(QA_DIR / "cardinality_ninth_esto.csv", index=False)
    print(f"  cardinality_leap_esto:  {len(card_lcesto):,} pairs  "
          f"({(card_lcesto['cardinality'] == 'one_to_one').sum():,} one-to-one)")
    print(f"  cardinality_leap_ninth: {len(card_lcninth):,} pairs  "
          f"({(card_lcninth['cardinality'] == 'one_to_one').sum():,} one-to-one)")
    print(f"  cardinality_ninth_esto: {len(card_nesto):,} pairs  "
          f"({(card_nesto['cardinality'] == 'one_to_one').sum():,} one-to-one)")

    # Unmapped pairs
    unmapped_esto = _unmapped_esto_pairs([df_lcesto, df_nesto], esto_lookup)
    unmapped_ninth = _unmapped_ninth_pairs([df_lcninth, df_nesto], ninth_lookup)
    unmapped_esto.to_csv(QA_DIR / "unmapped_esto_pairs.csv", index=False)
    unmapped_ninth.to_csv(QA_DIR / "unmapped_ninth_pairs.csv", index=False)
    print(f"  unmapped_esto_pairs:  {len(unmapped_esto):,}")
    print(f"  unmapped_ninth_pairs: {len(unmapped_ninth):,}")

    # Subtotal mismatches (M6)
    mm_esto = _subtotal_mismatches(
        df_lcesto,
        "leap_sector_name_full_path", "raw_leap_fuel_name",
        "esto_flow", "esto_product",
        "leap_is_subtotal", "esto_pair_is_subtotal",
    )
    mm_ninth = _subtotal_mismatches(
        df_lcninth,
        "leap_sector_name_full_path", "raw_leap_fuel_name",
        "ninth_sector", "ninth_fuel",
        "leap_is_subtotal", "ninth_pair_is_subtotal",
    )
    mm_nesto = _subtotal_mismatches(
        df_nesto,
        "9th_sector", "9th_fuel",
        "esto_flow", "esto_product",
        "ninth_pair_is_subtotal", "esto_pair_is_subtotal",
    )
    all_mm = pd.concat([
        mm_esto.assign(sheet="leap_combined_esto"),
        mm_ninth.assign(sheet="leap_combined_ninth"),
        mm_nesto.assign(sheet="ninth_pairs_to_esto_pairs"),
    ], ignore_index=True)
    all_mm.to_csv(QA_DIR / "subtotal_mismatches.csv", index=False)
    print(f"  subtotal_mismatches:  {len(all_mm):,}  (leaf source -> aggregate target)")

    print(f"\nQA outputs written to: {QA_DIR}")

    # --- M3: tree structure ---------------------------------------------------
    print("\nBuilding dataset tree structures …")
    from codebase.mapping_tools.build_dataset_tree_structure import run_tree_structure_workflow
    run_tree_structure_workflow()


if __name__ == "__main__":
    run()
