#%%
"""Registry and normalized compiler for workbook rollup-rule sheets."""

#%%
from __future__ import annotations

from pathlib import Path

import pandas as pd

from codebase.mapping_tools.dataset_registry import (
    DATASET_REGISTRY_PATH,
    load_dataset_registry,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
ROLLUP_SHEET_REGISTRY_PATH = (
    REPO_ROOT / "config" / "datasets" / "rollup_sheet_registry.csv"
)
ROLLUP_SHEET_REGISTRY_COLUMNS = [
    "sheet_name",
    "enabled",
    "dataset_id",
    "input_axis_1_column",
    "input_axis_2_column",
    "output_axis_1_column",
    "output_axis_2_column",
    "parent_axis_1_column",
    "child_axis_1_column",
    "include_column",
    "mode_column",
    "owner",
    "notes",
]
NORMALIZED_ROLLUP_COLUMNS = [
    "rule_sheet",
    "dataset_id",
    "source_row_number",
    "input_axis_1_node_id",
    "input_axis_2_node_id",
    "output_axis_1_node_id",
    "output_axis_2_node_id",
    "rollup_mode",
    "include",
    "parent_axis_1_node_id",
    "child_axis_1_node_ids",
    "notes",
]


def _text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _truthy(value: object) -> bool:
    return value is True or _text(value).casefold() in {"true", "1", "yes"}


def _parse_enabled(value: object, sheet_name: str) -> bool:
    text = _text(value).casefold()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise ValueError(
        f"{sheet_name}: enabled must be an explicit Boolean, got {value!r}."
    )


def _rollup_mode(row: pd.Series, mode_column: str) -> str:
    explicit = _text(row.get(mode_column, "")).upper().replace("-", "_").replace(" ", "_")
    if explicit:
        if explicit not in {"EXPANDING", "NON_EXPANDING", "DETACHED"}:
            raise ValueError(f"Unsupported rollup mode: {explicit!r}")
        return explicit
    if _text(row.get("rollup_reason", "")).casefold() == "non_expanding_rollup":
        return "NON_EXPANDING"
    if _truthy(row.get("NON_EXPANDING_ROLLUP", "")):
        return "NON_EXPANDING"
    return "EXPANDING"


def load_rollup_sheet_registry(
    registry_path: Path = ROLLUP_SHEET_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
) -> pd.DataFrame:
    """Return validated rollup-sheet interpretations in execution order."""
    registry_path = Path(registry_path)
    frame = pd.read_csv(registry_path, dtype=str, keep_default_na=False)
    missing = [
        column
        for column in ROLLUP_SHEET_REGISTRY_COLUMNS
        if column not in frame.columns
    ]
    if missing:
        raise ValueError(f"{registry_path.name} is missing columns: {missing}")
    if frame.empty:
        raise ValueError("rollup_sheet_registry.csv must not be empty.")
    frame = frame[ROLLUP_SHEET_REGISTRY_COLUMNS].copy()
    for column in frame:
        frame[column] = frame[column].astype(str).str.strip()
    if frame["sheet_name"].eq("").any():
        raise ValueError("rollup_sheet_registry.csv contains a blank sheet_name.")
    duplicates = sorted(
        frame.loc[
            frame["sheet_name"].duplicated(keep=False), "sheet_name"
        ].unique()
    )
    if duplicates:
        raise ValueError(f"Duplicate rollup sheet names: {duplicates}")
    frame["enabled"] = [
        _parse_enabled(value, sheet_name)
        for value, sheet_name in zip(frame["enabled"], frame["sheet_name"])
    ]

    datasets = load_dataset_registry(dataset_registry_path)
    known_ids = set(datasets["dataset_id"])
    enabled_ids = set(datasets.loc[datasets["enabled"], "dataset_id"])
    required_value_columns = [
        "dataset_id",
        "input_axis_1_column",
        "input_axis_2_column",
        "output_axis_1_column",
        "output_axis_2_column",
        "include_column",
        "mode_column",
    ]
    for row in frame.itertuples(index=False):
        if row.dataset_id not in known_ids:
            raise ValueError(
                f"{row.sheet_name}: unknown dataset reference {row.dataset_id!r}."
            )
        if row.enabled and row.dataset_id not in enabled_ids:
            raise ValueError(
                f"{row.sheet_name}: enabled sheet references disabled dataset "
                f"{row.dataset_id!r}."
            )
        for column in required_value_columns:
            if not _text(getattr(row, column)):
                raise ValueError(f"{row.sheet_name}: {column} must not be empty.")
    return frame


def build_rollup_sheet_configs(
    registry_path: Path = ROLLUP_SHEET_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
) -> dict[str, dict[str, str]]:
    """Build the legacy ROLLUP_SHEET_CONFIGS view."""
    frame = load_rollup_sheet_registry(registry_path, dataset_registry_path)
    return {
        row.sheet_name: {
            "source_system": row.dataset_id,
            "input_flow": row.input_axis_1_column,
            "input_product": row.input_axis_2_column,
            "rolled_flow": row.output_axis_1_column,
            "rolled_product": row.output_axis_2_column,
        }
        for row in frame[frame["enabled"]].itertuples(index=False)
    }


def load_active_rollup_rules(
    workbook_path: Path,
    registry_path: Path = ROLLUP_SHEET_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
) -> dict[str, pd.DataFrame]:
    """Load active raw workbook rows for every enabled registered sheet."""
    registry = load_rollup_sheet_registry(registry_path, dataset_registry_path)
    result: dict[str, pd.DataFrame] = {}
    for row in registry[registry["enabled"]].itertuples(index=False):
        try:
            rules = pd.read_excel(
                workbook_path,
                sheet_name=row.sheet_name,
                dtype=object,
            ).fillna("")
        except Exception:
            result[row.sheet_name] = pd.DataFrame()
            continue
        if row.include_column in rules:
            rules = rules[rules[row.include_column].map(_truthy)]
        result[row.sheet_name] = rules.reset_index(drop=True)
    return result


def compile_normalized_rollup_rules(
    workbook_path: Path,
    registry_path: Path = ROLLUP_SHEET_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
) -> pd.DataFrame:
    """Compile current dataset-specific columns into one generic schema."""
    registry = load_rollup_sheet_registry(registry_path, dataset_registry_path)
    raw_by_sheet = load_active_rollup_rules(
        workbook_path,
        registry_path,
        dataset_registry_path,
    )
    rows: list[dict[str, object]] = []
    for config in registry[registry["enabled"]].itertuples(index=False):
        raw = raw_by_sheet.get(config.sheet_name, pd.DataFrame())
        for source_index, rule in raw.iterrows():
            rows.append(
                {
                    "rule_sheet": config.sheet_name,
                    "dataset_id": config.dataset_id,
                    "source_row_number": int(source_index) + 2,
                    "input_axis_1_node_id": _text(rule.get(config.input_axis_1_column)),
                    "input_axis_2_node_id": _text(rule.get(config.input_axis_2_column)),
                    "output_axis_1_node_id": _text(rule.get(config.output_axis_1_column)),
                    "output_axis_2_node_id": _text(rule.get(config.output_axis_2_column)),
                    "rollup_mode": _rollup_mode(rule, config.mode_column),
                    "include": True,
                    "parent_axis_1_node_id": _text(rule.get(config.parent_axis_1_column)),
                    "child_axis_1_node_ids": _text(rule.get(config.child_axis_1_column)),
                    "notes": _text(rule.get("Note", rule.get("notes", ""))),
                }
            )
    return pd.DataFrame(rows, columns=NORMALIZED_ROLLUP_COLUMNS)


#%%
