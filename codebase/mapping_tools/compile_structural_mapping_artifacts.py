#%%
"""Compile value-free Common ESTO mapping membership artifacts."""

#%%
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from codebase.mapping_tools.structural_resolver import prepare_pair_rollup_rules


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

STRUCTURAL_SCHEMA_VERSION = "common_esto_structural_v1"
DEFAULT_RELATIONSHIPS_PATH = REPO_ROOT / "results" / "mapping_relationships" / "energy_balance_relationships.csv"
DEFAULT_COMMON_MAP_PATH = REPO_ROOT / "results" / "common_esto" / "common_esto_rows.csv"
DEFAULT_WORKBOOK_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "results" / "common_esto" / "structural_artifacts"

SOURCE_COMPONENT_COLUMNS = [
    "structural_mapping_version", "comparison_scope", "source_system", "original_source_flow",
    "original_source_product", "effective_source_flow", "effective_source_product",
    "relationship_id", "rule_id", "rollup_context", "evidence_type", "component_esto_flow",
    "component_esto_product",
]
COMPONENT_COMMON_COLUMNS = [
    "structural_mapping_version", "comparison_scope", "component_esto_flow",
    "component_esto_product", "common_row_id", "component_sign", "common_flow_code",
    "common_flow_name", "common_flow_label", "common_product_code", "common_product_name",
    "common_product_label", "common_row_basis", "is_exact_row", "requires_rollup",
    "source_aggregate_labels", "source_aggregate_group_ids",
]
SOURCE_COMMON_COLUMNS = [
    *SOURCE_COMPONENT_COLUMNS, "common_row_id", "component_sign", "common_flow_code",
    "common_flow_name", "common_flow_label", "common_product_code", "common_product_name",
    "common_product_label", "common_row_basis", "is_exact_row", "requires_rollup",
    "source_aggregate_labels", "source_aggregate_group_ids",
]
REVERSE_COLUMNS = [
    "structural_mapping_version", "comparison_scope", "common_row_id", "source_system",
    "original_source_flow", "original_source_product", "effective_source_flow",
    "effective_source_product", "relationship_id", "rule_id", "rollup_context", "evidence_type",
    "component_esto_flow", "component_esto_product",
]


def _truthy(value: Any) -> bool:
    return value is True or str(value).strip().casefold() in {"true", "1", "yes"}


