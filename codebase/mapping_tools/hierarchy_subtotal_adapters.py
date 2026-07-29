#%%
"""Dataset adapters for the canonical hierarchy/subtotal contract."""

#%%
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from codebase.mapping_tools.build_dataset_tree_structure import (
    build_common_esto_hierarchy_edges,
    build_common_esto_tree,
    build_esto_tree,
    build_ninth_tree,
)
from codebase.mapping_tools.hierarchy_subtotal_contract import (
    AdapterTables,
    CallableDatasetAdapter,
    classify_pairs,
    empty_observations,
    normalize_adapter_tables,
)
from codebase.mapping_tools.dataset_registry import load_dataset_registry


ADAPTER_VERSION = "1.0.0"
MAPPING_SHEETS = [
    "leap_combined_esto",
    "ninth_pairs_to_esto_pairs",
    "leap_combined_ninth",
]


def _text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _truthy(value: object) -> bool:
    return value is True or _text(value).casefold() in {"true", "1", "yes"}


def _source_version(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"{path.name}:{digest[:16]}"


def _active(frame: pd.DataFrame) -> pd.DataFrame:
    if "duplicate_to_remove" not in frame:
        return frame.copy()
    return frame[~frame["duplicate_to_remove"].map(_truthy)].copy()


def _node_rows_from_tree(
    tree: pd.DataFrame,
    dataset_id: str,
    axis_map: dict[str, tuple[str, str]],
    hierarchy_status: str,
    provenance: str,
    signal_lookup: dict[tuple[str, str], dict[str, bool]] | None = None,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for row in tree.to_dict("records"):
        raw_axis = _text(row.get("axis"))
        if raw_axis not in axis_map:
            continue
        axis_id, axis_role = axis_map[raw_axis]
        node_id = _text(row.get("code"))
        signals = (signal_lookup or {}).get((axis_id, node_id), {})
        records.append({
            "dataset_id": dataset_id,
            "axis_id": axis_id,
            "axis_role": axis_role,
            "node_id": node_id,
            "node_label": _text(row.get("label")) or node_id,
            "depth": int(pd.to_numeric(row.get("level"), errors="coerce") or 0),
            "display_parent_node_id": _text(row.get("parent_code")),
            "hierarchy_status": hierarchy_status,
            "source_subtotal_layout": signals.get("layout", pd.NA),
            "source_subtotal_results": signals.get("results", pd.NA),
            "source_subtotal_other": signals.get("other", row.get("is_subtotal", pd.NA)),
            "classification_rule": "declared ordinary child_count > 0",
            "evidence": f"tree code={node_id}",
            "provenance": provenance,
        })
    return pd.DataFrame(records)


def _ordinary_edges_from_tree(
    tree: pd.DataFrame,
    dataset_id: str,
    axis_map: dict[str, tuple[str, str]],
    provenance: str,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for row in tree.to_dict("records"):
        raw_axis = _text(row.get("axis"))
        parent = _text(row.get("parent_code"))
        child = _text(row.get("code"))
        if raw_axis not in axis_map or not parent or not child:
            continue
        axis_id = axis_map[raw_axis][0]
        records.append({
            "dataset_id": dataset_id,
            "axis_id": axis_id,
            "parent_node_id": parent,
            "child_node_id": child,
            "relationship_type": "ordinary_hierarchy",
            "direction": "parent_to_child",
            "is_additive": True,
            "source_rule_id": "",
            "review_status": "declared",
            "provenance": provenance,
        })
    return pd.DataFrame(records)


def _pair_frame(
    dataset_id: str,
    pairs: set[tuple[str, str]],
    provenance: str,
) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "dataset_id": dataset_id,
            "axis_1_id": "axis_1",
            "axis_1_node_id": axis_1,
            "axis_2_id": "axis_2",
            "axis_2_node_id": axis_2,
            "pair_provenance": provenance,
        }
        for axis_1, axis_2 in sorted(pairs)
        if axis_1 and axis_2
    ], columns=[
        "dataset_id",
        "axis_1_id",
        "axis_1_node_id",
        "axis_2_id",
        "axis_2_node_id",
        "pair_provenance",
    ])


def _canonicalize_pairs_against_nodes(
    pairs: set[tuple[str, str]],
    nodes: pd.DataFrame,
) -> set[tuple[str, str]]:
    """Resolve mapping-facing labels to unique normalized node identifiers."""
    resolved: set[tuple[str, str]] = set()
    axis_lookups: dict[str, dict[str, str]] = {}
    for axis_id in ["axis_1", "axis_2"]:
        axis_nodes = nodes[nodes["axis_id"].eq(axis_id)]
        exact = {value: value for value in axis_nodes["node_id"].astype(str)}
        labels = (
            axis_nodes.groupby(axis_nodes["node_label"].astype(str))["node_id"]
            .agg(lambda values: sorted(set(map(str, values))))
        )
        unique_labels = {
            label: values[0] for label, values in labels.items() if len(values) == 1
        }
        axis_lookups[axis_id] = {**unique_labels, **exact}
    for axis_1, axis_2 in pairs:
        resolved.add((
            axis_lookups["axis_1"].get(axis_1, axis_1),
            axis_lookups["axis_2"].get(axis_2, axis_2),
        ))
    return resolved


