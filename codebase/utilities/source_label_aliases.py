#%%
"""Load reviewed source-label aliases without adding duplicate mapping relationships."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ALIAS_PATH = REPO_ROOT / "config" / "leap_export_label_aliases.csv"
REQUIRED_COLUMNS = {"alias_scope", "label_axis", "raw_label", "canonical_label", "enabled", "rationale"}
TRUE_VALUES = {"true", "1", "yes", "y", "on"}


def normalise_source_label_key(value: object) -> str:
    """Return the case-insensitive lookup key while preserving semantic wording."""
    return " ".join(str(value or "").strip().casefold().split())


@lru_cache(maxsize=None)
def load_source_label_aliases(alias_scope: str, label_axis: str, alias_path: str | Path = DEFAULT_ALIAS_PATH) -> dict[str, str]:
    """Return enabled raw-label aliases for one parser or extractor scope and axis."""
    path = Path(alias_path)
    if not path.exists():
        raise FileNotFoundError(f"Missing source-label alias configuration: {path}")

    aliases = pd.read_csv(path, dtype=str).fillna("")
    missing_columns = REQUIRED_COLUMNS - set(aliases.columns)
    if missing_columns:
        raise ValueError(f"{path} is missing required columns: {sorted(missing_columns)}")

    enabled = aliases["enabled"].map(normalise_source_label_key).isin(TRUE_VALUES)
    aliases = aliases[
        enabled
        & aliases["alias_scope"].map(normalise_source_label_key).eq(normalise_source_label_key(alias_scope))
        & aliases["label_axis"].map(normalise_source_label_key).eq(normalise_source_label_key(label_axis))
    ].copy()

    resolved: dict[str, str] = {}
    for row in aliases.itertuples(index=False):
        raw_key = normalise_source_label_key(row.raw_label)
        canonical_label = str(row.canonical_label).strip()
        if not raw_key or not canonical_label:
            raise ValueError(f"{path} contains an empty active source-label alias.")
        existing = resolved.get(raw_key)
        if existing is not None and existing != canonical_label:
            raise ValueError(f"{path} assigns conflicting canonical labels to {row.raw_label!r}.")
        resolved[raw_key] = canonical_label
    return resolved


#%%
