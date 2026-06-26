import pandas as pd

from codebase.mapping_tools.apply_common_esto_structure import (
    filter_missing_common_map_diagnostics,
    should_ignore_missing_common_map_flow,
)


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
