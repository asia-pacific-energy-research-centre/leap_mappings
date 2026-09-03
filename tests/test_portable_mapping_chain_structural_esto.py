from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from codebase.mapping_tools.apply_common_esto_structure import (
    run_common_esto_comparison_fast_path,
)
from codebase.mapping_tools.esto_extended_catalogue import build_structural_catalogue
from codebase.portable_mapping_chain import (
    ordinary_esto_source_paths,
    prepare_esto_extended_exact_rows,
    run_mapping_chain,
    validate_esto_extended_catalogue,
)


def _write_mapping_workbook(path: Path) -> None:
    mappings = pd.DataFrame([
        {
            "esto_flow": "09.01.01 Gas",
            "esto_product": "08 Gas",
            "duplicate_to_remove": False,
            "remove_row": False,
            "esto_dataset_scope": "BOTH",
        },
        {
            "esto_flow": "09.01.01.04 Gas_CCUS",
            "esto_product": "08 Gas",
            "duplicate_to_remove": False,
            "remove_row": False,
            "esto_dataset_scope": "ESTO_EXTENDED",
        },
        {
            "esto_flow": "09.01.01.01 Gas combustion",
            "esto_product": "08 Gas",
            "duplicate_to_remove": False,
            "remove_row": False,
            "esto_dataset_scope": "BOTH",
        },
    ])
    rollups = pd.DataFrame([{
        "input_esto_flow": "09.01.01.01 Gas combustion",
        "input_esto_product": "08 Gas",
        "rolled_esto_flow": "09.01.01 Gas",
        "rolled_esto_product": "08 Gas",
        "include": True,
        "ROLLUP_MODE": "NON_EXPANDING",
        "rollup_group_id": "gas_boundary",
        "esto_dataset_scope": "ESTO_EXTENDED",
    }])
    with pd.ExcelWriter(path) as writer:
        mappings.to_excel(writer, sheet_name="leap_combined_esto", index=False)
        mappings.iloc[0:0].to_excel(
            writer, sheet_name="ninth_pairs_to_esto_pairs", index=False,
        )
        rollups.to_excel(writer, sheet_name="esto_rollup_rules", index=False)


def _common_rows() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "comparison_scope": "esto_extended",
            "component_esto_flow": "09.01.01.01 Gas combustion",
            "component_esto_product": "08 Gas",
            "common_row_id": "gas",
            "common_flow_code": "09.01.01",
            "common_flow_name": "Gas",
            "common_flow_label": "09.01.01 Gas",
            "common_product_code": "08",
            "common_product_name": "Gas",
            "common_product_label": "08 Gas",
            "component_sign": 1,
        },
        {
            "comparison_scope": "esto_extended",
            "component_esto_flow": "09.01.01.04 Gas_CCUS",
            "component_esto_product": "08 Gas",
            "common_row_id": "gas_ccus",
            "common_flow_code": "09.01.01.04",
            "common_flow_name": "Gas CCUS",
            "common_flow_label": "09.01.01.04 Gas_CCUS",
            "common_product_code": "08",
            "common_product_name": "Gas",
            "common_product_label": "08 Gas",
            "component_sign": 1,
        },
    ])


def test_portable_extended_scope_reuses_ordinary_gas_without_gas_ccus_history(
    tmp_path: Path,
) -> None:
    workbook = tmp_path / "mappings.xlsx"
    catalogue_path = tmp_path / "esto_extended_catalogue.csv"
    ordinary_path = tmp_path / "esto_results_exact_rows.csv"
    common_rows_path = tmp_path / "common_esto_rows.csv"
    output_dir = tmp_path / "output"
    lineage_path = output_dir / "esto_component_to_common_row_lineage.csv.gz"
    _write_mapping_workbook(workbook)
    build_structural_catalogue(workbook, catalogue_path)
    validate_esto_extended_catalogue(catalogue_path, workbook)
    pd.DataFrame([{
        "source_system": "ESTO",
        "economy": "01_AUS",
        "scenario": "historical",
        "year": 2022,
        "esto_flow": "09.01.01.01 Gas combustion",
        "esto_product": "08 Gas",
        "fact_value_provenance": "observed_ordinary_esto",
        "value": 10.0,
    }]).to_csv(ordinary_path, index=False)
    _common_rows().to_csv(common_rows_path, index=False)

    source_paths = ordinary_esto_source_paths(ordinary_path)
    assert source_paths["ESTO"] == source_paths["ESTO_EXTENDED"] == ordinary_path
    comparison, _, missing = run_common_esto_comparison_fast_path(
        source_paths=source_paths,
        common_rows_path=common_rows_path,
        output_dir=output_dir,
        default_economy="01_AUS",
        active_component_abs_tolerance=0.0,
        comparison_scope_systems={"esto_extended": {"ESTO_EXTENDED"}},
        source_system_overrides={"ESTO_EXTENDED": "ESTO_EXTENDED"},
        esto_component_lineage_output_path=lineage_path,
        run_id="portable_structural_esto",
        run_timestamp_utc="2026-09-03T00:00:00+00:00",
    )

    extended = comparison.loc[comparison["source_system"].eq("ESTO_EXTENDED")]
    assert missing.empty
    assert extended["common_row_id"].tolist() == ["gas"]
    assert extended["value"].sum() == 10.0
    assert "gas_ccus" not in set(extended["common_row_id"])
    assert set(extended["fact_value_provenance"]) == {"observed_ordinary_esto"}
    fact = pd.read_csv(output_dir / "common_esto_comparison_fact.csv.gz")
    lineage = pd.read_csv(lineage_path)
    assert set(fact["fact_value_provenance"]) == {"observed_ordinary_esto"}
    assert set(lineage["fact_value_provenance"]) == {"observed_ordinary_esto"}


def test_portable_contract_rejects_numeric_extended_inputs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="structural-only"):
        prepare_esto_extended_exact_rows(
            bundled_exact_rows=tmp_path / "legacy.csv.gz",
            esto_extended_table=tmp_path / "esto_extended.csv",
            relationships_path=tmp_path / "relationships.csv",
            mapping_workbook_path=tmp_path / "mappings.xlsx",
            work_dir=tmp_path,
            notes=[],
        )

    with pytest.raises(ValueError, match="esto_extended_table_path is retired"):
        run_mapping_chain({
            "economy": "01_AUS",
            "export_dir": str(tmp_path),
            "work_dir": str(tmp_path / "work"),
            "config": {"esto_extended_table_path": str(tmp_path / "legacy.csv")},
        })


def test_portable_catalogue_validation_rejects_numeric_columns(tmp_path: Path) -> None:
    workbook = tmp_path / "mappings.xlsx"
    catalogue_path = tmp_path / "esto_extended_catalogue.csv"
    _write_mapping_workbook(workbook)
    catalogue = build_structural_catalogue(workbook, catalogue_path)
    catalogue["2022"] = 10.0
    catalogue.to_csv(catalogue_path, index=False)

    with pytest.raises(ValueError, match="invalid_numeric_column"):
        validate_esto_extended_catalogue(catalogue_path, workbook)
