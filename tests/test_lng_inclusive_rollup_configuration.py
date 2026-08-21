#%%
"""Regression checks for the signed LEAP LNG inclusive comparison boundary."""

from pathlib import Path

import pandas as pd
import pytest

from codebase.mapping_tools.convert_leap_results_to_esto import (
    convert_leap_results_to_esto,
)
from codebase.mapping_tools.apply_source_to_common_esto_map import (
    apply_source_to_common_esto_map,
)
from codebase.mapping_tools.build_source_to_common_esto_map import (
    build_source_to_common_esto_map,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKBOOK_PATH = REPO_ROOT / "config" / "outlook_mappings_single_axis.xlsx"
LNG_OWN_USE_SOURCE = (
    "Other loss and own use/Liquefaction and regasification plants"
)
LNG_INCLUSIVE_FLOW = "Liquefaction/regasification plants (including own use)"
GAS_PROCESSING_INCLUSIVE_FLOW = "Gas processing plants (including own use)"
LNG_INCLUSIVE_ESTO_FLOW = (
    "09.06.02 Liquefaction/regasification plants (including own use)"
)
GAS_PROCESSING_INCLUSIVE_ESTO_FLOW = (
    "09.06 Gas processing plants (including own use)"
)


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


def test_lng_inclusive_rollups_have_consistent_esto_and_ninth_identities() -> None:
    leap_to_esto = pd.read_excel(
        WORKBOOK_PATH,
        sheet_name="leap_sector_to_esto",
        dtype=object,
    ).fillna("")
    leap_to_ninth = pd.read_excel(
        WORKBOOK_PATH,
        sheet_name="leap_sector_to_ninth",
        dtype=object,
    ).fillna("")

    assert set(
        leap_to_esto.loc[
            leap_to_esto["leap_sector"].isin(
                [LNG_INCLUSIVE_FLOW, GAS_PROCESSING_INCLUSIVE_FLOW]
            ),
            ["leap_sector", "esto_flow"],
        ].itertuples(index=False, name=None)
    ) == {
        (LNG_INCLUSIVE_FLOW, LNG_INCLUSIVE_ESTO_FLOW),
        (GAS_PROCESSING_INCLUSIVE_FLOW, GAS_PROCESSING_INCLUSIVE_ESTO_FLOW),
    }
    assert set(
        leap_to_ninth.loc[
            leap_to_ninth["leap_sector"].isin(
                [LNG_INCLUSIVE_FLOW, GAS_PROCESSING_INCLUSIVE_FLOW]
            ),
            ["leap_sector", "ninth_sector"],
        ].itertuples(index=False, name=None)
    ) == {
        (
            LNG_INCLUSIVE_FLOW,
            "09_06_02_liquefaction_regasification_plants_incl_own_use",
        ),
        (
            GAS_PROCESSING_INCLUSIVE_FLOW,
            "09_06_gas_processing_plants_incl_own_use",
        ),
    }


def test_lng_inclusive_conversion_adds_signed_demand_proxy_by_product() -> None:
    relationships = []
    for product in ["Natural gas", "LNG", "Electricity"]:
        relationships.append({
            "source_system": "LEAP",
            "source_flow": LNG_INCLUSIVE_FLOW,
            "source_product": product,
            "target_system": "ESTO",
            "target_flow": LNG_INCLUSIVE_ESTO_FLOW,
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
            LNG_INCLUSIVE_ESTO_FLOW
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


def test_lng_inclusive_leap_value_routes_to_the_inclusive_common_row(
    tmp_path: Path,
) -> None:
    relationships_path = tmp_path / "relationships.csv"
    esto_to_common_path = tmp_path / "esto_to_common.csv"
    common_row_id = "common_esto_lng_inclusive_natural_gas"

    pd.DataFrame(
        [
            {
                "relationship_id": "lng-inclusive-natural-gas",
                "source_system": "LEAP",
                "source_flow": LNG_INCLUSIVE_FLOW,
                "source_product": "Natural gas",
                "target_system": "ESTO",
                "target_flow": LNG_INCLUSIVE_ESTO_FLOW,
                "target_product": "08.01 Natural gas",
            }
        ]
    ).to_csv(relationships_path, index=False)
    pd.DataFrame(
        [
            {
                "comparison_scope": "esto_leap_ninth",
                "component_esto_flow": LNG_INCLUSIVE_ESTO_FLOW,
                "component_esto_product": "08.01 Natural gas",
                "common_row_id": common_row_id,
                "common_flow_label": LNG_INCLUSIVE_ESTO_FLOW,
                "common_product_label": "08.01 Natural gas",
            }
        ]
    ).to_csv(esto_to_common_path, index=False)

    source_map, coverage = build_source_to_common_esto_map(
        relationships_path=relationships_path,
        esto_to_common_map_path=esto_to_common_path,
    )
    assert coverage.empty

    converted = apply_source_to_common_esto_map(
        pd.DataFrame(
            [
                {
                    "source_flow": LNG_INCLUSIVE_FLOW,
                    "source_product": "Natural gas",
                    "economy": "01_AUS",
                    "scenario": "Target",
                    "year": 2023,
                    "value": -4527.154166,
                }
            ]
        ),
        source_map,
        comparison_scope="esto_leap_ninth",
        source_system="LEAP",
    )

    assert converted["common_row_id"].tolist() == [common_row_id]
    assert converted["common_flow_label"].tolist() == [LNG_INCLUSIVE_ESTO_FLOW]
    assert converted["value"].tolist() == pytest.approx([-4527.154166])


#%%
