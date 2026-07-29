import hashlib
import json
from pathlib import Path

from codebase.mapping_tools.capture_multi_dataset_baseline import (
    inspect_artifact,
    summarize_stage_3_manifest,
)


def test_inspect_csv_artifact_captures_schema_count_and_hash(
    tmp_path: Path,
) -> None:
    path = tmp_path / "example.csv"
    content = "dataset_id,value\nESTO,1\nLEAP,2\n"
    path.write_text(content, encoding="utf-8")
    written_bytes = path.read_bytes()

    result = inspect_artifact(
        root=tmp_path,
        artifact_spec={
            "stage": "stage_1",
            "relative_path": "example.csv",
            "format": "csv",
            "required": True,
        },
        source_label="test",
    )

    assert result["columns"] == ["dataset_id", "value"]
    assert result["row_count"] == 2
    assert result["size_bytes"] == len(written_bytes)
    assert result["sha256"] == hashlib.sha256(written_bytes).hexdigest()


def test_inspect_json_artifact_records_top_level_keys(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"status": "completed", "run_id": "example"}),
        encoding="utf-8",
    )

    result = inspect_artifact(
        root=tmp_path,
        artifact_spec={
            "stage": "stage_3",
            "relative_path": "manifest.json",
            "format": "json",
            "required": True,
        },
        source_label="test",
    )

    assert result["top_level_keys"] == ["run_id", "status"]


def test_inspect_empty_csv_records_zero_rows_and_no_schema(
    tmp_path: Path,
) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("\n", encoding="utf-8")

    result = inspect_artifact(
        root=tmp_path,
        artifact_spec={
            "stage": "stage_1",
            "relative_path": "empty.csv",
            "format": "csv",
            "required": True,
        },
        source_label="test",
    )

    assert result["columns"] == []
    assert result["row_count"] == 0


def test_stage_3_summary_preserves_failures_without_absolute_paths() -> None:
    manifest = {
        "run_id": "run_1",
        "run_timestamp_utc": "2026-07-29T00:00:00+00:00",
        "status": "completed",
        "comparison_scopes": ["esto_leap"],
        "datasets": {
            "ESTO": {
                "exists": True,
                "size_bytes": 100,
                "path": "C:/machine/local/file.csv",
            }
        },
        "timings_seconds": {"stage3_total": 12.5},
        "validation": {
            "anchor_status": [
                {
                    "status": "failed",
                    "eligible": 10,
                    "passed": 8,
                    "failed": 2,
                    "input_path": "C:/machine/local/input.csv",
                },
                {
                    "status": "passed",
                    "eligible": 5,
                    "passed": 5,
                    "failed": 0,
                },
            ],
            "anchor_summary_path": "C:/machine/local/summary.csv",
        },
    }

    result = summarize_stage_3_manifest(manifest)

    assert result["datasets"] == {
        "ESTO": {"exists": True, "size_bytes": 100}
    }
    assert result["validation"]["anchor_status"] == {
        "row_count": 2,
        "status_counts": {"failed": 1, "passed": 1},
        "numeric_totals": {
            "eligible": 15,
            "passed": 13,
            "failed": 2,
        },
    }
    assert "anchor_summary_path" not in result["validation"]
