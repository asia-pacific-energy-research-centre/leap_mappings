#%%
"""Resolve an emissions factor set onto the common ESTO axis.

Relocated from ``leap_dashboard/codebase/common_esto_dashboard_emissions.py``
(overnight work program, W5/Phase B, 2026-08-06/07): the dashboard is not the
owner of what a fuel's CO2e factor is, so this stays where the mapping is
owned. This module is a **relocation, not a rewrite** - the subfuel collapse,
``_unallocated`` aliasing, ``prefer_specific_then_mean`` conflict resolution,
and the common-axis join are copied verbatim from the dashboard module
(compare line for line if in doubt), only path resolution changed to be
leap_mappings-repo-relative instead of dashboard-repo-relative.

T5 gate (see the overnight work program): ``emissions_factor_resolution.csv``
must be byte-identical in content (same factors, same ``factor_source_keys``,
same ``esto_components``) to what the dashboard's own
``build_factor_table`` produced before this move, modulo the new
``derived_from`` column this module adds. That is the whole proof this was a
relocation and not a rewrite.

Publishes B1 (factors on the common ESTO axis, one row per
``common_product_label``) via ``build_and_write_b1_factor_table``. Every
published factor artifact carries ``derived_from`` (owner decision,
2026-08-06) - valued ``"ninth"`` today, because the 9th edition is the
current derivation source. This is a config parameter
(``factor_set["derived_from"]``, defaulting to ``"ninth"``), not a hardcoded
path, so a future factor set keyed differently (e.g. LEAP fuel, once real
ESTO factors exist) declares its own provenance rather than this module
guessing at it.

**Deliberately not done here** (see the overnight work program's Deferred
list - "the behaviour-changing half of Phase B... should follow W3 landing"):
this module does not relax ``native_unit == "PJ"`` or register emissions as a
dataset, and the dashboard does not yet consume this published table - it
still resolves factors with its own copy of this logic. Switching the
dashboard over to a single merge against this table is the next step, not
part of this commit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]

# Axis kinds a factor set may be keyed on - copied from the dashboard module
# (common_esto_dashboard_emissions.SUPPORTED_MAPPING_AXES) so this stays a
# relocation, not a narrower reimplementation.
NINTH_FUEL_AXIS = "ninth_fuel"
ESTO_PRODUCT_AXIS = "esto_product"
ESTO_PRODUCT_FLOW_AXIS = "esto_product_flow"
SUPPORTED_MAPPING_AXES = (NINTH_FUEL_AXIS, ESTO_PRODUCT_AXIS, ESTO_PRODUCT_FLOW_AXIS)

DEFAULT_EMISSIONS_UNIT = "Mt CO2e"
DEFAULT_DERIVED_FROM = "ninth"

DEFAULT_FACTOR_SETS_CONFIG_PATH = REPO_ROOT / "config" / "emissions_factor_sets.json"
DEFAULT_B1_OUTPUT_PATH = REPO_ROOT / "results" / "common_esto" / "emissions_factor_resolution.csv"


def _resolve_repo_path(path: str | Path) -> Path:
    """Resolve a leap_mappings-repo-relative path, notebook-safe."""
    path_obj = Path(str(path).replace("\\", "/"))
    return path_obj if path_obj.is_absolute() else REPO_ROOT / path_obj


#%%
# ---------------------------------------------------------------------------
# Factor set configuration
# ---------------------------------------------------------------------------
def load_factor_set_config(config_path: str | Path) -> dict:
    """Load the emissions factor-set config file."""
    return json.loads(_resolve_repo_path(config_path).read_text(encoding="utf-8"))


def select_factor_set(config: dict, factor_set_key: str | None = None) -> dict:
    """Return the requested factor set, defaulting to ``active_factor_set``."""
    factor_sets = config.get("factor_sets", [])
    if not factor_sets:
        raise ValueError("Emissions factor config declares no factor_sets.")
    wanted = str(factor_set_key or config.get("active_factor_set", "")).strip()
    if not wanted:
        return factor_sets[0]
    for factor_set in factor_sets:
        if str(factor_set.get("key", "")) == wanted:
            return factor_set
    available = ", ".join(str(item.get("key", "")) for item in factor_sets)
    raise ValueError(f"Unknown emissions factor set '{wanted}'. Available: {available}")


#%%
# ---------------------------------------------------------------------------
# Shared collapse helper
# ---------------------------------------------------------------------------
def _collapse_factors(
    df: pd.DataFrame,
    key_columns: list[str],
    strategy: str,
    stage: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Collapse many factor rows onto one factor per key.

    Returns ``(collapsed, conflicts)``. A conflict is any key whose incoming
    rows disagree on the factor value; it is resolved by *strategy* and
    reported rather than silently averaged away.
    """
    working = df.copy()
    working["emissions_factor"] = pd.to_numeric(working["emissions_factor"], errors="coerce")
    configured_strategy = strategy

    distinct = (
        working.dropna(subset=["emissions_factor"])
        .groupby(key_columns)["emissions_factor"]
        .nunique()
    )
    conflict_keys = distinct[distinct > 1].index

    if strategy == "prefer_specific_then_mean" and "factor_is_residual" in working.columns:
        # Drop residual/unallocated contributors for keys that also have a
        # specific contributor, then fall through to the mean of what is left.
        has_specific = (
            working.assign(_specific=~working["factor_is_residual"].fillna(False))
            .groupby(key_columns)["_specific"]
            .transform("max")
        )
        working = working[~(working["factor_is_residual"].fillna(False) & has_specific)]
        strategy = "mean"

    aggregator = {"mean": "mean", "max": "max", "min": "min"}.get(strategy, "mean")
    collapsed = (
        working.groupby(key_columns, as_index=False)
        .agg(emissions_factor=("emissions_factor", aggregator))
    )

    if len(conflict_keys) == 0:
        conflicts = pd.DataFrame(columns=[*key_columns, "stage", "resolution", "contributors"])
    else:
        conflict_rows = df.set_index(key_columns).loc[conflict_keys].reset_index()
        source_column = next(
            (col for col in ("ninth_fuel", "esto_product", "component_esto_product") if col in conflict_rows.columns),
            key_columns[0],
        )
        conflicts = (
            conflict_rows.assign(
                contributor=conflict_rows[source_column].astype(str)
                + " = "
                + conflict_rows["emissions_factor"].astype(str)
            )
            .groupby(key_columns, as_index=False)
            .agg(contributors=("contributor", lambda values: "; ".join(sorted(set(values)))))
        )
        conflicts["stage"] = stage
        conflicts["resolution"] = configured_strategy
    return collapsed, conflicts


