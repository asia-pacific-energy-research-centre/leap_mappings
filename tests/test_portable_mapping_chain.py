"""
Integration test for codebase.portable_mapping_chain against a real economy.

This exercises the exact call sequence proven in
leap_initialisation/docs/leap_review_tools_handover_20260803.md §2, using the
real 12_NZ LEAP balance export and the real mapping/config artifacts checked
into this repo (or its results/ output). It is slow (parses ~385k raw rows)
and depends on the sibling leap_initialisation checkout's export data, so it
is skipped when either is unavailable rather than failing the suite.
"""

from pathlib import Path

import pytest

from codebase.portable_mapping_chain import run_mapping_chain

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = (
    REPO_ROOT.parent / "leap_initialisation" / "data" / "leap balances exports" / "12_NZ"
)
CONFIG = REPO_ROOT / "config"
REL = REPO_ROOT / "results" / "mapping_relationships"
CE = REPO_ROOT / "results" / "common_esto"

REQUIRED_PATHS = [
    EXPORT_DIR,
    CONFIG / "outlook_mappings_master.xlsx",
    CONFIG / "source_branch_fallback_rules.csv",
    CONFIG / "all_demand_aggregated_components.json",
    REL / "energy_balance_relationships.csv",
    REL / "esto_results_exact_rows.csv.gz",
    REL / "ninth_results_converted_to_esto.csv.gz",
    CE / "common_esto_rows.csv",
]

pytestmark = pytest.mark.skipif(
    not all(path.exists() for path in REQUIRED_PATHS),
    reason="requires the real 12_NZ export and generated mapping artifacts on disk",
)


def test_run_mapping_chain_12_nz(tmp_path):
    job = {
        "economy": "12_NZ",
        "export_dir": str(EXPORT_DIR),
        "work_dir": str(tmp_path),
        "artifacts": {
            "relationships_path": str(REL / "energy_balance_relationships.csv"),
            "esto_exact_rows_path": str(REL / "esto_results_exact_rows.csv.gz"),
            "ninth_converted_path": str(REL / "ninth_results_converted_to_esto.csv.gz"),
            "common_esto_rows_path": str(CE / "common_esto_rows.csv"),
        },
        "config": {
            "mapping_workbook_path": str(CONFIG / "outlook_mappings_master.xlsx"),
            "source_branch_fallback_rules_path": str(CONFIG / "source_branch_fallback_rules.csv"),
            "all_demand_components_path": str(CONFIG / "all_demand_aggregated_components.json"),
        },
    }

    result = run_mapping_chain(job)

    assert result["raw_leap_rows"] == 385_035
    assert result["converted_rows"] == 45_409
    assert result["comparison_rows"] == 186_211
    assert Path(result["comparison_data_path"]).exists()
    assert Path(result["common_rows_path"]).exists()
    assert "12_NZ" not in result["scenarios"]  # scenario codes, not the economy
    assert result["years"]
