#%%
"""Configuration checks for the signed LEAP international-transport boundary."""

from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKBOOK_PATH = REPO_ROOT / "config" / "outlook_mappings_single_axis.xlsx"


def test_leap_tpes_rollup_subtracts_international_transport() -> None:
    rules = pd.read_excel(WORKBOOK_PATH, sheet_name="leap_rollup_rules", dtype=object).fillna("")
    tpes_label = "Total Primary Supply including international transport adjustment"
    tpes_rules = rules[rules["rolled_leap_sector_name_full_path"].eq(tpes_label)]

    assert dict(zip(
        tpes_rules["input_leap_sector_name_full_path"],
        pd.to_numeric(tpes_rules["input_value_multiplier"]),
    )) == {
        "Total Primary Supply": 1,
        "All demand aggregated/International transport": -1,
    }


def test_leap_international_transport_is_published_as_signed_supply() -> None:
    rules = pd.read_excel(WORKBOOK_PATH, sheet_name="leap_rollup_rules", dtype=object).fillna("")
    sector_map = pd.read_excel(WORKBOOK_PATH, sheet_name="leap_sector_to_esto", dtype=object).fillna("")
    bunker_label = "International transport signed for supply"
    bunker_rules = rules[rules["rolled_leap_sector_name_full_path"].eq(bunker_label)]

    assert bunker_rules["input_leap_sector_name_full_path"].tolist() == [
        "All demand aggregated/International transport"
    ]
    assert pd.to_numeric(bunker_rules["input_value_multiplier"]).tolist() == [-1]
    mapped = sector_map[sector_map["leap_sector"].eq(bunker_label)]
    assert mapped["esto_flow"].tolist() == ["04-05 International transport (bunkers)"]
    assert not sector_map["leap_sector"].eq(
        "All demand aggregated/International transport"
    ).any()


#%%