def _mapping_pairs(workbook_path: Path) -> dict[str, set[tuple[str, str]]]:
    frames = {
        sheet: _active(pd.read_excel(workbook_path, sheet_name=sheet, dtype=object))
        for sheet in MAPPING_SHEETS
    }
    pairs: dict[str, set[tuple[str, str]]] = {
        "leap": set(),
        "ninth": set(),
        "esto": set(),
        "esto_extended": set(),
    }
    for sheet in ["leap_combined_esto", "leap_combined_ninth"]:
        frame = frames[sheet]
        pairs["leap"].update(
            (_text(row["leap_sector_name_full_path"]), _text(row["raw_leap_fuel_name"]))
            for _, row in frame.iterrows()
        )
    for sheet in ["ninth_pairs_to_esto_pairs", "leap_combined_ninth"]:
        frame = frames[sheet]
        pairs["ninth"].update(
            (_text(row["ninth_sector"]), _text(row["ninth_fuel"]))
            for _, row in frame.iterrows()
        )
    for sheet in ["leap_combined_esto", "ninth_pairs_to_esto_pairs"]:
        for _, row in frames[sheet].iterrows():
            scope = _text(row.get("esto_dataset_scope")).casefold()
            target = "esto_extended" if "extended" in scope else "esto"
            pairs[target].add((_text(row["esto_flow"]), _text(row["esto_product"])))
    return pairs


def _ninth_signal_lookup(data: pd.DataFrame) -> dict[tuple[str, str], dict[str, bool]]:
    lookup: dict[tuple[str, str], dict[str, bool]] = {}
    sector_columns = [
        "sectors",
        "sub1sectors",
        "sub2sectors",
        "sub3sectors",
        "sub4sectors",
    ]
    evidence_columns = [
        *sector_columns,
        "fuels",
        "subfuels",
        "subtotal_layout",
        "subtotal_results",
    ]
    evidence_rows = data[evidence_columns].drop_duplicates()
    for row in evidence_rows.to_dict("records"):
        segments = []
        for column in sector_columns:
            value = _text(row.get(column))
            if not value or value == "x":
                break
            segments.append(value)
        if segments:
            key = ("axis_1", "/".join(segments))
            evidence = lookup.setdefault(key, {"layout": False, "results": False})
            evidence["layout"] |= _truthy(row.get("subtotal_layout"))
            evidence["results"] |= _truthy(row.get("subtotal_results"))
        fuel = _text(row.get("fuels"))
        subfuel = _text(row.get("subfuels"))
        fuel_id = f"{fuel}/{subfuel}" if subfuel and subfuel != "x" else fuel
        if fuel_id:
            key = ("axis_2", fuel_id)
            evidence = lookup.setdefault(key, {"layout": False, "results": False})
            evidence["layout"] |= _truthy(row.get("subtotal_layout"))
            evidence["results"] |= _truthy(row.get("subtotal_results"))
    return lookup


def build_ninth_adapter(
    data_path: Path,
    workbook_path: Path,
    data_df: pd.DataFrame | None = None,
) -> AdapterTables:
    """Build Ninth hierarchy from every declared sector/fuel hierarchy column."""
    data = data_df.copy() if data_df is not None else pd.read_csv(data_path, dtype=object)
    tree = build_ninth_tree(data_csv_path=data_path, data_df=data)
    provenance = f"{Path(data_path).resolve()} hierarchy columns"
    axis_map = {"sector": ("axis_1", "sector"), "fuel": ("axis_2", "fuel")}
    nodes = _node_rows_from_tree(
        tree,
        "ninth",
        axis_map,
        "complete_declared_schema",
        provenance,
        _ninth_signal_lookup(data),
    )
    edges = _ordinary_edges_from_tree(tree, "ninth", axis_map, provenance)
    mapping_pairs = _canonicalize_pairs_against_nodes(
        _mapping_pairs(workbook_path)["ninth"],
        nodes,
    )
    pairs = _pair_frame("ninth", mapping_pairs, str(workbook_path))
    return AdapterTables(
        dataset_id="ninth",
        source_version=_source_version(data_path) if Path(data_path).exists() else "in_memory",
        adapter_version=ADAPTER_VERSION,
        dataset_kind="raw_source",
        nodes=nodes,
        edges=edges,
        pairs=pairs,
        observations=empty_observations(),
        provenance={"hierarchy": provenance, "pairs": str(Path(workbook_path).resolve())},
    )


