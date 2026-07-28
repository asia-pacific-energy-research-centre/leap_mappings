#%%
"""Build the versioned hierarchy/subtotal contract and review-only artifacts."""

#%%
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.mapping_tools.hierarchy_subtotal_adapters import (  # noqa: E402
    build_ninth_family_conformance,
    current_adapter_registry,
)
from codebase.mapping_tools.hierarchy_subtotal_contract import (  # noqa: E402
    build_contract_frames,
    load_contract,
    write_contract,
)
from codebase.mapping_tools.hierarchy_subtotal_review import (  # noqa: E402
    build_review_frames,
    write_review_csvs,
)


def _resolve(path: str | Path) -> Path:
    normalized = Path(str(path).replace("\\", "/"))
    return normalized if normalized.is_absolute() else REPO_ROOT / normalized


def build_hierarchy_subtotal_contract(
    workbook_path: str | Path,
    exception_workbook_path: str | Path,
    output_dir: str | Path,
    review_csv_dir: str | Path,
    include_ninth_value_diagnostics: bool = True,
) -> tuple[dict[str, object], dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """Build, strictly reload, and prepare a non-writing workbook review."""
    workbook_path = _resolve(workbook_path)
    exception_workbook_path = _resolve(exception_workbook_path)
    output_dir = _resolve(output_dir)
    review_csv_dir = _resolve(review_csv_dir)
    adapters = current_adapter_registry(REPO_ROOT, workbook_path)
    frames, registry = build_contract_frames(adapters)
    ninth_path = REPO_ROOT / "data" / "merged_file_energy_ALL_20251106.csv"
    if include_ninth_value_diagnostics:
        frames["value_conformance_diagnostics"] = pd.concat(
            [
                frames["value_conformance_diagnostics"],
                build_ninth_family_conformance(ninth_path),
            ],
            ignore_index=True,
        )
    input_paths = [
        workbook_path,
        exception_workbook_path,
        REPO_ROOT / "data" / "00APEC_2025_low_with_subtotals.csv",
        ninth_path,
        REPO_ROOT / "data" / "temp" / "new leap rows.xlsx",
        REPO_ROOT / "results" / "tree_structure" / "esto_extended_tree.csv",
        REPO_ROOT / "results" / "tree_structure" / "common_esto_tree.csv",
    ]
    manifest = write_contract(
        output_dir=output_dir,
        frames=frames,
        registry=registry,
        input_paths=input_paths,
        repo_root=REPO_ROOT,
        compatibility={
            "leap_dashboard": "hierarchy_subtotal_contract_v1",
            "leap_initialisation": "hierarchy_subtotal_contract_v1",
            "common_esto_output_contract": "separate referenced structural contract",
        },
    )
    # Fail closed immediately if the selected build cannot be verified.
    _, loaded_frames = load_contract(
        output_dir,
        expected_build_id=str(manifest["build_id"]),
    )
    review_frames = build_review_frames(
        workbook_path,
        exception_workbook_path,
        loaded_frames,
    )
    write_review_csvs(review_csv_dir, review_frames)
    return manifest, loaded_frames, review_frames


# --- Notebook run block ---

BUILD_CONTRACT = False
MAPPING_WORKBOOK_PATH = "config/outlook_mappings_master todo.xlsx"
EXCEPTION_WORKBOOK_PATH = "config/mapping_issue_exception_sets.xlsx"
CONTRACT_OUTPUT_DIR = "results/hierarchy_subtotal_contract/current"
REVIEW_CSV_DIR = "results/hierarchy_subtotal_contract/review_csv"
INCLUDE_NINTH_VALUE_DIAGNOSTICS = True

if BUILD_CONTRACT:
    MANIFEST, CONTRACT_FRAMES, REVIEW_FRAMES = build_hierarchy_subtotal_contract(
        workbook_path=MAPPING_WORKBOOK_PATH,
        exception_workbook_path=EXCEPTION_WORKBOOK_PATH,
        output_dir=CONTRACT_OUTPUT_DIR,
        review_csv_dir=REVIEW_CSV_DIR,
        include_ninth_value_diagnostics=INCLUDE_NINTH_VALUE_DIAGNOSTICS,
    )
    print(f"Built hierarchy contract: {MANIFEST['build_id']}")
    print(REVIEW_FRAMES["summary"].to_string(index=False))

#%%
