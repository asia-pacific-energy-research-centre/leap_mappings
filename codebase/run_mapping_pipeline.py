"""
run_mapping_pipeline.py

End-to-end mapping pipeline for LEAP -> ESTO / 9th Outlook comparison.

Core stages
-----------
1  Relationships — build energy_balance_relationships.csv from outlook_mappings_master.xlsx
2  Common ESTO structure — build common comparison rows via graph partitioning
   LEAP parse   — parse raw LEAP balance xlsx exports to long-format CSV
   Data convert — convert LEAP and 9th data to ESTO-style rows
   ESTO rows    — prepare non-subtotal ESTO rows as long-format CSV
3  Apply structure — map all sources to common comparison rows and aggregate

Optional maintenance is deliberately outside this pipeline:
- codebase/missing_mapped_esto_rows_workflow.py prepares review-only ESTO rows.
- codebase/hierarchy_subtotal_contract_workflow.py builds the structural
  hierarchy/subtotal contract and workbook review tables.

Run all stages:
    python codebase/run_mapping_pipeline.py

Run specific stages (comma-separated):
    python codebase/run_mapping_pipeline.py --stages 1,2,3

Run only Stage 1:
    python codebase/run_mapping_pipeline.py --stages 1
"""

from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import json
import os
import sys
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

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

from codebase.utilities.leap_balance_export_resolver import (  # noqa: E402
    discover_available_economies,
    discover_balance_export_workbooks,
    format_balance_export_discovery_report,
    resolve_balance_exports_root,
)
from codebase.mapping_tools.typed_output import (  # noqa: E402
    read_manifested_parquet,
    write_manifested_parquet,
)

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

WORKBOOK_PATH       = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
ESTO_CSV_PATH       = REPO_ROOT / "data" / "00APEC_2024_low_with_subtotals.csv"
ESTO_EXTENDED_CSV_PATH = REPO_ROOT / "data" / "esto_extended.csv"
NINTH_CSV_PATH      = REPO_ROOT / "data" / "merged_file_energy_ALL_20251106.csv"
SOURCE_BRANCH_FALLBACK_RULES_PATH = REPO_ROOT / "config" / "source_branch_fallback_rules.csv"
ALL_DEMAND_COMPONENTS_PATH        = REPO_ROOT / "config" / "all_demand_aggregated_components.json"

REL_DIR             = REPO_ROOT / "results" / "mapping_relationships"
COMMON_ESTO_DIR     = REPO_ROOT / "results" / "common_esto"
STAGE3_RUN_MANIFEST_PATH = COMMON_ESTO_DIR / "stage3_run_manifest.json"
MAPPING_GENERATION_MANIFEST_PATH = (
    REPO_ROOT / "config" / "outlook_mappings_generation_manifest.json"
)
DATASET_REGISTRY_ROOT = REPO_ROOT / "config" / "datasets"
REGISTRY_PROVENANCE_FILES = {
    "dataset_registry": "dataset_registry.csv",
    "value_adapter_registry": "value_adapter_registry.csv",
    "mapping_sheet_registry": "mapping_sheet_registry.csv",
    "rollup_sheet_registry": "rollup_sheet_registry.csv",
    "diagnostic_adapter_registry": "diagnostic_adapter_registry.csv",
    "comparison_scope_registry": "comparison_scopes.csv",
}

RAW_LEAP_PATH       = REL_DIR / "raw_leap_results.csv"
LEAP_ESTO_PATH      = REL_DIR / "leap_results_converted_to_esto.csv"
LEAP_ROLLUP_AUDIT_PATH = REL_DIR / "leap_source_rollup_audit.csv"
LEAP_SOURCE_LINEAGE_PATH = REL_DIR / "leap_source_to_esto_component_lineage.csv.gz"
NINTH_ESTO_PATH     = REL_DIR / "ninth_results_converted_to_esto.csv.gz"
NINTH_SOURCE_LINEAGE_PATH = REL_DIR / "ninth_source_to_esto_component_lineage.csv.gz"
ESTO_ROWS_PATH      = REL_DIR / "esto_results_exact_rows.csv.gz"
ESTO_EXTENDED_ROWS_PATH = REL_DIR / "esto_extended_results_exact_rows.csv.gz"
ESTO_EXTENDED_DELTA_PATH = REL_DIR / "esto_extended_results_exact_rows.delta.csv.gz"
ESTO_EXTENDED_DELTA_MANIFEST_PATH = (
    REL_DIR / "esto_extended_results_exact_rows.delta.json"
)
RELATIONSHIPS_PATH  = REL_DIR / "energy_balance_relationships.csv"
COMMON_ROWS_PATH    = COMMON_ESTO_DIR / "common_esto_rows.csv"
ESTO_COMPONENT_LINEAGE_PATH = COMMON_ESTO_DIR / "esto_component_to_common_row_lineage.csv.gz"
ESTO_EXACT_ROWS_SOURCE_IDENTITY_QA_PATH = (
    REL_DIR / "qa_esto_exact_rows_source_identity.csv"
)

# Aggregate comparisons that require the exact ESTO parent alongside the
# ordinary non-subtotal frontier. Other dashboard totals are currently built
# from their reviewed additive frontiers.
ESTO_REFERENCE_ROLLUP_LABELS = {"Total transformation - no transfers"}

# Some ESTO parent flows contain the published observations even though they
# are structurally marked as subtotals. In particular, 08 Transfers can be
# non-zero while its 08.01-08.99 detail rows are zero or incomplete, so the
# parent must survive the ordinary leaf-only extraction for Common ESTO.
ESTO_RETAINED_SUBTOTAL_FLOW_LABELS = {"08 Transfers"}

# Raw LEAP workbooks are owned by the sibling leap_initialisation repository.
LEAP_EXPORTS_ROOT = resolve_balance_exports_root(require_exists=False)
if not LEAP_EXPORTS_ROOT.is_dir():
    # A Git worktree lives under github/worktrees/<name>, while the canonical
    # initialisation repository remains under github/leap_initialisation.
    worktree_sibling = (
        REPO_ROOT.parent.parent
        / "leap_initialisation"
        / "data"
        / "leap balances exports"
    )
    if worktree_sibling.is_dir():
        LEAP_EXPORTS_ROOT = worktree_sibling

# ---------------------------------------------------------------------------
# Output logging
# ---------------------------------------------------------------------------
_PIPELINE_LOG_PATH = REPO_ROOT / "results" / "logs" / "mapping_pipeline.log"
_RESOURCE_USAGE_PATH = REPO_ROOT / "results" / "logs" / "mapping_pipeline_resource_usage.json"