#%%
# ---------------------------------------------------------------------------
# Axis resolvers: factor file -> ESTO product (and optionally ESTO flow)
# ---------------------------------------------------------------------------
def collapse_ninth_fuel_rows(
    factor_df: pd.DataFrame,
    factor_set: dict,
    ninth_fuel_registry: list[str] | set[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Collapse a fuels/subfuels factor file onto 9th-edition fuel codes.

    Any subfuel other than the placeholder replaces its parent fuel. A parent
    row carrying the placeholder stands in for that fuel's ``_unallocated``
    code only when no explicit unallocated subfuel row already supplies it;
    otherwise it is a fuel-level aggregate over rows already present and is
    dropped so its members are not counted twice.

    *ninth_fuel_registry* is the set of 9th fuel codes the leap_mappings
    contract knows about; anything outside it is not a mappable fuel.

    Returns ``(resolved, dropped)``.
    """
    axis = factor_set.get("ninth_fuel_axis", {})
    fuel_col = str(axis.get("fuel_column", "fuels"))
    subfuel_col = str(axis.get("subfuel_column", "subfuels"))
    placeholder = str(axis.get("subfuel_placeholder", "x")).strip().casefold()
    suffix = str(axis.get("unallocated_suffix", "_unallocated"))

    working = factor_df.copy()
    subfuel = working[subfuel_col].astype(str).str.strip()
    is_placeholder = subfuel.str.casefold() == placeholder
    working["ninth_fuel_key"] = working[fuel_col].astype(str).str.strip().where(
        is_placeholder, subfuel
    )
    working["is_fuel_level_row"] = is_placeholder

    registry = {str(code).strip() for code in ninth_fuel_registry}
    direct_keys = set(working.loc[~working["is_fuel_level_row"], "ninth_fuel_key"]) & registry

    def resolve(row: pd.Series) -> str | None:
        key = str(row["ninth_fuel_key"])
        if key in registry:
            return key
        alias = f"{key}{suffix}"
        if row["is_fuel_level_row"] and alias in registry and alias not in direct_keys:
            return alias
        return None

    working["ninth_fuel"] = working.apply(resolve, axis=1)
    working["factor_is_residual"] = working["ninth_fuel"].astype(str).str.endswith(suffix)

    dropped = working[working["ninth_fuel"].isna()].copy()
    dropped["drop_reason"] = (
        "No 9th fuel in the leap_mappings ninth_fuel_to_esto contract; treated as "
        "a fuel-level aggregate or total whose members are already listed."
    )
    resolved = working[working["ninth_fuel"].notna()].copy()

    duplicated = resolved["ninth_fuel"].duplicated(keep=False)
    if duplicated.any():
        clashing = sorted(set(resolved.loc[duplicated, "ninth_fuel"]))
        raise ValueError(
            "Emissions factor file collapses to duplicate 9th fuel codes: " + ", ".join(clashing)
        )
    return resolved, dropped


_NINTH_FUEL_TO_ESTO_CACHE: dict[str, pd.DataFrame] = {}


def load_ninth_fuel_to_esto(
    workbook_path: str | Path | None = None,
    sheet_name: str = "ninth_fuel_to_esto",
) -> pd.DataFrame:
    """Read the 9th-fuel -> ESTO-product mapping contract."""
    path = _resolve_repo_path(
        workbook_path or "config/outlook_mappings_single_axis.xlsx"
    )
    cache_key = f"{path}::{sheet_name}"
    cached = _NINTH_FUEL_TO_ESTO_CACHE.get(cache_key)
    if cached is not None:
        return cached.copy()
    frame = pd.read_excel(path, sheet_name=sheet_name)
    missing = {"ninth_fuel", "esto_product"} - set(frame.columns)
    if missing:
        raise ValueError(
            f"{path} sheet '{sheet_name}' is missing required columns: {sorted(missing)}"
        )
    frame = frame[["ninth_fuel", "esto_product"]].dropna().drop_duplicates()
    frame["ninth_fuel"] = frame["ninth_fuel"].astype(str).str.strip()
    frame["esto_product"] = frame["esto_product"].astype(str).str.strip()
    _NINTH_FUEL_TO_ESTO_CACHE[cache_key] = frame
    return frame.copy()


def load_esto_to_common_map(
    map_path: str | Path | None = None,
    comparison_scope: str = "esto_leap_ninth",
) -> pd.DataFrame:
    """Read the common ESTO row metadata (component-ESTO -> common axis map).

    Reads ``common_esto_rows.csv``, matching the dashboard's own switch
    (overnight work program W2, 2026-08-06): it and
    ``esto_to_common_esto_map.csv`` give set-identical component-ESTO ->
    common product/flow pairs, and ``common_esto_rows.csv`` is the one
    already declared as a runtime asset.
    """
    path = _resolve_repo_path(map_path or "results/common_esto/common_esto_rows.csv")
    frame = pd.read_csv(
        path,
        usecols=[
            "comparison_scope",
            "component_esto_flow",
            "component_esto_product",
            "common_flow_label",
            "common_product_label",
        ],
    )
    scoped = frame[frame["comparison_scope"].astype(str) == str(comparison_scope)]
    if scoped.empty:
        scoped = frame
    return scoped.drop_duplicates().reset_index(drop=True)


#%%
# ---------------------------------------------------------------------------
# Factor table
# ---------------------------------------------------------------------------
def build_factor_table(
    factor_set: dict,
    mapping_sources: dict | None = None,
    comparison_scope: str = "esto_leap_ninth",
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Resolve a factor set onto the common ESTO axis.

    Returns ``(factors, diagnostics)`` where ``factors`` has one row per
    ``common_product_label`` (plus ``common_flow_label`` when the factor set
    is keyed on ESTO product/flow combinations) and ``diagnostics`` holds the
    dropped-row, conflict, and resolution tables.

    ``factors`` also carries ``derived_from`` (``factor_set.get("derived_from",
    DEFAULT_DERIVED_FROM)``) - every published factor artifact states where it
    came from, so nothing published can later be mistaken for authoritative
    just because it was copied out of context (owner decision, 2026-08-06).
    """
    mapping_sources = mapping_sources or {}
    axis = str(factor_set.get("mapping_axis", NINTH_FUEL_AXIS))
    if axis not in SUPPORTED_MAPPING_AXES:
        raise ValueError(
            f"Unsupported emissions mapping_axis '{axis}'. Supported: {', '.join(SUPPORTED_MAPPING_AXES)}"
        )

    raw = pd.read_csv(_resolve_repo_path(factor_set["path"]))
    factor_column = str(factor_set.get("factor_column", "CO2e emissions factor"))
    raw = raw.rename(columns={factor_column: "emissions_factor"})

    gas_column = str(factor_set.get("gas_column", "")).strip()
    gases = [str(gas).strip().casefold() for gas in factor_set.get("gases", []) if str(gas).strip()]
    if gas_column and gas_column in raw.columns:
        present = sorted(set(raw[gas_column].astype(str).str.strip()))
        if gases:
            raw = raw[raw[gas_column].astype(str).str.strip().str.casefold().isin(gases)]
        if raw.empty:
            raise ValueError(
                f"Emissions factor set '{factor_set.get('key')}' has no rows for the configured "
                f"gases {factor_set.get('gases')}; file contains: {present}."
            )
        # One factor column carries one gas. Multiple retained gases would need
        # per-gas factor columns before they could be summed, so refuse rather
        # than silently mixing them into a single factor.
        retained = sorted(set(raw[gas_column].astype(str).str.strip()))
        if len(retained) > 1:
            raise ValueError(
                f"Emissions factor set '{factor_set.get('key')}' retains multiple gases {retained} "
                "in a single factor column. Restrict 'gases' to one, or add a per-gas factor set."
            )

    # A blank factor is 'no emissions associated with this fuel', not missing data.
    if str(factor_set.get("blank_factor_means", "zero")).casefold() == "zero":
        raw["emissions_factor"] = pd.to_numeric(raw["emissions_factor"], errors="coerce").fillna(0.0)
    else:
        raw["emissions_factor"] = pd.to_numeric(raw["emissions_factor"], errors="coerce")

    diagnostics: dict[str, pd.DataFrame] = {}
    conflict_frames: list[pd.DataFrame] = []

    if axis == NINTH_FUEL_AXIS:
        crosswalk = load_ninth_fuel_to_esto(
            mapping_sources.get("ninth_fuel_to_esto_workbook"),
            str(mapping_sources.get("ninth_fuel_to_esto_sheet", "ninth_fuel_to_esto")),
        )
        resolved, dropped = collapse_ninth_fuel_rows(
            raw, factor_set, crosswalk["ninth_fuel"].tolist()
        )
        diagnostics["dropped_factor_rows"] = dropped[
            ["ninth_fuel_key", "emissions_factor", "drop_reason"]
        ].rename(columns={"ninth_fuel_key": "factor_key"})
        product_level = crosswalk.merge(
            resolved[["ninth_fuel", "emissions_factor", "factor_is_residual"]],
            on="ninth_fuel",
            how="left",
        )
        product_level, ninth_conflicts = _collapse_factors(
            product_level,
            ["esto_product"],
            str(factor_set.get("ninth_conflict_resolution", "prefer_specific_then_mean")),
            stage="ninth_fuel_to_esto_product",
        )
        conflict_frames.append(ninth_conflicts)
        contributors = (
            crosswalk.groupby("esto_product")["ninth_fuel"]
            .apply(lambda values: "; ".join(sorted(set(values))))
            .rename("factor_source_keys")
        )
        product_level = product_level.merge(contributors, on="esto_product", how="left")
    else:
        product_column = str(factor_set.get("esto_product_column", "esto_product"))
        renames = {product_column: "esto_product"}
        if axis == ESTO_PRODUCT_FLOW_AXIS:
            renames[str(factor_set.get("esto_flow_column", "esto_flow"))] = "esto_flow"
        product_level = raw.rename(columns=renames)
        keep = ["esto_product", "emissions_factor"] + (
            ["esto_flow"] if axis == ESTO_PRODUCT_FLOW_AXIS else []
        )
        missing = [column for column in keep if column not in product_level.columns]
        if missing:
            raise ValueError(
                f"Emissions factor set '{factor_set.get('key')}' is missing columns {missing} "
                f"required by mapping_axis '{axis}'."
            )
        product_level = product_level[keep].copy()
        product_level["factor_source_keys"] = product_level["esto_product"].astype(str)
        diagnostics["dropped_factor_rows"] = pd.DataFrame(
            columns=["factor_key", "emissions_factor", "drop_reason"]
        )

    overrides = {
        str(key): float(value)
        for key, value in (factor_set.get("esto_product_factor_overrides") or {}).items()
        if not str(key).startswith("_")
    }
    if overrides:
        override_mask = product_level["esto_product"].astype(str).isin(overrides)
        product_level.loc[override_mask, "emissions_factor"] = (
            product_level.loc[override_mask, "esto_product"].astype(str).map(overrides)
        )

    common_map = load_esto_to_common_map(
        mapping_sources.get("esto_to_common_map"), comparison_scope
    )
    join_keys = ["component_esto_product"]
    axis_keys = ["common_product_label"]
    left_keys = ["esto_product"]
    if axis == ESTO_PRODUCT_FLOW_AXIS:
        join_keys.append("component_esto_flow")
        left_keys.append("esto_flow")
        axis_keys.insert(0, "common_flow_label")

    joined = common_map.merge(
        product_level, left_on=join_keys, right_on=left_keys, how="left"
    )
    unmapped = joined[joined["emissions_factor"].isna()][
        ["component_esto_flow", "component_esto_product", *axis_keys]
    ].drop_duplicates()
    diagnostics["axis_values_without_factor"] = unmapped

    factors, component_conflicts = _collapse_factors(
        joined.dropna(subset=["emissions_factor"]),
        axis_keys,
        str(factor_set.get("component_conflict_resolution", "mean")),
        stage="esto_component_to_common_axis",
    )
    conflict_frames.append(component_conflicts)

    provenance = (
        joined.dropna(subset=["emissions_factor"])
        .groupby(axis_keys, as_index=False)
        .agg(
            esto_components=("component_esto_product", lambda values: "; ".join(sorted(set(values)))),
            factor_source_keys=(
                "factor_source_keys",
                lambda values: "; ".join(
                    sorted({part.strip() for value in values for part in str(value).split(";") if part.strip()})
                ),
            ),
        )
    )
    factors = factors.merge(provenance, on=axis_keys, how="left")
    factors["factor_set_key"] = str(factor_set.get("key", ""))
    factors["emissions_unit"] = str(factor_set.get("emissions_unit", DEFAULT_EMISSIONS_UNIT))
    factors["mapping_axis"] = axis
    factors["derived_from"] = str(factor_set.get("derived_from", DEFAULT_DERIVED_FROM))

    diagnostics["factor_conflicts"] = (
        pd.concat([frame for frame in conflict_frames if not frame.empty], ignore_index=True)
        if any(not frame.empty for frame in conflict_frames)
        else pd.DataFrame(columns=["stage", "resolution", "contributors"])
    )
    diagnostics["factor_resolution"] = factors.copy()
    return factors, diagnostics


#%%
# ---------------------------------------------------------------------------
# B1 publish entry point
# ---------------------------------------------------------------------------
def build_and_write_b1_factor_table(
    config_path: str | Path = DEFAULT_FACTOR_SETS_CONFIG_PATH,
    factor_set_key: str | None = None,
    comparison_scope: str = "esto_leap_ninth",
    output_path: str | Path = DEFAULT_B1_OUTPUT_PATH,
) -> pd.DataFrame:
    """Publish B1: emissions factors on the common ESTO axis (see module docstring).

    One row per ``common_product_label``, with ``derived_from`` naming where
    the factors came from. Returns the written frame.
    """
    config = load_factor_set_config(config_path)
    factor_set = select_factor_set(config, factor_set_key)
    mapping_sources = config.get("mapping_sources", {})
    factors, _diagnostics = build_factor_table(factor_set, mapping_sources, comparison_scope)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    factors.to_csv(output_path, index=False)
    print(f"B1 emissions factor table written: {len(factors)} rows -> {output_path}")
    return factors


if __name__ == "__main__":
    build_and_write_b1_factor_table()
