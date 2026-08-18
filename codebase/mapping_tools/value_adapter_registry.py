#%%
"""Registry helpers for normalized value-adapter orchestration."""

#%%
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import pandas as pd

from codebase.mapping_tools.dataset_registry import (
    DATASET_REGISTRY_PATH,
    load_dataset_registry,
)
from codebase.mapping_tools.result_storage import prefer_compressed_csv_path


# See dataset_registry.py's REPO_ROOT for why this falls back when frozen.
REPO_ROOT = (
    Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
)
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
    "relevance_period_policy",
    "relevance_evidence_column",
    "relevance_include_year_range",
    "relevance_reference_glob",
    "lineage_relative_path",
    "owner",
    "notes",
]
NORMALIZED_VALUE_COLUMNS = [
    "source_system",
    "economy",
    "scenario",
    "year",
    "esto_flow",
    "esto_product",
    "value",
]
GENERIC_NORMALIZED_ADAPTER = "normalized_long_passthrough"
RELEVANCE_PERIOD_POLICIES = {
    "latest_available_year",
    "from_projection_start",
    "all_periods",
}


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
    for column in [
        "enabled",
        "stage3_source",
        "relevance_include_year_range",
    ]:
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
        if row.relevance_period_policy not in RELEVANCE_PERIOD_POLICIES:
            raise ValueError(
                f"{row.dataset_id}: unknown relevance_period_policy "
                f"{row.relevance_period_policy!r}."
            )
        if row.stage3_source and not row.relevance_evidence_column:
            raise ValueError(
                f"{row.dataset_id}: Stage 3 sources require "
                "relevance_evidence_column."
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
    paths = {
        row.dataset_id: prefer_compressed_csv_path(
            Path(repo_root) / row.output_relative_path
        )
        for row in sources.itertuples(index=False)
    }
    # ESTO Extended is a structural comparison basis, not an independently
    # estimated historical series. Stage 3 maps the ordinary ESTO exact rows
    # through both the ordinary and Extended structures.
    if "ESTO" in paths and "ESTO_EXTENDED" in paths:
        paths["ESTO_EXTENDED"] = paths["ESTO"]
    return paths


def get_component_relevance_policies(
    registry_path: Path = VALUE_ADAPTER_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
) -> list[dict[str, object]]:
    """Return ordered relevance policies for enabled Stage 3 sources."""
    registry = load_value_adapter_registry(
        registry_path,
        dataset_registry_path,
    )
    selected = registry[registry["enabled"] & registry["stage3_source"]]
    return [
        {
            "dataset_id": row.dataset_id,
            "period_policy": row.relevance_period_policy,
            "evidence_column": row.relevance_evidence_column,
            "include_year_range": bool(row.relevance_include_year_range),
        }
        for row in selected.itertuples(index=False)
    ]


def get_component_relevance_reference_paths(
    repo_root: Path,
    registry_path: Path = VALUE_ADAPTER_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
) -> dict[str, list[Path]]:
    """Return supplemental relevance-only inputs, excluding active value inputs."""
    registry = load_value_adapter_registry(
        registry_path,
        dataset_registry_path,
    )
    selected = registry[
        registry["enabled"]
        & registry["stage3_source"]
        & registry["relevance_reference_glob"].astype(str).str.strip().ne("")
    ]
    root = Path(repo_root)
    references: dict[str, list[Path]] = {}
    for row in selected.itertuples(index=False):
        active_input = (root / row.input_relative_path).resolve()
        matches = sorted(
            path.resolve()
            for path in root.glob(row.relevance_reference_glob)
            if path.is_file() and path.resolve() != active_input
        )
        if matches:
            references[str(row.dataset_id)] = matches
    return references


def run_registered_value_adapters(
    adapter_runners: dict[str, Callable[[], None]],
    registry_path: Path = VALUE_ADAPTER_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    """Run each enabled native adapter once in configured order."""
    registry = load_value_adapter_registry(
        registry_path,
        dataset_registry_path,
    )
    enabled = registry[registry["enabled"]]
    supported_adapters = set(adapter_runners) | {GENERIC_NORMALIZED_ADAPTER}
    missing = sorted(set(enabled["adapter_name"]) - supported_adapters)
    if missing:
        raise ValueError(f"Missing registered value-adapter runners: {missing}")
    datasets = load_dataset_registry(dataset_registry_path).set_index("dataset_id")
    executed: list[str] = []
    for row in enabled.itertuples(index=False):
        if row.adapter_name == GENERIC_NORMALIZED_ADAPTER:
            _run_normalized_long_passthrough(
                row=row,
                dataset_row=datasets.loc[row.dataset_id],
                repo_root=Path(repo_root),
            )
        else:
            adapter_runners[row.adapter_name]()
        executed.append(row.dataset_id)
    return executed


def _run_normalized_long_passthrough(
    row: object,
    dataset_row: pd.Series,
    repo_root: Path,
) -> None:
    """Validate and publish an already-normalized PJ dataset."""
    if str(dataset_row["native_unit"]).strip().upper() != "PJ":
        raise ValueError(
            f"{row.dataset_id}: normalized passthrough requires native_unit=PJ."
        )
    input_path = repo_root / row.input_relative_path
    output_path = repo_root / row.output_relative_path
    values = pd.read_csv(input_path, dtype=object)
    missing_columns = sorted(set(NORMALIZED_VALUE_COLUMNS) - set(values.columns))
    if missing_columns:
        raise ValueError(
            f"{row.dataset_id}: normalized input is missing columns: "
            f"{missing_columns}"
        )
    values = values[NORMALIZED_VALUE_COLUMNS].copy()
    source_systems = set(
        values["source_system"].dropna().astype(str).str.strip()
    )
    if source_systems != {row.dataset_id}:
        raise ValueError(
            f"{row.dataset_id}: normalized input must contain only its own "
            f"source_system; found {sorted(source_systems)}."
        )
    values["year"] = pd.to_numeric(values["year"], errors="raise").astype(int)
    values["value"] = pd.to_numeric(values["value"], errors="raise")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    values.to_csv(output_path, index=False)


#%%
