#%%
"""Registry helpers for normalized value-adapter orchestration."""

#%%
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

from codebase.mapping_tools.dataset_registry import (
    DATASET_REGISTRY_PATH,
    load_dataset_registry,
)
from codebase.mapping_tools.result_storage import prefer_compressed_csv_path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALUE_ADAPTER_REGISTRY_PATH = (
    REPO_ROOT / "config" / "datasets" / "value_adapter_registry.csv"
)
VALUE_ADAPTER_REGISTRY_COLUMNS = [
    "dataset_id",
    "enabled",
    "adapter_name",
    "execution_order",
    "input_relative_path",
    "output_relative_path",
    "stage3_source",
    "lineage_relative_path",
    "owner",
    "notes",
]


def _boolean(value: object, field: str, dataset_id: str) -> bool:
    text = str(value).strip().casefold()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise ValueError(
        f"{dataset_id}: {field} must be an explicit Boolean, got {value!r}."
    )


def load_value_adapter_registry(
    registry_path: Path = VALUE_ADAPTER_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
) -> pd.DataFrame:
    """Return validated value adapters in declared execution order."""
    frame = pd.read_csv(registry_path, dtype=str, keep_default_na=False)
    missing = [
        column
        for column in VALUE_ADAPTER_REGISTRY_COLUMNS
        if column not in frame.columns
    ]
    if missing:
        raise ValueError(f"{Path(registry_path).name} is missing columns: {missing}")
    if frame.empty:
        raise ValueError("value_adapter_registry.csv must not be empty.")
    frame = frame[VALUE_ADAPTER_REGISTRY_COLUMNS].copy()
    for column in frame:
        frame[column] = frame[column].astype(str).str.strip()
    duplicates = sorted(
        frame.loc[
            frame["dataset_id"].duplicated(keep=False), "dataset_id"
        ].unique()
    )
    if duplicates:
        raise ValueError(f"Duplicate value-adapter dataset IDs: {duplicates}")
    for column in ["enabled", "stage3_source"]:
        frame[column] = [
            _boolean(value, column, dataset_id)
            for value, dataset_id in zip(frame[column], frame["dataset_id"])
        ]
    frame["execution_order"] = pd.to_numeric(
        frame["execution_order"],
        errors="coerce",
    )
    if frame["execution_order"].isna().any():
        raise ValueError("Every value adapter requires numeric execution_order.")
    if frame["execution_order"].duplicated().any():
        raise ValueError("value adapter execution_order values must be unique.")

    datasets = load_dataset_registry(dataset_registry_path)
    known_ids = set(datasets["dataset_id"])
    enabled_ids = set(datasets.loc[datasets["enabled"], "dataset_id"])
    for row in frame.itertuples(index=False):
        if row.dataset_id not in known_ids:
            raise ValueError(f"Unknown value-adapter dataset: {row.dataset_id}")
        if row.enabled and row.dataset_id not in enabled_ids:
            raise ValueError(
                f"Enabled value adapter references disabled dataset: "
                f"{row.dataset_id}"
            )
        if not row.adapter_name or not row.output_relative_path:
            raise ValueError(
                f"{row.dataset_id}: adapter_name and output_relative_path "
                "must not be empty."
            )
    return frame.sort_values("execution_order", kind="stable").reset_index(
        drop=True
    )


def get_registered_stage3_source_paths(
    repo_root: Path,
    registry_path: Path = VALUE_ADAPTER_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
) -> dict[str, Path]:
    """Return enabled Stage 3 sources in registry order."""
    registry = load_value_adapter_registry(
        registry_path,
        dataset_registry_path,
    )
    sources = registry[registry["enabled"] & registry["stage3_source"]]
    return {
        row.dataset_id: prefer_compressed_csv_path(
            Path(repo_root) / row.output_relative_path
        )
        for row in sources.itertuples(index=False)
    }


def run_registered_value_adapters(
    adapter_runners: dict[str, Callable[[], None]],
    registry_path: Path = VALUE_ADAPTER_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
) -> list[str]:
    """Run each enabled native adapter once in configured order."""
    registry = load_value_adapter_registry(
        registry_path,
        dataset_registry_path,
    )
    enabled = registry[registry["enabled"]]
    missing = sorted(set(enabled["adapter_name"]) - set(adapter_runners))
    if missing:
        raise ValueError(f"Missing registered value-adapter runners: {missing}")
    executed: list[str] = []
    for row in enabled.itertuples(index=False):
        adapter_runners[row.adapter_name]()
        executed.append(row.dataset_id)
    return executed


#%%
