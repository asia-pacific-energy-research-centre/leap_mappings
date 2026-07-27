#%%
"""Build a non-destructive ESTO Extended prototype.

The prototype copies a base ESTO CSV, inventories LEAP export-template branch
paths, restores established ESTO structural children, and creates review-only
extension candidates by comparing LEAP leaves with the ESTO flow tree.
Generated rows carry provenance columns so this can become a reviewed
production workflow later.
"""

#%%
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.mapping_tools.build_missing_mapped_esto_rows import build_lng_split_esto_rows
from codebase.mapping_tools.non_expanding_rollups import (
    ROLLUP_SHEET_CONFIGS,
    build_esto_non_expanding_subtotal_rows,
    get_rollup_mode,
    load_non_expanding_rollup_rules,
    non_expanding_rollup_id,
)

#%%
LEAP_INITIALISATION_ROOT = Path(r"C:\Users\Work\github\leap_initialisation")
BASE_ESTO_PATH = REPO_ROOT / "data" / "00APEC_2025_low_with_subtotals.csv"
MAPPING_WORKBOOK_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
TEMPLATE_DIR = LEAP_INITIALISATION_ROOT / "data" / "leap_export_templates"
NEW_LEAP_ROWS_WORKBOOK_PATH = REPO_ROOT / "data" / "temp" / "new leap rows.xlsx"
# Backwards-compatible name retained for callers that already import this
# constant. The workbook now contains explicit ``demand`` and ``power`` tabs.
DEMAND_BRANCH_WORKBOOK_PATH = NEW_LEAP_ROWS_WORKBOOK_PATH
NEW_LEAP_ROW_SHEETS = ("demand", "power")
OUTPUT_DIR = REPO_ROOT / "results" / "esto_extended_test"

ESTO_REQUIRED_COLUMNS = ["economy", "flows", "products"]
ESTO_CODE_PATTERN = re.compile(r"\d+(?:\.\d+)*")
PROVENANCE_COLUMNS = [
    "esto_extended_row_origin",
    "esto_extended_rule_id",
    "esto_extended_parent_flow",
    "esto_extended_parent_product",
    "esto_extended_derived_from",
    "esto_extended_source_leap_paths",
    "esto_extended_rollup_mode",
    "esto_extended_rollup_id",
]

ESTABLISHED_FLOW_RULE = {
    "rule_id": "established_lng_split",
    "source_flow": "09.06.02 Liquefaction/regasification plants",
    "generated_flows": [
        "09.06.02.01 Liquefaction",
        "09.06.02.02 Regasification",
    ],
    "value_method": "signed_lng_direction_split",
}

# This rule exists only for the unit test proving that the old 16.01.99
# mechanism is still understood. It is deliberately not part of the real
# ESTO Extended build.
DEMO_RESIDUAL_RULE = {
    "rule_id": "demo_parent_minus_children",
    "rule_type": "parent_minus_children",
    "parent_flow": "16.01 Commercial and public services",
    "excluded_child_flows": ["16.01.01 Datacentres"],
    "generated_flow": "16.01.99 Commercial and public services unallocated",
}

ESTO_MATCH_STOPWORDS = {
    "and", "of", "the", "plants", "plant", "other", "non", "specified",
    "unspecified", "services", "sector", "transformation", "fuel", "fuels",
}

ESTABLISHED_FLOW_LABELS = {
    "09.06.02.01 Liquefaction",
    "09.06.02.02 Regasification",
}
ESTABLISHED_LEAF_TARGETS = {
    "lng regasification": "09.06.02.02 Regasification",
    "ng liquefaction": "09.06.02.01 Liquefaction",
}
FUEL_ROLE_LABELS = {"Feedstock Fuels", "Output Fuels", "Auxiliary Fuels"}
SPECIAL_ALREADY_MAPPED_TEMPLATE_CHILDREN = {
    ("transmission and distribution", "electricity"): "10.02 Transmission and distribution losses / 17 Electricity"
}


#%%
def _normalise_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).split())


def _normalise_path(value: object) -> str:
    return "/".join(part.strip() for part in _normalise_text(value).replace("\\", "/").split("/") if part.strip())


def _normalise_economy(value: object) -> str:
    return _normalise_text(value).replace("_", "")


def _esto_code(label: object) -> str:
    text = _normalise_text(label)
    if not text:
        return ""
    code = text.split(" ", 1)[0]
    return code if ESTO_CODE_PATTERN.fullmatch(code) else ""


def _year_columns(df: pd.DataFrame) -> list[str]:
    return [column for column in df.columns if str(column).isdigit()]


def _require_columns(df: pd.DataFrame, required: list[str], label: str) -> None:
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def _with_provenance_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    defaults = {
        "esto_extended_row_origin": "base_esto",
        "esto_extended_rule_id": "",
        "esto_extended_parent_flow": "",
        "esto_extended_parent_product": "",
        "esto_extended_derived_from": "",
        "esto_extended_source_leap_paths": "",
        "esto_extended_rollup_mode": "",
        "esto_extended_rollup_id": "",
    }
    for column in PROVENANCE_COLUMNS:
        if column not in out.columns:
            out[column] = defaults[column]
    return out


#%%
def read_leap_template_branch_inventory(template_dir: Path) -> pd.DataFrame:
    """Extract branch paths and ancestor paths from current LEAP templates."""
    rows: list[dict[str, Any]] = []
    template_paths = sorted(template_dir.glob("leap_export_template *.xlsx"))
    if not template_paths:
        raise FileNotFoundError(f"No LEAP export templates found in {template_dir}")

    for path in template_paths:
        try:
            frame = pd.read_excel(path, sheet_name=0, header=2, usecols=["Branch Path"], dtype=object)
        except ValueError:
            # Some archived/legacy templates may not expose the standard header.
            continue
        branch_paths = frame["Branch Path"].map(_normalise_path)
        for branch_path in sorted(set(branch_paths[branch_paths.ne("")])):
            segments = branch_path.split("/")
            for depth in range(1, len(segments) + 1):
                node = "/".join(segments[:depth])
                rows.append(
                    {
                        "template_file": path.name,
                        "branch_path": node,
                        "parent_path": "/".join(segments[: depth - 1]),
                        "depth": depth,
                        "leaf_label": segments[-1] if depth == len(segments) else segments[depth - 1],
                        "is_observed_leaf": depth == len(segments),
                    }
                )

    inventory = pd.DataFrame(rows).drop_duplicates()
    if inventory.empty:
        raise ValueError("No usable Branch Path values were found in the LEAP templates")
    presence = (
        inventory.groupby("branch_path", as_index=False)
        .agg(
            parent_path=("parent_path", "first"),
            depth=("depth", "first"),
            leaf_label=("leaf_label", "first"),
            template_count=("template_file", "nunique"),
            template_files=("template_file", lambda values: "|".join(sorted(set(values)))),
            observed_as_leaf=("is_observed_leaf", "any"),
        )
    )
    return presence.sort_values(["depth", "branch_path"]).reset_index(drop=True)


def read_demand_branch_inventory(
    workbook_path: Path,
    sheet_names: tuple[str, ...] = NEW_LEAP_ROW_SHEETS,
) -> pd.DataFrame:
    """Read named demand/power branch tabs as a LEAP path source.

    The source workbook is deliberately kept separate from the mapping
    workbook. Each row retains its source tab so candidate additions and
    later removals can be audited without mutating the master mappings.
    """
    if not workbook_path.exists():
        raise FileNotFoundError(f"Demand branch workbook not found: {workbook_path}")
    available_sheets = set(pd.ExcelFile(workbook_path).sheet_names)
    missing_sheets = [sheet_name for sheet_name in sheet_names if sheet_name not in available_sheets]
    if missing_sheets:
        raise ValueError(
            f"Branch workbook {workbook_path} is missing required sheet(s): "
            f"{', '.join(missing_sheets)}. Available sheets: {sorted(available_sheets)}"
        )

    rows: list[dict[str, Any]] = []
    for sheet_name in sheet_names:
        frame = pd.read_excel(
            workbook_path,
            sheet_name=sheet_name,
            header=0,
            usecols=["Branch Path"],
            dtype=object,
        )
        paths = frame["Branch Path"].map(_normalise_path)
        for branch_path in sorted(set(paths[paths.ne("")])):
            if branch_path.casefold() == "branch path":
                continue
            segments = branch_path.split("/")
            for depth in range(1, len(segments) + 1):
                node = "/".join(segments[:depth])
                rows.append(
                    {
                        "template_file": workbook_path.name,
                        "source_sheet": sheet_name,
                        "branch_path": node,
                        "parent_path": "/".join(segments[: depth - 1]),
                        "depth": depth,
                        "leaf_label": segments[-1] if depth == len(segments) else segments[depth - 1],
                        "is_observed_leaf": depth == len(segments),
                    }
                )
    if not rows:
        raise ValueError(f"No branch paths found in {workbook_path}")
    inventory = pd.DataFrame(rows).drop_duplicates()
    return (
        inventory.groupby("branch_path", as_index=False)
        .agg(
            parent_path=("parent_path", "first"),
            depth=("depth", "first"),
            leaf_label=("leaf_label", "first"),
            template_count=("template_file", "nunique"),
            template_files=("template_file", lambda values: "|".join(sorted(set(values)))),
            source_sheets=("source_sheet", lambda values: "|".join(sorted(set(values)))),
            observed_as_leaf=("is_observed_leaf", "any"),
        )
        .sort_values(["depth", "branch_path"])
        .reset_index(drop=True)
    )


