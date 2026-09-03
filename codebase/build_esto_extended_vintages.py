#%%
"""Build the ESTO Extended structural catalogue.

Former per-vintage numeric Extended tables remain legacy compatibility
artifacts only. They are not regenerated here and must not be historical data.
"""

#%%
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.mapping_tools.esto_extended_catalogue import build_structural_catalogue


VINTAGE_PATTERN = re.compile(
    r"^00APEC_(?P<vintage>\d{4})_low_with_subtotals(?P<preliminary>_PRELIMINARY)?\.csv$"
)
DATA_DIR = REPO_ROOT / "data"
MAPPING_WORKBOOK_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
AUDIT_ROOT = REPO_ROOT / "results" / "esto_extended_vintages"


def available_esto_vintages(data_dir: Path = DATA_DIR) -> list[tuple[int, Path, bool]]:
    """Return available raw ESTO issues in ascending issue order.

    Each entry is ``(vintage, base_path, is_preliminary)``. A ``_PRELIMINARY``
    suffix (e.g. ``00APEC_2026_low_with_subtotals_PRELIMINARY.csv``) marks an
    issue still missing economies or carrying backfilled/proxy figures — the
    Extended table built from it stays tagged the same way so it is never
    mistaken for a complete, reviewed vintage downstream.
    """
    found: list[tuple[int, Path, bool]] = []
    for path in sorted(data_dir.glob("00APEC_*_low_with_subtotals*.csv")):
        match = VINTAGE_PATTERN.match(path.name)
        if match:
            found.append((int(match.group("vintage")), path, bool(match.group("preliminary"))))
    return found


def extended_path_for_vintage(
    vintage: int, data_dir: Path = DATA_DIR, is_preliminary: bool = False
) -> Path:
    """Return the stable filename used by the dashboard release."""
    suffix = "_PRELIMINARY" if is_preliminary else ""
    return data_dir / f"esto_extended_{vintage}_low_with_subtotals{suffix}.csv"


def build_all_esto_extended_vintages(
    data_dir: Path = DATA_DIR,
    audit_root: Path = AUDIT_ROOT,
) -> pd.DataFrame:
    """Compatibility entrypoint that writes one non-numeric catalogue.

    Legacy registries and per-vintage files stay untouched until the portable
    consumer cutover; this builder no longer creates or selects them.
    """
    del audit_root
    catalogue_path = data_dir / "esto_extended_catalogue.csv"
    catalogue = build_structural_catalogue(MAPPING_WORKBOOK_PATH, catalogue_path)
    return pd.DataFrame([{
        "catalogue_path": str(catalogue_path.relative_to(REPO_ROOT)),
        "structural_pair_count": len(catalogue),
        "legacy_numeric_vintages": "deprecated_unmodified",
    }])


#%%
RUN_BUILD = False

if __name__ == "__main__":
    if RUN_BUILD:
        print(build_all_esto_extended_vintages().to_string(index=False))

#%%
