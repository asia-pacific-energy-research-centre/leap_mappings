#%%
"""Build the generated LEAP sector/fuel pair registry.

The registry is structural authority for the separate-axis prototype. It is
rebuilt from the union of current economy export templates and the temporary
``new leap rows.xlsx`` demand/power inventories whenever any source workbook
changes.
"""

#%%
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


# --- Stable constants -------------------------------------------------------

EXPORT_SHEET_NAME = "Export"
EXPORT_HEADER_ROW = 2
NEW_ROW_SHEETS = ("demand", "power")
FUEL_ROLE_LABELS = {
    "Feedstock Fuels",
    "Auxiliary Fuels",
    "Output Fuels",
}
LEGACY_BRANCH_SUFFIX = "_do not use"
LEAP_PAIR_REGISTRY_VERSION = 4
FIXED_BALANCE_FLOWS = {
    "Production",
    "Imports",
    "Exports",
    "Stock Changes",
    "Total Primary Supply",
    "Total Transformation",
    "Statistical Differences",
    "Total Final Energy Demand",
    "Unmet Requirements",
}

PAIR_COLUMNS = [
    "dataset",
    "flow",
    "product",
    "flow_is_parent",
    "product_is_parent",
    "pair_is_subtotal",
    "pair_exists_in_dataset",
    "pair_universe_member",
    "pair_status",
    "temporal_evidence_status",
    "pair_universe_authority",
    "authority_layer",
    "source_kind",
    "template_support_count",
    "template_files",
    "new_rows_sheet_count",
    "new_rows_sheets",
    "source_path_count",
    "source_paths",
]


# --- Path and fingerprint helpers ------------------------------------------

def _clean(value: Any) -> str:
    """Return stripped text, treating null values as blank."""
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.casefold() in {"nan", "none", "<na>"} else text


def _normalise_branch_path(value: Any) -> str:
    """Return one backslash-separated LEAP branch path."""
    text = _clean(value).replace("/", "\\")
    return "\\".join(part.strip() for part in text.split("\\") if part.strip())


def _file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 digest of one source file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_leap_pair_sources(
    template_dir: Path,
    new_rows_workbook_path: Path,
) -> list[dict[str, Any]]:
    """Return the current top-level template set plus the detailed-row source."""
    template_dir = Path(template_dir)
    new_rows_workbook_path = Path(new_rows_workbook_path)
    if not template_dir.exists():
        raise FileNotFoundError(
            f"LEAP export template directory not found: {template_dir}"
        )
    if not new_rows_workbook_path.exists():
        raise FileNotFoundError(
            f"Detailed LEAP row workbook not found: {new_rows_workbook_path}"
        )

    template_paths = sorted(
        path
        for path in template_dir.glob("*.xlsx")
        if not path.name.startswith("~$")
        and path.resolve() != new_rows_workbook_path.resolve()
    )
    if not template_paths:
        raise FileNotFoundError(
            f"No current top-level LEAP export templates found in {template_dir}"
        )

    sources = [
        {
            "source_kind": "export_template",
            "source_id": path.name,
            "path": path,
        }
        for path in template_paths
    ]
    sources.append(
        {
            "source_kind": "detailed_model_rows",
            "source_id": new_rows_workbook_path.name,
            "path": new_rows_workbook_path,
        }
    )
    return sources


