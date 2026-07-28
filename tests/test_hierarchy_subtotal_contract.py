"""Focused tests for the canonical hierarchy/subtotal contract."""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from codebase.mapping_tools.hierarchy_subtotal_adapters import (
    build_ninth_family_conformance,
)
from codebase.mapping_tools.hierarchy_subtotal_contract import (
    AdapterTables,
    CallableDatasetAdapter,
    build_contract_frames,
    empty_observations,
    load_contract,
    write_contract,
)
from codebase.mapping_tools.hierarchy_subtotal_review import build_review_frames


def _nodes(dataset_id: str = "synthetic") -> pd.DataFrame:
    rows = []
    for axis_id, role in [("axis_1", "flow"), ("axis_2", "product")]:
        for node_id, depth in [("parent", 1), ("child_a", 2), ("child_b", 2), ("leaf", 1)]:
            rows.append({
                "dataset_id": dataset_id,
                "axis_id": axis_id,
                "axis_role": role,
                "node_id": node_id,
                "node_label": node_id,
                "depth": depth,
                "hierarchy_status": "complete",
                "source_subtotal_layout": False,
                "source_subtotal_results": False,
                "source_subtotal_other": False,
                "classification_rule": "declared ordinary child_count > 0",
                "evidence": "fixture",
                "provenance": "fixture",
            })
    return pd.DataFrame(rows)


def _edges(dataset_id: str = "synthetic") -> pd.DataFrame:
    rows = []
    for axis_id in ["axis_1", "axis_2"]:
        for child in ["child_a", "child_b"]:
            rows.append({
                "dataset_id": dataset_id,
                "axis_id": axis_id,
                "parent_node_id": "parent",
                "child_node_id": child,
                "relationship_type": "ordinary_hierarchy",
                "direction": "parent_to_child",
                "is_additive": True,
                "source_rule_id": "",
                "review_status": "declared",
                "provenance": "fixture",
            })
    rows.append({
        "dataset_id": dataset_id,
        "axis_id": "axis_1",
        "parent_node_id": "leaf",
        "child_node_id": "child_a",
        "relationship_type": "detached_diagnostic_boundary",
        "direction": "component_to_declared_target",
        "is_additive": False,
        "source_rule_id": "detached",
        "review_status": "declared",
        "provenance": "fixture",
    })
    return pd.DataFrame(rows)


def _pairs(dataset_id: str = "synthetic") -> pd.DataFrame:
    return pd.DataFrame([
        {
            "dataset_id": dataset_id,
            "axis_1_id": "axis_1",
            "axis_1_node_id": axis_1,
            "axis_2_id": "axis_2",
            "axis_2_node_id": axis_2,
            "pair_provenance": "fixture",
        }
        for axis_1, axis_2 in [
            ("parent", "leaf"),
            ("leaf", "parent"),
            ("parent", "parent"),
            ("leaf", "leaf"),
        ]
    ])


def _observations(dataset_id: str = "synthetic") -> pd.DataFrame:
    rows = []
    for axis_1, value in [("parent", 10), ("child_a", 2), ("child_b", 3)]:
        rows.append({
            "dataset_id": dataset_id,
            "source_version": "fixture-v1",
            "economy": "20_USA",
            "scenario": "reference",
            "year_or_period": "2030",
            "axis_1_node_id": axis_1,
            "axis_2_node_id": "leaf",
            "value": value,
            "source_row_id": axis_1,
            "provenance": "fixture",
        })
    return pd.DataFrame(rows)


def _adapter(
    dataset_id: str = "synthetic",
    observations: pd.DataFrame | None = None,
) -> CallableDatasetAdapter:
    def build() -> AdapterTables:
        return AdapterTables(
            dataset_id=dataset_id,
            source_version="fixture-v1",
            adapter_version="fixture-adapter-v1",
            dataset_kind="raw_source",
            nodes=_nodes(dataset_id),
            edges=_edges(dataset_id),
            pairs=_pairs(dataset_id),
            observations=observations if observations is not None else empty_observations(),
            provenance={"source": "fixture"},
        )

    return CallableDatasetAdapter(dataset_id, "fixture-adapter-v1", build)


def test_any_axis_parent_rule_covers_all_four_pair_cases() -> None:
    frames, _ = build_contract_frames([_adapter()])
    pairs = frames["canonical_source_pairs"].set_index(
        ["axis_1_node_id", "axis_2_node_id"]
    )
    assert bool(pairs.loc[("parent", "leaf"), "pair_is_subtotal"])
    assert bool(pairs.loc[("leaf", "parent"), "pair_is_subtotal"])
    assert bool(pairs.loc[("parent", "parent"), "pair_is_subtotal"])
    assert not bool(pairs.loc[("leaf", "leaf"), "pair_is_subtotal"])


def test_failed_additivity_does_not_change_structural_parenthood() -> None:
    frames, _ = build_contract_frames([_adapter(observations=_observations())])
    parent = frames["axis_nodes"].query(
        "axis_id == 'axis_1' and node_id == 'parent'"
    ).iloc[0]
    diagnostic = frames["value_conformance_diagnostics"].iloc[0]
    assert bool(parent["is_structural_parent"])
    assert diagnostic["status"] == "failed"
    assert diagnostic["reason"] == "difference_exceeds_tolerance"


