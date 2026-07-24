"""Reusable source-to-LEAP fuel coverage audit.

This module answers a structural question before a mapping is trusted:

    Which non-zero 9th/ESTO source fuels occur in each economy and scope, and
    do their mapped LEAP fuel leaves exist in the current LEAP structure?

The source inventory is deliberately built before mappings are applied. An
unmapped non-zero source row remains visible as a diagnostic rather than being
silently filtered out. The scope definitions are configuration-owned so the
same checker can be reused for other LEAP sectors later.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
INITIALISATION_ROOT = REPO_ROOT.parent / "leap_initialisation"

DEFAULT_SCOPE_CONFIG_PATH = REPO_ROOT / "config" / "source_coverage_scopes.json"
DEFAULT_MAPPING_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
DEFAULT_NINTH_PATH = REPO_ROOT / "data" / "merged_file_energy_ALL_20251106.csv"
DEFAULT_ESTO_PATH = REPO_ROOT / "data" / "00APEC_2025_low_with_subtotals.csv"
DEFAULT_LEAP_TEMPLATE_DIR = INITIALISATION_ROOT / "data" / "leap_export_templates"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "results" / "source_coverage"

STATUS_OK = "OK"
STATUS_UNMAPPED = "UNMAPPED_SOURCE_FUEL"
STATUS_REMOVED_ONLY = "REMOVED_MAPPING_ONLY"
STATUS_AMBIGUOUS = "AMBIGUOUS_MAPPING"
STATUS_MISSING_LEAP = "MISSING_LEAP_FUEL"
STATUS_TEMPLATE_MISSING = "LEAP_TEMPLATE_MISSING"

DETAIL_COLUMNS = [
    "economy",
    "scope",
    "component",
    "source",
    "source_flow",
    "source_fuel",
    "nonzero_rows",
    "nonzero_years",
    "total_abs",
    "max_abs",
    "has_negative_value",
    "mapped_leap_fuel",
    "mapping_status",
    "leap_branch_path",
    "leap_present",
    "coverage_status",
]


def _text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _truthy(value: object) -> bool:
    return _text(value).casefold() in {"true", "1", "yes", "y"}


def _normalise_economy(value: object) -> str:
    text = _text(value)
    if re.fullmatch(r"\d{2}[A-Za-z]{2,3}", text):
        return f"{text[:2]}_{text[2:].upper()}"
    return text


def _numeric_columns(columns: Iterable[object]) -> list[object]:
    return [column for column in columns if str(column).isdigit()]


def _nonzero_stats(frame: pd.DataFrame, value_columns: list[object], key_columns: list[str]) -> pd.DataFrame:
    """Aggregate rows with any non-zero value, preserving negative evidence."""
    output_columns = key_columns + ["nonzero_rows", "nonzero_years", "total_abs", "max_abs", "has_negative_value"]
    if frame.empty or not value_columns:
        return pd.DataFrame(columns=output_columns)

    values = frame[value_columns].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    nonzero = values.abs().gt(1e-12).any(axis=1)
    working = frame.loc[nonzero, key_columns].copy()
    if working.empty:
        return pd.DataFrame(columns=output_columns)
    working["_row_total_abs"] = values.loc[nonzero].abs().sum(axis=1).to_numpy()
    working["_row_max_abs"] = values.loc[nonzero].abs().max(axis=1).to_numpy()
    working["_has_negative"] = values.loc[nonzero].lt(-1e-12).any(axis=1).to_numpy()

    rows: list[dict[str, Any]] = []
    for keys, group in working.groupby(key_columns, dropna=False, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        record = dict(zip(key_columns, keys))
        source_indices = group.index
        record.update(
            {
                "nonzero_rows": int(len(group)),
                "nonzero_years": int(values.loc[source_indices].abs().gt(1e-12).any(axis=0).sum()),
                "total_abs": float(group["_row_total_abs"].sum()),
                "max_abs": float(group["_row_max_abs"].max()),
                "has_negative_value": bool(group["_has_negative"].any()),
            }
        )
        rows.append(record)
    return pd.DataFrame(rows, columns=output_columns)


def _match_values(frame: pd.DataFrame, column: str, values: list[str]) -> pd.Series:
    if not values:
        return pd.Series(True, index=frame.index)
    return frame[column].astype(str).str.strip().isin(values)


def _match_ninth_component(frame: pd.DataFrame, component: dict[str, Any]) -> pd.Series:
    clauses = component.get("ninth_any_of", [])
    if not clauses:
        clauses = [component.get("ninth", {})]
    masks: list[pd.Series] = []
    for clause in clauses:
        mask = pd.Series(True, index=frame.index)
        for column, values in clause.items():
            if column not in frame.columns:
                mask &= False
            else:
                mask &= _match_values(frame, column, [str(value) for value in values])
        masks.append(mask)
    result = pd.Series(False, index=frame.index)
    for mask in masks:
        result |= mask
    return result


def _match_esto_component(frame: pd.DataFrame, component: dict[str, Any]) -> pd.Series:
    prefixes = [str(value) for value in component.get("esto_flow_prefixes", [])]
    if not prefixes:
        return pd.Series(False, index=frame.index)
    flows = frame["flows"].astype(str).str.strip()
    return flows.map(lambda flow: any(flow.startswith(prefix) for prefix in prefixes))


def _resolve_ninth_fuel(frame: pd.DataFrame) -> pd.Series:
    parent = frame["fuels"].astype(str).str.strip()
    child = frame["subfuels"].astype(str).str.strip()
    # ``x`` is valid for a parent-level fuel such as electricity. It is not a
    # reason to discard the row; it means the parent fuel code is the source key.
    use_child = child.ne("") & child.ne("x") & child.ne("nan")
    return child.where(use_child, parent)


def load_scope_config(path: Path = DEFAULT_SCOPE_CONFIG_PATH, scope_name: str = "all_demand_aggregated") -> dict[str, Any]:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    scopes = config.get("scopes", {})
    if scope_name not in scopes:
        raise KeyError(f"Unknown source coverage scope {scope_name!r}; available: {sorted(scopes)}")
    scope = dict(scopes[scope_name])
    scope["name"] = scope_name
    return scope


def build_ninth_source_inventory(
    path: Path,
    scope: dict[str, Any],
    *,
    scenario: str = "reference",
    chunksize: int = 200_000,
) -> pd.DataFrame:
    """Build a non-zero 9th inventory, dropping only result subtotals."""
    header = pd.read_csv(path, nrows=0)
    value_columns = _numeric_columns(header.columns)
    stable = [
        "economy", "scenarios", "sectors", "sub1sectors", "sub2sectors",
        "sub3sectors", "sub4sectors", "fuels", "subfuels", "subtotal_results",
    ]
    usecols = [column for column in stable + value_columns if column in header.columns]
    component_stats: list[pd.DataFrame] = []
    for chunk in pd.read_csv(path, usecols=usecols, chunksize=chunksize, low_memory=False):
        chunk = chunk[chunk["scenarios"].astype(str).str.strip().str.casefold().eq(scenario.casefold())].copy()
        chunk = chunk[~chunk["subtotal_results"].map(_truthy)].copy()
        if chunk.empty:
            continue
        chunk["source_fuel"] = _resolve_ninth_fuel(chunk)
        for component in scope["components"]:
            selected = chunk[_match_ninth_component(chunk, component)].copy()
            if selected.empty:
                continue
            selected["component"] = component["name"]
            selected["economy"] = selected["economy"].map(_normalise_economy)
            selected["source"] = "9th"
            selected["source_flow"] = selected["sectors"].astype(str).str.strip()
            component_stats.append(
                _nonzero_stats(
                    selected,
                    value_columns,
                    ["economy", "component", "source", "source_flow", "source_fuel"],
                )
            )
    if not component_stats:
        return pd.DataFrame(columns=["scope", "component", "source", "source_flow", "source_fuel", *DETAIL_COLUMNS[0:1]])
    stats = pd.concat(component_stats, ignore_index=True)
    stats = (
        stats.groupby(["economy", "component", "source", "source_flow", "source_fuel"], dropna=False)
        .agg(
            nonzero_rows=("nonzero_rows", "sum"),
            nonzero_years=("nonzero_years", "max"),
            total_abs=("total_abs", "sum"),
            max_abs=("max_abs", "max"),
            has_negative_value=("has_negative_value", "any"),
        )
        .reset_index()
    )
    stats.insert(1, "scope", scope["name"])
    return stats


def build_esto_source_inventory(path: Path, scope: dict[str, Any]) -> pd.DataFrame:
    """Build a non-zero ESTO inventory, dropping only ``is_subtotal`` rows."""
    frame = pd.read_csv(path, low_memory=False)
    frame = frame[~frame["is_subtotal"].map(_truthy)].copy()
    value_columns = _numeric_columns(frame.columns)
    component_frames: list[pd.DataFrame] = []
    for component in scope["components"]:
        selected = frame[_match_esto_component(frame, component)].copy()
        if selected.empty:
            continue
        selected["component"] = component["name"]
        selected["economy"] = selected["economy"].map(_normalise_economy)
        selected["source"] = "ESTO"
        selected["source_flow"] = selected["flows"].astype(str).str.strip()
        selected["source_fuel"] = selected["products"].astype(str).str.strip()
        component_frames.append(selected)
    if not component_frames:
        return pd.DataFrame()
    selected = pd.concat(component_frames, ignore_index=True)
    stats = _nonzero_stats(
        selected,
        value_columns,
        ["economy", "component", "source", "source_flow", "source_fuel"],
    )
    stats.insert(1, "scope", scope["name"])
    return stats


def _load_mapping_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    frame = pd.read_excel(path, sheet_name=sheet_name, dtype=object).fillna("")
    frame.columns = [str(column).strip() for column in frame.columns]
    for column in frame.columns:
        frame[column] = frame[column].map(_text)
    if "duplicate_to_remove" not in frame.columns:
        frame["duplicate_to_remove"] = False
    return frame


def load_leap_presence(template_dir: Path, leap_root: str) -> dict[str, set[str] | None]:
    """Read relative branch paths below the configured LEAP root per economy."""
    presence: dict[str, set[str] | None] = {}
    root = leap_root.replace("/", "\\").rstrip("\\")
    for path in sorted(Path(template_dir).glob("leap_export_template *.xlsx")):
        match = re.search(r"leap_export_template (.+)\.xlsx$", path.name)
        if not match:
            continue
        economy = match.group(1)
        # Generic templates use a filename suffix while source data and
        # mapping outputs use the compact economy code (e.g. 03_CDA).
        if economy.endswith("_COMP_GEN"):
            economy = economy[: -len("_COMP_GEN")]
        try:
            frame = pd.read_excel(path, sheet_name="Export", header=2, usecols=["Branch Path"])
        except (FileNotFoundError, ValueError, KeyError):
            presence[economy] = None
            continue
        paths = frame["Branch Path"].dropna().astype(str).str.replace("/", "\\", regex=False)
        leaves: set[str] = set()
        prefix = root + "\\"
        for full_path in paths:
            if full_path.startswith(prefix):
                relative = full_path[len(prefix):]
                leaves.add(relative)
        presence[economy] = leaves
    return presence


def _mapping_result(
    source_row: pd.Series,
    component: dict[str, Any],
    ninth_mapping: pd.DataFrame,
    esto_mapping: pd.DataFrame,
) -> tuple[str, str]:
    if source_row["source"] == "9th":
        candidates_all = ninth_mapping[
            ninth_mapping["ninth_sector"].isin([str(value) for value in component.get("mapping_ninth_sectors", [])])
            & ninth_mapping["ninth_fuel"].eq(source_row["source_fuel"])
        ]
        candidates = candidates_all[~candidates_all["duplicate_to_remove"].map(_truthy)]
    else:
        candidates_all = esto_mapping[
            esto_mapping["esto_flow"].isin([str(value) for value in component.get("mapping_esto_flows", [])])
            & esto_mapping["esto_product"].eq(source_row["source_fuel"])
        ]
        candidates = candidates_all[~candidates_all["duplicate_to_remove"].map(_truthy)]
    names = sorted(set(candidates.get("raw_leap_fuel_name", pd.Series(dtype=str))))
    names = [name for name in names if name]
    if len(names) > 1:
        return "; ".join(names), STATUS_AMBIGUOUS
    if len(names) == 1:
        return names[0], "MAPPED"
    if not candidates_all.empty:
        return "", STATUS_REMOVED_ONLY
    return "", STATUS_UNMAPPED


def audit_source_coverage(
    source_inventory: pd.DataFrame,
    scope: dict[str, Any],
    *,
    mapping_path: Path = DEFAULT_MAPPING_PATH,
    leap_presence: dict[str, set[str] | None] | None = None,
) -> pd.DataFrame:
    """Apply mappings after source extraction and return one auditable detail table."""
    ninth_mapping = _load_mapping_sheet(mapping_path, "leap_combined_ninth")
    esto_mapping = _load_mapping_sheet(mapping_path, "leap_combined_esto")
    component_by_name = {component["name"]: component for component in scope["components"]}
    rows: list[dict[str, Any]] = []
    for _, source_row in source_inventory.iterrows():
        component = component_by_name[source_row["component"]]
        mapped_fuel, mapping_status = _mapping_result(source_row, component, ninth_mapping, esto_mapping)
        economy = source_row["economy"]
        branch_path = ""
        leap_present: object = ""
        coverage_status = mapping_status
        if mapped_fuel and mapping_status == "MAPPED":
            branch_path = f"{scope['leap_root']}\\{component['name']}\\{mapped_fuel}"
            leaves = None if leap_presence is None else leap_presence.get(economy)
            if leaves is None:
                coverage_status = STATUS_TEMPLATE_MISSING
                leap_present = False
            else:
                relative_path = f"{component['name']}\\{mapped_fuel}"
                leap_present = relative_path in leaves
                coverage_status = STATUS_OK if leap_present else STATUS_MISSING_LEAP
        rows.append(
            {
                **{column: source_row.get(column, "") for column in [
                    "economy", "scope", "component", "source", "source_flow", "source_fuel",
                    "nonzero_rows", "nonzero_years", "total_abs", "max_abs", "has_negative_value",
                ]},
                "mapped_leap_fuel": mapped_fuel,
                "mapping_status": mapping_status,
                "leap_branch_path": branch_path,
                "leap_present": leap_present,
                "coverage_status": coverage_status,
            }
        )
    return pd.DataFrame(rows, columns=DETAIL_COLUMNS)


def run_coverage_audit(
    *,
    scope_name: str = "all_demand_aggregated",
    scope_config_path: Path = DEFAULT_SCOPE_CONFIG_PATH,
    mapping_path: Path = DEFAULT_MAPPING_PATH,
    ninth_path: Path = DEFAULT_NINTH_PATH,
    esto_path: Path = DEFAULT_ESTO_PATH,
    leap_template_dir: Path = DEFAULT_LEAP_TEMPLATE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    scenario: str = "reference",
) -> dict[str, Path]:
    """Run the configured audit and write detail, gap, and summary CSVs."""
    scope = load_scope_config(scope_config_path, scope_name)
    ninth = build_ninth_source_inventory(ninth_path, scope, scenario=scenario)
    esto = build_esto_source_inventory(esto_path, scope)
    source_inventory = pd.concat([ninth, esto], ignore_index=True)
    presence = load_leap_presence(leap_template_dir, scope["leap_root"])
    detail = audit_source_coverage(source_inventory, scope, mapping_path=mapping_path, leap_presence=presence)
    gaps = detail[detail["coverage_status"].ne(STATUS_OK)].copy()
    summary = (
        detail.groupby(["economy", "component", "source", "coverage_status"], dropna=False)
        .size().reset_index(name="rows")
        .sort_values(["economy", "component", "source", "coverage_status"])
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "detail": output_dir / f"{scope_name}_coverage_detail.csv",
        "gaps": output_dir / f"{scope_name}_coverage_gaps.csv",
        "summary": output_dir / f"{scope_name}_coverage_summary.csv",
        "source_inventory": output_dir / f"{scope_name}_source_inventory.csv",
    }
    detail.to_csv(paths["detail"], index=False)
    gaps.to_csv(paths["gaps"], index=False)
    summary.to_csv(paths["summary"], index=False)
    source_inventory.to_csv(paths["source_inventory"], index=False)
    return paths


if __name__ == "__main__":
    for label, path in run_coverage_audit().items():
        print(f"{label}: {path}")
