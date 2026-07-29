#%%
"""Capture reproducible Stage 1-3 evidence for multi-dataset refactoring.

The manifest distinguishes freshly generated artifacts from historical
reference artifacts. It is intentionally descriptive: failed validations and
dirty source checkouts are recorded rather than converted into a false pass.
"""

#%%
from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_OUTPUT_PATH = (
    REPO_ROOT
    / "docs"
    / "baselines"
    / "multi_dataset_m0_reference_20260729.json"
)

CURRENT_ARTIFACT_SPECS = [
    {
        "stage": "input",
        "relative_path": "config/outlook_mappings_master.xlsx",
        "format": "xlsx",
        "required": True,
    },
    {
        "stage": "input",
        "relative_path": "config/datasets/dataset_registry.csv",
        "format": "csv",
        "required": True,
    },
    {
        "stage": "input",
        "relative_path": "config/datasets/comparison_scopes.csv",
        "format": "csv",
        "required": True,
    },
    {
        "stage": "input",
        "relative_path": "config/datasets/mapping_sheet_registry.csv",
        "format": "csv",
        "required": True,
    },
    {
        "stage": "stage_1",
        "relative_path": (
            "results/mapping_relationships/energy_balance_relationships.csv"
        ),
        "format": "csv",
        "required": True,
    },
    {
        "stage": "stage_1",
        "relative_path": (
            "results/mapping_relationships/relationship_catalogue_6_col.csv"
        ),
        "format": "csv",
        "required": True,
    },
    {
        "stage": "stage_1",
        "relative_path": (
            "results/mapping_relationships/"
            "one_to_many_mappings_without_allocation_or_combined_target.csv"
        ),
        "format": "csv",
        "required": True,
    },
    {
        "stage": "stage_2",
        "relative_path": "results/common_esto/common_esto_rows.csv",
        "format": "csv",
        "required": True,
    },
    {
        "stage": "stage_2",
        "relative_path": "results/common_esto/esto_to_common_esto_map.csv",
        "format": "csv",
        "required": True,
    },
    {
        "stage": "stage_2",
        "relative_path": (
            "results/common_esto/qa_common_esto_structure_summary.csv"
        ),
        "format": "csv",
        "required": True,
    },
]

HISTORICAL_STAGE_3_ARTIFACT_SPECS = [
    {
        "stage": "stage_3",
        "relative_path": "results/common_esto/common_esto_comparison_data.csv",
        "format": "csv",
        "required": True,
    },
    {
        "stage": "stage_3",
        "relative_path": "results/common_esto/common_esto_comparison_wide.csv",
        "format": "csv",
        "required": True,
    },
    {
        "stage": "stage_3",
        "relative_path": "results/common_esto/common_esto_output_status.csv",
        "format": "csv",
        "required": True,
    },
    {
        "stage": "stage_3",
        "relative_path": "results/common_esto/stage3_run_manifest.json",
        "format": "json",
        "required": True,
    },
    {
        "stage": "stage_3",
        "relative_path": "results/common_esto/common_esto_total_check.csv",
        "format": "csv",
        "required": True,
    },
    {
        "stage": "stage_3",
        "relative_path": (
            "results/common_esto/common_esto_source_coverage_check.csv"
        ),
        "format": "csv",
        "required": True,
    },
]