def build_esto_adapter(
    data_path: Path,
    workbook_path: Path,
) -> AdapterTables:
    """Build raw ESTO hierarchy from the full published code population."""
    tree = build_esto_tree(data_csv_path=data_path)
    provenance = f"{Path(data_path).resolve()} dot-code hierarchy"
    axis_map = {"flow": ("axis_1", "flow"), "product": ("axis_2", "product")}
    nodes = _node_rows_from_tree(
        tree,
        "esto",
        axis_map,
        "complete_declared_code_list",
        provenance,
    )
    edges = _ordinary_edges_from_tree(tree, "esto", axis_map, provenance)
    pairs = _pair_frame("esto", _mapping_pairs(workbook_path)["esto"], str(workbook_path))
    return AdapterTables(
        dataset_id="esto",
        source_version=_source_version(data_path),
        adapter_version=ADAPTER_VERSION,
        dataset_kind="raw_source",
        nodes=nodes,
        edges=edges,
        pairs=pairs,
        observations=empty_observations(),
        provenance={"hierarchy": provenance, "pairs": str(Path(workbook_path).resolve())},
    )


def _split_leap_path(value: object) -> list[str]:
    normalized = _text(value).replace("\\", "/")
    return [segment.strip() for segment in normalized.split("/") if segment.strip()]


def build_leap_adapter(
    workbook_path: Path,
    new_branch_inventory_path: Path,
) -> AdapterTables:
    """Build the available LEAP tree and explicitly mark incomplete fuel evidence."""
    mapping_pairs = _mapping_pairs(workbook_path)["leap"]
    sector_paths = {pair[0] for pair in mapping_pairs}
    fuel_names = {pair[1] for pair in mapping_pairs}
    inventory_sources: list[str] = []
    if Path(new_branch_inventory_path).exists():
        for sheet in pd.ExcelFile(new_branch_inventory_path).sheet_names:
            frame = pd.read_excel(new_branch_inventory_path, sheet_name=sheet, dtype=object)
            if "Branch Path" not in frame:
                continue
            inventory_sources.append(sheet)
            sector_paths.update(
                _text(value).replace("\\", "/")
                for value in frame["Branch Path"].dropna()
                if _text(value)
            )

    node_records: list[dict[str, object]] = []
    edge_records: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    provenance = (
        f"{Path(workbook_path).resolve()} plus "
        f"{Path(new_branch_inventory_path).resolve()} sheets={inventory_sources}"
    )
    for raw_path in sorted(sector_paths):
        segments = _split_leap_path(raw_path)
        for depth in range(1, len(segments) + 1):
            node_id = "/".join(segments[:depth])
            key = ("axis_1", node_id)
            if key not in seen:
                seen.add(key)
                node_records.append({
                    "dataset_id": "leap",
                    "axis_id": "axis_1",
                    "axis_role": "branch",
                    "node_id": node_id,
                    "node_label": segments[depth - 1],
                    "depth": depth,
                    "hierarchy_status": "partial_inventory",
                    "source_subtotal_layout": pd.NA,
                    "source_subtotal_results": pd.NA,
                    "source_subtotal_other": pd.NA,
                    "classification_rule": "declared ordinary child_count > 0",
                    "evidence": raw_path,
                    "provenance": provenance,
                })
            if depth > 1:
                edge_records.append({
                    "dataset_id": "leap",
                    "axis_id": "axis_1",
                    "parent_node_id": "/".join(segments[: depth - 1]),
                    "child_node_id": node_id,
                    "relationship_type": "ordinary_hierarchy",
                    "direction": "parent_to_child",
                    "is_additive": True,
                    "source_rule_id": "",
                    "review_status": "inventory_declared",
                    "provenance": provenance,
                })
    for fuel in sorted(fuel_names):
        node_records.append({
            "dataset_id": "leap",
            "axis_id": "axis_2",
            "axis_role": "fuel",
            "node_id": fuel,
            "node_label": fuel,
            "depth": 1,
            "hierarchy_status": "unresolved_fuel_taxonomy",
            "source_subtotal_layout": pd.NA,
            "source_subtotal_results": pd.NA,
            "source_subtotal_other": pd.NA,
            "classification_rule": "declared ordinary child_count > 0",
            "evidence": "mapping-facing fuel label only",
            "provenance": str(Path(workbook_path).resolve()),
        })
    edges = pd.DataFrame(edge_records, columns=[
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
    ]).drop_duplicates()
    return AdapterTables(
        dataset_id="leap",
        source_version=_source_version(new_branch_inventory_path),
        adapter_version=ADAPTER_VERSION,
        dataset_kind="raw_model_structure_partial",
        nodes=pd.DataFrame(node_records),
        edges=edges,
        pairs=_pair_frame("leap", mapping_pairs, str(workbook_path)),
        observations=empty_observations(),
        provenance={
            "hierarchy": provenance,
            "limitation": "Full model export unavailable; fuel taxonomy unresolved",
        },
    )


