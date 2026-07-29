#%%
"""Run the full value-delivery gate against the generated compatibility master.

Stage 1-2 inputs and all ordinary Stage 3 outputs stay under the separate-axis
shadow output tree. Deep tree/anchor diagnostics retain the pipeline's current
``results/tree_structure`` location.
"""

#%%
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path


# --- Stable paths -----------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_LEAP_EXPORTS_ROOT = (
    REPO_ROOT.parent.parent
    / "leap_initialisation"
    / "data"
    / "leap balances exports"
)
os.environ.setdefault(
    "LEAP_BALANCE_EXPORTS_ROOT",
    str(DEFAULT_LEAP_EXPORTS_ROOT),
)

import codebase.run_mapping_pipeline as pipeline  # noqa: E402

GENERATED_WORKBOOK_PATH = (
    REPO_ROOT
    / "config"
    / "outlook_mappings_master_generated_prototype.xlsx"
)
SHADOW_ROOT = (
    REPO_ROOT
    / "outputs"
    / "separate_axis_mapping_shadow_validation_20260729"
    / "generated"
)
RELATIONSHIP_DIR = SHADOW_ROOT / "mapping_relationships"
COMMON_ESTO_DIR = SHADOW_ROOT / "common_esto"


# --- Configuration ----------------------------------------------------------

def configure_shadow_pipeline_paths() -> None:
    """Point pipeline globals at the isolated generated-master output tree."""
    if not GENERATED_WORKBOOK_PATH.exists():
        raise FileNotFoundError(GENERATED_WORKBOOK_PATH)
    required_stage_1_2 = [
        RELATIONSHIP_DIR / "energy_balance_relationships.csv",
        COMMON_ESTO_DIR / "common_esto_rows.csv",
    ]
    missing = [
        str(path)
        for path in required_stage_1_2
        if not path.exists()
    ]
    if missing:
        raise FileNotFoundError(
            "Run the Stage 1-2 shadow workflow first:\n- "
            + "\n- ".join(missing)
        )

    pipeline.WORKBOOK_PATH = GENERATED_WORKBOOK_PATH
    pipeline.REL_DIR = RELATIONSHIP_DIR
    pipeline.COMMON_ESTO_DIR = COMMON_ESTO_DIR
    pipeline.STAGE3_RUN_MANIFEST_PATH = (
        COMMON_ESTO_DIR / "stage3_run_manifest.json"
    )
    pipeline.RAW_LEAP_PATH = (
        RELATIONSHIP_DIR / "raw_leap_results.csv"
    )
    pipeline.LEAP_ESTO_PATH = (
        RELATIONSHIP_DIR / "leap_results_converted_to_esto.csv"
    )
    pipeline.LEAP_ROLLUP_AUDIT_PATH = (
        RELATIONSHIP_DIR / "leap_source_rollup_audit.csv"
    )
    pipeline.LEAP_SOURCE_LINEAGE_PATH = (
        RELATIONSHIP_DIR
        / "leap_source_to_esto_component_lineage.csv.gz"
    )
    pipeline.NINTH_ESTO_PATH = (
        RELATIONSHIP_DIR / "ninth_results_converted_to_esto.csv.gz"
    )
    pipeline.NINTH_SOURCE_LINEAGE_PATH = (
        RELATIONSHIP_DIR
        / "ninth_source_to_esto_component_lineage.csv.gz"
    )
    pipeline.ESTO_ROWS_PATH = (
        RELATIONSHIP_DIR / "esto_results_exact_rows.csv.gz"
    )
    pipeline.ESTO_EXTENDED_ROWS_PATH = (
        RELATIONSHIP_DIR
        / "esto_extended_results_exact_rows.csv.gz"
    )
    pipeline.ESTO_EXTENDED_DELTA_PATH = (
        RELATIONSHIP_DIR
        / "esto_extended_results_exact_rows.delta.csv.gz"
    )
    pipeline.ESTO_EXTENDED_DELTA_MANIFEST_PATH = (
        RELATIONSHIP_DIR
        / "esto_extended_results_exact_rows.delta.json"
    )
    pipeline.RELATIONSHIPS_PATH = (
        RELATIONSHIP_DIR / "energy_balance_relationships.csv"
    )
    pipeline.COMMON_ROWS_PATH = (
        COMMON_ESTO_DIR / "common_esto_rows.csv"
    )
    pipeline.ESTO_COMPONENT_LINEAGE_PATH = (
        COMMON_ESTO_DIR
        / "esto_component_to_common_row_lineage.csv.gz"
    )


# --- Workflow ---------------------------------------------------------------

def run_separate_axis_stage3_shadow(
    *,
    parse_leap: bool = True,
    convert_data: bool = True,
    run_stage_3: bool = True,
    skip_deep_validation: bool = False,
) -> dict[str, object]:
    """Run source parsing, conversion, and Stage 3 on generated mappings."""
    configure_shadow_pipeline_paths()
    if parse_leap:
        pipeline.run_leap_parse()
    if convert_data:
        pipeline.run_data_convert()
    if run_stage_3:
        pipeline.run_stage_3(
            skip_deep_validation=skip_deep_validation,
        )

    manifest_path = COMMON_ESTO_DIR / "stage3_run_manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {
            "status": "stage3_not_run",
            "mapping_workbook": str(GENERATED_WORKBOOK_PATH),
        }
    )
    print(json.dumps(manifest, indent=2))
    return manifest


# --- Frequently changed run flags ------------------------------------------

# Disabled by default after the provisional graph reached about 9 GB during
# Ninth conversion. Review the structural source-once QA before enabling.
RUN_SEPARATE_AXIS_STAGE3_SHADOW = False
PARSE_LEAP = True
CONVERT_DATA = True
RUN_STAGE_3 = True
SKIP_DEEP_VALIDATION = False


#%%
if __name__ == "__main__" and RUN_SEPARATE_AXIS_STAGE3_SHADOW:
    try:
        STAGE3_SHADOW_MANIFEST = run_separate_axis_stage3_shadow(
            parse_leap=PARSE_LEAP,
            convert_data=CONVERT_DATA,
            run_stage_3=RUN_STAGE_3,
            skip_deep_validation=SKIP_DEEP_VALIDATION,
        )
    except Exception:
        print("Separate-axis Stage 3 shadow run failed.")
        traceback.print_exc()
        raise

#%%
