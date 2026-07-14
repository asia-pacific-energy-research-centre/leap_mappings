import pandas as pd

from codebase.mapping_tools.apply_common_esto_structure import apply_common_structure
from codebase.mapping_tools.build_common_esto_structure import build_common_rows


def test_source_aggregate_membership_links_separate_parent_and_rollup_rows() -> None:
    parent_pair = ("09 Total transformation sector", "09 Nuclear")
    detail_pair = ("09.01.01 Electricity plants", "09 Nuclear")
    components_by_root = {
        parent_pair: [parent_pair],
        detail_pair: [detail_pair],
    }
    aggregate_groups_df = pd.DataFrame(
        [
            {
                "source_flow": "Total transformation - no transfers",
                "aggregate_group_source": "LEAP",
                "aggregate_group_source_id": "rollup_total_transformation_nuclear",
                "aggregation_reason": "leap_defined_aggregate",
                "component_pairs": (
                    "09 Total transformation sector :: 09 Nuclear|"
                    "09.01.01 Electricity plants :: 09 Nuclear"
                ),
            }
        ]
    )

    common_rows = build_common_rows(
        components_by_root=components_by_root,
        aggregate_groups_df=aggregate_groups_df,
        label_overrides_df=pd.DataFrame(),
        flow_code_to_name={"09": "Total transformation sector"},
        product_code_to_name={"09": "Nuclear"},
        comparison_scope="esto_leap_ninth",
    )

    assert set(common_rows["source_aggregate_labels"]) == {
        "Total transformation - no transfers"
    }
    assert set(common_rows["source_aggregate_group_ids"]) == {
        "rollup_total_transformation_nuclear"
    }


def test_stage3_output_preserves_common_row_identity_and_aggregate_membership() -> None:
    source_df = pd.DataFrame(
        [
            {
                "source_system": "LEAP",
                "economy": "20_USA",
                "scenario": "Target",
                "year": 2060,
                "esto_flow": "09.01.01 Electricity plants",
                "esto_product": "09 Nuclear",
                "value": -10.0,
            }
        ]
    )
    common_rows_df = pd.DataFrame(
        [
            {
                "comparison_scope": "esto_leap_ninth",
                "component_esto_flow": "09.01.01 Electricity plants",
                "component_esto_product": "09 Nuclear",
                "common_row_id": "common_rollup_nuclear",
                "common_flow_code": "09.01.01",
                "common_flow_name": "Electricity plants",
                "common_flow_label": "09.01.01 Electricity plants",
                "common_product_code": "09",
                "common_product_name": "Nuclear",
                "common_product_label": "09 Nuclear",
                "component_sign": 1,
                "common_row_basis": "connected_component_rollup",
                "is_exact_row": False,
                "requires_rollup": True,
                "source_aggregate_labels": "Total transformation - no transfers",
                "source_aggregate_group_ids": "rollup_total_transformation_nuclear",
            }
        ]
    )

    comparison_df, missing_map_df, _ = apply_common_structure(source_df, common_rows_df)

    assert missing_map_df.empty
    row = comparison_df.iloc[0]
    assert row["common_row_id"] == "common_rollup_nuclear"
    assert row["common_row_basis"] == "connected_component_rollup"
    assert bool(row["requires_rollup"])
    assert row["source_aggregate_labels"] == "Total transformation - no transfers"