class _ResourceUsageMonitor:
    """Sample this process's RSS without adding a hard runtime dependency."""

    def __init__(self, output_path: Path, interval_seconds: float = 5.0):
        self.output_path = output_path
        self.interval_seconds = interval_seconds
        self.stage = "startup"
        self.samples: list[dict[str, object]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        try:
            import psutil
        except ImportError:
            psutil = None
        self._process = psutil.Process(os.getpid()) if psutil else None

    def set_stage(self, stage: str) -> None:
        self.stage = stage

    def _sample(self) -> None:
        if self._process is None:
            return
        memory = self._process.memory_info()
        self.samples.append(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "stage": self.stage,
                "rss_bytes": int(memory.rss),
            }
        )

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self._sample()

    def __enter__(self):
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        if self._process is not None:
            self._sample()
            self._thread = threading.Thread(
                target=self._run,
                name="mapping-pipeline-resource-monitor",
                daemon=True,
            )
            self._thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_seconds + 1)
        self._sample()
        values = [int(item["rss_bytes"]) for item in self.samples]
        summary: dict[str, object] = {
            "status": "recorded" if self._process is not None else "psutil_unavailable",
            "sampling_interval_seconds": self.interval_seconds,
            "sample_count": len(values),
            "average_rss_bytes": round(sum(values) / len(values)) if values else None,
            "peak_rss_bytes": max(values) if values else None,
            "minimum_rss_bytes": min(values) if values else None,
            "samples": self.samples,
        }
        self.output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        if values:
            print(
                "[resource] RSS average: "
                f"{summary['average_rss_bytes'] / 1024**3:.2f} GB; "
                f"peak: {summary['peak_rss_bytes'] / 1024**3:.2f} GB; "
                f"samples: {len(values)}"
            )
        else:
            print("[resource] RSS sampling unavailable; install psutil to enable it.")