def _sha256(path: Path) -> str:
    """Return a streaming SHA-256 digest for one artifact."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _csv_schema_and_row_count(
    path: Path,
    chunk_size: int = 250_000,
) -> tuple[list[str], int]:
    """Read a CSV in bounded chunks and return its ordered schema and row count."""
    try:
        header = pd.read_csv(path, nrows=0)
    except pd.errors.EmptyDataError:
        return [], 0
    row_count = 0
    for chunk in pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        chunksize=chunk_size,
        low_memory=False,
    ):
        row_count += len(chunk)
    return header.columns.astype(str).tolist(), row_count


def inspect_artifact(
    root: Path,
    artifact_spec: dict[str, Any],
    source_label: str,
) -> dict[str, Any]:
    """Return hash, size, timestamp, schema, and count for one artifact."""
    root = Path(root)
    relative_path = str(artifact_spec["relative_path"])
    path = root / relative_path
    required = bool(artifact_spec.get("required", True))
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Required baseline artifact is missing: {path}")
        return {
            "stage": str(artifact_spec["stage"]),
            "source_label": source_label,
            "relative_path": relative_path,
            "format": str(artifact_spec["format"]),
            "exists": False,
        }

    modified_at = datetime.fromtimestamp(
        path.stat().st_mtime,
        tz=timezone.utc,
    ).isoformat()
    result: dict[str, Any] = {
        "stage": str(artifact_spec["stage"]),
        "source_label": source_label,
        "relative_path": relative_path,
        "format": str(artifact_spec["format"]),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "modified_at_utc": modified_at,
        "sha256": _sha256(path),
    }

    if artifact_spec["format"] == "csv":
        columns, row_count = _csv_schema_and_row_count(path)
        result["columns"] = columns
        result["row_count"] = row_count
    elif artifact_spec["format"] == "json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        result["top_level_keys"] = (
            sorted(payload) if isinstance(payload, dict) else []
        )
    return result


def _run_git(root: Path, arguments: list[str]) -> str:
    """Run one read-only Git query and return stripped text."""
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def capture_git_context(root: Path) -> dict[str, Any]:
    """Return the checkout identity without embedding machine-local paths."""
    status_lines = [
        line
        for line in _run_git(root, ["status", "--short"]).splitlines()
        if line.strip()
    ]
    return {
        "commit": _run_git(root, ["rev-parse", "HEAD"]),
        "branch": _run_git(root, ["branch", "--show-current"]),
        "clean": not status_lines,
        "dirty_entry_count": len(status_lines),
    }


def _numeric_totals(rows: list[dict[str, Any]]) -> dict[str, int | float]:
    """Sum stable validation count fields found across status rows."""
    count_fields = [
        "eligible",
        "passed",
        "failed",
        "skipped",
        "checks_performed",
        "mismatch_count",
        "raw_check_row_count",
        "raw_mismatch_row_count",
    ]
    totals: dict[str, int | float] = {}
    for field in count_fields:
        values = [
            row[field]
            for row in rows
            if isinstance(row.get(field), (int, float))
        ]
        if values:
            totals[field] = sum(values)
    return totals


def summarize_stage_3_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return a bounded summary without retaining machine-local paths."""
    validation_summary: dict[str, Any] = {}
    for section_name, value in manifest.get("validation", {}).items():
        if not isinstance(value, list):
            continue
        rows = [row for row in value if isinstance(row, dict)]
        validation_summary[section_name] = {
            "row_count": len(rows),
            "status_counts": dict(
                sorted(
                    Counter(
                        str(row.get("status", "unspecified"))
                        for row in rows
                    ).items()
                )
            ),
            "numeric_totals": _numeric_totals(rows),
        }

    datasets = {
        dataset_id: {
            "exists": bool(metadata.get("exists")),
            "size_bytes": metadata.get("size_bytes"),
        }
        for dataset_id, metadata in manifest.get("datasets", {}).items()
        if isinstance(metadata, dict)
    }
    return {
        "run_id": manifest.get("run_id"),
        "run_timestamp_utc": manifest.get("run_timestamp_utc"),
        "status": manifest.get("status"),
        "comparison_scopes": manifest.get("comparison_scopes", []),
        "datasets": datasets,
        "timings_seconds": manifest.get("timings_seconds", {}),
        "validation": validation_summary,
    }


def capture_multi_dataset_baseline(
    current_root: Path,
    historical_stage_3_root: Path,
    output_path: Path,
    captured_at_utc: str | None = None,
) -> dict[str, Any]:
    """Capture current Stage 1/2 and reference-only historical Stage 3 evidence."""
    current_root = Path(current_root)
    historical_stage_3_root = Path(historical_stage_3_root)
    output_path = Path(output_path)
    capture_time = captured_at_utc or datetime.now(timezone.utc).isoformat()

    artifacts = [
        inspect_artifact(current_root, spec, "current_worktree")
        for spec in CURRENT_ARTIFACT_SPECS
    ]
    artifacts.extend(
        inspect_artifact(
            historical_stage_3_root,
            spec,
            "historical_stage_3_reference",
        )
        for spec in HISTORICAL_STAGE_3_ARTIFACT_SPECS
    )

    stage_3_manifest_path = (
        historical_stage_3_root
        / "results"
        / "common_esto"
        / "stage3_run_manifest.json"
    )
    stage_3_manifest = json.loads(
        stage_3_manifest_path.read_text(encoding="utf-8")
    )
    manifest = {
        "contract_version": "multi_dataset_m0_baseline_v1",
        "captured_at_utc": capture_time,
        "release_gate_complete": False,
        "baseline_status": "current_stage_1_2_with_historical_stage_3_reference",
        "current_worktree_git": capture_git_context(current_root),
        "historical_stage_3_checkout_git_at_capture": capture_git_context(
            historical_stage_3_root
        ),
        "artifacts": artifacts,
        "historical_stage_3_run": summarize_stage_3_manifest(stage_3_manifest),
        "limitations": [
            (
                "Stage 1 and Stage 2 were freshly generated in the isolated "
                "multi-dataset registry worktree."
            ),
            (
                "Stage 3 artifacts are reference-only: they predate the current "
                "branch and their manifest contains known failed validations."
            ),
            (
                "The historical Stage 3 checkout is dirty at capture time; its "
                "current Git state is not asserted to be the producing state."
            ),
            (
                "A fresh QA-reviewed Stage 3 run is still required before the "
                "M0 release equivalence gate can be marked complete."
            ),
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)
    return manifest


#%%
# Toggle block for Jupyter use. Keep false unless a historical Stage 3 checkout
# has been reviewed and selected deliberately.
CAPTURE_BASELINE = False
HISTORICAL_STAGE_3_ROOT = Path(r"C:\Users\Work\github\leap_mappings")

if CAPTURE_BASELINE:
    CAPTURED_BASELINE = capture_multi_dataset_baseline(
        current_root=REPO_ROOT,
        historical_stage_3_root=HISTORICAL_STAGE_3_ROOT,
        output_path=BASELINE_OUTPUT_PATH,
    )
    print(json.dumps(CAPTURED_BASELINE, indent=2))

#%%