def build_tree_artifact_adapter(
    dataset_id: str,
    tree_path: Path,
    workbook_path: Path,
    dataset_kind: str,
) -> AdapterTables:
    """Adapt a derived comparison tree without splicing it into raw hierarchies."""
    tree = pd.read_csv(tree_path, dtype=object)
    axis_map = {
        "flow": ("axis_1", "flow"),
        "sector": ("axis_1", "sector"),
        "product": ("axis_2", "product"),
        "fuel": ("axis_2", "fuel"),
    }
    provenance = str(Path(tree_path).resolve())
    nodes = _node_rows_from_tree(
        tree,
        dataset_id,
        axis_map,
        "derived_declared_structure",
        provenance,
    )
    edges = _ordinary_edges_from_tree(tree, dataset_id, axis_map, provenance)
    if dataset_id in {"esto_extended", "common_esto"}:
        rules = pd.read_excel(
            workbook_path,
            sheet_name="esto_rollup_rules",
            dtype=object,
        )
        relationship_records: list[dict[str, object]] = []
        for row_number, row in rules.iterrows():
            if not _truthy(row.get("include")):
                continue
            source = _text(row.get("input_esto_flow"))
            target = _text(row.get("rolled_esto_flow"))
            if not source or not target:
                continue
            mode = _text(row.get("ROLLUP_MODE")).upper()
            if source == target:
                relationship_type = "exact_alias"
            else:
                relationship_type = {
                    "EXPANDING": "expanding_rollup",
                    "NON_EXPANDING": "non_expanding_replacement",
                    "DETACHED": "detached_diagnostic_boundary",
                }.get(mode, "additive_synthetic_rollup")
            relationship_records.append({
                "dataset_id": dataset_id,
                "axis_id": "axis_1",
                "parent_node_id": target,
                "child_node_id": source,
                "relationship_type": relationship_type,
                "direction": "component_to_declared_target",
                "is_additive": relationship_type in {
                    "additive_synthetic_rollup",
                    "expanding_rollup",
                },
                "source_rule_id": f"esto_rollup_rules:{row_number + 2}",
                "review_status": "workbook_declared",
                "provenance": str(Path(workbook_path).resolve()),
            })
        if relationship_records:
            edges = pd.concat(
                [edges, pd.DataFrame(relationship_records)],
                ignore_index=True,
            ).drop_duplicates()
    pairs_by_dataset = _mapping_pairs(workbook_path)
    if dataset_id == "common_esto":
        pair_values = set()
        source = pd.read_csv(tree_path, dtype=object)
        flow_nodes = set(source.loc[source["axis"].eq("flow"), "code"].astype(str))
        product_nodes = set(source.loc[source["axis"].eq("product"), "code"].astype(str))
        # A tree alone does not declare the pair frontier; keep it empty rather
        # than inventing a Cartesian product.
        pair_values = set() if flow_nodes or product_nodes else set()
    else:
        pair_values = pairs_by_dataset.get(dataset_id, set())
    return AdapterTables(
        dataset_id=dataset_id,
        source_version=_source_version(tree_path),
        adapter_version=ADAPTER_VERSION,
        dataset_kind=dataset_kind,
        nodes=nodes,
        edges=edges,
        pairs=_pair_frame(dataset_id, pair_values, provenance),
        observations=empty_observations(),
        provenance={"hierarchy": provenance, "relationship_boundary": dataset_kind},
    )


def build_common_esto_adapter(
    common_rows_path: Path,
    workbook_path: Path,
) -> AdapterTables:
    """Build Common ESTO structure and actual output pairs from source inputs.

    Typed hierarchy edges keep ordinary parenthood separate from expanding,
    non-expanding, and detached comparison relationships. Pair classification
    is limited to flow/product combinations that occur in common_esto_rows.csv.
    """
    common_rows_path = Path(common_rows_path)
    workbook_path = Path(workbook_path)
    tree = build_common_esto_tree(common_rows_path, workbook_path)
    typed_edges = build_common_esto_hierarchy_edges(tree, workbook_path)
    provenance = (
        f"{common_rows_path.resolve()} plus {workbook_path.resolve()}"
    )
    axis_map = {"flow": ("axis_1", "flow"), "product": ("axis_2", "product")}
    nodes = _node_rows_from_tree(
        tree,
        "common_esto",
        axis_map,
        "derived_declared_structure",
        provenance,
    )
    edge_records: list[dict[str, object]] = []
    relationship_lookup = {
        ("tree_edge", ""): "ordinary_hierarchy",
        ("expanding_rollup", "EXPANDING"): "expanding_rollup",
        ("comparison_boundary", "NON_EXPANDING"): "non_expanding_replacement",
        ("comparison_boundary", "DETACHED"): "detached_diagnostic_boundary",
    }
    for row_number, row in typed_edges.iterrows():
        edge_type = _text(row.get("edge_type"))
        rollup_mode = _text(row.get("rollup_mode")).upper()
        relationship_type = relationship_lookup.get(
            (edge_type, rollup_mode),
            "ordinary_hierarchy" if edge_type == "tree_edge" else "unresolved",
        )
        edge_records.append({
            "dataset_id": "common_esto",
            "axis_id": axis_map[_text(row.get("axis"))][0],
            "parent_node_id": _text(row.get("parent_code")),
            "child_node_id": _text(row.get("child_code")),
            "relationship_type": relationship_type,
            "direction": (
                "parent_to_child"
                if relationship_type == "ordinary_hierarchy"
                else "component_to_declared_target"
            ),
            "is_additive": relationship_type in {
                "ordinary_hierarchy",
                "expanding_rollup",
            },
            "source_rule_id": f"common_esto_hierarchy_edges:{row_number + 2}",
            "review_status": "derived_from_typed_edge",
            "provenance": provenance,
        })
    common_rows = pd.read_csv(
        common_rows_path,
        usecols=["common_flow_label", "common_product_label"],
        dtype=object,
    )
    pair_values = {
        (_text(row["common_flow_label"]), _text(row["common_product_label"]))
        for _, row in common_rows.drop_duplicates().iterrows()
    }
    source_version = (
        f"{_source_version(common_rows_path)};"
        f"{_source_version(workbook_path)}"
    )
    return AdapterTables(
        dataset_id="common_esto",
        source_version=source_version,
        adapter_version=ADAPTER_VERSION,
        dataset_kind="derived_comparison_structure",
        nodes=nodes,
        edges=pd.DataFrame(edge_records),
        pairs=_pair_frame("common_esto", pair_values, provenance),
        observations=empty_observations(),
        provenance={
            "hierarchy": provenance,
            "pair_frontier": str(common_rows_path.resolve()),
            "relationship_boundary": "typed Common ESTO hierarchy edges",
        },
    )


