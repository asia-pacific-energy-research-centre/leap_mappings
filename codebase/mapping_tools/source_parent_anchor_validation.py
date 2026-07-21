#%%
"""Validate raw source parent totals against Common ESTO additive frontiers."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd

from codebase.mapping_tools.structural_resolver import (
    build_tree_index,
    resolve_nearest_mapped_pair,
)
from codebase.mapping_tools.mapping_issue_exceptions import unmodelled_source_pair_mask


COMPARISON_SCOPE_SYSTEMS = {
    "esto_leap": {"LEAP", "ESTO"},
    "leap_vs_ninth": {"LEAP", "NINTH"},
    "esto_leap_ninth": {"LEAP", "NINTH", "ESTO"},
    "esto_only": {"ESTO"},
}


ANCHOR_COLUMNS = [
    "validation_axis", "comparison_scope", "source_system", "economy",
    "scenario", "year", "other_axis_value", "parent_code", "status",
    "reason", "parent_value", "frontier_sum", "difference", "abs_error",
    "proportional_error", "frontier_row_count", "missing_expected_children",
    "parent_positive_value", "parent_negative_value", "frontier_positive_sum",
    "frontier_negative_sum",
]


def _normalize_economy(economy: pd.Series) -> pd.Series:
    """Canonicalize APEC economy codes so ``20USA`` and ``20_USA`` unify.

    The underscore between the numeric prefix and the alpha code is a cosmetic
    separator that appears inconsistently across ESTO/Ninth/LEAP sources; strip
    it so source and comparison rows join on a single code form.
    """
    return economy.astype(str).str.replace("_", "", regex=False)


def _children_map(tree_df: pd.DataFrame, dataset: str, axis: str) -> dict[str, list[str]]:
    selected = tree_df[(tree_df["dataset"] == dataset) & (tree_df["axis"] == axis)]
    result: dict[str, list[str]] = {}
    for row in selected.itertuples(index=False):
        parent = str(row.parent_code).strip() if pd.notna(row.parent_code) else ""
        if parent:
            result.setdefault(parent, []).append(str(row.code).strip())
    return result


def _mapped_descendants(
    code: str,
    other_axis_value: str,
    children: dict[str, list[str]],
    direct_index: dict[tuple[str, str], pd.DataFrame],
    empty_frame: pd.DataFrame,
    cache: dict[tuple[str, str], tuple[pd.DataFrame, list[str]]],
    visited: frozenset = frozenset(),
) -> tuple[pd.DataFrame, list[str]]:
    """Resolve an absent intermediate source node to mapped descendants.

    Result depends only on ``(code, other_axis_value)`` for a fixed source
    system/axis, so it is memoized in ``cache``. ``direct_index`` is a prebuilt
    ``(axis_value, other_axis_value) -> rows`` lookup replacing a per-call scan
    of the mapping frame. ``visited`` tracks the current ancestor chain purely as
    a cycle backstop; trees are acyclic in practice, so the cached results are
    exact for real data.
    """
    key = (code, other_axis_value)
    cached = cache.get(key)
    if cached is not None:
        return cached
    direct = direct_index.get(key)
    if direct is not None:
        result = (direct, [])
    elif code not in children or code in visited:
        # Missing leaf, or a cycle re-entering an ancestor: flag as unresolved.
        result = (empty_frame, [code])
    else:
        frames: list[pd.DataFrame] = []
        missing: list[str] = []
        next_visited = visited | {code}
        for child in children[code]:
            resolved, child_missing = _mapped_descendants(
                child, other_axis_value, children, direct_index, empty_frame, cache, next_visited
            )
            frames.append(resolved)
            missing.extend(child_missing)
        available = pd.concat(frames, ignore_index=True) if frames else empty_frame
        result = (available, missing)
    cache[key] = result
    return result


def validate_source_parent_anchors(
    source_df: pd.DataFrame,
    source_tree_df: pd.DataFrame,
    source_mapping_df: pd.DataFrame,
    common_rows_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
    tolerance: float = 0.01,
    economies: set[str] | None = None,
    years_by_system: dict[str, set[int]] | None = None,
    unmodelled_source_codes: dict[str, set[int]] | None = None,
) -> pd.DataFrame:
    """Return one explicit passed/failed/skipped record per raw source parent group.

    Inputs use normalized source columns: ``source_flow``, ``source_product``,
    ``source_system``, economy, scenario, year, and value. Mapping rows connect
    each source pair to one ESTO component pair.

    The mapping structure it validates is economy/year-independent, so callers
    building the template only need a small numeric slice to exercise the anchor
    totals. ``economies`` (normalized codes) and ``years_by_system`` (per source
    system) restrict the source rows to that slice; leaving them ``None`` runs
    the full-scale reconciliation across every economy and year.
    """
    required_source = {
        "source_system", "economy", "scenario", "year", "source_flow",
        "source_product", "value",
    }
    missing_columns = required_source.difference(source_df.columns)
    if missing_columns:
        raise ValueError(f"Source anchor input is missing columns: {sorted(missing_columns)}")

    common_key = ["comparison_scope", "component_esto_flow", "component_esto_product"]
    common_map = common_rows_df[common_key + ["common_row_id"]].drop_duplicates()
    ambiguous = common_map.groupby(common_key, dropna=False)["common_row_id"].nunique()
    if (ambiguous > 1).any():
        bad = ambiguous[ambiguous > 1].head(10).reset_index().to_dict("records")
        raise ValueError(f"Component maps to multiple Common ESTO rows: {bad}")

    source = source_df.copy()
    source["value"] = pd.to_numeric(source["value"], errors="coerce").fillna(0.0)
    source["year"] = pd.to_numeric(source["year"], errors="coerce")
    source["economy"] = _normalize_economy(source["economy"])
    if economies is not None:
        source = source[source["economy"].isin(economies)]
    if years_by_system is not None:
        # Keep only the requested years per source system (systems absent from
        # the mapping fall through unrestricted).
        keep = source["source_system"].map(years_by_system)
        mask = pd.Series(True, index=source.index)
        has_limit = keep.notna()
        mask.loc[has_limit] = [
            year in allowed for year, allowed in zip(source.loc[has_limit, "year"], keep[has_limit])
        ]
        source = source[mask]
    mappings = source_mapping_df.drop_duplicates().copy()
    records_frames: list[pd.DataFrame] = []

    scopes = common_rows_df["comparison_scope"].dropna().astype(str).unique()
    # Prebuild scope -> scoped component map once (small; was rebuilt per group).
    scoped_maps = {scope: common_map[common_map["comparison_scope"] == scope] for scope in scopes}

    # Slim + normalize the comparison frame once. It has millions of rows, so
    # keep only the columns used below (the raw frame is all-object dtype and
    # would otherwise carry gigabytes of unused cells forward). The per-group
    # boolean scan of the original nested loop is replaced by a single
    # vectorized merge per (source_system, axis) below.
    comparison_keys = ["comparison_scope", "source_system", "economy", "scenario", "year"]
    comparison = comparison_df[comparison_keys + ["common_row_id", "value"]].copy()
    comparison["economy"] = _normalize_economy(comparison["economy"])
    comparison["year"] = pd.to_numeric(comparison["year"], errors="coerce")
    comparison["value"] = pd.to_numeric(comparison["value"], errors="coerce").fillna(0.0)
    comparison["common_row_id"] = comparison["common_row_id"].astype(str)

    for source_system in sorted(source["source_system"].dropna().astype(str).unique()):
        dataset = source_system.casefold()
        system_source = source[source["source_system"] == source_system]
        system_mappings = mappings[mappings["source_system"] == source_system]
        # Scopes this system participates in, and the comparison rows scoped to
        # them — pre-filtered once so the per-axis frontier merge stays small.
        applicable_scopes = [
            scope for scope in scopes
            if source_system in COMPARISON_SCOPE_SYSTEMS.get(scope, {source_system})
        ]
        system_comparison = comparison[
            (comparison["source_system"] == source_system)
            & (comparison["comparison_scope"].isin(applicable_scopes))
        ][["comparison_scope", "economy", "scenario", "year", "common_row_id", "value"]]
        for axis, tree_axis in [("flow", "flow"), ("product", "product")]:
            # LEAP and Ninth trees use sector/fuel terminology.
            if dataset in {"leap", "ninth"}:
                tree_axis = "sector" if axis == "flow" else "fuel"
            children = _children_map(source_tree_df, dataset, tree_axis)
            axis_col = "source_product" if axis == "product" else "source_flow"
            other_col = "source_flow" if axis == "product" else "source_product"
            # Prebuilt direct-mapping lookup + memo cache, scoped to this
            # (source_system, axis) since children/mappings are fixed here.
            direct_index = {
                key: group
                for key, group in system_mappings.groupby([axis_col, other_col], dropna=False)
            }
            empty_mapping = system_mappings.iloc[0:0]
            # Aggregate the source to the granularity the mapping anchors: roll
            # the non-validated ("other") axis up to its deepest mapped ancestor
            # so leaf-level rows collapse onto the aggregate node the workbook
            # maps (e.g. leaf plant sectors -> 09_01_electricity_plants). The
            # groupby below then sums the collapsed rows to that level.
            axis_source = system_source.copy()
            other_tree_axis = "product" if other_col == "source_product" else "flow"
            if dataset in {"leap", "ninth"}:
                other_tree_axis = "fuel" if other_col == "source_product" else "sector"
            parent_index, tree_issues = build_tree_index(source_tree_df, dataset, other_tree_axis)
            if not tree_issues.empty:
                bad = tree_issues[tree_issues["issue_type"].isin(["ambiguous_parent", "cycle"])]
                if not bad.empty:
                    raise ValueError(f"Invalid source tree for {dataset}/{other_tree_axis}: {bad.head(10).to_dict('records')}")
            mapped_pairs = set(zip(system_mappings["source_flow"].astype(str), system_mappings["source_product"].astype(str)))
            pair_remap: dict[tuple[str, str], tuple[str, str]] = {}
            for flow, product in axis_source[["source_flow", "source_product"]].drop_duplicates().itertuples(index=False):
                resolved = resolve_nearest_mapped_pair(
                    flow, product, mapped_pairs,
                    "product" if other_col == "source_product" else "flow",
                    parent_index,
                )
                pair_remap[(str(flow), str(product))] = (
                    resolved["flow"], resolved["product"]
                ) if resolved["status"] == "resolved" else (str(flow), str(product))
            remapped = [pair_remap[(str(flow), str(product))] for flow, product in axis_source[["source_flow", "source_product"]].itertuples(index=False)]
            axis_source["source_flow"] = [pair[0] for pair in remapped]
            axis_source["source_product"] = [pair[1] for pair in remapped]
            descendant_cache: dict[tuple[str, str], tuple[pd.DataFrame, list[str]]] = {}
            # Frontier resolution depends only on (parent_code, other_axis_value),
            # not on economy/scenario/year or scope; cache across groups.
            frontier_cache: dict[tuple[str, str], tuple[pd.DataFrame, list[str]]] = {}
            frontier_ids_cache: dict[tuple[str, str, str], list] = {}
            # --- Vectorized parent aggregation (replaces the per-parent /
            # per-group / per-scope Python loop). Sum every parent's value,
            # positive part, and negative part for every
            # (parent_code, economy, scenario, year, other_axis_value) in one
            # pass instead of re-filtering axis_source per parent. ---
            parents_present = set(children.keys())
            parent_src = axis_source[axis_source[axis_col].isin(parents_present)]
            if parent_src.empty:
                continue
            parent_src = parent_src.assign(
                _pos=parent_src["value"].where(parent_src["value"] > 0, 0.0),
                _neg=parent_src["value"].where(parent_src["value"] < 0, 0.0),
            )
            agg = (
                parent_src.groupby(
                    [axis_col, "economy", "scenario", "year", other_col],
                    dropna=False, sort=False,
                )
                .agg(
                    parent_value=("value", "sum"),
                    parent_positive_value=("_pos", "sum"),
                    parent_negative_value=("_neg", "sum"),
                )
                .reset_index()
                .rename(columns={axis_col: "parent_code", other_col: "other_axis_value"})
            )

            # Resolve the mapped-descendant frontier and its per-scope
            # common_row_ids for each unique (parent_code, other_axis_value)
            # present — reusing the memo caches. Flatten frontier ids into a
            # join table so the comparison lookup can be a single merge.
            missing_join_map: dict[tuple[str, str], str] = {}
            has_missing_map: dict[tuple[str, str], bool] = {}
            fids_empty_map: dict[tuple[str, str, str], bool] = {}
            fid_rows: list[tuple[str, str, str, str]] = []
            for pcode, oav in agg[["parent_code", "other_axis_value"]].drop_duplicates().itertuples(index=False):
                oas = str(oav)
                fk = (pcode, oas)
                frontier_entry = frontier_cache.get(fk)
                if frontier_entry is None:
                    frontier_parts: list[pd.DataFrame] = []
                    missing_children: list[str] = []
                    for child in children.get(pcode, []):
                        resolved, missing = _mapped_descendants(
                            child, oas, children, direct_index,
                            empty_mapping, descendant_cache,
                        )
                        frontier_parts.append(resolved)
                        missing_children.extend(missing)
                    frontier_components = (
                        pd.concat(frontier_parts, ignore_index=True).drop_duplicates()
                        if frontier_parts else empty_mapping
                    )
                    frontier_entry = (frontier_components, missing_children)
                    frontier_cache[fk] = frontier_entry
                frontier_components, missing_children = frontier_entry
                missing_join_map[fk] = "|".join(sorted(set(missing_children)))
                has_missing_map[fk] = bool(missing_children)
                for scope in applicable_scopes:
                    ids_key = (pcode, oas, scope)
                    frontier_ids = frontier_ids_cache.get(ids_key)
                    if frontier_ids is None:
                        frontier_ids = frontier_components.merge(
                            scoped_maps[scope],
                            on=["component_esto_flow", "component_esto_product"],
                            how="left",
                        )["common_row_id"].dropna().unique().tolist()
                        frontier_ids_cache[ids_key] = frontier_ids
                    fids_empty_map[ids_key] = (len(frontier_ids) == 0)
                    for cid in frontier_ids:
                        fid_rows.append((pcode, oas, scope, str(cid)))

            # Cross parent aggregates with the scopes this system serves.
            base = agg.merge(
                pd.DataFrame({"comparison_scope": applicable_scopes}), how="cross"
            )
            base["_oas"] = base["other_axis_value"].astype(str)

            # Frontier sums via a single explode+merge rather than a per-group
            # .isin() over the comparison frame.
            if fid_rows:
                fid_df = pd.DataFrame(
                    fid_rows,
                    columns=["parent_code", "_oas", "comparison_scope", "common_row_id"],
                )
                exploded = base[
                    ["parent_code", "_oas", "comparison_scope", "economy", "scenario", "year"]
                ].merge(fid_df, on=["parent_code", "_oas", "comparison_scope"], how="inner")
                matched = exploded.merge(
                    system_comparison,
                    on=["comparison_scope", "economy", "scenario", "year", "common_row_id"],
                    how="inner",
                )
            else:
                matched = base.iloc[0:0].assign(value=pd.Series(dtype=float))

            if not matched.empty:
                matched = matched.assign(
                    _mpos=matched["value"].where(matched["value"] > 0, 0.0),
                    _mneg=matched["value"].where(matched["value"] < 0, 0.0),
                )
                fsum = (
                    matched.groupby(
                        ["parent_code", "_oas", "comparison_scope", "economy", "scenario", "year"],
                        dropna=False, sort=False,
                    )
                    .agg(
                        frontier_sum=("value", "sum"),
                        frontier_positive_sum=("_mpos", "sum"),
                        frontier_negative_sum=("_mneg", "sum"),
                        frontier_row_count=("common_row_id", "nunique"),
                        _matched=("value", "size"),
                    )
                    .reset_index()
                )
                base = base.merge(
                    fsum,
                    on=["parent_code", "_oas", "comparison_scope", "economy", "scenario", "year"],
                    how="left",
                )
            else:
                for col in ["frontier_sum", "frontier_positive_sum", "frontier_negative_sum",
                            "frontier_row_count", "_matched"]:
                    base[col] = 0.0

            base["frontier_sum"] = base["frontier_sum"].fillna(0.0)
            base["frontier_positive_sum"] = base["frontier_positive_sum"].fillna(0.0)
            base["frontier_negative_sum"] = base["frontier_negative_sum"].fillna(0.0)
            base["frontier_row_count"] = base["frontier_row_count"].fillna(0).astype(int)
            base["_matched"] = base["_matched"].fillna(0)

            pcoa = list(zip(base["parent_code"], base["_oas"]))
            base["missing_expected_children"] = [missing_join_map[k] for k in pcoa]
            has_missing = np.array([has_missing_map[k] for k in pcoa])
            fids_empty = np.array([
                fids_empty_map[(pc, oa, sc)]
                for pc, oa, sc in zip(base["parent_code"], base["_oas"], base["comparison_scope"])
            ])

            base["difference"] = base["parent_value"] - base["frontier_sum"]
            base["abs_error"] = base["difference"].abs()
            rows_empty = (base["_matched"].to_numpy() == 0)
            tol_exceeded = (
                base["abs_error"].to_numpy()
                > tolerance * np.maximum(base["parent_value"].abs().to_numpy(), 1.0)
            )
            # Priority mirrors the original if/elif chain, with two refinements:
            # an incomplete frontier (some leaf child unmapped) that still
            # reconciles the parent within tolerance is a pass, not a failure.
            # Unmapped children are typically intentional placeholders (e.g.
            # ``08_gas_unallocated``) that contribute ~0, so when
            # parent == mapped-leaf sum they do not indicate a real problem.
            # A raw source-tree path with no Common ESTO boundary is instead
            # unanchorable. It is not evidence of a numeric disagreement: this
            # validator cannot compare it until the source frontier is resolved
            # at the real Common ESTO comparison level. Likewise, an absent
            # source frontier with a zero-valued parent is uninformative and is
            # skipped rather than reported as a failed Cartesian combination.
            incomplete_reconciles = has_missing & ~tol_exceeded
            incomplete_gap = has_missing & tol_exceeded
            zero_parent_without_rows = rows_empty & ~tol_exceeded
            conditions = [
                fids_empty,
                zero_parent_without_rows,
                incomplete_reconciles,
                incomplete_gap,
                rows_empty,
                tol_exceeded,
            ]
            base["status"] = np.select(
                conditions,
                ["skipped", "skipped", "passed", "failed", "failed", "failed"],
                default="passed",
            )
            base["reason"] = np.select(
                conditions,
                ["no_anchorable_common_esto_boundary", "no_observed_source_frontier",
                 "within_tolerance_incomplete_frontier", "incomplete_frontier",
                 "frontier_rows_absent", "difference_exceeds_tolerance"],
                default="within_tolerance",
            )
            # Drop unmodelled ESTO/9th sectors/fuels (e.g. stock changes,
            # statistical discrepancy, power-output flows, aggregate fuels): we
            # never reconcile them, so they must not surface as issues at all.
            # Flow/product resolve from the current axis.
            if unmodelled_source_codes:
                if axis == "flow":
                    flow_codes, product_codes = base["parent_code"], base["other_axis_value"]
                else:
                    flow_codes, product_codes = base["other_axis_value"], base["parent_code"]
                excepted = unmodelled_source_pair_mask(
                    flow_codes, product_codes, unmodelled_source_codes
                ).to_numpy()
                if excepted.any():
                    base = base.loc[~excepted]
            with np.errstate(divide="ignore", invalid="ignore"):
                proportional = base["difference"].to_numpy() / base["parent_value"].to_numpy()
            base["proportional_error"] = np.where(
                base["parent_value"].abs().to_numpy() > tolerance, proportional, np.nan
            )
            base["year"] = [int(y) if pd.notna(y) else "" for y in base["year"]]
            base["validation_axis"] = axis
            base["source_system"] = source_system
            records_frames.append(base[ANCHOR_COLUMNS].copy())

    if not records_frames:
        return pd.DataFrame(columns=ANCHOR_COLUMNS)
    return pd.concat(records_frames, ignore_index=True)


# Economy used to exercise the numeric anchor totals when validating the
# mapping template. The mapping is economy-independent, so one economy suffices.
VALIDATION_ECONOMY = "20USA"


def default_validation_slice(
    source_df: pd.DataFrame,
    economy: str = VALIDATION_ECONOMY,
) -> tuple[set[str], dict[str, set[int]]]:
    """Derive the small numeric-validation slice for template building.

    Anchored on the latest year present in the ESTO source (``Y1``): ESTO is
    checked at ``Y1`` (its last historical year), Ninth at ``Y1 + 1`` (its first
    projection year past the ESTO horizon), and LEAP at both ``Y1`` and
    ``Y1 + 1``. Returns ``(economies, years_by_system)`` for
    :func:`validate_source_parent_anchors`.
    """
    years = pd.to_numeric(source_df["year"], errors="coerce")
    esto_years = years[source_df["source_system"] == "ESTO"].dropna()
    if esto_years.empty:
        raise ValueError("Cannot derive validation slice: no ESTO years present.")
    y1 = int(esto_years.max())
    y2 = y1 + 1
    years_by_system = {"ESTO": {y1}, "NINTH": {y2}, "LEAP": {y1, y2}}
    return {_normalize_economy(pd.Series([economy])).iloc[0]}, years_by_system


def _join_hierarchy_path(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    """Vectorized equivalent of row-wise '/'.join(non-empty, non-'x' values).

    Preserves column order; skips values that are NaN, blank, or 'x'.
    """
    result = pd.Series("", index=df.index)
    for column in columns:
        cleaned = df[column].astype(str).str.strip()
        valid = ~cleaned.isin(["", "x", "nan"])
        has_prefix = result.str.len() > 0
        separator = pd.Series(np.where(has_prefix & valid, "/", ""), index=df.index)
        result = result.where(~valid, result + separator + cleaned)
    return result


def _resolve_most_specific(df: pd.DataFrame, columns_least_to_most_specific: list[str]) -> pd.Series:
    """Vectorized equivalent of picking the deepest non-empty, non-'x' column value."""
    result = pd.Series("", index=df.index)
    for column in columns_least_to_most_specific:
        cleaned = df[column].astype(str).str.strip()
        valid = ~cleaned.isin(["", "x", "nan"])
        result = result.where(~valid, cleaned)
    return result


def _melt_years(df: pd.DataFrame, id_columns: list[str]) -> pd.DataFrame:
    year_columns = [column for column in df.columns if str(column).isdigit()]
    return df.melt(id_vars=id_columns, value_vars=year_columns, var_name="year", value_name="value")


def _active_mapping_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Keep active workbook mappings when an include flag is present."""
    if "include" not in df.columns:
        return df
    active = df["include"].apply(
        lambda value: value is True or str(value).strip().casefold() in {"true", "1", "yes"}
    )
    return df[active].copy()


