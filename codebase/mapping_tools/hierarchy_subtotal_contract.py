#%%
"""Build and strictly load the mappings-owned hierarchy/subtotal contract.

The core functions operate only on normalized adapter tables. Dataset parsing
belongs in adapter functions; structural classification and validation are
shared and never depend on observed values adding successfully.
"""

#%%
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

import pandas as pd


CONTRACT_NAME = "aperc_hierarchy_subtotal_contract"
SCHEMA_VERSION = "hierarchy_subtotal_contract_v1"
PAIR_RULE = "any(axis_node_is_structural_parent)"
RELATIONSHIP_TYPES = {
    "ordinary_hierarchy",
    "additive_synthetic_rollup",
    "exact_alias",
    "expanding_rollup",
    "non_expanding_replacement",
    "detached_diagnostic_boundary",
    "graph_generated_comparison_category",
    "unresolved",
}
CONFORMANCE_STATUSES = {
    "passed",
    "failed",
    "children_incomplete",
    "unavailable",
    "not_applicable",
    "unanchorable",
    "mapping_ambiguous",
    "intentionally_non_additive",
    "unresolved",
}

NODE_KEY = ["dataset_id", "axis_id", "node_id"]
EDGE_KEY = ["dataset_id", "axis_id", "parent_node_id", "child_node_id", "relationship_type"]
PAIR_KEY = ["dataset_id", "axis_1_node_id", "axis_2_node_id"]


