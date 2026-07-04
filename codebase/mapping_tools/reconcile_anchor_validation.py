#%%
"""Reconcile raw source parent totals against the existing converted-to-ESTO outputs.

This module **replaces the tree-walk anchor methodology of Prompt 4**
(``validate_lineage_anchors.py``). That approach re-derived each source system's
frontier from its own tree and crossed every parent against every unrelated
other-axis value, manufacturing thousands of false failures from vocabulary that
does not match the mapped vocabulary (see ``PROMPT5_STATUS_AND_ISSUES.md``).

Instead we reconcile two *independently derived* totals per source parent:

* **left** — the raw source parent total, read straight from the raw source
  data (the partitioned source caches / raw CSVs).
* **right** — the converted-to-ESTO total for the common boundary that parent
  maps into, read from the already-correct conversion outputs
  (``leap_results_converted_to_esto.csv``, ``ninth_results_converted_to_esto.csv``,
  ``esto_results_exact_rows.csv``).

Interpretation and assumptions (documented also in ``docs/mappings_system.md``)
------------------------------------------------------------------------------
We treat *"the mapped children sum back to the raw source parent total"* as
evidence that the parent's data was mapped cleanly. This is a **necessary, not
sufficient**, condition:

* Children summing to the parent does not *prove* every child was individually
  mapped to the correct common row -- in principle offsetting errors could still
  sum correctly.
* We accept it as the working verification because producing a correct parent
  total by any *other* route would be very hard: for independently-mapped
  children to add back up to the raw parent, the mapping almost certainly has to
  be right. A clean reconciliation is therefore strong (if not absolute)
  evidence.
* Where a parent total reconciles we report ``passed`` but claim nothing about
  per-child correctness beyond that. Where it does not reconcile, that is a real
  signal.

The two sides are read from **different files** so the check is not a tautology:
the left comes from raw source rows, the right from the converted output, and
they can genuinely disagree. Boundaries are classified from the **structural
artifacts** (``source_pair_to_common_row.csv`` / ``esto_component_to_common_row``),
never from string prefixes or tree-reconstructed frontiers. The tree is used
*only* to enumerate parents and to sum the raw descendants of a parent.
"""

#%%
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Iterator

import pandas as pd

from codebase.mapping_tools.structural_resolver import build_tree_index


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

VALIDATION_MODES = {"structural", "slice", "full"}

# Each converted output is a single-system conversion into ESTO components. The
# comparison scope that carries that system's full component mapping (verified by
# overlap against the converted target pairs) is fixed here.
SYSTEM_SCOPE = {
    "LEAP": "leap_vs_esto",
    "NINTH": "leap_vs_esto_vs_ninth",
    "ESTO": "esto_only",
}
SOURCE_SYSTEMS = ("LEAP", "NINTH", "ESTO")

DETAIL_COLUMNS = [
    "validation_axis", "source_system", "economy", "scenario", "year",
    "parent_code", "boundary_kind", "status", "reason",
    "raw_parent_total", "converted_boundary_total", "difference", "abs_error",
    "mapped_member_count", "component_count", "common_row_count",
    "contaminating_codes",
]


def _normalize_economy(economy: pd.Series) -> pd.Series:
    """Canonicalize APEC economy codes so ``20USA`` and ``20_USA`` unify.

    The underscore between the numeric prefix and the alpha code is a cosmetic
    separator that appears inconsistently across ESTO/Ninth/LEAP sources.
    """
    return economy.astype(str).str.replace("_", "", regex=False).str.strip()


def _tree_axes(dataset: str, axis: str) -> str:
    """Map a validation axis to the tree axis vocabulary for a dataset."""
    if dataset in {"leap", "ninth"}:
        return "sector" if axis == "flow" else "fuel"
    return axis


# --------------------------------------------------------------------------- #
# Normalizing the trusted (converted) side.
# --------------------------------------------------------------------------- #

CONVERTED_SHAPE = [
    "source_system", "economy", "scenario", "year", "esto_flow", "esto_product",
    "value",
]


def normalize_converted_output(df: pd.DataFrame, source_system: str) -> pd.DataFrame:
    """Normalize one converted-to-ESTO file to the common shape.

    Each converted file uses its own column names; map them explicitly rather
    than assuming a shared schema:

    * LEAP  -- ``economy, scenario, year, target_flow, target_product, value``
      (source system implicit).
    * Ninth -- ``source_system, economy, scenario, year, target_flow,
      target_product, value``.
    * ESTO  -- ``economy, esto_flow, esto_product, year, value, source_system,
      scenario`` (already ``esto_flow`` / ``esto_product``).
    """
    result = df.copy()
    renames = {"target_flow": "esto_flow", "target_product": "esto_product"}
    result = result.rename(columns={k: v for k, v in renames.items() if k in result})
    if "source_system" not in result:
        result["source_system"] = source_system
    result["source_system"] = result["source_system"].fillna(source_system).astype(str).str.upper()
    missing = set(CONVERTED_SHAPE).difference(result.columns)
    if missing:
        raise ValueError(
            f"Converted output for {source_system} is missing columns: {sorted(missing)}"
        )
    result = result[CONVERTED_SHAPE].copy()
    result["economy"] = _normalize_economy(result["economy"])
    result["year"] = pd.to_numeric(result["year"], errors="coerce").astype("Int64")
    result["value"] = pd.to_numeric(result["value"], errors="coerce").fillna(0.0)
    for column in ["scenario", "esto_flow", "esto_product"]:
        result[column] = result[column].fillna("").astype(str).str.strip()
    return result


def load_converted_output(
    path: Path,
    source_system: str,
    economies: set[str] | None = None,
    years: set[int] | None = None,
    chunksize: int = 500_000,
) -> pd.DataFrame:
    """Read a (possibly large) converted output filtered to a slice, memory-bounded."""
    frames: list[pd.DataFrame] = []
    for chunk in pd.read_csv(path, dtype=object, chunksize=chunksize):
        normalized = normalize_converted_output(chunk, source_system)
        if economies is not None:
            normalized = normalized[normalized["economy"].isin(economies)]
        if years is not None:
            normalized = normalized[normalized["year"].isin(years)]
        if not normalized.empty:
            frames.append(normalized)
    if not frames:
        return pd.DataFrame(columns=CONVERTED_SHAPE)
    return pd.concat(frames, ignore_index=True)


# --------------------------------------------------------------------------- #
# Tree parents (enumeration only).
# --------------------------------------------------------------------------- #

def parent_descendants(
    tree_df: pd.DataFrame, dataset: str, tree_axis: str
) -> dict[str, set[str]]:
    """Return, for every internal tree node, the set of descendant codes (incl self).

    The tree is used *only* to enumerate parents and to define which raw source
    codes roll up under a parent; it is never used to predict mapped output.
    """
    index, _ = build_tree_index(tree_df, dataset, tree_axis)
    children: dict[str, list[str]] = defaultdict(list)
    for child, parent in index.items():
        if parent:
            children[parent].append(child)
    result: dict[str, set[str]] = {}
    for parent in children:
        stack = [parent]
        seen: set[str] = set()
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            stack.extend(children.get(node, ()))
        result[parent] = seen
    return result


