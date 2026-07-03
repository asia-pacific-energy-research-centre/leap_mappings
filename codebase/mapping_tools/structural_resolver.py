#%%
"""Resolve mapping rollups and hierarchy only from explicit structural evidence."""

#%%
from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd


TREE_REQUIRED_COLUMNS = {"dataset", "axis", "code", "parent_code"}


def build_tree_index(
    tree_df: pd.DataFrame,
    dataset: str,
    axis: str,
) -> tuple[dict[str, str], pd.DataFrame]:
    """Return child-to-parent edges and QA issues for one explicit tree axis."""
    missing = TREE_REQUIRED_COLUMNS.difference(tree_df.columns)
    if missing:
        raise ValueError(f"Tree is missing required columns: {sorted(missing)}")
    selected = tree_df[
        tree_df["dataset"].astype(str).str.casefold().eq(dataset.casefold())
        & tree_df["axis"].astype(str).str.casefold().eq(axis.casefold())
    ].copy()
    selected["code"] = selected["code"].fillna("").astype(str).str.strip()
    selected["parent_code"] = selected["parent_code"].fillna("").astype(str).str.strip()

    issues: list[dict[str, str]] = []
    parent_sets = selected[selected["code"].ne("")].groupby("code")["parent_code"].agg(
        lambda values: sorted(set(values))
    )
    index: dict[str, str] = {}
    known = set(parent_sets.index)
    for code, parents in parent_sets.items():
        if len(parents) > 1:
            issues.append({"issue_type": "ambiguous_parent", "code": code, "related_code": "|".join(parents)})
            continue
        parent = parents[0]
        if parent and parent not in known:
            issues.append({"issue_type": "missing_parent", "code": code, "related_code": parent})
            continue
        index[code] = parent

    for start in sorted(index):
        seen: set[str] = set()
        current = start
        while current:
            if current in seen:
                issues.append({"issue_type": "cycle", "code": start, "related_code": current})
                break
            seen.add(current)
            current = index.get(current, "")
    issue_df = pd.DataFrame(issues, columns=["issue_type", "code", "related_code"]).drop_duplicates()
    return index, issue_df.reset_index(drop=True)


def resolve_ancestry(code: str, parent_index: dict[str, str]) -> dict[str, Any]:
    """Resolve an explicit ancestor chain, returning its tree evidence and status."""
    code = str(code).strip()
    if code not in parent_index:
        return {"status": "unresolved", "code": code, "ancestors": [], "evidence_type": "tree", "evidence": []}
    ancestors: list[str] = []
    evidence: list[dict[str, str]] = []
    seen = {code}
    current = code
    while parent := parent_index.get(current, ""):
        evidence.append({"child_code": current, "parent_code": parent})
        if parent in seen:
            return {"status": "cyclic", "code": code, "ancestors": ancestors, "evidence_type": "tree", "evidence": evidence}
        ancestors.append(parent)
        seen.add(parent)
        current = parent
    return {"status": "resolved", "code": code, "ancestors": ancestors, "evidence_type": "tree", "evidence": evidence}


def resolve_nearest_mapped_pair(
    flow: str,
    product: str,
    mapped_pairs: set[tuple[str, str]],
    roll_axis: str,
    parent_index: dict[str, str],
) -> dict[str, Any]:
    """Find the nearest mapped pair by walking explicit parents on one axis."""
    flow, product = str(flow).strip(), str(product).strip()
    pair = (flow, product)
    if pair in mapped_pairs:
        return {"status": "resolved", "flow": flow, "product": product, "evidence_type": "direct", "evidence": []}
    code = flow if roll_axis == "flow" else product
    ancestry = resolve_ancestry(code, parent_index)
    if ancestry["status"] != "resolved":
        return {**ancestry, "flow": flow, "product": product}
    for depth, ancestor in enumerate(ancestry["ancestors"], start=1):
        candidate = (ancestor, product) if roll_axis == "flow" else (flow, ancestor)
        if candidate in mapped_pairs:
            return {
                "status": "resolved", "flow": candidate[0], "product": candidate[1],
                "evidence_type": "tree", "evidence": ancestry["evidence"][:depth],
            }
    return {"status": "unresolved", "flow": flow, "product": product, "evidence_type": "tree", "evidence": ancestry["evidence"]}


