"""Unit tests for the reusable unmodelled-source exception helpers."""

import pandas as pd

from codebase.mapping_tools.mapping_issue_exceptions import (
    excepted_code_mask,
    leading_code_number,
    unmodelled_source_pair_mask,
)


def test_leading_code_number_across_representations() -> None:
    assert leading_code_number("18 Electricity output in GWh") == 18
    assert leading_code_number("18.02 MAP CHP plants") == 18
    assert leading_code_number("06_stock_changes") == 6
    assert leading_code_number("18_electricity_output_in_gwh/18_01_electricity_plants") == 18
    assert leading_code_number("19 Total") == 19
    assert leading_code_number("Total final consumption") is None
    assert leading_code_number("") is None


def test_excepted_code_mask_matches_whole_family() -> None:
    codes = pd.Series([
        "18 Electricity output in GWh", "18.02 MAP CHP plants",
        "17 Electricity", "180 Not a match", "06 Stock changes",
    ])
    mask = excepted_code_mask(codes, {18, 6})
    assert mask.tolist() == [True, True, False, False, True]


def test_excepted_code_mask_empty_set_is_all_false() -> None:
    codes = pd.Series(["18 X", "19 Y"])
    assert excepted_code_mask(codes, set()).tolist() == [False, False]


def test_pair_mask_scopes_sector_vs_fuel() -> None:
    flows = pd.Series(["01 Production", "18 Electricity output", "01 Production"])
    products = pd.Series(["01 Coal", "01 Coal", "19 Total"])
    codes = {"sector": {18}, "fuel": {19}}
    # row0: neither; row1: sector 18; row2: fuel 19
    assert unmodelled_source_pair_mask(flows, products, codes).tolist() == [False, True, True]
    # fuel 19 must not suppress a *sector* 19 (axis-scoped)
    codes_sector_only = {"sector": {19}, "fuel": set()}
    assert unmodelled_source_pair_mask(flows, products, codes_sector_only).tolist() == [False, False, False]
