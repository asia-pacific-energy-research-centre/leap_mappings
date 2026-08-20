#%%
"""Checks for per-section mapping-pipeline wall-time and RAM profiling."""

import json
import time

import pandas as pd

from codebase.run_mapping_pipeline import _ResourceUsageMonitor


def test_resource_monitor_writes_nested_section_time_and_ram(tmp_path) -> None:
    json_path = tmp_path / "resource_usage.json"
    csv_path = tmp_path / "performance_summary.csv"

    with _ResourceUsageMonitor(
        json_path,
        interval_seconds=0.01,
        performance_summary_path=csv_path,
    ) as monitor:
        with monitor.measure("stage_1"):
            with monitor.measure("minor_part"):
                payload = bytearray(1024 * 1024)
                time.sleep(0.03)
                assert len(payload) == 1024 * 1024

    report = json.loads(json_path.read_text(encoding="utf-8"))
    summary = pd.read_csv(csv_path)

    assert report["status"] == "recorded"
    assert report["peak_rss_bytes"] > 0
    assert {"stage_1", "stage_1/minor_part"}.issubset(set(summary["section"]))
    assert summary["elapsed_seconds"].gt(0).all()
    assert summary["peak_rss_bytes"].gt(0).all()
    assert {
        "timestamp_utc",
        "section",
        "process_rss_bytes",
        "children_rss_bytes",
        "rss_bytes",
    }.issubset(report["samples"][0])


def test_resource_monitor_checkpoints_active_section_before_exit(tmp_path) -> None:
    json_path = tmp_path / "resource_usage.json"
    csv_path = tmp_path / "performance_summary.csv"
    monitor = _ResourceUsageMonitor(
        json_path,
        interval_seconds=60,
        performance_summary_path=csv_path,
    )

    monitor.__enter__()
    monitor.section_stack.append("deep_validation/recursive_product_group")
    for _ in range(10):
        monitor._sample()

    checkpoint = json.loads(json_path.read_text(encoding="utf-8"))
    assert checkpoint["status"] == "running"
    assert checkpoint["active_section"] == "deep_validation/recursive_product_group"
    assert checkpoint["samples"][-1]["section"] == checkpoint["active_section"]

    monitor.section_stack.pop()
    monitor.__exit__(None, None, None)


#%%