# --------------------------------------------------------------------------- #
# Boundary classification (structural artifacts only).
# --------------------------------------------------------------------------- #

class ParentBoundary:
    """Structural boundary a parent maps into, classified without values."""

    __slots__ = (
        "parent_code", "source_pairs", "components", "common_rows",
        "member_count", "is_rollup", "contaminating_codes", "edges",
    )

    def __init__(
        self,
        parent_code: str,
        source_pairs: frozenset[tuple[str, str]],
        components: frozenset[tuple[str, str]],
        common_rows: frozenset[str],
        member_count: int,
        is_rollup: bool,
        contaminating_codes: frozenset[str],
        edges: tuple[tuple[str, str, str, str, str], ...] = (),
    ) -> None:
        self.parent_code = parent_code
        # Mapped raw source pairs under this parent -- the left side sums these
        # raw rows, so it shares the mapped-leaf granularity of the right side
        # and never double-counts the source's own subtotal rows.
        self.source_pairs = source_pairs
        self.components = components
        self.common_rows = common_rows
        self.member_count = member_count
        self.is_rollup = is_rollup
        self.contaminating_codes = contaminating_codes
        # De-duplicated mapping edges under this parent, each a tuple of
        # ``(source_flow, source_product, esto_flow, esto_product, relationship_id)``.
        # The raw side keys on the first two, the converted side on the next two;
        # for ESTO identity rows they coincide. Edges carry the source->target
        # topology that the aggregate ``source_pairs``/``components`` sets lose,
        # so a contributor breakdown can tell a clean 1:1 pair apart from a
        # fanned-out one.
        self.edges = edges

    @property
    def anchorable(self) -> bool:
        # Exact ESTO rows owned solely by this parent's descendants are cleanly
        # separable. A rolled/combined common row, or an exact row shared with
        # source pairs outside the parent, mixes in unrelated contributors.
        return (
            self.member_count > 0
            and not self.is_rollup
            and not self.contaminating_codes
        )

    @property
    def kind(self) -> str:
        if self.member_count == 0:
            return "none"
        if self.is_rollup:
            return "rollup"
        if self.contaminating_codes:
            return "shared_exact"
        return "exact"


def build_parent_boundaries(
    structural_df: pd.DataFrame,
    tree_df: pd.DataFrame,
    source_system: str,
    axis: str,
) -> dict[str, ParentBoundary]:
    """Classify the common boundary each tree parent maps into for one axis.

    Uses ``source_pair_to_common_row`` membership (filtered to the system's
    scope) to find the common rows a parent's descendant source pairs land in,
    and classifies exact vs rollup / contaminated from ``is_exact_row`` and the
    structural membership of those common rows.
    """
    dataset = source_system.casefold()
    tree_axis = _tree_axes(dataset, axis)
    axis_col = "original_source_flow" if axis == "flow" else "original_source_product"
    scope = SYSTEM_SCOPE[source_system]

    sub = structural_df[
        structural_df["source_system"].astype(str).str.upper().eq(source_system)
        & structural_df["comparison_scope"].astype(str).eq(scope)
    ].copy()
    for column in ["original_source_flow", "original_source_product",
                   "component_esto_flow", "component_esto_product",
                   "common_row_id", "is_exact_row"]:
        sub[column] = sub[column].fillna("").astype(str).str.strip()
    sub["_exact"] = sub["is_exact_row"].str.casefold().isin({"true", "1", "yes"})

    # Drop redundant subtotal pairs (anti-chain filter). Source data carries a
    # subtotal at every level of both axes, so if a mapped pair AND a strict
    # descendant of it (deeper flow and/or deeper product) are both mapped, the
    # ancestor pair's raw row already contains the descendant's value and summing
    # both double-counts. We keep only the minimal (deepest) mapped pairs -- the
    # granularity the conversion actually joins on -- regardless of absolute tree
    # depth, so systems whose mappings sit at intermediate nodes (Ninth) are
    # preserved while ESTO/LEAP subtotal+leaf overlaps collapse to the leaf.
    # This uses tree ancestry only to detect the overlap, never to build a
    # frontier; pairs absent from the tree have no ancestors and stay minimal.
    flow_tree_axis = tree_axis if axis == "flow" else _tree_axes(dataset, "flow")
    product_tree_axis = tree_axis if axis == "product" else _tree_axes(dataset, "product")
    flow_parent, _ = build_tree_index(tree_df, dataset, flow_tree_axis)
    product_parent, _ = build_tree_index(tree_df, dataset, product_tree_axis)

    def _ancestors(code: str, parent_index: dict[str, str]) -> list[str]:
        chain: list[str] = []
        seen = {code}
        current = parent_index.get(code, "")
        while current and current not in seen:
            chain.append(current)
            seen.add(current)
            current = parent_index.get(current, "")
        return chain

    present_pairs = set(zip(sub["original_source_flow"], sub["original_source_product"]))
    redundant: set[tuple[str, str]] = set()
    for flow, product in present_pairs:
        flow_line = [flow, *_ancestors(flow, flow_parent)]
        product_line = [product, *_ancestors(product, product_parent)]
        for ancestor_flow in flow_line:
            for ancestor_product in product_line:
                candidate = (ancestor_flow, ancestor_product)
                if candidate != (flow, product) and candidate in present_pairs:
                    redundant.add(candidate)
    if redundant:
        pair_index = pd.MultiIndex.from_arrays(
            [sub["original_source_flow"], sub["original_source_product"]]
        )
        sub = sub[~pair_index.isin(redundant)].copy()

    # common_row_id -> set of axis codes that contribute to it (contamination set)
    common_contributors: dict[str, set[str]] = (
        sub.groupby("common_row_id")[axis_col].agg(lambda s: set(s)).to_dict()
    )
    # axis code -> member rows lookup
    by_code = {code: group for code, group in sub.groupby(axis_col, sort=False)}

    descendants = parent_descendants(tree_df, dataset, tree_axis)
    boundaries: dict[str, ParentBoundary] = {}
    for parent, codes in descendants.items():
        member_frames = [by_code[c] for c in codes if c in by_code]
        if not member_frames:
            boundaries[parent] = ParentBoundary(
                parent, frozenset(), frozenset(), frozenset(), 0, False, frozenset()
            )
            continue
        members = pd.concat(member_frames, ignore_index=True)
        source_pairs = frozenset(
            zip(members["original_source_flow"], members["original_source_product"])
        )
        components = frozenset(
            zip(members["component_esto_flow"], members["component_esto_product"])
        )
        common_rows = frozenset(members["common_row_id"].dropna().tolist()) - {""}
        is_rollup = bool((~members["_exact"]).any())
        contaminating: set[str] = set()
        for cr in common_rows:
            contaminating |= common_contributors.get(cr, set()) - codes
        relationship_ids = (
            members["relationship_id"].fillna("").astype(str)
            if "relationship_id" in members
            else pd.Series([""] * len(members))
        )
        edge_map: dict[tuple[str, str, str, str], str] = {}
        for sf, sp, cf, cp, rid in zip(
            members["original_source_flow"], members["original_source_product"],
            members["component_esto_flow"], members["component_esto_product"],
            relationship_ids,
        ):
            edge_map.setdefault((sf, sp, cf, cp), rid)
        edges = tuple((sf, sp, cf, cp, rid) for (sf, sp, cf, cp), rid in edge_map.items())
        boundaries[parent] = ParentBoundary(
            parent, source_pairs, components, common_rows, len(members), is_rollup,
            frozenset(contaminating), edges,
        )
    return boundaries