def build_common_esto_pair_classification(
    common_rows_path: Path,
    workbook_path: Path,
) -> pd.DataFrame:
    """Return canonical subtotal flags for actual Common ESTO output pairs."""
    tables = normalize_adapter_tables(
        build_common_esto_adapter(common_rows_path, workbook_path)
    )
    return classify_pairs(tables.nodes, tables.pairs, tables.edges)


def current_adapter_registry(
    repo_root: Path,
    workbook_path: Path,
) -> list[CallableDatasetAdapter]:
    """Return the current explicit adapter registry without core dataset branches."""
    repo_root = Path(repo_root)
    workbook_path = Path(workbook_path)
    ninth_path = repo_root / "data" / "merged_file_energy_ALL_20251106.csv"
    esto_path = repo_root / "data" / "00APEC_2025_low_with_subtotals.csv"
    leap_inventory = repo_root / "data" / "temp" / "new leap rows.xlsx"
    extended_tree = repo_root / "results" / "tree_structure" / "esto_extended_tree.csv"
    common_rows = repo_root / "results" / "common_esto" / "common_esto_rows.csv"
    registered_adapters = [
        (
            "ESTO",
            CallableDatasetAdapter(
                "esto",
                ADAPTER_VERSION,
                lambda: build_esto_adapter(esto_path, workbook_path),
            ),
        ),
        (
            "NINTH",
            CallableDatasetAdapter(
                "ninth",
                ADAPTER_VERSION,
                lambda: build_ninth_adapter(ninth_path, workbook_path),
            ),
        ),
        (
            "LEAP",
            CallableDatasetAdapter(
                "leap",
                ADAPTER_VERSION,
                lambda: build_leap_adapter(workbook_path, leap_inventory),
            ),
        ),
        (
            "ESTO_EXTENDED",
            CallableDatasetAdapter(
                "esto_extended",
                ADAPTER_VERSION,
                lambda: build_tree_artifact_adapter(
                    "esto_extended",
                    extended_tree,
                    workbook_path,
                    "derived_extended_source",
                ),
            ),
        ),
        (
            "COMMON_ESTO",
            CallableDatasetAdapter(
                "common_esto",
                ADAPTER_VERSION,
                lambda: build_common_esto_adapter(common_rows, workbook_path),
            ),
        ),
    ]
    dataset_registry = load_dataset_registry(
        repo_root / "config" / "datasets" / "dataset_registry.csv"
    )
    enabled_rows = dataset_registry[dataset_registry["enabled"]]
    enabled_ids = set(enabled_rows["dataset_id"])
    available_ids = {dataset_id for dataset_id, _ in registered_adapters}

    missing_adapters = sorted(enabled_ids - available_ids)
    if missing_adapters:
        raise ValueError(
            "Enabled datasets have no current hierarchy adapter: "
            f"{missing_adapters}"
        )

    expected_adapter_names = {
        dataset_id: adapter.dataset_id
        for dataset_id, adapter in registered_adapters
    }
    mismatches = [
        f"{row.dataset_id}={row.hierarchy_adapter!r}"
        for row in enabled_rows.itertuples(index=False)
        if row.hierarchy_adapter != expected_adapter_names[row.dataset_id]
    ]
    if mismatches:
        raise ValueError(
            "Configured hierarchy_adapter does not match the current adapter: "
            f"{mismatches}"
        )

    # Preserve the established adapter execution order for output equivalence.
    return [
        adapter
        for dataset_id, adapter in registered_adapters
        if dataset_id in enabled_ids
    ]