def _sha256(path: Path) -> str:
    """Return a stable SHA-256 digest for provenance checks."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_active_mapping_generation_manifest() -> dict[str, object] | None:
    """Load the generation manifest only when it matches the active workbook."""
    if not MAPPING_GENERATION_MANIFEST_PATH.exists():
        return None
    manifest = json.loads(
        MAPPING_GENERATION_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    promoted_hash = (
        manifest.get("hashes", {}).get("promoted_master_sha256")
        if isinstance(manifest.get("hashes"), dict)
        else None
    )
    if promoted_hash != _sha256(WORKBOOK_PATH):
        raise ValueError(
            "The mapping generation manifest does not match the active "
            "outlook_mappings_master.xlsx. Refresh the separate-axis contract "
            "or deliberately restore both workbook and manifest together."
        )
    return manifest


def build_registry_provenance() -> dict[str, object]:
    """Return hashes plus the active dataset/scope policy contract."""
    files: dict[str, object] = {}
    for registry_name, filename in REGISTRY_PROVENANCE_FILES.items():
        path = DATASET_REGISTRY_ROOT / filename
        frame = pd.read_csv(path, dtype=str).fillna("")
        files[registry_name] = {
            "path": str(path.resolve()),
            "sha256": _sha256(path),
            "row_count": int(len(frame)),
        }

    datasets = pd.read_csv(
        DATASET_REGISTRY_ROOT / "dataset_registry.csv",
        dtype=str,
    ).fillna("")
    enabled = datasets["enabled"].str.casefold().eq("true")
    dataset_policies = (
        datasets.loc[
            enabled,
            [
                "dataset_id",
                "source_version",
                "value_adapter",
                "hierarchy_adapter",
                "scenario_policy_id",
                "period_policy_id",
                "native_unit",
            ],
        ]
        .set_index("dataset_id")
        .to_dict(orient="index")
    )

    scopes = pd.read_csv(
        DATASET_REGISTRY_ROOT / "comparison_scopes.csv",
        dtype=str,
    ).fillna("")
    default_scopes = scopes[
        scopes["enabled"].str.casefold().eq("true")
        & scopes["default_enabled"].str.casefold().eq("true")
    ]
    scope_policies = (
        default_scopes[
            [
                "comparison_scope",
                "included_dataset_ids",
                "scenario_alignment_policy",
                "period_alignment_policy",
            ]
        ]
        .set_index("comparison_scope")
        .to_dict(orient="index")
    )
    return {
        "files": files,
        "enabled_dataset_policies": dataset_policies,
        "default_scope_policies": scope_policies,
    }


def _write_stage3_run_manifest(manifest: dict[str, object]) -> None:
    """Write a compact machine-readable Stage 3 run/timing summary."""
    STAGE3_RUN_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    STAGE3_RUN_MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )


def _stage3_completion_status(validation_summary: pd.DataFrame) -> str:
    """Do not report a Stage 3 run as cleanly completed after validator errors."""
    if (
        not validation_summary.empty
        and "status" in validation_summary.columns
        and validation_summary["status"].astype(str).str.casefold().eq("error").any()
    ):
        return "completed_with_validation_errors"
    return "completed"


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
# Stage 1 — Build relationships
# ---------------------------------------------------------------------------

def run_separate_axis_refresh() -> None:
    """Regenerate and promote the validated compatibility mapping workbook."""
    print("\n" + "=" * 60)
    print("GENERATE  Refresh separate-axis mapping contract")
    print("=" * 60)
    from codebase.separate_axis_mapping_refresh_workflow import (
        run_separate_axis_mapping_refresh,
    )

    run_separate_axis_mapping_refresh(promote_master=True)


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
        mapping_workbook_path=WORKBOOK_PATH,
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

def run_stage_2(
    enabled_scopes: list[str] | None = None,
    allow_direct_subtotal_edges: bool | None = None,
) -> None:
    print("\n" + "=" * 60)
    print("STAGE 2  Build common ESTO structure")
    print("=" * 60)
    from codebase.mapping_tools.build_common_esto_structure import (
        COMMON_ESTO_LABEL_OVERRIDES_PATH,
        COMMON_ESTO_OVERRIDES_PATH,
        COVERAGE_EXCLUSIONS_PATH,
        DEFAULT_ENABLED_COMPARISON_SCOPES,
        OUTPUT_DIR,
        OUTLOOK_MAPPINGS_PATH,
        RELATIONSHIPS_PATH as STAGE_2_RELATIONSHIPS_PATH,
        run_common_esto_structure_workflow,
    )
    generation_manifest = load_active_mapping_generation_manifest()
    direct_subtotal_edges = (
        generation_manifest is not None
        if allow_direct_subtotal_edges is None
        else bool(allow_direct_subtotal_edges)
    )
    run_common_esto_structure_workflow(
        relationships_path=STAGE_2_RELATIONSHIPS_PATH,
        coverage_exclusions_path=COVERAGE_EXCLUSIONS_PATH,
        common_esto_overrides_path=COMMON_ESTO_OVERRIDES_PATH,
        common_esto_label_overrides_path=COMMON_ESTO_LABEL_OVERRIDES_PATH,
        outlook_mappings_path=WORKBOOK_PATH,
        output_dir=OUTPUT_DIR,
        enabled_scopes=(
            DEFAULT_ENABLED_COMPARISON_SCOPES
            if enabled_scopes is None
            else enabled_scopes
        ),
        allow_direct_subtotal_edges=direct_subtotal_edges,
    )
    from codebase.mapping_tools.compile_structural_mapping_artifacts import (
        compile_structural_mapping_artifacts,
    )

    compile_structural_mapping_artifacts()
    from codebase.mapping_tools.build_source_to_common_esto_map import (
        build_and_write_source_to_common_esto_map,
    )

    build_and_write_source_to_common_esto_map()


# ---------------------------------------------------------------------------
# LEAP parse — produce raw_leap_results.csv
# ---------------------------------------------------------------------------

def run_leap_parse(economies: Sequence[str] | None = None) -> None:
    """Parse raw LEAP balance exports for one or more economies into RAW_LEAP_PATH.

    ``economies`` may be an explicit list (e.g. from ``--leap-economies``). When
    omitted (``None``), every economy with a recognized export directory under
    the canonical exports root is auto-discovered and parsed -- no economy list
    is hardcoded. Each requested economy is parsed independently; an economy
    with no export directory present logs a warning and is skipped rather than
    failing the whole run. All successfully parsed economies are combined into
    one DataFrame and written once to RAW_LEAP_PATH.
    """
    print("\n" + "=" * 60)
    print("LEAP PARSE  Parse LEAP balance exports")
    print("=" * 60)

    if economies is None:
        requested_economies = discover_available_economies(LEAP_EXPORTS_ROOT)
    else:
        requested_economies = [str(economy).strip() for economy in economies if str(economy).strip()]

    print(
        format_balance_export_discovery_report(
            discover_balance_export_workbooks(
                economies=requested_economies,
                exports_root=LEAP_EXPORTS_ROOT,
            )
        )
    )

    if not requested_economies:
        print("  WARNING: no LEAP economies requested or discovered; nothing to parse.")
        return

    from codebase.mapping_tools.parse_leap_balance_export import parse_leap_balance_dir

    frames: list[pd.DataFrame] = []
    parsed_economies: list[str] = []
    with tempfile.TemporaryDirectory(prefix="leap_parse_") as tmp_dir:
        for economy in requested_economies:
            export_dir = LEAP_EXPORTS_ROOT / economy
            if not export_dir.exists():
                print(f"  WARNING: no {economy} raw LEAP exports found at {export_dir}")
                continue
            # parse_leap_balance_dir writes its own CSV as a side effect; give
            # it a scratch path per economy and use the returned DataFrame so
            # the shared RAW_LEAP_PATH is only written once, combined below.
            scratch_output = Path(tmp_dir) / f"{economy}_raw_leap.csv"
            try:
                df = parse_leap_balance_dir(export_dir, scratch_output, economy_code=economy)
            except FileNotFoundError as exc:
                print(f"  WARNING: {economy} export directory has no .xlsx files ({exc})")
                continue
            frames.append(df)
            parsed_economies.append(economy)

    if not frames:
        print("  WARNING: no economies parsed; RAW_LEAP_PATH not written.")
        return

    combined = pd.concat(frames, ignore_index=True)
    RAW_LEAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(RAW_LEAP_PATH, index=False)
    try:
        display_path = RAW_LEAP_PATH.relative_to(REPO_ROOT)
    except ValueError:
        display_path = RAW_LEAP_PATH
    print(
        f"  Combined LEAP long-format across {len(parsed_economies)} economy(ies) "
        f"({', '.join(parsed_economies)}): {len(combined):,} rows -> {display_path}"
    )


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
        target_values_path=ESTO_ROWS_PATH,
        lineage_output_path=LEAP_SOURCE_LINEAGE_PATH,
        source_branch_fallback_rules_path=SOURCE_BRANCH_FALLBACK_RULES_PATH,
        all_demand_components_path=ALL_DEMAND_COMPONENTS_PATH,
        preflight_audit_dir=REL_DIR,
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
        load_non_expanding_ninth_rollup_rules,
        iter_ninth_results_to_esto_by_economy,
        relationships_need_target_dataset_share,
        GROUP_COLUMNS,
        SOURCE_LINEAGE_COLUMNS,
    )
    from codebase.mapping_tools.target_share_allocation import (
        target_dataset_share_target_flows,
        load_target_dataset_share_basis_rows,
    )
    # Load the mapping first so the wide 9th frame can be filtered to only
    # sector/fuel pairs with an included ESTO mapping *before* the year melt.
    relationships_df = load_ninth_to_esto_relationships(RELATIONSHIPS_PATH)
    ninth_rollup_rules_df = load_non_expanding_ninth_rollup_rules(WORKBOOK_PATH)
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

    target_values_df = None
    if relationships_need_target_dataset_share(relationships_df):
        target_values_df = pd.read_csv(ESTO_ROWS_PATH, dtype=object)
        needed_flows = target_dataset_share_target_flows(relationships_df)
        subtotal_basis_df = load_target_dataset_share_basis_rows(ESTO_CSV_PATH, needed_flows)
        if not subtotal_basis_df.empty:
            # esto_results_exact_rows.csv deliberately drops is_subtotal rows
            # (see run_esto_exact_rows); a source relationship can target an
            # aggregate ESTO flow only resolvable at that subtotal level, so
            # the allocation basis is fetched back in here, scoped to exactly
            # the flows that need it -- see target_share_allocation.py.
            target_values_df = pd.concat(
                [target_values_df, subtotal_basis_df], ignore_index=True
            )
            print(
                f"  Target-dataset-share basis: added {len(subtotal_basis_df):,} "
                f"ESTO subtotal rows for {len(needed_flows):,} aggregate flow(s)"
            )
    NINTH_ESTO_PATH.parent.mkdir(parents=True, exist_ok=True)
    NINTH_SOURCE_LINEAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    converted_temp_path = NINTH_ESTO_PATH.with_name(
        f"{NINTH_ESTO_PATH.name}.tmp"
    )
    lineage_temp_path = NINTH_SOURCE_LINEAGE_PATH.with_name(
        f"{NINTH_SOURCE_LINEAGE_PATH.name}.tmp"
    )
    converted_row_count = 0
    lineage_row_count = 0
    chunk_count = 0
    try:
        with (
            gzip.open(
                converted_temp_path,
                mode="wt",
                encoding="utf-8",
                newline="",
            ) as converted_handle,
            gzip.open(
                lineage_temp_path,
                mode="wt",
                encoding="utf-8",
                newline="",
            ) as lineage_handle,
        ):
            for economy, converted_df, lineage_df in (
                iter_ninth_results_to_esto_by_economy(
                    ninth_long,
                    relationships_df,
                    target_values_df=target_values_df,
                    rollup_rules_df=ninth_rollup_rules_df,
                )
            ):
                converted_df.to_csv(
                    converted_handle,
                    index=False,
                    header=chunk_count == 0,
                )
                lineage_df.to_csv(
                    lineage_handle,
                    index=False,
                    header=chunk_count == 0,
                )
                converted_row_count += len(converted_df)
                lineage_row_count += len(lineage_df)
                chunk_count += 1
                print(
                    f"  Converted Ninth economy chunk {economy}: "
                    f"{len(converted_df):,} rows, "
                    f"{len(lineage_df):,} lineage rows"
                )
                del converted_df, lineage_df
                gc.collect()

            if chunk_count == 0:
                pd.DataFrame(columns=GROUP_COLUMNS).to_csv(
                    converted_handle,
                    index=False,
                )
                pd.DataFrame(columns=SOURCE_LINEAGE_COLUMNS).to_csv(
                    lineage_handle,
                    index=False,
                )
        converted_temp_path.replace(NINTH_ESTO_PATH)
        lineage_temp_path.replace(NINTH_SOURCE_LINEAGE_PATH)
    except Exception:
        converted_temp_path.unlink(missing_ok=True)
        lineage_temp_path.unlink(missing_ok=True)
        raise
    print(f"  Conversion relationships used: {len(relationships_df):,}")
    print(f"  Economy chunks written: {chunk_count:,}")
    print(f"  Converted ESTO rows written: {converted_row_count:,}")
    print(f"  Source-to-ESTO lineage rows written: {lineage_row_count:,}")
    print(f"  Wrote: {NINTH_ESTO_PATH.relative_to(REPO_ROOT)}")
    print(f"  Wrote lineage: {NINTH_SOURCE_LINEAGE_PATH.relative_to(REPO_ROOT)}")








def run_esto_exact_rows() -> None:
    run_esto_exact_rows_for_path(ESTO_CSV_PATH, ESTO_ROWS_PATH, "ESTO")



# Moved to mapping_tools/esto_exact_rows.py so the portable worker can re-extract
# ESTO rows without importing this runner (which drags in the Stage 1/2 builders,
# the separate-axis workflows and Pillow). Re-exported so callers are unaffected.
from codebase.mapping_tools.esto_exact_rows import (  # noqa: E402
    configured_rollup_reference_pairs,
    select_esto_comparison_rows,
)
from codebase.mapping_tools.esto_exact_rows import (  # noqa: E402
    run_esto_exact_rows_for_path as _run_esto_exact_rows_for_path,
)


def run_esto_exact_rows_for_path(data_path, output_path, source_system):
    """Pipeline-flavoured wrapper: supply this runner's configured paths."""
    return _run_esto_exact_rows_for_path(
        data_path,
        output_path,
        source_system,
        relationships_path=RELATIONSHIPS_PATH,
        mapping_workbook_path=WORKBOOK_PATH,
        qa_path=ESTO_EXACT_ROWS_SOURCE_IDENTITY_QA_PATH,
        repo_root=REPO_ROOT,
    )

