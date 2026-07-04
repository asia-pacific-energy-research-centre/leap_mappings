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
        "member_count", "is_rollup", "contaminating_codes",
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
        boundaries[parent] = ParentBoundary(
            parent, source_pairs, components, common_rows, len(members), is_rollup,
            frozenset(contaminating),
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
