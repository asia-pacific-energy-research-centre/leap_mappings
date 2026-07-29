from pathlib import Path

import pandas as pd
import pytest

from codebase.mapping_tools.non_expanding_rollups import ROLLUP_SHEET_CONFIGS
from codebase.mapping_tools.rollup_sheet_registry import (
    NORMALIZED_ROLLUP_COLUMNS,
    ROLLUP_SHEET_REGISTRY_PATH,
    build_rollup_sheet_configs,
    compile_normalized_rollup_rules,
    load_rollup_sheet_registry,
)


EXPECTED_CONFIGS = {
    "leap_rollup_rules": {
        "source_system": "LEAP",
        "input_flow": "input_leap_sector_name_full_path",
        "input_product": "input_raw_leap_fuel_name",
        "rolled_flow": "rolled_leap_sector_name_full_path",
        "rolled_product": "rolled_raw_leap_fuel_name",
    },
    "esto_rollup_rules": {
        "source_system": "ESTO",
        "input_flow": "input_esto_flow",
        "input_product": "input_esto_product",
        "rolled_flow": "rolled_esto_flow",
        "rolled_product": "rolled_esto_product",
    },
    "ninth_rollup_rules": {
        "source_system": "NINTH",
        "input_flow": "input_ninth_sector",
        "input_product": "input_ninth_fuel",
        "rolled_flow": "rolled_ninth_sector",
        "rolled_product": "rolled_ninth_fuel",
    },
}


def test_bundled_rollup_registry_preserves_legacy_config() -> None:
    assert build_rollup_sheet_configs() == EXPECTED_CONFIGS
    assert ROLLUP_SHEET_CONFIGS == EXPECTED_CONFIGS


def test_compile_normalized_rollups_from_all_registered_sheets(
    tmp_path: Path,
) -> None:
    workbook = tmp_path / "rules.xlsx"
    with pd.ExcelWriter(workbook) as writer:
        pd.DataFrame([{
            "include": True,
            "input_leap_sector_name_full_path": "Demand\\A",
            "input_raw_leap_fuel_name": "Fuel",
            "rolled_leap_sector_name_full_path": "Demand",
            "rolled_raw_leap_fuel_name": "Fuel",
            "ROLLUP_MODE": "EXPANDING",
        }]).to_excel(writer, sheet_name="leap_rollup_rules", index=False)
        pd.DataFrame([{
            "include": True,
            "input_esto_flow": "Flow A",
            "input_esto_product": "Product",
            "rolled_esto_flow": "Flow parent",
            "rolled_esto_product": "Product",
            "ROLLUP_MODE": "NON_EXPANDING",
        }]).to_excel(writer, sheet_name="esto_rollup_rules", index=False)
        pd.DataFrame([{
            "include": True,
            "input_ninth_sector": "Sector A",
            "input_ninth_fuel": "Fuel",
            "rolled_ninth_sector": "Sector parent",
            "rolled_ninth_fuel": "Fuel",
            "ROLLUP_MODE": "DETACHED",
        }]).to_excel(writer, sheet_name="ninth_rollup_rules", index=False)

    compiled = compile_normalized_rollup_rules(workbook)

    assert compiled.columns.tolist() == NORMALIZED_ROLLUP_COLUMNS
    assert compiled["dataset_id"].tolist() == ["LEAP", "ESTO", "NINTH"]
    assert compiled["rollup_mode"].tolist() == [
        "EXPANDING",
        "NON_EXPANDING",
        "DETACHED",
    ]
    assert compiled["source_row_number"].tolist() == [2, 2, 2]


def test_rollup_registry_rejects_unknown_dataset(tmp_path: Path) -> None:
    frame = pd.read_csv(
        ROLLUP_SHEET_REGISTRY_PATH,
        dtype=str,
        keep_default_na=False,
    )
    frame.loc[0, "dataset_id"] = "UNREGISTERED"
    path = tmp_path / "rollup_sheet_registry.csv"
    frame.to_csv(path, index=False)

    with pytest.raises(ValueError, match="unknown dataset reference"):
        load_rollup_sheet_registry(registry_path=path)
