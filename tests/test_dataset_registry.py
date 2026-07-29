from pathlib import Path

import pandas as pd
import pytest

from codebase.mapping_tools.dataset_registry import (
    COMPARISON_SCOPE_REGISTRY_PATH,
    DATASET_REGISTRY_PATH,
    build_comparison_scope_configs,
    get_comparison_scope_systems,
    get_default_enabled_comparison_scopes,
    load_comparison_scope_registry,
    load_dataset_registry,
)
from codebase.mapping_tools.hierarchy_subtotal_adapters import (
    current_adapter_registry,
)


EXPECTED_SCOPE_CONFIGS = {
    "esto_leap_ninth": {
        "systems": ["ESTO", "LEAP", "NINTH"],
        "use_cases": [
            "leap_to_esto_balance_conversion",
            "ninth_to_esto_balance_conversion",
        ],
        "aggregate_source_systems": ["LEAP", "NINTH"],
    },
    "esto_leap": {
        "systems": ["ESTO", "LEAP"],
        "use_cases": ["leap_to_esto_balance_conversion"],
        "aggregate_source_systems": ["LEAP"],
    },
    "esto_extended_leap": {
        "systems": ["ESTO_EXTENDED", "LEAP"],
        "use_cases": ["leap_to_esto_balance_conversion"],
        "aggregate_source_systems": ["LEAP"],
    },
    "leap_vs_ninth": {
        "systems": ["LEAP", "NINTH"],
        "use_cases": ["ninth_to_esto_balance_conversion"],
        "aggregate_source_systems": ["NINTH"],
    },
    "esto_only": {
        "systems": ["ESTO"],
        "use_cases": [
            "leap_to_esto_balance_conversion",
            "ninth_to_esto_balance_conversion",
        ],
        "aggregate_source_systems": ["LEAP", "NINTH"],
    },
    "esto_extended_leap_ninth": {
        "systems": ["ESTO_EXTENDED", "LEAP", "NINTH"],
        "use_cases": [
            "leap_to_esto_balance_conversion",
            "ninth_to_esto_balance_conversion",
        ],
        "aggregate_source_systems": ["LEAP", "NINTH"],
    },
}


def test_bundled_registries_preserve_current_behavior() -> None:
    datasets = load_dataset_registry()

    assert datasets["dataset_id"].tolist() == [
        "ESTO",
        "ESTO_EXTENDED",
        "NINTH",
        "LEAP",
        "COMMON_ESTO",
        "SYNTH_BALANCE",
    ]
    assert datasets.set_index("dataset_id").loc["SYNTH_BALANCE", "enabled"] == False
    assert datasets.loc[
        datasets["dataset_id"].ne("SYNTH_BALANCE"), "enabled"
    ].all()
    assert build_comparison_scope_configs() == EXPECTED_SCOPE_CONFIGS
    assert get_default_enabled_comparison_scopes() == [
        "esto_leap",
        "esto_extended_leap",
        "esto_leap_ninth",
        "esto_extended_leap_ninth",
    ]
    assert get_comparison_scope_systems() == {
        scope: set(config["systems"])
        for scope, config in EXPECTED_SCOPE_CONFIGS.items()
    }


def test_hierarchy_registry_keeps_existing_adapter_order() -> None:
    repo_root = DATASET_REGISTRY_PATH.parents[2]
    adapters = current_adapter_registry(
        repo_root=repo_root,
        workbook_path=repo_root / "config" / "outlook_mappings_master.xlsx",
    )

    assert [adapter.dataset_id for adapter in adapters] == [
        "esto",
        "ninth",
        "leap",
        "esto_extended",
        "common_esto",
    ]


def test_dataset_registry_rejects_unknown_canonical_target(
    tmp_path: Path,
) -> None:
    datasets = pd.read_csv(DATASET_REGISTRY_PATH, dtype=str, keep_default_na=False)
    datasets.loc[datasets["dataset_id"].eq("LEAP"), "canonical_target_dataset_id"] = (
        "MISSING"
    )
    registry_path = tmp_path / "dataset_registry.csv"
    datasets.to_csv(registry_path, index=False)

    with pytest.raises(ValueError, match="unknown datasets.*MISSING"):
        load_dataset_registry(registry_path)


def test_scope_registry_rejects_unknown_dataset_reference(
    tmp_path: Path,
) -> None:
    scopes = pd.read_csv(
        COMPARISON_SCOPE_REGISTRY_PATH,
        dtype=str,
        keep_default_na=False,
    )
    scopes.loc[
        scopes["comparison_scope"].eq("esto_leap"),
        "included_dataset_ids",
    ] = "ESTO|UNREGISTERED"
    registry_path = tmp_path / "comparison_scopes.csv"
    scopes.to_csv(registry_path, index=False)

    with pytest.raises(ValueError, match="unknown dataset references.*UNREGISTERED"):
        load_comparison_scope_registry(
            registry_path=registry_path,
            dataset_registry_path=DATASET_REGISTRY_PATH,
        )


def test_scope_registry_rejects_implicit_boolean(tmp_path: Path) -> None:
    scopes = pd.read_csv(
        COMPARISON_SCOPE_REGISTRY_PATH,
        dtype=str,
        keep_default_na=False,
    )
    scopes.loc[0, "enabled"] = "sometimes"
    registry_path = tmp_path / "comparison_scopes.csv"
    scopes.to_csv(registry_path, index=False)

    with pytest.raises(ValueError, match="enabled must be an explicit Boolean"):
        load_comparison_scope_registry(
            registry_path=registry_path,
            dataset_registry_path=DATASET_REGISTRY_PATH,
        )
