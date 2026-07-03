#%%
"""Validate raw source parent totals against Common ESTO additive frontiers."""

from __future__ import annotations

from typing import Any

import pandas as pd

from codebase.mapping_tools.structural_resolver import (
    build_tree_index,
    resolve_nearest_mapped_pair,
)


COMPARISON_SCOPE_SYSTEMS = {
    "leap_vs_esto": {"LEAP", "ESTO"},
    "leap_vs_ninth": {"LEAP", "NINTH"},
    "leap_vs_esto_vs_ninth": {"LEAP", "NINTH", "ESTO"},
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
    records: list[dict[str, Any]] = []

    scopes = common_rows_df["comparison_scope"].dropna().astype(str).unique()
    # Prebuild scope -> scoped component map once (small; was rebuilt per group).
    scoped_maps = {scope: common_map[common_map["comparison_scope"] == scope] for scope in scopes}

    # Index the comparison frame once by its lookup keys. It has millions of
    # rows, so the previous per-iteration boolean scan (plus a full-column
    # pd.to_numeric on every pass) was the dominant cost. Keep only the columns
    # used below (the raw frame is all-object dtype and would otherwise carry
    # gigabytes of unused cells into the index), and resolve groups lazily via
    # get_group so only queried groups are materialized.
    comparison_keys = ["comparison_scope", "source_system", "economy", "scenario", "year"]
    comparison = comparison_df[comparison_keys + ["common_row_id", "value"]].copy()
    comparison["economy"] = _normalize_economy(comparison["economy"])
    comparison["year"] = pd.to_numeric(comparison["year"], errors="coerce")
    comparison["value"] = pd.to_numeric(comparison["value"], errors="coerce").fillna(0.0)
    empty_comparison = comparison.iloc[0:0]
    # O(1) lookup on the slimmed frame: building the group->frame dict once is
    # far cheaper than calling get_group() inside the (potentially millions of)
    # inner-loop iterations.
    comparison_index = {
        key: group
        for key, group in comparison.groupby(comparison_keys, dropna=False, sort=False)
    }

    for source_system in sorted(source["source_system"].dropna().astype(str).unique()):
        dataset = source_system.casefold()
        system_source = source[source["source_system"] == source_system]
        system_mappings = mappings[mappings["source_system"] == source_system]
        for axis, tree_axis in [("flow", "flow"), ("product", "product")]:
            # LEAP and Ninth trees use sector/fuel terminology.
            if dataset in {"leap", "ninth"}:
                tree_axis = "sector" if axis == "flow" else "fuel"
            children = _children_map(source_tree_df, dataset, tree_axis)
            axis_col = "source_product" if axis == "product" else "source_flow"
            other_col = "source_flow" if axis == "product" else "source_product"
            group_cols = ["economy", "scenario", "year", other_col]
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
            for parent_code, direct_children in children.items():
                parent_rows = axis_source[axis_source[axis_col] == parent_code]
                for group_key, parent_group in parent_rows.groupby(group_cols, dropna=False):
                    economy, scenario, year, other_axis_value = group_key
                    parent_value = float(parent_group["value"].sum())
                    parent_positive = float(parent_group.loc[parent_group["value"] > 0, "value"].sum())
                    parent_negative = float(parent_group.loc[parent_group["value"] < 0, "value"].sum())
                    other_axis_str = str(other_axis_value)
                    frontier_key = (parent_code, other_axis_str)
                    frontier_entry = frontier_cache.get(frontier_key)
                    if frontier_entry is None:
                        frontier_parts: list[pd.DataFrame] = []
                        missing_children = []
                        for child in direct_children:
                            resolved, missing = _mapped_descendants(
                                child, other_axis_str, children, direct_index,
                                empty_mapping, descendant_cache,
                            )
                            frontier_parts.append(resolved)
                            missing_children.extend(missing)
                        frontier_components = (
                            pd.concat(frontier_parts, ignore_index=True).drop_duplicates()
                            if frontier_parts else empty_mapping
                        )
                        frontier_entry = (frontier_components, missing_children)
                        frontier_cache[frontier_key] = frontier_entry
                    frontier_components, missing_children = frontier_entry
                    for scope in scopes:
                        if source_system not in COMPARISON_SCOPE_SYSTEMS.get(scope, {source_system}):
                            continue
                        ids_key = (parent_code, other_axis_str, scope)
                        frontier_ids = frontier_ids_cache.get(ids_key)
                        if frontier_ids is None:
                            frontier_ids = frontier_components.merge(
                                scoped_maps[scope],
                                on=["component_esto_flow", "component_esto_product"],
                                how="left",
                            )["common_row_id"].dropna().unique().tolist()
                            frontier_ids_cache[ids_key] = frontier_ids
                        comparison_key = (scope, source_system, economy, scenario, year)
                        group = comparison_index.get(comparison_key)
                        if group is None:
                            rows = empty_comparison
                        else:
                            rows = group[group["common_row_id"].isin(frontier_ids)]
                        frontier_sum = float(rows["value"].sum())
                        difference = parent_value - frontier_sum
                        abs_error = abs(difference)
                        if missing_children:
                            status, reason = "failed", "incomplete_frontier"
                        elif not frontier_ids:
                            status, reason = "skipped", "no_anchorable_common_esto_boundary"
                        elif rows.empty:
                            status, reason = "failed", "frontier_rows_absent"
                        elif abs_error > tolerance * max(abs(parent_value), 1.0):
                            status, reason = "failed", "difference_exceeds_tolerance"
                        else:
                            status, reason = "passed", "within_tolerance"
                        records.append({
                            "validation_axis": axis,
                            "comparison_scope": scope,
                            "source_system": source_system,
                            "economy": economy,
                            "scenario": scenario,
                            "year": int(year) if pd.notna(year) else "",
                            "other_axis_value": other_axis_value,
                            "parent_code": parent_code,
                            "status": status,
                            "reason": reason,
                            "parent_value": parent_value,
                            "frontier_sum": frontier_sum,
                            "difference": difference,
                            "abs_error": abs_error,
                            "proportional_error": difference / parent_value if abs(parent_value) > tolerance else None,
                            "frontier_row_count": int(rows["common_row_id"].nunique()) if not rows.empty else 0,
                            "missing_expected_children": "|".join(sorted(set(missing_children))),
                            "parent_positive_value": parent_positive,
                            "parent_negative_value": parent_negative,
                            "frontier_positive_sum": float(rows.loc[rows["value"] > 0, "value"].sum()),
                            "frontier_negative_sum": float(rows.loc[rows["value"] < 0, "value"].sum()),
                        })
    return pd.DataFrame(records, columns=ANCHOR_COLUMNS)


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

    ninth = pd.read_csv(ninth_data_path, dtype=object)
    sector_columns = ["sectors", "sub1sectors", "sub2sectors", "sub3sectors", "sub4sectors"]
    ninth["source_flow"] = ninth[sector_columns].apply(
        lambda row: "/".join(str(value).strip() for value in row if pd.notna(value) and str(value).strip() not in {"", "x"}),
        axis=1,
    )
    ninth["source_product"] = ninth.apply(
        lambda row: "/".join(
            str(value).strip() for value in [row.get("fuels"), row.get("subfuels")]
            if pd.notna(value) and str(value).strip() not in {"", "x"}
        ), axis=1,
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
    sector_lookup["9th_sector"] = sector_lookup[sector_columns].apply(
        lambda row: next((str(value).strip() for value in reversed(row.tolist()) if pd.notna(value) and str(value).strip() not in {"", "x"}), ""),
        axis=1,
    )
    sector_lookup = sector_lookup[["9th_sector", "source_flow"]].drop_duplicates()
    fuel_lookup = ninth[["source_product", "fuels", "subfuels"]].copy()
    fuel_lookup["9th_fuel"] = fuel_lookup.apply(
        lambda row: str(row["subfuels"]).strip() if pd.notna(row["subfuels"]) and str(row["subfuels"]).strip() not in {"", "x"} else str(row["fuels"]).strip(),
        axis=1,
    )
    fuel_lookup = fuel_lookup[["9th_fuel", "source_product"]].drop_duplicates()
    ninth_map = ninth_map.merge(sector_lookup, on="9th_sector", how="left").merge(fuel_lookup, on="9th_fuel", how="left")
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
