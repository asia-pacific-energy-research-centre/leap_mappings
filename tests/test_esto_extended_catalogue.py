from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from codebase.mapping_tools.build_esto_extended_test import build_esto_extended
from codebase.mapping_tools.esto_extended_catalogue import (
    CATALOGUE_COLUMNS,
    assert_valid_catalogue,
    build_structural_catalogue,
    catalogue_diagnostics,
    required_extended_pairs,
)
from codebase.mapping_tools.esto_exact_rows import (
    OBSERVED_ORDINARY_ESTO_FACT_PROVENANCE,
)
from codebase.mapping_tools.apply_common_esto_structure import normalise_source_columns


def _workbook(path: Path) -> None:
    mappings = pd.DataFrame([
        {
            "esto_flow": "09.01.01.04 Gas_CCUS",
            "esto_product": "08 Gas",
            "duplicate_to_remove": False,
            "remove_row": False,
            "esto_dataset_scope": "ESTO_EXTENDED",
        },
        {
            "esto_flow": "09.01.01 Gas",
            "esto_product": "08 Gas",
            "duplicate_to_remove": False,
            "remove_row": False,
            "esto_dataset_scope": "BOTH",
        },
    ])
    rollups = pd.DataFrame([
        {
            "input_esto_flow": "09.01.01.04 Gas_CCUS",
            "input_esto_product": "08 Gas",
            "rolled_esto_flow": "09.01.01 Gas",
            "rolled_esto_product": "08 Gas",
            "include": True,
            "ROLLUP_MODE": "EXPANDING",
            "rollup_group_id": "gas_power",
            "esto_dataset_scope": "ESTO_EXTENDED",
        }
    ])
    with pd.ExcelWriter(path) as writer:
        mappings.to_excel(writer, sheet_name="leap_combined_esto", index=False)
        mappings.iloc[0:0].to_excel(writer, sheet_name="ninth_pairs_to_esto_pairs", index=False)
        rollups.to_excel(writer, sheet_name="esto_rollup_rules", index=False)


def test_structural_catalogue_preserves_gas_ccus_without_historical_facts(tmp_path: Path) -> None:
    workbook = tmp_path / "mappings.xlsx"
    output = tmp_path / "esto_extended_catalogue.csv"
    _workbook(workbook)

    catalogue = build_structural_catalogue(workbook, output)

    assert list(catalogue.columns) == CATALOGUE_COLUMNS
    assert (catalogue["flows"] == "09.01.01.04 Gas_CCUS").any()
    assert not {"economy", "year", "value", "2022"}.intersection(catalogue.columns)
    assert catalogue.loc[catalogue["flows"].eq("09.01.01.04 Gas_CCUS"), "rollup_modes"].iloc[0] == "EXPANDING"
    assert output.is_file()


def test_catalogue_coverage_reports_missing_stale_and_numeric_rows_deterministically(tmp_path: Path) -> None:
    workbook = tmp_path / "mappings.xlsx"
    _workbook(workbook)
    required = required_extended_pairs(workbook)
    invalid = required.iloc[[0]].copy()
    invalid.loc[:, "flows"] = "99 Stale"
    invalid["2022"] = 1.0

    diagnostics = catalogue_diagnostics(invalid, required)

    assert diagnostics["status"].tolist() == [
        "invalid_numeric_column",
        "missing_required_pair",
        "missing_required_pair",
        "stale_catalogue_pair",
    ]
    with pytest.raises(ValueError, match="ESTO Extended structural catalogue is invalid"):
        assert_valid_catalogue(invalid, required)


def test_removed_extended_mapping_is_not_required_or_stale(tmp_path: Path) -> None:
    workbook = tmp_path / "mappings.xlsx"
    _workbook(workbook)
    mappings = pd.read_excel(workbook, sheet_name="leap_combined_esto", dtype=object)
    mappings.loc[len(mappings)] = {
        "esto_flow": "09.01.01.99 Removed Gas detail",
        "esto_product": "08 Gas",
        "duplicate_to_remove": False,
        "remove_row": True,
        "esto_dataset_scope": "ESTO_EXTENDED",
    }
    rollups = pd.read_excel(workbook, sheet_name="esto_rollup_rules", dtype=object)
    with pd.ExcelWriter(workbook) as writer:
        mappings.to_excel(writer, sheet_name="leap_combined_esto", index=False)
        mappings.iloc[0:0].to_excel(writer, sheet_name="ninth_pairs_to_esto_pairs", index=False)
        rollups.to_excel(writer, sheet_name="esto_rollup_rules", index=False)

    required = required_extended_pairs(workbook)

    assert "09.01.01.99 Removed Gas detail" not in set(required["flows"])
    assert catalogue_diagnostics(required, required).empty


def test_numeric_fixture_builder_cannot_publish_copied_or_equal_split_gas_ccus_history(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="test-only"):
        build_esto_extended(
            tmp_path / "ordinary_esto.csv",
            tmp_path / "templates",
            tmp_path / "mappings.xlsx",
            tmp_path / "audit",
            production_dataset_path=tmp_path / "esto_extended.csv",
        )


def test_observed_fact_provenance_is_separate_from_structural_exactness() -> None:
    numeric_fact = normalise_source_columns(
        pd.DataFrame([{
            "esto_flow": "09.01.01.04 Gas_CCUS",
            "esto_product": "08 Gas",
            "value": 1.0,
            "is_exact_row": False,
            "fact_value_provenance": OBSERVED_ORDINARY_ESTO_FACT_PROVENANCE,
        }]),
        default_source_system="ESTO",
        default_economy="01_AUS",
    ).iloc[0]

    assert numeric_fact["fact_value_provenance"] == OBSERVED_ORDINARY_ESTO_FACT_PROVENANCE
    assert "is_exact_row" not in numeric_fact.index
