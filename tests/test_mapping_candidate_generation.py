import pandas as pd

from codebase.mapping_tools.mapping_candidate_generation import (
    generate_partial_coverage_candidates_for_system,
    generate_unmapped_leap_branch_candidates,
    select_highly_recommended_candidates,
)


def test_partial_candidate_combines_independent_branch_and_fuel_axes() -> None:
    issues_df = pd.DataFrame(
        [
            {
                "comparison_scope": "leap_vs_ninth",
                "use_case": "leap_to_esto_balance_conversion",
                "source_system": "LEAP",
                "common_row_id": "common_1",
                "missing_component_esto_flow": "Target flow",
                "missing_component_esto_product": "Target product",
            }
        ]
    )
    mapping_df = pd.DataFrame(
        [
            {
                "leap_sector_name_full_path": "Target branch",
                "raw_leap_fuel_name": "Other fuel",
                "esto_flow": "Target flow",
                "esto_product": "Other product",
            },
            {
                "leap_sector_name_full_path": "Other branch",
                "raw_leap_fuel_name": "Target fuel",
                "esto_flow": "Other flow",
                "esto_product": "Target product",
            },
        ]
    )
    active_pairs_df = pd.DataFrame(
        [
            {
                "source_flow": "Target branch",
                "source_product": "Target fuel",
                "source_nonzero_row_count": 3,
                "source_nonzero_economy_count": 1,
                "source_abs_sum": 12,
            }
        ]
    )

    candidates_df = generate_partial_coverage_candidates_for_system(
        issues_df=issues_df,
        active_source_pairs_df=active_pairs_df,
        mapping_df=mapping_df,
        source_flow_column="leap_sector_name_full_path",
        source_product_column="raw_leap_fuel_name",
        mapping_sheet="leap_combined_esto",
        max_candidates_per_issue=5,
    )

    candidate = candidates_df.iloc[0]
    assert candidate["candidate_status"] == "proposed"
    assert candidate["leap_sector_name_full_path"] == "Target branch"
    assert candidate["raw_leap_fuel_name"] == "Target fuel"
    assert candidate["esto_flow"] == "Target flow"
    assert candidate["esto_product"] == "Target product"
    assert candidate["source_pair_nonzero"]
    assert candidate["computer_generated_review_only"]


def test_unmapped_leap_candidate_uses_collapsed_branch_and_exact_fuel_profiles() -> None:
    audit_df = pd.DataFrame(
        [
            {
                "leap_flow": "Blast furnaces",
                "leap_product": "Natural gas",
                "indirect_esto_flow": "",
                "indirect_esto_product": "",
            }
        ]
    )
    mapping_df = pd.DataFrame(
        [
            {
                "leap_sector_name_full_path": "Blast furnaces/Blast furnaces",
                "raw_leap_fuel_name": "Coal",
                "esto_flow": "09.06 Blast furnaces",
                "esto_product": "01 Coal",
            },
            {
                "leap_sector_name_full_path": "Other process",
                "raw_leap_fuel_name": "Natural gas",
                "esto_flow": "09.99 Other",
                "esto_product": "08 Natural gas",
            },
        ]
    )

    candidates_df = generate_unmapped_leap_branch_candidates(audit_df, mapping_df)

    candidate = candidates_df.iloc[0]
    assert candidate["candidate_status"] == "proposed"
    assert candidate["flow_axis_match_method"] == "collapsed_branch_path"
    assert candidate["product_axis_match_method"] == "exact_fuel_profile"
    assert candidate["esto_flow"] == "09.06 Blast furnaces"
    assert candidate["esto_product"] == "08 Natural gas"


def test_partial_candidate_explains_when_axes_exist_but_no_observed_pair_combines_them() -> None:
    issues_df = pd.DataFrame(
        [
            {
                "comparison_scope": "leap_vs_ninth",
                "use_case": "leap_to_esto_balance_conversion",
                "source_system": "LEAP",
                "common_row_id": "common_2",
                "missing_component_esto_flow": "Target flow",
                "missing_component_esto_product": "Target product",
            }
        ]
    )
    mapping_df = pd.DataFrame(
        [
            {
                "leap_sector_name_full_path": "Target branch",
                "raw_leap_fuel_name": "Other fuel",
                "esto_flow": "Target flow",
                "esto_product": "Other product",
            },
            {
                "leap_sector_name_full_path": "Other branch",
                "raw_leap_fuel_name": "Target fuel",
                "esto_flow": "Other flow",
                "esto_product": "Target product",
            },
        ]
    )
    active_pairs_df = pd.DataFrame(
        [
            {
                "source_flow": "Target branch",
                "source_product": "Other fuel",
                "source_nonzero_row_count": 1,
                "source_nonzero_economy_count": 1,
                "source_abs_sum": 2,
            },
            {
                "source_flow": "Other branch",
                "source_product": "Target fuel",
                "source_nonzero_row_count": 1,
                "source_nonzero_economy_count": 1,
                "source_abs_sum": 3,
            },
        ]
    )

    candidates_df = generate_partial_coverage_candidates_for_system(
        issues_df=issues_df,
        active_source_pairs_df=active_pairs_df,
        mapping_df=mapping_df,
        source_flow_column="leap_sector_name_full_path",
        source_product_column="raw_leap_fuel_name",
        mapping_sheet="leap_combined_esto",
        max_candidates_per_issue=5,
    )

    candidate = candidates_df.iloc[0]
    assert candidate["candidate_status"] == "no_observed_source_pair_matches_both_axes"
    assert candidate["missing_axis_evidence"] == "no_nonzero_source_pair_combines_the_two_axes"
    assert "Target branch" in candidate["flow_axis_alternatives"]
    assert "Target fuel" in candidate["product_axis_alternatives"]


def test_highly_recommended_output_excludes_incomplete_and_medium_candidates() -> None:
    candidate_df = pd.DataFrame(
        [
            {
                "candidate_status": "proposed",
                "candidate_confidence": "high",
                "mapping_sheet": "leap_combined_esto",
                "leap_sector_name_full_path": "Branch",
                "raw_leap_fuel_name": "Fuel",
                "esto_flow": "Flow",
                "esto_product": "Product",
                "source_pair_nonzero": True,
                "candidate_would_add_another_target": False,
            },
            {
                "candidate_status": "proposed",
                "candidate_confidence": "medium",
                "mapping_sheet": "leap_combined_esto",
                "leap_sector_name_full_path": "Ambiguous branch",
                "raw_leap_fuel_name": "Fuel",
                "esto_flow": "Flow",
                "esto_product": "Product",
                "source_pair_nonzero": True,
                "candidate_would_add_another_target": False,
            },
            {
                "candidate_status": "insufficient_axis_evidence",
                "candidate_confidence": "none",
                "mapping_sheet": "leap_combined_esto",
                "leap_sector_name_full_path": "Incomplete branch",
                "raw_leap_fuel_name": "Fuel",
                "esto_flow": "",
                "esto_product": "Product",
                "source_pair_nonzero": True,
                "candidate_would_add_another_target": False,
            },
        ]
    )

    recommended_df = select_highly_recommended_candidates(candidate_df)

    assert len(recommended_df) == 1
    assert recommended_df.loc[0, "candidate_status"] == "highly_recommended_copy_ready"
    assert recommended_df.loc[0, "paste_ready"]
    assert recommended_df.loc[0, "derived_from_existing_axis_mappings"]
    assert "leap_combined_esto" in recommended_df.loc[0, "paste_instruction"]