def run_esto_extended_exact_rows() -> None:
    run_esto_exact_rows_for_path(
        ESTO_EXTENDED_CSV_PATH,
        ESTO_EXTENDED_ROWS_PATH,
        "ESTO_EXTENDED",
    )


def run_esto_extended_delta_contract() -> dict[str, object]:
    """Publish the optional verified base-plus-delta representation."""
    from codebase.mapping_tools.esto_extended_delta import (
        write_esto_extended_delta_contract,
    )

    print("\n" + "-" * 40)
    print("  ESTO Extended exact-row delta contract")
    manifest = write_esto_extended_delta_contract(
        esto_base_path=ESTO_ROWS_PATH,
        esto_extended_path=ESTO_EXTENDED_ROWS_PATH,
        delta_path=ESTO_EXTENDED_DELTA_PATH,
        manifest_path=ESTO_EXTENDED_DELTA_MANIFEST_PATH,
    )
    print(
        "  Verified delta: "
        f"{int(manifest['delta']['row_count']):,} rows, "
        f"{int(manifest['delta']['size_bytes']):,} bytes"
    )
    return manifest


def run_data_convert(write_esto_extended_delta: bool = False) -> None:
    print("\n" + "=" * 60)
    print("DATA CONVERT  LEAP, 9th, ESTO -> common input format")
    print("=" * 60)
    from codebase.mapping_tools.value_adapter_registry import (
        run_registered_value_adapters,
    )
    run_registered_value_adapters({
        "esto_exact_rows": run_esto_exact_rows,
        "esto_extended_exact_rows": run_esto_extended_exact_rows,
        "leap_to_esto": run_leap_to_esto,
        "ninth_to_esto": run_ninth_to_esto,
    })
    if write_esto_extended_delta:
        run_esto_extended_delta_contract()


# ---------------------------------------------------------------------------
# Stage 3 — Apply common ESTO structure
# ---------------------------------------------------------------------------

