"""
run_mapping_pipeline.py

End-to-end mapping pipeline for LEAP -> ESTO / 9th Outlook comparison.

Stages
------
0  Maintenance — update subtotal flags, produce QA outputs, build tree structure
1  Relationships — build energy_balance_relationships.csv from outlook_mappings_master.xlsx
2  Common ESTO structure — build common comparison rows via graph partitioning
   LEAP parse   — parse raw LEAP balance xlsx exports to long-format CSV
   Data convert — convert LEAP and 9th data to ESTO-style rows
   ESTO rows    — prepare non-subtotal ESTO rows as long-format CSV
3  Apply structure — map all sources to common comparison rows and aggregate

Run all stages:
    python codebase/run_mapping_pipeline.py

Apply Stage 0 subtotal changes before continuing (reviewed overrides win):
    python codebase/run_mapping_pipeline.py --apply-maintenance

Run specific stages (comma-separated):
    python codebase/run_mapping_pipeline.py --stages 1,2,3

Skip stages:
    python codebase/run_mapping_pipeline.py --skip 0
"""

from __future__ import annotations

import argparse
import gc
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Repo root
# ---------------------------------------------------------------------------

def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "config" / "outlook_mappings_master.xlsx").exists():
            return parent
    raise RuntimeError("Could not locate repo root.")

REPO_ROOT = _find_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

WORKBOOK_PATH       = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
ESTO_CSV_PATH       = REPO_ROOT / "data" / "00APEC_2025_low_with_subtotals.csv"
NINTH_CSV_PATH      = REPO_ROOT / "data" / "merged_file_energy_ALL_20251106.csv"

REL_DIR             = REPO_ROOT / "results" / "mapping_relationships"
COMMON_ESTO_DIR     = REPO_ROOT / "results" / "common_esto"

RAW_LEAP_PATH       = REL_DIR / "raw_leap_results.csv"
LEAP_ESTO_PATH      = REL_DIR / "leap_results_converted_to_esto.csv"
LEAP_ROLLUP_AUDIT_PATH = REL_DIR / "leap_source_rollup_audit.csv"
NINTH_ESTO_PATH     = REL_DIR / "ninth_results_converted_to_esto.csv"
ESTO_ROWS_PATH      = REL_DIR / "esto_results_exact_rows.csv"
RELATIONSHIPS_PATH  = REL_DIR / "energy_balance_relationships.csv"
COMMON_ROWS_PATH    = COMMON_ESTO_DIR / "common_esto_rows.csv"

# Aggregate comparisons that require the exact ESTO parent alongside the
# ordinary non-subtotal frontier. Other dashboard totals are currently built
# from their reviewed additive frontiers.
ESTO_REFERENCE_ROLLUP_LABELS = {"Total transformation - no transfers"}

# LEAP export directory — check both this repo and leap_initialisation
def _default_leap_export_dir() -> Path:
    local = REPO_ROOT / "data" / "leap balances exports" / "20_USA"
    if local.exists():
        return local
    sibling = REPO_ROOT.parent / "leap_initialisation" / "data" / "leap balances exports" / "20_USA"
    if sibling.exists():
        return sibling
    return local  # return local even if it doesn't exist; error will surface in stage

LEAP_EXPORT_DIR = _default_leap_export_dir()

# ---------------------------------------------------------------------------
# Output logging
# ---------------------------------------------------------------------------
_PIPELINE_LOG_PATH = REPO_ROOT / "results" / "logs" / "mapping_pipeline.log"


class _TeeWriter:
    def __init__(self, file_obj, stream):
        self._file = file_obj
        self._stream = stream

    def write(self, data):
        self._file.write(data)
        self._stream.write(data)
        return len(data)

    def flush(self):
        self._file.flush()
        self._stream.flush()

    def isatty(self):
        return False


