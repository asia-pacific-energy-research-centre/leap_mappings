"""Tests for bounded partition application and contribution lineage."""

import json
from pathlib import Path

import pandas as pd

from codebase.mapping_tools.apply_partitioned_common_esto import (
    apply_partition_frame,
    apply_partitioned_common_esto,
    prepare_partition_cache,
)


def _mapping() -> pd.DataFrame:
    rows = []
    for flow, relation in [("Passenger", "p"), ("Freight", "f")]:
        rows.append({
            "source_system": "LEAP", "original_source_flow": flow,
            "original_source_product": "Oil", "effective_source_flow": "Road",
            "effective_source_product": "Oil", "relationship_id": relation,
            "rule_id": f"road:{relation}", "rollup_context": "road_comparison",
            "evidence_type": "rollup_rule", "component_esto_flow": "15.02 Road",
            "component_esto_product": "07 Oil", "comparison_scope": "all",
            "common_row_id": "road_oil", "component_sign": 1,
        })
    return pd.DataFrame(rows)


def _source() -> pd.DataFrame:
    return pd.DataFrame([
        {"source_system": "LEAP", "economy": "20_USA", "scenario": "Reference", "year": 2023, "source_flow": "Passenger", "source_product": "Oil", "value": "3.5"},
        {"source_system": "LEAP", "economy": "20_USA", "scenario": "Reference", "year": 2023, "source_flow": "Freight", "source_product": "Oil", "value": "2.5"},
    ])


def test_numeric_strings_roll_to_road_with_detailed_lineage() -> None:
    lineage, final, unmatched, accounting = apply_partition_frame(_source(), _mapping())
    assert final.iloc[0]["value"] == 6.0
    assert set(lineage["original_source_flow"]) == {"Passenger", "Freight"}
    assert set(lineage["effective_source_flow"]) == {"Road"}
    assert unmatched.empty
    assert accounting.iloc[0]["input_total"] == 6.0


def test_chunked_cache_reuse_and_result_equivalence(tmp_path: Path, monkeypatch) -> None:
    source_path = tmp_path / "source.csv"
    cache_dir = tmp_path / "cache"
    output_dir = tmp_path / "output"
    map_path = tmp_path / "map.csv"
    pd.concat([_source(), _source().assign(year=2024)], ignore_index=True).to_csv(source_path, index=False)
    _mapping().to_csv(map_path, index=False)
    first = prepare_partition_cache(source_path, cache_dir, chunksize=1)
    assert first["partition_count"] == 2
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cache reparsed")))
    second = prepare_partition_cache(source_path, cache_dir, chunksize=1)
    assert second["cache_reused"]
    monkeypatch.undo()
    apply_partitioned_common_esto(cache_dir, map_path, output_dir)
    result = pd.read_csv(output_dir / "common_esto_comparison_data.csv")
    assert result["value"].tolist() == [6.0, 6.0]
    assert json.loads((output_dir / "application_manifest.json").read_text())["status"] == "complete"


def test_failed_run_never_publishes_final_output(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "cache_manifest.json").write_text(json.dumps({"status": "incomplete"}))
    try:
        apply_partitioned_common_esto(cache_dir, tmp_path / "missing.csv", tmp_path / "output")
    except ValueError:
        pass
    assert not (tmp_path / "output" / "common_esto_comparison_data.csv").exists()