def run_stage_3(
    skip_deep_validation: bool = False,
    use_esto_extended_delta: bool = False,
    chunk_value_application: bool = True,
    stage3_source_paths: dict[str, Path] | None = None,
) -> None:
    import time
    from codebase.mapping_tools.value_adapter_registry import (
        get_component_relevance_reference_paths,
        get_registered_stage3_source_paths,
    )

    stage3_t0 = time.perf_counter()
    print("\n" + "=" * 60)
    print("STAGE 3  Apply common ESTO structure to source data")
    print("=" * 60)

    source_paths = (
        get_registered_stage3_source_paths(REPO_ROOT)
        if stage3_source_paths is None
        else {
            source_system: Path(source_path)
            for source_system, source_path in stage3_source_paths.items()
        }
    )
    # ESTO Extended changes only the structural category basis. Historical
    # values always come from the ordinary ESTO exact-row artifact.
    source_paths["ESTO_EXTENDED"] = source_paths["ESTO"]
    esto_extended_storage = {
        "mode": "ordinary_esto_history",
        "base_path": str(source_paths["ESTO"].resolve()),
        "deprecated_delta_requested": bool(use_esto_extended_delta),
    }
    relevance_reference_paths = get_component_relevance_reference_paths(REPO_ROOT)
    stage3_input_paths = [*source_paths.values(), COMMON_ROWS_PATH]
    missing = [path for path in stage3_input_paths if not path.exists()]
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
        build_common_esto_hierarchy_edges,
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
    from codebase.mapping_tools.apec_anchor_validation import (
        validate_source_parent_anchors_apec_first,
    )
    from codebase.mapping_tools.source_parent_anchor_validation import (
        ANCHOR_COLUMNS,
        ANCHOR_CHILD_CONTEXT_COLUMNS,
        ANCHOR_CHILD_VALUE_COLUMNS,
        ANCHOR_MAPPED_COMPONENT_CONTEXT_COLUMNS,
        LEAF_RECONCILIATION_CANDIDATE_COLUMNS,
        build_leaf_reconciliation_exception_candidates,
        build_failed_anchor_mapped_component_context_values,
        build_failed_anchor_raw_child_context_values,
        load_raw_source_anchor_inputs,
        select_source_parent_anchor_findings,
        summarise_failed_anchor_raw_child_context_values,
        summarise_source_parent_anchors,
    )

    run_timestamp = datetime.now(timezone.utc)
    run_timestamp_utc = run_timestamp.isoformat()
    run_id = run_timestamp.strftime("common_esto_%Y%m%dT%H%M%S%fZ")

    comparison_scopes = sorted(
        pd.read_csv(COMMON_ROWS_PATH, usecols=["comparison_scope"], dtype=object)
        ["comparison_scope"].dropna().astype(str).unique().tolist()
    )
    generation_manifest = load_active_mapping_generation_manifest()
    run_manifest: dict[str, object] = {
        "run_id": run_id,
        "run_timestamp_utc": run_timestamp_utc,
        "status": "running",
        "comparison_scopes": comparison_scopes,
        "esto_extended_storage": esto_extended_storage,
        "datasets": {
            name: {
                "path": str(path.resolve()),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else None,
            }
            for name, path in source_paths.items()
        },
        "relevance_reference_files": {
            source_system: [str(path.resolve()) for path in paths]
            for source_system, paths in relevance_reference_paths.items()
        },
        "mapping_workbook": str(WORKBOOK_PATH.resolve()),
        "mapping_workbook_sha256": _sha256(WORKBOOK_PATH),
        "mapping_generation": generation_manifest,
        "registry_provenance": build_registry_provenance(),
        "chunk_value_application": chunk_value_application,
        "timings_seconds": {},
        "validation": {},
    }
    _write_stage3_run_manifest(run_manifest)
    apply_t0 = time.perf_counter()
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
        esto_component_lineage_output_path=ESTO_COMPONENT_LINEAGE_PATH,
        chunk_by_source_economy=chunk_value_application,
        run_id=run_id,
        run_timestamp_utc=run_timestamp_utc,
        relevance_reference_paths=relevance_reference_paths,
        source_system_overrides={"ESTO_EXTENDED": "ESTO_EXTENDED"},
    )
    run_manifest["timings_seconds"]["apply_common_esto_structure"] = round(
        time.perf_counter() - apply_t0, 3
    )

    if skip_deep_validation:
        from codebase.mapping_tools.build_dataset_tree_structure import (
            build_common_esto_hierarchy_edges,
            build_common_esto_tree,
        )
        tree_output_dir = REPO_ROOT / "results" / "tree_structure"
        tree_output_dir.mkdir(parents=True, exist_ok=True)
        common_tree = build_common_esto_tree(COMMON_ROWS_PATH, WORKBOOK_PATH)
        hierarchy_edges_path = tree_output_dir / "common_esto_hierarchy_edges.csv"
        build_common_esto_hierarchy_edges(common_tree, WORKBOOK_PATH).to_csv(
            hierarchy_edges_path, index=False
        )
        run_manifest["hierarchy_edges_path"] = str(hierarchy_edges_path.resolve())
        run_manifest["status"] = "completed_skip_deep_validation"
        run_manifest["timings_seconds"]["stage3_total"] = round(
            time.perf_counter() - stage3_t0, 3
        )
        _write_stage3_run_manifest(run_manifest)
        print("  Deep recursive-tree and source-anchor validations skipped by explicit test-mode flag.")
        print(f"  Common ESTO comparison output written to: {COMMON_ESTO_DIR}")
        return

    status_path = COMMON_ESTO_DIR / "common_esto_output_status.csv"
    stage3_status = pd.read_csv(status_path, dtype=object).fillna("")
    comparison_status = stage3_status[
        stage3_status["artifact_name"] == "common_esto_comparison_data"
    ]
    comparison_path = COMMON_ESTO_DIR / "common_esto_comparison_data.parquet"
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

    common_tree = build_common_esto_tree(COMMON_ROWS_PATH, WORKBOOK_PATH)
    common_hierarchy_edges = build_common_esto_hierarchy_edges(
        common_tree, WORKBOOK_PATH
    )
    esto_tree = build_esto_tree(ESTO_CSV_PATH, dataset_id="esto")
    esto_extended_tree = build_esto_tree(
        ESTO_EXTENDED_CSV_PATH,
        dataset_id="esto_extended",
    )
    ninth_tree = build_ninth_tree(NINTH_CSV_PATH, data_df=ninth_wide)
    leap_tree = build_leap_tree(WORKBOOK_PATH)
    validation_tree = pd.concat(
        [esto_tree, esto_extended_tree, ninth_tree, leap_tree, common_tree],
        ignore_index=True,
    )
    tree_output_dir = REPO_ROOT / "results" / "tree_structure"
    tree_output_dir.mkdir(parents=True, exist_ok=True)
    esto_tree.to_csv(tree_output_dir / "esto_tree.csv", index=False)
    esto_extended_tree.to_csv(tree_output_dir / "esto_extended_tree.csv", index=False)
    ninth_tree.to_csv(tree_output_dir / "ninth_tree.csv", index=False)
    leap_tree.to_csv(tree_output_dir / "leap_tree.csv", index=False)
    common_tree.to_csv(tree_output_dir / "common_esto_tree.csv", index=False)
    common_hierarchy_edges.to_csv(
        tree_output_dir / "common_esto_hierarchy_edges.csv", index=False
    )
    run_manifest["hierarchy_edges_path"] = str(
        (tree_output_dir / "common_esto_hierarchy_edges.csv").resolve()
    )
    validation_tree.to_csv(tree_output_dir / "all_dataset_trees.csv", index=False)

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

    common_validation_t0 = time.perf_counter()
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
        workbook_path=WORKBOOK_PATH,
    )
    run_manifest["timings_seconds"]["common_esto_validation"] = round(
        time.perf_counter() - common_validation_t0, 3
    )
    validation_detail_row_count = len(detail_df)

    anchor_detail_path = tree_output_dir / "source_parent_anchor_validation.parquet"
    anchor_full_detail_path = tree_output_dir / "source_parent_anchor_validation_full.parquet"
    anchor_summary_path = tree_output_dir / "source_parent_anchor_validation_summary.parquet"
    anchor_child_values_path = tree_output_dir / "source_parent_anchor_child_values.parquet"
    anchor_child_context_values_path = tree_output_dir / "source_parent_anchor_child_context_values.parquet"
    anchor_mapped_component_context_values_path = tree_output_dir / "source_parent_anchor_mapped_component_context_values.parquet"
    anchor_economy_examples_path = tree_output_dir / "source_parent_anchor_economy_examples.parquet"
    anchor_economy_child_context_values_path = tree_output_dir / "source_parent_anchor_economy_child_context_values.parquet"
    anchor_economy_mapped_component_context_values_path = tree_output_dir / "source_parent_anchor_economy_mapped_component_context_values.parquet"
    leaf_reconciliation_candidates_path = tree_output_dir / "source_parent_anchor_leaf_reconciliation_candidates.parquet"
    if skip_reason:
        anchor_detail = pd.DataFrame(columns=["run_id"] + ANCHOR_COLUMNS)
        anchor_child_values = pd.DataFrame(columns=["run_id"] + ANCHOR_CHILD_VALUE_COLUMNS)
        anchor_child_context_values = pd.DataFrame(columns=["run_id"] + ANCHOR_CHILD_CONTEXT_COLUMNS)
        anchor_mapped_component_context_values = pd.DataFrame(columns=["run_id"] + ANCHOR_MAPPED_COMPONENT_CONTEXT_COLUMNS)
        anchor_economy_examples = pd.DataFrame(columns=["run_id"] + ANCHOR_COLUMNS)
        anchor_economy_child_context_values = pd.DataFrame(columns=["run_id"] + ANCHOR_CHILD_CONTEXT_COLUMNS)
        anchor_economy_mapped_component_context_values = pd.DataFrame(columns=["run_id"] + ANCHOR_MAPPED_COMPONENT_CONTEXT_COLUMNS)
        leaf_reconciliation_candidates = pd.DataFrame(columns=["run_id"] + LEAF_RECONCILIATION_CANDIDATE_COLUMNS)
        anchor_summary = pd.DataFrame([{
            "run_id": run_id, "status": "skipped", "eligible": 0,
            "passed": 0, "failed": 0, "skipped": 0, "reason": skip_reason,
        }])
    else:
        # Release memory before the final anchor pass. The core Stage 3
        # comparison output and validation summary are already written by this
        # point, so they are no longer needed for the anchor QA step.
        del detail_df, source_inconsistencies
        gc.collect()
        try:
            raw_anchor_source, source_mapping = load_raw_source_anchor_inputs(
                esto_data_path=ESTO_CSV_PATH,
                esto_extended_data_path=ESTO_EXTENDED_CSV_PATH,
                ninth_data_path=NINTH_CSV_PATH,
                raw_leap_path=RAW_LEAP_PATH,
                workbook_path=WORKBOOK_PATH,
                leap_var_base_year=LEAP_VAR_BASE_YEAR,
                anchor_target_years=set(range(2030, 2071, 10)),
            )
            common_rows = pd.read_csv(COMMON_ROWS_PATH, dtype=object)
            comparison_data = read_manifested_parquet(comparison_path)
            from codebase.mapping_tools.mapping_issue_exceptions import (
                load_unmodelled_source_codes,
            )
            unmodelled_source_codes = load_unmodelled_source_codes()

            # Full-scale anchor validation checks every year for every source
            # system; that is most of its 260k+ row output and multi-minute
            # runtime. The mapping structure being validated is economy/year-
            # independent (see validate_source_parent_anchors docstring), so a
            # base-year-plus-decade slice exercises the same anchors without
            # the near-duplicate rows for every intervening year.
            raw_anchor_years = pd.to_numeric(raw_anchor_source["year"], errors="coerce")
            esto_base_year = int(raw_anchor_years[raw_anchor_source["source_system"] == "ESTO"].max())
            anchor_target_years = {esto_base_year} | set(range(2030, 2071, 10))
            anchor_years_by_system = {
                system: set(
                    raw_anchor_years[raw_anchor_source["source_system"] == system]
                    .dropna().astype(int)
                ) & anchor_target_years
                for system in raw_anchor_source["source_system"].unique()
            }
            print(f"  Anchor validation year slice: {anchor_years_by_system}")

            # Named non-expanding / detached rollup subtotals (e.g. "09.06 Gas
            # processing plants") are genuine raw-source tree nodes, but their
            # value is an explicit rollup-rule contributor sum, not a literal
            # additive total of their declared tree children; exclude them
            # from ordinary additive-parent validation here, matching the
            # Common ESTO recursive validator's exclude_parents fix.
            try:
                from codebase.mapping_tools.non_expanding_rollups import (
                    DETACHED_MODE,
                    NON_EXPANDING_MODE,
                    load_rollup_mode_labels,
                )

                anchor_exclude_parents = {
                    label
                    for label, mode in load_rollup_mode_labels(WORKBOOK_PATH).items()
                    if mode in {NON_EXPANDING_MODE, DETACHED_MODE}
                }
            except Exception as exc:
                print(
                    f"  WARNING: failed to load non-expanding rollup labels for anchor "
                    f"validation ({type(exc).__name__}: {exc}); anchor_exclude_parents will "
                    f"be empty, so NON_EXPANDING/DETACHED rollup subtotals will be validated "
                    f"as ordinary additive parents and may show spurious failures."
                )
                anchor_exclude_parents = set()

            # LEAP interim branches (e.g. "CHP interim") are an alternative
            # representation of the same physical total as their standard
            # sibling ("CHP plants"), not an independent additive total of
            # their own declared children -- the same "not meant to
            # reconcile on its own" semantics as a non-expanding rollup
            # label, just sourced from source_branch_fallback_rules.csv
            # instead of the workbook. Exclude them from ordinary
            # additive-parent validation for the same reason.
            try:
                from codebase.mapping_tools.source_branch_preflight import (
                    load_source_branch_fallback_rules,
                )

                fallback_rules = load_source_branch_fallback_rules(SOURCE_BRANCH_FALLBACK_RULES_PATH)
                anchor_exclude_parents |= {
                    str(branch).strip()
                    for branch in fallback_rules.get("interim_branch", [])
                    if str(branch).strip()
                }
            except Exception as exc:
                print(
                    f"  WARNING: failed to load LEAP interim-branch fallback rules for anchor "
                    f"validation ({type(exc).__name__}: {exc}); interim branches (e.g. \"CHP "
                    f"interim\") will not be excluded from ordinary additive-parent validation "
                    f"and may show spurious failures."
                )

            anchor_t0 = time.perf_counter()
            anchor_result = validate_source_parent_anchors_apec_first(
                source_df=raw_anchor_source,
                source_tree_df=validation_tree,
                source_mapping_df=source_mapping,
                common_rows_df=common_rows,
                years_by_system=anchor_years_by_system,
                comparison_df=comparison_data,
                unmodelled_source_codes=unmodelled_source_codes,
                exclude_parents=anchor_exclude_parents,
            )
            anchor_detail = anchor_result["apec_detail"]
            anchor_economy_examples = anchor_result["economy_examples"]
            anchor_child_context_values = build_failed_anchor_raw_child_context_values(
                anchor_detail,
                anchor_result["apec_source"],
                validation_tree,
            )
            anchor_child_values = summarise_failed_anchor_raw_child_context_values(anchor_child_context_values)
            anchor_mapped_component_context_values = build_failed_anchor_mapped_component_context_values(
                anchor_detail, validation_tree, source_mapping, common_rows,
                anchor_result["apec_comparison"],
            )
            anchor_economy_child_context_values = build_failed_anchor_raw_child_context_values(
                anchor_economy_examples, raw_anchor_source, validation_tree,
            )
            anchor_economy_mapped_component_context_values = build_failed_anchor_mapped_component_context_values(
                anchor_economy_examples, validation_tree, source_mapping, common_rows,
                comparison_data,
            )
            leaf_reconciliation_candidates = build_leaf_reconciliation_exception_candidates(
                anchor_detail, anchor_result["apec_source"], validation_tree,
            )
        except MemoryError as exc:
            print(
                "  WARNING: source_parent_anchor_validation ran out of memory; "
                "skipping anchor detail and writing a skipped summary."
            )
            print(f"  WARNING: {type(exc).__name__}: {exc}")
            anchor_detail = pd.DataFrame(columns=["run_id"] + ANCHOR_COLUMNS)
            anchor_child_values = pd.DataFrame(columns=["run_id"] + ANCHOR_CHILD_VALUE_COLUMNS)
            anchor_child_context_values = pd.DataFrame(columns=["run_id"] + ANCHOR_CHILD_CONTEXT_COLUMNS)
            anchor_mapped_component_context_values = pd.DataFrame(columns=["run_id"] + ANCHOR_MAPPED_COMPONENT_CONTEXT_COLUMNS)
            anchor_economy_examples = pd.DataFrame(columns=["run_id"] + ANCHOR_COLUMNS)
            anchor_economy_child_context_values = pd.DataFrame(columns=["run_id"] + ANCHOR_CHILD_CONTEXT_COLUMNS)
            anchor_economy_mapped_component_context_values = pd.DataFrame(columns=["run_id"] + ANCHOR_MAPPED_COMPONENT_CONTEXT_COLUMNS)
            leaf_reconciliation_candidates = pd.DataFrame(columns=["run_id"] + LEAF_RECONCILIATION_CANDIDATE_COLUMNS)
            anchor_summary = pd.DataFrame([{
                "run_id": run_id,
                "status": "skipped",
                "eligible": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "reason": "memory_error",
            }])
            run_manifest["timings_seconds"]["source_parent_anchor_validation"] = round(
                time.perf_counter() - anchor_t0, 3
            )
        else:
            print(
                f"  [timing] validate_source_parent_anchors: "
                f"{time.perf_counter() - anchor_t0:.1f}s ({len(anchor_detail):,} rows)"
            )
            anchor_detail.insert(0, "run_id", run_id)
            anchor_child_values.insert(0, "run_id", run_id)
            anchor_child_context_values.insert(0, "run_id", run_id)
            anchor_mapped_component_context_values.insert(0, "run_id", run_id)
            anchor_economy_examples.insert(0, "run_id", run_id)
            anchor_economy_child_context_values.insert(0, "run_id", run_id)
            anchor_economy_mapped_component_context_values.insert(0, "run_id", run_id)
            leaf_reconciliation_candidates.insert(0, "run_id", run_id)
            anchor_summary = summarise_source_parent_anchors(anchor_detail)
            anchor_summary.insert(0, "run_id", run_id)
            run_manifest["timings_seconds"]["source_parent_anchor_validation"] = round(
                time.perf_counter() - anchor_t0, 3
            )
    anchor_summary["run_timestamp_utc"] = run_timestamp_utc
    anchor_summary["input_path"] = str(comparison_path.resolve())
    anchor_summary["input_mtime_ns"] = expected_mtime_ns if expected_mtime_ns is not None else ""
    anchor_findings = select_source_parent_anchor_findings(anchor_detail)
    write_manifested_parquet(
        anchor_findings,
        anchor_detail_path,
        artifact_type="source_parent_anchor_validation_findings",
    )
    write_manifested_parquet(
        anchor_detail,
        anchor_full_detail_path,
        artifact_type="source_parent_anchor_validation_full_detail",
    )
    write_manifested_parquet(
        anchor_child_values,
        anchor_child_values_path,
        artifact_type="source_parent_anchor_child_values",
    )
    write_manifested_parquet(
        anchor_child_context_values,
        anchor_child_context_values_path,
        artifact_type="source_parent_anchor_child_context_detail",
    )
    write_manifested_parquet(
        anchor_mapped_component_context_values,
        anchor_mapped_component_context_values_path,
        artifact_type="source_parent_anchor_mapped_component_context_detail",
    )
    write_manifested_parquet(
        anchor_economy_examples,
        anchor_economy_examples_path,
        artifact_type="source_parent_anchor_economy_examples",
    )
    write_manifested_parquet(
        anchor_economy_child_context_values,
        anchor_economy_child_context_values_path,
        artifact_type="source_parent_anchor_economy_child_context_detail",
    )
    write_manifested_parquet(
        anchor_economy_mapped_component_context_values,
        anchor_economy_mapped_component_context_values_path,
        artifact_type="source_parent_anchor_economy_mapped_component_context_detail",
    )
    write_manifested_parquet(
        leaf_reconciliation_candidates,
        leaf_reconciliation_candidates_path,
        artifact_type="source_parent_anchor_leaf_reconciliation_candidates",
    )
    write_manifested_parquet(
        anchor_summary,
        anchor_summary_path,
        artifact_type="source_parent_anchor_validation_summary",
    )

    detail_path = REPO_ROOT / "results" / "tree_structure" / "common_esto_validation.csv"
    summary_path = REPO_ROOT / "results" / "tree_structure" / "common_esto_validation_summary.csv"
    diagnostic_paths = {
        "common_esto_validation_child_detail": tree_output_dir / "common_esto_validation_child_detail.csv",
        "common_esto_validation_issue_patterns": tree_output_dir / "common_esto_validation_issue_patterns.csv",
        "common_esto_validation_rollup_diagnosis": tree_output_dir / "common_esto_validation_rollup_diagnosis.csv",
    }
    validation_status = validation_summary.copy()
    validation_status["record_type"] = "validation"
    validation_status["artifact_name"] = validation_status["validation_name"]
    validation_status["current_output_file"] = detail_path.name
    validation_status["output_mtime_ns"] = detail_path.stat().st_mtime_ns
    validation_status["validation_summary_path"] = str(summary_path.resolve())
    diagnostic_status_rows = []
    for artifact_name, artifact_path in diagnostic_paths.items():
        if artifact_path.exists():
            diagnostic_status_rows.append({
                "run_id": run_id,
                "run_timestamp_utc": run_timestamp_utc,
                "record_type": "validation_diagnostic",
                "artifact_name": artifact_name,
                "current_output_file": artifact_path.name,
                "output_mtime_ns": artifact_path.stat().st_mtime_ns,
                "validation_summary_path": str(summary_path.resolve()),
            })
    diagnostic_status = pd.DataFrame(diagnostic_status_rows)
    anchor_status = anchor_summary.copy()
    anchor_status["record_type"] = "validation"
    anchor_status["artifact_name"] = "source_parent_anchor_validation"
    anchor_status["current_output_file"] = anchor_detail_path.name
    anchor_status["output_mtime_ns"] = anchor_detail_path.stat().st_mtime_ns
    anchor_status["validation_summary_path"] = str(anchor_summary_path.resolve())
    combined_status = pd.concat(
        [stage3_status, validation_status, anchor_status, diagnostic_status], ignore_index=True, sort=False
    )
    combined_status.to_csv(status_path, index=False)

    print(f"  Validation detail rows: {validation_detail_row_count:,}")
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
        raw_checks = int(row.get("raw_check_row_count", row["checks_performed"]))
        raw_mismatches = int(row.get("raw_mismatch_row_count", row["mismatch_count"]))
        print(
            f"  {row['validation_axis']} / {row['source_system']}: {row['status']} "
            f"({int(row['checks_performed']):,} grouped checks, "
            f"{raw_checks:,} fuel/year rows, "
            f"{int(row['eligible_parent_count']):,} eligible parents, "
            f"{int(row['mismatch_count']):,} grouped mismatches, "
            f"{raw_mismatches:,} raw mismatches)"
        )
    print(f"  [timing] STAGE 3 total: {time.perf_counter() - stage3_t0:.1f}s")
    run_manifest["status"] = _stage3_completion_status(validation_summary)
    run_manifest["timings_seconds"]["stage3_total"] = round(
        time.perf_counter() - stage3_t0, 3
    )
    run_manifest["validation"] = {
        "common_esto_summary_path": str(summary_path.resolve()),
        "anchor_summary_path": str(anchor_summary_path.resolve()),
        "anchor_full_detail_path": str(anchor_full_detail_path.resolve()),
        "anchor_status": anchor_summary.to_dict(orient="records"),
        "common_esto_status": validation_summary.to_dict(orient="records"),
    }
    _write_stage3_run_manifest(run_manifest)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_ALL_STAGES = ["generate", "1", "2", "leap_parse", "data_convert", "3"]