def build_source_manifest(
    sources: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Fingerprint every workbook used to build the LEAP pair registry."""
    records: list[dict[str, Any]] = []
    for source in sources:
        path = Path(source["path"]).resolve()
        stat = path.stat()
        records.append(
            {
                "source_kind": str(source["source_kind"]),
                "source_id": str(source["source_id"]),
                "path": str(path),
                "size_bytes": int(stat.st_size),
                "modified_time_ns": int(stat.st_mtime_ns),
                "sha256": _file_sha256(path),
            }
        )
    records.sort(
        key=lambda row: (
            row["source_kind"],
            row["source_id"].casefold(),
            row["path"].casefold(),
        )
    )
    signature_payload = json.dumps(
        records,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "manifest_version": LEAP_PAIR_REGISTRY_VERSION,
        "source_signature": hashlib.sha256(signature_payload).hexdigest(),
        "source_count": len(records),
        "sources": records,
    }


def source_manifest_changed(
    current_manifest: dict[str, Any],
    previous_manifest: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Explain whether the cached registry must be refreshed."""
    if previous_manifest is None:
        return True, "no_previous_manifest"
    if previous_manifest.get("manifest_version") != current_manifest.get(
        "manifest_version"
    ):
        return True, "manifest_version_changed"
    if previous_manifest.get("source_signature") != current_manifest.get(
        "source_signature"
    ):
        return True, "source_workbook_set_or_fingerprint_changed"
    return False, "source_workbooks_unchanged"


# --- Branch parsing ---------------------------------------------------------

def _leaf_paths(paths: Iterable[Any]) -> list[str]:
    """Return paths that have no descendant in the same source inventory."""
    normalised = sorted(
        {
            path
            for value in paths
            if (path := _normalise_branch_path(value))
        }
    )
    path_set = set(normalised)
    parents = {
        "\\".join(parts[:depth])
        for path in normalised
        for parts in [path.split("\\")]
        for depth in range(1, len(parts))
        if "\\".join(parts[:depth]) in path_set
    }
    return [path for path in normalised if path not in parents]


def parse_leap_branch_paths_to_pairs(
    paths: Iterable[Any],
    *,
    source_kind: str,
    source_id: str,
    source_sheet: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert one branch inventory into exact LEAP sector/fuel pairs.

    Demand fuel keys are leaf labels. Transformation fuel keys must sit
    immediately below an explicit LEAP fuel-role node.
    """
    pair_records: list[dict[str, Any]] = []
    diagnostic_records: list[dict[str, Any]] = []
    for branch_path in _leaf_paths(paths):
        parts = branch_path.split("\\")
        lower_parts = [part.casefold() for part in parts]
        if any(part.endswith(LEGACY_BRANCH_SUFFIX) for part in lower_parts):
            diagnostic_records.append(
                {
                    "source_kind": source_kind,
                    "source_id": source_id,
                    "source_sheet": source_sheet,
                    "branch_path": branch_path,
                    "status": "excluded_legacy_do_not_use",
                }
            )
            continue

        sector = ""
        fuel = ""
        parse_rule = ""
        if parts[0] == "Demand" and len(parts) >= 3:
            sector = "/".join(parts[1:-1])
            fuel = parts[-1]
            parse_rule = "demand_leaf"
        elif parts[0] == "Transformation":
            role_indexes = [
                index
                for index, part in enumerate(parts)
                if part in FUEL_ROLE_LABELS
            ]
            if (
                role_indexes
                and role_indexes[-1] >= 2
                and role_indexes[-1] + 1 == len(parts) - 1
            ):
                role_index = role_indexes[-1]
                sector = "/".join(parts[1:role_index])
                fuel = parts[role_index + 1]
                parse_rule = (
                    "transformation_"
                    + parts[role_index].lower().replace(" ", "_")
                )

        if not sector or not fuel:
            diagnostic_records.append(
                {
                    "source_kind": source_kind,
                    "source_id": source_id,
                    "source_sheet": source_sheet,
                    "branch_path": branch_path,
                    "status": "excluded_non_energy_or_unrecognised_leaf",
                }
            )
            continue

        pair_records.append(
            {
                "flow": sector,
                "product": fuel,
                "source_kind": source_kind,
                "source_id": source_id,
                "source_sheet": source_sheet,
                "branch_path": branch_path,
                "parse_rule": parse_rule,
            }
        )
        if (
            parts[0] == "Demand"
            and len(parts) >= 3
            and parts[1] == "All demand aggregated"
        ):
            pair_records.append(
                {
                    "flow": "\\".join(parts[:-1]),
                    "product": fuel,
                    "source_kind": source_kind,
                    "source_id": source_id,
                    "source_sheet": source_sheet,
                    "branch_path": branch_path,
                    "parse_rule": "literal_demand_branch_key",
                }
            )

    pair_frame = pd.DataFrame(
        pair_records,
        columns=[
            "flow",
            "product",
            "source_kind",
            "source_id",
            "source_sheet",
            "branch_path",
            "parse_rule",
        ],
    )
    diagnostic_frame = pd.DataFrame(
        diagnostic_records,
        columns=[
            "source_kind",
            "source_id",
            "source_sheet",
            "branch_path",
            "status",
        ],
    )
    return pair_frame, diagnostic_frame


def derive_leap_balance_structure(
    paths: Iterable[Any],
    *,
    source_kind: str,
    source_id: str,
    source_sheet: str,
    include_fixed_flows: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Derive balance-report flows and the global fuel-column catalogue.

    LEAP energy-balance exports are grids. The report flows are generated from
    Demand ancestors, Transformation module/process rows, and fixed balance
    rows. The fuel columns are the leaves below ``All demand aggregated`` in
    the current economy templates.
    """
    flow_records: list[dict[str, Any]] = []
    fuel_records: list[dict[str, Any]] = []

    def add_flow(
        flow: str,
        branch_path: str,
        parse_rule: str,
    ) -> None:
        if not flow:
            return
        flow_records.append(
            {
                "flow": flow,
                "source_kind": source_kind,
                "source_id": source_id,
                "source_sheet": source_sheet,
                "branch_path": branch_path,
                "parse_rule": parse_rule,
            }
        )

    if include_fixed_flows:
        for flow in sorted(FIXED_BALANCE_FLOWS):
            add_flow(flow, "", "fixed_balance_flow")

    for branch_path in _leaf_paths(paths):
        parts = branch_path.split("\\")
        lower_parts = [part.casefold() for part in parts]
        if any(part.endswith(LEGACY_BRANCH_SUFFIX) for part in lower_parts):
            continue

        if parts[0] == "Demand" and len(parts) >= 3:
            sector_parts = parts[1:-1]
            for depth in range(1, len(sector_parts) + 1):
                add_flow(
                    "/".join(sector_parts[:depth]),
                    branch_path,
                    "demand_balance_ancestor",
                )
            if parts[1] == "All demand aggregated":
                # These Total Energy branches are visible as report rows as
                # well as defining the global product-column catalogue.
                add_flow(
                    "/".join(parts[1:]),
                    branch_path,
                    "all_demand_aggregated_fuel_flow",
                )
                fuel_records.append(
                    {
                        "product": parts[-1],
                        "source_kind": source_kind,
                        "source_id": source_id,
                        "source_sheet": source_sheet,
                        "branch_path": branch_path,
                    }
                )
            continue

        if parts[0] != "Transformation":
            continue
        role_indexes = [
            index
            for index, part in enumerate(parts)
            if part in FUEL_ROLE_LABELS
        ]
        if not role_indexes or role_indexes[-1] + 1 != len(parts) - 1:
            continue
        role_index = role_indexes[-1]
        sector_parts = parts[1:role_index]
        if not sector_parts:
            continue
        if "Processes" in sector_parts:
            process_index = sector_parts.index("Processes")
            module_parts = sector_parts[:process_index]
            process_parts = sector_parts[process_index + 1 :]
            add_flow(
                "/".join(module_parts),
                branch_path,
                "transformation_balance_module",
            )
            add_flow(
                "/".join(module_parts + process_parts),
                branch_path,
                "transformation_balance_process",
            )
        else:
            add_flow(
                "/".join(sector_parts),
                branch_path,
                "transformation_balance_module",
            )

    flow_frame = pd.DataFrame(
        flow_records,
        columns=[
            "flow",
            "source_kind",
            "source_id",
            "source_sheet",
            "branch_path",
            "parse_rule",
        ],
    ).drop_duplicates()
    fuel_frame = pd.DataFrame(
        fuel_records,
        columns=[
            "product",
            "source_kind",
            "source_id",
            "source_sheet",
            "branch_path",
        ],
    ).drop_duplicates()
    return flow_frame, fuel_frame


def _balance_grid_evidence(
    template_structures: list[tuple[pd.DataFrame, pd.DataFrame]],
    detailed_flows: pd.DataFrame,
) -> pd.DataFrame:
    """Cross report flows with their structurally available fuel columns."""
    pair_frames: list[pd.DataFrame] = []
    template_catalog_frames: list[pd.DataFrame] = []
    template_flow_frames = [
        flows
        for flows, catalogue in template_structures
        if not flows.empty and not catalogue.empty
    ]
    template_catalog_frames = [
        catalogue
        for flows, catalogue in template_structures
        if not flows.empty and not catalogue.empty
    ]
    if template_flow_frames and template_catalog_frames:
        all_template_flows = pd.concat(
            template_flow_frames,
            ignore_index=True,
        ).drop_duplicates()
        global_catalogue = (
            pd.concat(template_catalog_frames, ignore_index=True)[["product"]]
            .drop_duplicates()
        )
        pairs = all_template_flows.merge(global_catalogue, how="cross")
        pairs["source_kind"] = "balance_export_template"
        pair_frames.append(
            pairs[
                [
                    "flow",
                    "product",
                    "source_kind",
                    "source_id",
                    "source_sheet",
                    "branch_path",
                    "parse_rule",
                ]
            ]
        )

    if template_catalog_frames and not detailed_flows.empty:
        global_catalogue = pd.concat(
            template_catalog_frames,
            ignore_index=True,
        )[["product"]].drop_duplicates()
        detailed_pairs = detailed_flows.merge(
            global_catalogue,
            how="cross",
        )
        detailed_pairs["source_kind"] = "balance_detailed_model_rows"
        pair_frames.append(
            detailed_pairs[
                [
                    "flow",
                    "product",
                    "source_kind",
                    "source_id",
                    "source_sheet",
                    "branch_path",
                    "parse_rule",
                ]
            ]
        )

    if not pair_frames:
        return pd.DataFrame(
            columns=[
                "flow",
                "product",
                "source_kind",
                "source_id",
                "source_sheet",
                "branch_path",
                "parse_rule",
            ]
        )
    return pd.concat(pair_frames, ignore_index=True).drop_duplicates()


def _read_export_template_pairs(
    path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read one template into direct pairs and balance-grid structure."""
    frame = pd.read_excel(
        path,
        sheet_name=EXPORT_SHEET_NAME,
        header=EXPORT_HEADER_ROW,
        usecols=["Branch Path"],
        dtype=object,
    )
    pairs, diagnostics = parse_leap_branch_paths_to_pairs(
        frame["Branch Path"],
        source_kind="direct_export_template",
        source_id=path.name,
        source_sheet=EXPORT_SHEET_NAME,
    )
    flows, catalogue = derive_leap_balance_structure(
        frame["Branch Path"],
        source_kind="export_template",
        source_id=path.name,
        source_sheet=EXPORT_SHEET_NAME,
        include_fixed_flows=True,
    )
    return pairs, diagnostics, flows, catalogue


def _read_detailed_model_row_pairs(
    path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read direct pairs and balance flows from detailed demand/power tabs."""
    available_sheets = set(pd.ExcelFile(path).sheet_names)
    missing = [sheet for sheet in NEW_ROW_SHEETS if sheet not in available_sheets]
    if missing:
        raise ValueError(
            f"{path} is missing required sheet(s): {', '.join(missing)}"
        )

    pair_frames: list[pd.DataFrame] = []
    diagnostic_frames: list[pd.DataFrame] = []
    flow_frames: list[pd.DataFrame] = []
    for sheet in NEW_ROW_SHEETS:
        frame = pd.read_excel(
            path,
            sheet_name=sheet,
            usecols=["Branch Path"],
            dtype=object,
        )
        pairs, diagnostics = parse_leap_branch_paths_to_pairs(
            frame["Branch Path"],
            source_kind="direct_detailed_model_rows",
            source_id=path.name,
            source_sheet=sheet,
        )
        flows, _catalogue = derive_leap_balance_structure(
            frame["Branch Path"],
            source_kind="detailed_model_rows",
            source_id=path.name,
            source_sheet=sheet,
            include_fixed_flows=False,
        )
        pair_frames.append(pairs)
        diagnostic_frames.append(diagnostics)
        flow_frames.append(flows)
    return (
        pd.concat(pair_frames, ignore_index=True),
        pd.concat(diagnostic_frames, ignore_index=True),
        pd.concat(flow_frames, ignore_index=True).drop_duplicates(),
    )


def _join_sorted(values: Iterable[Any]) -> str:
    """Join distinct nonblank values in stable order."""
    return "|".join(sorted({_clean(value) for value in values if _clean(value)}))


def build_leap_pair_registry(
    template_dir: Path,
    new_rows_workbook_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Build layered direct-branch and deterministic balance-grid pairs."""
    sources = discover_leap_pair_sources(
        template_dir,
        new_rows_workbook_path,
    )
    pair_frames: list[pd.DataFrame] = []
    diagnostic_frames: list[pd.DataFrame] = []
    template_structures: list[tuple[pd.DataFrame, pd.DataFrame]] = []
    detailed_flow_frames: list[pd.DataFrame] = []
    for source in sources:
        path = Path(source["path"])
        if source["source_kind"] == "export_template":
            pairs, diagnostics, flows, catalogue = (
                _read_export_template_pairs(path)
            )
            template_structures.append((flows, catalogue))
        else:
            pairs, diagnostics, flows = _read_detailed_model_row_pairs(path)
            detailed_flow_frames.append(flows)
        pair_frames.append(pairs)
        diagnostic_frames.append(diagnostics)

    direct_evidence = pd.concat(
        pair_frames,
        ignore_index=True,
    ).drop_duplicates()
    detailed_flows = (
        pd.concat(detailed_flow_frames, ignore_index=True).drop_duplicates()
        if detailed_flow_frames
        else pd.DataFrame()
    )
    balance_evidence = _balance_grid_evidence(
        template_structures,
        detailed_flows,
    )
    evidence = pd.concat(
        [direct_evidence, balance_evidence],
        ignore_index=True,
    ).drop_duplicates()
    diagnostics = pd.concat(
        diagnostic_frames,
        ignore_index=True,
    ).drop_duplicates()
    if evidence.empty:
        raise ValueError("No viable LEAP sector/fuel pairs were parsed.")

    records: list[dict[str, Any]] = []
    for (flow, product), group in evidence.groupby(
        ["flow", "product"],
        sort=True,
        dropna=False,
    ):
        template_group = group[
            group["source_kind"].str.contains("export_template")
        ]
        new_rows_group = group[
            group["source_kind"].str.contains("detailed_model_rows")
        ]
        source_kinds = set(group["source_kind"])
        has_direct = bool(group["source_kind"].str.startswith("direct_").any())
        has_balance = bool(
            group["source_kind"].str.startswith("balance_").any()
        )
        authority_layer = (
            "direct_model_branch_and_balance_grid"
            if has_direct and has_balance
            else (
                "direct_model_branch"
                if has_direct
                else "deterministic_balance_grid"
            )
        )
        records.append(
            {
                "flow": flow,
                "product": product,
                "authority_layer": authority_layer,
                "source_kind": _join_sorted(source_kinds),
                "template_support_count": int(
                    template_group["source_id"].nunique()
                ),
                "template_files": _join_sorted(template_group["source_id"]),
                "new_rows_sheet_count": int(
                    new_rows_group["source_sheet"].nunique()
                ),
                "new_rows_sheets": _join_sorted(
                    new_rows_group["source_sheet"]
                ),
                "source_path_count": int(group["branch_path"].nunique()),
                "source_paths": _join_sorted(group["branch_path"]),
            }
        )

    registry = pd.DataFrame(records)
    flows = set(registry["flow"])
    products = set(registry["product"])
    flow_parents = {
        flow
        for flow in flows
        if any(other.startswith(flow + "/") for other in flows if other != flow)
    }
    product_parents = {
        product
        for product in products
        if any(
            other.startswith(product + "/")
            for other in products
            if other != product
        )
    }
    registry.insert(0, "dataset", "LEAP")
    registry["flow_is_parent"] = registry["flow"].isin(flow_parents)
    registry["product_is_parent"] = registry["product"].isin(product_parents)
    registry["pair_is_subtotal"] = (
        registry["flow_is_parent"] | registry["product_is_parent"]
    )
    registry["pair_exists_in_dataset"] = True
    registry["pair_universe_member"] = True
    registry["pair_status"] = registry["authority_layer"].map(
        {
            "direct_model_branch_and_balance_grid": (
                "structurally_eligible_branch_and_balance"
            ),
            "direct_model_branch": "structurally_eligible_model_branch",
            "deterministic_balance_grid": (
                "structurally_eligible_balance_cell"
            ),
        }
    )
    registry["temporal_evidence_status"] = registry["pair_status"]
    registry["pair_universe_authority"] = (
        "generated_from_model_branches_and_balance_report_contract"
    )
    registry = registry[PAIR_COLUMNS].sort_values(
        ["flow", "product"],
        kind="stable",
    ).reset_index(drop=True)

    summary = {
        "registry_version": LEAP_PAIR_REGISTRY_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "pair_count": len(registry),
        "subtotal_pair_count": int(registry["pair_is_subtotal"].sum()),
        "direct_only_pair_count": int(
            registry["authority_layer"].eq("direct_model_branch").sum()
        ),
        "balance_only_pair_count": int(
            registry["authority_layer"].eq(
                "deterministic_balance_grid"
            ).sum()
        ),
        "shared_authority_pair_count": int(
            registry["authority_layer"].eq(
                "direct_model_branch_and_balance_grid"
            ).sum()
        ),
        "balance_flow_count": int(
            balance_evidence["flow"].nunique()
        ),
        "balance_product_count": int(
            balance_evidence["product"].nunique()
        ),
        "excluded_leaf_count": len(diagnostics),
    }
    return registry, diagnostics, summary


# --- Cached refresh ---------------------------------------------------------

def load_or_refresh_leap_pair_registry(
    template_dir: Path,
    new_rows_workbook_path: Path,
    registry_path: Path,
    manifest_path: Path,
    diagnostics_path: Path,
    *,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return the cached registry, rebuilding it after any source update."""
    registry_path = Path(registry_path)
    manifest_path = Path(manifest_path)
    diagnostics_path = Path(diagnostics_path)
    sources = discover_leap_pair_sources(
        template_dir,
        new_rows_workbook_path,
    )
    current_source_manifest = build_source_manifest(sources)
    previous_manifest: dict[str, Any] | None = None
    if manifest_path.exists():
        try:
            previous_manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            previous_manifest = None

    changed, refresh_reason = source_manifest_changed(
        current_source_manifest,
        previous_manifest,
    )
    needs_refresh = (
        force_refresh
        or changed
        or not registry_path.exists()
        or not diagnostics_path.exists()
    )
    if not needs_refresh:
        manifest = dict(previous_manifest or {})
        manifest["refreshed_this_run"] = False
        manifest["refresh_reason"] = refresh_reason
        return pd.read_csv(registry_path, low_memory=False), manifest

    registry, diagnostics, registry_summary = build_leap_pair_registry(
        template_dir,
        new_rows_workbook_path,
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    registry.to_csv(registry_path, index=False)
    diagnostics.to_csv(diagnostics_path, index=False)
    manifest = {
        **current_source_manifest,
        **registry_summary,
        "registry_path": str(registry_path.resolve()),
        "diagnostics_path": str(diagnostics_path.resolve()),
        "refreshed_this_run": True,
        "refresh_reason": (
            "forced_refresh" if force_refresh else refresh_reason
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return registry, manifest


#%%