def combine_branch_inventories(*inventories: pd.DataFrame) -> pd.DataFrame:
    """Combine template and externally supplied branch trees without losing provenance."""
    frames = [frame for frame in inventories if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    return (
        combined.groupby("branch_path", as_index=False)
        .agg(
            parent_path=("parent_path", "first"),
            depth=("depth", "first"),
            leaf_label=("leaf_label", "first"),
            template_count=("template_count", "sum"),
            template_files=("template_files", lambda values: "|".join(sorted(set("|".join(values).split("|"))))),
            observed_as_leaf=("observed_as_leaf", "any"),
        )
        .sort_values(["depth", "branch_path"])
        .reset_index(drop=True)
    )


def load_active_leap_esto_paths(mapping_workbook_path: Path) -> set[str]:
    mappings = pd.read_excel(mapping_workbook_path, sheet_name="leap_combined_esto", dtype=object)
    _require_columns(mappings, ["leap_sector_name_full_path"], "leap_combined_esto")
    removed = mappings.get("remove_row", pd.Series(False, index=mappings.index)).map(
        lambda value: _normalise_text(value).lower() in {"true", "1", "yes", "y"}
    )
    return set(
        mappings.loc[~removed, "leap_sector_name_full_path"]
        .map(_normalise_path)
        .loc[lambda values: values.ne("")]
    )


def build_unmapped_branch_candidates(
    inventory: pd.DataFrame,
    mapped_paths: set[str],
) -> pd.DataFrame:
    """Mark observed template leaves with exact active mapping coverage."""
    candidates = inventory[inventory["observed_as_leaf"]].copy()
    candidates["exact_active_esto_mapping"] = candidates["branch_path"].isin(mapped_paths)
    candidates["candidate_status"] = candidates["exact_active_esto_mapping"].map(
        {True: "mapped_exactly", False: "unmapped_review"}
    )
    candidates["proposed_extension_label"] = candidates["leaf_label"].map(_normalise_extension_label)
    return candidates.sort_values(["candidate_status", "depth", "branch_path"]).reset_index(drop=True)


def _normalise_extension_label(value: object) -> str:
    """Return a stable human-facing descriptor for a branch leaf."""
    label = _normalise_text(value)
    label = re.sub(r"\s+", " ", label).strip(" -_")
    return label


def _label_tokens(value: object) -> set[str]:
    label = _normalise_text(value).casefold()
    label = re.sub(r"[^a-z0-9]+", " ", label)
    return {
        token
        for token in label.split()
        if len(token) > 2 and token not in ESTO_MATCH_STOPWORDS
    }


def load_esto_flow_tree(base_esto_path: Path) -> pd.DataFrame:
    """Return unique ESTO flows with their numeric hierarchy codes."""
    esto = pd.read_csv(base_esto_path, usecols=["flows"], dtype=object)
    base_flows = set(esto["flows"].dropna().map(_normalise_text))
    all_flows = sorted(base_flows | ESTABLISHED_FLOW_LABELS)
    flows = pd.DataFrame({"esto_flow": all_flows})
    flows["esto_flow_code"] = flows["esto_flow"].map(_esto_code)
    flows["flow_present_in_base"] = flows["esto_flow"].isin(base_flows)
    return flows[flows["esto_flow_code"].ne("")].reset_index(drop=True)


def build_tree_based_extension_candidates(
    unmapped_candidates: pd.DataFrame,
    esto_flow_tree: pd.DataFrame,
) -> pd.DataFrame:
    """Match unmapped LEAP leaves to likely ESTO flow parents.

    This is intentionally review-only. It identifies a possible target parent
    and a proposed child label, but it does not allocate a code or create data.
    """
    flow_records = esto_flow_tree.to_dict("records")
    output: list[dict[str, Any]] = []
    for _, row in unmapped_candidates.iterrows():
        if row.get("exact_active_esto_mapping", False):
            continue
        path_tokens = _label_tokens(row["branch_path"])
        leaf_tokens = _label_tokens(row["leaf_label"])
        scored: list[tuple[int, int, str, str]] = []
        for flow in flow_records:
            flow_tokens = _label_tokens(flow["esto_flow"])
            leaf_overlap = len(leaf_tokens & flow_tokens)
            path_overlap = len(path_tokens & flow_tokens)
            score = (leaf_overlap * 3) + path_overlap
            if score:
                scored.append((score, leaf_overlap, flow["esto_flow"], flow["esto_flow_code"]))
        if not scored:
            continue
        scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
        established_target = ESTABLISHED_LEAF_TARGETS.get(_normalise_text(row["leaf_label"]).casefold())
        if established_target:
            established_code = _esto_code(established_target)
            best_score = max(item[0] for item in scored) + 100
            best_leaf_overlap = len(leaf_tokens & _label_tokens(established_target))
            best_flow = established_target
            best_code = established_code
        else:
            best_score, best_leaf_overlap, best_flow, best_code = scored[0]
        tied = [item for item in scored if item[:2] == (best_score, best_leaf_overlap)]
        if established_target:
            tied = [(best_score, best_leaf_overlap, best_flow, best_code)]
        output.append(
            {
                "leap_branch_path": row["branch_path"],
                "leap_parent_path": row["parent_path"],
                "leap_leaf_label": row["leaf_label"],
                "proposed_child_label": row["proposed_extension_label"],
                "esto_parent_flow": best_flow,
                "esto_parent_code": best_code,
                "match_score": best_score,
                "leaf_token_overlap": best_leaf_overlap,
                "tied_parent_count": len(tied),
                "candidate_status": (
                    "review_existing_established_target"
                    if best_flow in ESTABLISHED_FLOW_LABELS
                    else "review_possible_new_child"
                ),
                "target_flow_present_in_base": bool(
                    next(
                        (
                            flow.get("flow_present_in_base", True)
                            for flow in flow_records
                            if flow["esto_flow"] == best_flow
                        ),
                        False,
                    )
                ),
                "proposed_code": "",
                "value_status": "not_generated_review_only",
            }
        )
    return pd.DataFrame(output)


def summarise_extension_candidate_sets(candidates: pd.DataFrame) -> pd.DataFrame:
    """Show parent groups where multiple LEAP leaves suggest one ESTO parent."""
    if candidates.empty:
        return pd.DataFrame(
            columns=["esto_parent_flow", "esto_parent_code", "candidate_count", "leap_branches", "set_status"]
        )
    grouped = (
        candidates.groupby(["esto_parent_flow", "esto_parent_code"], as_index=False)
        .agg(
            candidate_count=("leap_branch_path", "nunique"),
            leap_branches=("leap_branch_path", lambda values: "|".join(sorted(set(values)))),
        )
    )
    grouped["set_status"] = grouped["candidate_count"].map(
        lambda count: "candidate_extension_set" if count >= 2 else "single_candidate"
    )
    return grouped.sort_values(["set_status", "candidate_count", "esto_parent_flow"], ascending=[True, False, True])


def summarise_leap_parent_candidate_sets(candidates: pd.DataFrame) -> pd.DataFrame:
    """Identify LEAP tree parents with several unmapped child branches."""
    if candidates.empty:
        return pd.DataFrame(
            columns=["leap_parent_path", "candidate_count", "leap_child_branches", "suggested_esto_parents", "set_status"]
        )
    grouped = (
        candidates.groupby("leap_parent_path", as_index=False)
        .agg(
            candidate_count=("leap_branch_path", "nunique"),
            leap_child_branches=("leap_leaf_label", lambda values: "|".join(sorted(set(values)))),
            suggested_esto_parents=("esto_parent_flow", lambda values: "|".join(sorted(set(values)))),
        )
    )
    grouped["set_status"] = grouped["candidate_count"].map(
        lambda count: "candidate_leap_child_set" if count >= 2 else "single_candidate"
    )
    return grouped.sort_values(["set_status", "candidate_count", "leap_parent_path"], ascending=[True, False, True])


#%%
def _numeric_values(row: pd.Series, year_columns: list[str]) -> pd.Series:
    return pd.to_numeric(row[year_columns], errors="coerce").fillna(0.0).astype(float)


def apply_parent_minus_children_rule(
    esto_df: pd.DataFrame,
    rule: dict[str, Any],
    source_leap_paths: str = "",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate missing residual rows while preserving the source schema."""
    _require_columns(esto_df, ESTO_REQUIRED_COLUMNS, "ESTO data")
    year_columns = _year_columns(esto_df)
    if not year_columns:
        raise ValueError("ESTO data has no year columns")
    source_columns = [column for column in esto_df.columns if column not in PROVENANCE_COLUMNS]

    parent_code = _esto_code(rule["parent_flow"])
    excluded_codes = {_esto_code(label) for label in rule["excluded_child_flows"]}
    generated_code = _esto_code(rule["generated_flow"])
    working = esto_df.copy()
    working["_economy_key"] = working["economy"].map(_normalise_economy)
    working["_flow_code"] = working["flows"].map(_esto_code)
    working["_product_code"] = working["products"].map(_esto_code)

    parent = working[working["_flow_code"].eq(parent_code)]
    children = working[working["_flow_code"].isin(excluded_codes)]
    existing = set(
        map(
            tuple,
            working.loc[working["_flow_code"].eq(generated_code), ["_economy_key", "_product_code"]]
            .itertuples(index=False, name=None),
        )
    )
    child_groups = {
        key: group for key, group in children.groupby(["_economy_key", "_product_code"], dropna=False)
    }
    rows: list[dict[str, Any]] = []
    for key, parent_group in parent.groupby(["_economy_key", "_product_code"], dropna=False):
        if key in existing:
            continue
        parent_row = parent_group.iloc[0]
        child_group = child_groups.get(key)
        child_values = (
            child_group[year_columns].apply(pd.to_numeric, errors="coerce").fillna(0.0).sum()
            if child_group is not None
            else pd.Series(0.0, index=year_columns)
        )
        parent_values = _numeric_values(parent_row, year_columns)
        output = {column: parent_row.get(column, pd.NA) for column in source_columns}
        output["flows"] = rule["generated_flow"]
        if "is_subtotal" in output:
            output["is_subtotal"] = False
        for year in year_columns:
            output[year] = float(parent_values[year] - child_values[year])
        output.update(
            {
                "esto_extended_row_origin": "generated",
                "esto_extended_rule_id": rule["rule_id"],
                "esto_extended_parent_flow": rule["parent_flow"],
                "esto_extended_parent_product": parent_row["products"],
                "esto_extended_derived_from": f"{rule['parent_flow']} minus {'|'.join(rule['excluded_child_flows'])}",
                "esto_extended_source_leap_paths": source_leap_paths,
            }
        )
        rows.append(output)
        existing.add(key)

    generated = pd.DataFrame(rows, columns=source_columns + PROVENANCE_COLUMNS)
    return generated, pd.DataFrame(
        [
            {
                "rule_id": rule["rule_id"],
                "generated_flow": rule["generated_flow"],
                "generated_rows": len(generated),
                "source_leap_paths": source_leap_paths,
            }
        ]
    )


def restore_established_lng_rows(esto_df: pd.DataFrame, base_esto_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Restore only missing established LNG child rows using the tested splitter."""
    source_rows, audit = build_lng_split_esto_rows(base_esto_path)
    if source_rows.empty:
        return pd.DataFrame(columns=list(esto_df.columns)), audit

    existing_keys = {
        tuple(row)
        for row in esto_df[["economy", "flows", "products"]]
        .assign(
            economy=lambda frame: frame["economy"].map(_normalise_economy),
            flows=lambda frame: frame["flows"].map(_esto_code),
            products=lambda frame: frame["products"].map(_esto_code),
        )
        .itertuples(index=False, name=None)
    }
    source_rows = source_rows.copy()
    source_rows["_key"] = list(
        zip(
            source_rows["economy"].map(_normalise_economy),
            source_rows["flows"].map(_esto_code),
            source_rows["products"].map(_esto_code),
        )
    )
    missing = source_rows[~source_rows["_key"].isin(existing_keys)].drop(columns=["_key"])
    missing = _with_provenance_columns(missing)
    missing["esto_extended_row_origin"] = "established_structural_completion"
    missing["esto_extended_rule_id"] = ESTABLISHED_FLOW_RULE["rule_id"]
    missing["esto_extended_parent_flow"] = ESTABLISHED_FLOW_RULE["source_flow"]
    missing["esto_extended_derived_from"] = ESTABLISHED_FLOW_RULE["value_method"]
    return missing.reindex(columns=list(esto_df.columns)), audit


def load_rollup_catalogue(mapping_workbook_path: Path) -> pd.DataFrame:
    """Compile all enabled rollup rules with their declared mode and lineage."""
    rows: list[dict[str, Any]] = []
    for sheet_name, config in ROLLUP_SHEET_CONFIGS.items():
        rules = pd.read_excel(mapping_workbook_path, sheet_name=sheet_name, dtype=object).fillna("")
        if "include" in rules.columns:
            rules = rules[rules["include"].map(lambda value: _normalise_text(value).casefold() in {"true", "1", "yes", "y"})]
        for _, rule in rules.iterrows():
            rolled_flow = _normalise_text(rule.get(config["rolled_flow"], ""))
            if not rolled_flow:
                continue
            rows.append(
                {
                    "rule_sheet": sheet_name,
                    "source_system": config["source_system"],
                    "rollup_mode": get_rollup_mode(rule),
                    "input_flow": _normalise_text(rule.get(config["input_flow"], "")),
                    "input_product": _normalise_text(rule.get(config["input_product"], "")),
                    "rolled_flow": rolled_flow,
                    "rolled_product": _normalise_text(rule.get(config["rolled_product"], "")),
                    "parent_flow_label": _normalise_text(rule.get("parent_flow", rule.get("parent_flow_label", ""))),
                    "child_flow_labels": _normalise_text(rule.get("child_flow_labels", "")),
                    "rollup_context": _normalise_text(rule.get("rollup_context", "")),
                    "rollup_group_id": _normalise_text(rule.get("rollup_group_id", "")),
                    "note": _normalise_text(rule.get("Note", "")),
                }
            )
    return pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)


def build_esto_rollup_rows(
    base_esto: pd.DataFrame,
    mapping_workbook_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Materialise only safe ESTO non-expanding/detached rollup values."""
    rules_by_sheet = load_non_expanding_rollup_rules(mapping_workbook_path)
    esto_rules = rules_by_sheet.get("esto_rollup_rules", pd.DataFrame())
    if esto_rules.empty:
        return pd.DataFrame(columns=list(base_esto.columns)), pd.DataFrame()

    long_rows = build_esto_non_expanding_subtotal_rows(
        esto_wide_df=base_esto,
        esto_non_expanding_rules_df=esto_rules,
        year_columns=_year_columns(base_esto),
    )
    if long_rows.empty:
        return pd.DataFrame(columns=list(base_esto.columns)), pd.DataFrame()

    year_columns = _year_columns(base_esto)
    keys = ["economy", "esto_flow", "esto_product"]
    wide = long_rows.pivot_table(index=keys, columns="year", values="value", aggfunc="sum", fill_value=0.0).reset_index()
    wide.columns = [str(column) for column in wide.columns]
    rollup_ids = (
        long_rows.groupby(["esto_flow", "esto_product"], dropna=False)["non_expanding_rollup_id"]
        .first()
        .to_dict()
    )
    rows: list[dict[str, Any]] = []
    for _, row in wide.iterrows():
        output = {column: pd.NA for column in base_esto.columns if column not in PROVENANCE_COLUMNS}
        output["economy"] = row["economy"]
        output["flows"] = row["esto_flow"]
        output["products"] = row["esto_product"]
        if "is_subtotal" in output:
            output["is_subtotal"] = True
        for year in year_columns:
            output[year] = float(row.get(year, 0.0))
        output.update(
            {
                "esto_extended_row_origin": "rollup_derived",
                "esto_extended_rollup_mode": "NON_EXPANDING_OR_DETACHED",
                "esto_extended_rollup_id": rollup_ids.get((row["esto_flow"], row["esto_product"]), non_expanding_rollup_id(row["esto_flow"])),
                "esto_extended_derived_from": "declared ESTO rollup contributors",
            }
        )
        rows.append(output)
    generated = pd.DataFrame(rows, columns=[column for column in base_esto.columns if column not in PROVENANCE_COLUMNS] + PROVENANCE_COLUMNS)

    existing_keys = {
        tuple(row)
        for row in base_esto[["economy", "flows", "products"]]
        .assign(
            economy=lambda frame: frame["economy"].map(_normalise_economy),
            flows=lambda frame: frame["flows"].map(_esto_code),
            products=lambda frame: frame["products"].map(_esto_code),
        )
        .itertuples(index=False, name=None)
    }
    generated_keys = list(
        zip(
            generated["economy"].map(_normalise_economy),
            generated["flows"].map(_esto_code),
            generated["products"].map(_esto_code),
        )
    )
    generated = generated.loc[[key not in existing_keys for key in generated_keys]].reset_index(drop=True)
    audit = long_rows.copy()
    audit["row_origin"] = "rollup_derived"
    return generated.reindex(columns=list(base_esto.columns)), audit


def build_rollup_tree_edges(rollup_catalogue: pd.DataFrame) -> pd.DataFrame:
    """Expose declared rollup parent/child relationships without changing values."""
    rows: list[dict[str, Any]] = []
    for _, rule in rollup_catalogue.iterrows():
        # The rolled flow is the actual derived node.  parent_flow_label is
        # retained as the surrounding tree context, not substituted for it.
        parent = _normalise_text(rule.get("rolled_flow", ""))
        context_parent = _normalise_text(rule.get("parent_flow_label", ""))
        children = [child.strip() for child in _normalise_text(rule.get("child_flow_labels", "")).split(";") if child.strip()]
        if not parent or not children:
            continue
        for child in children:
            rows.append(
                {
                    "source_system": rule["source_system"],
                    "rule_sheet": rule["rule_sheet"],
                    "rollup_mode": rule["rollup_mode"],
                    "rollup_group_id": rule["rollup_group_id"],
                    "parent_flow": parent,
                    "context_parent_flow": context_parent,
                    "child_flow": child,
                    "edge_type": "declared_rollup_hierarchy",
                }
            )
    return pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)


def _active_leap_mapping_rows(mapping_workbook_path: Path) -> pd.DataFrame:
    """Load active LEAP mappings used as sector/product inheritance evidence."""
    mappings = pd.read_excel(mapping_workbook_path, sheet_name="leap_combined_esto", dtype=object).fillna("")
    required = ["leap_sector_name_full_path", "raw_leap_fuel_name", "esto_flow", "esto_product"]
    _require_columns(mappings, required, "leap_combined_esto")
    removed = mappings.get("remove_row", pd.Series(False, index=mappings.index)).map(
        lambda value: _normalise_text(value).casefold() in {"true", "1", "yes", "y"}
    )
    duplicate = mappings.get("duplicate_to_remove", pd.Series(False, index=mappings.index)).map(
        lambda value: _normalise_text(value).casefold() in {"true", "1", "yes", "y"}
    )
    mappings = mappings.loc[~(removed | duplicate), required].copy()
    mappings["leap_sector_name_full_path"] = mappings["leap_sector_name_full_path"].map(_normalise_path)
    mappings["raw_leap_fuel_name"] = mappings["raw_leap_fuel_name"].map(_normalise_text)
    mappings["esto_flow"] = mappings["esto_flow"].map(_normalise_text)
    mappings["esto_product"] = mappings["esto_product"].map(_normalise_text)
    return mappings[mappings["leap_sector_name_full_path"].ne("") & mappings["esto_flow"].ne("")].drop_duplicates()


def _path_suffix_candidates(path: str) -> list[str]:
    parts = _normalise_path(path).split("/")
    return ["/".join(parts[index:]) for index in range(len(parts))]


def _mapping_rows_for_sector_and_fuel(
    mappings: pd.DataFrame,
    sector_path: str,
    fuel_label: str,
) -> pd.DataFrame:
    """Find mappings by longest sector suffix, then inherited fuel label."""
    fuel = _normalise_text(fuel_label)
    sector_suffixes = _path_suffix_candidates(sector_path)
    for suffix in sorted(sector_suffixes, key=len, reverse=True):
        scoped = mappings[mappings["leap_sector_name_full_path"].eq(suffix)]
        if scoped.empty:
            continue
        exact = scoped[scoped["raw_leap_fuel_name"].eq(fuel)]
        if not exact.empty:
            return exact
        normalised_fuel = re.sub(r"[^a-z0-9]+", "", fuel.casefold())
        fuzzy = scoped[
            scoped["raw_leap_fuel_name"].map(lambda value: re.sub(r"[^a-z0-9]+", "", value.casefold())).eq(normalised_fuel)
        ]
        if not fuzzy.empty:
            return fuzzy
    return mappings.iloc[0:0].copy()


def _extract_template_fuel_evidence(inventory: pd.DataFrame, sector_path: str) -> pd.DataFrame:
    """Extract descendant fuels and their LEAP transformation roles."""
    prefix = _normalise_path(sector_path).rstrip("/") + "/"
    descendants = inventory[inventory["branch_path"].str.startswith(prefix)].copy()
    rows: list[dict[str, Any]] = []
    for path in descendants["branch_path"].drop_duplicates():
        parts = path.split("/")
        role_positions = [index for index, part in enumerate(parts) if part in FUEL_ROLE_LABELS]
        if not role_positions or role_positions[-1] + 1 >= len(parts):
            if not _normalise_path(sector_path).casefold().startswith("demand/"):
                continue
            if not bool(inventory.loc[inventory["branch_path"].eq(path), "observed_as_leaf"].any()):
                continue
            rows.append(
                {
                    "branch_path": path,
                    "fuel_role": "Demand fuel",
                    "fuel_label": parts[-1],
                    "fuel_path": path,
                }
            )
            continue
        role_index = role_positions[-1]
        rows.append(
            {
                "branch_path": path,
                "fuel_role": parts[role_index],
                "fuel_label": parts[role_index + 1],
                "fuel_path": "/".join(parts[: role_index + 2]),
            }
        )
    return pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)


def _esto_flow_components(rollup_catalogue: pd.DataFrame, flow_label: str) -> list[str]:
    """Expand a mapped composite ESTO flow to declared component leaves."""
    label = _normalise_text(flow_label)
    direct_codes = re.findall(r"\d+(?:\.\d+)*", label.split(" ", 1)[0])
    if len(direct_codes) == 1:
        return [label]
    matching = rollup_catalogue[(rollup_catalogue["source_system"] == "ESTO") & rollup_catalogue["rolled_flow"].eq(label)]
    components: list[str] = []
    for child_list in matching["child_flow_labels"]:
        components.extend(child.strip() for child in _normalise_text(child_list).split(";") if child.strip())
    return sorted(set(components)) or [label]


def _existing_child_flow_match(
    existing_esto_flow_labels: set[str],
    parent_code: str,
    child_label: str,
) -> str:
    """Match template child names to existing ESTO labels despite punctuation/detail."""
    child_key = re.sub(r"[^a-z0-9]+", "", _normalise_text(child_label).casefold())
    matches: list[str] = []
    for flow in existing_esto_flow_labels:
        if not _esto_code(flow).startswith(parent_code + "."):
            continue
        existing_label = _normalise_text(flow).split(" ", 1)[-1]
        existing_key = re.sub(r"[^a-z0-9]+", "", existing_label.casefold())
        if existing_key == child_key or existing_key.startswith(child_key):
            matches.append(flow)
    return sorted(matches, key=lambda value: (_esto_code(value).count("."), value))[0] if matches else ""


def build_template_driven_child_candidates(
    inventory: pd.DataFrame,
    mapping_workbook_path: Path,
    rollup_catalogue: pd.DataFrame,
    existing_esto_flow_labels: set[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build reviewable child-flow candidates from Transformation/Demand trees.

    A candidate is a LEAP sector/process node with descendant fuel-role leaves.
    Fuel labels are inherited as products from its mapped parent sector.  The
    function does not invent values: candidate rows are structural zero rows,
    while the evidence table records the role/product combinations that need
    value allocation or review.
    """
    scoped = inventory[inventory["branch_path"].str.split("/").str[0].isin(["Transformation", "Demand"])].copy()
    mappings = _active_leap_mapping_rows(mapping_workbook_path)
    existing_esto_flow_labels = existing_esto_flow_labels or set()
    candidate_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()

    for path in sorted(scoped["branch_path"].drop_duplicates(), key=lambda value: (value.count("/"), value)):
        parts = path.split("/")
        if len(parts) < 3 or path in seen_nodes:
            continue
        if parts[0] == "Transformation":
            if "Processes" not in parts:
                continue
            process_index = parts.index("Processes")
            if process_index + 1 >= len(parts) or parts[process_index + 1] in FUEL_ROLE_LABELS:
                continue
            if process_index + 2 < len(parts) and parts[process_index + 2] in FUEL_ROLE_LABELS:
                continue
            sector_path = "/".join(parts[1:process_index]) or parts[1]
            child_label = parts[process_index + 1]
            if (sector_path.casefold(), child_label.casefold()) in SPECIAL_ALREADY_MAPPED_TEMPLATE_CHILDREN:
                continue
        else:
            if any(part in FUEL_ROLE_LABELS for part in parts):
                continue
            sector_path = "/".join(parts[1:-1])
            child_label = parts[-1]
            if not sector_path or child_label in {"All demand aggregated", "Other loss and own use"}:
                continue

        fuel_evidence = _extract_template_fuel_evidence(scoped, path)
        if fuel_evidence.empty:
            continue
        seen_nodes.add(path)
        mapped_products: list[dict[str, Any]] = []
        for _, fuel_row in fuel_evidence.iterrows():
            mapped = _mapping_rows_for_sector_and_fuel(mappings, sector_path, fuel_row["fuel_label"])
            for _, mapping in mapped.iterrows():
                mapped_products.append(
                    {
                        "fuel_role": fuel_row["fuel_role"],
                        "fuel_label": fuel_row["fuel_label"],
                        "esto_flow": mapping["esto_flow"],
                        "esto_product": mapping["esto_product"],
                    }
                )
        if not mapped_products:
            continue
        parent_flows = sorted(set(item["esto_flow"] for item in mapped_products))
        component_flows = sorted({component for parent in parent_flows for component in _esto_flow_components(rollup_catalogue, parent)})
        placement_status = "review_rollup_placement" if any("," in parent.split(" ", 1)[0] for parent in parent_flows) else "review_new_child"
        for component_index, component in enumerate(component_flows, start=1):
            parent_code = _esto_code(component)
            if not parent_code:
                continue
            existing_child = _existing_child_flow_match(existing_esto_flow_labels, parent_code, child_label)
            proposed_flow = existing_child or f"{parent_code}.{component_index:02d} {child_label}"
            child_status = "existing_esto_child" if existing_child else placement_status
            for item in mapped_products:
                evidence_rows.append(
                    {
                        "leap_sector_path": path,
                        "leap_parent_sector_path": sector_path,
                        "leap_child_label": child_label,
                        "fuel_role": item["fuel_role"],
                        "leap_fuel_label": item["fuel_label"],
                        "esto_parent_flow": item["esto_flow"],
                        "esto_component_flow": component,
                        "esto_product": item["esto_product"],
                        "proposed_child_flow": proposed_flow,
                        "candidate_status": child_status,
                    }
                )
                candidate_rows.append(
                    {
                        "flows": proposed_flow,
                        "products": item["esto_product"],
                        "esto_extended_row_origin": "template_driven_candidate",
                        "esto_extended_rule_id": "template_tree_child_inference",
                        "esto_extended_parent_flow": component,
                        "esto_extended_derived_from": f"{path} | {item['fuel_role']}",
                        "esto_extended_source_leap_paths": path,
                        "candidate_status": child_status,
                    }
                )
    evidence = pd.DataFrame(evidence_rows).drop_duplicates().reset_index(drop=True)
    if not evidence.empty:
        # Allocate child ordinals independently beneath each component leaf.
        # This prevents the second component of a rollup receiving ``.02``
        # merely because it was enumerated after the first component.
        ordinal_lookup: dict[tuple[str, str], int] = {}
        for component, group in evidence.groupby("esto_component_flow"):
            for ordinal, child_label in enumerate(sorted(group["leap_child_label"].unique()), start=1):
                ordinal_lookup[(component, child_label)] = ordinal
        evidence["proposed_child_flow"] = evidence.apply(
            lambda row: _existing_child_flow_match(
                existing_esto_flow_labels,
                _esto_code(row["esto_component_flow"]),
                row["leap_child_label"],
            ) or (
                f"{_esto_code(row['esto_component_flow'])}.{ordinal_lookup[(row['esto_component_flow'], row['leap_child_label'])]:02d} {row['leap_child_label']}"
            ),
            axis=1,
        )
        evidence["candidate_status"] = evidence.apply(
            lambda row: "existing_esto_child"
            if row["proposed_child_flow"] in existing_esto_flow_labels
            else row["candidate_status"],
            axis=1,
        )
        flow_lookup = {
            (row["esto_component_flow"], row["leap_sector_path"]): row["proposed_child_flow"]
            for _, row in evidence.drop_duplicates(["esto_component_flow", "leap_sector_path"]).iterrows()
        }
        for row in candidate_rows:
            row["flows"] = flow_lookup.get(
                (row["esto_extended_parent_flow"], row["esto_extended_source_leap_paths"]),
                row["flows"],
            )
        candidate_status_lookup = {
            (row["esto_component_flow"], row["leap_sector_path"]): row["candidate_status"]
            for _, row in evidence.drop_duplicates(["esto_component_flow", "leap_sector_path"]).iterrows()
        }
        candidate_rows = [
            row
            for row in candidate_rows
            if candidate_status_lookup.get(
                (row["esto_extended_parent_flow"], row["esto_extended_source_leap_paths"]),
                row["candidate_status"],
            )
            != "existing_esto_child"
        ]
        for row in candidate_rows:
            row["candidate_status"] = candidate_status_lookup.get(
                (row["esto_extended_parent_flow"], row["esto_extended_source_leap_paths"]),
                row["candidate_status"],
            )
    candidates = pd.DataFrame(candidate_rows).drop_duplicates().reset_index(drop=True)
    return candidates, evidence


def materialise_template_candidate_rows(base_esto: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    """Create zero-valued structural rows for review, never merge automatically."""
    if candidates.empty:
        return pd.DataFrame(columns=list(base_esto.columns) + ["candidate_status"])
    rows = []
    source_columns = [column for column in base_esto.columns if column not in PROVENANCE_COLUMNS]
    year_columns = _year_columns(base_esto)
    for _, candidate in candidates.iterrows():
        row = {column: pd.NA for column in source_columns}
        row["economy"] = "TEMPLATE"
        row["flows"] = candidate["flows"]
        row["products"] = candidate["products"]
        if "is_subtotal" in row:
            row["is_subtotal"] = False
        for year in year_columns:
            row[year] = 0.0
        row.update({column: candidate.get(column, "") for column in PROVENANCE_COLUMNS})
        row["candidate_status"] = candidate["candidate_status"]
        rows.append(row)
    return pd.DataFrame(rows, columns=source_columns + PROVENANCE_COLUMNS + ["candidate_status"])


def apply_general_subtotal_labels(
    frame: pd.DataFrame,
    all_flow_labels: set[str],
    all_product_labels: set[str],
) -> pd.DataFrame:
    """Mark rows subtotal when their flow or product has descendants."""
    output = frame.copy()
    flow_codes = {_esto_code(label): label for label in all_flow_labels if _esto_code(label)}
    product_codes = {_esto_code(label): label for label in all_product_labels if _esto_code(label)}
    flow_parent_codes = {
        code for code in flow_codes if any(other.startswith(code + ".") for other in flow_codes)
    }
    product_parent_codes = {
        code for code in product_codes if any(other.startswith(code + ".") for other in product_codes)
    }
    output["is_subtotal"] = output.apply(
        lambda row: (
            _normalise_text(row.get("is_subtotal", "")).casefold() in {"true", "1", "yes", "y"}
            or _esto_code(row.get("flows", "")) in flow_parent_codes
            or _esto_code(row.get("products", "")) in product_parent_codes
        ),
        axis=1,
    )
    return output


def build_evenly_disaggregated_candidate_rows(
    base_esto: pd.DataFrame,
    candidate_rows: pd.DataFrame,
    all_flow_labels: set[str],
    all_product_labels: set[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Populate every candidate economy by evenly splitting each parent row.

    Allocation is performed independently for each economy/product/year. A
    parent value is divided equally across the direct candidate children that
    exist for that product; nested candidates are then allocated from the
    populated intermediate rows. This creates a deterministic fourth-dataset
    fixture while retaining exact parent-child conservation for each populated
    branch.
    """
    if candidate_rows.empty:
        return candidate_rows.copy(), pd.DataFrame()
    year_columns = _year_columns(base_esto)
    base_source = base_esto.drop_duplicates(["economy", "flows", "products"]).copy()
    flow_labels = set(base_source["flows"].dropna().map(_normalise_text)) | all_flow_labels
    flow_by_code = {_esto_code(label): label for label in flow_labels if _esto_code(label)}
    candidate = candidate_rows.drop_duplicates(["flows", "products"]).copy()
    candidate_keys = set(zip(candidate["flows"], candidate["products"]))
    candidate_flows = set(candidate["flows"])
    child_lookup: dict[str, list[str]] = {}
    for flow in candidate_flows:
        code = _esto_code(flow)
        parent_code = code.rsplit(".", 1)[0] if "." in code else ""
        parent_flow = flow_by_code.get(parent_code, "")
        if parent_flow:
            child_lookup.setdefault(parent_flow, []).append(flow)
    for parent in child_lookup:
        child_lookup[parent] = sorted(set(child_lookup[parent]), key=lambda value: (_esto_code(value).count("."), value))

    source_columns = [column for column in base_esto.columns if column not in PROVENANCE_COLUMNS]
    economies = sorted(base_source["economy"].dropna().unique())
    base_lookup = base_source.set_index(["economy", "flows", "products"])
    generated_lookup: dict[tuple[str, str, str], dict[str, float]] = {}
    output_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []

    def parent_values(economy: str, flow: str, product: str) -> dict[str, float]:
        key = (economy, flow, product)
        if key in generated_lookup:
            return generated_lookup[key]
        if key not in base_lookup.index:
            return {year: 0.0 for year in year_columns}
        source = base_lookup.loc[key]
        if isinstance(source, pd.DataFrame):
            source = source.iloc[0]
        values = {}
        for year in year_columns:
            value = pd.to_numeric(source[year], errors="coerce")
            values[year] = 0.0 if pd.isna(value) else float(value)
        return values

    ordered_candidates = candidate.assign(_depth=candidate["flows"].map(lambda value: _esto_code(value).count("."))).sort_values(["_depth", "flows", "products"])
    for _, candidate_row in ordered_candidates.iterrows():
        flow = candidate_row["flows"]
        product = candidate_row["products"]
        flow_children = [child for child in child_lookup.get(flow_by_code.get(_esto_code(flow), flow), []) if (child, product) in candidate_keys]
        code = _esto_code(flow)
        parent_flow = flow_by_code.get(code.rsplit(".", 1)[0], "") if "." in code else ""
        if not parent_flow:
            continue
        siblings = [child for child in child_lookup.get(parent_flow, []) if (child, product) in candidate_keys]
        divisor = len(siblings) or 1
        for economy in economies:
            source_values = parent_values(economy, parent_flow, product)
            values = {year: source_values[year] / divisor for year in year_columns}
            generated_lookup[(economy, flow, product)] = values
            row = {column: pd.NA for column in source_columns}
            row.update({column: candidate_row.get(column, "") for column in PROVENANCE_COLUMNS})
            row.update({"economy": economy, "flows": flow, "products": product, "esto_extended_row_origin": "synthetic_disaggregation", "esto_extended_rule_id": "even_parent_split", "esto_extended_parent_flow": parent_flow, "candidate_status": candidate_row.get("candidate_status", "")})
            row["is_subtotal"] = candidate_row.get("is_subtotal", False)
            row.update(values)
            output_rows.append(row)
        audit_rows.append({"flow": flow, "product": product, "parent_flow": parent_flow, "direct_sibling_count": divisor, "allocation_method": "equal_split"})
    output = pd.DataFrame(output_rows, columns=source_columns + PROVENANCE_COLUMNS + ["candidate_status"])
    output = apply_general_subtotal_labels(output, flow_labels, all_product_labels)
    return output, pd.DataFrame(audit_rows)


def audit_even_disaggregation_values(
    extended: pd.DataFrame,
    candidate_rows: pd.DataFrame,
) -> pd.DataFrame:
    """Check parent conservation and equal direct-child allocations."""
    if candidate_rows.empty:
        return pd.DataFrame(columns=["parent_flow", "product_count", "max_conservation_difference", "max_child_share_difference", "status"])
    labels = set(extended["flows"].dropna().map(_normalise_text)) | set(candidate_rows["flows"].dropna().map(_normalise_text))
    by_code = {_esto_code(label): label for label in labels if _esto_code(label)}
    candidate_flows = set(candidate_rows["flows"])
    parent_children: dict[str, list[str]] = {}
    for flow in candidate_flows:
        code = _esto_code(flow)
        parent = by_code.get(code.rsplit(".", 1)[0], "") if "." in code else ""
        if parent:
            parent_children.setdefault(parent, []).append(flow)
    year_columns = _year_columns(extended)
    rows: list[dict[str, Any]] = []
    for parent, children in sorted(parent_children.items()):
        child_frame = extended[extended["flows"].isin(children)].copy()
        products = sorted(child_frame["products"].dropna().unique())
        parent_frame = extended[extended["flows"].eq(parent) & extended["products"].isin(products)].copy()
        if parent_frame.empty or child_frame.empty:
            rows.append({"parent_flow": parent, "product_count": len(products), "max_conservation_difference": "", "max_child_share_difference": "", "status": "skipped_no_parent_values"})
            continue
        parent_sum = parent_frame.groupby(["economy", "products"], as_index=False)[year_columns].sum()
        child_sum = child_frame.groupby(["economy", "products"], as_index=False)[year_columns].sum()
        merged = parent_sum.merge(child_sum, on=["economy", "products"], how="inner", suffixes=("_parent", "_children"))
        max_conservation = 0.0
        max_share = 0.0
        for year in year_columns:
            max_conservation = max(max_conservation, float((pd.to_numeric(merged[f"{year}_parent"], errors="coerce").fillna(0.0) - pd.to_numeric(merged[f"{year}_children"], errors="coerce").fillna(0.0)).abs().max() or 0.0))
        child_values = child_frame.groupby(["economy", "products", "flows"], as_index=False)[year_columns].sum()
        for year in year_columns:
            grouped = child_values.groupby(["economy", "products"])[year].transform("mean")
            max_share = max(max_share, float((pd.to_numeric(child_values[year], errors="coerce").fillna(0.0) - pd.to_numeric(grouped, errors="coerce").fillna(0.0)).abs().max() or 0.0))
        rows.append({"parent_flow": parent, "product_count": len(products), "max_conservation_difference": max_conservation, "max_child_share_difference": max_share, "status": "pass" if max_conservation <= 1e-8 and max_share <= 1e-8 else "fail"})
    return pd.DataFrame(rows)


def build_transport_tree_candidates(
    inventory: pd.DataFrame,
    mapping_workbook_path: Path,
    existing_esto_flow_labels: set[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build nested Road child candidates from Freight/Passenger road branches."""
    transport_roots = {"Demand/Freight road", "Demand/Passenger road"}
    paths = sorted(
        {
            path
            for path in inventory["branch_path"].drop_duplicates()
            if any(path == root or path.startswith(root + "/") for root in transport_roots)
        },
        key=lambda value: (value.count("/"), value),
    )
    nodes = [path for path in paths if any(other.startswith(path + "/") for other in paths)]
    if not nodes:
        return pd.DataFrame(), pd.DataFrame()

    mappings = _active_leap_mapping_rows(mapping_workbook_path)
    code_lookup: dict[str, str] = {}
    root_flow = "15.02 Road"
    for path in nodes:
        parent_path = "/".join(path.split("/")[:-1])
        parent_flow = code_lookup.get(parent_path, root_flow)
        parent_code = _esto_code(parent_flow)
        sibling_labels = sorted(
            {
                child.split("/")[-1]
                for child in nodes
                if "/".join(child.split("/")[:-1]) == parent_path
            },
            key=str.casefold,
        )
        ordinal = sibling_labels.index(path.split("/")[-1]) + 1
        code_lookup[path] = f"{parent_code}.{ordinal:02d} {path.split('/')[-1]}"

    candidate_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    for path in nodes:
        fuel_evidence = _extract_template_fuel_evidence(inventory, path)
        if fuel_evidence.empty:
            continue
        proposed_flow = code_lookup[path]
        for _, fuel_row in fuel_evidence.iterrows():
            mapped = _mapping_rows_for_sector_and_fuel(mappings, "Road", fuel_row["fuel_label"])
            for _, mapping in mapped.iterrows():
                evidence_rows.append(
                    {
                        "leap_sector_path": path,
                        "leap_parent_sector_path": "/".join(path.split("/")[:-1]),
                        "leap_child_label": path.split("/")[-1],
                        "fuel_role": fuel_row["fuel_role"],
                        "leap_fuel_label": fuel_row["fuel_label"],
                        "esto_parent_flow": root_flow,
                        "esto_component_flow": root_flow,
                        "esto_product": mapping["esto_product"],
                        "proposed_child_flow": proposed_flow,
                        "candidate_status": "review_transport_child",
                    }
                )
                candidate_rows.append(
                    {
                        "flows": proposed_flow,
                        "products": mapping["esto_product"],
                        "esto_extended_row_origin": "template_driven_candidate",
                        "esto_extended_rule_id": "transport_tree_child_inference",
                        "esto_extended_parent_flow": root_flow if path in transport_roots else code_lookup["/".join(path.split("/")[:-1])],
                        "esto_extended_derived_from": f"{path} | {fuel_row['fuel_role']}",
                        "esto_extended_source_leap_paths": path,
                        "candidate_status": "review_transport_child",
                    }
                )
    return pd.DataFrame(candidate_rows).drop_duplicates().reset_index(drop=True), pd.DataFrame(evidence_rows).drop_duplicates().reset_index(drop=True)


def _active_mapping_sheet_rows(
    mapping_workbook_path: Path,
    sheet_name: str,
    required_columns: list[str],
) -> pd.DataFrame:
    """Load active rows from a mapping sheet while ignoring review removals."""
    frame = pd.read_excel(mapping_workbook_path, sheet_name=sheet_name, dtype=object).fillna("")
    _require_columns(frame, required_columns, sheet_name)
    remove = frame.get("duplicate_to_remove", pd.Series(False, index=frame.index)).map(
        lambda value: _normalise_text(value).casefold() in {"true", "1", "yes", "y"}
    )
    remove |= frame.get("remove_row", pd.Series(False, index=frame.index)).map(
        lambda value: _normalise_text(value).casefold() in {"true", "1", "yes", "y"}
    )
    frame = frame.loc[~remove, required_columns].copy()
    for column in required_columns:
        frame[column] = frame[column].map(_normalise_text)
    return frame[frame[required_columns].ne("").all(axis=1)].drop_duplicates().reset_index(drop=True)


def _candidate_source_path_variants(branch_path: str) -> list[str]:
    """Return likely mapping keys for a full template branch path."""
    path = _normalise_path(branch_path)
    parts = path.split("/")
    if parts and parts[0] in {"Transformation", "Demand"}:
        parts = parts[1:]
    variants = ["/".join(parts[:index]) for index in range(1, len(parts) + 1)]
    variants.extend("/".join(parts[index:]) for index in range(len(parts)) if parts[index:])
    lower = path.casefold()
    if lower.startswith("demand/freight road") or lower.startswith("demand/passenger road"):
        variants.insert(0, "Road")
    if lower.startswith("transformation/transmission and distribution"):
        variants.insert(0, "Transmission and Distribution")
    return list(dict.fromkeys(variants))


def _find_mapping_anchor_rows(
    mapping_rows: pd.DataFrame,
    branch_path: str,
    fuel_label: str,
    source_path_column: str,
    fuel_column: str,
) -> tuple[str, pd.DataFrame]:
    """Find the longest active mapping anchor supporting a branch fuel."""
    fuel_key = re.sub(r"[^a-z0-9]+", "", _normalise_text(fuel_label).casefold())
    for variant in sorted(_candidate_source_path_variants(branch_path), key=len, reverse=True):
        scoped = mapping_rows[mapping_rows[source_path_column].eq(variant)]
        if scoped.empty:
            continue
        scoped = scoped[
            scoped[fuel_column].map(lambda value: re.sub(r"[^a-z0-9]+", "", value.casefold())).eq(fuel_key)
        ]
        if not scoped.empty:
            return variant, scoped
    return "", mapping_rows.iloc[0:0].copy()


def build_mapping_candidates_from_template_evidence(
    template_evidence: pd.DataFrame,
    mapping_workbook_path: Path,
) -> dict[str, pd.DataFrame]:
    """Derive LEAP→ESTO, LEAP→Ninth, and Ninth→ESTO review candidates."""
    empty_outputs = {
        "leap_to_esto": pd.DataFrame(),
        "leap_to_ninth": pd.DataFrame(),
        "ninth_to_esto": pd.DataFrame(),
    }
    if template_evidence.empty:
        return empty_outputs
    leap_esto = _active_mapping_sheet_rows(
        mapping_workbook_path,
        "leap_combined_esto",
        ["leap_sector_name_full_path", "raw_leap_fuel_name", "esto_flow", "esto_product"],
    )
    leap_ninth = _active_mapping_sheet_rows(
        mapping_workbook_path,
        "leap_combined_ninth",
        ["leap_sector_name_full_path", "raw_leap_fuel_name", "ninth_sector", "ninth_fuel"],
    )
    ninth_esto = _active_mapping_sheet_rows(
        mapping_workbook_path,
        "ninth_pairs_to_esto_pairs",
        ["ninth_sector", "ninth_fuel", "esto_flow", "esto_product"],
    )
    leap_esto_existing = set(zip(leap_esto.iloc[:, 0], leap_esto.iloc[:, 1], leap_esto.iloc[:, 2], leap_esto.iloc[:, 3]))
    leap_ninth_existing = set(zip(leap_ninth.iloc[:, 0], leap_ninth.iloc[:, 1], leap_ninth.iloc[:, 2], leap_ninth.iloc[:, 3]))
    ninth_esto_existing = set(zip(ninth_esto.iloc[:, 0], ninth_esto.iloc[:, 1], ninth_esto.iloc[:, 2], ninth_esto.iloc[:, 3]))
    leap_esto_rows: list[dict[str, Any]] = []
    leap_ninth_rows: list[dict[str, Any]] = []
    ninth_esto_rows: list[dict[str, Any]] = []
    for _, evidence in template_evidence.drop_duplicates().iterrows():
        branch_path = evidence["leap_sector_path"]
        fuel = evidence["leap_fuel_label"]
        source_path = "/".join(_normalise_path(branch_path).split("/")[1:])
        proposed_flow = evidence["proposed_child_flow"]
        proposed_product = evidence["esto_product"]
        leap_esto_key = (source_path, fuel, proposed_flow, proposed_product)
        if leap_esto_key not in leap_esto_existing:
            leap_esto_rows.append(
                {
                    "leap_sector_name_full_path": source_path,
                    "raw_leap_fuel_name": fuel,
                    "esto_flow": proposed_flow,
                    "esto_product": proposed_product,
                    "leap_is_subtotal": False,
                    "esto_pair_is_subtotal": False,
                    "duplicate_to_remove": False,
                    "mapping_anchor_flow": evidence["esto_parent_flow"],
                    "mapping_anchor_path": _find_mapping_anchor_rows(leap_esto, branch_path, fuel, "leap_sector_name_full_path", "raw_leap_fuel_name")[0],
                    "candidate_status": evidence["candidate_status"],
                }
            )
        anchor_path, ninth_matches = _find_mapping_anchor_rows(
            leap_ninth,
            branch_path,
            fuel,
            "leap_sector_name_full_path",
            "raw_leap_fuel_name",
        )
        if ninth_matches.empty:
            continue
        for _, ninth_match in ninth_matches.iterrows():
            ninth_key = (source_path, fuel, ninth_match["ninth_sector"], ninth_match["ninth_fuel"])
            if ninth_key not in leap_ninth_existing:
                leap_ninth_rows.append(
                    {
                        "leap_sector_name_full_path": source_path,
                        "raw_leap_fuel_name": fuel,
                        "ninth_sector": ninth_match["ninth_sector"],
                        "ninth_fuel": ninth_match["ninth_fuel"],
                        "leap_is_subtotal": False,
                        "ninth_pair_is_subtotal": False,
                        "duplicate_to_remove": False,
                        "mapping_anchor_path": anchor_path,
                        "candidate_status": evidence["candidate_status"],
                    }
                )
            ninth_esto_key = (ninth_match["ninth_sector"], ninth_match["ninth_fuel"], proposed_flow, proposed_product)
            if ninth_esto_key not in ninth_esto_existing:
                ninth_esto_rows.append(
                    {
                        "ninth_sector": ninth_match["ninth_sector"],
                        "ninth_fuel": ninth_match["ninth_fuel"],
                        "esto_flow": proposed_flow,
                        "esto_product": proposed_product,
                        "ninth_pair_is_subtotal": False,
                        "esto_pair_is_subtotal": False,
                        "duplicate_to_remove": False,
                        "mapping_anchor_esto_flow": evidence["esto_parent_flow"],
                        "candidate_status": evidence["candidate_status"],
                    }
                )
    outputs = {
        "leap_to_esto": pd.DataFrame(leap_esto_rows).drop_duplicates().reset_index(drop=True),
        "leap_to_ninth": pd.DataFrame(leap_ninth_rows).drop_duplicates().reset_index(drop=True),
        "ninth_to_esto": pd.DataFrame(ninth_esto_rows).drop_duplicates().reset_index(drop=True),
    }
    if not outputs["ninth_to_esto"].empty:
        combined = pd.concat(
            [ninth_esto[["ninth_sector", "ninth_fuel", "esto_flow", "esto_product"]], outputs["ninth_to_esto"][["ninth_sector", "ninth_fuel", "esto_flow", "esto_product"]]],
            ignore_index=True,
        ).drop_duplicates()
        source_counts = combined.groupby(["ninth_sector", "ninth_fuel"]).apply(
            lambda frame: frame[["esto_flow", "esto_product"]].drop_duplicates().shape[0]
        )
        target_counts = combined.groupby(["esto_flow", "esto_product"]).apply(
            lambda frame: frame[["ninth_sector", "ninth_fuel"]].drop_duplicates().shape[0]
        )
        outputs["ninth_to_esto"]["candidate_status"] = outputs["ninth_to_esto"].apply(
            lambda row: "review_many_to_many_before_adding"
            if source_counts.get((row["ninth_sector"], row["ninth_fuel"]), 0) > 1
            or target_counts.get((row["esto_flow"], row["esto_product"]), 0) > 1
            else row["candidate_status"],
            axis=1,
        )
    return outputs


def build_extended_default_audits(
    base_esto: pd.DataFrame,
    extended: pd.DataFrame,
    generated: pd.DataFrame,
    template_candidates: pd.DataFrame,
    rollup_catalogue: pd.DataFrame,
    disaggregation_audit: pd.DataFrame | None = None,
    disaggregation_value_audit: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the reusable hierarchy, subtotal, and detached-category checks."""
    base_flows = set(base_esto["flows"].dropna().map(_normalise_text))
    candidate_flows = set(template_candidates.get("flows", pd.Series(dtype=object)).dropna().map(_normalise_text))
    all_flows = base_flows | candidate_flows
    code_to_flow = {_esto_code(flow): flow for flow in all_flows if _esto_code(flow)}
    detail_rows: list[dict[str, Any]] = []
    for _, row in template_candidates.iterrows():
        code = _esto_code(row["flows"])
        parent_code = code.rsplit(".", 1)[0] if "." in code else ""
        detail_rows.append(
            {
                "check_name": "candidate_parent_closure",
                "item": row["flows"],
                "parent": code_to_flow.get(parent_code, row.get("esto_extended_parent_flow", "")),
                "status": "pass" if parent_code in code_to_flow else "fail",
                "detail": row.get("esto_extended_source_leap_paths", ""),
            }
        )
    rollup_mask = generated.get("esto_extended_row_origin", pd.Series(dtype=object)).eq("rollup_derived")
    candidate_flow_labels = set(template_candidates.get("flows", pd.Series(dtype=object)).dropna().map(_normalise_text))
    candidate_product_labels = set(template_candidates.get("products", pd.Series(dtype=object)).dropna().map(_normalise_text)) | set(base_esto["products"].dropna().map(_normalise_text))
    expected_candidates = apply_general_subtotal_labels(
        template_candidates,
        base_flows | candidate_flow_labels,
        candidate_product_labels,
    )
    candidate_subtotal_ok = template_candidates.empty or (
        expected_candidates["is_subtotal"].astype(bool).eq(
            template_candidates["is_subtotal"].map(
                lambda value: _normalise_text(value).casefold() in {"true", "1", "yes", "y"}
            )
        ).all()
    )
    rollup_subtotal_ok = not rollup_mask.any() or generated.loc[rollup_mask, "is_subtotal"].map(
        lambda value: _normalise_text(value).casefold() in {"true", "1", "yes", "y"}
    ).all()
    detail_rows.extend(
        [
            {"check_name": "candidate_subtotal_roles", "item": "template_candidate_rows", "parent": "", "status": "pass" if candidate_subtotal_ok else "fail", "detail": "Flow and product parents are subtotals; leaves remain non-subtotals."},
            {"check_name": "rollup_rows_are_subtotals", "item": "rollup_derived", "parent": "", "status": "pass" if rollup_subtotal_ok else "fail", "detail": "Derived rollup rows remain subtotal rows."},
            {"check_name": "extended_duplicate_keys", "item": "economy/flows/products", "parent": "", "status": "pass" if not extended.duplicated(["economy", "flows", "products"]).any() else "fail", "detail": "No duplicate ESTO keys."},
        ]
    )
    detached = rollup_catalogue[rollup_catalogue["rollup_mode"].isin(["DETACHED", "NON_EXPANDING"])]
    detail_rows.append({"check_name": "declared_detached_rollups", "item": "rollup catalogue", "parent": "", "status": "info", "detail": f"{len(detached)} declared boundary rules retained as metadata."})
    if disaggregation_audit is not None and not disaggregation_audit.empty:
        detail_rows.append({"check_name": "synthetic_disaggregation_rules", "item": "candidate rows", "parent": "", "status": "pass", "detail": f"{len(disaggregation_audit):,} flow/product allocations populated by equal parent splits."})
    if disaggregation_value_audit is not None and not disaggregation_value_audit.empty:
        failed_value_checks = int(disaggregation_value_audit["status"].eq("fail").sum())
        detail_rows.append({"check_name": "synthetic_value_conservation", "item": "candidate parent flows", "parent": "", "status": "fail" if failed_value_checks else "pass", "detail": f"{failed_value_checks:,} parent boundaries failed conservation/equal-share checks."})
    details = pd.DataFrame(detail_rows)
    summary = details.groupby(["check_name", "status"], as_index=False).size().rename(columns={"size": "count"})
    return summary, details


def build_esto_extended(
    base_esto_path: Path,
    template_dir: Path,
    mapping_workbook_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    """Build the test dataset and its audit files without changing inputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    esto = pd.read_csv(base_esto_path, dtype=object, low_memory=False)
    _require_columns(esto, ESTO_REQUIRED_COLUMNS, "Base ESTO data")
    esto = _with_provenance_columns(esto)

    inventory = combine_branch_inventories(
        read_leap_template_branch_inventory(template_dir),
        read_demand_branch_inventory(DEMAND_BRANCH_WORKBOOK_PATH),
    )
    mapped_paths = load_active_leap_esto_paths(mapping_workbook_path)
    candidates = build_unmapped_branch_candidates(inventory, mapped_paths)
    unmapped_paths = candidates.loc[~candidates["exact_active_esto_mapping"], "branch_path"].tolist()
    rule_source_paths = "|".join(
        path
        for path in unmapped_paths
        if any(token in path.casefold() for token in ["commercial and public services", "datacentres"])
    )

    generated, lng_audit = restore_established_lng_rows(esto, base_esto_path)
    rollup_catalogue = load_rollup_catalogue(mapping_workbook_path)
    rollup_generated, rollup_audit = build_esto_rollup_rows(esto, mapping_workbook_path)
    all_generated = pd.concat([generated, rollup_generated], ignore_index=True)
    candidate_flows = load_esto_flow_tree(base_esto_path)
    extension_candidates = build_tree_based_extension_candidates(candidates, candidate_flows)
    candidate_sets = summarise_extension_candidate_sets(extension_candidates)
    leap_parent_sets = summarise_leap_parent_candidate_sets(extension_candidates)
    template_child_candidates, template_child_evidence = build_template_driven_child_candidates(
        inventory,
        mapping_workbook_path,
        rollup_catalogue,
        existing_esto_flow_labels=set(candidate_flows["esto_flow"]),
    )
    transport_candidates, transport_evidence = build_transport_tree_candidates(
        inventory,
        mapping_workbook_path,
        set(candidate_flows["esto_flow"]),
    )
    template_child_candidates = pd.concat([template_child_candidates, transport_candidates], ignore_index=True).drop_duplicates()
    template_child_evidence = pd.concat([template_child_evidence, transport_evidence], ignore_index=True).drop_duplicates()
    template_candidate_rows = materialise_template_candidate_rows(esto, template_child_candidates)
    all_flow_labels = set(esto["flows"].dropna().map(_normalise_text)) | set(template_child_candidates["flows"].dropna().map(_normalise_text))
    all_product_labels = set(esto["products"].dropna().map(_normalise_text)) | set(template_child_candidates["products"].dropna().map(_normalise_text))
    template_candidate_rows = apply_general_subtotal_labels(template_candidate_rows, all_flow_labels, all_product_labels)
    disaggregated_rows, disaggregation_audit = build_evenly_disaggregated_candidate_rows(
        esto,
        template_candidate_rows,
        all_flow_labels,
        all_product_labels,
    )
    mapping_candidate_outputs = build_mapping_candidates_from_template_evidence(
        template_child_evidence[template_child_evidence["candidate_status"].ne("existing_esto_child")],
        mapping_workbook_path,
    )

    all_generated = pd.concat([all_generated, disaggregated_rows], ignore_index=True)
    extended = pd.concat([esto, all_generated], ignore_index=True)
    extended = apply_general_subtotal_labels(extended, all_flow_labels, all_product_labels)
    disaggregation_value_audit = audit_even_disaggregation_values(extended, template_candidate_rows)
    key_columns = ["economy", "flows", "products"]
    duplicate_keys = extended.duplicated(key_columns, keep=False)
    if duplicate_keys.any():
        raise ValueError(f"ESTO Extended contains duplicate keys: {int(duplicate_keys.sum())}")

    output_paths = {
        "dataset": output_dir / "esto_extended_test.csv",
        "data_dataset": REPO_ROOT / "data" / "esto_extended.csv",
        "branch_inventory": output_dir / "leap_template_branch_inventory.csv",
        "unmapped_candidates": output_dir / "unmapped_leap_branch_candidates.csv",
        "generated_rows": output_dir / "esto_extended_generated_rows.csv",
        "rollup_catalogue": output_dir / "esto_extended_rollup_catalogue.csv",
        "rollup_rows": output_dir / "esto_extended_rollup_rows.csv",
        "rollup_lineage": output_dir / "esto_extended_rollup_lineage.csv",
        "rollup_tree_edges": output_dir / "esto_extended_rollup_tree_edges.csv",
        "template_child_candidates": output_dir / "esto_extended_template_child_candidates.csv",
        "template_child_evidence": output_dir / "esto_extended_template_child_evidence.csv",
        "template_candidate_rows": output_dir / "esto_extended_template_candidate_rows.csv",
        "disaggregated_rows": output_dir / "esto_extended_disaggregated_rows.csv",
        "disaggregation_audit": output_dir / "esto_extended_disaggregation_audit.csv",
        "disaggregation_value_audit": output_dir / "esto_extended_disaggregation_value_audit.csv",
        "mapping_candidates_leap_to_esto": output_dir / "esto_extended_mapping_candidates_leap_to_esto.csv",
        "mapping_candidates_leap_to_ninth": output_dir / "esto_extended_mapping_candidates_leap_to_ninth.csv",
        "mapping_candidates_ninth_to_esto": output_dir / "esto_extended_mapping_candidates_ninth_to_esto.csv",
        "hierarchy_audit_summary": output_dir / "esto_extended_hierarchy_audit_summary.csv",
        "hierarchy_audit_details": output_dir / "esto_extended_hierarchy_audit_details.csv",
        "rule_summary": output_dir / "esto_extended_rule_summary.csv",
        "extension_registry": output_dir / "esto_extended_extension_registry.csv",
        "extension_candidates": output_dir / "esto_extended_extension_candidates.csv",
        "extension_candidate_sets": output_dir / "esto_extended_extension_candidate_sets.csv",
        "leap_parent_candidate_sets": output_dir / "esto_extended_leap_parent_candidate_sets.csv",
        "lng_split_audit": output_dir / "esto_extended_lng_split_audit.csv",
    }
    extended.to_csv(output_paths["dataset"], index=False)
    # Keep the reusable production fixture compact.  Detailed provenance and
    # review status remain available in the results/ audit artefacts and the
    # full test dataset above, but are not part of the ESTO-shaped input that
    # downstream mapping code consumes.
    production_dataset = extended.drop(
        columns=PROVENANCE_COLUMNS + ["candidate_status"],
        errors="ignore",
    )
    production_dataset.to_csv(output_paths["data_dataset"], index=False)
    inventory.to_csv(output_paths["branch_inventory"], index=False)
    candidates.to_csv(output_paths["unmapped_candidates"], index=False)
    all_generated.to_csv(output_paths["generated_rows"], index=False)
    rollup_catalogue.to_csv(output_paths["rollup_catalogue"], index=False)
    rollup_generated.to_csv(output_paths["rollup_rows"], index=False)
    rollup_audit.to_csv(output_paths["rollup_lineage"], index=False)
    build_rollup_tree_edges(rollup_catalogue).to_csv(output_paths["rollup_tree_edges"], index=False)
    template_child_candidates.to_csv(output_paths["template_child_candidates"], index=False)
    template_child_evidence.to_csv(output_paths["template_child_evidence"], index=False)
    template_candidate_rows.to_csv(output_paths["template_candidate_rows"], index=False)
    disaggregated_rows.to_csv(output_paths["disaggregated_rows"], index=False)
    disaggregation_audit.to_csv(output_paths["disaggregation_audit"], index=False)
    disaggregation_value_audit.to_csv(output_paths["disaggregation_value_audit"], index=False)
    for key, frame in mapping_candidate_outputs.items():
        output_paths[f"mapping_candidates_{key}"].parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output_paths[f"mapping_candidates_{key}"], index=False)
    hierarchy_summary, hierarchy_details = build_extended_default_audits(
        esto,
        extended,
        all_generated,
        template_candidate_rows,
        rollup_catalogue,
        disaggregation_audit,
        disaggregation_value_audit,
    )
    hierarchy_summary.to_csv(output_paths["hierarchy_audit_summary"], index=False)
    hierarchy_details.to_csv(output_paths["hierarchy_audit_details"], index=False)
    pd.DataFrame(
        [
            {
                "rule_id": ESTABLISHED_FLOW_RULE["rule_id"],
                "source_flow": ESTABLISHED_FLOW_RULE["source_flow"],
                "generated_flows": "|".join(ESTABLISHED_FLOW_RULE["generated_flows"]),
                "generated_rows": len(generated),
                "value_method": ESTABLISHED_FLOW_RULE["value_method"],
            }
        ]
    ).to_csv(output_paths["rule_summary"], index=False)
    extension_candidates.to_csv(output_paths["extension_candidates"], index=False)
    candidate_sets.to_csv(output_paths["extension_candidate_sets"], index=False)
    leap_parent_sets.to_csv(output_paths["leap_parent_candidate_sets"], index=False)
    lng_audit.to_csv(output_paths["lng_split_audit"], index=False)
    registry = pd.DataFrame(
        [
            {
                "extension_id": ESTABLISHED_FLOW_RULE["rule_id"],
                "parent_flow": ESTABLISHED_FLOW_RULE["source_flow"],
                "generated_flow": "|".join(ESTABLISHED_FLOW_RULE["generated_flows"]),
                "generated_code": "09.06.02.01|09.06.02.02",
                "generated_label": "Liquefaction|Regasification",
                "naming_method": "established_esto_code_and_label",
                "value_method": ESTABLISHED_FLOW_RULE["value_method"],
                "source_leap_paths": rule_source_paths,
                "review_status": "established_structural_rule",
            }
        ]
    )
    registry.to_csv(output_paths["extension_registry"], index=False)
    return output_paths


#%%
def run_synthetic_smoke_test() -> None:
    """Verify the residual algorithm with a tiny in-memory example."""
    sample = pd.DataFrame(
        [
            {"economy": "20USA", "flows": "16.01 Commercial and public services", "products": "17 Electricity", "is_subtotal": True, "2022": 100.0},
            {"economy": "20USA", "flows": "16.01.01 Datacentres", "products": "17 Electricity", "is_subtotal": False, "2022": 25.0},
        ]
    )
    generated, _ = apply_parent_minus_children_rule(sample, DEMO_RESIDUAL_RULE)
    assert len(generated) == 1
    assert generated.iloc[0]["flows"] == DEMO_RESIDUAL_RULE["generated_flow"]
    assert generated.iloc[0]["2022"] == 75.0
    assert generated.iloc[0]["esto_extended_row_origin"] == "generated"
    print("Synthetic ESTO Extended smoke test passed")


#%%
RUN_REAL_BUILD = True
RUN_SYNTHETIC_SMOKE_TEST = True

if __name__ == "__main__":
    if RUN_SYNTHETIC_SMOKE_TEST:
        run_synthetic_smoke_test()

    if RUN_REAL_BUILD:
        paths = build_esto_extended(BASE_ESTO_PATH, TEMPLATE_DIR, MAPPING_WORKBOOK_PATH, OUTPUT_DIR)
        print("ESTO Extended test outputs:")
        for label, path in paths.items():
            print(f"  {label}: {path}")

#%%