_STAGE_RUNNERS = {
    "generate":     run_separate_axis_refresh,
    "1":            run_stage_1,
    "2":            run_stage_2,
    "leap_parse":   run_leap_parse,
    "data_convert": run_data_convert,
    "3":            run_stage_3,
}


def expand_requested_stages(requested: list[str], skipped: set[str]) -> list[str]:
    """Add conversion dependencies to the common abbreviated run sequence.

    ``--stages 1,2,3`` is commonly used as a full mapping refresh, but the
    historical CLI treated ``data_convert`` as an unrelated stage and reused
    whatever conversion artifacts happened to be on disk.  Insert the normal
    LEAP parse and data conversion steps when that exact abbreviated sequence
    is requested, unless the caller explicitly skips them.
    """
    if not {"1", "2", "3"}.issubset(requested):
        return requested

    expanded: list[str] = []
    for stage in requested:
        expanded.append(stage)
        if stage == "2":
            for dependency in ["leap_parse", "data_convert"]:
                if dependency not in skipped and dependency not in requested:
                    expanded.append(dependency)
    return expanded


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
        "--leap-economies",
        default=None,
        help=(
            "Comma-separated list of economy codes to parse during the leap_parse "
            "stage (e.g. --leap-economies 20_USA,12_NZ). Default: auto-discover "
            "every economy with a recognized export directory under the canonical "
            "LEAP exports root."
        ),
    )
    parser.add_argument(
        "--esto-path",
        default=None,
        help="Optional ESTO-style CSV override, allowing a fourth test dataset such as data/esto_extended.csv.",
    )
    parser.add_argument(
        "--esto-extended-path",
        default=None,
        help="Optional additional ESTO Extended CSV override; it is loaded alongside the original ESTO input.",
    )
    parser.add_argument(
        "--mapping-workbook-path",
        default=None,
        help="Optional mapping workbook override for an isolated test mapping set.",
    )
    parser.add_argument(
        "--ninth-path",
        default=None,
        help="Optional Ninth-style CSV override, useful for a reproducible fourth-dataset test slice.",
    )
    parser.add_argument(
        "--raw-leap-path",
        default=None,
        help="Optional parsed raw-LEAP CSV override for a reproducible test slice.",
    )
    parser.add_argument(
        "--skip-deep-validation",
        action="store_true",
        help="Test mode: stop after common-structure application and skip the full recursive/anchor validation pass.",
    )
    parser.add_argument(
        "--write-esto-extended-delta",
        action="store_true",
        help=(
            "After data conversion, publish a verified ESTO-base plus "
            "ESTO-Extended delta contract alongside the full fallback artifact."
        ),
    )
    parser.add_argument(
        "--use-esto-extended-delta",
        action="store_true",
        help=(
            "For Stage 3, validate and reconstruct ESTO Extended from its delta "
            "contract; fall back to the full artifact if contract validation fails."
        ),
    )
    args = parser.parse_args()

    global ESTO_CSV_PATH, ESTO_EXTENDED_CSV_PATH, WORKBOOK_PATH, NINTH_CSV_PATH, RAW_LEAP_PATH
    if args.esto_path:
        ESTO_CSV_PATH = Path(args.esto_path).resolve()
    if args.esto_extended_path:
        ESTO_EXTENDED_CSV_PATH = Path(args.esto_extended_path).resolve()
    if args.mapping_workbook_path:
        WORKBOOK_PATH = Path(args.mapping_workbook_path).resolve()
    if args.ninth_path:
        NINTH_CSV_PATH = Path(args.ninth_path).resolve()
    if args.raw_leap_path:
        RAW_LEAP_PATH = Path(args.raw_leap_path).resolve()

    requested = [s.strip() for s in args.stages.split(",") if s.strip()]
    skipped   = {s.strip() for s in args.skip.split(",") if s.strip()}

    requested = expand_requested_stages(requested, skipped)
    stages_to_run = [s for s in requested if s not in skipped]

    unknown = [s for s in stages_to_run if s not in _STAGE_RUNNERS]
    if unknown:
        print(f"Unknown stage(s): {unknown}")
        print(f"Valid stages: {_ALL_STAGES}")
        sys.exit(1)

    with _log_to_file(_PIPELINE_LOG_PATH) as log_path:
        print(f"[LOG] Writing output to: {log_path}")
        print("Running pipeline stages:", stages_to_run)
        leap_economies = (
            [item.strip() for item in args.leap_economies.split(",") if item.strip()]
            if args.leap_economies
            else None
        )
        with _ResourceUsageMonitor(_RESOURCE_USAGE_PATH) as resource_monitor:
            for stage in stages_to_run:
                resource_monitor.set_stage(stage)
                if stage == "leap_parse":
                    run_leap_parse(economies=leap_economies)
                elif stage == "data_convert":
                    run_data_convert(
                        write_esto_extended_delta=args.write_esto_extended_delta
                    )
                elif stage == "3":
                    run_stage_3(
                        skip_deep_validation=args.skip_deep_validation,
                        use_esto_extended_delta=args.use_esto_extended_delta,
                    )
                else:
                    _STAGE_RUNNERS[stage]()

            print("\n" + "=" * 60)
            print("Pipeline complete.")
            print("=" * 60)


if __name__ == "__main__":
    main()
