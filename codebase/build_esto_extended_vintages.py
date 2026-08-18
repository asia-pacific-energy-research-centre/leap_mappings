#%%
"""Build one ESTO Extended source table for each available ESTO vintage.

The raw ``00APEC_<issue>_low_with_subtotals.csv`` files remain the source of
truth.  Each generated Extended table is built from its matching raw issue so
historical values cannot accidentally be mixed between vintages.
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

from codebase.mapping_tools.build_esto_extended_test import build_esto_extended


VINTAGE_PATTERN = re.compile(
    r"^00APEC_(?P<vintage>\d{4})_low_with_subtotals(?P<preliminary>_PRELIMINARY)?\.csv$"
)
DATA_DIR = REPO_ROOT / "data"
LEAP_INITIALISATION_ROOT = Path(r"C:\Users\Work\github\leap_initialisation")
TEMPLATE_DIR = LEAP_INITIALISATION_ROOT / "data" / "leap_export_templates"
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


def _add_reviewed_green_electricity_rows(
    generated_path: Path,
    reviewed_extended_path: Path,
) -> int:
    """Carry the reviewed green-electricity structural keys to each vintage.

    These rows are deliberately structural zero rows.  Their mapping is
    reviewed separately from the vintage builder and they must be present in
    every Extended input so the green-electricity source can be admitted by
    the mapping chain without borrowing values from another issue.
    """
    generated = pd.read_csv(generated_path, dtype=object, low_memory=False)
    reviewed = pd.read_csv(reviewed_extended_path, dtype=object, low_memory=False)
    reviewed = reviewed.loc[reviewed["products"].eq("20 Green electricity")].copy()
    if reviewed.empty:
        return 0
    keys = ["economy", "flows", "products"]
    existing = set(map(tuple, generated[keys].itertuples(index=False, name=None)))
    additions = reviewed.loc[
        ~reviewed[keys].apply(tuple, axis=1).isin(existing)
    ].copy()
    if additions.empty:
        return 0
    for column in generated.columns:
        if column not in additions:
            additions[column] = ""
    additions = additions[generated.columns]
    year_columns = [column for column in generated.columns if str(column).isdigit()]
    additions[year_columns] = additions[year_columns].fillna("0")
    pd.concat([generated, additions], ignore_index=True).to_csv(generated_path, index=False)
    return len(additions)


def build_all_esto_extended_vintages(
    data_dir: Path = DATA_DIR,
    audit_root: Path = AUDIT_ROOT,
) -> pd.DataFrame:
    """Build and register all raw ESTO vintages currently present."""
    rows: list[dict[str, object]] = []
    for vintage, base_path, is_preliminary in available_esto_vintages(data_dir):
        output_path = extended_path_for_vintage(vintage, data_dir, is_preliminary=is_preliminary)
        audit_dir = audit_root / (f"{vintage}_PRELIMINARY" if is_preliminary else str(vintage))
        build_esto_extended(
            base_esto_path=base_path,
            template_dir=TEMPLATE_DIR,
            mapping_workbook_path=MAPPING_WORKBOOK_PATH,
            output_dir=audit_dir,
            production_dataset_path=output_path,
        )
        reviewed_rows = _add_reviewed_green_electricity_rows(
            output_path,
            data_dir / "esto_extended.csv",
        )
        years = [int(column) for column in pd.read_csv(base_path, nrows=0).columns if str(column).isdigit()]
        rows.append(
            {
                "vintage": vintage,
                "is_preliminary": is_preliminary,
                "base_year": max(years),
                "base_path": str(base_path.relative_to(REPO_ROOT)),
                "extended_path": str(output_path.relative_to(REPO_ROOT)),
                "extended_builder": "codebase.mapping_tools.build_esto_extended_test.build_esto_extended",
                "reviewed_structural_rows_added": reviewed_rows,
            }
        )
    registry = pd.DataFrame(
        rows,
        columns=[
            "vintage",
            "is_preliminary",
            "base_year",
            "base_path",
            "extended_path",
            "extended_builder",
            "reviewed_structural_rows_added",
        ],
    )
    registry.to_csv(data_dir / "esto_extended_vintage_registry.csv", index=False)
    return registry


#%%
RUN_BUILD = False

if __name__ == "__main__":
    if RUN_BUILD:
        print(build_all_esto_extended_vintages().to_string(index=False))

#%%