def load_raw_source_anchor_inputs(
    esto_data_path,
    ninth_data_path,
    raw_leap_path,
    workbook_path,
    leap_var_base_year: int = 2022,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load raw ESTO, Ninth, and LEAP values plus their source-to-component mappings."""
    source_frames: list[pd.DataFrame] = []
    mapping_frames: list[pd.DataFrame] = []

    esto = pd.read_csv(esto_data_path, dtype=object)
    esto_long = _melt_years(esto, ["economy", "flows", "products"])
    esto_long = esto_long.rename(columns={"flows": "source_flow", "products": "source_product"})
    esto_long["source_system"] = "ESTO"
    esto_long["scenario"] = "historical"
    source_frames.append(esto_long)
    esto_pairs = esto[["flows", "products"]].drop_duplicates().rename(columns={
        "flows": "source_flow", "products": "source_product",
    })
    esto_pairs["source_system"] = "ESTO"
    esto_pairs["component_esto_flow"] = esto_pairs["source_flow"]
    esto_pairs["component_esto_product"] = esto_pairs["source_product"]
    mapping_frames.append(esto_pairs)

    ninth_load_start = time.perf_counter()
    ninth = pd.read_csv(ninth_data_path, dtype=object)
    sector_columns = ["sectors", "sub1sectors", "sub2sectors", "sub3sectors", "sub4sectors"]
    source_flow = _join_hierarchy_path(ninth, sector_columns)
    source_product = _join_hierarchy_path(ninth, ["fuels", "subfuels"])
    ninth = ninth.copy()
    ninth["source_flow"] = source_flow
    ninth["source_product"] = source_product
    print(
        f"  [timing] 9th source_flow/source_product resolved in "
        f"{time.perf_counter() - ninth_load_start:.2f}s ({len(ninth):,} rows)"
    )
    ninth_long = _melt_years(ninth, ["economy", "scenarios", "source_flow", "source_product"])
    ninth_long = ninth_long.rename(columns={"scenarios": "scenario"})
    ninth_long["year"] = pd.to_numeric(ninth_long["year"], errors="coerce")
    ninth_long = ninth_long[ninth_long["year"] > leap_var_base_year]
    ninth_long["source_system"] = "NINTH"
    source_frames.append(ninth_long)

    ninth_map = _active_mapping_rows(
        pd.read_excel(workbook_path, sheet_name="ninth_pairs_to_esto_pairs", dtype=object)
    )
    sector_lookup = ninth[["source_flow"] + sector_columns].copy()
    sector_lookup["ninth_sector"] = _resolve_most_specific(sector_lookup, sector_columns)
    sector_lookup = sector_lookup[["ninth_sector", "source_flow"]].drop_duplicates()
    fuel_lookup = ninth[["source_product", "fuels", "subfuels"]].copy()
    subfuels_clean = fuel_lookup["subfuels"].astype(str).str.strip()
    valid_subfuels = ~subfuels_clean.isin(["", "x", "nan"])
    fuels_clean = fuel_lookup["fuels"].astype(str).str.strip()
    fuel_lookup["ninth_fuel"] = np.where(valid_subfuels, subfuels_clean, fuels_clean)
    fuel_lookup = fuel_lookup[["ninth_fuel", "source_product"]].drop_duplicates()
    ninth_map = ninth_map.merge(sector_lookup, on="ninth_sector", how="left").merge(fuel_lookup, on="ninth_fuel", how="left")
    ninth_map = ninth_map.rename(columns={"esto_flow": "component_esto_flow", "esto_product": "component_esto_product"})
    ninth_map["source_system"] = "NINTH"
    mapping_frames.append(ninth_map[["source_system", "source_flow", "source_product", "component_esto_flow", "component_esto_product"]].dropna())

    if raw_leap_path is not None and raw_leap_path.exists():
        leap = pd.read_csv(raw_leap_path, dtype=object).rename(columns={
            "leap_flow": "source_flow", "leap_product": "source_product",
        })
        leap["year"] = pd.to_numeric(leap["year"], errors="coerce")
        leap = leap[leap["year"] > leap_var_base_year]
        leap["source_system"] = "LEAP"
        source_frames.append(leap)
        leap_map = _active_mapping_rows(
            pd.read_excel(workbook_path, sheet_name="leap_combined_esto", dtype=object)
        ).rename(columns={
            "leap_sector_name_full_path": "source_flow", "raw_leap_fuel_name": "source_product",
            "esto_flow": "component_esto_flow", "esto_product": "component_esto_product",
        })
        leap_map["source_system"] = "LEAP"
        mapping_frames.append(leap_map[["source_system", "source_flow", "source_product", "component_esto_flow", "component_esto_product"]].dropna())

    source_columns = ["source_system", "economy", "scenario", "year", "source_flow", "source_product", "value"]
    mapping_columns = ["source_system", "source_flow", "source_product", "component_esto_flow", "component_esto_product"]
    return (
        pd.concat(source_frames, ignore_index=True)[source_columns],
        pd.concat(mapping_frames, ignore_index=True)[mapping_columns].drop_duplicates(),
    )


def summarise_source_parent_anchors(detail_df: pd.DataFrame) -> pd.DataFrame:
    """Summarise explicit anchor statuses without treating zero checks as a pass."""
    columns = ["validation_axis", "comparison_scope", "source_system"]
    if detail_df.empty:
        return pd.DataFrame(columns=columns + ["eligible", "passed", "failed", "skipped", "status"])
    summary = detail_df.groupby(columns + ["status"], dropna=False).size().unstack(fill_value=0)
    for status in ["passed", "failed", "skipped"]:
        if status not in summary.columns:
            summary[status] = 0
    summary = summary.reset_index()
    summary["eligible"] = summary["passed"] + summary["failed"]
    summary["status"] = summary.apply(
        lambda row: "failed" if row["failed"] else "passed" if row["eligible"] else "skipped",
        axis=1,
    )
    return summary[columns + ["eligible", "passed", "failed", "skipped", "status"]]

#%%
