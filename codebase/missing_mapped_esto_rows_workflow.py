#%%
"""Generate review-only ESTO rows required by maintained mapping structures.

This is an optional source-maintenance workflow, not a mapping-pipeline stage.
It never edits the source ESTO CSVs or the canonical mapping workbook. Review
the generated files before using ``propagate_esto_rows_workflow.py`` to apply
an explicitly chosen row set.
"""

#%%
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.mapping_tools.build_missing_mapped_esto_rows import (  # noqa: E402
    write_missing_mapped_esto_rows,
)


DEFAULT_ESTO_SOURCE_PATHS = (
    REPO_ROOT / "data" / "00APEC_2025_low_with_subtotals.csv",
    REPO_ROOT / "data" / "00APEC_2024_low_with_subtotals.csv",
)
DEFAULT_MAPPING_WORKBOOK_PATH = (
    REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
)
DEFAULT_NINTH_SOURCE_PATH = (
    REPO_ROOT / "data" / "merged_file_energy_ALL_20251106.csv"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "results" / "maintenance" / "missing_mapped_esto_rows"
)


def _resolve(path: str | Path) -> Path:
    """Resolve notebook-friendly paths against the repository root."""
    normalized = Path(str(path).replace("\\", "/"))
    return normalized if normalized.is_absolute() else REPO_ROOT / normalized


def run_missing_mapped_esto_rows_review(
    esto_source_paths: tuple[str | Path, ...] = DEFAULT_ESTO_SOURCE_PATHS,
    mapping_workbook_path: str | Path = DEFAULT_MAPPING_WORKBOOK_PATH,
    ninth_source_path: str | Path = DEFAULT_NINTH_SOURCE_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> pd.DataFrame:
    """Write paste-ready rows and audit files without modifying source inputs."""
    resolved_esto_paths = tuple(_resolve(path) for path in esto_source_paths)
    resolved_mapping_path = _resolve(mapping_workbook_path)
    resolved_ninth_path = _resolve(ninth_source_path)
    missing_inputs = [
        path
        for path in (
            *resolved_esto_paths,
            resolved_mapping_path,
            resolved_ninth_path,
        )
        if not path.exists()
    ]
    if missing_inputs:
        formatted = "\n".join(f"- {path}" for path in missing_inputs)
        raise FileNotFoundError(
            "Missing input(s) for the ESTO-row review workflow:\n"
            f"{formatted}"
        )

    return write_missing_mapped_esto_rows(
        esto_csv_paths=list(resolved_esto_paths),
        mapping_workbook_path=resolved_mapping_path,
        ninth_csv_path=resolved_ninth_path,
        output_dir=_resolve(output_dir),
    )


# --- Notebook run block ---

RUN_MISSING_MAPPED_ESTO_ROWS_REVIEW = False

if RUN_MISSING_MAPPED_ESTO_ROWS_REVIEW:
    REVIEW_SUMMARY = run_missing_mapped_esto_rows_review()
    print(REVIEW_SUMMARY.to_string(index=False))

#%%
