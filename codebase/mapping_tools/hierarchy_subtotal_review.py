#%%
"""Create cell-level review and exception-audit tables without workbook writes."""

#%%
from __future__ import annotations

from pathlib import Path

import pandas as pd


SIDE_CONFIGS = [
    {
        "sheet": "leap_combined_esto",
        "dataset_id": "leap",
        "axis_1_column": "leap_sector_name_full_path",
        "axis_2_column": "raw_leap_fuel_name",
        "flag_column": "leap_is_subtotal",
    },
    {
        "sheet": "leap_combined_esto",
        "dataset_id": "esto",
        "axis_1_column": "esto_flow",
        "axis_2_column": "esto_product",
        "flag_column": "esto_pair_is_subtotal",
    },
    {
        "sheet": "ninth_pairs_to_esto_pairs",
        "dataset_id": "ninth",
        "axis_1_column": "ninth_sector",
        "axis_2_column": "ninth_fuel",
        "flag_column": "ninth_pair_is_subtotal",
    },
    {
        "sheet": "ninth_pairs_to_esto_pairs",
        "dataset_id": "esto",
        "axis_1_column": "esto_flow",
        "axis_2_column": "esto_product",
        "flag_column": "esto_pair_is_subtotal",
    },
    {
        "sheet": "leap_combined_ninth",
        "dataset_id": "leap",
        "axis_1_column": "leap_sector_name_full_path",
        "axis_2_column": "raw_leap_fuel_name",
        "flag_column": "leap_is_subtotal",
    },
    {
        "sheet": "leap_combined_ninth",
        "dataset_id": "ninth",
        "axis_1_column": "ninth_sector",
        "axis_2_column": "ninth_fuel",
        "flag_column": "ninth_pair_is_subtotal",
    },
]


def _text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _truthy(value: object) -> bool:
    return value is True or _text(value).casefold() in {"true", "1", "yes"}


def _active(frame: pd.DataFrame) -> pd.DataFrame:
    if "duplicate_to_remove" not in frame:
        return frame.copy()
    return frame[~frame["duplicate_to_remove"].map(_truthy)].copy()


def _node_aliases(nodes: pd.DataFrame) -> dict[tuple[str, str, str], str]:
    aliases: dict[tuple[str, str, str], str] = {}
    for (dataset_id, axis_id), group in nodes.groupby(["dataset_id", "axis_id"]):
        for node_id in group["node_id"].astype(str):
            aliases[(dataset_id, axis_id, node_id)] = node_id
        labels = group.groupby(group["node_label"].astype(str))["node_id"].agg(
            lambda values: sorted(set(map(str, values)))
        )
        for label, node_ids in labels.items():
            if len(node_ids) == 1:
                aliases[(dataset_id, axis_id, label)] = node_ids[0]
    return aliases