def build_ninth_family_conformance(
    data_path: Path,
    family_codes: tuple[str, ...] = (
        "09_06_gas_processing_plants",
        "09_08_coal_transformation",
    ),
    years: tuple[str, ...] | None = ("2022", "2023", "2050", "2070"),
    tolerance: float = 0.01,
) -> pd.DataFrame:
    """Return exact-context source additivity evidence for required regressions.

    The default bounded years cover the layout/projection boundary and two
    projection horizons. Pass ``years=None`` for every available year.
    """
    header = pd.read_csv(data_path, nrows=0)
    year_columns = [column for column in header.columns if str(column).isdigit()]
    if years is not None:
        year_columns = [column for column in year_columns if str(column) in years]
    use_columns = [
        "economy",
        "scenarios",
        "sectors",
        "sub1sectors",
        "sub2sectors",
        "sub3sectors",
        "sub4sectors",
        "fuels",
        "subfuels",
        *year_columns,
    ]
    data = pd.read_csv(data_path, usecols=use_columns, dtype=object)
    data = data[data["sub1sectors"].isin(family_codes)].copy()
    data[year_columns] = data[year_columns].apply(pd.to_numeric, errors="coerce")
    id_columns = [
        "economy",
        "scenarios",
        "sectors",
        "sub1sectors",
        "sub2sectors",
        "fuels",
        "subfuels",
    ]
    long = data[id_columns + year_columns].melt(
        id_vars=id_columns,
        value_vars=year_columns,
        var_name="year_or_period",
        value_name="value",
    )
    long["opposite_axis"] = (
        long["fuels"].fillna("").astype(str)
        + long["subfuels"].fillna("").astype(str).map(
            lambda value: "" if not value or value == "x" else f"/{value}"
        )
    )
    context = [
        "economy",
        "scenarios",
        "year_or_period",
        "sectors",
        "sub1sectors",
        "opposite_axis",
    ]
    parents = (
        long[long["sub2sectors"].fillna("x").eq("x")]
        .groupby(context, dropna=False)["value"]
        .sum(min_count=1)
        .rename("parent_value")
        .reset_index()
    )
    children_long = long[~long["sub2sectors"].fillna("x").eq("x")].copy()
    children = (
        children_long.groupby(context, dropna=False)
        .agg(
            child_sum=("value", lambda values: values.sum(min_count=1)),
            positive_child_sum=("value", lambda values: values[values > 0].sum()),
            negative_child_sum=("value", lambda values: values[values < 0].sum()),
            observed_child_count=("sub2sectors", "nunique"),
        )
        .reset_index()
    )
    expected = (
        children_long.groupby(["sectors", "sub1sectors"])["sub2sectors"]
        .nunique()
        .rename("expected_child_count")
        .reset_index()
    )
    result = parents.merge(children, on=context, how="outer").merge(
        expected,
        on=["sectors", "sub1sectors"],
        how="left",
    )
    result["missing_child_count"] = (
        result["expected_child_count"].fillna(0)
        - result["observed_child_count"].fillna(0)
    ).clip(lower=0)
    result["signed_difference"] = result["parent_value"] - result["child_sum"]
    result["absolute_difference"] = result["signed_difference"].abs()
    unavailable = result["parent_value"].isna() | result["child_sum"].isna()
    incomplete = result["missing_child_count"].gt(0)
    result["status"] = "passed"
    result.loc[result["absolute_difference"].gt(tolerance), "status"] = "failed"
    result.loc[incomplete, "status"] = "children_incomplete"
    result.loc[unavailable, "status"] = "unavailable"
    result["reason"] = result["status"].map({
        "passed": "within_tolerance",
        "failed": "difference_exceeds_tolerance",
        "children_incomplete": "declared_children_missing",
        "unavailable": "parent_or_children_unavailable",
    })
    source_version = _source_version(data_path)
    return pd.DataFrame({
        "dataset_id": "ninth",
        "source_version": source_version,
        "economy": result["economy"],
        "scenario": result["scenarios"],
        "year_or_period": result["year_or_period"],
        "validation_axis": "axis_1",
        "parent_node_id": result["sectors"].astype(str) + "/" + result["sub1sectors"].astype(str),
        "fixed_opposite_axis_node_id": result["opposite_axis"],
        "parent_value": result["parent_value"],
        "child_sum": result["child_sum"],
        "signed_difference": result["signed_difference"],
        "absolute_difference": result["absolute_difference"],
        "positive_child_sum": result["positive_child_sum"],
        "negative_child_sum": result["negative_child_sum"],
        "expected_child_count": result["expected_child_count"],
        "observed_child_count": result["observed_child_count"],
        "missing_child_count": result["missing_child_count"],
        "mapped_child_count": result["observed_child_count"],
        "tolerance": tolerance,
        "status": result["status"],
        "reason": result["reason"],
        "inherited_source_inconsistency": result["status"].eq("failed"),
        "exception_status": "",
        "exception_reason": "",
        "provenance": str(Path(data_path).resolve()),
    })