# --------------------------------------------------------------------------- #
# Reconciliation of one partition.
# --------------------------------------------------------------------------- #

def reconcile_partition(
    raw_partition: pd.DataFrame,
    converted: pd.DataFrame,
    boundaries_by_axis: dict[str, dict[str, ParentBoundary]],
    converted_components_by_axis: dict[str, set[tuple[str, str]]],
    source_system: str,
    tolerance: float = 0.01,
) -> pd.DataFrame:
    """Reconcile every parent for one ``economy x scenario x year`` partition.

    ``raw_partition`` holds one partition's raw source rows with columns
    ``economy, scenario, year, source_flow, source_product, value``.
    ``converted`` holds the converted-to-ESTO rows for the same partition.
    """
    records: list[dict[str, Any]] = []
    if raw_partition.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    economy = str(raw_partition["economy"].iloc[0])
    scenario = str(raw_partition["scenario"].iloc[0])
    year = raw_partition["year"].iloc[0]
    raw = raw_partition.copy()
    raw["value"] = pd.to_numeric(raw["value"], errors="coerce").fillna(0.0)

    # Right side: converted totals per ESTO component for this partition.
    converted_totals: dict[tuple[str, str], float] = {}
    if not converted.empty:
        grouped = converted.groupby(["esto_flow", "esto_product"])["value"].sum()
        converted_totals = {tuple(k): float(v) for k, v in grouped.items()}

    # Left side is keyed on the raw source pair. Summing a flow parent's own
    # rows over every product would double-count, because the source data
    # carries a subtotal at every product level too; instead we sum only the
    # parent's mapped source pairs, matching the mapped-leaf granularity of the
    # right side. This is read from the raw file, the right side from the
    # converted file, so the two remain independent.
    raw_pair_totals: dict[tuple[str, str], float] = {
        tuple(k): float(v)
        for k, v in raw.groupby(["source_flow", "source_product"])["value"].sum().items()
    }

    for axis in ["flow", "product"]:
        boundaries = boundaries_by_axis[axis]
        converted_components = converted_components_by_axis[axis]
        for parent, boundary in boundaries.items():
            raw_total = float(
                sum(raw_pair_totals.get(pair, 0.0) for pair in boundary.source_pairs)
            )
            component_count = len(boundary.components)
            common_row_count = len(boundary.common_rows)
            converted_total = float(
                sum(converted_totals.get(c, 0.0) for c in boundary.components)
            )
            difference = raw_total - converted_total
            abs_error = abs(difference)

            if boundary.member_count == 0:
                status, reason = "unanchorable", "no_anchorable_boundary"
            elif not boundary.anchorable:
                status, reason = "unanchorable", "rollup_boundary_not_separable"
            elif not (boundary.components & converted_components):
                status, reason = "unanchorable", "parent_absent_from_converted_output"
            elif abs_error <= tolerance * max(abs(raw_total), 1.0):
                status, reason = "passed", "within_tolerance"
            else:
                status, reason = "failed", "difference_outside_tolerance"

            records.append({
                "validation_axis": axis, "source_system": source_system,
                "economy": economy, "scenario": scenario,
                "year": int(year) if pd.notna(year) else "",
                "parent_code": parent, "boundary_kind": boundary.kind,
                "status": status, "reason": reason,
                "raw_parent_total": raw_total,
                "converted_boundary_total": converted_total,
                "difference": difference, "abs_error": abs_error,
                "mapped_member_count": boundary.member_count,
                "component_count": component_count,
                "common_row_count": common_row_count,
                "contaminating_codes": "|".join(sorted(boundary.contaminating_codes)[:8]),
            })
    return pd.DataFrame(records, columns=DETAIL_COLUMNS)


# --------------------------------------------------------------------------- #
# Contributor breakdown (Phase 1: explain a failed anchor from its parts).
# --------------------------------------------------------------------------- #
#
# A reconcile check reports a single ``difference`` per parent. This layer
# decomposes that one number into the individual mapping contributors behind it,
# so a failed anchor reads as "these specific rows drive the gap" rather than an
# unexplained aggregate. It adds *no new numeric observation*: it re-expresses
# the same raw and converted totals reconcile already compares, and the per-check
# ``breakdown_remainder`` is asserted to reproduce reconcile's own ``difference``.
#
# The raw side and the converted side live in different vocabularies (LEAP/Ninth
# codes vs ESTO codes) joined by the boundary's mapping ``edges``. This layer is
# **Option A -- honest, no allocation, no rerun**:
#
# * A *bijective* edge (one source pair <-> one ESTO component, neither fanning
#   out nor shared) is netted per row: ``raw_value - converted_value``. For ESTO
#   every edge is an identity row, so every contributor is bijective and the
#   output matches the pure ESTO decomposition exactly.
# * Anything *entangled* -- a source pair that fans out to several components, or
#   a component fed by several sources -- is NOT split per edge, because the
#   converters do not record the allocation share that split it. Those rows are
#   emitted one-sided (raw ledger and converted ledger) and flagged
#   ``value_quality=unknown`` / ``mapping_status=unsafe_unallocated_fanout`` (or
#   ``unsafe_many_to_one``). No per-edge difference is fabricated for them.
#
# Every source pair and every component still appears exactly once, so the two
# column sums equal reconcile's ``raw_parent_total`` and
# ``converted_boundary_total`` and the total difference always reproduces --
# ``fully_attributed`` records whether it did so per row (no entangled residue)
# or only in aggregate.

BREAKDOWN_SCHEMA_VERSION = "anchor_contribution_v2"

CONTRIBUTION_COLUMNS = [
    "check_id", "validation_axis", "source_system", "economy", "scenario", "year",
    "parent_code", "boundary_kind", "check_status", "counting_role",
    "source_flow", "source_product", "esto_flow", "esto_product", "relationship_id",
    "raw_value", "converted_value", "contribution_difference",
    "mapping_cardinality", "value_quality", "mapping_status", "exclusion_reason",
]