def test_missing_child_is_incomplete_not_passed_or_leaf() -> None:
    observations = _observations()
    observations = observations[~observations["axis_1_node_id"].eq("child_b")]
    frames, _ = build_contract_frames([_adapter(observations=observations)])
    diagnostic = frames["value_conformance_diagnostics"].iloc[0]
    parent = frames["axis_nodes"].query(
        "axis_id == 'axis_1' and node_id == 'parent'"
    ).iloc[0]
    assert diagnostic["status"] == "children_incomplete"
    assert bool(parent["is_structural_parent"])


def test_detached_boundary_is_not_an_ordinary_parent_edge() -> None:
    frames, _ = build_contract_frames([_adapter()])
    leaf = frames["axis_nodes"].query(
        "axis_id == 'axis_1' and node_id == 'leaf'"
    ).iloc[0]
    assert not bool(leaf["is_structural_parent"])
    assert "detached_diagnostic_boundary" in set(
        frames["declared_relationship_edges"]["relationship_type"]
    )


def test_new_dataset_adapter_requires_no_core_classifier_change() -> None:
    frames, registry = build_contract_frames([_adapter("fourth_dataset")])
    assert registry[0]["dataset_id"] == "fourth_dataset"
    assert set(frames["canonical_source_pairs"]["dataset_id"]) == {"fourth_dataset"}


def test_strict_loader_rejects_stale_build_and_tampered_member(tmp_path: Path) -> None:
    frames, registry = build_contract_frames([_adapter()])
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    manifest = write_contract(
        output_dir=tmp_path / "contract",
        frames=frames,
        registry=registry,
        input_paths=[source],
        repo_root=tmp_path,
        generation_time=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )
    load_contract(tmp_path / "contract", expected_build_id=manifest["build_id"])
    with pytest.raises(ValueError, match="build_id"):
        load_contract(tmp_path / "contract", expected_build_id="stale")
    member = tmp_path / "contract" / "axis_nodes.csv"
    member.write_text(member.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_contract(tmp_path / "contract")


def test_ninth_0906_and_0908_real_semantics_fixture_are_failed_but_structural(
    tmp_path: Path,
) -> None:
    rows = []
    for family in [
        "09_06_gas_processing_plants",
        "09_08_coal_transformation",
    ]:
        base = {
            "economy": "20_USA",
            "scenarios": "reference",
            "sectors": "09_total_transformation_sector",
            "sub1sectors": family,
            "sub3sectors": "x",
            "sub4sectors": "x",
            "fuels": "08_gas",
            "subfuels": "x",
        }
        rows.extend([
            {**base, "sub2sectors": "x", "2023": 10},
            {**base, "sub2sectors": f"{family}_child_a", "2023": 2},
            {**base, "sub2sectors": f"{family}_child_b", "2023": 3},
        ])
    data_path = tmp_path / "ninth.csv"
    pd.DataFrame(rows).to_csv(data_path, index=False)

    diagnostics = build_ninth_family_conformance(data_path)

    assert set(diagnostics["status"]) == {"failed"}
    assert set(diagnostics["parent_node_id"]) == {
        "09_total_transformation_sector/09_06_gas_processing_plants",
        "09_total_transformation_sector/09_08_coal_transformation",
    }


def test_same_pair_in_two_mapping_sheets_gets_one_canonical_flag(tmp_path: Path) -> None:
    workbook = tmp_path / "mapping.xlsx"
    leap_pair = {
        "leap_sector_name_full_path": "parent",
        "raw_leap_fuel_name": "leaf",
    }
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame([{**leap_pair, "esto_flow": "leaf", "esto_product": "leaf", "leap_is_subtotal": False}]).to_excel(
            writer,
            sheet_name="leap_combined_esto",
            index=False,
        )
        pd.DataFrame([{
            "ninth_sector": "leaf",
            "ninth_fuel": "leaf",
            "esto_flow": "leaf",
            "esto_product": "leaf",
        }]).to_excel(writer, sheet_name="ninth_pairs_to_esto_pairs", index=False)
        pd.DataFrame([{**leap_pair, "ninth_sector": "leaf", "ninth_fuel": "leaf", "leap_is_subtotal": True}]).to_excel(
            writer,
            sheet_name="leap_combined_ninth",
            index=False,
        )
    exception_workbook = tmp_path / "exceptions.xlsx"
    with pd.ExcelWriter(exception_workbook, engine="openpyxl") as writer:
        for sheet in [
            "subtotal_mismatch_allowed",
            "subtotal_label_exceptions",
            "subtotal_label_overrides",
        ]:
            pd.DataFrame(columns=["enabled", "notes"]).to_excel(
                writer,
                sheet_name=sheet,
                index=False,
            )
    frames, _ = build_contract_frames([_adapter("leap")])

    review = build_review_frames(workbook, exception_workbook, frames)
    leap_cells = review["all_workbook_cells"].query("dataset_id == 'leap'")
    assert set(leap_cells["proposed_value"]) == {True}
    assert len(review["cross_sheet_conflicts"]) == 1
