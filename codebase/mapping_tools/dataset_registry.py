#%%
"""Load and validate the dataset and comparison-scope registries.

This is the M1 compatibility layer for the multi-dataset framework.  It keeps
the existing execution functions and public constants intact while moving
dataset identity and comparison-scope membership into reviewed configuration.
"""

#%%
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_REGISTRY_PATH = REPO_ROOT / "config" / "datasets" / "dataset_registry.csv"
COMPARISON_SCOPE_REGISTRY_PATH = (
    REPO_ROOT / "config" / "datasets" / "comparison_scopes.csv"
)

DATASET_REGISTRY_COLUMNS = [
    "dataset_id",
    "display_name",
    "enabled",
    "dataset_kind",
    "source_version",
    "value_adapter",
    "hierarchy_adapter",
    "hierarchy_input_relative_path",
    "axis_1_id",
    "axis_1_role",
    "axis_2_id",
    "axis_2_role",
    "canonical_target_dataset_id",
    "native_unit",
    "sign_convention_id",
    "scenario_policy_id",
    "period_policy_id",
    "subtotal_authority",
    "owner",
    "notes",
]
COMPARISON_SCOPE_REGISTRY_COLUMNS = [
    "comparison_scope",
    "enabled",
    "default_enabled",
    "default_order",
    "canonical_component_dataset_id",
    "included_dataset_ids",
    "use_cases",
    "aggregate_constraint_dataset_ids",
    "scenario_alignment_policy",
    "period_alignment_policy",
    "notes",
]

_DATASET_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
_SCOPE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_DATASET_KINDS = {"observed", "model", "derived", "comparison"}
_AXIS_ROLES = {"flow", "sector", "product", "fuel"}
_TRUE_VALUES = {"true", "1", "yes"}
_FALSE_VALUES = {"false", "0", "no"}


