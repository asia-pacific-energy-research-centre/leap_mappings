#%%
"""Build a non-destructive ESTO Extended prototype.

The prototype copies a base ESTO CSV, inventories LEAP export-template branch
paths, records unmapped template branches, and applies declarative hierarchy
extension rules.  The first rule reproduces the existing 16.01.99 pattern:
parent minus known children.  Generated rows carry provenance columns so this
can become a reviewed production workflow later.
"""

#%%
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

#%%
REPO_ROOT = Path(__file__).resolve().parents[2]
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
]

# This is deliberately declarative.  Future extension rules should be added
# here or moved to a reviewed config table rather than copied into the logic.
EXTENSION_RULES = [
    {
        "rule_id": "commercial_services_residual",
        "rule_type": "parent_minus_children",
        "parent_flow": "16.01 Commercial and public services",
        "excluded_child_flows": ["16.01.01 Datacentres"],
        "generated_flow": "16.01.99 Commercial and public services unallocated",
        "description": "Parent flow minus known detailed child flows.",
    },
]


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

    generated_frames: list[pd.DataFrame] = []
    rule_summaries: list[pd.DataFrame] = []
    for rule in EXTENSION_RULES:
        if rule["rule_type"] != "parent_minus_children":
            raise ValueError(f"Unsupported extension rule type: {rule['rule_type']}")
        generated, summary = apply_parent_minus_children_rule(esto, rule, rule_source_paths)
        generated_frames.append(generated)
        rule_summaries.append(summary)

    generated = pd.concat(generated_frames, ignore_index=True) if generated_frames else pd.DataFrame(columns=esto.columns)
    extended = pd.concat([esto, generated], ignore_index=True)
    key_columns = ["economy", "flows", "products"]
    duplicate_keys = extended.duplicated(key_columns, keep=False)
    if duplicate_keys.any():
        raise ValueError(f"ESTO Extended contains duplicate keys: {int(duplicate_keys.sum())}")

    output_paths = {
        "dataset": output_dir / "esto_extended_test.csv",
        "branch_inventory": output_dir / "leap_template_branch_inventory.csv",
        "unmapped_candidates": output_dir / "unmapped_leap_branch_candidates.csv",
        "generated_rows": output_dir / "esto_extended_generated_rows.csv",
        "rule_summary": output_dir / "esto_extended_rule_summary.csv",
        "extension_registry": output_dir / "esto_extended_extension_registry.csv",
    }
    extended.to_csv(output_paths["dataset"], index=False)
    inventory.to_csv(output_paths["branch_inventory"], index=False)
    candidates.to_csv(output_paths["unmapped_candidates"], index=False)
    generated.to_csv(output_paths["generated_rows"], index=False)
    pd.concat(rule_summaries, ignore_index=True).to_csv(output_paths["rule_summary"], index=False)
    registry = pd.DataFrame(
        [
            {
                "extension_id": rule["rule_id"],
                "parent_flow": rule["parent_flow"],
                "generated_flow": rule["generated_flow"],
                "generated_code": _esto_code(rule["generated_flow"]),
                "generated_label": _normalise_text(rule["generated_flow"]),
                "naming_method": "configured_parent_code_plus_residual_suffix",
                "value_method": rule["rule_type"],
                "source_leap_paths": rule_source_paths,
                "review_status": "prototype_only",
            }
            for rule in EXTENSION_RULES
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
    generated, _ = apply_parent_minus_children_rule(sample, EXTENSION_RULES[0])
    assert len(generated) == 1
    assert generated.iloc[0]["flows"] == EXTENSION_RULES[0]["generated_flow"]
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
