from pathlib import Path

import pandas as pd
import pytest

from codebase.mapping_tools.build_energy_balance_relationships import (
    SHEET_CONFIGS,
    USE_CASES,
)
from codebase.mapping_tools.dataset_registry import DATASET_REGISTRY_PATH
from codebase.mapping_tools.mapping_sheet_registry import (
    MAPPING_SHEET_REGISTRY_PATH,
    build_mapping_sheet_configs,
    load_mapping_sheet_registry,
)


EXPECTED_SHEET_CONFIGS = [
    {
        "sheet_name": "leap_combined_esto",
        "source_system": "LEAP",
        "target_system": "ESTO",
        "source_flow_candidates": ["leap_sector_name_full_path"],
        "source_product_candidates": ["raw_leap_fuel_name"],
        "target_flow_candidates": ["esto_flow"],
        "target_product_candidates": ["esto_product"],
        "use_cases": ["leap_to_esto_balance_conversion", "mapping_review"],
    },
    {
        "sheet_name": "ninth_pairs_to_esto_pairs",
        "source_system": "NINTH",
        "target_system": "ESTO",
        "source_flow_candidates": ["ninth_sector", "ninth_sector"],
        "source_product_candidates": ["ninth_fuel", "ninth_fuel"],
        "target_flow_candidates": ["esto_flow"],
        "target_product_candidates": ["esto_product"],
        "use_cases": ["ninth_to_esto_balance_conversion", "mapping_review"],
    },
    {
        "sheet_name": "leap_combined_ninth",
        "source_system": "LEAP",
        "target_system": "NINTH",
        "source_flow_candidates": ["leap_sector_name_full_path"],
        "source_product_candidates": ["raw_leap_fuel_name"],
        "target_flow_candidates": ["ninth_sector"],
        "target_product_candidates": ["ninth_fuel"],
        "use_cases": ["leap_to_ninth_comparison", "mapping_review"],
    },
]


def test_bundled_mapping_sheet_registry_preserves_legacy_configs() -> None:
    assert build_mapping_sheet_configs(known_use_cases=USE_CASES) == (
        EXPECTED_SHEET_CONFIGS
    )
    assert SHEET_CONFIGS == EXPECTED_SHEET_CONFIGS


def test_mapping_sheet_registry_rejects_unknown_dataset(
    tmp_path: Path,
) -> None:
    frame = pd.read_csv(
        MAPPING_SHEET_REGISTRY_PATH,
        dtype=str,
        keep_default_na=False,
    )
    frame.loc[0, "source_dataset_id"] = "UNREGISTERED"
    path = tmp_path / "mapping_sheet_registry.csv"
    frame.to_csv(path, index=False)

    with pytest.raises(ValueError, match="unknown dataset references"):
        load_mapping_sheet_registry(
            registry_path=path,
            dataset_registry_path=DATASET_REGISTRY_PATH,
            known_use_cases=USE_CASES,
        )


def test_mapping_sheet_registry_rejects_unknown_use_case(
    tmp_path: Path,
) -> None:
    frame = pd.read_csv(
        MAPPING_SHEET_REGISTRY_PATH,
        dtype=str,
        keep_default_na=False,
    )
    frame.loc[0, "use_cases"] = "not_a_real_use_case"
    path = tmp_path / "mapping_sheet_registry.csv"
    frame.to_csv(path, index=False)

    with pytest.raises(ValueError, match="unknown use_cases"):
        load_mapping_sheet_registry(
            registry_path=path,
            dataset_registry_path=DATASET_REGISTRY_PATH,
            known_use_cases=USE_CASES,
        )
