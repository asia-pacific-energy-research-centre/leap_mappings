"""
portable_mapping_chain.py

Worker entry point for the portable LEAP review tools' dashboard chain.

Runs entirely inside a process with only ``leap_mappings`` on ``sys.path``
(see the two-executable design in
``leap_initialisation/docs/leap_review_tools_handover_20260803.md`` §1 —
``leap_initialisation.codebase`` and ``leap_mappings.codebase`` both use
absolute ``codebase.x.y`` imports under the same top-level package name and
cannot coexist in one PyInstaller bundle).

Reads a single JSON job from stdin, runs the three proven chain steps
(parse export -> convert to ESTO -> apply Common ESTO structure fast path),
and writes a single JSON result to stdout. Any failure becomes
``{"error": "..."}`` on stdout with a non-zero exit code, so the caller never
has to parse a Python traceback.

Job schema (all paths are strings, resolved by the caller before invocation)::

    {
        "economy": "12_NZ",
        "export_dir": "...",
        "work_dir": "...",
        "artifacts": {
            "relationships_path": "...",
            "esto_exact_rows_path": "...",
            "ninth_converted_path": "...",
            "common_esto_rows_path": "..."
        },
        "config": {
            "mapping_workbook_path": "...",
            "source_branch_fallback_rules_path": "...",
            "all_demand_components_path": "..."
        }
    }

Result schema on success::

    {
        "comparison_data_path": "...",
        "common_rows_path": "...",
        "raw_leap_rows": 385035,
        "converted_rows": 48068,
        "comparison_rows": 194694,
        "scenarios": [...],
        "years": [...],
        "notes": [...]
    }
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.mapping_tools.apply_common_esto_structure import (  # noqa: E402
    NINTH_PROJECTION_START_YEAR,
    run_common_esto_comparison_fast_path,
)
from codebase.mapping_tools.convert_leap_results_to_esto import (  # noqa: E402
    run_conversion,
)
from codebase.mapping_tools.parse_leap_balance_export import (  # noqa: E402
    parse_leap_balance_dir,
)


def prepare_esto_exact_rows(
    *,
    bundled_exact_rows: Path,
    esto_base_table: Path | None,
    synthetic_rules_path: Path | None,
    relationships_path: Path,
    mapping_workbook_path: Path,
    work_dir: Path,
    notes: list[str],
) -> Path:
    """Return the ESTO exact-row table to compare against.

    A release ships exact rows extracted from one ESTO issue. When the caller
    supplies a raw ESTO base table - because the user dropped in a newer issue -
    those shipped rows are the wrong vintage, and using them would compare LEAP
    against last year's data while looking entirely normal.

    So the rows are re-extracted here from the supplied table. Synthetic
    reference rows are applied to the raw table *first*, because they describe
    rows a given ESTO issue may not carry (Datacentres, hydrogen transformation)
    and the extraction can only find rows that exist. Every injected row stays
    tagged with the rule that created it.

    Extraction takes roughly a minute, so the result is cached on the identity
    of its inputs: a second run against the same table reuses it.
    """
    if esto_base_table is None or not Path(esto_base_table).is_file():
        return bundled_exact_rows

    esto_base_table = Path(esto_base_table)
    fingerprint = _fingerprint(
        [esto_base_table, synthetic_rules_path, relationships_path, mapping_workbook_path]
    )
    cached = work_dir / f"esto_results_exact_rows_{fingerprint}.csv.gz"
    if cached.is_file():
        notes.append(f"Reused cached ESTO exact rows for this table ({cached.name}).")
        return cached

    prepared_table = esto_base_table
    if synthetic_rules_path and Path(synthetic_rules_path).is_file():
        prepared_table, added = _apply_synthetic_rows(
            esto_base_table, Path(synthetic_rules_path), work_dir
        )
        notes.append(
            f"Applied synthetic reference rows to the ESTO table: {added} row(s) added."
        )

    # The extracted module, not the pipeline runner: importing the runner would
    # bundle the Stage 1/2 builders and the separate-axis workflows into this
    # worker to reach one function.
    from codebase.mapping_tools.esto_exact_rows import run_esto_exact_rows_for_path

    run_esto_exact_rows_for_path(
        prepared_table,
        cached,
        "ESTO",
        relationships_path=relationships_path,
        mapping_workbook_path=mapping_workbook_path,
    )
    notes.append(
        f"Re-extracted ESTO exact rows from {esto_base_table.name} "
        "because a base table was supplied."
    )
    return cached


def _fingerprint(paths: list[Path | None]) -> str:
    """Return a short digest identifying a set of input files."""
    import hashlib

    digest = hashlib.sha256()
    for path in paths:
        if path is None or not Path(path).is_file():
            digest.update(b"<absent>")
            continue
        stat = Path(path).stat()
        digest.update(f"{Path(path).name}:{stat.st_size}:{int(stat.st_mtime)}".encode())
    return digest.hexdigest()[:12]


def _apply_synthetic_rows(
    esto_table: Path, rules_path: Path, work_dir: Path
) -> tuple[Path, int]:
    """Write a copy of *esto_table* with the synthetic reference rows added."""
    import pandas as pd

    from codebase.utilities.leap_results_dashboard_v2.reference_loader import (
        append_synthetic_reference_rows,
        load_synthetic_reference_rows_config,
    )

    esto_df = pd.read_csv(esto_table, dtype=object)
    rules = load_synthetic_reference_rows_config(rules_path)
    # The 9th frame is not needed here: only the ESTO side feeds this extraction.
    esto_out, _ninth_out, _status = append_synthetic_reference_rows(
        esto_df=esto_df,
        ninth_df=pd.DataFrame(),
        rules=rules,
    )
    added = len(esto_out) - len(esto_df)
    # The tagging columns are for provenance, not for the extraction, which
    # expects the published ESTO column set.
    esto_out = esto_out.drop(
        columns=[c for c in esto_out.columns if c.startswith("_synthetic")],
        errors="ignore",
    )
    prepared = work_dir / "esto_base_table_with_synthetic_rows.csv"
    esto_out.to_csv(prepared, index=False)
    return prepared, added


def run_mapping_chain(job: dict) -> dict:
    """Run the parse -> convert -> Common ESTO fast-path chain for one economy."""
    economy = job["economy"]
    export_dir = Path(job["export_dir"])
    work_dir = Path(job["work_dir"])
    work_dir.mkdir(parents=True, exist_ok=True)

    artifacts = job.get("artifacts", {})
    config = job.get("config", {})
    notes: list[str] = []

    # Settle which ESTO exact rows this run compares against before anything
    # else uses them: both the conversion and the fast path read them.
    esto_exact_rows_path = prepare_esto_exact_rows(
        bundled_exact_rows=Path(artifacts["esto_exact_rows_path"]),
        esto_base_table=(
            Path(config["esto_base_table_path"])
            if config.get("esto_base_table_path")
            else None
        ),
        synthetic_rules_path=(
            Path(config["synthetic_reference_rows_path"])
            if config.get("synthetic_reference_rows_path")
            else None
        ),
        relationships_path=Path(artifacts["relationships_path"]),
        mapping_workbook_path=Path(config["mapping_workbook_path"]),
        work_dir=work_dir,
        notes=notes,
    )

    raw_leap_path = work_dir / "raw_leap_results.csv"
    converted_path = work_dir / "leap_results_converted_to_esto.csv"

    raw_df = parse_leap_balance_dir(export_dir, raw_leap_path, economy_code=economy)
    raw_leap_rows = len(raw_df)

    converted_df = run_conversion(
        leap_results_path=raw_leap_path,
        relationships_path=Path(artifacts["relationships_path"]),
        output_path=converted_path,
        mapping_workbook_path=Path(config["mapping_workbook_path"]),
        rollup_audit_path=work_dir / "leap_source_rollup_audit.csv",
        target_values_path=esto_exact_rows_path,
        lineage_output_path=work_dir / "lineage.csv.gz",
        source_branch_fallback_rules_path=Path(config["source_branch_fallback_rules_path"]),
        all_demand_components_path=Path(config["all_demand_components_path"]),
        preflight_audit_dir=work_dir,
    )
    converted_rows = len(converted_df)

    common_rows_path = Path(artifacts["common_esto_rows_path"])
    comparison_df, _wide_year_df, missing_map_df = run_common_esto_comparison_fast_path(
        source_paths={
            "LEAP": converted_path,
            "NINTH": Path(artifacts["ninth_converted_path"]),
            "ESTO": esto_exact_rows_path,
        },
        common_rows_path=common_rows_path,
        output_dir=work_dir,
        default_economy=economy,
        active_component_abs_tolerance=0.0,
        ninth_projection_start_year=NINTH_PROJECTION_START_YEAR,
        economies=[economy],
        run_id=job.get("run_id"),
        run_timestamp_utc=job.get("run_timestamp_utc"),
        # Without this, build_wide_year_output() (called internally, with no
        # override) falls back to the module-level OUTLOOK_MAPPINGS_PATH
        # constant, which is REPO_ROOT/config/outlook_mappings_master.xlsx -
        # REPO_ROOT being sys._MEIPASS when frozen, where that file does not
        # exist. Point it at the workbook this job was actually given.
        outlook_mappings_path=Path(config["mapping_workbook_path"]),
    )
    comparison_rows = len(comparison_df)
    if not missing_map_df.empty:
        notes.append(
            f"{len(missing_map_df):,} source rows had no Common ESTO map "
            "(see qa_common_esto_unresolved_partial_coverage.csv)."
        )

    scenarios = sorted(comparison_df["scenario"].dropna().astype(str).unique().tolist())
    years = sorted(int(year) for year in comparison_df["year"].dropna().unique().tolist())

    return {
        "comparison_data_path": str(work_dir / "common_esto_comparison_data.csv"),
        "common_rows_path": str(common_rows_path),
        "raw_leap_rows": raw_leap_rows,
        "converted_rows": converted_rows,
        "comparison_rows": comparison_rows,
        "scenarios": scenarios,
        "years": years,
        "notes": notes,
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--self-test":
        print(json.dumps({"ok": True, "worker": "leap_mapping_chain"}))
        return 0

    try:
        job = json.load(sys.stdin)
        result = run_mapping_chain(job)
    except Exception as exc:  # noqa: BLE001 - errors must reach the caller as JSON
        print(json.dumps({"error": str(exc)}))
        return 1

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
