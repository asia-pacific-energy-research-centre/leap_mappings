from pathlib import Path

import pandas as pd

from codebase.mapping_tools.source_coverage_audit import (
    STATUS_MISSING_LEAP,
    STATUS_OK,
    STATUS_UNMAPPED,
    _nonzero_stats,
    audit_source_coverage,
)


def test_nonzero_stats_keeps_negative_values_and_drops_zero_rows() -> None:
    frame = pd.DataFrame(
        {
            "economy": ["20_USA", "20_USA", "20_USA"],
            "fuel": ["bunker", "bunker", "zero"],
            "2023": [-4.0, 0.0, 0.0],
            "2024": [0.0, 0.0, 0.0],
        }
    )
    result = _nonzero_stats(frame, ["2023", "2024"], ["economy", "fuel"])
    assert result[["economy", "fuel"]].to_records(index=False).tolist() == [("20_USA", "bunker")]
    assert bool(result.iloc[0]["has_negative_value"])
    assert result.iloc[0]["total_abs"] == 4.0


def test_audit_is_source_first_and_flags_unmapped_and_missing_leap() -> None:
    scope = {
        "name": "test",
        "leap_root": r"Demand\All demand aggregated",
        "components": [
            {
                "name": "Industry",
                "mapping_ninth_sectors": ["14_industry_sector"],
                "mapping_esto_flows": [],
            }
        ],
    }
    source = pd.DataFrame(
        [
            {"economy": "20_USA", "scope": "test", "component": "Industry", "source": "9th", "source_flow": "14_industry_sector", "source_fuel": "mapped", "nonzero_rows": 1, "nonzero_years": 1, "total_abs": 2.0, "max_abs": 2.0, "has_negative_value": False},
            {"economy": "20_USA", "scope": "test", "component": "Industry", "source": "9th", "source_flow": "14_industry_sector", "source_fuel": "unmapped", "nonzero_rows": 1, "nonzero_years": 1, "total_abs": 3.0, "max_abs": 3.0, "has_negative_value": False},
        ]
    )
    mapping = pd.DataFrame(
        [{"ninth_sector": "14_industry_sector", "ninth_fuel": "mapped", "raw_leap_fuel_name": "Mapped fuel", "duplicate_to_remove": False}]
    )
    mapping_path = Path("test_source_coverage_mapping.xlsx")
    with pd.ExcelWriter(mapping_path) as writer:
        mapping.to_excel(writer, sheet_name="leap_combined_ninth", index=False)
        pd.DataFrame(columns=["esto_flow", "esto_product", "raw_leap_fuel_name", "duplicate_to_remove"]).to_excel(writer, sheet_name="leap_combined_esto", index=False)
    try:
        detail = audit_source_coverage(
            source,
            scope,
            mapping_path=mapping_path,
            leap_presence={"20_USA": {r"Industry\Mapped fuel"}},
        )
    finally:
        mapping_path.unlink(missing_ok=True)
    statuses = dict(zip(detail["source_fuel"], detail["coverage_status"]))
    assert statuses["mapped"] == STATUS_OK
    assert statuses["unmapped"] == STATUS_UNMAPPED


def test_audit_flags_mapped_fuel_missing_from_leap() -> None:
    scope = {
        "name": "test",
        "leap_root": r"Demand\All demand aggregated",
        "components": [{"name": "Industry", "mapping_ninth_sectors": ["14"], "mapping_esto_flows": []}],
    }
    source = pd.DataFrame([{"economy": "20_USA", "scope": "test", "component": "Industry", "source": "9th", "source_flow": "14", "source_fuel": "mapped", "nonzero_rows": 1, "nonzero_years": 1, "total_abs": 1.0, "max_abs": 1.0, "has_negative_value": False}])
    mapping_path = Path("test_source_coverage_mapping_missing.xlsx")
    with pd.ExcelWriter(mapping_path) as writer:
        pd.DataFrame([{"ninth_sector": "14", "ninth_fuel": "mapped", "raw_leap_fuel_name": "Mapped fuel", "duplicate_to_remove": False}]).to_excel(writer, sheet_name="leap_combined_ninth", index=False)
        pd.DataFrame(columns=["esto_flow", "esto_product", "raw_leap_fuel_name", "duplicate_to_remove"]).to_excel(writer, sheet_name="leap_combined_esto", index=False)
    try:
        detail = audit_source_coverage(source, scope, mapping_path=mapping_path, leap_presence={"20_USA": set()})
    finally:
        mapping_path.unlink(missing_ok=True)
    assert detail.iloc[0]["coverage_status"] == STATUS_MISSING_LEAP
