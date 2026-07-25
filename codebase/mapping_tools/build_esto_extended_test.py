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

    inventory = read_leap_template_branch_inventory(template_dir)
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

    extended = pd.concat([esto, all_generated], ignore_index=True)
    key_columns = ["economy", "flows", "products"]
    duplicate_keys = extended.duplicated(key_columns, keep=False)
    if duplicate_keys.any():
        raise ValueError(f"ESTO Extended contains duplicate keys: {int(duplicate_keys.sum())}")

    output_paths = {
        "dataset": output_dir / "esto_extended_test.csv",
        "branch_inventory": output_dir / "leap_template_branch_inventory.csv",
        "unmapped_candidates": output_dir / "unmapped_leap_branch_candidates.csv",
        "generated_rows": output_dir / "esto_extended_generated_rows.csv",
        "rollup_catalogue": output_dir / "esto_extended_rollup_catalogue.csv",
        "rollup_rows": output_dir / "esto_extended_rollup_rows.csv",
        "rollup_lineage": output_dir / "esto_extended_rollup_lineage.csv",
        "rollup_tree_edges": output_dir / "esto_extended_rollup_tree_edges.csv",
        "rule_summary": output_dir / "esto_extended_rule_summary.csv",
        "extension_registry": output_dir / "esto_extended_extension_registry.csv",
        "extension_candidates": output_dir / "esto_extended_extension_candidates.csv",
        "extension_candidate_sets": output_dir / "esto_extended_extension_candidate_sets.csv",
        "leap_parent_candidate_sets": output_dir / "esto_extended_leap_parent_candidate_sets.csv",
        "lng_split_audit": output_dir / "esto_extended_lng_split_audit.csv",
    }
    extended.to_csv(output_paths["dataset"], index=False)
    inventory.to_csv(output_paths["branch_inventory"], index=False)
    candidates.to_csv(output_paths["unmapped_candidates"], index=False)
    all_generated.to_csv(output_paths["generated_rows"], index=False)
    rollup_catalogue.to_csv(output_paths["rollup_catalogue"], index=False)
    rollup_generated.to_csv(output_paths["rollup_rows"], index=False)
    rollup_audit.to_csv(output_paths["rollup_lineage"], index=False)
    build_rollup_tree_edges(rollup_catalogue).to_csv(output_paths["rollup_tree_edges"], index=False)
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
