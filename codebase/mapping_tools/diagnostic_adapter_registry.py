#%%
"""Load and execute registered source-specific Stage 3 diagnostics."""

#%%
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

from codebase.mapping_tools.dataset_registry import (
    DATASET_REGISTRY_PATH,
    load_dataset_registry,
)
from codebase.mapping_tools.mapping_sheet_registry import (
    MAPPING_SHEET_REGISTRY_PATH,
    load_mapping_sheet_registry,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DIAGNOSTIC_ADAPTER_REGISTRY_PATH = (
    REPO_ROOT / "config" / "datasets" / "diagnostic_adapter_registry.csv"
)
DIAGNOSTIC_ADAPTER_REGISTRY_COLUMNS = [
    "diagnostic_id",
    "enabled",
    "adapter_name",
    "execution_order",
    "source_dataset_id",
    "raw_source_relative_path",
    "direct_mapping_sheet",
    "bridge_mapping_sheet",
    "bridge_target_mapping_sheet",
    "owner",
    "notes",
]


def _boolean(value: object, diagnostic_id: str) -> bool:
    """Parse an explicit registry Boolean."""
    text = str(value).strip().casefold()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise ValueError(
        f"{diagnostic_id}: enabled must be an explicit Boolean, got {value!r}."
    )


def load_diagnostic_adapter_registry(
    registry_path: Path = DIAGNOSTIC_ADAPTER_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
    mapping_sheet_registry_path: Path = MAPPING_SHEET_REGISTRY_PATH,
) -> pd.DataFrame:
    """Return validated source-specific diagnostics in execution order."""
    registry_path = Path(registry_path)
    if not registry_path.exists():
        raise FileNotFoundError(
            f"Diagnostic-adapter registry does not exist: {registry_path}"
        )
    frame = pd.read_csv(registry_path, dtype=str, keep_default_na=False)
    missing = [
        column
        for column in DIAGNOSTIC_ADAPTER_REGISTRY_COLUMNS
        if column not in frame.columns
    ]
    if missing:
        raise ValueError(f"{registry_path.name} is missing columns: {missing}")
    if frame.empty:
        raise ValueError("diagnostic_adapter_registry.csv must not be empty.")

    frame = frame[DIAGNOSTIC_ADAPTER_REGISTRY_COLUMNS].copy()
    for column in frame:
        frame[column] = frame[column].astype(str).str.strip()
    blank_ids = frame["diagnostic_id"].eq("")
    if blank_ids.any():
        raise ValueError(
            "diagnostic_adapter_registry.csv contains a blank diagnostic_id."
        )
    duplicates = sorted(
        frame.loc[
            frame["diagnostic_id"].duplicated(keep=False), "diagnostic_id"
        ].unique()
    )
    if duplicates:
        raise ValueError(f"Duplicate diagnostic IDs: {duplicates}")
    frame["enabled"] = [
        _boolean(value, diagnostic_id)
        for value, diagnostic_id in zip(
            frame["enabled"],
            frame["diagnostic_id"],
        )
    ]
    frame["execution_order"] = pd.to_numeric(
        frame["execution_order"],
        errors="coerce",
    )
    if frame["execution_order"].isna().any():
        raise ValueError(
            "Every diagnostic adapter requires numeric execution_order."
        )
    if frame["execution_order"].duplicated().any():
        raise ValueError(
            "Diagnostic adapter execution_order values must be unique."
        )

    datasets = load_dataset_registry(dataset_registry_path)
    known_dataset_ids = set(datasets["dataset_id"])
    enabled_dataset_ids = set(
        datasets.loc[datasets["enabled"], "dataset_id"]
    )
    mapping_sheets = load_mapping_sheet_registry(
        registry_path=mapping_sheet_registry_path,
        dataset_registry_path=dataset_registry_path,
    )
    known_mapping_sheets = set(mapping_sheets["sheet_name"])
    enabled_mapping_sheets = set(
        mapping_sheets.loc[mapping_sheets["enabled"], "sheet_name"]
    )
    mapping_columns = [
        "direct_mapping_sheet",
        "bridge_mapping_sheet",
        "bridge_target_mapping_sheet",
    ]
    for row in frame.itertuples(index=False):
        if not row.adapter_name:
            raise ValueError(
                f"{row.diagnostic_id}: adapter_name must not be empty."
            )
        if row.source_dataset_id not in known_dataset_ids:
            raise ValueError(
                f"{row.diagnostic_id}: unknown source dataset "
                f"{row.source_dataset_id!r}."
            )
        if row.enabled and row.source_dataset_id not in enabled_dataset_ids:
            raise ValueError(
                f"{row.diagnostic_id}: enabled diagnostic references disabled "
                f"dataset {row.source_dataset_id!r}."
            )
        if not row.raw_source_relative_path:
            raise ValueError(
                f"{row.diagnostic_id}: raw_source_relative_path must not be "
                "empty."
            )
        for column in mapping_columns:
            sheet_name = getattr(row, column)
            if sheet_name not in known_mapping_sheets:
                raise ValueError(
                    f"{row.diagnostic_id}: {column} references unknown mapping "
                    f"sheet {sheet_name!r}."
                )
            if row.enabled and sheet_name not in enabled_mapping_sheets:
                raise ValueError(
                    f"{row.diagnostic_id}: enabled diagnostic references "
                    f"disabled mapping sheet {sheet_name!r}."
                )
    return frame.sort_values(
        "execution_order",
        kind="stable",
    ).reset_index(drop=True)


def run_registered_diagnostic_adapters(
    adapter_runners: dict[str, Callable[[pd.Series], object]],
    registry_path: Path = DIAGNOSTIC_ADAPTER_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
    mapping_sheet_registry_path: Path = MAPPING_SHEET_REGISTRY_PATH,
) -> dict[str, object]:
    """Run each enabled diagnostic through its registered adapter."""
    registry = load_diagnostic_adapter_registry(
        registry_path=registry_path,
        dataset_registry_path=dataset_registry_path,
        mapping_sheet_registry_path=mapping_sheet_registry_path,
    )
    enabled = registry[registry["enabled"]]
    missing_runners = sorted(
        set(enabled["adapter_name"]) - set(adapter_runners)
    )
    if missing_runners:
        raise ValueError(
            f"Missing registered diagnostic-adapter runners: "
            f"{missing_runners}"
        )
    results: dict[str, object] = {}
    for _, row in enabled.iterrows():
        results[row["diagnostic_id"]] = adapter_runners[
            row["adapter_name"]
        ](row)
    return results


#%%