def _fingerprint(paths: list[Path]) -> str:
    """Hash structural input contents and names reproducibly."""
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.as_posix().casefold()):
        digest.update(path.name.encode("utf-8"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _stable(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Select a stable schema, remove duplicates, and sort deterministically."""
    result = df.copy()
    for column in columns:
        if column not in result:
            result[column] = ""
    result = result[columns].fillna("").drop_duplicates()
    return result.sort_values(columns, kind="stable", key=lambda series: series.astype(str)).reset_index(drop=True)


def _rule_columns(system: str) -> tuple[str, str, str, str]:
    if system == "LEAP":
        return (
            "input_leap_sector_name_full_path", "input_raw_leap_fuel_name",
            "rolled_leap_sector_name_full_path", "rolled_raw_leap_fuel_name",
        )
    if system == "NINTH":
        return "input_9th_sector", "input_9th_fuel", "rolled_9th_sector", "rolled_9th_fuel"
    return "input_esto_flow", "input_esto_product", "rolled_esto_flow", "rolled_esto_product"


def _compile_source_components(
    relationships_df: pd.DataFrame,
    rollup_rules: dict[str, pd.DataFrame],
    version: str,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    required = {
        "source_system", "source_flow", "source_product", "target_system", "target_flow",
        "target_product", "relationship_id", "include_in_use_case", "is_rollup_derived",
    }
    missing = required.difference(relationships_df.columns)
    if missing:
        raise ValueError(f"Relationships artifact is missing columns: {sorted(missing)}")
    active = relationships_df[
        relationships_df["include_in_use_case"].apply(_truthy)
        & relationships_df["target_system"].astype(str).str.upper().eq("ESTO")
        & ~relationships_df["is_rollup_derived"].apply(_truthy)
    ].copy()
    active = active[active["source_system"].astype(str).str.upper().isin(["LEAP", "NINTH"])]
    records: list[dict[str, Any]] = []
    for row in active.drop_duplicates([
        "source_system", "source_flow", "source_product", "target_flow", "target_product", "relationship_id"
    ]).to_dict("records"):
        records.append({
            "structural_mapping_version": version,
            "comparison_scope": "",
            "source_system": str(row["source_system"]).upper(),
            "original_source_flow": row["source_flow"], "original_source_product": row["source_product"],
            "effective_source_flow": row["source_flow"], "effective_source_product": row["source_product"],
            "relationship_id": row["relationship_id"], "rule_id": "", "rollup_context": "", "evidence_type": "direct_relationship",
            "component_esto_flow": row["target_flow"], "component_esto_product": row["target_product"],
        })

    qa: dict[str, pd.DataFrame] = {}
    for system in ["LEAP", "NINTH"]:
        rules = rollup_rules.get(system, pd.DataFrame())
        if rules.empty:
            continue
        columns = _rule_columns(system)
        context_groups = rules.groupby("rollup_context", dropna=False) if "rollup_context" in rules else [("", rules)]
        qa_frames: list[pd.DataFrame] = []
        system_base = [record for record in records if record["source_system"] == system and not record["rule_id"]]
        by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for record in system_base:
            by_pair.setdefault((str(record["original_source_flow"]), str(record["original_source_product"])), []).append(record)
        for context, context_rules in context_groups:
            context = "" if pd.isna(context) else str(context).strip()
            rule_index, issues = prepare_pair_rollup_rules(context_rules, *columns)
            if not issues.empty:
                qa_frames.append(issues.assign(rollup_context=context))
            for (input_flow, input_product), assignments in rule_index.items():
                candidate_pairs = [pair for pair in by_pair if pair[0] == input_flow and (not input_product or pair[1] == input_product)]
                for pair in candidate_pairs:
                    for base in by_pair[pair]:
                        for assignment in assignments:
                            rolled_flow, rolled_product = assignment["output_pair"]
                            records.append({
                                **base,
                                "effective_source_flow": rolled_flow,
                                "effective_source_product": rolled_product or pair[1],
                                "rule_id": f"{context}:{assignment['rule_id']}",
                                "rollup_context": context,
                                "evidence_type": "rollup_rule",
                            })
        qa[system] = pd.concat(qa_frames, ignore_index=True) if qa_frames else pd.DataFrame()

    return _stable(pd.DataFrame(records), SOURCE_COMPONENT_COLUMNS), qa


def compile_structural_frames(
    relationships_df: pd.DataFrame,
    common_map_df: pd.DataFrame,
    rollup_rules: dict[str, pd.DataFrame] | None = None,
    input_fingerprint: str = "in_memory",
) -> dict[str, pd.DataFrame]:
    """Compile deterministic structural tables without loading source values."""
    required_common = {
        "comparison_scope", "component_esto_flow", "component_esto_product",
        "common_row_id", "component_sign",
    }
    missing = required_common.difference(common_map_df.columns)
    if missing:
        raise ValueError(f"Common map artifact is missing columns: {sorted(missing)}")
    version = f"{STRUCTURAL_SCHEMA_VERSION}:{input_fingerprint[:16]}"
    source_components, rule_qa = _compile_source_components(relationships_df, rollup_rules or {}, version)
    components = common_map_df.copy()
    components.insert(0, "structural_mapping_version", version)
    components = _stable(components, COMPONENT_COMMON_COLUMNS)

    # ESTO is an identity source system over every component represented in the common map.
    esto = components[["structural_mapping_version", "component_esto_flow", "component_esto_product"]].drop_duplicates()
    esto["source_system"] = "ESTO"
    esto["original_source_flow"] = esto["component_esto_flow"]
    esto["original_source_product"] = esto["component_esto_product"]
    esto["effective_source_flow"] = esto["component_esto_flow"]
    esto["effective_source_product"] = esto["component_esto_product"]
    esto["relationship_id"] = esto.apply(
        lambda row: "esto_identity_" + hashlib.sha1(
            f"{row['component_esto_flow']}|{row['component_esto_product']}".encode("utf-8")
        ).hexdigest()[:16], axis=1,
    )
    esto["rule_id"] = ""
    esto["rollup_context"] = ""
    esto["evidence_type"] = "identity"
    source_components = _stable(pd.concat([source_components, esto], ignore_index=True), SOURCE_COMPONENT_COLUMNS)

    joined = source_components.merge(
        components,
        on=["structural_mapping_version", "component_esto_flow", "component_esto_product"],
        how="left", indicator=True,
    )
    unresolved = joined[joined["_merge"] == "left_only"].copy()
    unresolved["comparison_scope"] = unresolved["comparison_scope_x"]
    unresolved = unresolved[SOURCE_COMPONENT_COLUMNS]
    unresolved["issue_type"] = "component_missing_common_row"
    resolved = joined[joined["_merge"] == "both"].drop(columns="_merge")
    resolved["comparison_scope"] = resolved["comparison_scope_y"]
    resolved = resolved.drop(columns=["comparison_scope_x", "comparison_scope_y"])
    source_common = _stable(resolved, SOURCE_COMMON_COLUMNS)
    scoped_source_components = _stable(source_common, SOURCE_COMPONENT_COLUMNS)
    reverse = _stable(source_common, REVERSE_COLUMNS)

    ambiguous_components = components.groupby(
        ["comparison_scope", "component_esto_flow", "component_esto_product"], dropna=False
    )["common_row_id"].nunique().reset_index(name="common_row_count")
    ambiguous_components = ambiguous_components[ambiguous_components["common_row_count"] > 1]
    issue_frames = [frame.assign(source_system=system) for system, frame in rule_qa.items() if not frame.empty]
    issues = pd.concat(issue_frames, ignore_index=True) if issue_frames else pd.DataFrame(columns=["issue_type"])
    duplicate = issues[issues.get("issue_type", pd.Series(dtype=str)).eq("exact_duplicate_rule")]
    cyclic = issues[issues.get("issue_type", pd.Series(dtype=str)).eq("cycle")]
    conflicting = issues[issues.get("issue_type", pd.Series(dtype=str)).eq("conflicting_assignment")]
    ambiguous_rules = issues[issues.get("issue_type", pd.Series(dtype=str)).eq("ambiguous_assignment")]
    ambiguous = pd.concat([ambiguous_components, ambiguous_rules], ignore_index=True, sort=False)
    summary = pd.DataFrame([
        {"structural_mapping_version": version, "artifact": "source_pair_to_esto_component", "row_count": len(scoped_source_components)},
        {"structural_mapping_version": version, "artifact": "esto_component_to_common_row", "row_count": len(components)},
        {"structural_mapping_version": version, "artifact": "source_pair_to_common_row", "row_count": len(source_common)},
        {"structural_mapping_version": version, "artifact": "common_row_to_source_pairs", "row_count": len(reverse)},
    ])
    return {
        "source_pair_to_esto_component": scoped_source_components,
        "esto_component_to_common_row": components,
        "source_pair_to_common_row": source_common,
        "common_row_to_source_pairs": reverse,
        "structural_compilation_summary": summary,
        "qa_unresolved_structural": unresolved,
        "qa_ambiguous_structural": ambiguous,
        "qa_cyclic_structural": cyclic,
        "qa_duplicate_structural": duplicate,
        "qa_conflicting_structural": conflicting,
    }


def compile_structural_mapping_artifacts(
    relationships_path: Path = DEFAULT_RELATIONSHIPS_PATH,
    common_map_path: Path = DEFAULT_COMMON_MAP_PATH,
    workbook_path: Path = DEFAULT_WORKBOOK_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, pd.DataFrame]:
    """Read only structural inputs, compile artifacts, and write narrow CSVs."""
    paths = [Path(relationships_path), Path(common_map_path), Path(workbook_path)]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Structural compilation inputs do not exist: {missing}")
    fingerprint = _fingerprint(paths)
    relationships = pd.read_csv(relationships_path, dtype=object)
    common_map = pd.read_csv(common_map_path, dtype=object)
    rules = {
        "LEAP": pd.read_excel(workbook_path, sheet_name="leap_rollup_rules", dtype=object),
        "NINTH": pd.read_excel(workbook_path, sheet_name="ninth_rollup_rules", dtype=object),
    }
    artifacts = compile_structural_frames(relationships, common_map, rules, fingerprint)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in artifacts.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False)
    manifest = {
        "structural_schema_version": STRUCTURAL_SCHEMA_VERSION,
        "input_fingerprint": fingerprint,
        "inputs": [str(path.resolve()) for path in paths],
    }
    (output_dir / "structural_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return artifacts


# --- Notebook run block ---

RUN_STRUCTURAL_COMPILATION = False

if RUN_STRUCTURAL_COMPILATION:
    COMPILED_ARTIFACTS = compile_structural_mapping_artifacts()

#%%
