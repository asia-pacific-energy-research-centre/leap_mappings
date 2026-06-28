import pandas as pd

from codebase.mapping_tools.apply_common_esto_structure import (
    apply_common_structure,
    build_component_relevance,
    build_unmapped_leap_branch_evidence,
    filter_missing_common_map_diagnostics,
    filter_partial_coverage_by_relevance,
    should_ignore_missing_common_map_flow,
)


def test_apply_common_structure_retains_generated_total_label() -> None:
    source_df = pd.DataFrame(
        [
            {
                "source_system": "LEAP",
                "economy": "20_USA",
                "scenario": "Reference",
                "year": 2060,
                "esto_flow": "14 Industry sector",
                "esto_product": "08.01 Natural gas",
                "value": 10.0,
            }
        ]
    )
    common_rows_df = pd.DataFrame(
        [
            {
                "comparison_scope": "leap_vs_esto",
                "component_esto_flow": "14 Industry sector",
                "component_esto_product": "08.01 Natural gas",
                "common_row_id": "common_total_final_consumption",
                "common_flow_code": "12,13,14,16.01-16.02",
                "common_flow_name": "Total final consumption",
                "common_flow_label": "12,13,14,16.01-16.02 Total final consumption",
                "common_product_code": "08.01",
                "common_product_name": "Natural gas",
                "common_product_label": "08.01 Natural gas",
                "component_sign": 1,
            }
        ]
    )

    comparison_df, missing_map_df, _ = apply_common_structure(source_df, common_rows_df)

    assert missing_map_df.empty
    assert comparison_df["common_flow_label"].tolist() == [
        "12,13,14,16.01-16.02 Total final consumption"
    ]
    assert comparison_df["value"].tolist() == [10.0]


def test_should_ignore_missing_common_map_flow_for_known_ignored_flows() -> None:
    assert should_ignore_missing_common_map_flow("06 Stock changes")
    assert should_ignore_missing_common_map_flow("  11   Statistical discrepancy  ")
    assert should_ignore_missing_common_map_flow("18.01 MAP electricity plants")
    assert should_ignore_missing_common_map_flow("19.01 MAP CHP plants")
    assert not should_ignore_missing_common_map_flow("09.01.01 Electricity plants")
    assert not should_ignore_missing_common_map_flow("16.09 Other sources")


def test_filter_missing_common_map_diagnostics_drops_ignored_flows_only() -> None:
    missing_map_df = pd.DataFrame(
        {
            "esto_flow": [
                "06 Stock changes",
                "11 Statistical discrepancy",
                "18.01 MAP electricity plants",
                "19.01 MAP CHP plants",
                "09.01.01 Electricity plants",
                "16.09 Other sources",
            ],
            "esto_product": [
                "01.01 Coking coal",
                "01.01 Coking coal",
                "15.05 Other biomass",
                "19 Total",
                "17 Electricity",
                "16.09 Other sources",
            ],
        }
    )

    filtered_df = filter_missing_common_map_diagnostics(missing_map_df)

    assert filtered_df["esto_flow"].tolist() == [
        "09.01.01 Electricity plants",
        "16.09 Other sources",
    ]


def test_component_relevance_uses_esto_base_year_ninth_projections_and_leap_balances() -> None:
    source_df = pd.DataFrame(
        [
            {"source_system": "ESTO", "year": 2022, "esto_flow": "F1", "esto_product": "P1", "value": 5},
            {"source_system": "ESTO", "year": 2023, "esto_flow": "F1", "esto_product": "P1", "value": 0},
            {"source_system": "ESTO", "year": 2023, "esto_flow": "F2", "esto_product": "P2", "value": 2},
            {"source_system": "NINTH", "year": 2022, "esto_flow": "F3", "esto_product": "P3", "value": 3},
            {"source_system": "NINTH", "year": 2024, "esto_flow": "F4", "esto_product": "P4", "value": -4},
            {"source_system": "LEAP", "year": 2060, "esto_flow": "F5", "esto_product": "P5", "value": 1},
        ]
    )

    relevance_df, base_year = build_component_relevance(
        source_df=source_df,
        active_component_abs_tolerance=0,
        ninth_projection_start_year=2023,
    )

    assert base_year == 2023
    assert set(zip(relevance_df["component_esto_flow"], relevance_df["component_esto_product"])) == {
        ("F2", "P2"),
        ("F4", "P4"),
        ("F5", "P5"),
    }
    reasons = relevance_df.set_index("component_esto_flow")["relevance_reasons"].to_dict()
    assert reasons == {
        "F2": "esto_base_year_nonzero",
        "F4": "ninth_projection_nonzero",
        "F5": "mapped_leap_balance_nonzero",
    }
    evidence = relevance_df.set_index("component_esto_flow")
    assert evidence.loc["F2", "esto_base_year"] == 2023
    assert evidence.loc["F2", "esto_base_year_nonzero_row_count"] == 1
    assert evidence.loc["F2", "esto_base_year_abs_sum"] == 2
    assert evidence.loc["F4", "ninth_projection_first_nonzero_year"] == 2024
    assert evidence.loc["F4", "ninth_projection_max_abs_value"] == 4


