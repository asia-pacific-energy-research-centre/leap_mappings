from pathlib import Path

import pandas as pd

from codebase.mapping_tools.build_source_coverage_mapping_candidates import (
    _annotate_cardinality,
    build_candidates,
)


def test_cardinality_annotation_quarantines_many_to_many_edges() -> None:
    existing = pd.DataFrame(
        [
            {"source": "S", "target": "T1", "duplicate_to_remove": False},
            {"source": "S2", "target": "T2", "duplicate_to_remove": False},
        ]
    )
    candidates = pd.DataFrame([{"source": "S", "target": "T2"}])

    annotated = _annotate_cardinality(candidates, existing, ["source"], ["target"])

    assert annotated.iloc[0]["cardinality_if_added"] == "MANY_TO_MANY_CONFLICT"


def test_cardinality_annotation_quarantines_parent_child_overlap() -> None:
    existing = pd.DataFrame(
        [
            {
                "source": "16_01_01_child",
                "target": "16.01 Commercial and public services",
                "duplicate_to_remove": False,
            }
        ]
    )
    candidates = pd.DataFrame(
        [{"source": "16_01_parent", "target": "16.01 Commercial and public services"}]
    )

    annotated = _annotate_cardinality(
        candidates, existing, ["source"], ["target"]
    )

    assert annotated.iloc[0]["cardinality_if_added"] == "PARENT_CHILD_OVERLAP_CONFLICT"
    assert bool(annotated.iloc[0]["parent_child_overlap"])


def test_cardinality_annotation_shows_existing_mapping_context() -> None:
    existing = pd.DataFrame(
        [
            {"source": "Existing branch", "target": "Existing flow", "duplicate_to_remove": False}
        ]
    )
    candidates = pd.DataFrame([{"source": "New branch", "target": "Existing flow"}])

    annotated = _annotate_cardinality(candidates, existing, ["source"], ["target"])

    assert annotated.iloc[0]["existing_mappings_to_same_target"] == "Existing branch"
    assert annotated.iloc[0]["existing_mappings_from_same_source"] == ""


def test_build_candidates_keeps_sheet_rows_copy_ready_and_does_not_edit_workbook() -> None:
    detail = pd.DataFrame(
        [
            {
                "scope": "test",
                "component": "Industry",
                "source": "9th",
                "economy": "20_USA",
                "source_flow": "14_industry_sector",
                "source_fuel": "07_01_motor_gasoline",
                "mapped_leap_fuel": "Motor gasoline",
                "coverage_status": "MISSING_LEAP_FUEL",
                "mapping_status": "MAPPED",
            }
        ]
    )
    scope = {
        "name": "test",
        "mapping_root": "All demand aggregated",
        "components": [
            {
                "name": "Industry",
                "mapping_ninth_sectors": ["14_industry_sector"],
                "mapping_esto_flows": ["14 Industry sector"],
            }
        ],
    }
    mapping_path = Path("test_source_coverage_candidates.xlsx")
    with pd.ExcelWriter(mapping_path) as writer:
        pd.DataFrame(
            [
                {
                    "leap_sector_name_full_path": "Industry",
                    "raw_leap_fuel_name": "Motor gasoline",
                    "ninth_sector": "14_industry_sector",
                    "ninth_fuel": "07_01_motor_gasoline",
                    "duplicate_to_remove": False,
                }
            ]
        ).to_excel(writer, sheet_name="leap_combined_ninth", index=False)
        pd.DataFrame(
            [
                {
                    "leap_sector_name_full_path": "Industry",
                    "raw_leap_fuel_name": "Motor gasoline",
                    "esto_flow": "14 Industry sector",
                    "esto_product": "07.01 Motor gasoline",
                    "duplicate_to_remove": False,
                }
            ]
        ).to_excel(writer, sheet_name="leap_combined_esto", index=False)
        pd.DataFrame(columns=["ninth_sector", "ninth_fuel", "esto_flow", "esto_product"]).to_excel(
            writer, sheet_name="ninth_pairs_to_esto_pairs", index=False
        )
    try:
        outputs = build_candidates(detail, scope, mapping_path=mapping_path)
    finally:
        mapping_path.unlink(missing_ok=True)
    # The candidate target path is the new nested branch, and rows already
    # present under the old path are not treated as duplicates.
    assert outputs["leap_combined_ninth"].iloc[0]["leap_sector_name_full_path"] == "All demand aggregated/Industry"
    assert outputs["leap_combined_ninth"].iloc[0]["ninth_fuel"] == "07_01_motor_gasoline"
    assert outputs["unresolved"].empty
