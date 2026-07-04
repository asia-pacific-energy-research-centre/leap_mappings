"""
build_dataset_tree_structure.py

Build hierarchical tree structures for ESTO, 9th Edition, LEAP, and Common ESTO
datasets. Outputs tree CSVs to results/tree_structure/ and runs recursive sum
validation against the ESTO balance data.

Outputs (results/tree_structure/):
    esto_tree.csv                         — ESTO flow and product node hierarchy
    ninth_tree.csv                        — 9th Edition sector and fuel node hierarchy
    leap_tree.csv                         — LEAP sector and fuel node hierarchy
    common_esto_tree.csv                  — Common ESTO flow and product node hierarchy
    esto_validation.csv                   — Stage A: ESTO recursive sum validation
    ninth_validation.csv                  — Stage A: Ninth fuel parent/child consistency
    leap_validation.csv                   — Stage A: LEAP sector parent/child consistency
    common_esto_validation.csv            — Stage B: Common ESTO recursive sum validation
                                            with inherited_source_inconsistency flag
    common_esto_non_esto_parent_child_edges.csv

Stage A / Stage B design
------------------------
Stage A validates each raw source dataset independently before any cross-dataset
comparison is performed.  Mismatches found in Stage A are recorded as
``inherited_source_inconsistency`` in the Stage B Common ESTO validation output,
distinguishing gaps that already existed in the source from gaps introduced by
the mapping.

Tree CSV columns:
    dataset, axis, code, label, level, parent_code, is_leaf, is_subtotal
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Repo root and paths
# ---------------------------------------------------------------------------

def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "config" / "outlook_mappings_master.xlsx").exists():
            return parent
    raise RuntimeError("Could not locate repo root (no config/outlook_mappings_master.xlsx found).")

REPO_ROOT = _find_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ESTO_DATA_PATH        = REPO_ROOT / "data" / "00APEC_2025_low_with_subtotals.csv"
NINTH_DATA_PATH       = REPO_ROOT / "data" / "merged_file_energy_ALL_20251106.csv"
LEAP_DATA_PATH        = REPO_ROOT / "results" / "mapping_relationships" / "raw_leap_results.csv"
LEGACY_LEAP_DATA_PATH = REPO_ROOT / "data" / "usa_leap_balance_long.csv"
OUTLOOK_MAPPINGS_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
COMMON_ESTO_ROWS_PATH = REPO_ROOT / "results" / "common_esto" / "common_esto_rows.csv"
COMMON_ESTO_COMPARISON_PATH = REPO_ROOT / "results" / "common_esto" / "common_esto_comparison_data.csv"
TREE_OUTPUT_DIR       = REPO_ROOT / "results" / "tree_structure"
LEAP_VAR_BASE_YEAR    = 2022

TREE_COLS = ["dataset", "axis", "code", "label", "level", "parent_code", "is_leaf", "is_subtotal"]


def combine_dataset_trees(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate per-dataset tree frames into one explicit edge table.

    Downstream consumers (the lineage anchor validator, partitioned application
    source-parent lineage) need a single ``dataset/axis/code/parent_code`` table.
    Empty frames are dropped so an unavailable dataset does not add blank rows.
    """
    kept = [frame for frame in frames if frame is not None and not frame.empty]
    if not kept:
        return pd.DataFrame(columns=TREE_COLS)
    return pd.concat(kept, ignore_index=True)


_ESTO_PREFIX_RE = re.compile(r"^([\d.]+)\s")

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _str(val: Any) -> str:
    return "" if (val is None or (isinstance(val, float) and pd.isna(val))) else str(val).strip()


def _extract_esto_prefix(label: str) -> str | None:
    m = _ESTO_PREFIX_RE.match(label)
    return m.group(1) if m else None


def _parent_prefix(prefix: str) -> str | None:
    parts = prefix.split(".")
    return ".".join(parts[:-1]) if len(parts) > 1 else None