def prepare_pair_rollup_rules(
    rules_df: pd.DataFrame,
    input_flow_column: str,
    input_product_column: str,
    rolled_flow_column: str,
    rolled_product_column: str,
    flow_parent_index: dict[str, str] | None = None,
    product_parent_index: dict[str, str] | None = None,
) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], pd.DataFrame]:
    """Build a pair-sensitive rule index and report duplicates/conflicts/cycles."""
    required = {input_flow_column, rolled_flow_column}
    missing = required.difference(rules_df.columns)
    if missing:
        raise ValueError(f"Rollup rules are missing required columns: {sorted(missing)}")
    rules = rules_df.copy()
    if "include" in rules:
        rules = rules[rules["include"].apply(lambda value: value is True or str(value).strip().casefold() in {"true", "1", "yes"})]
    for column in [input_flow_column, input_product_column, rolled_flow_column, rolled_product_column]:
        if column not in rules:
            rules[column] = ""
        rules[column] = rules[column].fillna("").astype(str).str.strip()
    rules = rules[rules[input_flow_column].ne("") & rules[rolled_flow_column].ne("")].copy()
    rules["rule_id"] = [f"rule_{number:06d}" for number in range(1, len(rules) + 1)]

    key_columns = [input_flow_column, input_product_column, rolled_flow_column, rolled_product_column]
    issues: list[dict[str, str]] = []
    for key, group in rules.groupby(key_columns, dropna=False, sort=True):
        if len(group) > 1:
            issues.append({"issue_type": "exact_duplicate_rule", "input_pair": f"{key[0]}|{key[1]}", "related_pairs": f"{key[2]}|{key[3]}"})
    rules = rules.drop_duplicates(key_columns, keep="first")

    index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rules.to_dict("records"):
        input_pair = (row[input_flow_column], row[input_product_column])
        output_pair = (row[rolled_flow_column], row[rolled_product_column] or row[input_product_column])
        record = {"rule_id": row["rule_id"], "input_pair": input_pair, "output_pair": output_pair, "evidence_type": "rollup_rule"}
        index[input_pair].append(record)
    def _is_ancestor(candidate: str, code: str, parents: dict[str, str]) -> bool:
        seen = {code}
        current = code
        while parent := parents.get(current, ""):
            if parent == candidate:
                return True
            if parent in seen:
                return False
            seen.add(parent)
            current = parent
        return False

    flow_parents = flow_parent_index or {}
    product_parents = product_parent_index or {}
    rule_graph: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for input_pair, assignments in index.items():
        outputs = sorted({item["output_pair"] for item in assignments})
        if len(outputs) > 1:
            nested = all(
                left == right
                or (
                    left[1] == right[1]
                    and (_is_ancestor(left[0], right[0], flow_parents) or _is_ancestor(right[0], left[0], flow_parents))
                )
                or (
                    left[0] == right[0]
                    and (_is_ancestor(left[1], right[1], product_parents) or _is_ancestor(right[1], left[1], product_parents))
                )
                for position, left in enumerate(outputs)
                for right in outputs[position + 1:]
            )
            if not nested:
                issues.append({"issue_type": "conflicting_assignment", "input_pair": "|".join(input_pair), "related_pairs": ";".join("|".join(pair) for pair in outputs)})
        rule_graph[input_pair].update(outputs)

    for start in sorted(rule_graph):
        stack = [(start, [start])]
        while stack:
            current, path = stack.pop()
            for target in rule_graph.get(current, set()):
                if target == start:
                    issues.append({"issue_type": "cycle", "input_pair": "|".join(start), "related_pairs": ";".join("|".join(pair) for pair in [*path, target])})
                    stack.clear()
                    break
                if target not in path:
                    stack.append((target, [*path, target]))
    return dict(index), pd.DataFrame(issues, columns=["issue_type", "input_pair", "related_pairs"])


def resolve_pair_rollups(
    flow: str,
    product: str,
    rule_index: dict[tuple[str, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    """Resolve exact-product rules first, then blank-product wildcard rules."""
    flow, product = str(flow).strip(), str(product).strip()
    assignments = rule_index.get((flow, product), []) or rule_index.get((flow, ""), [])
    if not assignments:
        return {"status": "unresolved", "input_pair": (flow, product), "resolutions": []}
    resolutions = []
    for assignment in assignments:
        output_flow, output_product = assignment["output_pair"]
        resolutions.append({**assignment, "output_pair": (output_flow, output_product or product)})
    return {"status": "resolved" if len(resolutions) == 1 else "ambiguous", "input_pair": (flow, product), "resolutions": resolutions}

#%%