@contextmanager
def _log_to_file(log_path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    original = sys.stdout
    with open(log_path, "w", encoding="utf-8") as f:
        sys.stdout = _TeeWriter(f, original)
        try:
            yield log_path
        finally:
            sys.stdout = original


# ---------------------------------------------------------------------------
# Stage 0 — Maintenance
# ---------------------------------------------------------------------------

def run_stage_0(apply_subtotal_changes: bool = False) -> None:
    print("\n" + "=" * 60)
    print("STAGE 0  Maintenance")
    print("=" * 60)
    from codebase.outlook_mapping_maintenance_workflow import run as maintenance_run
    maintenance_run(apply_subtotal_changes_to_workbook=apply_subtotal_changes)


# ---------------------------------------------------------------------------
# Stage 1 — Build relationships
# ---------------------------------------------------------------------------

def run_stage_1() -> None:
    print("\n" + "=" * 60)
    print("STAGE 1  Build energy balance relationships")
    print("=" * 60)
    from codebase.mapping_tools.build_energy_balance_relationships import (
        COMPACT_CATALOGUE_CSV_PATH,
        FALLBACK_WORKBOOK_PATH,
        MAPPING_WORKBOOK_PATH,
        OUTPUT_CSV_PATH,
        OUTPUT_XLSX_PATH,
        QA_DIR,
        SHEET_CONFIGS,
        run_relationship_workflow,
    )
    run_relationship_workflow(
        mapping_workbook_path=MAPPING_WORKBOOK_PATH,
        fallback_workbook_path=FALLBACK_WORKBOOK_PATH,
        sheet_configs=SHEET_CONFIGS,
        output_csv_path=OUTPUT_CSV_PATH,
        output_xlsx_path=OUTPUT_XLSX_PATH,
        compact_catalogue_csv_path=COMPACT_CATALOGUE_CSV_PATH,
        qa_dir=QA_DIR,
    )


# ---------------------------------------------------------------------------
# Stage 2 — Common ESTO structure
# ---------------------------------------------------------------------------

def run_stage_2() -> None:
    print("\n" + "=" * 60)
    print("STAGE 2  Build common ESTO structure")
    print("=" * 60)
    from codebase.mapping_tools.build_common_esto_structure import (
        COMMON_ESTO_LABEL_OVERRIDES_PATH,
        COMMON_ESTO_OVERRIDES_PATH,
        COVERAGE_EXCLUSIONS_PATH,
        OUTPUT_DIR,
        OUTLOOK_MAPPINGS_PATH,
        RELATIONSHIPS_PATH as STAGE_2_RELATIONSHIPS_PATH,
        run_common_esto_structure_workflow,
    )
    run_common_esto_structure_workflow(
        relationships_path=STAGE_2_RELATIONSHIPS_PATH,
        coverage_exclusions_path=COVERAGE_EXCLUSIONS_PATH,
        common_esto_overrides_path=COMMON_ESTO_OVERRIDES_PATH,
        common_esto_label_overrides_path=COMMON_ESTO_LABEL_OVERRIDES_PATH,
        outlook_mappings_path=OUTLOOK_MAPPINGS_PATH,
        output_dir=OUTPUT_DIR,
    )


# ---------------------------------------------------------------------------
# LEAP parse — produce raw_leap_results.csv
# ---------------------------------------------------------------------------

def run_leap_parse() -> None:
    print("\n" + "=" * 60)
    print("LEAP PARSE  Parse LEAP balance exports")
    print("=" * 60)
    if not LEAP_EXPORT_DIR.exists():
        print(f"  WARNING: LEAP export directory not found: {LEAP_EXPORT_DIR}")
        print("  Skipping LEAP parse. Set LEAP_EXPORT_DIR in run_mapping_pipeline.py")
        return

    from codebase.mapping_tools.parse_leap_balance_export import parse_leap_balance_dir
    parse_leap_balance_dir(LEAP_EXPORT_DIR, RAW_LEAP_PATH)


# ---------------------------------------------------------------------------
# Data convert — LEAP and 9th to ESTO-style rows
# ---------------------------------------------------------------------------

def run_leap_to_esto() -> None:
    print("\n" + "-" * 40)
    print("  LEAP -> ESTO conversion")
    if not RAW_LEAP_PATH.exists():
        print(f"  WARNING: {RAW_LEAP_PATH.name} not found — run LEAP parse first.")
        return

    from codebase.mapping_tools.convert_leap_results_to_esto import run_conversion
    run_conversion(
        leap_results_path=RAW_LEAP_PATH,
        relationships_path=RELATIONSHIPS_PATH,
        output_path=LEAP_ESTO_PATH,
        mapping_workbook_path=WORKBOOK_PATH,
        rollup_audit_path=LEAP_ROLLUP_AUDIT_PATH,
    )


def run_ninth_to_esto() -> None:
    print("\n" + "-" * 40)
    print("  9th -> ESTO conversion")
    if not NINTH_CSV_PATH.exists():
        print(f"  WARNING: {NINTH_CSV_PATH.name} not found.")
        return

    import time

    from codebase.mapping_tools.apply_ninth_to_esto_conversion import (
        prepare_ninth_long_format,
        load_ninth_to_esto_relationships,
        convert_ninth_results_to_esto,
    )
    # Load the mapping first so the wide 9th frame can be filtered to only
    # sector/fuel pairs with an included ESTO mapping *before* the year melt.
    relationships_df = load_ninth_to_esto_relationships(RELATIONSHIPS_PATH)
    mapped_pairs = set(
        zip(
            relationships_df["source_flow"].astype(str),
            relationships_df["source_product"].astype(str),
        )
    )
    print("  Preparing 9th long-format data (filter-before-melt) …")
    _t = time.perf_counter()
    ninth_long = prepare_ninth_long_format(NINTH_CSV_PATH, mapped_pairs=mapped_pairs)
    print(
        f"  9th long-format rows: {len(ninth_long):,} "
        f"(prepared in {time.perf_counter() - _t:.1f}s)"
    )

    converted_df = convert_ninth_results_to_esto(ninth_long, relationships_df)

    NINTH_ESTO_PATH.parent.mkdir(parents=True, exist_ok=True)
    converted_df.to_csv(NINTH_ESTO_PATH, index=False)
    print(f"  Conversion relationships used: {len(relationships_df):,}")
    print(f"  Converted ESTO rows written: {len(converted_df):,}")
    print(f"  Wrote: {NINTH_ESTO_PATH.relative_to(REPO_ROOT)}")


def configured_rollup_reference_pairs(
    relationships_df: pd.DataFrame,
    leap_rollup_rules_df: pd.DataFrame,
    retained_rollup_labels: set[str],
) -> set[tuple[str, str]]:
    """Return exact ESTO pairs explicitly targeted by configured LEAP rollups."""
    if relationships_df.empty or leap_rollup_rules_df.empty:
        return set()
    included_rules = leap_rollup_rules_df[
        leap_rollup_rules_df["include"].astype(str).str.strip().str.lower().isin({"true", "1", "yes"})
    ]
    rolled_flows = {
        str(value).strip()
        for value in included_rules["rolled_leap_sector_name_full_path"]
        if str(value).strip() in retained_rollup_labels
    }
    if not rolled_flows:
        return set()
    include_mask = relationships_df["include_in_use_case"].astype(str).str.strip().str.lower().isin(
        {"true", "1", "yes"}
    )
    reference_rows = relationships_df[
        include_mask
        & (relationships_df["source_system"].astype(str) == "LEAP")
        & (relationships_df["target_system"].astype(str) == "ESTO")
        & ~relationships_df["is_rollup_derived"].astype(str).str.strip().str.lower().isin({"true", "1", "yes"})
        & relationships_df["source_flow"].astype(str).isin(rolled_flows)
    ]
    return {
        (str(flow).strip(), str(product).strip())
        for flow, product in reference_rows[["target_flow", "target_product"]].itertuples(index=False, name=None)
        if str(flow).strip() and str(product).strip()
    }


def select_esto_comparison_rows(
    esto_df: pd.DataFrame,
    rollup_reference_pairs: set[tuple[str, str]],
) -> pd.DataFrame:
    """Keep ESTO leaves plus exact parent pairs required by configured rollups.

    rollup_reference_pairs: retain specific (flow, product) subtotal pairs
        needed by LEAP rollup comparisons (e.g. 'Total transformation - no transfers').
    """
    leaf_mask = esto_df["is_subtotal"].astype(str).str.strip().str.lower() == "false"
    if not rollup_reference_pairs:
        return esto_df[leaf_mask].copy()
    pair_mask = pd.Series(
        [
            (str(flow).strip(), str(product).strip()) in rollup_reference_pairs
            for flow, product in esto_df[["flows", "products"]].itertuples(index=False, name=None)
        ],
        index=esto_df.index,
    )
    return esto_df[leaf_mask | pair_mask].copy()


def run_esto_exact_rows() -> None:
    print("\n" + "-" * 40)
    print("  ESTO exact rows")
    if not ESTO_CSV_PATH.exists():
        print(f"  WARNING: {ESTO_CSV_PATH.name} not found.")
        return

    df = pd.read_csv(ESTO_CSV_PATH, dtype=object)
    year_cols = [c for c in df.columns if str(c).isdigit()]
    for col in year_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    relationships_df = pd.read_csv(RELATIONSHIPS_PATH, dtype=object).fillna("")
    if "is_rollup_derived" not in relationships_df.columns:
        relationships_df["is_rollup_derived"] = "False"
    leap_rollup_rules_df = pd.read_excel(
        WORKBOOK_PATH,
        sheet_name="leap_rollup_rules",
        dtype=object,
    ).fillna("")
    reference_pairs = configured_rollup_reference_pairs(
        relationships_df=relationships_df,
        leap_rollup_rules_df=leap_rollup_rules_df,
        retained_rollup_labels=ESTO_REFERENCE_ROLLUP_LABELS,
    )
    del relationships_df, leap_rollup_rules_df
    df_leaf = select_esto_comparison_rows(df, reference_pairs)
    del df
    gc.collect()

    id_cols = ["economy", "flows", "products"]
    long_df = df_leaf[id_cols + year_cols].melt(
        id_vars=id_cols,
        value_vars=year_cols,
        var_name="year",
        value_name="value",
    ).dropna(subset=["value"])

    long_df = long_df.rename(columns={"flows": "esto_flow", "products": "esto_product"})
    long_df["source_system"] = "ESTO"
    long_df["scenario"] = "historical"
    long_df["year"] = long_df["year"].astype(int)

    ESTO_ROWS_PATH.parent.mkdir(parents=True, exist_ok=True)
    long_df.to_csv(ESTO_ROWS_PATH, index=False)
    print(f"  ESTO exact rows: {len(long_df):,} -> {ESTO_ROWS_PATH.relative_to(REPO_ROOT)}")
    print(f"  Configured rollup reference pairs retained: {len(reference_pairs):,}")


def run_data_convert() -> None:
    print("\n" + "=" * 60)
    print("DATA CONVERT  LEAP, 9th, ESTO -> common input format")
    print("=" * 60)
    run_leap_to_esto()
    run_ninth_to_esto()
    run_esto_exact_rows()


# ---------------------------------------------------------------------------
# Stage 3 — Apply common ESTO structure
# ---------------------------------------------------------------------------

def run_stage_3() -> None:
    import time
    stage3_t0 = time.perf_counter()
    print("\n" + "=" * 60)
    print("STAGE 3  Apply common ESTO structure to source data")
    print("=" * 60)

    missing = [
        p for p in [LEAP_ESTO_PATH, NINTH_ESTO_PATH, ESTO_ROWS_PATH, COMMON_ROWS_PATH]
        if not p.exists()
    ]
    if missing:
        print("  WARNING: Missing input files for Stage 3:")
        for p in missing:
            print(f"    {p.relative_to(REPO_ROOT)}")
        print("  Run earlier stages first.")
        return

    from codebase.mapping_tools.apply_common_esto_structure import run_apply_common_esto_structure
    from codebase.mapping_tools.build_dataset_tree_structure import (
        LEAP_VAR_BASE_YEAR,
        _build_source_inconsistency_lookup,
        build_common_esto_tree,
        build_esto_tree,
        build_leap_tree,
        build_ninth_tree,
        validate_leap_recursive_sums,
        validate_ninth_fuel_recursive_sums,
        validate_ninth_recursive_sums,
        validate_ninth_sector_recursive_sums,
    )
    from codebase.mapping_tools.common_esto_validation_orchestration import (
        run_common_esto_validation_workflow,
    )
    from codebase.mapping_tools.source_parent_anchor_validation import (
        ANCHOR_COLUMNS,
        load_raw_source_anchor_inputs,
        summarise_source_parent_anchors,
        validate_source_parent_anchors,
    )

    run_timestamp = datetime.now(timezone.utc)
    run_timestamp_utc = run_timestamp.isoformat()
    run_id = run_timestamp.strftime("common_esto_%Y%m%dT%H%M%S%fZ")

    source_paths = {
        "LEAP":  LEAP_ESTO_PATH,
        "NINTH": NINTH_ESTO_PATH,
        "ESTO":  ESTO_ROWS_PATH,
    }
    run_apply_common_esto_structure(
        source_paths=source_paths,
        common_rows_path=COMMON_ROWS_PATH,
        output_dir=COMMON_ESTO_DIR,
        default_economy="20USA",
        broad_common_row_component_limit=50,
        active_component_abs_tolerance=0.0,
        raw_leap_results_path=RAW_LEAP_PATH,
        outlook_mappings_path=WORKBOOK_PATH,
        structural_partial_coverage_path=COMMON_ESTO_DIR / "qa_common_esto_structural_partial_coverage.csv",
        ninth_source_data_path=NINTH_CSV_PATH,
        ninth_projection_start_year=2023,
        run_id=run_id,
        run_timestamp_utc=run_timestamp_utc,
    )

    status_path = COMMON_ESTO_DIR / "common_esto_output_status.csv"
    stage3_status = pd.read_csv(status_path, dtype=object).fillna("")
    comparison_status = stage3_status[
        stage3_status["artifact_name"] == "common_esto_comparison_data"
    ]
    comparison_path = COMMON_ESTO_DIR / "common_esto_comparison_data.csv"
    skip_reason = ""
    expected_mtime_ns: int | None = None
    if comparison_status.empty:
        skip_reason = "Current Stage 3 manifest does not contain the comparison output."
    else:
        comparison_record = comparison_status.iloc[0]
        current_output_file = str(comparison_record["current_output_file"])
        if current_output_file != comparison_path.name:
            skip_reason = (
                "Stage 3 did not write the canonical comparison output for this run; "
                f"current output is {current_output_file}."
            )
        else:
            expected_mtime_ns = int(comparison_record["output_mtime_ns"])

    # Read the wide 9th CSV once and share it across the tree build and the
    # three recursive-sum validations below (each previously re-read the same
    # ~290MB file). Each consumer copies before mutating, so the shared frame
    # is never altered in place and outputs are unchanged.
    print("  Reading 9th wide CSV once for Stage 3 consumers …")
    ninth_wide = pd.read_csv(NINTH_CSV_PATH, dtype=object)

    common_tree = build_common_esto_tree(COMMON_ROWS_PATH)
    esto_tree = build_esto_tree(ESTO_CSV_PATH)
    ninth_tree = build_ninth_tree(NINTH_CSV_PATH, data_df=ninth_wide)
    leap_tree = build_leap_tree(WORKBOOK_PATH)
    validation_tree = pd.concat([esto_tree, ninth_tree, leap_tree, common_tree], ignore_index=True)
    tree_output_dir = REPO_ROOT / "results" / "tree_structure"
    tree_output_dir.mkdir(parents=True, exist_ok=True)

    print("  Running projection-only source hierarchy validation ...")
    ninth_validation = validate_ninth_recursive_sums(
        data_csv_path=NINTH_CSV_PATH,
        workbook_path=WORKBOOK_PATH,
        leap_var_base_year=LEAP_VAR_BASE_YEAR,
        data_df=ninth_wide,
    )
    ninth_sector_validation = validate_ninth_sector_recursive_sums(
        data_csv_path=NINTH_CSV_PATH,
        workbook_path=WORKBOOK_PATH,
        common_rows_path=COMMON_ROWS_PATH,
        leap_var_base_year=LEAP_VAR_BASE_YEAR,
        data_df=ninth_wide,
    )
    ninth_fuel_validation = validate_ninth_fuel_recursive_sums(
        data_csv_path=NINTH_CSV_PATH,
        workbook_path=WORKBOOK_PATH,
        common_rows_path=COMMON_ROWS_PATH,
        leap_var_base_year=LEAP_VAR_BASE_YEAR,
        data_df=ninth_wide,
    )
    leap_validation = validate_leap_recursive_sums(
        leap_data_paths=[RAW_LEAP_PATH],
        workbook_path=WORKBOOK_PATH,
        esto_data_path=ESTO_CSV_PATH,
        leap_var_base_year=LEAP_VAR_BASE_YEAR,
    )
    ninth_validation.to_csv(tree_output_dir / "ninth_validation.csv", index=False)
    ninth_sector_validation.to_csv(tree_output_dir / "ninth_sector_validation.csv", index=False)
    ninth_fuel_validation.to_csv(tree_output_dir / "ninth_fuel_validation.csv", index=False)
    leap_validation.to_csv(tree_output_dir / "leap_validation.csv", index=False)
    print(f"  Ninth sector validation findings: {len(ninth_sector_validation):,}")
    print(f"  Ninth fuel validation findings: {len(ninth_fuel_validation):,}")
    del ninth_wide
    gc.collect()
    source_inconsistencies = _build_source_inconsistency_lookup(
        ninth_validation,
        leap_validation,
        ninth_sector_validation,
        ninth_fuel_validation,
    )

    detail_df, validation_summary = run_common_esto_validation_workflow(
        tree_df=validation_tree,
        comparison_data_path=comparison_path,
        output_dir=tree_output_dir,
        run_id=run_id,
        run_timestamp_utc=run_timestamp_utc,
        expected_input_mtime_ns=expected_mtime_ns,
        skip_reason=skip_reason,
        source_inconsistencies=source_inconsistencies,
        leap_var_base_year=LEAP_VAR_BASE_YEAR,
    )

    anchor_detail_path = tree_output_dir / "source_parent_anchor_validation.csv"
    anchor_summary_path = tree_output_dir / "source_parent_anchor_validation_summary.csv"
    if skip_reason:
        anchor_detail = pd.DataFrame(columns=["run_id"] + ANCHOR_COLUMNS)
        anchor_summary = pd.DataFrame([{
            "run_id": run_id, "status": "skipped", "eligible": 0,
            "passed": 0, "failed": 0, "skipped": 0, "reason": skip_reason,
        }])
    else:
        raw_anchor_source, source_mapping = load_raw_source_anchor_inputs(
            esto_data_path=ESTO_CSV_PATH,
            ninth_data_path=NINTH_CSV_PATH,
            raw_leap_path=RAW_LEAP_PATH,
            workbook_path=WORKBOOK_PATH,
            leap_var_base_year=LEAP_VAR_BASE_YEAR,
        )
        common_rows = pd.read_csv(COMMON_ROWS_PATH, dtype=object)
        comparison_data = pd.read_csv(comparison_path, dtype=object)
        from codebase.mapping_tools.mapping_issue_exceptions import (
            load_unmodelled_source_codes,
        )
        unmodelled_source_codes = load_unmodelled_source_codes()
        anchor_t0 = time.perf_counter()
        anchor_detail = validate_source_parent_anchors(
            source_df=raw_anchor_source,
            source_tree_df=validation_tree,
            source_mapping_df=source_mapping,
            common_rows_df=common_rows,
            comparison_df=comparison_data,
            unmodelled_source_codes=unmodelled_source_codes,
        )
        print(
            f"  [timing] validate_source_parent_anchors: "
            f"{time.perf_counter() - anchor_t0:.1f}s ({len(anchor_detail):,} rows)"
        )
        anchor_detail.insert(0, "run_id", run_id)
        anchor_summary = summarise_source_parent_anchors(anchor_detail)
        anchor_summary.insert(0, "run_id", run_id)
    anchor_summary["run_timestamp_utc"] = run_timestamp_utc
    anchor_summary["input_path"] = str(comparison_path.resolve())
    anchor_summary["input_mtime_ns"] = expected_mtime_ns if expected_mtime_ns is not None else ""
    anchor_detail.to_csv(anchor_detail_path, index=False)
    anchor_summary.to_csv(anchor_summary_path, index=False)

    detail_path = REPO_ROOT / "results" / "tree_structure" / "common_esto_validation.csv"
    summary_path = REPO_ROOT / "results" / "tree_structure" / "common_esto_validation_summary.csv"
    validation_status = validation_summary.copy()
    validation_status["record_type"] = "validation"
    validation_status["artifact_name"] = validation_status["validation_name"]
    validation_status["current_output_file"] = detail_path.name
    validation_status["output_mtime_ns"] = detail_path.stat().st_mtime_ns
    validation_status["validation_summary_path"] = str(summary_path.resolve())
    anchor_status = anchor_summary.copy()
    anchor_status["record_type"] = "validation"
    anchor_status["artifact_name"] = "source_parent_anchor_validation"
    anchor_status["current_output_file"] = anchor_detail_path.name
    anchor_status["output_mtime_ns"] = anchor_detail_path.stat().st_mtime_ns
    anchor_status["validation_summary_path"] = str(anchor_summary_path.resolve())
    combined_status = pd.concat(
        [stage3_status, validation_status, anchor_status], ignore_index=True, sort=False
    )
    combined_status.to_csv(status_path, index=False)

    print(f"  Validation detail rows: {len(detail_df):,}")
    print("  Original-source parent anchors:")
    if anchor_summary.empty:
        print("    eligible 0, passed 0, failed 0, skipped 0")
    else:
        for _, row in anchor_summary.iterrows():
            print(
                f"    {row.get('validation_axis', 'all')} / {row.get('source_system', 'ALL')}: "
                f"eligible {int(row.get('eligible', 0)):,}, passed {int(row.get('passed', 0)):,}, "
                f"failed {int(row.get('failed', 0)):,}, skipped {int(row.get('skipped', 0)):,}"
            )
    print("  Internal Common ESTO parent/child consistency:")
    for _, row in validation_summary.iterrows():
        print(
            f"  {row['validation_axis']} / {row['source_system']}: {row['status']} "
            f"({int(row['checks_performed']):,} checks, "
            f"{int(row['eligible_parent_count']):,} eligible parents, "
            f"{int(row['mismatch_count']):,} mismatches)"
        )
    print(f"  [timing] STAGE 3 total: {time.perf_counter() - stage3_t0:.1f}s")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_ALL_STAGES = ["0", "1", "2", "leap_parse", "data_convert", "3"]

_STAGE_RUNNERS = {
    "0":            run_stage_0,
    "1":            run_stage_1,
    "2":            run_stage_2,
    "leap_parse":   run_leap_parse,
    "data_convert": run_data_convert,
    "3":            run_stage_3,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LEAP->ESTO mapping pipeline.")
    parser.add_argument(
        "--stages",
        default=",".join(_ALL_STAGES),
        help="Comma-separated list of stages to run (default: all).",
    )
    parser.add_argument(
        "--skip",
        default="",
        help="Comma-separated list of stages to skip.",
    )
    parser.add_argument(
        "--apply-maintenance",
        action="store_true",
        help=(
            "Allow Stage 0 to write computed subtotal values to the mapping workbook. "
            "Reviewed subtotal_label_overrides are applied last. Without this flag, "
            "Stage 0 writes preview and stale-override QA files only."
        ),
    )
    args = parser.parse_args()

    requested = [s.strip() for s in args.stages.split(",") if s.strip()]
    skipped   = {s.strip() for s in args.skip.split(",") if s.strip()}

    stages_to_run = [s for s in requested if s not in skipped]

    unknown = [s for s in stages_to_run if s not in _STAGE_RUNNERS]
    if unknown:
        print(f"Unknown stage(s): {unknown}")
        print(f"Valid stages: {_ALL_STAGES}")
        sys.exit(1)

    with _log_to_file(_PIPELINE_LOG_PATH) as log_path:
        print(f"[LOG] Writing output to: {log_path}")
        print("Running pipeline stages:", stages_to_run)
        for stage in stages_to_run:
            if stage == "0":
                run_stage_0(apply_subtotal_changes=args.apply_maintenance)
            else:
                _STAGE_RUNNERS[stage]()

        print("\n" + "=" * 60)
        print("Pipeline complete.")
        print("=" * 60)
        _chime()


def _chime() -> None:
    try:
        import time
        import winsound  # type: ignore
        for freq, dur in [(659, 90), (784, 90), (988, 140)]:
            winsound.Beep(freq, dur)
            time.sleep(0.04)
    except Exception:
        pass


if __name__ == "__main__":
    main()