def _build_esto_axis_tree(codes: list[str], axis: str, dataset: str,
                           subtotal_codes: set[str]) -> pd.DataFrame:
    """
    Build a tree DataFrame for one ESTO axis (flow or product) from a list of
    unique code labels.  Hierarchy is inferred from the numeric dot-prefix.
    """
    # Build prefix → full label lookup
    prefix_map: dict[str, str] = {}
    for c in codes:
        p = _extract_esto_prefix(c)
        if p:
            prefix_map[p] = c

    rows = []
    for c in codes:
        p = _extract_esto_prefix(c)
        if p is None:
            continue
        parent_p = _parent_prefix(p)
        parent_code = prefix_map.get(parent_p, "") if parent_p else ""
        level = len(p.split("."))
        rows.append({
            "dataset": dataset,
            "axis": axis,
            "code": c,
            "label": c,
            "level": level,
            "parent_code": parent_code,
            "is_subtotal": c in subtotal_codes,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=TREE_COLS)

    leaf_mask = ~df["code"].isin(df["parent_code"].unique())
    df["is_leaf"] = leaf_mask
    return df[TREE_COLS].reset_index(drop=True)


# ---------------------------------------------------------------------------
# ESTO tree
# ---------------------------------------------------------------------------

def build_esto_tree(data_csv_path: Path = ESTO_DATA_PATH) -> pd.DataFrame:
    """Build ESTO flow and product hierarchy from the balance data CSV."""
    df = pd.read_csv(data_csv_path, dtype=object)

    flows = sorted(df["flows"].dropna().unique())
    prods = sorted(df["products"].dropna().unique())

    # is_subtotal is derived from tree structure: a node is a subtotal iff it has children.
    # (The data's is_subtotal column reflects M6 mapping context, not product hierarchy.)
    all_flow_prefixes = {_extract_esto_prefix(f) for f in flows if _extract_esto_prefix(f)}
    subtotal_flows: set[str] = {
        f for f in flows
        if (p := _extract_esto_prefix(f)) and any(
            op.startswith(p + ".") for op in all_flow_prefixes if op != p
        )
    }
    all_prod_prefixes = {_extract_esto_prefix(p) for p in prods if _extract_esto_prefix(p)}
    subtotal_prods: set[str] = {
        p for p in prods
        if (pp := _extract_esto_prefix(p)) and any(
            op.startswith(pp + ".") for op in all_prod_prefixes if op != pp
        )
    }

    flow_tree = _build_esto_axis_tree(flows, "flow", "esto", subtotal_flows)
    prod_tree = _build_esto_axis_tree(prods, "product", "esto", subtotal_prods)

    return pd.concat([flow_tree, prod_tree], ignore_index=True)


# ---------------------------------------------------------------------------
# 9th Edition tree
# ---------------------------------------------------------------------------

_NINTH_SECTOR_COLS = ["sectors", "sub1sectors", "sub2sectors", "sub3sectors", "sub4sectors"]
_NINTH_FUEL_COLS   = ["fuels", "subfuels"]


def _build_ninth_subtotal_results_sets(df: pd.DataFrame) -> tuple[set[str], set[str]]:
    """
    Return (subtotal_sector_codes, subtotal_fuel_codes) derived from the Ninth data.

    Fuel subtotals (subtotal_fuel_codes)
    -------------------------------------
    A fuel code is a subtotal if it appears as a parent of subfuels anywhere in
    the data (structural: has at least one row where subfuels != 'x').  This is
    the clean fuel signal and is independent of subtotal_results.

    Sector subtotals (subtotal_sector_codes)
    -----------------------------------------
    A sector path is a subtotal if subtotal_results is True for ANY row where
    that sector path is the deepest path AND the fuel is a LEAF fuel (not in
    subtotal_fuel_codes AND subfuels == 'x').

    This separation is necessary because subtotal_results fires on rows where
    EITHER the sector OR the fuel is an aggregate.  Without filtering to leaf
    fuels, supply-side sectors such as 01_production appear as sector subtotals
    simply because subtotal fuel buckets (e.g. 01_coal) appear under them.
    """
    def _truthy(val: Any) -> bool:
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            return val.strip().lower() in {"true", "1", "yes"}
        return False

    # Pass 1: fuel subtotals from structure (fuels that have subfuel children)
    subtotal_fuels: set[str] = set(
        df.loc[df["subfuels"].notna() & (df["subfuels"].astype(str).str.strip() != "x"), "fuels"]
        .dropna()
        .unique()
    )

    # Pass 2: sector subtotals from subtotal_results on leaf-fuel rows only
    subtotal_sectors: set[str] = set()
    leaf_fuel_mask = (
        df["subfuels"].isna() | (df["subfuels"].astype(str).str.strip() == "x")
    ) & (~df["fuels"].isin(subtotal_fuels))

    for _, row in df[leaf_fuel_mask].iterrows():
        if not _truthy(row.get("subtotal_results", False)):
            continue
        vals = [_str(row.get(c, "")) for c in _NINTH_SECTOR_COLS]
        segments: list[str] = []
        for v in vals:
            if v in ("", "x"):
                break
            segments.append(v)
        if segments:
            subtotal_sectors.add("/".join(segments))

    return subtotal_sectors, subtotal_fuels


def _ninth_sector_tree(df: pd.DataFrame, subtotal_sector_codes: set[str]) -> pd.DataFrame:
    """
    Build 9th Edition sector hierarchy.

    Level is determined by how many non-'x' sector columns a row uses.
    Node code: slash-joined non-'x' values, e.g. '09_electricity/09_01_main_activity'.

    is_subtotal is True when the node's full path appears in subtotal_sector_codes,
    which is derived from subtotal_results in the source data.
    """
    seen: dict[str, dict] = {}

    for _, row in df[_NINTH_SECTOR_COLS].drop_duplicates().iterrows():
        vals = [_str(row[c]) for c in _NINTH_SECTOR_COLS]
        segments: list[str] = []
        for v in vals:
            if v in ("", "x"):
                break
            segments.append(v)
        if not segments:
            continue

        for depth in range(1, len(segments) + 1):
            code = "/".join(segments[:depth])
            if code in seen:
                continue
            parent_code = "/".join(segments[: depth - 1]) if depth > 1 else ""
            seen[code] = {
                "dataset": "ninth",
                "axis": "sector",
                "code": code,
                "label": segments[depth - 1],
                "level": depth,
                "parent_code": parent_code,
                "is_subtotal": code in subtotal_sector_codes,
            }

    if not seen:
        return pd.DataFrame(columns=TREE_COLS)

    result = pd.DataFrame(seen.values())
    leaf_mask = ~result["code"].isin(result["parent_code"].unique())
    result["is_leaf"] = leaf_mask
    return result[TREE_COLS].reset_index(drop=True)


def _ninth_fuel_tree(df: pd.DataFrame, subtotal_fuel_codes: set[str]) -> pd.DataFrame:
    """
    Build 9th Edition fuel hierarchy.

    Level 1 = fuels; Level 2 = subfuels (where subfuels != 'x').
    Node code: slash-joined, e.g. '01_coal/01_01_coking_coal'.

    is_subtotal is True when the top-level fuel code appears in subtotal_fuel_codes,
    derived from subtotal_results in the source data.  Subfuel nodes are always
    leaves and are never marked as subtotals.
    """
    seen: dict[str, dict] = {}

    for _, row in df[_NINTH_FUEL_COLS].drop_duplicates().iterrows():
        fuel    = _str(row["fuels"])
        subfuel = _str(row["subfuels"])
        if not fuel:
            continue

        if fuel not in seen:
            seen[fuel] = {
                "dataset": "ninth",
                "axis": "fuel",
                "code": fuel,
                "label": fuel,
                "level": 1,
                "parent_code": "",
                "is_subtotal": fuel in subtotal_fuel_codes,
            }

        if subfuel and subfuel != "x":
            code = f"{fuel}/{subfuel}"
            if code not in seen:
                seen[code] = {
                    "dataset": "ninth",
                    "axis": "fuel",
                    "code": code,
                    "label": subfuel,
                    "level": 2,
                    "parent_code": fuel,
                    "is_subtotal": False,
                }

    if not seen:
        return pd.DataFrame(columns=TREE_COLS)

    result = pd.DataFrame(seen.values())
    leaf_mask = ~result["code"].isin(result["parent_code"].unique())
    result["is_leaf"] = leaf_mask
    return result[TREE_COLS].reset_index(drop=True)


def build_ninth_tree(
    data_csv_path: Path = NINTH_DATA_PATH,
    data_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Build 9th Edition sector and fuel hierarchy from the balance data CSV.

    is_subtotal is derived solely from the subtotal_results column in the source
    data: a node is marked True if subtotal_results is True for any row with that
    sector path or fuel code across all economies and scenarios.
    """
    df = data_df.copy() if data_df is not None else pd.read_csv(data_csv_path, dtype=object)
    subtotal_sector_codes, subtotal_fuel_codes = _build_ninth_subtotal_results_sets(df)
    sector_tree = _ninth_sector_tree(df, subtotal_sector_codes)
    fuel_tree   = _ninth_fuel_tree(df, subtotal_fuel_codes)
    return pd.concat([sector_tree, fuel_tree], ignore_index=True)


# ---------------------------------------------------------------------------
# LEAP tree
# ---------------------------------------------------------------------------

def build_leap_tree(workbook_path: Path = OUTLOOK_MAPPINGS_PATH) -> pd.DataFrame:
    """
    Build LEAP sector and fuel hierarchy from the mapping workbook.

    Sectors come from `leap_sector_name_full_path` (slash-separated paths).
    Fuels come from `raw_leap_fuel_name` (single-level).
    """
    esto_df  = pd.read_excel(workbook_path, sheet_name="leap_combined_esto",  dtype=object)
    ninth_df = pd.read_excel(workbook_path, sheet_name="leap_combined_ninth", dtype=object)
    combined = pd.concat([esto_df, ninth_df], ignore_index=True)

    # --- sectors (slash-separated paths) ---
    sector_nodes: dict[str, dict] = {}
    for raw in combined["leap_sector_name_full_path"].dropna().unique():
        path = _str(raw)
        if not path:
            continue
        segments = [s.strip() for s in path.split("/") if s.strip()]
        for depth in range(1, len(segments) + 1):
            code = "/".join(segments[:depth])
            if code in sector_nodes:
                continue
            parent_code = "/".join(segments[: depth - 1]) if depth > 1 else ""
            sector_nodes[code] = {
                "dataset": "leap",
                "axis": "sector",
                "code": code,
                "label": segments[depth - 1],
                "level": depth,
                "parent_code": parent_code,
                "is_subtotal": False,
            }

    if sector_nodes:
        sector_df = pd.DataFrame(sector_nodes.values())
        leaf_mask = ~sector_df["code"].isin(sector_df["parent_code"].unique())
        sector_df["is_leaf"] = leaf_mask
        parents = set(sector_df.loc[~leaf_mask, "code"])
        sector_df.loc[sector_df["code"].isin(parents), "is_subtotal"] = True
        sector_df = sector_df[TREE_COLS]
    else:
        sector_df = pd.DataFrame(columns=TREE_COLS)

    # --- fuels (flat single-level) ---
    fuel_codes = sorted(combined["raw_leap_fuel_name"].dropna().unique())
    fuel_rows = [
        {
            "dataset": "leap",
            "axis": "fuel",
            "code": _str(f),
            "label": _str(f),
            "level": 1,
            "parent_code": "",
            "is_leaf": True,
            "is_subtotal": False,
        }
        for f in fuel_codes if _str(f)
    ]
    fuel_df = pd.DataFrame(fuel_rows, columns=TREE_COLS) if fuel_rows else pd.DataFrame(columns=TREE_COLS)

    return pd.concat([sector_df, fuel_df], ignore_index=True)


# ---------------------------------------------------------------------------
# Common ESTO tree
# ---------------------------------------------------------------------------

def build_common_esto_tree(common_rows_path: Path = COMMON_ESTO_ROWS_PATH) -> pd.DataFrame:
    """
    Build Common ESTO flow and product hierarchy from common_esto_rows.csv.

    Exact rows follow ESTO dot-notation; non-exact (graph-generated) rows are
    treated as leaf nodes with no inherent parent relationship.
    """
    df = pd.read_csv(common_rows_path, dtype=object)

    # Unique flow and product labels appearing in the common structure
    flow_labels = sorted(df["common_flow_label"].dropna().unique())
    prod_labels = sorted(df["common_product_label"].dropna().unique())

    # Determine which are subtotals from the original ESTO data if present,
    # otherwise infer from tree structure (same as ESTO build_esto_tree).
    all_flow_prefixes = {_extract_esto_prefix(f) for f in flow_labels if _extract_esto_prefix(f)}
    subtotal_flows: set[str] = {
        f for f in flow_labels
        if (p := _extract_esto_prefix(f)) and any(
            op.startswith(p + ".") for op in all_flow_prefixes if op != p
        )
    }
    all_prod_prefixes = {_extract_esto_prefix(p) for p in prod_labels if _extract_esto_prefix(p)}
    subtotal_prods: set[str] = {
        p for p in prod_labels
        if (pp := _extract_esto_prefix(p)) and any(
            op.startswith(pp + ".") for op in all_prod_prefixes if op != pp
        )
    }

    flow_tree = _build_esto_axis_tree(flow_labels, "flow", "common_esto", subtotal_flows)
    prod_tree = _build_esto_axis_tree(prod_labels, "product", "common_esto", subtotal_prods)

    return pd.concat([flow_tree, prod_tree], ignore_index=True)


# ---------------------------------------------------------------------------
# Legacy product-only recursive sum validation
# ---------------------------------------------------------------------------

def _validate_esto_product_recursive_sums_legacy(
    tree_df: pd.DataFrame,
    data_csv_path: Path = ESTO_DATA_PATH,
    tolerance: float = 0.01,
) -> pd.DataFrame:
    """
    Validate that each ESTO product subtotal equals the sum of its direct
    children across all economies and flows.

    Returns a DataFrame with mismatch records. Empty DataFrame = all checks pass.

    Columns:
        economy, flow, parent_product, child_product_count,
        year, parent_value, children_sum, abs_error
    """
    data = pd.read_csv(data_csv_path, dtype=object)
    year_cols = [c for c in data.columns if c.isdigit()]

    # Convert year columns to numeric
    data[year_cols] = data[year_cols].apply(pd.to_numeric, errors="coerce")

    # Build product parent → children mapping from tree (non-leaf nodes are the parents to validate)
    prod_tree = tree_df[(tree_df["dataset"] == "esto") & (tree_df["axis"] == "product")]
    children_map: dict[str, list[str]] = {}
    for _, row in prod_tree.iterrows():
        parent = _str(row["parent_code"])
        if parent:
            children_map.setdefault(parent, []).append(_str(row["code"]))

    mismatches = []

    for parent_prod, children in children_map.items():
        parent_rows   = data[data["products"] == parent_prod]
        children_rows = data[data["products"].isin(children)]

        if parent_rows.empty or children_rows.empty:
            continue

        parent_sum   = parent_rows.groupby(["economy", "flows"])[year_cols].sum()
        children_sum = children_rows.groupby(["economy", "flows"])[year_cols].sum()

        common_idx = parent_sum.index.intersection(children_sum.index)
        if common_idx.empty:
            continue

        p_vals = parent_sum.loc[common_idx]
        c_vals = children_sum.loc[common_idx]
        diff   = (p_vals - c_vals).abs()

        threshold = tolerance * p_vals.abs().clip(lower=1)
        flagged = (diff > threshold).any(axis=1)

        for idx in common_idx[flagged.values]:
            economy, flow = idx
            for yr in year_cols:
                pv = float(p_vals.at[idx, yr]) if not pd.isna(p_vals.at[idx, yr]) else None
                cv = float(c_vals.at[idx, yr]) if not pd.isna(c_vals.at[idx, yr]) else None
                if pv is None or cv is None:
                    continue
                err = abs(pv - cv)
                if err > tolerance * max(abs(pv), 1):
                    mismatches.append({
                        "economy": economy,
                        "flow": flow,
                        "parent_product": parent_prod,
                        "child_product_count": len(children),
                        "year": yr,
                        "parent_value": pv,
                        "children_sum": cv,
                        "abs_error": err,
                    })

    result = pd.DataFrame(mismatches)
    if result.empty:
        return pd.DataFrame(columns=[
            "economy", "flow", "parent_product", "child_product_count",
            "year", "parent_value", "children_sum", "abs_error",
        ])
    return result.sort_values(["economy", "flow", "parent_product", "year"]).reset_index(drop=True)


ESTO_VALIDATION_COLS = [
    "validation_axis",
    "economy",
    "other_axis_value",
    "parent_code",
    "child_count",
    "year",
    "parent_value",
    "children_sum",
    "abs_error",
]

NINTH_VALIDATION_COLS = [
    "source_issue_id",
    "source_system",
    "economy",
    "scenario",
    "year",
    "ninth_sector",
    "parent_ninth_fuel_code",
    "child_ninth_fuel_codes",
    "esto_parent_flow",
    "esto_parent_product",
    "child_esto_products",
    "source_issue_class",
    "mapping_status",
    "child_coverage_status",
    "inheritance_eligible",
    "subtotal_results",
    "child_count",
    "mapped_child_count",
    "parent_value",
    "children_sum",
    "difference",
    "abs_error",
]

NINTH_SECTOR_VALIDATION_COLS = [
    "source_issue_id",
    "source_system",
    "economy",
    "scenario",
    "year",
    "ninth_sector",
    "ninth_fuel",
    "child_ninth_sectors",
    "esto_parent_flow",
    "esto_parent_product",
    "source_issue_class",
    "child_coverage_status",
    "inheritance_eligible",
    "child_count",
    "parent_value",
    "children_sum",
    "difference",
    "abs_error",
]

NINTH_FUEL_VALIDATION_COLS = [
    "source_issue_id",
    "source_system",
    "economy",
    "scenario",
    "year",
    "ninth_sector",
    "ninth_fuel",
    "child_ninth_fuels",
    "esto_parent_product",
    "esto_parent_flow",
    "source_issue_class",
    "child_coverage_status",
    "inheritance_eligible",
    "child_count",
    "parent_value",
    "children_sum",
    "difference",
    "abs_error",
]

LEAP_VALIDATION_COLS = [
    "source_issue_id",
    "source_system",
    "economy",
    "scenario",
    "year",
    "parent_leap_sector_path",
    "parent_leap_sector",
    "leap_product",
    "child_leap_sector_paths",
    "esto_parent_flow",
    "esto_parent_product",
    "child_esto_flows",
    "source_context_status",
    "source_issue_class",
    "mapping_status",
    "child_coverage_status",
    "inheritance_eligible",
    "child_count",
    "mapped_child_count",
    "parent_value",
    "children_sum",
    "difference",
    "abs_error",
]

COMMON_ESTO_VALIDATION_COLS = [
    "validation_axis",
    "comparison_scope",
    "source_system",
    "economy",
    "scenario",
    "other_axis_value",
    "parent_code",
    "child_count",
    "frontier_row_count",
    "missing_expected_children",
    "year",
    "parent_value",
    "children_sum",
    "difference",
    "abs_error",
    "proportional_error",
    "status",
    "reason",
    "source_inconsistency_status",
    "sector_hierarchy_status",
    "fuel_hierarchy_status",
    "source_issue_ids",
    "inherited_source_inconsistency",
]

COMMON_ESTO_NON_ESTO_EDGE_COLS = [
    "axis",
    "parent_code",
    "child_code",
    "risk_reason",
]


def _tree_children_map(tree_df: pd.DataFrame, dataset: str, axis: str) -> dict[str, list[str]]:
    """Return direct parent -> children mapping for one tree axis."""
    axis_tree = tree_df[(tree_df["dataset"] == dataset) & (tree_df["axis"] == axis)]
    children_map: dict[str, list[str]] = {}
    for _, row in axis_tree.iterrows():
        parent = _str(row["parent_code"])
        if parent:
            children_map.setdefault(parent, []).append(_str(row["code"]))
    return children_map


def _common_esto_validation_children_map(tree_df: pd.DataFrame, axis: str) -> dict[str, list[str]]:
    """
    Return Common ESTO parent/child edges that are also present in the ESTO tree.

    Common ESTO can contain generated or projection-only labels such as
    datacentres. Their numeric prefixes may look hierarchical, but they are not
    valid subtotal checks unless the same edge exists in the source ESTO tree.
    """
    common_map = _tree_children_map(tree_df, "common_esto", axis)
    esto_map = _tree_children_map(tree_df, "esto", axis)
    esto_child_sets = {parent: set(children) for parent, children in esto_map.items()}
    filtered: dict[str, list[str]] = {}
    for parent, children in common_map.items():
        valid_children = [child for child in children if child in esto_child_sets.get(parent, set())]
        if valid_children:
            filtered[parent] = valid_children
    return filtered


def common_esto_non_esto_parent_child_edges(tree_df: pd.DataFrame) -> pd.DataFrame:
    """
    Return Common ESTO parent/child edges not present in the source ESTO tree.

    These are review signals for dashboard/additive-total design, not recursive
    subtotal validation failures.
    """
    rows = []
    for axis in ["flow", "product"]:
        common_map = _tree_children_map(tree_df, "common_esto", axis)
        esto_map = _tree_children_map(tree_df, "esto", axis)
        esto_child_sets = {parent: set(children) for parent, children in esto_map.items()}
        for parent, children in common_map.items():
            for child in children:
                if child in esto_child_sets.get(parent, set()):
                    continue
                rows.append({
                    "axis": axis,
                    "parent_code": parent,
                    "child_code": child,
                    "risk_reason": "common_parent_child_edge_not_present_in_source_esto_tree",
                })
    if not rows:
        return pd.DataFrame(columns=COMMON_ESTO_NON_ESTO_EDGE_COLS)
    return pd.DataFrame(rows, columns=COMMON_ESTO_NON_ESTO_EDGE_COLS).sort_values(
        ["axis", "parent_code", "child_code"]
    ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Stage A: source-data consistency pre-checks
# ---------------------------------------------------------------------------

def _truthy(value: Any) -> bool:
    """Return a strict boolean value for source metadata fields."""
    if value is None or pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def _join_sorted(values: list[str] | set[str] | tuple[str, ...]) -> str:
    """Join unique non-empty values in deterministic order."""
    return "|".join(sorted({_str(value) for value in values if _str(value)}))


def _source_issue_id(*parts: Any) -> str:
    """Build a readable, stable identifier for one exact source context."""
    return "source_issue::" + "::".join(_str(part) for part in parts)


def _direct_child_labels(parent_label: str, labels: set[str]) -> set[str]:
    """Return direct dot-hierarchy children of one ESTO code label."""
    parent_prefix = _extract_esto_prefix(parent_label)
    if not parent_prefix:
        return set()
    parent_depth = len(parent_prefix.split("."))
    return {
        label
        for label in labels
        if (prefix := _extract_esto_prefix(label))
        and prefix.startswith(parent_prefix + ".")
        and len(prefix.split(".")) == parent_depth + 1
    }


def _mapping_targets(
    mapping_df: pd.DataFrame,
    source_flow_column: str,
    source_product_column: str,
    target_flow_column: str,
    target_product_column: str,
) -> dict[tuple[str, str], set[tuple[str, str]]]:
    """Return every reviewed target pair for each source pair without first-win loss."""
    targets: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for _, row in mapping_df.iterrows():
        source_pair = (
            _str(row.get(source_flow_column, "")),
            _str(row.get(source_product_column, "")),
        )
        target_pair = (
            _str(row.get(target_flow_column, "")),
            _str(row.get(target_product_column, "")),
        )
        if all(source_pair) and all(target_pair):
            targets.setdefault(source_pair, set()).add(target_pair)
    return targets

def validate_ninth_recursive_sums(
    data_csv_path: Path = NINTH_DATA_PATH,
    workbook_path: Path = OUTLOOK_MAPPINGS_PATH,
    tolerance: float = 0.01,
    leap_var_base_year: int = LEAP_VAR_BASE_YEAR,
    scenario_filter: str = "reference",
    data_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Validate projected Ninth fuel parents against children in exact source context.

    The Common conversion uses top-sector rows and the reference scenario. This
    validation mirrors that boundary, checks only years strictly after
    ``leap_var_base_year``, and uses ``subtotal_results`` because those years are
    projected results. Findings retain scenario and source-sector context. A
    finding is eligible for confirmed Stage B inheritance only when the parent
    and all non-zero children have one unambiguous ESTO mapping and the child
    coverage is complete.
    """
    df = data_df.copy() if data_df is not None else pd.read_csv(data_csv_path, dtype=object)
    year_cols = [
        column
        for column in df.columns
        if str(column).isdigit() and int(column) > int(leap_var_base_year)
    ]
    if not year_cols:
        return pd.DataFrame(columns=NINTH_VALIDATION_COLS)
    df[year_cols] = df[year_cols].apply(pd.to_numeric, errors="coerce")
    if scenario_filter:
        df = df[df["scenarios"].astype(str).str.casefold() == scenario_filter.casefold()].copy()
    # Match the production Ninth conversion boundary.
    df = df[df["sub1sectors"].astype(str).str.strip() == "x"].copy()

    pairs = pd.read_excel(workbook_path, sheet_name="ninth_pairs_to_esto_pairs", dtype=object)
    source_targets = _mapping_targets(
        pairs,
        "9th_sector",
        "9th_fuel",
        "esto_flow",
        "esto_product",
    )

    parent_rows = df[
        (df["subfuels"] == "x")
        & df["subtotal_results"].map(_truthy)
    ].copy()
    child_rows = df[df["subfuels"] != "x"].copy()

    group_cols = [
        "economy",
        "scenarios",
        "sectors",
        "sub1sectors",
        "sub2sectors",
        "sub3sectors",
        "sub4sectors",
        "fuels",
    ]
    child_groups: dict[tuple, pd.DataFrame] = {
        key: group for key, group in child_rows.groupby(group_cols, dropna=False)
    }

    mismatches: list[dict] = []
    for group_key, parent_group in parent_rows.groupby(group_cols, dropna=False):
        children = child_groups.get(group_key)
        if children is None or children.empty:
            continue

        economy = _str(group_key[0])
        scenario = _str(group_key[1])
        ninth_sector = _str(group_key[2])
        fuel_code = _str(group_key[-1])
        parent_targets = source_targets.get((ninth_sector, fuel_code), set())
        # Unmapped source parents cannot contribute to a Stage B Common row.
        # Mapping coverage QA owns those rows; including them here would create
        # thousands of source findings that cannot support inheritance.
        if not parent_targets:
            continue
        parent_mapping_status = (
            "exact" if len(parent_targets) == 1
            else "ambiguous_parent_mapping"
        )
        esto_parent_flow = ""
        esto_parent_product = ""
        if len(parent_targets) == 1:
            esto_parent_flow, esto_parent_product = next(iter(parent_targets))

        for yr in year_cols:
            pv = pd.to_numeric(parent_group[yr], errors="coerce").sum()
            cv = pd.to_numeric(children[yr], errors="coerce").sum()
            if pd.isna(pv) or pd.isna(cv):
                continue
            difference = float(pv - cv)
            err = abs(difference)
            if err <= tolerance * max(abs(pv), 1):
                continue

            child_codes = [_str(value) for value in children["subfuels"].tolist()]
            nonzero_child_codes = [
                _str(row["subfuels"])
                for _, row in children.iterrows()
                if abs(float(pd.to_numeric(row[yr], errors="coerce") or 0.0)) > tolerance
            ]
            child_target_pairs: set[tuple[str, str]] = set()
            missing_children: list[str] = []
            ambiguous_children: list[str] = []
            for child_code in nonzero_child_codes:
                targets = source_targets.get((ninth_sector, child_code), set())
                if not targets:
                    missing_children.append(child_code)
                elif len(targets) > 1:
                    ambiguous_children.append(child_code)
                else:
                    child_target_pairs.update(targets)

            if parent_mapping_status != "exact":
                mapping_status = parent_mapping_status
            elif ambiguous_children:
                mapping_status = "ambiguous_child_mapping"
            elif missing_children:
                mapping_status = "missing_child_mapping"
            elif any(flow != esto_parent_flow for flow, _ in child_target_pairs):
                mapping_status = "child_flow_mismatch"
            else:
                mapping_status = "exact"

            if abs(float(pv)) > tolerance and abs(float(cv)) <= tolerance:
                source_issue_class = "children_incomplete"
                child_coverage_status = "no_nonzero_children"
            elif ambiguous_children:
                source_issue_class = "mapping_ambiguous"
                child_coverage_status = "ambiguous_child_mapping"
            elif missing_children:
                source_issue_class = "children_incomplete"
                child_coverage_status = "unmapped_nonzero_children"
            else:
                source_issue_class = "sum_mismatch"
                child_coverage_status = "complete"

            inheritance_eligible = (
                source_issue_class == "sum_mismatch"
                and mapping_status == "exact"
                and child_coverage_status == "complete"
            )
            mismatches.append({
                "source_issue_id": _source_issue_id(
                    "NINTH", economy, scenario, yr, ninth_sector, fuel_code
                ),
                "source_system": "NINTH",
                "economy": economy,
                "scenario": scenario,
                "year": yr,
                "ninth_sector": ninth_sector,
                "parent_ninth_fuel_code": fuel_code,
                "child_ninth_fuel_codes": _join_sorted(child_codes),
                "esto_parent_flow": esto_parent_flow,
                "esto_parent_product": esto_parent_product,
                "child_esto_products": _join_sorted(
                    {product for _, product in child_target_pairs}
                ),
                "source_issue_class": source_issue_class,
                "mapping_status": mapping_status,
                "child_coverage_status": child_coverage_status,
                "inheritance_eligible": inheritance_eligible,
                "subtotal_results": True,
                "child_count": len(set(child_codes)),
                "mapped_child_count": len(child_target_pairs),
                "parent_value": float(pv),
                "children_sum": float(cv),
                "difference": difference,
                "abs_error": err,
            })

    if not mismatches:
        return pd.DataFrame(columns=NINTH_VALIDATION_COLS)
    return (
        pd.DataFrame(mismatches)
        .sort_values(["economy", "year", "parent_ninth_fuel_code"])
        .reset_index(drop=True)
    )


def validate_ninth_sector_recursive_sums(
    data_csv_path: Path = NINTH_DATA_PATH,
    workbook_path: Path = OUTLOOK_MAPPINGS_PATH,
    common_rows_path: Path = COMMON_ESTO_ROWS_PATH,
    tolerance: float = 0.01,
    leap_var_base_year: int = LEAP_VAR_BASE_YEAR,
    scenario_filter: str = "reference",
    data_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Validate projected Ninth sub1sector parents against sub2sector children.

    Checks whether each sub1sector aggregate (sub2sectors='x') matches the
    sum of its sub2sector children for each (economy, scenario, ninth_fuel, year).
    Produces findings keyed to Stage B's common ESTO partition labels so that
    _build_source_inconsistency_lookup can mark matching Stage B flow-axis
    mismatches as confirmed_inherited.
    """
    df = data_df.copy() if data_df is not None else pd.read_csv(data_csv_path, dtype=object)
    year_cols = [
        c for c in df.columns
        if str(c).isdigit() and int(c) > int(leap_var_base_year)
    ]
    if not year_cols:
        return pd.DataFrame(columns=NINTH_SECTOR_VALIDATION_COLS)
    df[year_cols] = df[year_cols].apply(pd.to_numeric, errors="coerce")
    if scenario_filter:
        df = df[df["scenarios"].astype(str).str.casefold() == scenario_filter.casefold()].copy()

    # ninth_fuel: subfuels if not 'x', else fuels — mirrors prepare_ninth_long_format
    df["ninth_fuel"] = df["subfuels"].astype(str).str.strip()
    mask_x = df["ninth_fuel"] == "x"
    df.loc[mask_x, "ninth_fuel"] = df.loc[mask_x, "fuels"].astype(str).str.strip()

    has_sub1 = df["sub1sectors"].astype(str).str.strip() != "x"
    parent_df = df[has_sub1 & (df["sub2sectors"].astype(str).str.strip() == "x")].copy()
    child_df  = df[has_sub1 & (df["sub2sectors"].astype(str).str.strip() != "x")].copy()

    if parent_df.empty or child_df.empty:
        return pd.DataFrame(columns=NINTH_SECTOR_VALIDATION_COLS)

    # Build ESTO flow lookup: 9th_sector -> set of esto_flow labels
    pairs = pd.read_excel(workbook_path, sheet_name="ninth_pairs_to_esto_pairs", dtype=object)
    sector_to_flows: dict[str, set[str]] = {}
    sector_fuel_to_products: dict[tuple[str, str], set[str]] = {}
    for _, row in pairs.iterrows():
        sector  = _str(row.get("9th_sector", ""))
        fuel    = _str(row.get("9th_fuel", ""))
        flow    = _str(row.get("esto_flow", ""))
        product = _str(row.get("esto_product", ""))
        if sector and flow:
            sector_to_flows.setdefault(sector, set()).add(flow)
        if sector and fuel and product:
            sector_fuel_to_products.setdefault((sector, fuel), set()).add(product)

    # Build partition label lookup: (common_flow_label, component_esto_product)
    # -> common_product_label, so Stage A output matches Stage B's partition labels.
    # Use only scopes that include Ninth data: leap_vs_esto uses ESTO-only product
    # codes (no Ninth-driven partitions) and would overwrite partition labels with
    # individual codes, breaking the Stage A → Stage B key match.
    common_rows = pd.read_csv(common_rows_path, dtype=object)
    ninth_scopes = {"leap_vs_esto_vs_ninth", "leap_vs_ninth"}
    scope_rows = common_rows[common_rows["comparison_scope"].astype(str).isin(ninth_scopes)]
    partition_lookup: dict[tuple[str, str], str] = {}
    for _, row in scope_rows.iterrows():
        flow_label   = _str(row.get("common_flow_label", ""))
        comp_product = _str(row.get("component_esto_product", ""))
        prod_label   = _str(row.get("common_product_label", ""))
        if flow_label and comp_product and prod_label:
            partition_lookup[(flow_label, comp_product)] = prod_label

    group_cols = ["economy", "scenarios", "sub1sectors", "ninth_fuel"]
    child_groups = {key: g for key, g in child_df.groupby(group_cols, dropna=False)}

    mismatches: list[dict] = []
    for group_key, parent_group in parent_df.groupby(group_cols, dropna=False):
        children = child_groups.get(group_key)
        if children is None or children.empty:
            continue

        economy     = _str(group_key[0])
        scenario    = _str(group_key[1])
        parent_sub1 = _str(group_key[2])
        ninth_fuel  = _str(group_key[3])

        esto_flows = sector_to_flows.get(parent_sub1, set())
        if len(esto_flows) != 1:
            continue  # Unmapped or ambiguous parent sector
        esto_parent_flow = next(iter(esto_flows))

        # Resolve component ESTO products for this fuel, then map to partition labels
        raw_products = sector_fuel_to_products.get((parent_sub1, ninth_fuel), set())
        partition_labels: set[str] = set()
        for product in raw_products:
            label = partition_lookup.get((esto_parent_flow, product), "")
            if label:
                partition_labels.add(label)
        if not partition_labels:
            continue  # No common-ESTO row covers this (sector, fuel) combination

        child_sector_codes = sorted({_str(v) for v in children["sub2sectors"].unique()})

        for yr in year_cols:
            pv = pd.to_numeric(parent_group[yr], errors="coerce").sum()
            cv = pd.to_numeric(children[yr], errors="coerce").sum()
            if pd.isna(pv) or pd.isna(cv):
                continue
            difference = float(pv - cv)
            err = abs(difference)
            if err <= tolerance * max(abs(pv), 1):
                continue

            # One row per partition label (usually one, occasionally more)
            for partition_label in sorted(partition_labels):
                mismatches.append({
                    "source_issue_id": _source_issue_id(
                        "NINTH", "sector", economy, scenario, yr, parent_sub1, ninth_fuel
                    ),
                    "source_system": "NINTH",
                    "economy": economy,
                    "scenario": scenario,
                    "year": yr,
                    "ninth_sector": parent_sub1,
                    "ninth_fuel": ninth_fuel,
                    "child_ninth_sectors": _join_sorted(child_sector_codes),
                    "esto_parent_flow": esto_parent_flow,
                    "esto_parent_product": partition_label,
                    "source_issue_class": "sum_mismatch",
                    "child_coverage_status": "complete",
                    "inheritance_eligible": True,
                    "child_count": len(child_sector_codes),
                    "parent_value": float(pv),
                    "children_sum": float(cv),
                    "difference": difference,
                    "abs_error": err,
                })

    if not mismatches:
        return pd.DataFrame(columns=NINTH_SECTOR_VALIDATION_COLS)
    return (
        pd.DataFrame(mismatches)
        .sort_values(["economy", "year", "ninth_fuel"])
        .reset_index(drop=True)
    )


def validate_ninth_fuel_recursive_sums(
    data_csv_path: Path = NINTH_DATA_PATH,
    workbook_path: Path = OUTLOOK_MAPPINGS_PATH,
    common_rows_path: Path = COMMON_ESTO_ROWS_PATH,
    tolerance: float = 0.01,
    leap_var_base_year: int = LEAP_VAR_BASE_YEAR,
    scenario_filter: str = "reference",
    data_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Validate projected Ninth fuel parents (subfuels='x') against subfuel children.

    Checks whether each fuel aggregate (subfuels='x') matches the sum of its
    subfuel children for each (economy, scenario, ninth_sector, year) across all
    sector hierarchy levels. Produces findings keyed to Stage B's common ESTO
    partition labels so that _build_source_inconsistency_lookup can mark matching
    Stage B product-axis mismatches as confirmed_inherited.
    """
    df = data_df.copy() if data_df is not None else pd.read_csv(data_csv_path, dtype=object)
    year_cols = [
        c for c in df.columns
        if str(c).isdigit() and int(c) > int(leap_var_base_year)
    ]
    if not year_cols:
        return pd.DataFrame(columns=NINTH_FUEL_VALIDATION_COLS)
    df[year_cols] = df[year_cols].apply(pd.to_numeric, errors="coerce")
    if scenario_filter:
        df = df[df["scenarios"].astype(str).str.casefold() == scenario_filter.casefold()].copy()

    # ninth_sector: most specific non-'x' sector — mirrors prepare_ninth_long_format
    sub2 = df["sub2sectors"].astype(str).str.strip()
    sub1 = df["sub1sectors"].astype(str).str.strip()
    sectors = df["sectors"].astype(str).str.strip()
    df["ninth_sector"] = sectors
    df.loc[sub1 != "x", "ninth_sector"] = sub1[sub1 != "x"]
    df.loc[sub2 != "x", "ninth_sector"] = sub2[sub2 != "x"]

    has_fuel = df["fuels"].astype(str).str.strip() != "x"
    parent_df = df[has_fuel & (df["subfuels"].astype(str).str.strip() == "x")].copy()
    child_df  = df[has_fuel & (df["subfuels"].astype(str).str.strip() != "x")].copy()

    if parent_df.empty or child_df.empty:
        return pd.DataFrame(columns=NINTH_FUEL_VALIDATION_COLS)

    # Build ESTO mapping lookup: (ninth_sector, ninth_fuel) -> set of (esto_flow, esto_product)
    # For parent fuel rows ninth_fuel == fuels (subfuels is 'x'), matching the production join.
    pairs = pd.read_excel(workbook_path, sheet_name="ninth_pairs_to_esto_pairs", dtype=object)
    source_targets = _mapping_targets(
        pairs,
        "9th_sector",
        "9th_fuel",
        "esto_flow",
        "esto_product",
    )

    # Build partition label lookup: (common_flow_label, component_esto_product)
    # -> common_product_label so Stage A output matches Stage B's product-axis partition labels.
    # Use only scopes that include Ninth data.
    common_rows = pd.read_csv(common_rows_path, dtype=object)
    ninth_scopes = {"leap_vs_esto_vs_ninth", "leap_vs_ninth"}
    scope_rows = common_rows[common_rows["comparison_scope"].astype(str).isin(ninth_scopes)]
    partition_lookup: dict[tuple[str, str], str] = {}
    for _, row in scope_rows.iterrows():
        flow_label   = _str(row.get("common_flow_label", ""))
        comp_product = _str(row.get("component_esto_product", ""))
        prod_label   = _str(row.get("common_product_label", ""))
        if flow_label and comp_product and prod_label:
            partition_lookup[(flow_label, comp_product)] = prod_label

    group_cols = ["economy", "scenarios", "ninth_sector", "fuels"]
    child_groups = {key: g for key, g in child_df.groupby(group_cols, dropna=False)}

    mismatches: list[dict] = []
    for group_key, parent_group in parent_df.groupby(group_cols, dropna=False):
        children = child_groups.get(group_key)
        if children is None or children.empty:
            continue

        economy      = _str(group_key[0])
        scenario     = _str(group_key[1])
        ninth_sector = _str(group_key[2])
        fuels_val    = _str(group_key[3])

        parent_targets = source_targets.get((ninth_sector, fuels_val), set())
        if len(parent_targets) != 1:
            continue  # Unmapped or ambiguous parent fuel
        esto_parent_flow, raw_esto_product = next(iter(parent_targets))

        partition_label = partition_lookup.get((esto_parent_flow, raw_esto_product), "")
        if not partition_label:
            continue  # No common-ESTO row covers this (sector, fuel) combination

        child_fuel_codes = sorted({_str(v) for v in children["subfuels"].unique()})

        for yr in year_cols:
            pv = pd.to_numeric(parent_group[yr], errors="coerce").sum()
            cv = pd.to_numeric(children[yr], errors="coerce").sum()
            if pd.isna(pv) or pd.isna(cv):
                continue
            difference = float(pv - cv)
            err = abs(difference)
            if err <= tolerance * max(abs(pv), 1):
                continue

            mismatches.append({
                "source_issue_id": _source_issue_id(
                    "NINTH", "fuel", economy, scenario, yr, ninth_sector, fuels_val
                ),
                "source_system": "NINTH",
                "economy": economy,
                "scenario": scenario,
                "year": yr,
                "ninth_sector": ninth_sector,
                "ninth_fuel": fuels_val,
                "child_ninth_fuels": _join_sorted(child_fuel_codes),
                "esto_parent_product": partition_label,
                "esto_parent_flow": esto_parent_flow,
                "source_issue_class": "sum_mismatch",
                "child_coverage_status": "complete",
                "inheritance_eligible": True,
                "child_count": len(child_fuel_codes),
                "parent_value": float(pv),
                "children_sum": float(cv),
                "difference": difference,
                "abs_error": err,
            })

    if not mismatches:
        return pd.DataFrame(columns=NINTH_FUEL_VALIDATION_COLS)
    return (
        pd.DataFrame(mismatches)
        .sort_values(["economy", "year", "ninth_fuel"])
        .reset_index(drop=True)
    )


def validate_leap_recursive_sums(
    leap_data_paths: list[Path] | None = None,
    workbook_path: Path = OUTLOOK_MAPPINGS_PATH,
    esto_data_path: Path = ESTO_DATA_PATH,
    tolerance: float = 0.01,
    leap_var_base_year: int = LEAP_VAR_BASE_YEAR,
) -> pd.DataFrame:
    """
    Validate projected LEAP parent sectors against mapped direct ESTO children.

    Years at or before ``leap_var_base_year`` are excluded. Full LEAP paths are
    used when present in the source file. Legacy leaf-only inputs remain
    reviewable, but they are eligible for confirmed inheritance only when every
    participating leaf/product maps to one unique full path and target pair.
    """
    if leap_data_paths is None:
        if LEAP_DATA_PATH.exists():
            leap_data_paths = [LEAP_DATA_PATH]
        elif LEGACY_LEAP_DATA_PATH.exists():
            leap_data_paths = [LEGACY_LEAP_DATA_PATH]
        else:
            leap_data_paths = []

    available = [p for p in leap_data_paths if p.exists()]
    if not available:
        return pd.DataFrame(columns=LEAP_VALIDATION_COLS)

    leap_df = pd.concat(
        [pd.read_csv(p, dtype=object) for p in available], ignore_index=True
    )
    leap_df["value"] = pd.to_numeric(leap_df["value"], errors="coerce").fillna(0.0)
    leap_df["year"] = pd.to_numeric(leap_df["year"], errors="coerce")
    leap_df = leap_df[leap_df["year"] > int(leap_var_base_year)].copy()
    leap_df["year"] = leap_df["year"].astype(int).astype(str)
    if leap_df.empty:
        return pd.DataFrame(columns=LEAP_VALIDATION_COLS)

    esto_map = pd.read_excel(workbook_path, sheet_name="leap_combined_esto", dtype=object)
    esto_map = esto_map[
        esto_map["leap_sector_name_full_path"].notna()
        & esto_map["esto_flow"].notna()
        & esto_map["raw_leap_fuel_name"].notna()
        & esto_map["esto_product"].notna()
    ].copy()
    esto_map["parent_path"] = esto_map["leap_sector_name_full_path"].map(_str)
    esto_map["parent_leaf"] = esto_map["parent_path"].str.split("/").str[-1]
    esto_map["source_product"] = esto_map["raw_leap_fuel_name"].map(_str)
    esto_map["target_flow"] = esto_map["esto_flow"].map(_str)
    esto_map["target_product"] = esto_map["esto_product"].map(_str)

    esto_flows = set(
        pd.read_csv(esto_data_path, usecols=["flows"], dtype=object)["flows"]
        .dropna()
        .map(_str)
    )
    source_pair_targets = (
        esto_map.groupby(["parent_path", "source_product"], dropna=False)
        .apply(
            lambda group: {
                (_str(row["target_flow"]), _str(row["target_product"]))
                for _, row in group.iterrows()
            },
            include_groups=False,
        )
        .to_dict()
    )
    leaf_product_paths = (
        esto_map.groupby(["parent_leaf", "source_product"])["parent_path"]
        .agg(lambda values: set(map(_str, values)))
        .to_dict()
    )

    source_path_column = (
        "leap_sector_path" if "leap_sector_path" in leap_df.columns
        else "leap_flow_path" if "leap_flow_path" in leap_df.columns
        else "leap_flow" if leap_df["leap_flow"].astype(str).str.contains("/", regex=False).any()
        else ""
    )

    mismatches: list[dict] = []
    parent_rows = esto_map.drop_duplicates(
        ["parent_path", "source_product", "target_flow", "target_product"]
    )
    for _, parent_mapping in parent_rows.iterrows():
        parent_path = _str(parent_mapping["parent_path"])
        parent_leaf = _str(parent_mapping["parent_leaf"])
        leap_product = _str(parent_mapping["source_product"])
        esto_parent_flow = _str(parent_mapping["target_flow"])
        esto_parent_product = _str(parent_mapping["target_product"])
        expected_child_flows = _direct_child_labels(esto_parent_flow, esto_flows)
        if not expected_child_flows:
            continue

        child_mappings = esto_map[
            esto_map["target_flow"].isin(expected_child_flows)
            & (esto_map["target_product"] == esto_parent_product)
        ].drop_duplicates(["parent_path", "source_product", "target_flow", "target_product"])
        if child_mappings.empty:
            continue

        mapped_child_flows = set(child_mappings["target_flow"].map(_str))
        missing_child_flows = expected_child_flows.difference(mapped_child_flows)
        parent_targets = source_pair_targets.get((parent_path, leap_product), set())
        parent_mapping_status = (
            "exact" if parent_targets == {(esto_parent_flow, esto_parent_product)}
            else "ambiguous_parent_mapping"
        )

        parent_mask = leap_df["leap_product"].map(_str) == leap_product
        if source_path_column:
            parent_mask &= leap_df[source_path_column].map(_str) == parent_path
            source_context_status = "full_path"
        else:
            parent_mask &= leap_df["leap_flow"].map(_str) == parent_leaf
            parent_paths = leaf_product_paths.get((parent_leaf, leap_product), set())
            source_context_status = (
                "leaf_only_unambiguous" if parent_paths == {parent_path}
                else "leaf_only_ambiguous"
            )
        parent_data = leap_df[parent_mask]
        if parent_data.empty:
            continue

        child_masks: list[pd.Series] = []
        child_paths: set[str] = set()
        child_mapping_ambiguous = False
        for _, child_mapping in child_mappings.iterrows():
            child_path = _str(child_mapping["parent_path"])
            child_leaf = _str(child_mapping["parent_leaf"])
            child_product = _str(child_mapping["source_product"])
            child_paths.add(child_path)
            mask = leap_df["leap_product"].map(_str) == child_product
            if source_path_column:
                mask &= leap_df[source_path_column].map(_str) == child_path
            else:
                mask &= leap_df["leap_flow"].map(_str) == child_leaf
                if leaf_product_paths.get((child_leaf, child_product), set()) != {child_path}:
                    child_mapping_ambiguous = True
            child_masks.append(mask)
        child_mask = pd.Series(False, index=leap_df.index)
        for mask in child_masks:
            child_mask |= mask
        children_data = leap_df[child_mask]

        group_cols = ["economy", "scenario", "year"]
        parent_sum = parent_data.groupby(group_cols, dropna=False)["value"].sum()
        children_sum = children_data.groupby(group_cols, dropna=False)["value"].sum()
        for idx in parent_sum.index:
            pv = float(parent_sum.loc[idx])
            cv = float(children_sum.get(idx, 0.0))
            difference = pv - cv
            err = abs(difference)
            if err <= tolerance * max(abs(pv), 1):
                continue
            economy, scenario, year = map(_str, idx)
            if source_context_status == "leaf_only_ambiguous" or child_mapping_ambiguous:
                mapping_status = "ambiguous_leaf_context"
                source_issue_class = "mapping_ambiguous"
                child_coverage_status = "ambiguous_source_paths"
            elif parent_mapping_status != "exact":
                mapping_status = parent_mapping_status
                source_issue_class = "mapping_ambiguous"
                child_coverage_status = "ambiguous_parent_mapping"
            elif missing_child_flows:
                mapping_status = "exact"
                source_issue_class = "children_incomplete"
                child_coverage_status = "unmapped_expected_children"
            elif abs(pv) > tolerance and abs(cv) <= tolerance:
                mapping_status = "exact"
                source_issue_class = "children_incomplete"
                child_coverage_status = "no_nonzero_children"
            else:
                mapping_status = "exact"
                source_issue_class = "sum_mismatch"
                child_coverage_status = "complete"

            inheritance_eligible = (
                source_issue_class == "sum_mismatch"
                and mapping_status == "exact"
                and child_coverage_status == "complete"
                and source_context_status in {"full_path", "leaf_only_unambiguous"}
            )
            mismatches.append({
                "source_issue_id": _source_issue_id(
                    "LEAP", economy, scenario, year, parent_path, leap_product,
                    esto_parent_flow, esto_parent_product
                ),
                "source_system": "LEAP",
                "economy": economy,
                "scenario": scenario,
                "year": year,
                "parent_leap_sector_path": parent_path,
                "parent_leap_sector": parent_leaf,
                "leap_product": leap_product,
                "child_leap_sector_paths": _join_sorted(child_paths),
                "esto_parent_flow": esto_parent_flow,
                "esto_parent_product": esto_parent_product,
                "child_esto_flows": _join_sorted(mapped_child_flows),
                "source_context_status": source_context_status,
                "source_issue_class": source_issue_class,
                "mapping_status": mapping_status,
                "child_coverage_status": child_coverage_status,
                "inheritance_eligible": inheritance_eligible,
                "child_count": len(expected_child_flows),
                "mapped_child_count": len(mapped_child_flows),
                "parent_value": pv,
                "children_sum": cv,
                "difference": difference,
                "abs_error": err,
            })

    if not mismatches:
        return pd.DataFrame(columns=LEAP_VALIDATION_COLS)
    return (
        pd.DataFrame(mismatches)
        .sort_values(["economy", "year", "parent_leap_sector"])
        .reset_index(drop=True)
    )


def _build_source_inconsistency_lookup(
    ninth_validation: pd.DataFrame,
    leap_validation: pd.DataFrame,
    ninth_sector_validation: pd.DataFrame | None = None,
    ninth_fuel_validation: pd.DataFrame | None = None,
) -> dict[tuple[str, str, str, str, str, str, str], dict[str, str]]:
    """
    Build an exact-context lookup for conservative Stage B source attribution.

    Keys retain source, economy, scenario, year, validation axis, parent code,
    and opposite-axis value. Multiple source findings for one exact key are
    retained through joined issue IDs. Only eligible findings produce
    ``confirmed_inherited``.

    ``ninth_sector_validation`` (from validate_ninth_sector_recursive_sums)
    supplies flow-axis findings where sub-sector Ninth values don't sum to their
    parent sector, so Stage B flow-axis mismatches for those parents can be
    marked confirmed_inherited rather than not_attributed.

    ``ninth_fuel_validation`` (from validate_ninth_fuel_recursive_sums)
    supplies product-axis findings where subfuels don't sum to their parent fuel,
    so Stage B product-axis mismatches for those parents can be marked
    confirmed_inherited rather than not_attributed.

    Each lookup entry additionally carries ``sector_hierarchy_status`` and
    ``fuel_hierarchy_status`` indicating which hierarchy type caused the match,
    so Stage B can record attribution at that level of detail.
    """
    lookup: dict[tuple[str, str, str, str, str, str, str], dict[str, str]] = {}
    # (frame, axis, parent_col, other_axis_col, source_type)
    # source_type is "sector" or "fuel" for the named hierarchy validators; None otherwise.
    frames: list[tuple[pd.DataFrame, str, str, str, str | None]] = [
        (ninth_validation, "product", "esto_parent_product", "esto_parent_flow", None),
        (leap_validation, "flow", "esto_parent_flow", "esto_parent_product", None),
    ]
    if ninth_sector_validation is not None and not ninth_sector_validation.empty:
        frames.append(
            (ninth_sector_validation, "flow", "esto_parent_flow", "esto_parent_product", "sector")
        )
    if ninth_fuel_validation is not None and not ninth_fuel_validation.empty:
        frames.append(
            (ninth_fuel_validation, "product", "esto_parent_product", "esto_parent_flow", "fuel")
        )
    for frame, axis, parent_column, other_axis_column, source_type in frames:
        for _, row in frame.iterrows():
            parent_code = _str(row.get(parent_column, ""))
            other_axis_value = _str(row.get(other_axis_column, ""))
            if not parent_code or not other_axis_value:
                continue
            key = (
                _str(row.get("source_system", "")).casefold(),
                _str(row.get("economy", "")),
                _str(row.get("scenario", "")).casefold(),
                _str(row.get("year", "")),
                axis,
                parent_code,
                other_axis_value,
            )
            eligible = _truthy(row.get("inheritance_eligible", False))
            issue_class = _str(row.get("source_issue_class", "source_issue"))
            status = "confirmed_inherited" if eligible else issue_class
            issue_id = _str(row.get("source_issue_id", ""))
            existing = lookup.get(key)
            if existing is None:
                lookup[key] = {
                    "status": status,
                    "source_issue_ids": issue_id,
                    "sector_hierarchy_status": "confirmed_inherited" if (source_type == "sector" and eligible) else "",
                    "fuel_hierarchy_status": "confirmed_inherited" if (source_type == "fuel" and eligible) else "",
                }
                continue
            statuses = {existing["status"], status}
            existing["status"] = (
                "confirmed_inherited" if statuses == {"confirmed_inherited"}
                else "multiple_source_issue_classes"
            )
            existing["source_issue_ids"] = _join_sorted(
                [existing["source_issue_ids"], issue_id]
            )
            if source_type == "sector" and eligible:
                existing["sector_hierarchy_status"] = "confirmed_inherited"
            if source_type == "fuel" and eligible:
                existing["fuel_hierarchy_status"] = "confirmed_inherited"
    return lookup


def _build_source_inconsistency_set(
    ninth_validation: pd.DataFrame,
    leap_validation: pd.DataFrame,
    ninth_sector_validation: pd.DataFrame | None = None,
    ninth_fuel_validation: pd.DataFrame | None = None,
) -> dict[tuple[str, str, str, str, str, str, str], dict[str, str]]:
    """Backward-compatible name for the exact-context source lookup."""
    return _build_source_inconsistency_lookup(
        ninth_validation, leap_validation, ninth_sector_validation, ninth_fuel_validation
    )


def _empty_esto_validation() -> pd.DataFrame:
    return pd.DataFrame(columns=ESTO_VALIDATION_COLS)


def _empty_common_esto_validation() -> pd.DataFrame:
    return pd.DataFrame(columns=COMMON_ESTO_VALIDATION_COLS)


def _validate_esto_axis_recursive_sums(
    tree_df: pd.DataFrame,
    data_csv_path: Path = ESTO_DATA_PATH,
    axis: str = "product",
    tolerance: float = 0.01,
) -> pd.DataFrame:
    """Validate one ESTO axis against direct child sums."""
    if axis not in {"product", "flow"}:
        raise ValueError(f"Unsupported ESTO validation axis: {axis}")

    data = pd.read_csv(data_csv_path, dtype=object)
    year_cols = [c for c in data.columns if c.isdigit()]
    data[year_cols] = data[year_cols].apply(pd.to_numeric, errors="coerce")

    axis_col = "products" if axis == "product" else "flows"
    other_axis_col = "flows" if axis == "product" else "products"
    children_map = _tree_children_map(tree_df, "esto", axis)
    mismatches = []

    for parent_code, children in children_map.items():
        parent_rows = data[data[axis_col] == parent_code]
        children_rows = data[data[axis_col].isin(children)]
        if parent_rows.empty or children_rows.empty:
            continue

        parent_sum = parent_rows.groupby(["economy", other_axis_col])[year_cols].sum()
        children_sum = children_rows.groupby(["economy", other_axis_col])[year_cols].sum()
        common_idx = parent_sum.index.intersection(children_sum.index)
        if common_idx.empty:
            continue

        p_vals = parent_sum.loc[common_idx]
        c_vals = children_sum.loc[common_idx]
        diff = (p_vals - c_vals).abs()
        threshold = tolerance * p_vals.abs().clip(lower=1)
        flagged = (diff > threshold).any(axis=1)

        for idx in common_idx[flagged.values]:
            economy, other_axis_value = idx
            for yr in year_cols:
                pv = float(p_vals.at[idx, yr]) if not pd.isna(p_vals.at[idx, yr]) else None
                cv = float(c_vals.at[idx, yr]) if not pd.isna(c_vals.at[idx, yr]) else None
                if pv is None or cv is None:
                    continue
                err = abs(pv - cv)
                if err > tolerance * max(abs(pv), 1):
                    mismatches.append({
                        "validation_axis": axis,
                        "economy": economy,
                        "other_axis_value": other_axis_value,
                        "parent_code": parent_code,
                        "child_count": len(children),
                        "year": yr,
                        "parent_value": pv,
                        "children_sum": cv,
                        "abs_error": err,
                    })

    result = pd.DataFrame(mismatches)
    if result.empty:
        return _empty_esto_validation()
    return result.sort_values(
        ["validation_axis", "economy", "other_axis_value", "parent_code", "year"]
    ).reset_index(drop=True)


def validate_esto_recursive_sums(
    tree_df: pd.DataFrame,
    data_csv_path: Path = ESTO_DATA_PATH,
    tolerance: float = 0.01,
) -> pd.DataFrame:
    """Validate ESTO product and flow subtotals against direct child sums."""
    result = pd.concat(
        [
            _validate_esto_axis_recursive_sums(tree_df, data_csv_path, "product", tolerance),
            _validate_esto_axis_recursive_sums(tree_df, data_csv_path, "flow", tolerance),
        ],
        ignore_index=True,
    )
    if result.empty:
        return _empty_esto_validation()
    return result.sort_values(
        ["validation_axis", "economy", "other_axis_value", "parent_code", "year"]
    ).reset_index(drop=True)


def _resolve_to_comparison_data(
    codes: list[str],
    data_codes: set[str],
    children_map: dict[str, list[str]],
) -> list[str]:
    """
    Expand any codes absent from comparison data to their tree descendants.

    Codes present in data are kept as-is. Codes absent from data but having
    tree children (e.g. an intermediate subtotal filtered from the comparison
    set) are replaced by their recursively resolved descendants. Codes absent
    with no tree children are dropped silently.

    This lets validation of a parent correctly sum through intermediate
    subtotals that were not included in the comparison dataset.
    """
    resolved: list[str] = []
    for code in codes:
        if code in data_codes:
            resolved.append(code)
        elif code in children_map:
            resolved.extend(
                _resolve_to_comparison_data(children_map[code], data_codes, children_map)
            )
    return resolved


def _validate_common_esto_axis_recursive_sums(
    tree_df: pd.DataFrame,
    comparison_data_path: Path,
    axis: str,
    tolerance: float = 0.01,
    source_inconsistencies: dict[
        tuple[str, str, str, str, str, str, str], dict[str, str]
    ] | None = None,
    leap_var_base_year: int = LEAP_VAR_BASE_YEAR,
    record_all_checks: bool = False,
) -> pd.DataFrame:
    """
    Validate one Common ESTO axis where dot-notation parent/child rows exist.

    Graph-generated aggregate labels are treated as leaves because they do not
    have a natural recursive hierarchy.

    ``source_inconsistencies`` uses the exact Stage B key: source system,
    economy, scenario, year, axis, parent code, and opposite-axis value. Only a
    Stage A record marked ``confirmed_inherited`` sets the convenience boolean.
    """
    if axis not in {"product", "flow"}:
        raise ValueError(f"Unsupported Common ESTO validation axis: {axis}")
    if not comparison_data_path.exists():
        return _empty_common_esto_validation()

    data = pd.read_csv(comparison_data_path, dtype=object)
    required = {
        "comparison_scope",
        "source_system",
        "economy",
        "scenario",
        "year",
        "common_flow_label",
        "common_product_label",
        "value",
    }
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(
            f"Common ESTO comparison data is missing required columns: {sorted(missing)}"
        )

    data["value"] = pd.to_numeric(data["value"], errors="coerce").fillna(0.0)
    data["year"] = pd.to_numeric(data["year"], errors="coerce")
    data = data[data["year"] > int(leap_var_base_year)].copy()
    data["year"] = data["year"].astype(int).astype(str)
    if data.empty:
        return _empty_common_esto_validation()
    axis_col = "common_product_label" if axis == "product" else "common_flow_label"
    other_axis_col = "common_flow_label" if axis == "product" else "common_product_label"
    group_cols = ["comparison_scope", "source_system", "economy", "scenario", other_axis_col, "year"]
    children_map = _common_esto_validation_children_map(tree_df, axis)
    source_inconsistencies = source_inconsistencies or {}
    all_data_codes: set[str] = set(data[axis_col].dropna().unique())
    checks = []

    for parent_code, children in children_map.items():
        parent_rows = data[data[axis_col] == parent_code]
        if parent_rows.empty:
            continue
        # Resolve: any direct child absent from the comparison data but present
        # in the tree as an intermediate subtotal is expanded to its own
        # descendants (recursively), so the children sum correctly accounts for
        # flows that were filtered from the comparison set (e.g. 09.06).
        resolved = _resolve_to_comparison_data(children, all_data_codes, children_map)
        if not resolved:
            continue
        children_rows = data[data[axis_col].isin(resolved)]
        if children_rows.empty:
            continue

        parent_sum = parent_rows.groupby(group_cols, dropna=False)["value"].sum()
        children_sum = children_rows.groupby(group_cols, dropna=False)["value"].sum()
        child_presence = children_rows.groupby(group_cols, dropna=False)[axis_col].agg(
            lambda values: set(values.astype(str))
        )
        common_idx = parent_sum.index

        for idx in common_idx:
            pv = float(parent_sum.loc[idx])
            present_children = child_presence.get(idx, set())
            missing_children = sorted(set(resolved).difference(present_children))
            cv = float(children_sum.get(idx, 0.0))
            err = abs(pv - cv)
            failed = bool(missing_children) or err > tolerance * max(abs(pv), 1)
            if not record_all_checks and not failed:
                continue
            scope, source_system, economy, scenario, other_axis_value, year = idx
            lookup_key = (
                _str(source_system).casefold(),
                _str(economy),
                _str(scenario).casefold(),
                _str(year),
                axis,
                _str(parent_code),
                _str(other_axis_value),
            )
            source_record = source_inconsistencies.get(lookup_key, {})
            source_status = source_record.get("status", "not_attributed")
            diff = pv - cv
            prop_err = diff / pv if abs(pv) > tolerance else None
            checks.append({
                "validation_axis": axis,
                "comparison_scope": scope,
                "source_system": source_system,
                "economy": economy,
                "scenario": scenario,
                "other_axis_value": other_axis_value,
                "parent_code": parent_code,
                "child_count": len(children),
                "frontier_row_count": len(present_children),
                "missing_expected_children": _join_sorted(missing_children),
                "year": year,
                "parent_value": pv,
                "children_sum": cv,
                "difference": diff,
                "abs_error": err,
                "proportional_error": prop_err,
                "status": "failed" if failed else "passed",
                "reason": (
                    "missing_expected_children" if missing_children
                    else "difference_exceeds_tolerance" if failed
                    else "within_tolerance"
                ),
                "source_inconsistency_status": source_status,
                "sector_hierarchy_status": source_record.get("sector_hierarchy_status", ""),
                "fuel_hierarchy_status": source_record.get("fuel_hierarchy_status", ""),
                "source_issue_ids": source_record.get("source_issue_ids", ""),
                "inherited_source_inconsistency": source_status == "confirmed_inherited",
            })

    result = pd.DataFrame(checks)
    if result.empty:
        return _empty_common_esto_validation()
    return result.sort_values([
        "validation_axis",
        "comparison_scope",
        "source_system",
        "economy",
        "scenario",
        "other_axis_value",
        "parent_code",
        "year",
    ]).reset_index(drop=True)


def validate_common_esto_recursive_sums(
    tree_df: pd.DataFrame,
    comparison_data_path: Path = COMMON_ESTO_COMPARISON_PATH,
    tolerance: float = 0.01,
    source_inconsistencies: dict[
        tuple[str, str, str, str, str, str, str], dict[str, str]
    ] | None = None,
    leap_var_base_year: int = LEAP_VAR_BASE_YEAR,
) -> pd.DataFrame:
    """
    Validate Common ESTO product and flow subtotals when comparison data exists.

    ``source_inconsistencies`` is passed through to the per-axis validator.
    """
    result = pd.concat(
        [
            _validate_common_esto_axis_recursive_sums(
                tree_df,
                comparison_data_path,
                "product",
                tolerance,
                source_inconsistencies,
                leap_var_base_year,
            ),
            _validate_common_esto_axis_recursive_sums(
                tree_df,
                comparison_data_path,
                "flow",
                tolerance,
                source_inconsistencies,
                leap_var_base_year,
            ),
        ],
        ignore_index=True,
    )
    if result.empty:
        return _empty_common_esto_validation()
    return result.sort_values([
        "validation_axis",
        "comparison_scope",
        "source_system",
        "economy",
        "scenario",
        "other_axis_value",
        "parent_code",
        "year",
    ]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def run_tree_structure_workflow(
    esto_data_path: Path = ESTO_DATA_PATH,
    ninth_data_path: Path = NINTH_DATA_PATH,
    leap_data_paths: list[Path] | None = None,
    outlook_mappings_path: Path = OUTLOOK_MAPPINGS_PATH,
    common_rows_path: Path = COMMON_ESTO_ROWS_PATH,
    common_comparison_path: Path = COMMON_ESTO_COMPARISON_PATH,
    output_dir: Path = TREE_OUTPUT_DIR,
    validate_esto: bool = True,
    leap_var_base_year: int = LEAP_VAR_BASE_YEAR,
) -> Path:
    """
    Build all four tree CSVs and run recursive sum validation.

    Stage A runs first, validating each source dataset independently:
    * ESTO (if ``validate_esto=True``) — expected to pass; re-check after data
      refreshes.
    * Ninth Edition fuel hierarchy — flags parent/child gaps in the raw Ninth CSV.
    * LEAP sector hierarchy — flags LEAP aggregate vs sub-sector gaps using
      available LEAP balance CSVs (defaults to the USA long-format file).

    Source validation is projection-only: years at or before
    ``leap_var_base_year`` are excluded. Stage A findings are translated into
    exact-context lookup records for Stage B.

    Returns the output directory path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Building ESTO tree …")
    esto_tree = build_esto_tree(esto_data_path)
    _write_tree(esto_tree, output_dir / "esto_tree.csv", "esto")

    print("Building 9th Edition tree …")
    ninth_tree = build_ninth_tree(ninth_data_path)
    _write_tree(ninth_tree, output_dir / "ninth_tree.csv", "ninth")

    print("Building LEAP tree …")
    leap_tree = build_leap_tree(outlook_mappings_path)
    _write_tree(leap_tree, output_dir / "leap_tree.csv", "leap")

    if common_rows_path.exists():
        print("Building Common ESTO tree …")
        common_tree = build_common_esto_tree(common_rows_path)
        _write_tree(common_tree, output_dir / "common_esto_tree.csv", "common_esto")
    else:
        print(f"  Skipping Common ESTO tree (not found: {common_rows_path.name})")
        common_tree = pd.DataFrame(columns=TREE_COLS)

    all_trees = combine_dataset_trees([esto_tree, ninth_tree, leap_tree, common_tree])

    # Persist the combined tree so downstream consumers (the lineage anchor
    # validator) have a single explicit source of dataset/axis/code/parent_code
    # edges instead of re-concatenating the per-dataset files themselves.
    all_trees_path = output_dir / "all_dataset_trees.csv"
    all_trees.to_csv(all_trees_path, index=False)
    print(f"  Wrote combined dataset trees -> {all_trees_path.name}")

    # ------------------------------------------------------------------
    # Stage A: source-data consistency pre-checks
    # ------------------------------------------------------------------
    if validate_esto:
        print("Stage A — ESTO recursive sum validation …")
        esto_validation = validate_esto_recursive_sums(all_trees, esto_data_path)
        esto_val_path = output_dir / "esto_validation.csv"
        esto_validation.to_csv(esto_val_path, index=False)
        if esto_validation.empty:
            print("  All ESTO recursive sum checks passed.")
        else:
            print(f"  {len(esto_validation):,} mismatch rows -> {esto_val_path.relative_to(REPO_ROOT)}")
    else:
        esto_validation = _empty_esto_validation()
        print("Stage A — ESTO recursive sum validation skipped (validate_esto=False).")

    print("Stage A — Ninth Edition fuel hierarchy validation …")
    ninth_validation = validate_ninth_recursive_sums(
        ninth_data_path,
        outlook_mappings_path,
        leap_var_base_year=leap_var_base_year,
    )
    ninth_val_path = output_dir / "ninth_validation.csv"
    ninth_validation.to_csv(ninth_val_path, index=False)
    if ninth_validation.empty:
        print("  All Ninth fuel hierarchy checks passed.")
    else:
        print(f"  {len(ninth_validation):,} mismatch rows -> {ninth_val_path.relative_to(REPO_ROOT)}")

    print("Stage A — LEAP sector hierarchy validation …")
    leap_validation = validate_leap_recursive_sums(
        leap_data_paths,
        outlook_mappings_path,
        esto_data_path=esto_data_path,
        leap_var_base_year=leap_var_base_year,
    )
    leap_val_path = output_dir / "leap_validation.csv"
    leap_validation.to_csv(leap_val_path, index=False)
    if leap_validation.empty:
        print("  All LEAP sector hierarchy checks passed (or no LEAP balance data available).")
    else:
        print(f"  {len(leap_validation):,} mismatch rows -> {leap_val_path.relative_to(REPO_ROOT)}")

    source_inconsistencies = _build_source_inconsistency_lookup(
        ninth_validation,
        leap_validation,
    )

    # ------------------------------------------------------------------
    # Stage B: Common ESTO recursive sum validation
    # ------------------------------------------------------------------
    common_val_path = output_dir / "common_esto_validation.csv"
    if common_tree.empty:
        common_validation = _empty_common_esto_validation()
        common_validation.to_csv(common_val_path, index=False)
        print("Stage B — Skipping Common ESTO validation (common tree not available).")
    elif not common_comparison_path.exists():
        common_validation = _empty_common_esto_validation()
        common_validation.to_csv(common_val_path, index=False)
        print(f"Stage B — Skipping Common ESTO validation (not found: {common_comparison_path.name})")
    else:
        print("Stage B — Common ESTO recursive sum validation …")
        common_validation = validate_common_esto_recursive_sums(
            all_trees,
            common_comparison_path,
            source_inconsistencies=source_inconsistencies,
            leap_var_base_year=leap_var_base_year,
        )
        common_validation.to_csv(common_val_path, index=False)
        if common_validation.empty:
            print("  All Common ESTO recursive sum checks passed.")
        else:
            inherited = int(common_validation["inherited_source_inconsistency"].sum()) if "inherited_source_inconsistency" in common_validation.columns else 0
            genuine = len(common_validation) - inherited
            print(
                f"  {len(common_validation):,} mismatch rows "
                f"({inherited:,} inherited from source, {genuine:,} potential mapping issues) "
                f"-> {common_val_path.relative_to(REPO_ROOT)}"
            )

    non_esto_edges = common_esto_non_esto_parent_child_edges(all_trees)
    non_esto_edges_path = output_dir / "common_esto_non_esto_parent_child_edges.csv"
    non_esto_edges.to_csv(non_esto_edges_path, index=False)
    print(
        f"  Common ESTO non-ESTO parent/child edges: {len(non_esto_edges):,} "
        f"-> {non_esto_edges_path.relative_to(REPO_ROOT)}"
    )

    print(f"\nTree structure outputs -> {output_dir.relative_to(REPO_ROOT)}")
    return output_dir


def _write_tree(df: pd.DataFrame, path: Path, label: str) -> None:
    df.to_csv(path, index=False)
    n_nodes = len(df)
    n_leaves = int(df["is_leaf"].sum()) if "is_leaf" in df.columns else 0
    print(f"  {label}: {n_nodes} nodes, {n_leaves} leaves -> {path.relative_to(REPO_ROOT)}")


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_tree_structure_workflow()