def build_review_frames(
    workbook_path: Path,
    exception_workbook_path: Path,
    contract_frames: dict[str, pd.DataFrame],
    workbook_sheets: dict[str, pd.DataFrame] | None = None,
) -> dict[str, pd.DataFrame]:
    """Build review-only tables keyed to exact workbook rows and cells."""
    nodes = contract_frames["axis_nodes"].copy()
    pairs = contract_frames["canonical_source_pairs"].copy()
    aliases = _node_aliases(nodes)
    pair_lookup = pairs.set_index(
        ["dataset_id", "axis_1_node_id", "axis_2_node_id"]
    ).to_dict("index")

    if workbook_sheets is None:
        workbook_sheets = pd.read_excel(
            workbook_path,
            sheet_name=sorted({config["sheet"] for config in SIDE_CONFIGS}),
            dtype=object,
        )
    sheets = {
        sheet: _active(workbook_sheets[sheet])
        for sheet in sorted({config["sheet"] for config in SIDE_CONFIGS})
    }
    cell_records: list[dict[str, object]] = []
    for config in SIDE_CONFIGS:
        frame = sheets[config["sheet"]]
        for row_index, row in frame.iterrows():
            dataset_id = config["dataset_id"]
            if dataset_id == "esto":
                scope = _text(row.get("esto_dataset_scope")).casefold()
                if "extended" in scope:
                    dataset_id = "esto_extended"
            raw_axis_1 = _text(row.get(config["axis_1_column"]))
            raw_axis_2 = _text(row.get(config["axis_2_column"]))
            if not raw_axis_1 or not raw_axis_2:
                continue
            axis_1 = aliases.get((dataset_id, "axis_1", raw_axis_1), raw_axis_1)
            axis_2 = aliases.get((dataset_id, "axis_2", raw_axis_2), raw_axis_2)
            evidence = pair_lookup.get((dataset_id, axis_1, axis_2), {})
            proposed = evidence.get("pair_is_subtotal", pd.NA)
            current = row.get(config["flag_column"], pd.NA)
            current_bool = _truthy(current) if not pd.isna(current) else pd.NA
            proposed_bool = (
                _truthy(proposed) if not pd.isna(proposed) else pd.NA
            )
            cell_records.append({
                "mapping_sheet": config["sheet"],
                "excel_row": int(row_index) + 2,
                "flag_column": config["flag_column"],
                "dataset_id": dataset_id,
                "axis_1_column": config["axis_1_column"],
                "axis_1_source_key": raw_axis_1,
                "axis_1_node_id": axis_1,
                "axis_1_is_structural_parent": evidence.get(
                    "axis_1_is_structural_parent",
                    pd.NA,
                ),
                "axis_1_hierarchy_status": evidence.get(
                    "axis_1_hierarchy_status",
                    "unresolved",
                ),
                "axis_2_column": config["axis_2_column"],
                "axis_2_source_key": raw_axis_2,
                "axis_2_node_id": axis_2,
                "axis_2_is_structural_parent": evidence.get(
                    "axis_2_is_structural_parent",
                    pd.NA,
                ),
                "axis_2_hierarchy_status": evidence.get(
                    "axis_2_hierarchy_status",
                    "unresolved",
                ),
                "current_value": current_bool,
                "proposed_value": proposed_bool,
                "change_required": (
                    current_bool != proposed_bool
                    if not pd.isna(current_bool) and not pd.isna(proposed_bool)
                    else pd.NA
                ),
                "every_node_resolved": evidence.get("every_node_resolved", False),
                "classification_rule": evidence.get("classification_rule", ""),
                "source_signal_disagreement": evidence.get(
                    "source_signal_disagreement",
                    pd.NA,
                ),
                "review_state": evidence.get("review_state", "review_required"),
            })
    cells = pd.DataFrame(cell_records)

    pair_review = pairs.copy()
    occurrences = (
        cells.groupby(["dataset_id", "axis_1_node_id", "axis_2_node_id"], dropna=False)
        .agg(
            workbook_occurrences=("excel_row", "size"),
            mapping_sheets=("mapping_sheet", lambda values: ";".join(sorted(set(values)))),
            current_values=(
                "current_value",
                lambda values: ";".join(sorted(set(map(str, values.dropna())))),
            ),
            affected_cells=(
                "change_required",
                lambda values: int(sum(value is True for value in values)),
            ),
        )
        .reset_index()
    )
    pair_review = pair_review.merge(
        occurrences,
        on=["dataset_id", "axis_1_node_id", "axis_2_node_id"],
        how="left",
    )
    pair_review["cross_sheet_conflict"] = pair_review["current_values"].fillna("").str.contains(";")

    conflicts = pair_review[
        pair_review["cross_sheet_conflict"].fillna(False).map(_truthy)
    ].copy()
    unresolved = pair_review[
        ~pair_review["every_node_resolved"].fillna(False).map(_truthy)
    ].copy()
    changes = cells[cells["change_required"].fillna(False).map(_truthy)].copy()

    exception_frames: list[pd.DataFrame] = []
    exception_book = pd.ExcelFile(exception_workbook_path)
    for sheet in [
        "subtotal_mismatch_allowed",
        "subtotal_label_exceptions",
        "subtotal_label_overrides",
    ]:
        if sheet not in exception_book.sheet_names:
            continue
        frame = pd.read_excel(exception_workbook_path, sheet_name=sheet, dtype=object)
        frame = frame[frame.get("enabled", False).map(_truthy)].copy()
        notes = frame.get("notes", pd.Series("", index=frame.index)).fillna("").astype(str)
        generic = notes.str.casefold().str.contains(
            "retain current|reviewed subtotal decision",
            regex=True,
        )
        frame.insert(0, "exception_sheet", sheet)
        frame.insert(1, "exception_excel_row", frame.index + 2)
        frame.insert(2, "audit_classification", generic.map({
            True: "unresolved_generic_reason",
            False: "requires_contract_join_review",
        }))
        exception_frames.append(frame)
    exception_audit = (
        pd.concat(exception_frames, ignore_index=True, sort=False)
        if exception_frames
        else pd.DataFrame()
    )

    summary = pd.DataFrame([
        {"metric": "canonical_pairs", "value": len(pair_review)},
        {"metric": "workbook_cells_reviewed", "value": len(cells)},
        {"metric": "proposed_cell_changes", "value": len(changes)},
        {"metric": "cross_sheet_conflicting_pairs", "value": len(conflicts)},
        {"metric": "unresolved_pairs", "value": len(unresolved)},
        {"metric": "enabled_exception_rows_audited", "value": len(exception_audit)},
    ])
    return {
        "summary": summary,
        "canonical_pair_review": pair_review,
        "affected_workbook_cells": changes,
        "all_workbook_cells": cells,
        "cross_sheet_conflicts": conflicts,
        "unresolved_pairs": unresolved,
        "exception_audit": exception_audit,
    }


def write_review_csvs(
    output_dir: Path,
    frames: dict[str, pd.DataFrame],
) -> None:
    """Write narrow intermediates used by the verified workbook builder."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False, lineterminator="\n")


#%%