def _read_registry(path: Path, required_columns: list[str]) -> pd.DataFrame:
    """Read a registry as text and reject missing columns or blank files."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Registry does not exist: {path}")

    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing_columns = [
        column for column in required_columns if column not in frame.columns
    ]
    if missing_columns:
        raise ValueError(
            f"{path.name} is missing required columns: {missing_columns}"
        )
    if frame.empty:
        raise ValueError(f"{path.name} must contain at least one row.")

    frame = frame[required_columns].copy()
    for column in frame.columns:
        frame[column] = frame[column].astype(str).str.strip()
    return frame


def _parse_boolean(value: object, field_name: str, row_label: str) -> bool:
    """Parse a deliberately small set of explicit Boolean spellings."""
    text = str(value).strip().casefold()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    raise ValueError(
        f"{row_label}: {field_name} must be an explicit Boolean, got {value!r}."
    )


def _split_ids(value: object) -> list[str]:
    """Split an ordered pipe-delimited registry field."""
    return [item.strip() for item in str(value).split("|") if item.strip()]


def load_dataset_registry(
    registry_path: Path = DATASET_REGISTRY_PATH,
) -> pd.DataFrame:
    """Return the validated dataset registry in declared row order."""
    frame = _read_registry(registry_path, DATASET_REGISTRY_COLUMNS)

    blank_ids = frame["dataset_id"].eq("")
    if blank_ids.any():
        raise ValueError("dataset_registry.csv contains a blank dataset_id.")
    duplicate_ids = sorted(
        frame.loc[frame["dataset_id"].duplicated(keep=False), "dataset_id"].unique()
    )
    if duplicate_ids:
        raise ValueError(f"Duplicate dataset_id values: {duplicate_ids}")

    invalid_ids = sorted(
        dataset_id
        for dataset_id in frame["dataset_id"]
        if not _DATASET_ID_PATTERN.fullmatch(dataset_id)
    )
    if invalid_ids:
        raise ValueError(
            "dataset_id values must use upper snake case; invalid values: "
            f"{invalid_ids}"
        )

    invalid_kinds = sorted(set(frame["dataset_kind"]) - _DATASET_KINDS)
    if invalid_kinds:
        raise ValueError(f"Unknown dataset_kind values: {invalid_kinds}")

    invalid_axis_roles = sorted(
        (set(frame["axis_1_role"]) | set(frame["axis_2_role"])) - _AXIS_ROLES
    )
    if invalid_axis_roles:
        raise ValueError(f"Unknown axis role values: {invalid_axis_roles}")

    frame["enabled"] = [
        _parse_boolean(value, "enabled", dataset_id)
        for value, dataset_id in zip(frame["enabled"], frame["dataset_id"])
    ]

    known_ids = set(frame["dataset_id"])
    unknown_targets = sorted(
        {
            target
            for target in frame["canonical_target_dataset_id"]
            if target and target not in known_ids
        }
    )
    if unknown_targets:
        raise ValueError(
            "canonical_target_dataset_id references unknown datasets: "
            f"{unknown_targets}"
        )
    return frame


def load_comparison_scope_registry(
    registry_path: Path = COMPARISON_SCOPE_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
) -> pd.DataFrame:
    """Return validated scopes with ordered list fields normalized to lists."""
    datasets = load_dataset_registry(dataset_registry_path)
    known_dataset_ids = set(datasets["dataset_id"])
    enabled_dataset_ids = set(
        datasets.loc[datasets["enabled"], "dataset_id"]
    )
    frame = _read_registry(registry_path, COMPARISON_SCOPE_REGISTRY_COLUMNS)

    blank_scopes = frame["comparison_scope"].eq("")
    if blank_scopes.any():
        raise ValueError("comparison_scopes.csv contains a blank comparison_scope.")
    duplicate_scopes = sorted(
        frame.loc[
            frame["comparison_scope"].duplicated(keep=False), "comparison_scope"
        ].unique()
    )
    if duplicate_scopes:
        raise ValueError(f"Duplicate comparison_scope values: {duplicate_scopes}")

    invalid_scopes = sorted(
        scope
        for scope in frame["comparison_scope"]
        if not _SCOPE_ID_PATTERN.fullmatch(scope)
    )
    if invalid_scopes:
        raise ValueError(
            "comparison_scope values must use lower snake case; invalid values: "
            f"{invalid_scopes}"
        )

    for boolean_column in ["enabled", "default_enabled"]:
        frame[boolean_column] = [
            _parse_boolean(value, boolean_column, scope)
            for value, scope in zip(
                frame[boolean_column], frame["comparison_scope"]
            )
        ]

    list_columns = [
        "included_dataset_ids",
        "use_cases",
        "aggregate_constraint_dataset_ids",
    ]
    for column in list_columns:
        frame[column] = frame[column].map(_split_ids)

    for row in frame.itertuples(index=False):
        referenced_ids = {
            row.canonical_component_dataset_id,
            *row.included_dataset_ids,
            *row.aggregate_constraint_dataset_ids,
        }
        unknown_ids = sorted(referenced_ids - known_dataset_ids)
        if unknown_ids:
            raise ValueError(
                f"{row.comparison_scope}: unknown dataset references: {unknown_ids}"
            )
        disabled_ids = sorted(referenced_ids - enabled_dataset_ids)
        if row.enabled and disabled_ids:
            raise ValueError(
                f"{row.comparison_scope}: enabled scope references disabled "
                f"datasets: {disabled_ids}"
            )
        if not row.included_dataset_ids:
            raise ValueError(
                f"{row.comparison_scope}: included_dataset_ids must not be empty."
            )
        if not row.use_cases:
            raise ValueError(f"{row.comparison_scope}: use_cases must not be empty.")
        if row.default_enabled and not row.enabled:
            raise ValueError(
                f"{row.comparison_scope}: a disabled scope cannot be default_enabled."
            )

    default_rows = frame[frame["default_enabled"]].copy()
    default_rows["default_order"] = pd.to_numeric(
        default_rows["default_order"], errors="coerce"
    )
    if default_rows["default_order"].isna().any():
        invalid_scopes = default_rows.loc[
            default_rows["default_order"].isna(), "comparison_scope"
        ].tolist()
        raise ValueError(
            "default_enabled scopes require a numeric default_order: "
            f"{invalid_scopes}"
        )
    if default_rows["default_order"].duplicated().any():
        raise ValueError("default_order values must be unique.")
    return frame


def build_comparison_scope_configs(
    registry_path: Path = COMPARISON_SCOPE_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
) -> dict[str, dict[str, list[str]]]:
    """Build the legacy scope-config shape consumed by current workflows."""
    frame = load_comparison_scope_registry(
        registry_path=registry_path,
        dataset_registry_path=dataset_registry_path,
    )
    return {
        row.comparison_scope: {
            "systems": list(row.included_dataset_ids),
            "use_cases": list(row.use_cases),
            "aggregate_source_systems": list(
                row.aggregate_constraint_dataset_ids
            ),
        }
        for row in frame[frame["enabled"]].itertuples(index=False)
    }


def get_default_enabled_comparison_scopes(
    registry_path: Path = COMPARISON_SCOPE_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
) -> list[str]:
    """Return default scopes in their reviewed registry order."""
    frame = load_comparison_scope_registry(
        registry_path=registry_path,
        dataset_registry_path=dataset_registry_path,
    )
    selected = frame[frame["enabled"] & frame["default_enabled"]].copy()
    selected["default_order"] = pd.to_numeric(selected["default_order"])
    selected = selected.sort_values("default_order", kind="stable")
    return selected["comparison_scope"].tolist()


def get_comparison_scope_systems(
    registry_path: Path = COMPARISON_SCOPE_REGISTRY_PATH,
    dataset_registry_path: Path = DATASET_REGISTRY_PATH,
) -> dict[str, set[str]]:
    """Return the legacy scope-to-system-set view used during application."""
    configs = build_comparison_scope_configs(
        registry_path=registry_path,
        dataset_registry_path=dataset_registry_path,
    )
    return {
        scope: set(config["systems"])
        for scope, config in configs.items()
    }


#%%
