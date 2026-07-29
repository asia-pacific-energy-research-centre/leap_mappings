#%%
"""Tests for registered source-specific Stage 3 diagnostics."""

#%%
from pathlib import Path

import pandas as pd
import pytest

from codebase.mapping_tools.diagnostic_adapter_registry import (
    load_diagnostic_adapter_registry,
    run_registered_diagnostic_adapters,
)


def test_default_diagnostic_registry_exposes_indirect_chain_adapter() -> None:
    registry = load_diagnostic_adapter_registry()

    enabled = registry[registry["enabled"]]
    assert enabled[
        ["diagnostic_id", "adapter_name", "source_dataset_id"]
    ].to_dict("records") == [
        {
            "diagnostic_id": "unmapped_source_indirect_chain",
            "adapter_name": "unmapped_indirect_chain",
            "source_dataset_id": "LEAP",
        }
    ]
    row = enabled.iloc[0]
    assert row["direct_mapping_sheet"] == "leap_combined_esto"
    assert row["bridge_mapping_sheet"] == "leap_combined_ninth"
    assert row["bridge_target_mapping_sheet"] == "ninth_pairs_to_esto_pairs"


def test_registered_diagnostic_runner_uses_registry_order() -> None:
    observed: list[str] = []

    results = run_registered_diagnostic_adapters(
        adapter_runners={
            "unmapped_indirect_chain": lambda row: observed.append(
                row["diagnostic_id"]
            )
            or {"status": "ran"}
        }
    )

    assert observed == ["unmapped_source_indirect_chain"]
    assert results == {
        "unmapped_source_indirect_chain": {"status": "ran"}
    }


def test_diagnostic_registry_rejects_unknown_mapping_sheet(
    tmp_path: Path,
) -> None:
    registry = load_diagnostic_adapter_registry()
    registry["enabled"] = registry["enabled"].map(
        {True: "true", False: "false"}
    )
    registry.loc[
        registry["diagnostic_id"].eq("unmapped_source_indirect_chain"),
        "direct_mapping_sheet",
    ] = "missing_sheet"
    registry_path = tmp_path / "diagnostic_adapter_registry.csv"
    registry.to_csv(registry_path, index=False)

    with pytest.raises(ValueError, match="unknown mapping sheet"):
        load_diagnostic_adapter_registry(registry_path=registry_path)


def test_disabled_diagnostic_does_not_invoke_runner(
    tmp_path: Path,
) -> None:
    registry = load_diagnostic_adapter_registry()
    registry["enabled"] = "false"
    registry_path = tmp_path / "diagnostic_adapter_registry.csv"
    registry.to_csv(registry_path, index=False)
    observed: list[str] = []

    results = run_registered_diagnostic_adapters(
        adapter_runners={
            "unmapped_indirect_chain": lambda row: observed.append(
                row["diagnostic_id"]
            )
        },
        registry_path=registry_path,
    )

    assert results == {}
    assert observed == []


#%%
