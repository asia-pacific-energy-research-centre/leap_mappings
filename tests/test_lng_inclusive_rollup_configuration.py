#%%
"""Regression checks for the signed LEAP LNG inclusive comparison boundary."""

from pathlib import Path

import pandas as pd
import pytest

from codebase.mapping_tools.convert_leap_results_to_esto import (
    convert_leap_results_to_esto,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKBOOK_PATH = REPO_ROOT / "config" / "outlook_mappings_single_axis.xlsx"
LNG_OWN_USE_SOURCE = (
    "Other loss and own use/Liquefaction and regasification plants"
)
LNG_INCLUSIVE_FLOW = "Liquefaction/regasification plants"
GAS_PROCESSING_INCLUSIVE_FLOW = "Gas processing plants"


def _load_rollup_rules() -> pd.DataFrame:
    return pd.read_excel(
        WORKBOOK_PATH,
        sheet_name="leap_rollup_rules",
        dtype=object,
    ).fillna("")


def test_lng_own_use_is_a_negative_contributor_to_both_inclusive_boundaries() -> None:
    rules = _load_rollup_rules()
    lng_rules = rules[
        rules["input_leap_sector_name_full_path"].eq(LNG_OWN_USE_SOURCE)
        & rules["rolled_leap_sector_name_full_path"].isin(
            [LNG_INCLUSIVE_FLOW, GAS_PROCESSING_INCLUSIVE_FLOW]
        )
    ]

    assert set(lng_rules["rolled_leap_sector_name_full_path"]) == {
        LNG_INCLUSIVE_FLOW,
        GAS_PROCESSING_INCLUSIVE_FLOW,
    }
    assert pd.to_numeric(lng_rules["input_value_multiplier"]).tolist() == [-1, -1]
    assert lng_rules["input_raw_leap_fuel_name"].eq("").all()
    assert lng_rules["rolled_raw_leap_fuel_name"].eq("").all()
    assert lng_rules["ROLLUP_MODE"].eq("NON_EXPANDING").all()


def test_lng_inclusive_conversion_adds_signed_demand_proxy_by_product() -> None:
    relationships = []
    for product in ["Natural gas", "LNG", "Electricity"]:
        relationships.append({
            "source_system": "LEAP",
            "source_flow": LNG_INCLUSIVE_FLOW,
            "source_product": product,
            "target_system": "ESTO",
            "target_flow": "09.06.02 Liquefaction/regasification plants",
            "target_product": {
                "Natural gas": "08.01 Natural gas",
                "LNG": "08.02 LNG",
                "Electricity": "17 Electricity",
            }[product],
            "relationship_id": f"rolled-{product}",
            "allocation_method": "direct",
            "relationship_type": "direct_or_existing_mapping",
        })
    for product in ["Natural gas", "Electricity"]:
        relationships.append({
            "source_system": "LEAP",
            "source_flow": LNG_OWN_USE_SOURCE,
            "source_product": product,
            "target_system": "ESTO",
            "target_flow": "10.01.03 Liquefaction/regasification plants",
            "target_product": {
                "Natural gas": "08.01 Natural gas",
                "Electricity": "17 Electricity",
            }[product],
            "relationship_id": f"own-use-{product}",
            "allocation_method": "direct",
            "relationship_type": "own_use_or_losses",
        })

    source_values = {
        ("NG Liquefaction", "Natural gas"): -4218.807364,
        ("NG Liquefaction", "LNG"): 4218.807364,
        ("NG Liquefaction", "Electricity"): 0.0,
        ("LNG regasification", "Natural gas"): 0.0,
        ("LNG regasification", "LNG"): 0.0,
        ("LNG regasification", "Electricity"): 0.0,
        (LNG_OWN_USE_SOURCE, "Natural gas"): 308.346802,
        (LNG_OWN_USE_SOURCE, "Electricity"): 28.073591,
    }
    leap_results = pd.DataFrame([
        {
            "economy": "01_AUS",
            "scenario": "Target",
            "year": 2023,
            "leap_flow": flow,
            "leap_product": product,
            "value": value,
        }
        for (flow, product), value in source_values.items()
    ])

    converted = convert_leap_results_to_esto(
        leap_results,
        pd.DataFrame(relationships),
        rollup_rules_df=_load_rollup_rules(),
    )
    inclusive = converted[
        converted["target_flow"].eq(
            "09.06.02 Liquefaction/regasification plants"
        )
    ].set_index("target_product")["value"]
    own_use = converted[
        converted["target_flow"].eq(
            "10.01.03 Liquefaction/regasification plants"
        )
    ].set_index("target_product")["value"]

    assert inclusive["08.01 Natural gas"] == pytest.approx(-4527.154166)
    assert inclusive["08.02 LNG"] == pytest.approx(4218.807364)
    assert inclusive["17 Electricity"] == pytest.approx(-28.073591)
    assert inclusive.sum() == pytest.approx(-336.420393)
    assert own_use["08.01 Natural gas"] == pytest.approx(-308.346802)
    assert own_use["17 Electricity"] == pytest.approx(-28.073591)


#%%