CONTRIBUTION_SUMMARY_COLUMNS = [
    "check_id", "validation_axis", "source_system", "economy", "scenario", "year",
    "parent_code", "boundary_kind", "check_status", "check_difference",
    "breakdown_raw_total", "breakdown_converted_total", "breakdown_difference",
    "breakdown_remainder",
    "resolved_difference", "resolved_contributor_count",
    "unresolved_raw_total", "unresolved_converted_total", "unresolved_difference",
    "unresolved_source_count", "unresolved_component_count",
    "fully_attributed", "lineage_complete",
]

# A contribution counts as "explaining" the failure once its raw/converted gap
# is larger than pure floating-point noise; zero-difference members mapped
# cleanly and are retained only for completeness, not as evidence.
_EXPLAINING_EPS = 1e-9


def check_id(
    source_system: str, economy: str, scenario: str, year: Any,
    validation_axis: str, parent_code: str,
) -> str:
    """Deterministic content-derived ID for an anchor check.

    Stable across runs because it is a hash of the semantic check key plus the
    breakdown schema version -- never a cache-local row index.
    """
    key = "|".join([
        BREAKDOWN_SCHEMA_VERSION, str(source_system), str(economy), str(scenario),
        "" if pd.isna(year) else str(int(year)) if isinstance(year, (int, float)) and not isinstance(year, bool) else str(year),
        str(validation_axis), str(parent_code),
    ])
    return "chk_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _resolved_reason(raw_v: float, conv_v: float) -> str:
    """Why a *bijective* contributor differs between the raw and converted sides."""
    if abs(raw_v - conv_v) <= _EXPLAINING_EPS:
        return ""  # mapped cleanly, no contribution to the difference
    if conv_v == 0.0:
        return "raw_present_converted_row_missing"
    if raw_v == 0.0:
        return "converted_present_raw_row_missing"
    return "value_mismatch"


def _edge_topology(
    edges: tuple[tuple[str, str, str, str, str], ...]
) -> tuple[
    dict[tuple[str, str], set[tuple[str, str]]],
    dict[tuple[str, str], set[tuple[str, str]]],
    dict[tuple[tuple[str, str], tuple[str, str]], str],
]:
    """Index mapping edges into source->targets, target<-sources, and edge ids."""
    targets_of: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    sources_of: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    relationship_of: dict[tuple[tuple[str, str], tuple[str, str]], str] = {}
    for sf, sp, cf, cp, rid in edges:
        source, target = (sf, sp), (cf, cp)
        targets_of[source].add(target)
        sources_of[target].add(source)
        relationship_of[(source, target)] = rid
    return targets_of, sources_of, relationship_of


