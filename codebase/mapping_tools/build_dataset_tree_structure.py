"""
build_dataset_tree_structure.py

Build hierarchical tree structures for ESTO, 9th Edition, LEAP, and Common ESTO
datasets. Outputs tree CSVs to results/tree_structure/ and runs recursive sum
validation against the ESTO balance data.

Outputs (results/tree_structure/):
    esto_tree.csv           — ESTO flow and product node hierarchy
    ninth_tree.csv          — 9th Edition sector and fuel node hierarchy
    leap_tree.csv           — LEAP sector and fuel node hierarchy
    common_esto_tree.csv    — Common ESTO flow and product node hierarchy
    esto_validation.csv     — Recursive sum validation (parent vs sum-of-children)

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
OUTLOOK_MAPPINGS_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
COMMON_ESTO_ROWS_PATH = REPO_ROOT / "results" / "common_esto" / "common_esto_rows.csv"
TREE_OUTPUT_DIR       = REPO_ROOT / "results" / "tree_structure"

TREE_COLS = ["dataset", "axis", "code", "label", "level", "parent_code", "is_leaf", "is_subtotal"]

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


def _ninth_sector_tree(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build 9th Edition sector hierarchy.

    Level is determined by how many non-'x' sector columns a row uses.
    Node code: slash-joined non-'x' values, e.g. '09_electricity/09_01_main_activity'.
    """
    seen: dict[str, dict] = {}

    for _, row in df[_NINTH_SECTOR_COLS].drop_duplicates().iterrows():
        vals = [_str(row[c]) for c in _NINTH_SECTOR_COLS]
        # collect non-x segments up to first 'x'
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
                "is_subtotal": False,
            }

    if not seen:
        return pd.DataFrame(columns=TREE_COLS)

    result = pd.DataFrame(seen.values())
    leaf_mask = ~result["code"].isin(result["parent_code"].unique())
    result["is_leaf"] = leaf_mask
    return result[TREE_COLS].reset_index(drop=True)


def _ninth_fuel_tree(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build 9th Edition fuel hierarchy.

    Level 1 = fuels; Level 2 = subfuels (where subfuels != 'x').
    Node code: slash-joined, e.g. '01_coal/01_01_coking_coal'.
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
                "is_subtotal": False,
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
    # Mark fuel-level nodes as subtotals where they have subfuel children
    parents_with_children = set(result.loc[result["level"] == 2, "parent_code"])
    result.loc[result["code"].isin(parents_with_children), "is_subtotal"] = True
    return result[TREE_COLS].reset_index(drop=True)


def build_ninth_tree(data_csv_path: Path = NINTH_DATA_PATH) -> pd.DataFrame:
    """Build 9th Edition sector and fuel hierarchy from the balance data CSV."""
    df = pd.read_csv(data_csv_path, dtype=object)
    sector_tree = _ninth_sector_tree(df)
    fuel_tree   = _ninth_fuel_tree(df)
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
# Recursive sum validation (ESTO)
# ---------------------------------------------------------------------------

def validate_esto_recursive_sums(
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


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def run_tree_structure_workflow(
    esto_data_path: Path = ESTO_DATA_PATH,
    ninth_data_path: Path = NINTH_DATA_PATH,
    outlook_mappings_path: Path = OUTLOOK_MAPPINGS_PATH,
    common_rows_path: Path = COMMON_ESTO_ROWS_PATH,
    output_dir: Path = TREE_OUTPUT_DIR,
) -> Path:
    """
    Build all four tree CSVs and run recursive sum validation.

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

    # Recursive validation uses the ESTO tree
    print("Running ESTO recursive sum validation …")
    all_trees = pd.concat(
        [t for t in [esto_tree, ninth_tree, leap_tree, common_tree] if not t.empty],
        ignore_index=True,
    )
    validation = validate_esto_recursive_sums(all_trees, esto_data_path)
    val_path = output_dir / "esto_validation.csv"
    validation.to_csv(val_path, index=False)
    if validation.empty:
        print("  All ESTO recursive sum checks passed.")
    else:
        print(f"  {len(validation):,} mismatch rows -> {val_path.relative_to(REPO_ROOT)}")

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
