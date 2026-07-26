#%%
"""Validate raw source parent totals against Common ESTO additive frontiers."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from codebase.mapping_tools.structural_resolver import (
    build_tree_index,
    build_tree_code_aliases,
    canonicalize_tree_codes,
    resolve_parent_to_mapped_other_axis,
    resolve_nearest_mapped_pair,
)
from codebase.mapping_tools.mapping_issue_exceptions import unmodelled_source_pair_mask
from codebase.mapping_issue_exceptions import (
    EXCEPTION_WORKBOOK_PATH,
    load_exception_sheet,
    matching_exception_row,
)


COMPARISON_SCOPE_SYSTEMS = {
    "esto_leap": {"LEAP", "ESTO"},
    "esto_extended_leap": {"LEAP", "ESTO_EXTENDED"},
    "leap_vs_ninth": {"LEAP", "NINTH"},
    "esto_leap_ninth": {"LEAP", "NINTH", "ESTO"},
    "esto_extended_leap_ninth": {"LEAP", "NINTH", "ESTO_EXTENDED"},
    "esto_only": {"ESTO"},
}
NONZERO_SOURCE_EVIDENCE_TOLERANCE = 1e-12


ANCHOR_COLUMNS = [
    "validation_axis", "comparison_scope", "source_system", "economy",
    "scenario", "year", "other_axis_value", "parent_code", "status",
    "reason", "parent_value", "frontier_sum", "difference", "abs_error",
    "proportional_error", "frontier_row_count", "missing_expected_children",
    "missing_expected_child_count", "missing_nonzero_child_count",
    "missing_nonzero_child_abs", "missing_zero_or_absent_child_count",
    "parent_positive_value", "parent_negative_value", "frontier_positive_sum",
    "frontier_negative_sum",
]

ANCHOR_CHILD_VALUE_COLUMNS = [
    "validation_axis", "comparison_scope", "source_system", "parent_code", "child_code",
    "failed_context_count", "parent_total", "frontier_total", "mismatch_total",
    "absolute_mismatch_total", "raw_child_total", "raw_child_row_count",
]

ANCHOR_CHILD_CONTEXT_COLUMNS = [
    "validation_axis", "comparison_scope", "source_system", "economy", "scenario", "year",
    "other_axis_value", "parent_code", "child_code", "parent_value", "frontier_sum",
    "difference", "abs_error", "raw_child_value", "raw_child_row_count",
]

ANCHOR_MAPPED_COMPONENT_CONTEXT_COLUMNS = [
    "validation_axis", "comparison_scope", "source_system", "economy", "scenario", "year",
    "other_axis_value", "parent_code", "raw_node_role", "raw_child_code", "resolved_source_flow",
    "resolved_source_product", "component_esto_flow", "component_esto_product", "common_row_id",
    "mapped_value", "mapping_status",
]

# A reviewed, manually-curated exception for a raw-source self-inconsistency
# NINTH/LEAP/ESTO's own data cannot resolve automatically (see
# _augment_with_data_quality_exceptions). Reuses the same
# config/mapping_issue_exception_sets.xlsx workbook and enabled/notes
# convention as every other exception family in this repo.
DATA_QUALITY_EXCEPTION_SHEET = "source_mismatch_allowed"
ANCHOR_EXCEPTION_COLUMNS = [
    "known_data_quality_exception", "data_quality_exception_notes", "exception_resolution",
]

LEAF_RECONCILIATION_CANDIDATE_COLUMNS = [
    "enabled", "source_system", "validation_axis", "parent_code", "other_axis_value",
    "economy", "parent_value", "notes", "candidate_classification", "comparison_scope",
    "scenario", "year", "direct_children_sum", "direct_children_residual",
    "leaf_descendants_sum", "leaf_descendants_residual", "leaf_descendant_codes",
]


def _normalize_economy(economy: pd.Series) -> pd.Series:
    """Canonicalize APEC economy codes so ``20USA`` and ``20_USA`` unify.

    The underscore between the numeric prefix and the alpha code is a cosmetic
    separator that appears inconsistently across ESTO/Ninth/LEAP sources; strip
    it so source and comparison rows join on a single code form.
    """
    return economy.astype(str).str.replace("_", "", regex=False)


def _children_map(
    tree_df: pd.DataFrame,
    dataset: str,
    axis: str,
) -> dict[str, list[str]]:
    """Return raw source tree parent -> children edges.

    Every parent/child edge in the raw tree is kept here regardless of
    ``exclude_parents`` (see :func:`validate_source_parent_anchors`): this
    dict is also used by :func:`_mapped_descendants` to descend *into* a
    node's children while resolving some *other* ancestor's frontier (e.g.
    descending into ``09.06 Gas processing plants`` while resolving
    ``09 Total transformation sector``'s frontier). Dropping an excluded
    label's entry here would silently make it unresolvable as a frontier
    component too, not just unvalidated as a parent -- a caller that wants a
    label excluded from *independent parent validation* must filter
    ``parents_present`` (the set of codes actually iterated as parents),
    not this map.
    """
    selected = tree_df[(tree_df["dataset"] == dataset) & (tree_df["axis"] == axis)]
    result: dict[str, list[str]] = {}
    for row in selected.itertuples(index=False):
        parent = str(row.parent_code).strip() if pd.notna(row.parent_code) else ""
        if parent:
            result.setdefault(parent, []).append(str(row.code).strip())
    return result


def _build_source_evidence_lookup(
    source_df: pd.DataFrame,
    axis_column: str,
    other_column: str,
    other_parent_index: dict[str, str],
) -> dict[tuple[str, str, str, str, int], float]:
    """Index absolute source evidence for an axis child and other-axis scope.

    The anchor frontier can be incomplete because a structural child is absent
    from the mapping, but that child may still be zero in the source data.  Keep
    an absolute-value lookup (rather than signed sums, which could cancel) and
    roll the other axis to its explicit ancestors so the evidence matches the
    validator's mapped ancestor scope.
    """
    working = source_df.copy()
    working[axis_column] = working[axis_column].fillna("").astype(str).str.strip()
    working[other_column] = working[other_column].fillna("").astype(str).str.strip()
    working["economy"] = working["economy"].fillna("").astype(str).str.strip()
    working["scenario"] = working["scenario"].fillna("").astype(str).str.strip()
    working["year"] = pd.to_numeric(working["year"], errors="coerce")
    working["_abs_value"] = pd.to_numeric(working["value"], errors="coerce").fillna(0.0).abs()
    working = working[
        working[axis_column].ne("")
        & working[other_column].ne("")
        & working["year"].notna()
    ]
    grouped = (
        working.groupby(
            [axis_column, other_column, "economy", "scenario", "year"],
            dropna=False,
        )["_abs_value"]
        .sum()
    )
    lookup: dict[tuple[str, str, str, str, int], float] = {}
    for (axis_value, other_value, economy, scenario, year), amount in grouped.items():
        current = str(other_value)
        visited: set[str] = set()
        while current and current not in visited:
            visited.add(current)
            key = (str(axis_value), current, str(economy), str(scenario), int(year))
            lookup[key] = lookup.get(key, 0.0) + float(amount)
            current = other_parent_index.get(current, "")
    return lookup


def _build_raw_pair_values(source_df: pd.DataFrame) -> pd.DataFrame:
    """Return a source system's own signed raw value summed by its exact literal pair.

    Unlike :func:`_build_source_evidence_lookup` this keeps the signed value
    (not its absolute value) and does not roll the other axis up to its
    ancestors -- it is an exact-match table for one resolved frontier
    component's own reported figure, used when Common ESTO structure
    building never registered that exact ``(component_esto_flow,
    component_esto_product)`` pair as any common row's component for a given
    scope, so there is no ``common_row_id`` to fetch a converted value
    through (see the raw-fallback contribution in
    :func:`validate_source_parent_anchors`). This is the source system's own
    figure, in its own accounting convention -- exactly the convention
    ``parent_value`` is already computed in from this same raw frame, so no
    sign/unit conversion is needed to compare the two directly. ``source_df``
    must already carry literal ``source_flow``/``source_product`` columns
    (unlike ``axis_col``/``other_col`` elsewhere in this module, these are
    never axis-swapped -- ``frontier_components`` and ``direct_index`` key on
    the same two literal names regardless of which axis is being validated).
    Output columns: ``source_flow``, ``source_product``, ``economy``,
    ``scenario``, ``year``, ``value``.
    """
    working = source_df[["source_flow", "source_product", "economy", "scenario", "year", "value"]].copy()
    working["source_flow"] = working["source_flow"].fillna("").astype(str).str.strip()
    working["source_product"] = working["source_product"].fillna("").astype(str).str.strip()
    working["economy"] = working["economy"].fillna("").astype(str).str.strip()
    working["scenario"] = working["scenario"].fillna("").astype(str).str.strip()
    working["year"] = pd.to_numeric(working["year"], errors="coerce")
    working["value"] = pd.to_numeric(working["value"], errors="coerce").fillna(0.0)
    working = working[
        working["source_flow"].ne("")
        & working["source_product"].ne("")
        & working["year"].notna()
    ]
    return (
        working.groupby(
            ["source_flow", "source_product", "economy", "scenario", "year"],
            dropna=False, as_index=False,
        )["value"]
        .sum()
    )


def _build_source_internal_bad_pairs(
    raw_pair_values: pd.DataFrame,
    other_children: dict[str, list[str]],
    axis_col: str,
    other_col: str,
    tolerance: float,
) -> pd.DataFrame:
    """Return (axis_col, other_col, economy, scenario, year) rows where a raw
    source node's own reported value disagrees with the sum of its own
    other-axis children, for the exact same validation-axis code.

    This is a pure self-consistency check on one source system's own raw
    file -- no ESTO mapping, no Common ESTO structure, no other source
    system involved. It catches cases like NINTH's own ``09_06_gas_
    processing_plants`` sector reporting ``08_02_lng = 0`` while its own
    ``09_06_02_liquefaction_regasification_plants`` sub-sector child reports
    the real ``08_02_lng = +4218.81`` -- an internal rollup defect in the raw
    file itself: the same physical quantity, reported two different ways at
    two depths of the SAME source's own tree, that no mapping or tree fix in
    this repo can reconcile. Rows whose frontier draws on such a pair are
    not evidence of a genuine mapping problem; see the caller for how this
    reclassifies their status.
    """
    if not other_children:
        return pd.DataFrame(columns=[axis_col, other_col, "economy", "scenario", "year"])
    child_to_parent = {
        child: parent for parent, children in other_children.items() for child in children
    }
    rpv = raw_pair_values.assign(_other_parent=raw_pair_values[other_col].map(child_to_parent))
    children_side = rpv[rpv["_other_parent"].notna()]
    if children_side.empty:
        return pd.DataFrame(columns=[axis_col, other_col, "economy", "scenario", "year"])
    children_sum = (
        children_side.groupby(
            [axis_col, "_other_parent", "economy", "scenario", "year"], dropna=False, as_index=False,
        )["value"]
        .sum()
        .rename(columns={"_other_parent": other_col, "value": "_children_sum"})
    )
    own_value = rpv[[axis_col, other_col, "economy", "scenario", "year", "value"]].rename(
        columns={"value": "_own_value"}
    )
    compare = own_value.merge(
        children_sum, on=[axis_col, other_col, "economy", "scenario", "year"], how="inner",
    )
    if compare.empty:
        return pd.DataFrame(columns=[axis_col, other_col, "economy", "scenario", "year"])
    abs_error = (compare["_own_value"] - compare["_children_sum"]).abs()
    bad_mask = abs_error > tolerance * compare["_own_value"].abs().clip(lower=1.0)
    return compare.loc[bad_mask, [axis_col, other_col, "economy", "scenario", "year"]].drop_duplicates()


def _mapped_descendants(
    code: str,
    other_axis_value: str,
    children: dict[str, list[str]],
    direct_index: dict[tuple[str, str], pd.DataFrame],
    empty_frame: pd.DataFrame,
    cache: dict[tuple[str, str], tuple[pd.DataFrame, list[str]]],
    has_data_pairs: set[tuple[str, str]] | None = None,
    visited: frozenset = frozenset(),
) -> tuple[pd.DataFrame, list[str]]:
    """Resolve an absent intermediate source node to mapped descendants.

    Result depends only on ``(code, other_axis_value)`` for a fixed source
    system/axis, so it is memoized in ``cache``. ``direct_index`` is a prebuilt
    ``(axis_value, other_axis_value) -> rows`` lookup replacing a per-call scan
    of the mapping frame. ``visited`` tracks the current ancestor chain purely as
    a cycle backstop; trees are acyclic in practice, so the cached results are
    exact for real data.

    ``has_data_pairs`` is a prebuilt set of
    ``(component_esto_flow, component_esto_product)`` pairs that actually have
    at least one real comparison row for the current source system (across the
    scopes it participates in). A raw source node can have its own direct
    identity mapping (``direct_index`` hit) while Common ESTO structure
    building has nonetheless pruned every comparison row for that exact
    component pair (e.g. a subtotal row whose value is entirely explained by,
    and de-duplicated against, a single real child, such as ESTO's
    ``16.01 Commercial and public services`` vs. its only real child
    ``16.01.99 ... unallocated``). Treating that direct hit as "resolved" would
    silently contribute zero to the frontier without being flagged missing.
    When the direct match has no real data and the node still has raw-tree
    children, descend into them instead so the real, mapped descendant(s) are
    used -- and anything genuinely absent is still flagged missing/evidenced
    as before. Nodes whose direct match does have real data (e.g. a
    NON_EXPANDING rollup subtotal that legitimately differs from the literal
    sum of its raw-tree children) are unaffected: this only overrides the
    direct match when that match is confirmed to be numerically inert for
    every comparison row we have.
    """
    key = (code, other_axis_value)
    cached = cache.get(key)
    if cached is not None:
        return cached
    direct = direct_index.get(key)
    direct_has_data = False
    if direct is not None and has_data_pairs:
        direct_pairs = set(
            zip(
                direct["component_esto_flow"].astype(str),
                direct["component_esto_product"].astype(str),
            )
        )
        direct_has_data = not direct_pairs.isdisjoint(has_data_pairs)
    elif direct is not None:
        direct_has_data = True
    can_descend = code in children and code not in visited
    if direct is not None and (direct_has_data or not can_descend):
        result = (direct, [])
    elif not can_descend:
        # Missing leaf, or a cycle re-entering an ancestor: flag as unresolved.
        result = (empty_frame, [code])
    else:
        frames: list[pd.DataFrame] = []
        missing: list[str] = []
        next_visited = visited | {code}
        for child in children[code]:
            resolved, child_missing = _mapped_descendants(
                child, other_axis_value, children, direct_index, empty_frame, cache,
                has_data_pairs, next_visited,
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
    exclude_parents: set[str] | None = None,
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

    ``exclude_parents`` drops named ``NON_EXPANDING`` / ``DETACHED`` rollup
    subtotal labels (e.g. ``09.06 Gas processing plants``) from being treated
    as ordinary additive parents in the raw source tree -- mirroring the
    Common ESTO recursive validator's ``exclude_parents`` fix. This only
    removes them from independent parent validation (``parents_present``);
    they remain fully present in the raw tree's parent/child edges, so they
    are still reachable as frontier components when *another* ancestor's
    frontier needs to descend into them. Callers should
    pass the same rolled-flow-label set built from
    ``non_expanding_rollups.load_rollup_mode_labels`` (filtered to
    ``NON_EXPANDING``/``DETACHED`` modes) that they already build for
    :func:`build_dataset_tree_structure.validate_common_esto_recursive_sums`.
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
        # Source-system can arrive as a pandas Categorical after concatenating
        # the raw inputs. Mapping categorical values directly to set objects
        # can make pandas treat the sets as category labels and raise
        # ``TypeError: unhashable type: 'set'``. Normalize to plain strings
        # before applying the per-system year sets.
        keep = source["source_system"].astype(str).map(years_by_system)
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
        system_mappings = mappings[mappings["source_system"] == source_system].copy()
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
        # Component pairs that actually have at least one real comparison row
        # for this source system, across the scopes it participates in.
        # Common ESTO structure building can prune a raw node's own literal
        # comparison row as a duplicate of a child's (see
        # ``_mapped_descendants``); this lets the frontier resolver tell that
        # case apart from a node whose direct value is genuinely real, using
        # actual data availability rather than tree/mapping structure alone.
        ids_with_data = set(system_comparison["common_row_id"].astype(str))
        scoped_common_map = common_map[common_map["comparison_scope"].isin(applicable_scopes)]
        has_data_mask = scoped_common_map["common_row_id"].astype(str).isin(ids_with_data)
        has_data_pairs = set(
            zip(
                scoped_common_map.loc[has_data_mask, "component_esto_flow"].astype(str),
                scoped_common_map.loc[has_data_mask, "component_esto_product"].astype(str),
            )
        )
        for axis, tree_axis in [("flow", "flow"), ("product", "product")]:
            # LEAP and Ninth trees use sector/fuel terminology.
            if dataset in {"leap", "ninth"}:
                tree_axis = "sector" if axis == "flow" else "fuel"
            axis_aliases = build_tree_code_aliases(source_tree_df, dataset, tree_axis)
            canonical_tree = source_tree_df.copy()
            tree_mask = (
                canonical_tree["dataset"].astype(str).str.casefold().eq(dataset)
                & canonical_tree["axis"].astype(str).str.casefold().eq(tree_axis)
            )
            canonical_tree.loc[tree_mask, "code"] = canonicalize_tree_codes(
                canonical_tree.loc[tree_mask, "code"], axis_aliases
            )
            canonical_tree.loc[tree_mask, "parent_code"] = canonicalize_tree_codes(
                canonical_tree.loc[tree_mask, "parent_code"], axis_aliases
            )
            children = _children_map(canonical_tree, dataset, tree_axis)
            axis_col = "source_product" if axis == "product" else "source_flow"
            other_col = "source_flow" if axis == "product" else "source_product"
            other_tree_axis = "product" if other_col == "source_product" else "flow"
            if dataset in {"leap", "ninth"}:
                other_tree_axis = "fuel" if other_col == "source_product" else "sector"
            other_aliases = build_tree_code_aliases(source_tree_df, dataset, other_tree_axis)
            other_tree_mask = (
                canonical_tree["dataset"].astype(str).str.casefold().eq(dataset)
                & canonical_tree["axis"].astype(str).str.casefold().eq(other_tree_axis)
            )
            canonical_tree.loc[other_tree_mask, "code"] = canonicalize_tree_codes(
                canonical_tree.loc[other_tree_mask, "code"], other_aliases
            )
            canonical_tree.loc[other_tree_mask, "parent_code"] = canonicalize_tree_codes(
                canonical_tree.loc[other_tree_mask, "parent_code"], other_aliases
            )
            axis_source = system_source.copy()
            axis_source[axis_col] = canonicalize_tree_codes(axis_source[axis_col], axis_aliases)
            axis_source[other_col] = canonicalize_tree_codes(axis_source[other_col], other_aliases)
            system_mappings[axis_col] = canonicalize_tree_codes(system_mappings[axis_col], axis_aliases)
            system_mappings[other_col] = canonicalize_tree_codes(system_mappings[other_col], other_aliases)
            if source_system == "LEAP" and axis == "flow":
                own_use_flows = _leap_own_use_rollup_flows(children, system_mappings)
                own_use_mask = axis_source["source_flow"].astype(str).isin(own_use_flows)
                axis_source.loc[own_use_mask, "value"] = -axis_source.loc[own_use_mask, "value"].abs()
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
            parent_index, tree_issues = build_tree_index(canonical_tree, dataset, other_tree_axis)
            if not tree_issues.empty:
                bad = tree_issues[tree_issues["issue_type"].isin(["ambiguous_parent", "cycle"])]
                if not bad.empty:
                    raise ValueError(f"Invalid source tree for {dataset}/{other_tree_axis}: {bad.head(10).to_dict('records')}")
            source_evidence_lookup = _build_source_evidence_lookup(
                axis_source,
                axis_col,
                other_col,
                parent_index,
            )
            raw_pair_values = _build_raw_pair_values(axis_source)
            other_children = _children_map(canonical_tree, dataset, other_tree_axis)
            # Checks whether an OTHER-axis node (e.g. a sector) reconciles
            # with its own other-axis children, for a fixed validation-axis
            # code. This is deliberately one-directional: checking whether a
            # VALIDATION-axis node reconciles with its own validation-axis
            # children would just re-derive the main parent-vs-frontier
            # check this loop already computes below, and would reclassify
            # every genuine mismatch as "source-internal" instead of
            # "failed". The other-axis direction is genuinely independent
            # information -- a structurally different tree -- so it can
            # corroborate without being circular.
            source_internal_bad_pairs = _build_source_internal_bad_pairs(
                raw_pair_values, other_children, axis_col, other_col, tolerance,
            )
            mapped_pairs = set(zip(system_mappings["source_flow"].astype(str), system_mappings["source_product"].astype(str)))
            # Raw source hierarchies (notably Ninth) often report the same
            # numeric total as literal separate rows at multiple depths at
            # once -- a leaf's "x"-rollup subtotal duplicates the value of an
            # ancestor's own "x"-rollup subtotal whenever no other sibling
            # contributes. If an unmapped leaf gets remapped onto such an
            # ancestor pair, the leaf row and the ancestor's own already-
            # present literal row land in the same groupby key below and get
            # summed together, silently doubling the true value. Track the
            # pairs that already have their own literal row in this axis'
            # source slice so the remap can be suppressed in that case --
            # the leaf is left at its own (likely unanchorable) code instead
            # of being folded into a total that already accounts for it.
            literal_pairs = set(
                zip(
                    axis_source["source_flow"].astype(str),
                    axis_source["source_product"].astype(str),
                )
            )
            pair_remap: dict[tuple[str, str], tuple[str, str]] = {}
            for flow, product in axis_source[["source_flow", "source_product"]].drop_duplicates().itertuples(index=False):
                original_pair = (str(flow), str(product))
                resolved = resolve_nearest_mapped_pair(
                    flow, product, mapped_pairs,
                    "product" if other_col == "source_product" else "flow",
                    parent_index,
                )
                if resolved["status"] != "resolved":
                    resolved = resolve_parent_to_mapped_other_axis(
                        flow,
                        product,
                        children,
                        mapped_pairs,
                        "product" if other_col == "source_product" else "flow",
                        parent_index,
                    )
                if resolved["status"] == "resolved":
                    target_pair = (resolved["flow"], resolved["product"])
                    if target_pair != original_pair and target_pair in literal_pairs:
                        # The resolved ancestor already has its own literal
                        # row for this exact (flow, product) key -- remapping
                        # would double-count against it. Leave unmapped.
                        pair_remap[original_pair] = original_pair
                    else:
                        pair_remap[original_pair] = target_pair
                else:
                    pair_remap[original_pair] = original_pair
            remapped = [pair_remap[(str(flow), str(product))] for flow, product in axis_source[["source_flow", "source_product"]].itertuples(index=False)]
            axis_source["source_flow"] = [pair[0] for pair in remapped]
            axis_source["source_product"] = [pair[1] for pair in remapped]
            descendant_cache: dict[tuple[str, str], tuple[pd.DataFrame, list[str]]] = {}
            # Frontier resolution depends only on (parent_code, other_axis_value),
            # not on economy/scenario/year or scope; cache across groups.
            frontier_cache: dict[tuple[str, str], tuple[pd.DataFrame, list[str]]] = {}
            frontier_ids_cache: dict[tuple[str, str, str], tuple[list, bool, list]] = {}
            # --- Vectorized parent aggregation (replaces the per-parent /
            # per-group / per-scope Python loop). Sum every parent's value,
            # positive part, and negative part for every
            # (parent_code, economy, scenario, year, other_axis_value) in one
            # pass instead of re-filtering axis_source per parent. ---
            parents_present = set(children.keys()) - (exclude_parents or set())
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
            # A resolved frontier component still has a real, correct raw
            # value from this same source system even when there is no way
            # to fetch a converted value for it through common_row_id ->
            # comparison_df, whether because Common ESTO structure building
            # never declared this exact pair as a component of any common
            # row at all (e.g. ESTO's own "09.01 Main activity producer" for
            # a product only NINTH/LEAP can report combined with
            # "09.02 Autoproducers"), or because it IS a declared component
            # but this source system's own comparison-data export has zero
            # rows for it across every economy/year (``has_data_pairs`` --
            # e.g. ESTO's "16.01 Biogas" under a flow where NINTH reports a
            # value but ESTO's own export simply never wrote a row, even
            # though ESTO's raw figure is real and the true reason the
            # parent has a nonzero total). Track those pairs per
            # (parent_code, other_axis_value, scope) so their own raw figure
            # can be added into frontier_sum below instead of the resolved
            # component being silently dropped.
            raw_fallback_rows: list[tuple[str, str, str, str, str]] = []
            # Every resolved frontier leaf, regardless of how its value gets
            # fetched, checked below against source_internal_bad_pairs -- a
            # row whose frontier touches a pair where this source's OWN
            # other-axis rollup contradicts its own raw children (see
            # _build_source_internal_bad_pairs) is not evidence of a mapping
            # problem; it inherits that status instead of "failed".
            frontier_leaf_rows: list[tuple[str, str, str, str]] = []
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
                            empty_mapping, descendant_cache, has_data_pairs,
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
                if not source_internal_bad_pairs.empty:
                    for sf, sp in frontier_components[["source_flow", "source_product"]].drop_duplicates().itertuples(index=False):
                        frontier_leaf_rows.append((pcode, oas, sf, sp))
                for scope in applicable_scopes:
                    ids_key = (pcode, oas, scope)
                    cached = frontier_ids_cache.get(ids_key)
                    if cached is None:
                        merged = frontier_components.merge(
                            scoped_maps[scope],
                            on=["component_esto_flow", "component_esto_product"],
                            how="left",
                        )
                        has_row_id = merged["common_row_id"].notna()
                        has_real_data = has_row_id & merged["common_row_id"].astype(str).isin(ids_with_data)
                        frontier_ids = merged.loc[has_real_data, "common_row_id"].unique().tolist()
                        # Structural registration (any common_row_id at all,
                        # data or not) is the gate below; the fallback
                        # candidates are every component that is NOT
                        # contributing a real matched value, whether
                        # unregistered or registered-but-dataless.
                        structurally_registered = bool(has_row_id.any())
                        fallback_candidates = merged.loc[
                            ~has_real_data, ["source_flow", "source_product"]
                        ].drop_duplicates()
                        cached = (
                            frontier_ids,
                            structurally_registered,
                            list(fallback_candidates.itertuples(index=False, name=None)),
                        )
                        frontier_ids_cache[ids_key] = cached
                    frontier_ids, structurally_registered, fallback_candidates = cached
                    for cid in frontier_ids:
                        fid_rows.append((pcode, oas, scope, str(cid)))
                    # Only fall back to raw values when this exact (parent,
                    # other_axis_value, scope) triple has at least one
                    # component Common ESTO structure building registered at
                    # all: that means this scope does cover this part of the
                    # tree, so a component with no real matched value --
                    # unregistered, or registered but dataless for this
                    # source system -- is a real coverage gap worth filling
                    # from raw data. When NOTHING in the frontier is
                    # registered at all, this scope may simply not apply to
                    # this parent/product at all -- stay
                    # "no_anchorable_common_esto_boundary" rather than
                    # guessing from raw data alone (see
                    # test_missing_common_boundary_is_unanchorable_even_when_source_value_is_nonzero).
                    fids_empty_map[ids_key] = not (frontier_ids or (structurally_registered and fallback_candidates))
                    if structurally_registered:
                        for sflow, sprod in fallback_candidates:
                            raw_fallback_rows.append((pcode, oas, scope, sflow, sprod))

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

            # --- Raw-fallback frontier contribution --------------------------
            # Add each unregistered resolved component's own raw value
            # directly (see raw_fallback_rows above), keyed on the exact
            # (source_flow, source_product, economy, scenario, year) this
            # source system actually reported -- the same convention
            # parent_value is already computed in, so it combines with the
            # common-row-matched contribution above without any conversion.
            if raw_fallback_rows:
                raw_pairs_df = pd.DataFrame(
                    raw_fallback_rows,
                    columns=["parent_code", "_oas", "comparison_scope", "source_flow", "source_product"],
                ).drop_duplicates()
                raw_exploded = base[
                    ["parent_code", "_oas", "comparison_scope", "economy", "scenario", "year"]
                ].merge(raw_pairs_df, on=["parent_code", "_oas", "comparison_scope"], how="inner")
                raw_matched = raw_exploded.merge(
                    raw_pair_values,
                    on=["source_flow", "source_product", "economy", "scenario", "year"],
                    how="inner",
                )
            else:
                raw_matched = base.iloc[0:0].assign(value=pd.Series(dtype=float))

            if not raw_matched.empty:
                raw_matched = raw_matched.assign(
                    _rpos=raw_matched["value"].where(raw_matched["value"] > 0, 0.0),
                    _rneg=raw_matched["value"].where(raw_matched["value"] < 0, 0.0),
                )
                raw_fsum = (
                    raw_matched.groupby(
                        ["parent_code", "_oas", "comparison_scope", "economy", "scenario", "year"],
                        dropna=False, sort=False,
                    )
                    .agg(
                        raw_fallback_sum=("value", "sum"),
                        raw_fallback_positive_sum=("_rpos", "sum"),
                        raw_fallback_negative_sum=("_rneg", "sum"),
                        raw_fallback_row_count=("value", "size"),
                    )
                    .reset_index()
                )
                base = base.merge(
                    raw_fsum,
                    on=["parent_code", "_oas", "comparison_scope", "economy", "scenario", "year"],
                    how="left",
                )
            else:
                for col in ["raw_fallback_sum", "raw_fallback_positive_sum",
                            "raw_fallback_negative_sum", "raw_fallback_row_count"]:
                    base[col] = 0.0

            base["frontier_sum"] += base["raw_fallback_sum"].fillna(0.0)
            base["frontier_positive_sum"] += base["raw_fallback_positive_sum"].fillna(0.0)
            base["frontier_negative_sum"] += base["raw_fallback_negative_sum"].fillna(0.0)
            base["frontier_row_count"] += base["raw_fallback_row_count"].fillna(0).astype(int)
            base["_matched"] += base["raw_fallback_row_count"].fillna(0)
            base = base.drop(columns=[
                "raw_fallback_sum", "raw_fallback_positive_sum",
                "raw_fallback_negative_sum", "raw_fallback_row_count",
            ])

            # --- Source-internal rollup inconsistency -------------------------
            # A row whose frontier touches a pair where this source's OWN
            # other-axis rollup contradicts its own raw children (e.g. NINTH's
            # own sector-level "08_02_lng" reads 0 while its own more granular
            # sub-sector reports the real +4218.81) is not evidence of a
            # mapping problem -- no tree/mapping change in this repo can fix a
            # source file disagreeing with itself. Flag it distinctly instead
            # of "failed" below.
            # Deliberately checks only the frontier's LEAF components, not
            # this row's own (parent_code, other_axis_value) pair: the row's
            # own pair is exactly what the main parent-vs-frontier check
            # below already evaluates, so treating its own mismatch as
            # "source-internal" would be circular and could silently
            # swallow a genuine, single-sided error in the parent's own
            # declared value (see
            # test_leaf_remap_onto_ancestor_with_own_row_still_fails_on_real_mismatch,
            # which pins exactly this: a corrupted parent value must still
            # surface as a real failure, not get waved off as "the source
            # disagrees with itself").
            bad_keys: set[tuple[str, str, str, str, str]] = set()
            if frontier_leaf_rows and not source_internal_bad_pairs.empty:
                leaf_df = pd.DataFrame(
                    frontier_leaf_rows, columns=["parent_code", "_oas", "source_flow", "source_product"],
                ).drop_duplicates()
                leaf_exploded = base[
                    ["parent_code", "_oas", "economy", "scenario", "year"]
                ].drop_duplicates().merge(leaf_df, on=["parent_code", "_oas"], how="inner")
                leaf_hits = leaf_exploded.merge(
                    source_internal_bad_pairs,
                    on=["source_flow", "source_product", "economy", "scenario", "year"],
                    how="inner",
                )
                bad_keys.update(
                    zip(leaf_hits["parent_code"], leaf_hits["_oas"], leaf_hits["economy"], leaf_hits["scenario"], leaf_hits["year"])
                )
            base["_source_internal_inconsistent"] = [
                (pc, oa, ec, sc, yr) in bad_keys
                for pc, oa, ec, sc, yr in zip(
                    base["parent_code"], base["_oas"], base["economy"], base["scenario"], base["year"],
                )
            ]

            # --- Shared-frontier group combination --------------------------
            # Multiple raw source products can legitimately map onto the SAME
            # Common ESTO aggregate row for a given comparison scope (e.g. six
            # distinct raw LEAP petroleum products collapsing onto one shared
            # "07.12-07.17 Petroleum products" row under esto_leap_ninth,
            # because Ninth's raw data cannot distinguish the sub-products).
            # In that case every member's frontier_sum already reflects the
            # WHOLE shared group's total, so comparing each raw product's own
            # individual parent_value against that shared total can only ever
            # reconcile for a member whose value happens to equal the group's
            # combined total.
            #
            # Grouping is by CONNECTED COMPONENT over shared common_row_ids,
            # not exact signature equality. A source system can legitimately
            # register only a partial, asymmetric subset of a semantically
            # related product family's common rows per flow child -- e.g.
            # ESTO's "10.01 Own Use" flow children each register a different
            # subset of the same 7 coal by-products' shared Common ESTO row:
            # "10.01.01" registers {02.01, 02.03, 02.07}, "10.01.11" registers
            # only {02.01}, others register all 7. Exact-equality grouping
            # split these into several partial groups that each got compared
            # against whichever partial subset of flow children happened to
            # have real data for a given economy/year -- a coincidence of
            # arithmetic, not a real reconciliation. Two other_axis_values now
            # belong in the same group whenever their registered
            # common_row_id sets overlap at all, transitively (union-find),
            # so the old exact-equality case is subsumed as the special case
            # where every signature in a component happens to be identical.
            uf_parent: dict[Any, Any] = {}

            def _uf_find(x: Any) -> Any:
                root = x
                while uf_parent[root] != root:
                    root = uf_parent[root]
                while uf_parent[x] != root:
                    uf_parent[x], x = root, uf_parent[x]
                return root

            def _uf_union(a: Any, b: Any) -> None:
                ra, rb = _uf_find(a), _uf_find(b)
                if ra != rb:
                    uf_parent[ra] = rb

            node_ids: dict[tuple[str, str, str], list[str]] = {}
            for (gpcode, goas, gscope), (ids, _structurally_registered, _fallback_candidates) in frontier_ids_cache.items():
                if not ids:
                    continue
                sig = sorted({str(cid) for cid in ids})
                node = (gpcode, gscope, goas)
                node_ids[node] = sig
                uf_parent.setdefault(node, node)
                for cid in sig:
                    id_node = ("__id__", gpcode, gscope, cid)
                    uf_parent.setdefault(id_node, id_node)
                    _uf_union(node, id_node)

            component_members: dict[Any, list[tuple[str, str, str]]] = {}
            for node in node_ids:
                component_members.setdefault(_uf_find(node), []).append(node)


            # Each connected component's group id is keyed on the UNION of
            # every common_row_id touched by any of its members, not on any
            # single member's own (possibly partial) signature.
            shared_groups: dict[str, dict[str, Any]] = {}
            for members in component_members.values():
                if len(members) <= 1:
                    continue
                gpcode, gscope = members[0][0], members[0][1]
                oas_members = sorted(m[2] for m in members)
                union_ids = sorted({cid for m in members for cid in node_ids[m]})
                group_id = f"{gpcode}||{gscope}||{'|'.join(union_ids)}"
                shared_groups[group_id] = {
                    "parent_code": gpcode,
                    "scope": gscope,
                    "members": oas_members,
                    "union_ids": union_ids,
                }

            # Index raw_fallback_rows by (parent_code, other_axis_value,
            # scope) once so the per-group fold-in below is O(1) per member
            # instead of an O(members * raw_fallback_rows) scan.
            raw_fallback_index: dict[tuple[str, str, str], set[tuple[str, str]]] = {}
            for pc2, oa2, sc2, sflow, sprod in raw_fallback_rows:
                raw_fallback_index.setdefault((pc2, oa2, sc2), set()).add((sflow, sprod))

            skip_rows = pd.Series(False, index=base.index)
            if shared_groups:
                group_id_of: dict[tuple[str, str, str], str] = {}
                primary_of: dict[str, str] = {}
                label_of: dict[str, str] = {}
                for group_id, info in shared_groups.items():
                    members = info["members"]
                    primary_of[group_id] = members[0]
                    label_of[group_id] = " + ".join(members)
                    for member in members:
                        group_id_of[(info["parent_code"], info["scope"], member)] = group_id
                base["_shared_group_id"] = [
                    group_id_of.get((pc, sc, oa))
                    for pc, sc, oa in zip(base["parent_code"], base["comparison_scope"], base["_oas"])
                ]
                grouped_mask = base["_shared_group_id"].notna()
                if grouped_mask.any():
                    is_primary = grouped_mask & (
                        base["_oas"] == base["_shared_group_id"].map(lambda gid: primary_of.get(gid, ""))
                    )
                    combine_cols = ["parent_value", "parent_positive_value", "parent_negative_value"]
                    group_sums = (
                        base.loc[grouped_mask]
                        .groupby(["_shared_group_id", "economy", "scenario", "year"])[combine_cols]
                        .transform("sum")
                    )
                    primary_rows = grouped_mask & is_primary
                    for col in combine_cols:
                        base.loc[primary_rows, col] = group_sums.loc[primary_rows, col]
                    base.loc[primary_rows, "other_axis_value"] = base.loc[
                        primary_rows, "_shared_group_id"
                    ].map(label_of)

                    # Recompute the group's frontier_sum from the union of
                    # every common_row_id touched by any member, each summed
                    # exactly once -- reusing one member's own frontier_sum
                    # (correct only when every member's registered id set was
                    # identical) would double-count ids shared by several
                    # members, or omit ids only some members registered, now
                    # that a component can span overlapping-but-not-identical
                    # signatures. Built as an explicit (group_id, economy,
                    # scenario, year) -> values map and applied via row-key
                    # lookup (not pd.merge) so ``base``'s index -- which the
                    # boolean masks above already depend on -- is preserved.
                    group_frontier_map: dict[tuple[str, Any, Any, Any], tuple[float, float, float, int]] = {}
                    for group_id, info in shared_groups.items():
                        scope = info["scope"]
                        union_ids = info["union_ids"]
                        if not union_ids:
                            continue
                        id_hits = system_comparison[
                            (system_comparison["comparison_scope"] == scope)
                            & (system_comparison["common_row_id"].isin(union_ids))
                        ]
                        member_fallback_pairs: set[tuple[str, str]] = set()
                        for member in info["members"]:
                            member_fallback_pairs |= raw_fallback_index.get(
                                (info["parent_code"], member, scope), set()
                            )
                        parts = [id_hits[["economy", "scenario", "year", "value"]]]
                        if member_fallback_pairs:
                            fb_df = pd.DataFrame(
                                sorted(member_fallback_pairs), columns=["source_flow", "source_product"],
                            )
                            fb_hits = fb_df.merge(
                                raw_pair_values, on=["source_flow", "source_product"], how="inner",
                            )
                            if not fb_hits.empty:
                                parts.append(fb_hits[["economy", "scenario", "year", "value"]])
                        combined = pd.concat(parts, ignore_index=True) if len(parts) > 1 else parts[0]
                        if combined.empty:
                            continue
                        combined = combined.assign(
                            _gpos=combined["value"].where(combined["value"] > 0, 0.0),
                            _gneg=combined["value"].where(combined["value"] < 0, 0.0),
                        )
                        gsum = (
                            combined.groupby(["economy", "scenario", "year"], dropna=False, sort=False)
                            .agg(
                                g_sum=("value", "sum"),
                                g_pos=("_gpos", "sum"),
                                g_neg=("_gneg", "sum"),
                                g_count=("value", "size"),
                            )
                            .reset_index()
                        )
                        for econ, scen, yr, gsum_v, gpos_v, gneg_v, gcount_v in gsum.itertuples(index=False):
                            group_frontier_map[(group_id, econ, scen, yr)] = (
                                gsum_v, gpos_v, gneg_v, int(gcount_v)
                            )

                    if group_frontier_map:
                        row_keys = list(
                            zip(base["_shared_group_id"], base["economy"], base["scenario"], base["year"])
                        )
                        recomputed = [group_frontier_map.get(k) for k in row_keys]
                        has_recompute = pd.Series(
                            [v is not None for v in recomputed], index=base.index,
                        )
                        apply_mask = primary_rows & has_recompute
                        if apply_mask.any():
                            recompute_cols = [
                                "frontier_sum", "frontier_positive_sum",
                                "frontier_negative_sum", "frontier_row_count",
                            ]
                            for col_idx, col in enumerate(recompute_cols):
                                values = pd.Series(
                                    [v[col_idx] if v is not None else None for v in recomputed],
                                    index=base.index,
                                )
                                base.loc[apply_mask, col] = values.loc[apply_mask]
                            base["frontier_row_count"] = base["frontier_row_count"].astype(int)

                    skip_rows = grouped_mask & ~is_primary
                base = base.drop(columns=["_shared_group_id"])

            pcoa = list(zip(base["parent_code"], base["_oas"]))
            base["missing_expected_children"] = [missing_join_map[k] for k in pcoa]
            has_missing = np.array([has_missing_map[k] for k in pcoa])
            missing_child_counts = np.zeros(len(base), dtype=int)
            missing_nonzero_counts = np.zeros(len(base), dtype=int)
            missing_nonzero_abs = np.zeros(len(base), dtype=float)
            missing_rows = base.index[has_missing]
            evidence_columns = ["missing_expected_children", "_oas", "economy", "scenario", "year"]
            for row_index, values in base.loc[missing_rows, evidence_columns].iterrows():
                missing_children = [
                    child for child in str(values["missing_expected_children"]).split("|") if child
                ]
                missing_child_counts[row_index] = len(missing_children)
                for child in missing_children:
                    axis_value, other_value = child, str(values["_oas"])
                    evidence = source_evidence_lookup.get(
                        (
                            axis_value,
                            other_value,
                            str(values["economy"]),
                            str(values["scenario"]),
                            int(values["year"]),
                        ),
                        0.0,
                    )
                    if evidence > NONZERO_SOURCE_EVIDENCE_TOLERANCE:
                        missing_nonzero_counts[row_index] += 1
                        missing_nonzero_abs[row_index] += evidence
            base["missing_expected_child_count"] = missing_child_counts
            base["missing_nonzero_child_count"] = missing_nonzero_counts
            base["missing_nonzero_child_abs"] = missing_nonzero_abs
            base["missing_zero_or_absent_child_count"] = (
                missing_child_counts - missing_nonzero_counts
            )
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
            nonzero_missing = has_missing & (missing_nonzero_counts > 0)
            zero_only_missing = has_missing & (missing_nonzero_counts == 0)
            incomplete_gap = nonzero_missing & tol_exceeded
            parent_child_inconsistency = zero_only_missing & tol_exceeded
            zero_parent_without_rows = rows_empty & ~tol_exceeded
            # A source-internal rollup contradiction takes priority over
            # every other outcome: if this same source's own data disagrees
            # with itself at a pair the frontier depends on, no comparison
            # this validator computes from it can be trusted either way,
            # pass or fail -- see _build_source_internal_bad_pairs.
            source_internal_inconsistent = base["_source_internal_inconsistent"].to_numpy()
            conditions = [
                source_internal_inconsistent,
                fids_empty,
                zero_parent_without_rows,
                incomplete_reconciles & nonzero_missing,
                incomplete_reconciles & zero_only_missing,
                parent_child_inconsistency,
                incomplete_gap,
                rows_empty,
                tol_exceeded,
            ]
            base["status"] = np.select(
                conditions,
                ["skipped", "skipped", "skipped", "passed", "passed", "failed", "failed", "failed", "failed"],
                default="passed",
            )
            base["reason"] = np.select(
                conditions,
                ["source_internal_recursive_sum_inconsistency",
                 "no_anchorable_common_esto_boundary", "no_observed_source_frontier",
                 "within_tolerance_incomplete_frontier", "within_tolerance_zero_only_missing_children",
                 "parent_child_source_inconsistency", "incomplete_frontier",
                 "frontier_rows_absent", "difference_exceeds_tolerance"],
                default="within_tolerance",
            )
            base = base.drop(columns=["_source_internal_inconsistent"])
            if skip_rows.any():
                # Non-primary members of a shared-frontier group: the primary
                # row above already carries the combined comparison, so these
                # are not independent numeric findings.
                base.loc[skip_rows, "status"] = "skipped"
                base.loc[skip_rows, "reason"] = "grouped_with_shared_frontier_sibling"
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
        return pd.DataFrame(columns=ANCHOR_COLUMNS + ANCHOR_EXCEPTION_COLUMNS)
    return _augment_with_data_quality_exceptions(pd.concat(records_frames, ignore_index=True))


def _augment_with_data_quality_exceptions(
    result: pd.DataFrame,
    workbook_path: Path = EXCEPTION_WORKBOOK_PATH,
    sheet_name: str = DATA_QUALITY_EXCEPTION_SHEET,
) -> pd.DataFrame:
    """Mark reviewed source-data exceptions as skipped, while retaining evidence.

    A reviewed exception is not a mapping defect, so it must not inflate the
    actionable anchor-failure count.  Keep it visible as ``skipped`` with a
    dedicated reason and its reviewer notes; this is the "skipped but flagged"
    outcome rather than silently dropping the raw evidence.

    Matching requires the row's own ``parent_value`` to be numerically within
    tolerance of the value recorded when the exception was reviewed, on top
    of the usual code/label match -- so if the underlying data later changes
    (a source correction, or a different bug landing on the same key), the
    exception stops applying instead of silently continuing to hide it. See
    ``codebase.mapping_issue_exceptions.matching_exception_row``'s
    ``numeric_tolerance_columns``.
    """
    result = result.copy()
    result["known_data_quality_exception"] = False
    result["data_quality_exception_notes"] = ""
    result["exception_resolution"] = ""
    exception_df = load_exception_sheet(sheet_name, workbook_path=workbook_path)
    if exception_df.empty or result.empty:
        return result

    failed = result[result["status"] == "failed"].copy()
    if failed.empty:
        return result

    # The exception sheet is keyed by the five categorical anchor fields and
    # additionally records the reviewed parent value.  The previous generic
    # matcher scanned every enabled exception row for every failed anchor
    # record, which became the dominant cost of all-economy validation.  Use a
    # vectorized keyed merge for the ordinary exact-key case, retaining the
    # generic matcher only for the uncommon prefix-wildcard case.
    key_columns = [
        column
        for column in [
            "source_system", "validation_axis", "parent_code",
            "other_axis_value", "economy",
        ]
        if column in failed.columns and column in exception_df.columns
    ]
    numeric_column = "parent_value"
    wildcard_mask = pd.Series(False, index=exception_df.index)
    for column in key_columns:
        wildcard_mask |= exception_df[column].astype(str).str.strip().str.endswith("*")

    def _normalised(series: pd.Series) -> pd.Series:
        return series.fillna("").astype(str).str.strip()

    exact_exceptions = exception_df.loc[~wildcard_mask].copy()
    matched = pd.DataFrame()
    if key_columns and not exact_exceptions.empty:
        left = failed[key_columns + [numeric_column]].copy()
        left["_result_index"] = left.index
        right_columns = key_columns + [numeric_column, "notes"]
        right = exact_exceptions[[column for column in right_columns if column in exact_exceptions.columns]].copy()
        for column in key_columns:
            left[column] = _normalised(left[column])
            right[column] = _normalised(right[column])
        left[numeric_column] = pd.to_numeric(left[numeric_column], errors="coerce")
        right[numeric_column] = pd.to_numeric(right[numeric_column], errors="coerce")
        matched = left.merge(right, on=key_columns, how="inner", suffixes=("_candidate", "_exception"))
        if not matched.empty:
            candidate_values = matched[f"{numeric_column}_candidate"]
            exception_values = matched[f"{numeric_column}_exception"]
            numeric_match = (
                candidate_values.notna()
                & exception_values.notna()
                & ((candidate_values - exception_values).abs()
                   <= 0.01 * exception_values.abs().clip(lower=1.0))
            )
            matched = matched.loc[numeric_match].drop_duplicates("_result_index", keep="first")

    # Preserve the generic behaviour for wildcard exception keys and for any
    # future sheet whose shape cannot use the keyed fast path.
    wildcard_exceptions = exception_df.loc[wildcard_mask]
    matched_indices = set(matched["_result_index"].tolist()) if not matched.empty else set()
    if not wildcard_exceptions.empty:
        for idx, row in failed.loc[~failed.index.isin(matched_indices)].iterrows():
            match = matching_exception_row(
                row, wildcard_exceptions,
                numeric_tolerance_columns=frozenset({numeric_column}),
            )
            if match is not None:
                matched = pd.concat([
                    matched,
                    pd.DataFrame([{
                        "_result_index": idx,
                        "notes": str(match.get("notes", "") or "").strip(),
                    }]),
                ], ignore_index=True)

    if not matched.empty:
        notes_by_index = matched.set_index("_result_index")["notes"].fillna("").astype(str).str.strip()
        result.loc[result.index.intersection(notes_by_index.index), "known_data_quality_exception"] = True
        result.loc[result.index.intersection(notes_by_index.index), "data_quality_exception_notes"] = notes_by_index
        result.loc[result.index.intersection(notes_by_index.index), "exception_resolution"] = "skipped_but_flagged"
        result.loc[result.index.intersection(notes_by_index.index), "status"] = "skipped"
        result.loc[result.index.intersection(notes_by_index.index), "reason"] = "reviewed_source_data_exception"
    return result


def _leap_own_use_rollup_flows(
    children: dict[str, list[str]],
    source_mapping: pd.DataFrame,
) -> set[str]:
    """Return LEAP flows whose mapped descendants are exclusively own-use/losses.

    Raw LEAP records these flows as positive consumption, whereas the ESTO
    balance convention records 10.01/10.02 own-use/loss flows as negative.
    Include their structural parents so a manually-created LEAP roll-up and
    its children are compared in the same convention.
    """
    direct_types: dict[str, set[str]] = {}
    for flow, group in source_mapping.groupby("source_flow", dropna=False):
        targets = group["component_esto_flow"].fillna("").astype(str).str.strip()
        types = {
            "own_use" if target.startswith(("10.01", "10.02")) else "other"
            for target in targets if target
        }
        if types:
            direct_types[str(flow)] = types

    cache: dict[str, set[str]] = {}
    def descendant_types(flow: str, seen: frozenset[str] = frozenset()) -> set[str]:
        if flow in cache:
            return cache[flow]
        if flow in seen:
            return set()
        types = set(direct_types.get(flow, set()))
        for child in children.get(flow, []):
            types |= descendant_types(child, seen | {flow})
        cache[flow] = types
        return types

    return {flow for flow in set(children) | set(direct_types) if descendant_types(flow) == {"own_use"}}


def build_leaf_reconciliation_exception_candidates(
    detail_df: pd.DataFrame,
    source_df: pd.DataFrame,
    source_tree_df: pd.DataFrame,
    tolerance: float = 0.01,
) -> pd.DataFrame:
    """Return review-only candidates where leaves reconcile but direct children do not.

    These rows are deliberately *not* applied automatically.  A reviewer may
    copy a candidate into ``source_mismatch_allowed`` after confirming that the
    source hierarchy's intermediate rollup is a valid representation rather
    than a data defect.  The candidate key includes the parent value, so a
    later source-data change cannot inherit the old sign-off.
    """
    required_detail = {
        "status", "validation_axis", "comparison_scope", "source_system", "economy",
        "scenario", "year", "other_axis_value", "parent_code", "parent_value",
    }
    required_source = {
        "source_system", "economy", "scenario", "year", "source_flow",
        "source_product", "value",
    }
    if not required_detail.issubset(detail_df.columns) or not required_source.issubset(source_df.columns):
        return pd.DataFrame(columns=LEAF_RECONCILIATION_CANDIDATE_COLUMNS)

    failed = detail_df[detail_df["status"].astype(str).eq("failed")].copy()
    if failed.empty:
        return pd.DataFrame(columns=LEAF_RECONCILIATION_CANDIDATE_COLUMNS)
    failed["economy"] = _normalize_economy(failed["economy"])
    failed["year"] = pd.to_numeric(failed["year"], errors="coerce")
    failed["parent_value"] = pd.to_numeric(failed["parent_value"], errors="coerce").fillna(0.0)

    source = source_df.copy()
    source["economy"] = _normalize_economy(source["economy"])
    source["year"] = pd.to_numeric(source["year"], errors="coerce")
    source["value"] = pd.to_numeric(source["value"], errors="coerce").fillna(0.0)
    rows: list[dict[str, object]] = []

    for source_system in sorted(failed["source_system"].dropna().astype(str).unique()):
        dataset = source_system.casefold()
        system_source = source[source["source_system"].astype(str).eq(source_system)]
        for validation_axis, tree_axis in [("flow", "flow"), ("product", "product")]:
            if dataset in {"leap", "ninth"}:
                tree_axis = "sector" if validation_axis == "flow" else "fuel"
            axis_failed = failed[
                failed["source_system"].astype(str).eq(source_system)
                & failed["validation_axis"].astype(str).eq(validation_axis)
            ]
            if axis_failed.empty:
                continue
            axis_col = "source_flow" if validation_axis == "flow" else "source_product"
            other_col = "source_product" if validation_axis == "flow" else "source_flow"
            aliases = build_tree_code_aliases(source_tree_df, dataset, tree_axis)
            tree = source_tree_df.loc[
                source_tree_df["dataset"].astype(str).str.casefold().eq(dataset)
                & source_tree_df["axis"].astype(str).str.casefold().eq(tree_axis),
                ["code", "parent_code"],
            ].copy()
            if tree.empty:
                continue
            tree["code"] = canonicalize_tree_codes(tree["code"], aliases)
            tree["parent_code"] = canonicalize_tree_codes(tree["parent_code"], aliases)
            children: dict[str, list[str]] = {}
            for tree_row in tree.itertuples(index=False):
                parent = str(tree_row.parent_code).strip() if pd.notna(tree_row.parent_code) else ""
                if parent:
                    children.setdefault(parent, []).append(str(tree_row.code).strip())
            if not children:
                continue
            axis_source = system_source.copy()
            axis_source[axis_col] = canonicalize_tree_codes(axis_source[axis_col], aliases)
            value_lookup = axis_source.groupby(
                [axis_col, other_col, "economy", "scenario", "year"], dropna=False
            )["value"].sum().to_dict()

            def leaf_descendants(code: str, seen: frozenset[str] = frozenset()) -> list[str]:
                if code in seen:
                    return []
                node_children = children.get(code, [])
                if not node_children:
                    return [code]
                leaves: list[str] = []
                for child in node_children:
                    leaves.extend(leaf_descendants(child, seen | {code}))
                return leaves

            for record in axis_failed.itertuples(index=False):
                parent = str(record.parent_code)
                immediate_children = children.get(parent, [])
                leaves = sorted(set(leaf_descendants(parent)))
                if not immediate_children or set(immediate_children) == set(leaves):
                    continue
                other_value = str(record.other_axis_value)
                context = (str(record.economy), str(record.scenario), record.year)
                direct_sum = sum(float(value_lookup.get((child, other_value, *context), 0.0)) for child in immediate_children)
                leaf_sum = sum(float(value_lookup.get((leaf, other_value, *context), 0.0)) for leaf in leaves)
                parent_value = float(record.parent_value)
                direct_residual = parent_value - direct_sum
                leaf_residual = parent_value - leaf_sum
                scale = max(abs(parent_value), 1.0)
                if abs(direct_residual) <= tolerance * scale or abs(leaf_residual) > tolerance * scale:
                    continue
                rows.append({
                    "enabled": False,
                    "source_system": source_system,
                    "validation_axis": validation_axis,
                    "parent_code": parent,
                    "other_axis_value": other_value,
                    "economy": str(record.economy),
                    "parent_value": parent_value,
                    "notes": "Review candidate: immediate children do not reconcile, but all descendant leaves reconcile. Confirm source hierarchy semantics before enabling.",
                    "candidate_classification": "direct_children_incomplete_but_leaves_reconcile",
                    "comparison_scope": str(record.comparison_scope),
                    "scenario": str(record.scenario),
                    "year": int(record.year) if pd.notna(record.year) else "",
                    "direct_children_sum": direct_sum,
                    "direct_children_residual": direct_residual,
                    "leaf_descendants_sum": leaf_sum,
                    "leaf_descendants_residual": leaf_residual,
                    "leaf_descendant_codes": "|".join(leaves),
                })
    if not rows:
        return pd.DataFrame(columns=LEAF_RECONCILIATION_CANDIDATE_COLUMNS)
    return pd.DataFrame(rows, columns=LEAF_RECONCILIATION_CANDIDATE_COLUMNS).drop_duplicates()


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


def _melt_years(
    df: pd.DataFrame,
    id_columns: list[str],
    target_years: set[int] | None = None,
    include_latest_year: bool = False,
) -> pd.DataFrame:
    """Melt only the raw years required by an anchor-validation run."""
    year_columns = [column for column in df.columns if str(column).isdigit()]
    if target_years is not None:
        allowed = {str(year) for year in target_years}
        if include_latest_year and year_columns:
            allowed.add(str(max(int(column) for column in year_columns)))
        year_columns = [column for column in year_columns if str(column) in allowed]
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
    esto_extended_data_path=None,
    leap_var_base_year: int = 2022,
    anchor_target_years: set[int] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load raw ESTO, Ninth, and LEAP values plus their source-to-component mappings.

    ``anchor_target_years`` is the existing production validation slice (the
    decade years). ESTO-family inputs also retain their latest available year,
    preserving the caller's base-year-plus-decades comparison without first
    materialising every historical/modelled year as a long object dataframe.
    """
    source_frames: list[pd.DataFrame] = []
    mapping_frames: list[pd.DataFrame] = []

    esto = pd.read_csv(esto_data_path, dtype=object)
    esto_long = _melt_years(
        esto, ["economy", "flows", "products"], anchor_target_years, include_latest_year=True,
    )
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

    if esto_extended_data_path is not None and Path(esto_extended_data_path).exists():
        esto_extended = pd.read_csv(esto_extended_data_path, dtype=object)
        extended_long = _melt_years(
            esto_extended, ["economy", "flows", "products"], anchor_target_years, include_latest_year=True,
        )
        extended_long = extended_long.rename(columns={"flows": "source_flow", "products": "source_product"})
        extended_long["source_system"] = "ESTO_EXTENDED"
        extended_long["scenario"] = "historical"
        source_frames.append(extended_long)
        extended_pairs = esto_extended[["flows", "products"]].drop_duplicates().rename(columns={
            "flows": "source_flow", "products": "source_product",
        })
        extended_pairs["source_system"] = "ESTO_EXTENDED"
        extended_pairs["component_esto_flow"] = extended_pairs["source_flow"]
        extended_pairs["component_esto_product"] = extended_pairs["source_product"]
        mapping_frames.append(extended_pairs)

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
    ninth_long = _melt_years(
        ninth, ["economy", "scenarios", "source_flow", "source_product"], anchor_target_years,
    )
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
        if anchor_target_years is not None:
            leap = leap[leap["year"].isin(anchor_target_years)]
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
    source = pd.concat(source_frames, ignore_index=True)[source_columns]
    source["year"] = pd.to_numeric(source["year"], errors="coerce").astype("Int16")
    source["value"] = pd.to_numeric(source["value"], errors="coerce").fillna(0.0)
    for column in ["source_system", "economy", "scenario", "source_flow", "source_product"]:
        source[column] = source[column].astype("category")
    return (
        source,
        pd.concat(mapping_frames, ignore_index=True)[mapping_columns].drop_duplicates(),
    )


def build_failed_anchor_raw_child_context_values(
    detail_df: pd.DataFrame,
    source_df: pd.DataFrame,
    source_tree_df: pd.DataFrame,
) -> pd.DataFrame:
    """Return immediate raw-child values for every failed anchor context.

    ``frontier_total`` remains the validator's authoritative, de-duplicated
    mapped-frontier total. ``raw_child_total`` is deliberately separate: it
    is the raw source value reported for one immediate child. This makes the
    tree inspectable without pretending that overlapping mapped descendants
    can be allocated uniquely to individual children.
    """
    required_detail = {
        "status", "validation_axis", "comparison_scope", "source_system",
        "economy", "scenario", "year", "other_axis_value", "parent_code",
        "parent_value", "frontier_sum", "difference", "abs_error",
    }
    required_source = {
        "source_system", "economy", "scenario", "year", "source_flow",
        "source_product", "value",
    }
    if not required_detail.issubset(detail_df.columns) or not required_source.issubset(source_df.columns):
        return pd.DataFrame(columns=ANCHOR_CHILD_CONTEXT_COLUMNS)

    failed = detail_df[detail_df["status"].astype(str).eq("failed")].copy()
    if failed.empty:
        return pd.DataFrame(columns=ANCHOR_CHILD_CONTEXT_COLUMNS)
    failed["economy"] = _normalize_economy(failed["economy"])
    failed["year"] = pd.to_numeric(failed["year"], errors="coerce")
    for column in ["parent_value", "frontier_sum", "difference", "abs_error"]:
        failed[column] = pd.to_numeric(failed[column], errors="coerce").fillna(0.0)

    source = source_df.copy()
    source["economy"] = _normalize_economy(source["economy"])
    source["year"] = pd.to_numeric(source["year"], errors="coerce")
    source["value"] = pd.to_numeric(source["value"], errors="coerce").fillna(0.0)
    detail_rows: list[pd.DataFrame] = []

    for source_system in sorted(failed["source_system"].dropna().astype(str).unique()):
        dataset = source_system.casefold()
        system_failed = failed[failed["source_system"].astype(str).eq(source_system)]
        system_source = source[source["source_system"].astype(str).eq(source_system)]
        for validation_axis, tree_axis in [("flow", "flow"), ("product", "product")]:
            if dataset in {"leap", "ninth"}:
                tree_axis = "sector" if validation_axis == "flow" else "fuel"
            axis_failed = system_failed[system_failed["validation_axis"].astype(str).eq(validation_axis)].copy()
            if axis_failed.empty:
                continue
            axis_col = "source_flow" if validation_axis == "flow" else "source_product"
            other_col = "source_product" if validation_axis == "flow" else "source_flow"
            aliases = build_tree_code_aliases(source_tree_df, dataset, tree_axis)
            tree_mask = (
                source_tree_df["dataset"].astype(str).str.casefold().eq(dataset)
                & source_tree_df["axis"].astype(str).str.casefold().eq(tree_axis)
            )
            tree = source_tree_df.loc[tree_mask, ["code", "parent_code"]].copy()
            if tree.empty:
                continue
            tree["code"] = canonicalize_tree_codes(tree["code"], aliases)
            tree["parent_code"] = canonicalize_tree_codes(tree["parent_code"], aliases)
            edges = tree[tree["parent_code"].astype(str).ne("")].rename(columns={
                "parent_code": "parent_code", "code": "child_code",
            }).drop_duplicates()
            axis_failed["parent_code"] = canonicalize_tree_codes(axis_failed["parent_code"], aliases)
            expanded = axis_failed.merge(edges, on="parent_code", how="inner")
            if expanded.empty:
                continue
            child_source = system_source.copy()
            child_source[axis_col] = canonicalize_tree_codes(child_source[axis_col], aliases)
            child_source = child_source.rename(columns={axis_col: "child_code", other_col: "other_axis_value"})
            join_columns = ["economy", "scenario", "year", "other_axis_value", "child_code"]
            matched = expanded.merge(
                child_source[join_columns + ["value"]],
                on=join_columns,
                how="left",
            )
            matched["value"] = matched["value"].fillna(0.0)
            grouped = (
                matched.groupby(
                    [
                        "validation_axis", "comparison_scope", "source_system", "economy", "scenario",
                        "year", "other_axis_value", "parent_code", "child_code", "parent_value",
                        "frontier_sum", "difference", "abs_error",
                    ],
                    dropna=False,
                )
                .agg(
                    raw_child_value=("value", "sum"),
                    raw_child_row_count=("value", lambda values: int((values != 0).sum())),
                )
                .reset_index()
            )
            detail_rows.append(grouped)

    if not detail_rows:
        return pd.DataFrame(columns=ANCHOR_CHILD_CONTEXT_COLUMNS)
    return pd.concat(detail_rows, ignore_index=True)[ANCHOR_CHILD_CONTEXT_COLUMNS]


def build_failed_anchor_raw_child_values(
    detail_df: pd.DataFrame,
    source_df: pd.DataFrame,
    source_tree_df: pd.DataFrame,
) -> pd.DataFrame:
    """Summarise immediate raw-child values across failed anchor contexts."""
    context_values = build_failed_anchor_raw_child_context_values(detail_df, source_df, source_tree_df)
    return summarise_failed_anchor_raw_child_context_values(context_values)


def build_failed_anchor_mapped_component_context_values(
    detail_df: pd.DataFrame,
    source_tree_df: pd.DataFrame,
    source_mapping_df: pd.DataFrame,
    common_rows_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
) -> pd.DataFrame:
    """Expose the actual mapped frontier components for failed anchor contexts.

    This is an inspection artifact only. A Common ESTO row can be reached from
    more than one raw child, so consumers must de-duplicate by ``common_row_id``
    before calculating a mapped total. ``raw_child_code`` preserves that
    relationship without pretending a shared mapped value has been allocated.
    """
    required = {"status", "validation_axis", "comparison_scope", "source_system", "economy", "scenario", "year", "other_axis_value", "parent_code"}
    if not required.issubset(detail_df.columns):
        return pd.DataFrame(columns=ANCHOR_MAPPED_COMPONENT_CONTEXT_COLUMNS)
    failed = detail_df[detail_df["status"].astype(str).eq("failed")].copy()
    if failed.empty:
        return pd.DataFrame(columns=ANCHOR_MAPPED_COMPONENT_CONTEXT_COLUMNS)
    failed["economy"] = _normalize_economy(failed["economy"])
    failed["year"] = pd.to_numeric(failed["year"], errors="coerce")
    comparison = comparison_df.copy()
    comparison["economy"] = _normalize_economy(comparison["economy"])
    comparison["year"] = pd.to_numeric(comparison["year"], errors="coerce")
    comparison["value"] = pd.to_numeric(comparison["value"], errors="coerce").fillna(0.0)
    common_ids_by_component = (
        common_rows_df.groupby(
            ["comparison_scope", "component_esto_flow", "component_esto_product"], dropna=False,
        )["common_row_id"].agg(lambda values: sorted(set(values.dropna().astype(str))))
        .to_dict()
    )
    comparison_values = (
        comparison.groupby(
            ["source_system", "comparison_scope", "economy", "scenario", "year", "common_row_id"],
            dropna=False,
        )["value"].sum().to_dict()
    )
    rows: list[dict[str, object]] = []

    for source_system in sorted(failed["source_system"].dropna().astype(str).unique()):
        dataset = source_system.casefold()
        system_failed = failed[failed["source_system"].astype(str).eq(source_system)]
        system_mapping = source_mapping_df[source_mapping_df["source_system"].astype(str).eq(source_system)].copy()
        if system_mapping.empty:
            continue
        applicable_scopes = [
            scope for scope in common_rows_df["comparison_scope"].dropna().astype(str).unique()
            if source_system in COMPARISON_SCOPE_SYSTEMS.get(scope, {source_system})
        ]
        system_comparison = comparison[
            comparison["source_system"].astype(str).eq(source_system)
            & comparison["comparison_scope"].astype(str).isin(applicable_scopes)
        ]
        ids_with_data = set(system_comparison["common_row_id"].astype(str))
        scoped_components = common_rows_df[
            common_rows_df["comparison_scope"].astype(str).isin(applicable_scopes)
        ]
        has_data_pairs = set(zip(
            scoped_components.loc[
                scoped_components["common_row_id"].astype(str).isin(ids_with_data),
                "component_esto_flow",
            ].astype(str),
            scoped_components.loc[
                scoped_components["common_row_id"].astype(str).isin(ids_with_data),
                "component_esto_product",
            ].astype(str),
        ))
        for validation_axis, tree_axis in [("flow", "flow"), ("product", "product")]:
            if dataset in {"leap", "ninth"}:
                tree_axis = "sector" if validation_axis == "flow" else "fuel"
            axis_failed = system_failed[system_failed["validation_axis"].astype(str).eq(validation_axis)].copy()
            if axis_failed.empty:
                continue
            axis_col = "source_flow" if validation_axis == "flow" else "source_product"
            other_col = "source_product" if validation_axis == "flow" else "source_flow"
            aliases = build_tree_code_aliases(source_tree_df, dataset, tree_axis)
            tree = source_tree_df[
                source_tree_df["dataset"].astype(str).str.casefold().eq(dataset)
                & source_tree_df["axis"].astype(str).str.casefold().eq(tree_axis)
            ].copy()
            if tree.empty:
                continue
            tree["code"] = canonicalize_tree_codes(tree["code"], aliases)
            tree["parent_code"] = canonicalize_tree_codes(tree["parent_code"], aliases)
            children = _children_map(tree, dataset, tree_axis)
            system_mapping[axis_col] = canonicalize_tree_codes(system_mapping[axis_col], aliases)
            direct_index = {
                key: group for key, group in system_mapping.groupby([axis_col, other_col], dropna=False)
            }
            empty_mapping = system_mapping.iloc[0:0]
            axis_failed["parent_code"] = canonicalize_tree_codes(axis_failed["parent_code"], aliases)
            cache: dict[tuple[str, str], tuple[pd.DataFrame, list[str]]] = {}
            for detail in axis_failed.itertuples(index=False):
                parent = str(detail.parent_code)
                other_value = str(detail.other_axis_value)
                for raw_node_role, raw_child in [("parent", parent)] + [("child", child) for child in children.get(parent, [])]:
                    resolved, missing = _mapped_descendants(
                        raw_child, other_value, children, direct_index, empty_mapping, cache,
                        has_data_pairs,
                    )
                    for missing_child in missing:
                        rows.append({
                            "validation_axis": validation_axis, "comparison_scope": detail.comparison_scope,
                            "source_system": source_system, "economy": detail.economy,
                            "scenario": detail.scenario, "year": detail.year,
                            "other_axis_value": other_value, "parent_code": parent,
                            "raw_node_role": raw_node_role, "raw_child_code": raw_child, "resolved_source_flow": "",
                            "resolved_source_product": "", "component_esto_flow": "",
                            "component_esto_product": "", "common_row_id": "",
                            "mapped_value": 0.0, "mapping_status": f"missing_source_mapping:{missing_child}",
                        })
                    for component in resolved.itertuples(index=False):
                        common_ids = common_ids_by_component.get(
                            (str(detail.comparison_scope), str(component.component_esto_flow), str(component.component_esto_product)),
                            [],
                        )
                        if not common_ids:
                            rows.append({
                                "validation_axis": validation_axis, "comparison_scope": detail.comparison_scope,
                                "source_system": source_system, "economy": detail.economy,
                                "scenario": detail.scenario, "year": detail.year,
                                "other_axis_value": other_value, "parent_code": parent,
                                "raw_node_role": raw_node_role, "raw_child_code": raw_child, "resolved_source_flow": component.source_flow,
                                "resolved_source_product": component.source_product,
                                "component_esto_flow": component.component_esto_flow,
                                "component_esto_product": component.component_esto_product,
                                "common_row_id": "", "mapped_value": 0.0,
                                "mapping_status": "component_not_registered_in_common_esto",
                            })
                            continue
                        for common_id in common_ids:
                            mapped_value = comparison_values.get(
                                (source_system, str(detail.comparison_scope), str(detail.economy),
                                 str(detail.scenario), detail.year, common_id),
                                0.0,
                            )
                            rows.append({
                                "validation_axis": validation_axis, "comparison_scope": detail.comparison_scope,
                                "source_system": source_system, "economy": detail.economy,
                                "scenario": detail.scenario, "year": detail.year,
                                "other_axis_value": other_value, "parent_code": parent,
                                "raw_node_role": raw_node_role, "raw_child_code": raw_child, "resolved_source_flow": component.source_flow,
                                "resolved_source_product": component.source_product,
                                "component_esto_flow": component.component_esto_flow,
                                "component_esto_product": component.component_esto_product,
                                "common_row_id": common_id,
                                "mapped_value": float(mapped_value),
                                "mapping_status": "mapped" if mapped_value != 0.0 else "mapped_but_no_context_value",
                            })
    if not rows:
        return pd.DataFrame(columns=ANCHOR_MAPPED_COMPONENT_CONTEXT_COLUMNS)
    return pd.DataFrame(rows)[ANCHOR_MAPPED_COMPONENT_CONTEXT_COLUMNS].drop_duplicates()


def summarise_failed_anchor_raw_child_context_values(context_values: pd.DataFrame) -> pd.DataFrame:
    """Aggregate context-level child values for compact tree display."""
    if context_values.empty:
        return pd.DataFrame(columns=ANCHOR_CHILD_VALUE_COLUMNS)
    return (
        context_values.groupby(
            ["validation_axis", "comparison_scope", "source_system", "parent_code", "child_code"],
            dropna=False,
        )
        .agg(
            failed_context_count=("parent_value", "size"),
            parent_total=("parent_value", "sum"),
            frontier_total=("frontier_sum", "sum"),
            mismatch_total=("difference", "sum"),
            absolute_mismatch_total=("abs_error", "sum"),
            raw_child_total=("raw_child_value", "sum"),
            raw_child_row_count=("raw_child_row_count", "sum"),
        )
        .reset_index()[ANCHOR_CHILD_VALUE_COLUMNS]
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
