"""
apply_display_name_updates.py

Applies reviewed leap_display_names changes to config/outlook_mappings_master.xlsx.

The Stage 0 maintenance run (update_leap_display_names) no longer edits the
master.  It only reports proposed additions/updates to

    results/maintenance/display_names_proposed_updates.csv

This helper reads that review CSV, applies the rows the user has approved, and
writes them into the leap_display_names sheet.

A row is applied when its approval column
("CAN BE INSERTED INTO MAPPINGS") is truthy.

Safety gates
------------
1.  Dry-run summary printed first — counts and a sample of planned changes.
2.  Explicit "yes" required at the prompt before the workbook is touched
    (unless --yes is passed).
3.  Timestamped archive of the workbook written before the write.

Usage:
    python -m codebase.mapping_tools.apply_display_name_updates [--dry-run] [--yes]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import openpyxl
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.mapping_tools.update_leap_display_names import (
    PROPOSED_UPDATES_APPROVAL_COL,
    PROPOSED_UPDATES_FILENAME,
    _apply_updates_to_workbook,
    _read_display_names_sheet,
    _truthy,
)

WORKBOOK_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
ARCHIVE_DIR = REPO_ROOT / "config" / "archive"
REVIEW_CSV_PATH = REPO_ROOT / "results" / "maintenance" / PROPOSED_UPDATES_FILENAME


def _norm(value: Any) -> str:
    text = " ".join(str(value if value is not None else "").split())
    return "" if text.lower() in {"nan", "none"} else text


def load_approved_updates(
    review_csv_path: Path = REVIEW_CSV_PATH,
) -> list[tuple[tuple[str, str], str, str, bool]]:
    """Return approved (key, auto_name, leap_display_name, matches_original) rows.

    Matches the update tuple shape expected by _apply_updates_to_workbook.
    """
    if not review_csv_path.exists():
        print(f"  [WARN] review CSV not found: {review_csv_path}")
        return []

    df = pd.read_csv(review_csv_path, dtype=object).fillna("")
    if PROPOSED_UPDATES_APPROVAL_COL not in df.columns:
        print(
            f"  [WARN] approval column '{PROPOSED_UPDATES_APPROVAL_COL}' missing "
            f"in {review_csv_path.name} — nothing to apply"
        )
        return []

    approved = df[df[PROPOSED_UPDATES_APPROVAL_COL].map(_truthy)]
    print(
        f"  {review_csv_path.name}: {len(approved)} row(s) approved "
        f"(of {len(df)} proposed)"
    )

    updates: list[tuple[tuple[str, str], str, str, bool]] = []
    for _, row in approved.iterrows():
        code_type = _norm(row.get("code_type", ""))
        code = _norm(row.get("code", ""))
        if not code_type or not code:
            continue
        auto_name = _norm(row.get("auto_name", ""))
        leap_display_name = _norm(row.get("proposed_leap_display_name", ""))
        matches_original = _truthy(row.get("proposed_matches_original_product_flow_name", ""))
        updates.append(((code_type, code), auto_name, leap_display_name, matches_original))
    return updates


def _print_summary(updates: list[tuple[tuple[str, str], str, str, bool]]) -> None:
    print("\n" + "=" * 70)
    print("PLANNED leap_display_names CHANGES")
    print("=" * 70)
    if not updates:
        print("  No approved changes to apply.")
        return
    print(f"  {'code_type':<16} {'code':<40} {'proposed_leap_display_name'}")
    print(f"  {'-' * 16} {'-' * 40} {'-' * 30}")
    for (code_type, code), _auto, leap_display_name, _matches in updates[:30]:
        print(f"  {code_type:<16} {code[:40]:<40} {leap_display_name}")
    if len(updates) > 30:
        print(f"  ... and {len(updates) - 30} more")
    print(f"\n  Total: {len(updates)} row(s)")


def _archive(workbook_path: Path) -> Path:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = ARCHIVE_DIR / f"{workbook_path.stem}.before_display_name_apply_{ts}.xlsx"
    shutil.copy2(workbook_path, dest)
    print(f"\nArchived: {dest}")
    return dest


def apply_updates(
    updates: list[tuple[tuple[str, str], str, str, bool]],
    workbook_path: Path = WORKBOOK_PATH,
) -> int:
    """Write approved updates into the leap_display_names sheet. Returns count."""
    wb = openpyxl.load_workbook(str(workbook_path))
    headers, rows_data = _read_display_names_sheet(wb)
    _apply_updates_to_workbook(wb, headers, rows_data, updates)
    wb.save(str(workbook_path))
    wb.close()
    return len(updates)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned changes without writing anything.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt.",
    )
    args = parser.parse_args()

    print("Loading approved display-name updates...")
    updates = load_approved_updates()
    _print_summary(updates)

    if not updates:
        print("\nNothing to do.")
        return

    if args.dry_run:
        print("\n[DRY RUN] No changes written.")
        return

    if not args.yes:
        print("\n" + "=" * 70)
        print("CONFIRMATION REQUIRED")
        print("=" * 70)
        print(f"About to write {len(updates)} row(s) to leap_display_names in:")
        print(f"  {WORKBOOK_PATH}")
        print("A timestamped archive will be created first.")
        answer = input("\nType 'yes' to proceed, anything else to abort: ").strip().lower()
        if answer != "yes":
            print("Aborted — no changes made.")
            sys.exit(0)

    _archive(WORKBOOK_PATH)
    written = apply_updates(updates, WORKBOOK_PATH)
    print(f"\nDone. Applied {written} row(s) to leap_display_names.")


if __name__ == "__main__":
    main()