def _text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _truthy(value: object) -> bool:
    return value is True or _text(value).casefold() in {"true", "1", "yes"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


def _producer_commit(repo_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


@dataclass(frozen=True)
class AdapterTables:
    """Normalized output supplied by one dataset adapter."""

    dataset_id: str
    source_version: str
    adapter_version: str
    dataset_kind: str
    nodes: pd.DataFrame
    edges: pd.DataFrame
    pairs: pd.DataFrame
    observations: pd.DataFrame
    provenance: dict[str, str]


class DatasetAdapter(Protocol):
    """Small adapter interface required by the contract builder."""

    dataset_id: str
    adapter_version: str

    def build(self) -> AdapterTables:
        """Return normalized node, edge, pair, and optional observation tables."""


@dataclass(frozen=True)
class CallableDatasetAdapter:
    """Explicit registry entry backed by a dataset-specific builder function."""

    dataset_id: str
    adapter_version: str
    builder: Callable[[], AdapterTables]

    def build(self) -> AdapterTables:
        tables = self.builder()
        if tables.dataset_id != self.dataset_id:
            raise ValueError(
                f"Adapter registry id {self.dataset_id!r} returned {tables.dataset_id!r}"
            )
        return tables


def empty_observations() -> pd.DataFrame:
    """Return the normalized optional-observation schema."""
    return pd.DataFrame(columns=[
        "dataset_id",
        "source_version",
        "economy",
        "scenario",
        "year_or_period",
        "axis_1_node_id",
        "axis_2_node_id",
        "value",
        "source_row_id",
        "provenance",
    ])


def normalize_adapter_tables(tables: AdapterTables) -> AdapterTables:
    """Validate one adapter and derive structural node fields from ordinary edges."""
    nodes = tables.nodes.copy()
    edges = tables.edges.copy()
    pairs = tables.pairs.copy()
    observations = tables.observations.copy()

    required_nodes = {
        "dataset_id",
        "axis_id",
        "node_id",
        "node_label",
        "depth",
        "hierarchy_status",
        "source_subtotal_layout",
        "source_subtotal_results",
        "source_subtotal_other",
        "classification_rule",
        "evidence",
        "provenance",
    }
    required_edges = {
        "dataset_id",
        "axis_id",
        "parent_node_id",
        "child_node_id",
        "relationship_type",
        "direction",
        "is_additive",
        "source_rule_id",
        "review_status",
        "provenance",
    }
    required_pairs = {
        "dataset_id",
        "axis_1_id",
        "axis_1_node_id",
        "axis_2_id",
        "axis_2_node_id",
        "pair_provenance",
    }
    for label, frame, required in [
        ("nodes", nodes, required_nodes),
        ("edges", edges, required_edges),
        ("pairs", pairs, required_pairs),
    ]:
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(
                f"{tables.dataset_id} adapter {label} missing columns: {sorted(missing)}"
            )

    if set(nodes["dataset_id"].dropna().astype(str)) != {tables.dataset_id}:
        raise ValueError(f"{tables.dataset_id} adapter emitted another dataset_id")
    if nodes.duplicated(NODE_KEY).any():
        duplicates = nodes.loc[nodes.duplicated(NODE_KEY, keep=False), NODE_KEY]
        raise ValueError(f"Duplicate node keys: {duplicates.to_dict('records')[:5]}")
    if edges.duplicated(EDGE_KEY).any():
        raise ValueError(f"{tables.dataset_id} adapter emitted duplicate edge keys")
    if not set(edges["relationship_type"].astype(str)).issubset(RELATIONSHIP_TYPES):
        invalid = sorted(set(edges["relationship_type"].astype(str)) - RELATIONSHIP_TYPES)
        raise ValueError(f"Unknown relationship types: {invalid}")
    if (edges["parent_node_id"].astype(str) == edges["child_node_id"].astype(str)).any():
        raise ValueError(f"{tables.dataset_id} adapter emitted a self-parent edge")

    ordinary = edges[edges["relationship_type"].eq("ordinary_hierarchy")].copy()
    node_keys = set(map(tuple, nodes[NODE_KEY].astype(str).to_numpy()))
    for side in ["parent_node_id", "child_node_id"]:
        edge_keys = set(
            map(
                tuple,
                ordinary[["dataset_id", "axis_id", side]]
                .rename(columns={side: "node_id"})
                .astype(str)
                .to_numpy(),
            )
        )
        missing_keys = sorted(edge_keys - node_keys)
        if missing_keys:
            raise ValueError(f"Ordinary edges reference missing {side}: {missing_keys[:5]}")

    parent_counts = (
        ordinary.groupby(["dataset_id", "axis_id", "parent_node_id"])
        .size()
        .rename("child_count")
        .reset_index()
        .rename(columns={"parent_node_id": "node_id"})
    )
    parent_assignments = (
        ordinary.groupby(["dataset_id", "axis_id", "child_node_id"])["parent_node_id"]
        .agg(lambda values: sorted(set(map(str, values))))
        .reset_index()
        .rename(columns={"child_node_id": "node_id"})
    )
    contradictory = parent_assignments[parent_assignments["parent_node_id"].map(len) > 1]
    if not contradictory.empty:
        raise ValueError(
            "Contradictory ordinary parent assignments: "
            f"{contradictory.to_dict('records')[:5]}"
        )
    parent_assignments["parent_node_id"] = parent_assignments["parent_node_id"].map(
        lambda values: values[0] if values else ""
    )

    nodes = nodes.drop(
        columns=[
            "parent_node_id",
            "child_count",
            "is_leaf",
            "is_structural_parent",
        ],
        errors="ignore",
    )
    nodes = nodes.merge(parent_assignments, on=NODE_KEY, how="left")
    nodes = nodes.merge(parent_counts, on=NODE_KEY, how="left")
    nodes["parent_node_id"] = nodes["parent_node_id"].fillna("")
    nodes["child_count"] = nodes["child_count"].fillna(0).astype(int)
    nodes["is_structural_parent"] = nodes["child_count"].gt(0)
    nodes["is_leaf"] = ~nodes["is_structural_parent"]

    # Directed-cycle check over ordinary hierarchy edges.
    parent_by_child = {
        (row.dataset_id, row.axis_id, row.child_node_id): row.parent_node_id
        for row in ordinary.itertuples(index=False)
    }
    for key in parent_by_child:
        seen: set[tuple[str, str, str]] = set()
        cursor = key
        while cursor in parent_by_child:
            if cursor in seen:
                raise ValueError(f"Ordinary hierarchy cycle detected at {cursor}")
            seen.add(cursor)
            cursor = (cursor[0], cursor[1], parent_by_child[cursor])

    nodes = nodes.sort_values(NODE_KEY, kind="stable").reset_index(drop=True)
    edges = edges.sort_values(EDGE_KEY, kind="stable").reset_index(drop=True)
    pairs = pairs.drop_duplicates().sort_values(
        ["dataset_id", "axis_1_id", "axis_1_node_id", "axis_2_id", "axis_2_node_id"],
        kind="stable",
    ).reset_index(drop=True)
    return AdapterTables(
        dataset_id=tables.dataset_id,
        source_version=tables.source_version,
        adapter_version=tables.adapter_version,
        dataset_kind=tables.dataset_kind,
        nodes=nodes,
        edges=edges,
        pairs=pairs,
        observations=observations,
        provenance=tables.provenance,
    )


def classify_pairs(
    nodes: pd.DataFrame,
    pairs: pd.DataFrame,
    edges: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Classify structural subtotals and separate output rollup treatment."""
    lookup = nodes.set_index(NODE_KEY)["is_structural_parent"].to_dict()
    hierarchy_lookup = nodes.set_index(NODE_KEY)["hierarchy_status"].to_dict()
    result = pairs.copy()
    for ordinal in [1, 2]:
        keys = list(
            zip(
                result["dataset_id"].astype(str),
                result[f"axis_{ordinal}_id"].astype(str),
                result[f"axis_{ordinal}_node_id"].astype(str),
            )
        )
        result[f"axis_{ordinal}_is_structural_parent"] = [
            lookup.get(key) if key in lookup else pd.NA for key in keys
        ]
        result[f"axis_{ordinal}_hierarchy_status"] = [
            hierarchy_lookup.get(key, "unresolved") for key in keys
        ]
        result[f"axis_{ordinal}_resolved"] = [key in lookup for key in keys]
    result["every_node_resolved"] = (
        result["axis_1_resolved"] & result["axis_2_resolved"]
    )
    result["pair_is_subtotal"] = (
        result["axis_1_is_structural_parent"].fillna(False).astype(bool)
        | result["axis_2_is_structural_parent"].fillna(False).astype(bool)
    )
    result["classification_rule"] = PAIR_RULE
    result["source_signal_disagreement"] = False
    synthetic_by_node: dict[tuple[str, str, str], str] = {}
    if edges is not None and not edges.empty:
        synthetic_edges = edges[
            ~edges["relationship_type"].eq("ordinary_hierarchy")
            & ~edges["relationship_type"].eq("unresolved")
        ]
        grouped = synthetic_edges.groupby(
            ["dataset_id", "axis_id", "parent_node_id"],
            dropna=False,
        )["relationship_type"].agg(
            lambda values: ";".join(sorted(set(map(str, values))))
        )
        synthetic_by_node = grouped.to_dict()
    synthetic_statuses: list[str] = []
    declared_output_subtotals: list[bool] = []
    subtotal_relationships = {
        "additive_synthetic_rollup",
        "expanding_rollup",
        "non_expanding_replacement",
        "detached_diagnostic_boundary",
    }
    for row in result.itertuples(index=False):
        statuses = []
        for ordinal in [1, 2]:
            key = (
                str(row.dataset_id),
                str(getattr(row, f"axis_{ordinal}_id")),
                str(getattr(row, f"axis_{ordinal}_node_id")),
            )
            status = synthetic_by_node.get(key, "")
            if status:
                statuses.extend(status.split(";"))
        unique_statuses = sorted(set(statuses))
        synthetic_statuses.append(
            ";".join(unique_statuses) if unique_statuses else "ordinary"
        )
        declared_output_subtotals.append(
            bool(row.pair_is_subtotal)
            or bool(subtotal_relationships.intersection(unique_statuses))
        )
    result["synthetic_status"] = synthetic_statuses
    result["declared_output_subtotal"] = declared_output_subtotals
    result["review_state"] = result["every_node_resolved"].map(
        {True: "resolved", False: "review_required"}
    )
    return result.sort_values(PAIR_KEY, kind="stable").reset_index(drop=True)


def validate_value_conformance(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    observations: pd.DataFrame,
    tolerance: float = 0.01,
) -> pd.DataFrame:
    """Test immediate-child additivity without changing structural classification."""
    columns = [
        "dataset_id",
        "source_version",
        "economy",
        "scenario",
        "year_or_period",
        "validation_axis",
        "parent_node_id",
        "fixed_opposite_axis_node_id",
        "parent_value",
        "child_sum",
        "signed_difference",
        "absolute_difference",
        "positive_child_sum",
        "negative_child_sum",
        "expected_child_count",
        "observed_child_count",
        "missing_child_count",
        "mapped_child_count",
        "tolerance",
        "status",
        "reason",
        "inherited_source_inconsistency",
        "exception_status",
        "exception_reason",
        "provenance",
    ]
    if observations.empty:
        return pd.DataFrame(columns=columns)

    ordinary = edges[edges["relationship_type"].eq("ordinary_hierarchy")]
    source_versions = (
        observations[["dataset_id", "source_version"]]
        .drop_duplicates("dataset_id")
        .set_index("dataset_id")["source_version"]
        .to_dict()
    )
    records: list[dict[str, object]] = []
    context_columns = ["dataset_id", "economy", "scenario", "year_or_period"]
    for edge_group in ordinary.groupby(["dataset_id", "axis_id", "parent_node_id"]):
        dataset_id, axis_id, parent_node_id = edge_group[0]
        children = set(edge_group[1]["child_node_id"].astype(str))
        opposite_axis = "axis_2_node_id" if axis_id == "axis_1" else "axis_1_node_id"
        validation_axis_node = "axis_1_node_id" if axis_id == "axis_1" else "axis_2_node_id"
        relevant = observations[
            observations["dataset_id"].astype(str).eq(str(dataset_id))
            & observations[validation_axis_node].astype(str).isin(children | {str(parent_node_id)})
        ].copy()
        for context, group in relevant.groupby(context_columns + [opposite_axis], dropna=False):
            values = (
                group.groupby(validation_axis_node, dropna=False)["value"]
                .sum(min_count=1)
                .to_dict()
            )
            parent_value = values.get(parent_node_id)
            observed_children = children.intersection(map(str, values))
            missing_children = children - observed_children
            child_values = [values[child] for child in observed_children]
            if parent_value is None:
                status, reason = "unavailable", "parent_value_unavailable"
            elif missing_children:
                status, reason = "children_incomplete", "declared_children_missing"
            elif not child_values:
                status, reason = "unavailable", "child_values_unavailable"
            else:
                difference = float(parent_value) - float(sum(child_values))
                status = "passed" if abs(difference) <= tolerance else "failed"
                reason = (
                    "within_tolerance"
                    if status == "passed"
                    else "difference_exceeds_tolerance"
                )
            child_sum = sum(child_values) if child_values else pd.NA
            signed_difference = (
                float(parent_value) - float(child_sum)
                if parent_value is not None and not pd.isna(child_sum)
                else pd.NA
            )
            records.append({
                "dataset_id": dataset_id,
                "source_version": source_versions.get(dataset_id, ""),
                "economy": context[1],
                "scenario": context[2],
                "year_or_period": context[3],
                "validation_axis": axis_id,
                "parent_node_id": parent_node_id,
                "fixed_opposite_axis_node_id": context[4],
                "parent_value": parent_value if parent_value is not None else pd.NA,
                "child_sum": child_sum,
                "signed_difference": signed_difference,
                "absolute_difference": (
                    abs(signed_difference) if not pd.isna(signed_difference) else pd.NA
                ),
                "positive_child_sum": sum(value for value in child_values if value > 0),
                "negative_child_sum": sum(value for value in child_values if value < 0),
                "expected_child_count": len(children),
                "observed_child_count": len(observed_children),
                "missing_child_count": len(missing_children),
                "mapped_child_count": len(observed_children),
                "tolerance": tolerance,
                "status": status,
                "reason": reason,
                "inherited_source_inconsistency": status == "failed",
                "exception_status": "",
                "exception_reason": "",
                "provenance": ";".join(sorted(set(group["provenance"].astype(str)))),
            })
    result = pd.DataFrame(records, columns=columns)
    if not set(result["status"].dropna().astype(str)).issubset(CONFORMANCE_STATUSES):
        raise ValueError("Unexpected value-conformance status")
    return result.sort_values(
        ["dataset_id", "validation_axis", "parent_node_id", "economy", "scenario", "year_or_period"],
        kind="stable",
    ).reset_index(drop=True)


def build_contract_frames(
    adapters: list[DatasetAdapter],
    tolerance: float = 0.01,
) -> tuple[dict[str, pd.DataFrame], list[dict[str, object]]]:
    """Build canonical frames from a registry of adapters."""
    normalized = [normalize_adapter_tables(adapter.build()) for adapter in adapters]
    nodes = pd.concat([tables.nodes for tables in normalized], ignore_index=True)
    edges = pd.concat([tables.edges for tables in normalized], ignore_index=True)
    pairs = pd.concat([tables.pairs for tables in normalized], ignore_index=True)
    observations = pd.concat(
        [tables.observations for tables in normalized],
        ignore_index=True,
    )
    canonical_pairs = classify_pairs(nodes, pairs, edges)
    diagnostics = validate_value_conformance(nodes, edges, observations, tolerance)
    datasets = pd.DataFrame([
        {
            "dataset_id": tables.dataset_id,
            "source_version": tables.source_version,
            "adapter_version": tables.adapter_version,
            "dataset_kind": tables.dataset_kind,
            "provenance": json.dumps(tables.provenance, sort_keys=True),
        }
        for tables in normalized
    ]).sort_values("dataset_id", kind="stable").reset_index(drop=True)
    registry = [
        {
            "dataset_id": tables.dataset_id,
            "source_version": tables.source_version,
            "adapter_version": tables.adapter_version,
            "dataset_kind": tables.dataset_kind,
        }
        for tables in normalized
    ]
    frames = {
        "datasets": datasets,
        "axis_nodes": nodes.sort_values(NODE_KEY, kind="stable").reset_index(drop=True),
        "declared_relationship_edges": edges.sort_values(EDGE_KEY, kind="stable").reset_index(drop=True),
        "canonical_source_pairs": canonical_pairs,
        "value_conformance_diagnostics": diagnostics,
    }
    return frames, registry


def write_contract(
    output_dir: Path,
    frames: dict[str, pd.DataFrame],
    registry: list[dict[str, object]],
    input_paths: list[Path],
    repo_root: Path,
    compatibility: dict[str, str] | None = None,
    generation_time: datetime | None = None,
) -> dict[str, object]:
    """Write deterministic members and a hash-validating manifest."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    members: dict[str, dict[str, object]] = {}
    member_payloads: dict[str, bytes] = {}
    for name, frame in sorted(frames.items()):
        payload = _stable_csv_bytes(frame)
        member_payloads[name] = payload
        members[name] = {
            "path": f"{name}.csv",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "row_count": len(frame),
            "key_columns": {
                "axis_nodes": NODE_KEY,
                "declared_relationship_edges": EDGE_KEY,
                "canonical_source_pairs": PAIR_KEY,
            }.get(name, []),
        }
    input_records = []
    for path in sorted(map(Path, input_paths), key=lambda item: str(item).casefold()):
        input_records.append({
            "path": str(path.resolve()),
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        })
    build_basis = {
        "contract_name": CONTRACT_NAME,
        "schema_version": SCHEMA_VERSION,
        "producer_commit": _producer_commit(repo_root),
        "inputs": input_records,
        "adapters": registry,
        "members": members,
        "compatibility": compatibility or {},
    }
    build_id = hashlib.sha256(
        json.dumps(build_basis, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    manifest = {
        **build_basis,
        "build_id": build_id,
        "generation_time_utc": (
            generation_time or datetime.now(timezone.utc)
        ).isoformat(),
        "validation_result": "passed",
        "failure_reason": "",
    }
    for name, payload in member_payloads.items():
        (output_dir / f"{name}.csv").write_bytes(payload)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_contract(
    contract_dir: Path,
    expected_build_id: str | None = None,
    expected_input_hashes: dict[str, str] | None = None,
) -> tuple[dict[str, object], dict[str, pd.DataFrame]]:
    """Strictly load one selected build; never fall back to another directory."""
    contract_dir = Path(contract_dir)
    manifest_path = contract_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Selected hierarchy contract is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("contract_name") != CONTRACT_NAME:
        raise ValueError("Selected hierarchy contract has the wrong contract name")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Selected hierarchy contract has an incompatible schema version")
    if manifest.get("validation_result") != "passed":
        raise ValueError(
            "Selected hierarchy contract is invalid: "
            f"{manifest.get('failure_reason', 'unspecified failure')}"
        )
    if expected_build_id and manifest.get("build_id") != expected_build_id:
        raise ValueError("Selected hierarchy contract build_id does not match")
    actual_inputs = {
        Path(item["path"]).name: item["sha256"] for item in manifest.get("inputs", [])
    }
    for name, expected_hash in (expected_input_hashes or {}).items():
        if actual_inputs.get(name) != expected_hash:
            raise ValueError(f"Selected hierarchy contract input hash mismatch for {name}")

    frames: dict[str, pd.DataFrame] = {}
    for name, metadata in manifest.get("members", {}).items():
        member_path = contract_dir / metadata["path"]
        if not member_path.exists():
            raise FileNotFoundError(f"Hierarchy contract member is missing: {member_path}")
        payload = member_path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != metadata["sha256"]:
            raise ValueError(f"Hierarchy contract member hash mismatch: {name}")
        frame = pd.read_csv(member_path, dtype=object)
        if len(frame) != int(metadata["row_count"]):
            raise ValueError(f"Hierarchy contract member row count mismatch: {name}")
        key_columns = metadata.get("key_columns", [])
        if key_columns and frame.duplicated(key_columns).any():
            raise ValueError(f"Hierarchy contract member has duplicate keys: {name}")
        frames[name] = frame
    return manifest, frames


#%%