def test_partial_coverage_keeps_only_missing_pairs_with_relevance_evidence() -> None:
    structural_df = pd.DataFrame(
        [
            {
                "comparison_scope": "leap_vs_ninth",
                "use_case": "leap_to_esto_balance_conversion",
                "source_system": "LEAP",
                "common_row_id": "common_1",
                "missing_component_pairs": "F1 :: P1|F2 :: P2",
                "qa_status": "unresolved_partial_component_coverage",
                "qa_severity": "high",
            }
        ]
    )
    relevance_df = pd.DataFrame(
        [
            {
                "component_esto_flow": "F2",
                "component_esto_product": "P2",
                "relevance_reasons": "ninth_projection_nonzero",
            }
        ]
    )

    actionable_df, inactive_df = filter_partial_coverage_by_relevance(structural_df, relevance_df)

    assert actionable_df.loc[0, "missing_component_pairs"] == "F2 :: P2"
    assert actionable_df.loc[0, "structural_missing_component_pairs"] == "F1 :: P1|F2 :: P2"
    assert actionable_df.loc[0, "relevant_missing_component_count"] == 1
    assert actionable_df.loc[0, "missing_component_esto_flow"] == "F2"
    assert actionable_df.loc[0, "missing_component_esto_product"] == "P2"
    assert actionable_df.loc[0, "mapping_sheet_to_review"] == "leap_combined_esto"
    assert not actionable_df.loc[0, "target_flow_looks_aggregate"]
    assert actionable_df.loc[0, "mapping_review_priority"] == "review_mapping_candidate"
    assert inactive_df.loc[0, "inactive_component_esto_flow"] == "F1"
    assert inactive_df.loc[0, "inactive_component_esto_product"] == "P1"
    assert inactive_df.loc[0, "qa_status"] == "partial_coverage_component_without_relevance"
    assert inactive_df.loc[0, "qa_severity"] == "info"


def test_nonzero_unmapped_leap_branch_can_infer_relevance_through_ninth_crosswalk() -> None:
    raw_leap_df = pd.DataFrame(
        [
            {"leap_flow": "Branch", "leap_product": "Fuel", "value": 4},
            {"leap_flow": "Unresolved", "leap_product": "Fuel", "value": 2},
            {"leap_flow": "Zero", "leap_product": "Fuel", "value": 0},
        ]
    )
    leap_esto_df = pd.DataFrame(
        columns=["leap_sector_name_full_path", "raw_leap_fuel_name"]
    )
    leap_ninth_df = pd.DataFrame(
        [
            {
                "leap_sector_name_full_path": "Branch",
                "raw_leap_fuel_name": "Fuel",
                "ninth_sector": "N1",
                "ninth_fuel": "NF1",
            }
        ]
    )
    ninth_esto_df = pd.DataFrame(
        [
            {
                "9th_sector": "N1",
                "9th_fuel": "NF1",
                "esto_flow": "F1",
                "esto_product": "P1",
            }
        ]
    )

    audit_df, relevance_df = build_unmapped_leap_branch_evidence(
        raw_leap_df=raw_leap_df,
        leap_esto_df=leap_esto_df,
        leap_ninth_df=leap_ninth_df,
        ninth_esto_df=ninth_esto_df,
        active_component_abs_tolerance=0,
    )

    statuses = audit_df.set_index("leap_flow")["qa_status"].to_dict()
    assert statuses == {
        "Branch": "nonzero_unmapped_leap_branch_with_indirect_esto_pair",
        "Unresolved": "nonzero_unmapped_leap_branch_without_esto_pair",
    }
    assert relevance_df.to_dict("records") == [
        {
            "component_esto_flow": "F1",
            "component_esto_product": "P1",
            "unmapped_leap_balance_nonzero": True,
            "unmapped_leap_branch_count": 1,
        }
    ]