def build_esto_family_conformance(
    data_path: Path,
    family_codes: tuple[str, ...] = (
        "09.06 Gas processing plants",
        "09.08 Coal transformation",
    ),
    years: tuple[str, ...] | None = None,
    tolerance: float = 0.01,
) -> pd.DataFrame:
    """Return exact-context ESTO flow additivity evidence for named families.

    ESTO flow parenthood comes from the same dot-code tree used by the ESTO
    contract adapter. Each parent is compared with its immediate flow children
    while economy, product, and year remain fixed.
    """
    data_path = Path(data_path)
    tree = build_esto_tree(data_csv_path=data_path)
    flow_edges = tree[
        tree["axis"].eq("flow")
        & tree["parent_code"].astype(str).isin(family_codes)
    ][["parent_code", "code"]].drop_duplicates()
    children_by_parent = (
        flow_edges.groupby("parent_code")["code"]
        .agg(lambda values: tuple(sorted(set(map(str, values)))))
        .to_dict()
    )
    missing_families = sorted(set(family_codes) - set(children_by_parent))
    if missing_families:
        raise ValueError(
            "ESTO conformance families have no declared immediate children: "
            + ", ".join(missing_families)
        )

    header = pd.read_csv(data_path, nrows=0)
    year_columns = [column for column in header.columns if str(column).isdigit()]
    if years is not None:
        year_columns = [column for column in year_columns if str(column) in years]
    relevant_flows = set(family_codes)
    for children in children_by_parent.values():
        relevant_flows.update(children)
    data = pd.read_csv(
        data_path,
        usecols=["economy", "flows", "products", *year_columns],
        dtype=object,
    )
    data = data[data["flows"].isin(relevant_flows)].copy()
    data[year_columns] = data[year_columns].apply(pd.to_numeric, errors="coerce")
    long = data.melt(
        id_vars=["economy", "flows", "products"],
        value_vars=year_columns,
        var_name="year_or_period",
        value_name="value",
    )
    source_version = _source_version(data_path)
    result_frames: list[pd.DataFrame] = []
    context_columns = ["economy", "products", "year_or_period"]
    for parent_node_id, children in children_by_parent.items():
        family = long[long["flows"].isin({parent_node_id, *children})]
        parents = (
            family[family["flows"].eq(parent_node_id)]
            .groupby(context_columns, dropna=False)["value"]
            .sum(min_count=1)
            .rename("parent_value")
            .reset_index()
        )
        child_rows = family[family["flows"].isin(children)]
        child_rows = child_rows.assign(
            positive_value=child_rows["value"].where(child_rows["value"].gt(0), 0),
            negative_value=child_rows["value"].where(child_rows["value"].lt(0), 0),
        )
        child_totals = (
            child_rows.groupby(context_columns, dropna=False)
            .agg(
                child_sum=("value", lambda values: values.sum(min_count=1)),
                positive_child_sum=("positive_value", "sum"),
                negative_child_sum=("negative_value", "sum"),
                observed_child_count=("flows", "nunique"),
            )
            .reset_index()
        )
        result = parents.merge(child_totals, on=context_columns, how="outer")
        result["expected_child_count"] = len(children)
        result["missing_child_count"] = (
            result["expected_child_count"]
            - result["observed_child_count"].fillna(0)
        ).clip(lower=0)
        result["signed_difference"] = result["parent_value"] - result["child_sum"]
        result["absolute_difference"] = result["signed_difference"].abs()
        unavailable = result["parent_value"].isna() | result["child_sum"].isna()
        incomplete = result["missing_child_count"].gt(0)
        result["status"] = "passed"
        result.loc[result["absolute_difference"].gt(tolerance), "status"] = "failed"
        result.loc[incomplete, "status"] = "children_incomplete"
        result.loc[unavailable, "status"] = "unavailable"
        result["reason"] = result["status"].map({
            "passed": "within_tolerance",
            "failed": "difference_exceeds_tolerance",
            "children_incomplete": "declared_children_missing",
            "unavailable": "parent_or_children_unavailable",
        })
        result_frames.append(pd.DataFrame({
            "dataset_id": "esto",
            "source_version": source_version,
            "economy": result["economy"],
            "scenario": "historical",
            "year_or_period": result["year_or_period"],
            "validation_axis": "axis_1",
            "parent_node_id": parent_node_id,
            "fixed_opposite_axis_node_id": result["products"],
            "parent_value": result["parent_value"],
            "child_sum": result["child_sum"],
            "signed_difference": result["signed_difference"],
            "absolute_difference": result["absolute_difference"],
            "positive_child_sum": result["positive_child_sum"],
            "negative_child_sum": result["negative_child_sum"],
            "expected_child_count": result["expected_child_count"],
            "observed_child_count": result["observed_child_count"],
            "missing_child_count": result["missing_child_count"],
            "mapped_child_count": result["observed_child_count"],
            "tolerance": tolerance,
            "status": result["status"],
            "reason": result["reason"],
            "inherited_source_inconsistency": result["status"].eq("failed"),
            "exception_status": "",
            "exception_reason": "",
            "provenance": f"{data_path.resolve()} dot-code immediate-child additivity",
        }))
    return pd.concat(result_frames, ignore_index=True).sort_values(
        [
            "parent_node_id",
            "economy",
            "fixed_opposite_axis_node_id",
            "year_or_period",
        ],
        kind="stable",
    ).reset_index(drop=True)


