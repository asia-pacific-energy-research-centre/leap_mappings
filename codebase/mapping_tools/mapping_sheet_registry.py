#%%
"""Load mapping-workbook sheet interpretations from reviewed configuration."""

#%%
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from codebase.mapping_tools.dataset_registry import (
    DATASET_REGISTRY_PATH,
    load_dataset_registry,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MAPPING_SHEET_REGISTRY_PATH = (
    REPO_ROOT / "config" / "datasets" / "mapping_sheet_registry.csv"
)
MAPPING_SHEET_REGISTRY_COLUMNS = [
    "sheet_name",
    "enabled",
    "source_dataset_id",
    "target_dataset_id",
    "source_axis_1_candidates",
    "source_axis_2_candidates",
    "target_axis_1_candidates",
    "target_axis_2_candidates",
    "use_cases",
    "owner",
    "notes",
]

_SHEET_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_ ]*$")
_TRUE_VALUES = {"true", "1", "yes"}
_FALSE_VALUES = {"false", "0", "no"}


def _parse_boolean(value: object, sheet_name: str) -> bool:
    """Parse an explicit registry Boolean."""
    text = str(value).strip().casefold()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    raise ValueError(
        f"{sheet_name}: enabled must be an explicit Boolean, got {value!r}."
    )


def _split_ordered(value: object) -> list[str]:
    """Split an ordered pipe-delimited field while preserving duplicates."""
    return [item.strip() for item in str(value).split("|") if item.strip()]


def load_mapping_sheet_registry(
    registry_path: Path = MAPPING_SHEET_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
    known_use_cases: list[str] | None = None,
) -> pd.DataFrame:
    """Return validated workbook-sheet metadata in declared execution order."""
    registry_path = Path(registry_path)
    if not registry_path.exists():
        raise FileNotFoundError(
            f"Mapping-sheet registry does not exist: {registry_path}"
        )

    frame = pd.read_csv(registry_path, dtype=str, keep_default_na=False)
    missing_columns = [
        column
        for column in MAPPING_SHEET_REGISTRY_COLUMNS
        if column not in frame.columns
    ]
    if missing_columns:
        raise ValueError(
            f"{registry_path.name} is missing required columns: {missing_columns}"
        )
    if frame.empty:
        raise ValueError("mapping_sheet_registry.csv must contain at least one row.")

    frame = frame[MAPPING_SHEET_REGISTRY_COLUMNS].copy()
    for column in frame.columns:
        frame[column] = frame[column].astype(str).str.strip()

    if frame["sheet_name"].eq("").any():
        raise ValueError("mapping_sheet_registry.csv contains a blank sheet_name.")
    duplicate_names = sorted(
        frame.loc[
            frame["sheet_name"].duplicated(keep=False), "sheet_name"
        ].unique()
    )
    if duplicate_names:
        raise ValueError(f"Duplicate sheet_name values: {duplicate_names}")

    invalid_names = sorted(
        name
        for name in frame["sheet_name"]
        if not _SHEET_NAME_PATTERN.fullmatch(name)
    )
    if invalid_names:
        raise ValueError(f"Invalid sheet_name values: {invalid_names}")

    frame["enabled"] = [
        _parse_boolean(value, sheet_name)
        for value, sheet_name in zip(frame["enabled"], frame["sheet_name"])
    ]

    list_columns = [
        "source_axis_1_candidates",
        "source_axis_2_candidates",
        "target_axis_1_candidates",
        "target_axis_2_candidates",
        "use_cases",
    ]
    for column in list_columns:
        frame[column] = frame[column].map(_split_ordered)

    datasets = load_dataset_registry(dataset_registry_path)
    enabled_dataset_ids = set(
        datasets.loc[datasets["enabled"], "dataset_id"]
    )
    allowed_use_cases = set(known_use_cases or [])
    for row in frame.itertuples(index=False):
        referenced_datasets = {
            row.source_dataset_id,
            row.target_dataset_id,
        }
        unknown_datasets = sorted(
            referenced_datasets - set(datasets["dataset_id"])
        )
        if unknown_datasets:
            raise ValueError(
                f"{row.sheet_name}: unknown dataset references: "
                f"{unknown_datasets}"
            )
        disabled_datasets = sorted(referenced_datasets - enabled_dataset_ids)
        if row.enabled and disabled_datasets:
            raise ValueError(
                f"{row.sheet_name}: enabled sheet references disabled datasets: "
                f"{disabled_datasets}"
            )
        for column in list_columns:
            if not getattr(row, column):
                raise ValueError(
                    f"{row.sheet_name}: {column} must not be empty."
                )
        if known_use_cases is not None:
            unknown_use_cases = sorted(set(row.use_cases) - allowed_use_cases)
            if unknown_use_cases:
                raise ValueError(
                    f"{row.sheet_name}: unknown use_cases: {unknown_use_cases}"
                )
    return frame


def build_mapping_sheet_configs(
    registry_path: Path = MAPPING_SHEET_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
    known_use_cases: list[str] | None = None,
) -> list[dict[str, object]]:
    """Build the legacy SHEET_CONFIGS shape consumed by Stage 1."""
    frame = load_mapping_sheet_registry(
        registry_path=registry_path,
        dataset_registry_path=dataset_registry_path,
        known_use_cases=known_use_cases,
    )
    return [
        {
            "sheet_name": row.sheet_name,
            "source_system": row.source_dataset_id,
            "target_system": row.target_dataset_id,
            "source_flow_candidates": list(row.source_axis_1_candidates),
            "source_product_candidates": list(row.source_axis_2_candidates),
            "target_flow_candidates": list(row.target_axis_1_candidates),
            "target_product_candidates": list(row.target_axis_2_candidates),
            "use_cases": list(row.use_cases),
        }
        for row in frame[frame["enabled"]].itertuples(index=False)
    ]


#%%