def build_anchor_contributions(
    raw_partition: pd.DataFrame,
    converted: pd.DataFrame,
    boundaries_by_axis: dict[str, dict[str, ParentBoundary]],
    converted_components_by_axis: dict[str, set[tuple[str, str]]],
    source_system: str,
    tolerance: float = 0.01,
    statuses: tuple[str, ...] = ("failed",),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Decompose each selected anchor into its mapping contributors (Option A).

    Reconciles the partition first (so status/difference match the anchor
    validation exactly), then for every parent whose status is in ``statuses``
    emits contributor rows: bijective edges netted per row, entangled fan-out /
    many-to-one members listed one-sided and flagged unresolved. The per-check
    summary's ``breakdown_remainder`` proves the contributions reproduce
    reconcile's own ``difference``; ``fully_attributed`` says whether every
    contribution was attributed per row.

    Returns ``(contributions_df, summary_df)``.
    """
    detail = reconcile_partition(
        raw_partition, converted, boundaries_by_axis,
        converted_components_by_axis, source_system, tolerance,
    )
    if detail.empty:
        return (
            pd.DataFrame(columns=CONTRIBUTION_COLUMNS),
            pd.DataFrame(columns=CONTRIBUTION_SUMMARY_COLUMNS),
        )

    economy = str(raw_partition["economy"].iloc[0])
    scenario = str(raw_partition["scenario"].iloc[0])
    year = raw_partition["year"].iloc[0]
    year_out = int(year) if pd.notna(year) else ""

    raw = raw_partition.copy()
    raw["value"] = pd.to_numeric(raw["value"], errors="coerce").fillna(0.0)
    raw_pair_totals: dict[tuple[str, str], float] = {
        tuple(k): float(v)
        for k, v in raw.groupby(["source_flow", "source_product"])["value"].sum().items()
    }
    converted_totals: dict[tuple[str, str], float] = {}
    if not converted.empty:
        grouped = converted.groupby(["esto_flow", "esto_product"])["value"].sum()
        converted_totals = {tuple(k): float(v) for k, v in grouped.items()}

    contribution_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for drow in detail.to_dict("records"):
        if drow["status"] not in statuses:
            continue
        axis = drow["validation_axis"]
        parent = drow["parent_code"]
        boundary = boundaries_by_axis[axis][parent]
        cid = check_id(source_system, economy, scenario, year, axis, parent)
        base = {
            "check_id": cid, "validation_axis": axis, "source_system": source_system,
            "economy": economy, "scenario": scenario, "year": year_out,
            "parent_code": parent, "boundary_kind": boundary.kind,
            "check_status": drow["status"],
        }

        targets_of, sources_of, relationship_of = _edge_topology(boundary.edges)

        resolved_rows: list[dict[str, Any]] = []
        raw_ledger_rows: list[dict[str, Any]] = []
        converted_ledger_rows: list[dict[str, Any]] = []

        # A source pair resolves iff it maps to exactly one component and that
        # component is fed by exactly one source: a clean 1:1 whose value can be
        # honestly netted. Everything else is entangled and left unallocated.
        resolved_sources: set[tuple[str, str]] = set()
        resolved_targets: set[tuple[str, str]] = set()
        for source, targets in targets_of.items():
            if len(targets) != 1:
                continue
            (target,) = tuple(targets)
            if len(sources_of[target]) != 1:
                continue
            resolved_sources.add(source)
            resolved_targets.add(target)
            raw_v = raw_pair_totals.get(source, 0.0)
            conv_v = converted_totals.get(target, 0.0)
            resolved_rows.append({
                **base, "counting_role": "resolved_pair",
                "source_flow": source[0], "source_product": source[1],
                "esto_flow": target[0], "esto_product": target[1],
                "relationship_id": relationship_of.get((source, target), ""),
                "raw_value": raw_v, "converted_value": conv_v,
                "contribution_difference": raw_v - conv_v,
                "mapping_cardinality": "direct", "value_quality": "exact_direct",
                "mapping_status": "resolved",
                "exclusion_reason": _resolved_reason(raw_v, conv_v),
            })

        # Entangled raw ledger: source pairs not cleanly bijective.
        for source, targets in targets_of.items():
            if source in resolved_sources:
                continue
            raw_v = raw_pair_totals.get(source, 0.0)
            fanout = len(targets) > 1
            cardinality = "fanout" if fanout else "many_to_one"
            status = "unsafe_unallocated_fanout" if fanout else "unsafe_many_to_one"
            raw_ledger_rows.append({
                **base, "counting_role": "raw_source",
                "source_flow": source[0], "source_product": source[1],
                "esto_flow": "", "esto_product": "",
                "relationship_id": "|".join(sorted(
                    relationship_of.get((source, t), "") for t in targets
                )).strip("|"),
                "raw_value": raw_v, "converted_value": None,
                "contribution_difference": None,
                "mapping_cardinality": cardinality, "value_quality": "unknown",
                "mapping_status": status,
                "exclusion_reason": (
                    "fanout_source_unallocated" if fanout
                    else "many_to_one_source_unattributed"
                ),
            })

        # Entangled converted ledger: components not cleanly bijective.
        for target, sources in sources_of.items():
            if target in resolved_targets:
                continue
            conv_v = converted_totals.get(target, 0.0)
            fed_by_fanout = any(len(targets_of[s]) > 1 for s in sources)
            cardinality = "fanout_target" if fed_by_fanout else "many_to_one_target"
            status = "unsafe_unallocated_fanout" if fed_by_fanout else "unsafe_many_to_one"
            converted_ledger_rows.append({
                **base, "counting_role": "converted_component",
                "source_flow": "", "source_product": "",
                "esto_flow": target[0], "esto_product": target[1],
                "relationship_id": "",
                "raw_value": None, "converted_value": conv_v,
                "contribution_difference": None,
                "mapping_cardinality": cardinality, "value_quality": "unknown",
                "mapping_status": status,
                "exclusion_reason": (
                    "fanout_target_unallocated" if fed_by_fanout
                    else "many_to_one_target_unattributed"
                ),
            })

        resolved_rows.sort(key=lambda r: abs(r["contribution_difference"]), reverse=True)
        raw_ledger_rows.sort(key=lambda r: abs(r["raw_value"]), reverse=True)
        converted_ledger_rows.sort(key=lambda r: abs(r["converted_value"]), reverse=True)
        contribution_rows.extend(resolved_rows + raw_ledger_rows + converted_ledger_rows)

        resolved_difference = sum(r["contribution_difference"] for r in resolved_rows)
        unresolved_raw = sum(r["raw_value"] for r in raw_ledger_rows)
        unresolved_converted = sum(r["converted_value"] for r in converted_ledger_rows)
        unresolved_difference = unresolved_raw - unresolved_converted
        breakdown_raw = sum(r["raw_value"] for r in resolved_rows) + unresolved_raw
        breakdown_converted = (
            sum(r["converted_value"] for r in resolved_rows) + unresolved_converted
        )
        breakdown_difference = breakdown_raw - breakdown_converted
        remainder = breakdown_difference - float(drow["difference"])
        fully_attributed = not raw_ledger_rows and not converted_ledger_rows
        summary_rows.append({
            **base,
            "check_difference": float(drow["difference"]),
            "breakdown_raw_total": breakdown_raw,
            "breakdown_converted_total": breakdown_converted,
            "breakdown_difference": breakdown_difference,
            "breakdown_remainder": remainder,
            "resolved_difference": resolved_difference,
            "resolved_contributor_count": len(resolved_rows),
            "unresolved_raw_total": unresolved_raw,
            "unresolved_converted_total": unresolved_converted,
            "unresolved_difference": unresolved_difference,
            "unresolved_source_count": len(raw_ledger_rows),
            "unresolved_component_count": len(converted_ledger_rows),
            "fully_attributed": bool(fully_attributed),
            "lineage_complete": bool(abs(remainder) <= _EXPLAINING_EPS),
        })

    return (
        pd.DataFrame(contribution_rows, columns=CONTRIBUTION_COLUMNS),
        pd.DataFrame(summary_rows, columns=CONTRIBUTION_SUMMARY_COLUMNS),
    )


# --------------------------------------------------------------------------- #
# Structural mode & summaries.
# --------------------------------------------------------------------------- #

def validate_structural(
    structural_df: pd.DataFrame,
    tree_df: pd.DataFrame,
    converted_paths: dict[str, Path],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Value-free checks: schemas, and that every tree parent resolves to an
    anchorable or explicitly-unanchorable boundary.

    Returns ``(checks_df, parent_classification_df)``.
    """
    checks: list[dict[str, Any]] = []
    required_structural = {
        "source_system", "comparison_scope", "original_source_flow",
        "original_source_product", "component_esto_flow", "component_esto_product",
        "common_row_id", "is_exact_row",
    }
    missing = required_structural.difference(structural_df.columns)
    checks.append({
        "check": "structural_schema",
        "status": "failed" if missing else "passed",
        "reason": f"missing:{'|'.join(sorted(missing))}" if missing else "ok",
    })
    for system, path in converted_paths.items():
        header = pd.read_csv(path, nrows=0)
        try:
            normalize_converted_output(header, system)
            checks.append({"check": f"converted_schema:{system}", "status": "passed", "reason": "ok"})
        except ValueError as error:
            checks.append({"check": f"converted_schema:{system}", "status": "failed", "reason": str(error)})

    classifications: list[dict[str, Any]] = []
    for system in SOURCE_SYSTEMS:
        for axis in ["flow", "product"]:
            boundaries = build_parent_boundaries(structural_df, tree_df, system, axis)
            for parent, boundary in boundaries.items():
                classifications.append({
                    "source_system": system, "validation_axis": axis,
                    "parent_code": parent, "boundary_kind": boundary.kind,
                    "anchorable": boundary.anchorable,
                    "mapped_member_count": boundary.member_count,
                    "component_count": len(boundary.components),
                })
    classification_df = pd.DataFrame(classifications)
    resolved = classification_df["boundary_kind"].isin({"exact", "rollup", "shared_exact", "none"}).all()
    checks.append({
        "check": "every_parent_resolves",
        "status": "passed" if resolved and not classification_df.empty else "failed",
        "reason": "all parents classified" if resolved else "unresolved boundary kind",
    })
    return pd.DataFrame(checks), classification_df


def summarise_reconciliation(detail_df: pd.DataFrame) -> pd.DataFrame:
    """Summarize statuses per axis/system; an empty validation is never a pass."""
    group_columns = ["validation_axis", "source_system"]
    if detail_df.empty:
        return pd.DataFrame([{
            "validation_axis": "", "source_system": "", "passed": 0, "failed": 0,
            "unanchorable": 0, "status": "failed", "reason": "empty_validation",
        }])
    summary = detail_df.groupby(group_columns + ["status"], dropna=False).size().unstack(fill_value=0)
    for status in ["passed", "failed", "unanchorable"]:
        if status not in summary:
            summary[status] = 0
    summary = summary.reset_index()
    summary["status"] = summary.apply(
        lambda row: "failed" if row["failed"] else "passed" if row["passed"] else "unanchorable",
        axis=1,
    )
    summary["reason"] = ""
    return summary[[*group_columns, "passed", "failed", "unanchorable", "status", "reason"]]


# --------------------------------------------------------------------------- #
# Raw source loading (left side), memory-bounded and economy/year filtered.
# --------------------------------------------------------------------------- #

def _melt_year_columns(df: pd.DataFrame, id_columns: list[str], years: set[int] | None) -> pd.DataFrame:
    year_columns = [c for c in df.columns if str(c).isdigit() and (years is None or int(c) in years)]
    if not year_columns:
        return pd.DataFrame(columns=id_columns + ["year", "value"])
    melted = df.melt(id_vars=id_columns, value_vars=year_columns, var_name="year", value_name="value")
    melted["year"] = pd.to_numeric(melted["year"], errors="coerce").astype("Int64")
    return melted


def _normalize_raw_leap(chunk: pd.DataFrame, economies: set[str] | None, years: set[int] | None) -> pd.DataFrame:
    result = chunk.rename(columns={"leap_flow": "source_flow", "leap_product": "source_product"}).copy()
    result["economy"] = _normalize_economy(result["economy"])
    if economies is not None:
        result = result[result["economy"].isin(economies)]
    result["year"] = pd.to_numeric(result["year"], errors="coerce").astype("Int64")
    if years is not None:
        result = result[result["year"].isin(years)]
    result["source_system"] = "LEAP"
    return result[["source_system", "economy", "scenario", "year", "source_flow", "source_product", "value"]]


def _normalize_raw_esto(chunk: pd.DataFrame, economies: set[str] | None, years: set[int] | None) -> pd.DataFrame:
    result = chunk.copy()
    result["economy"] = _normalize_economy(result["economy"])
    if economies is not None:
        result = result[result["economy"].isin(economies)]
    result = result.rename(columns={"flows": "source_flow", "products": "source_product"})
    id_columns = ["economy", "source_flow", "source_product"]
    melted = _melt_year_columns(result, id_columns, years)
    melted["source_system"] = "ESTO"
    melted["scenario"] = "historical"
    return melted[["source_system", "economy", "scenario", "year", "source_flow", "source_product", "value"]]


NINTH_SECTOR_COLUMNS = ["sectors", "sub1sectors", "sub2sectors", "sub3sectors", "sub4sectors"]


def _join_path(values: Iterable[Any]) -> str:
    return "/".join(
        str(v).strip() for v in values
        if pd.notna(v) and str(v).strip() not in {"", "x"}
    )


def _normalize_raw_ninth(chunk: pd.DataFrame, economies: set[str] | None, years: set[int] | None) -> pd.DataFrame:
    result = chunk.copy()
    result["economy"] = _normalize_economy(result["economy"])
    if economies is not None:
        result = result[result["economy"].isin(economies)]
    if result.empty:
        return pd.DataFrame(columns=["source_system", "economy", "scenario", "year", "source_flow", "source_product", "value"])
    result["source_flow"] = result[NINTH_SECTOR_COLUMNS].apply(_join_path, axis=1)
    result["source_product"] = result[["fuels", "subfuels"]].apply(_join_path, axis=1)
    result = result.rename(columns={"scenarios": "scenario"})
    id_columns = ["economy", "scenario", "source_flow", "source_product"]
    melted = _melt_year_columns(result, id_columns, years)
    melted["source_system"] = "NINTH"
    return melted[["source_system", "economy", "scenario", "year", "source_flow", "source_product", "value"]]


_RAW_NORMALIZERS = {
    "LEAP": _normalize_raw_leap,
    "ESTO": _normalize_raw_esto,
    "NINTH": _normalize_raw_ninth,
}


def iter_raw_partitions(
    source_system: str,
    raw_path: Path,
    economies: set[str] | None,
    years: set[int] | None,
    chunksize: int = 250_000,
) -> Iterator[pd.DataFrame]:
    """Yield one normalized raw partition (economy, scenario, year) at a time.

    Rows are aggregated to ``(source_flow, source_product)`` per partition while
    streaming, so peak memory is bounded by the filtered slice rather than the
    whole source file.
    """
    normalizer = _RAW_NORMALIZERS[source_system]
    accumulator: dict[tuple[Any, Any, Any], dict[tuple[str, str], float]] = defaultdict(lambda: defaultdict(float))
    for chunk in pd.read_csv(raw_path, dtype=object, chunksize=chunksize):
        normalized = normalizer(chunk, economies, years)
        if normalized.empty:
            continue
        normalized["value"] = pd.to_numeric(normalized["value"], errors="coerce").fillna(0.0)
        grouped = normalized.groupby(
            ["economy", "scenario", "year", "source_flow", "source_product"], dropna=False
        )["value"].sum()
        for (economy, scenario, year, flow, product), value in grouped.items():
            accumulator[(economy, scenario, year)][(flow, product)] += float(value)
    for (economy, scenario, year), pairs in accumulator.items():
        rows = [
            {"source_system": source_system, "economy": economy, "scenario": scenario,
             "year": year, "source_flow": flow, "source_product": product, "value": value}
            for (flow, product), value in pairs.items()
        ]
        yield pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Slice selection.
# --------------------------------------------------------------------------- #

def default_slice_years(converted_by_system: dict[str, pd.DataFrame]) -> dict[str, set[int]]:
    """Boundary years per system: ESTO at its last historical year Y1, Ninth at
    Y1+1 (first projection past the ESTO horizon), LEAP at both."""
    esto = converted_by_system.get("ESTO")
    if esto is None or esto.empty:
        raise ValueError("Cannot derive slice years: no ESTO converted output present.")
    y1 = int(pd.to_numeric(esto["year"], errors="coerce").max())
    return {"ESTO": {y1}, "NINTH": {y1 + 1}, "LEAP": {y1, y1 + 1}}


# --------------------------------------------------------------------------- #
# Orchestration.
# --------------------------------------------------------------------------- #

DEFAULT_CONVERTED_PATHS = {
    "LEAP": REPO_ROOT / "results/mapping_relationships/leap_results_converted_to_esto.csv",
    "NINTH": REPO_ROOT / "results/mapping_relationships/ninth_results_converted_to_esto.csv",
    "ESTO": REPO_ROOT / "results/mapping_relationships/esto_results_exact_rows.csv",
}
DEFAULT_RAW_PATHS = {
    "LEAP": REPO_ROOT / "results/mapping_relationships/raw_leap_results.csv",
    "NINTH": REPO_ROOT / "data/merged_file_energy_ALL_20251106.csv",
    "ESTO": REPO_ROOT / "data/00APEC_2025_low_with_subtotals.csv",
}


def run_anchor_reconciliation(
    mode: str,
    structural_path: Path,
    tree_path: Path,
    output_dir: Path,
    converted_paths: dict[str, Path] | None = None,
    raw_paths: dict[str, Path] | None = None,
    economies: set[str] | None = None,
    years_by_system: dict[str, set[int]] | None = None,
    tolerance: float = 0.01,
    pass_sample_size: int = 200,
) -> dict[str, Any]:
    """Run structural, slice, or full anchor reconciliation with bounded memory."""
    if mode not in VALIDATION_MODES:
        raise ValueError(f"Unknown mode {mode!r}; expected {sorted(VALIDATION_MODES)}")
    converted_paths = converted_paths or DEFAULT_CONVERTED_PATHS
    raw_paths = raw_paths or DEFAULT_RAW_PATHS
    structural = pd.read_csv(structural_path, dtype=object)
    tree = pd.read_csv(tree_path, dtype=object)

    output_dir = Path(output_dir)
    staging = output_dir.with_name(output_dir.name + ".building")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    if mode == "structural":
        checks, classification = validate_structural(structural, tree, converted_paths)
        checks.to_csv(staging / "validation_summary.csv", index=False)
        classification.to_csv(staging / "parent_boundary_classification.csv", index=False)
        pd.DataFrame(columns=DETAIL_COLUMNS).to_csv(staging / "validation_failures.csv", index=False)
        pd.DataFrame(columns=DETAIL_COLUMNS).to_csv(staging / "unmatched_unanchorable_boundaries.csv", index=False)
        pd.DataFrame([{"mode": mode, "status": "complete"}]).to_csv(
            staging / "partition_status_and_value_accounting.csv", index=False
        )
        manifest = {"mode": mode, "status": "complete", "checks": len(checks), "parents": len(classification)}
    else:
        # Slice needs the ESTO horizon to derive years; load converted filtered
        # to economies first (still bounded), then derive/reuse the year slice.
        if mode == "slice" and years_by_system is None:
            converted_for_years = {
                system: load_converted_output(converted_paths[system], system, economies=economies)
                for system in SOURCE_SYSTEMS
            }
            years_by_system = default_slice_years(converted_for_years)

        summary_frames: list[pd.DataFrame] = []
        failure_frames: list[pd.DataFrame] = []
        unanchorable_frames: list[pd.DataFrame] = []
        pass_frames: list[pd.DataFrame] = []
        accounting_records: list[dict[str, Any]] = []
        for system in SOURCE_SYSTEMS:
            years = years_by_system.get(system) if years_by_system else None
            converted = load_converted_output(
                converted_paths[system], system, economies=economies, years=years
            )
            boundaries_by_axis = {
                axis: build_parent_boundaries(structural, tree, system, axis)
                for axis in ["flow", "product"]
            }
            converted_components_by_axis = {
                axis: set(zip(converted["esto_flow"], converted["esto_product"]))
                for axis in ["flow", "product"]
            } if not converted.empty else {"flow": set(), "product": set()}
            partition_count = 0
            for raw_partition in iter_raw_partitions(system, raw_paths[system], economies, years):
                partition_count += 1
                economy = str(raw_partition["economy"].iloc[0])
                scenario = str(raw_partition["scenario"].iloc[0])
                year = raw_partition["year"].iloc[0]
                partition_converted = converted[
                    (converted["economy"] == economy)
                    & (converted["scenario"].astype(str).str.casefold() == scenario.casefold())
                    & (converted["year"] == year)
                ]
                detail = reconcile_partition(
                    raw_partition, partition_converted, boundaries_by_axis,
                    converted_components_by_axis, system, tolerance,
                )
                summary_frames.append(detail)
                failure_frames.append(detail[detail["status"] == "failed"])
                unanchorable_frames.append(detail[detail["status"] == "unanchorable"])
                passes = detail[detail["status"] == "passed"]
                pass_frames.append(passes)
                accounting_records.append({
                    "source_system": system, "economy": economy, "scenario": scenario,
                    "year": int(year) if pd.notna(year) else "",
                    "raw_total": float(pd.to_numeric(raw_partition["value"], errors="coerce").fillna(0).sum()),
                    "converted_total": float(partition_converted["value"].sum()),
                    "parents_checked": len(detail),
                    "passed": int((detail["status"] == "passed").sum()),
                    "failed": int((detail["status"] == "failed").sum()),
                    "unanchorable": int((detail["status"] == "unanchorable").sum()),
                })
            if partition_count == 0:
                accounting_records.append({
                    "source_system": system, "economy": "", "scenario": "", "year": "",
                    "raw_total": 0.0, "converted_total": float(converted["value"].sum()),
                    "parents_checked": 0, "passed": 0, "failed": 0, "unanchorable": 0,
                })

        all_detail = pd.concat(summary_frames, ignore_index=True) if summary_frames else pd.DataFrame(columns=DETAIL_COLUMNS)
        summary = summarise_reconciliation(all_detail)
        failures = pd.concat(failure_frames, ignore_index=True) if failure_frames else pd.DataFrame(columns=DETAIL_COLUMNS)
        unanchorable = pd.concat(unanchorable_frames, ignore_index=True) if unanchorable_frames else pd.DataFrame(columns=DETAIL_COLUMNS)
        passes = pd.concat(pass_frames, ignore_index=True) if pass_frames else pd.DataFrame(columns=DETAIL_COLUMNS)

        summary.to_csv(staging / "validation_summary.csv", index=False)
        failures.to_csv(staging / "validation_failures.csv", index=False)
        unanchorable.to_csv(staging / "unmatched_unanchorable_boundaries.csv", index=False)
        pd.DataFrame(accounting_records).to_csv(staging / "partition_status_and_value_accounting.csv", index=False)
        pass_summary = (
            passes.groupby(["validation_axis", "source_system"]).size().reset_index(name="passed_count")
            if not passes.empty else pd.DataFrame(columns=["validation_axis", "source_system", "passed_count"])
        )
        pass_summary.to_csv(staging / "validation_pass_summary.csv", index=False)
        passes.sort_values(DETAIL_COLUMNS[:6]).head(pass_sample_size).to_csv(
            staging / "validation_pass_sample.csv", index=False
        )
        manifest = {
            "mode": mode, "status": "complete",
            "economies": sorted(economies) if economies else "all",
            "years_by_system": {k: sorted(v) for k, v in (years_by_system or {}).items()},
            "checks": len(all_detail),
            "passed": int((all_detail["status"] == "passed").sum()),
            "failed": int((all_detail["status"] == "failed").sum()),
            "unanchorable": int((all_detail["status"] == "unanchorable").sum()),
        }
    (staging / "reconciliation_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.move(str(staging), str(output_dir))
    return manifest


def run_anchor_contribution_breakdown(
    structural_path: Path,
    tree_path: Path,
    output_dir: Path,
    converted_paths: dict[str, Path] | None = None,
    raw_paths: dict[str, Path] | None = None,
    economies: set[str] | None = None,
    years_by_system: dict[str, set[int]] | None = None,
    systems: tuple[str, ...] = SOURCE_SYSTEMS,
    statuses: tuple[str, ...] = ("failed",),
    tolerance: float = 0.01,
) -> dict[str, Any]:
    """Phase 1: explain failed anchors from their ESTO-pair contributors.

    For each requested source system this reconciles a slice, then decomposes
    every check whose status is in ``statuses`` into contributor rows. It writes
    ``anchor_contribution_breakdown.csv`` (one row per contributor) and
    ``anchor_contribution_summary.csv`` (one row per check, carrying
    ``breakdown_remainder`` and ``lineage_complete``). This adds no numeric
    observation the reconciliation does not already make; it only re-expresses
    the same totals contributor-by-contributor.

    The default ``systems``/``statuses`` reproduce the two ESTO oil-family
    failures when run on the ``20USA`` slice.
    """
    converted_paths = converted_paths or DEFAULT_CONVERTED_PATHS
    raw_paths = raw_paths or DEFAULT_RAW_PATHS
    structural = pd.read_csv(structural_path, dtype=object)
    tree = pd.read_csv(tree_path, dtype=object)

    output_dir = Path(output_dir)
    staging = output_dir.with_name(output_dir.name + ".building")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    if years_by_system is None:
        converted_for_years = {
            system: load_converted_output(converted_paths[system], system, economies=economies)
            for system in SOURCE_SYSTEMS
        }
        years_by_system = default_slice_years(converted_for_years)

    contribution_frames: list[pd.DataFrame] = []
    summary_frames: list[pd.DataFrame] = []
    for system in systems:
        years = years_by_system.get(system) if years_by_system else None
        converted = load_converted_output(
            converted_paths[system], system, economies=economies, years=years
        )
        boundaries_by_axis = {
            axis: build_parent_boundaries(structural, tree, system, axis)
            for axis in ["flow", "product"]
        }
        converted_components_by_axis = {
            axis: set(zip(converted["esto_flow"], converted["esto_product"]))
            for axis in ["flow", "product"]
        } if not converted.empty else {"flow": set(), "product": set()}
        for raw_partition in iter_raw_partitions(system, raw_paths[system], economies, years):
            economy = str(raw_partition["economy"].iloc[0])
            scenario = str(raw_partition["scenario"].iloc[0])
            year = raw_partition["year"].iloc[0]
            partition_converted = converted[
                (converted["economy"] == economy)
                & (converted["scenario"].astype(str).str.casefold() == scenario.casefold())
                & (converted["year"] == year)
            ]
            contributions, summary = build_anchor_contributions(
                raw_partition, partition_converted, boundaries_by_axis,
                converted_components_by_axis, system, tolerance, statuses,
            )
            if not contributions.empty:
                contribution_frames.append(contributions)
            if not summary.empty:
                summary_frames.append(summary)

    contributions_all = (
        pd.concat(contribution_frames, ignore_index=True)
        if contribution_frames else pd.DataFrame(columns=CONTRIBUTION_COLUMNS)
    )
    summary_all = (
        pd.concat(summary_frames, ignore_index=True)
        if summary_frames else pd.DataFrame(columns=CONTRIBUTION_SUMMARY_COLUMNS)
    )

    contributions_all.to_csv(staging / "anchor_contribution_breakdown.csv", index=False)
    summary_all.to_csv(staging / "anchor_contribution_summary.csv", index=False)

    incomplete = summary_all[~summary_all["lineage_complete"]] if not summary_all.empty else summary_all
    partial = summary_all[~summary_all["fully_attributed"]] if not summary_all.empty else summary_all
    max_remainder = (
        float(summary_all["breakdown_remainder"].abs().max()) if not summary_all.empty else 0.0
    )
    manifest = {
        "schema_version": BREAKDOWN_SCHEMA_VERSION,
        "status": "complete",
        "systems": list(systems),
        "statuses": list(statuses),
        "economies": sorted(economies) if economies else "all",
        "years_by_system": {k: sorted(v) for k, v in (years_by_system or {}).items()},
        "checks_explained": int(len(summary_all)),
        "contributor_rows": int(len(contributions_all)),
        "max_abs_remainder": max_remainder,
        "lineage_complete_all": bool(incomplete.empty),
        "fully_attributed_count": int((summary_all["fully_attributed"]).sum()) if not summary_all.empty else 0,
        "partially_attributed_check_ids": partial["check_id"].tolist() if not partial.empty else [],
        "incomplete_check_ids": incomplete["check_id"].tolist() if not incomplete.empty else [],
    }
    (staging / "contribution_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.move(str(staging), str(output_dir))
    return manifest


# --- Notebook run block ---

RUN_RECONCILIATION = False
RECONCILIATION_MODE = "slice"
RECONCILIATION_ECONOMY = "20USA"

if RUN_RECONCILIATION:
    RECONCILIATION_RESULT = run_anchor_reconciliation(
        mode=RECONCILIATION_MODE,
        structural_path=REPO_ROOT / "results/common_esto/structural_artifacts/source_pair_to_common_row.csv",
        tree_path=REPO_ROOT / "results/tree_structure/all_dataset_trees.csv",
        output_dir=REPO_ROOT / "results/common_esto/anchor_reconciliation",
        economies={RECONCILIATION_ECONOMY} if RECONCILIATION_MODE != "full" else None,
    )
    print(json.dumps(RECONCILIATION_RESULT, indent=2))

#%%

# --- Contributor-breakdown run block (Phase 1) ---

RUN_CONTRIBUTION_BREAKDOWN = False
CONTRIBUTION_ECONOMY = "20USA"
# All three systems: ESTO reproduces the oil-family failures per row; LEAP/Ninth
# net their bijective edges and flag fan-out / many-to-one members unresolved.
CONTRIBUTION_SYSTEMS = SOURCE_SYSTEMS

if RUN_CONTRIBUTION_BREAKDOWN:
    CONTRIBUTION_RESULT = run_anchor_contribution_breakdown(
        structural_path=REPO_ROOT / "results/common_esto/structural_artifacts/source_pair_to_common_row.csv",
        tree_path=REPO_ROOT / "results/tree_structure/all_dataset_trees.csv",
        output_dir=REPO_ROOT / "results/common_esto/anchor_contribution_breakdown",
        economies={CONTRIBUTION_ECONOMY},
        systems=CONTRIBUTION_SYSTEMS,
    )
    print(json.dumps(CONTRIBUTION_RESULT, indent=2))

#%%
