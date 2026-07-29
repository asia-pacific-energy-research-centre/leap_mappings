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

import pandas as pd


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
from codebase.separate_axis_mapping_shadow_validation_workflow import (  # noqa: E402
    _build_structural_source_once_diagnostic,
)

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
STAGE_2_COMMON_VARIANT = os.environ.get(
    "SEPARATE_AXIS_STAGE2_COMMON_LABEL",
    "generated",
)
RELATIONSHIP_DIR = SHADOW_ROOT / "mapping_relationships"
COMMON_ESTO_DIR = (
    REPO_ROOT
    / "outputs"
    / "separate_axis_mapping_shadow_validation_20260729"
    / STAGE_2_COMMON_VARIANT
    / "common_esto"
)


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

def shadow_stage3_source_paths() -> dict[str, Path]:
    """Return explicit cached sources for the isolated shadow output tree."""
    return {
        "LEAP": pipeline.LEAP_ESTO_PATH,
        "NINTH": pipeline.NINTH_ESTO_PATH,
        "ESTO": pipeline.ESTO_ROWS_PATH,
        "ESTO_EXTENDED": pipeline.ESTO_EXTENDED_ROWS_PATH,
    }


def _read_optional_csv(
    path: Path,
    usecols: list[str] | None = None,
) -> pd.DataFrame:
    """Read one generated QA table, returning an empty frame when absent."""
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, usecols=usecols, low_memory=False)


def write_stage3_shadow_gate_summary() -> dict[str, object]:
    """Publish compact structural, value, and contract gate evidence."""
    relationships = pd.read_csv(
        RELATIONSHIP_DIR / "energy_balance_relationships.csv",
        low_memory=False,
    )
    common_map = pd.read_csv(
        COMMON_ESTO_DIR / "esto_to_common_esto_map.csv",
        low_memory=False,
    )
    split_groups = _read_optional_csv(
        COMMON_ESTO_DIR / "qa_common_esto_source_aggregates_split.csv"
    )
    source_once = _build_structural_source_once_diagnostic(
        relationships,
        common_map,
        STAGE_2_COMMON_VARIANT,
        split_groups,
    )
    source_once_path = (
        COMMON_ESTO_DIR
        / "stage3_structural_source_once_diagnostic.csv"
    )
    source_once.to_csv(source_once_path, index=False)

    total_check = _read_optional_csv(
        COMMON_ESTO_DIR / "common_esto_total_check.csv"
    )
    total_summary = (
        total_check.groupby(
            ["comparison_scope", "source_system"],
            dropna=False,
            as_index=False,
        )[["source_total", "common_total", "difference"]]
        .sum()
        if not total_check.empty
        else pd.DataFrame()
    )
    maximum_abs_difference = (
        float(total_check["difference"].abs().max())
        if not total_check.empty
        else None
    )
    output_status = _read_optional_csv(
        COMMON_ESTO_DIR / "common_esto_output_status.csv"
    )
    output_status_counts = (
        output_status["status"].value_counts().to_dict()
        if not output_status.empty
        else {}
    )
    stage3_manifest_path = COMMON_ESTO_DIR / "stage3_run_manifest.json"
    contract_path = (
        COMMON_ESTO_DIR / "common_esto_output_contract.json"
    )
    stage3_manifest = json.loads(
        stage3_manifest_path.read_text(encoding="utf-8")
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    broad_rows = _read_optional_csv(
        COMMON_ESTO_DIR
        / "diagnostics"
        / "broad_common_row_summary.csv"
    )
    partial_rows = _read_optional_csv(
        COMMON_ESTO_DIR
        / "qa_common_esto_unresolved_partial_coverage.csv"
    )
    unmapped_leap = _read_optional_csv(
        COMMON_ESTO_DIR / "qa_nonzero_unmapped_leap_branches.csv"
    )
    highly_recommended = _read_optional_csv(
        COMMON_ESTO_DIR / "highly_recommended_mapping_candidates.csv"
    )
    missing_map = _read_optional_csv(
        COMMON_ESTO_DIR
        / "common_esto_source_rows_missing_common_map.csv",
        usecols=["source_system"],
    )

    unsafe_count = int(
        source_once["source_once_status"]
        .eq("unsafe_multiple_common_rows")
        .sum()
    )
    protected_count = int(
        source_once["source_once_status"]
        .eq("protected_parent_detail_alternative")
        .sum()
    )
    value_gate_passed = (
        maximum_abs_difference is not None
        and maximum_abs_difference <= 1e-8
    )
    output_gate_passed = (
        bool(output_status_counts)
        and set(output_status_counts) == {"passed"}
    )
    completed_stage3 = str(stage3_manifest.get("status", "")).startswith(
        "completed"
    )
    gate_passed = (
        completed_stage3
        and unsafe_count == 0
        and value_gate_passed
        and output_gate_passed
    )
    summary = {
        "status": (
            "passed_with_review_findings"
            if gate_passed
            else "failed"
        ),
        "stage2_common_variant": STAGE_2_COMMON_VARIANT,
        "mapping_workbook": str(GENERATED_WORKBOOK_PATH.resolve()),
        "stage3_run_id": stage3_manifest.get("run_id", ""),
        "stage3_status": stage3_manifest.get("status", ""),
        "deep_validation_status": (
            "skipped_by_explicit_shadow_flag"
            if stage3_manifest.get("status")
            == "completed_skip_deep_validation"
            else "see_stage3_manifest"
        ),
        "structural_source_once": {
            "groups_checked": int(len(source_once)),
            "one_common_row": int(
                source_once["source_once_status"]
                .eq("one_common_row")
                .sum()
            ),
            "protected_parent_detail_alternatives": protected_count,
            "unsafe_multiple_common_rows": unsafe_count,
            "maximum_common_rows_per_source_pair": int(
                source_once["common_row_count"].max()
            ),
            "diagnostic_path": str(source_once_path.resolve()),
        },
        "mapped_value_delivery": {
            "scope_source_combinations": int(len(total_summary)),
            "maximum_absolute_difference": maximum_abs_difference,
            "tolerance": 1e-8,
            "passed": value_gate_passed,
        },
        "output_contract": {
            "contract_version": contract.get("contract_version", ""),
            "fact_rows": contract.get("fact", {}).get("row_count", 0),
            "metadata_rows": contract.get("metadata", {}).get(
                "row_count",
                0,
            ),
            "output_status_counts": output_status_counts,
            "passed": output_gate_passed,
        },
        "review_findings": {
            "broad_common_rows": int(len(broad_rows)),
            "maximum_components_in_broad_row": (
                int(broad_rows["exact_component_count"].max())
                if not broad_rows.empty
                else 0
            ),
            "partial_coverage_rows": int(len(partial_rows)),
            "nonzero_unmapped_leap_branches": int(len(unmapped_leap)),
            "highly_recommended_mapping_candidates": int(
                len(highly_recommended)
            ),
            "source_rows_without_exact_common_map": int(len(missing_map)),
        },
    }
    summary_path = (
        COMMON_ESTO_DIR / "separate_axis_stage3_shadow_gate.json"
    )
    summary_path.write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return summary


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
            chunk_value_application=True,
            stage3_source_paths=shadow_stage3_source_paths(),
        )
        write_stage3_shadow_gate_summary()

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

# Disabled by default because Stage 3 is an explicit full-data shadow gate.
# The workflow uses economy-bounded Ninth conversion and value application.
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