def normalize_common_esto_value_conformance(
    validation_path: Path,
    expected_run_id: str | None = None,
    tolerance: float = 0.01,
) -> pd.DataFrame:
    """Normalize current-run Common ESTO checks into the contract schema.

    The Stage 3 validator remains responsible for resolving source-specific
    frontiers and rollup semantics. This adapter preserves its full comparison
    context instead of recomputing those rules inside the contract producer.
    """
    validation_path = Path(validation_path)
    validation = pd.read_csv(validation_path, dtype=object)
    required = {
        "run_id",
        "validation_axis",
        "comparison_scope",
        "source_system",
        "economy",
        "scenario",
        "other_axis_value",
        "parent_code",
        "child_count",
        "frontier_row_count",
        "year",
        "parent_value",
        "children_sum",
        "difference",
        "abs_error",
        "status",
        "reason",
        "inherited_source_inconsistency",
    }
    missing = required.difference(validation.columns)
    if missing:
        raise ValueError(
            "Common ESTO validation is missing required columns: "
            + ", ".join(sorted(missing))
        )
    run_ids = set(validation["run_id"].dropna().astype(str)) - {"", "nan"}
    if expected_run_id and run_ids != {expected_run_id}:
        raise ValueError(
            "Common ESTO validation run_id does not match the selected Stage 3 run"
        )
    axis_lookup = {"flow": "axis_1", "product": "axis_2"}
    validation_axis = validation["validation_axis"].astype(str).map(axis_lookup)
    if validation_axis.isna().any():
        unexpected = sorted(
            set(validation.loc[validation_axis.isna(), "validation_axis"].astype(str))
        )
        raise ValueError(
            f"Common ESTO validation has unsupported axes: {unexpected}"
        )
    missing_children = (
        validation.get("missing_expected_children", pd.Series("", index=validation.index))
        .fillna("")
        .astype(str)
        .map(lambda value: len([item for item in value.split(";") if item.strip()]))
    )
    numeric = {}
    for column in [
        "parent_value",
        "children_sum",
        "difference",
        "abs_error",
        "child_count",
        "frontier_row_count",
    ]:
        numeric[column] = pd.to_numeric(validation[column], errors="coerce")
    return pd.DataFrame({
        "dataset_id": "common_esto",
        "source_version": _source_version(validation_path),
        "run_id": validation["run_id"],
        "comparison_scope": validation["comparison_scope"],
        "source_system": validation["source_system"],
        "economy": validation["economy"],
        "scenario": validation["scenario"],
        "year_or_period": validation["year"],
        "validation_axis": validation_axis,
        "parent_node_id": validation["parent_code"],
        "fixed_opposite_axis_node_id": validation["other_axis_value"],
        "parent_value": numeric["parent_value"],
        "child_sum": numeric["children_sum"],
        "signed_difference": numeric["difference"],
        "absolute_difference": numeric["abs_error"],
        "positive_child_sum": pd.NA,
        "negative_child_sum": pd.NA,
        "expected_child_count": numeric["child_count"],
        "observed_child_count": numeric["frontier_row_count"],
        "missing_child_count": missing_children,
        "mapped_child_count": numeric["frontier_row_count"],
        "tolerance": tolerance,
        "tolerance_mode": "relative_with_absolute_floor",
        "status": validation["status"],
        "reason": validation["reason"],
        "inherited_source_inconsistency": validation[
            "inherited_source_inconsistency"
        ].map(_truthy),
        "source_inconsistency_status": validation.get(
            "source_inconsistency_status", ""
        ),
        "sector_hierarchy_status": validation.get("sector_hierarchy_status", ""),
        "fuel_hierarchy_status": validation.get("fuel_hierarchy_status", ""),
        "source_issue_ids": validation.get("source_issue_ids", ""),
        "exception_status": "",
        "exception_reason": "",
        "provenance": str(validation_path.resolve()),
    }).sort_values(
        [
            "comparison_scope",
            "source_system",
            "validation_axis",
            "parent_node_id",
            "economy",
            "scenario",
            "fixed_opposite_axis_node_id",
            "year_or_period",
        ],
        kind="stable",
    ).reset_index(drop=True)


#%%
