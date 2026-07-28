"""Tests for workbook-owned display labels on explicit rollup groups."""

from pathlib import Path

import pandas as pd
import pytest

from codebase.mapping_tools.build_common_esto_structure import (
    apply_rollup_label_overrides_to_common_rows,
)
from codebase.mapping_tools.build_energy_balance_relationships import (
    build_esto_overrides,
)
from codebase.mapping_tools.rollup_label_overrides import (
    load_rollup_label_overrides,
)


def _esto_rules() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "input_esto_flow": "09.01.03.03 Others HP",
                "input_esto_product": "",
                "rolled_esto_flow": "09.01.03.03,09.02.03.03 Others HP",
                "rolled_esto_product": "",
                "rollup_group_id": "power_process::others_hp",
                "ROLLUP_MODE": "EXPANDING",
                "include": True,
                "Note": "",
            },
            {
                "input_esto_flow": "09.02.03.03 Others HP",
                "input_esto_product": "",
                "rolled_esto_flow": "09.01.03.03,09.02.03.03 Others HP",
                "rolled_esto_product": "",
                "rollup_group_id": "power_process::others_hp",
                "ROLLUP_MODE": "EXPANDING",
                "include": True,
                "Note": "",
            },
        ]
    )


def _override_row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "rollup_group_id": "power_process::others_hp",
        "auto_rollup_code": "09.01.03.03,09.02.03.03",
        "auto_rollup_name": "Others HP",
        "auto_rollup_label": "09.01.03.03,09.02.03.03 Others HP",
        "preferred_rollup_code": "",
        "preferred_rollup_name": "Others HP (all producers)",
        "preferred_rollup_label": "Others HP (all producers)",
        "Note": "Display only.",
    }
    row.update(changes)
    return row


def _write_workbook(
    path: Path,
    *,
    override_rows: list[dict[str, object]],
) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        _esto_rules().to_excel(writer, sheet_name="esto_rollup_rules", index=False)
        pd.DataFrame(columns=["rollup_group_id"]).to_excel(
            writer, sheet_name="leap_rollup_rules", index=False
        )
        pd.DataFrame(columns=["rollup_group_id"]).to_excel(
            writer, sheet_name="ninth_rollup_rules", index=False
        )
        pd.DataFrame(override_rows).to_excel(
            writer, sheet_name="rollup_label_overrides", index=False
        )


def test_loader_validates_guards_and_keeps_structural_code(tmp_path: Path) -> None:
    workbook_path = tmp_path / "mappings.xlsx"
    _write_workbook(workbook_path, override_rows=[_override_row()])

    result = load_rollup_label_overrides(workbook_path)

    assert result.loc[0, "rule_sheet"] == "esto_rollup_rules"
    assert result.loc[0, "rollup_axis"] == "flow"
    assert result.loc[0, "structural_rollup_label"] == (
        "09.01.03.03,09.02.03.03 Others HP"
    )
    assert result.loc[0, "preferred_rollup_code"] == "09.01.03.03,09.02.03.03"
    assert result.loc[0, "preferred_rollup_name"] == "Others HP (all producers)"
    assert result.loc[0, "preferred_rollup_label"] == "Others HP (all producers)"


def test_loader_rejects_stale_auto_label(tmp_path: Path) -> None:
    workbook_path = tmp_path / "mappings.xlsx"
    _write_workbook(
        workbook_path,
        override_rows=[_override_row(auto_rollup_label="old label")],
    )

    with pytest.raises(ValueError, match="Stale auto_rollup_label"):
        load_rollup_label_overrides(workbook_path)


def test_loader_rejects_unknown_group_id(tmp_path: Path) -> None:
    workbook_path = tmp_path / "mappings.xlsx"
    _write_workbook(
        workbook_path,
        override_rows=[_override_row(rollup_group_id="missing_group")],
    )

    with pytest.raises(ValueError, match="unknown or inactive"):
        load_rollup_label_overrides(workbook_path)


def test_stage_one_emits_preferred_common_label_without_changing_components(
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "mappings.xlsx"
    rules = _esto_rules()
    _write_workbook(workbook_path, override_rows=[_override_row()])
    label_overrides = load_rollup_label_overrides(workbook_path)

    result = build_esto_overrides(
        rules,
        rollup_label_overrides_df=label_overrides,
    )

    assert set(result["component_esto_flow"]) == {
        "09.01.03.03 Others HP",
        "09.02.03.03 Others HP",
    }
    assert set(result["preferred_common_flow_label"]) == {
        "Others HP (all producers)"
    }


def test_exact_rollup_row_relabels_display_fields_only(tmp_path: Path) -> None:
    workbook_path = tmp_path / "mappings.xlsx"
    _write_workbook(workbook_path, override_rows=[_override_row()])
    label_overrides = load_rollup_label_overrides(workbook_path)
    common_rows = pd.DataFrame(
        [
            {
                "common_row_id": "common_unchanged",
                "common_flow_code": "09.01.03.03,09.02.03.03",
                "common_flow_name": "Others HP",
                "common_flow_label": "09.01.03.03,09.02.03.03 Others HP",
                "common_product_code": "17",
                "common_product_name": "Electricity",
                "common_product_label": "17 Electricity",
                "component_esto_flow": "09.01.03.03,09.02.03.03 Others HP",
                "component_esto_product": "17 Electricity",
                "component_sign": 1,
            }
        ]
    )

    result = apply_rollup_label_overrides_to_common_rows(
        common_rows,
        label_overrides,
    )

    assert result.loc[0, "common_row_id"] == "common_unchanged"
    assert result.loc[0, "component_esto_flow"] == (
        "09.01.03.03,09.02.03.03 Others HP"
    )
    assert result.loc[0, "component_esto_product"] == "17 Electricity"
    assert result.loc[0, "component_sign"] == 1
    assert result.loc[0, "common_flow_code"] == "09.01.03.03,09.02.03.03"
    assert result.loc[0, "common_flow_name"] == "Others HP (all producers)"
    assert result.loc[0, "common_flow_label"] == "Others HP (all producers)"


def test_exact_rollup_override_does_not_hide_a_larger_flow_partition() -> None:
    structural_label = "09.01.03.03,09.02.03.03 Others HP"
    common_rows = pd.DataFrame(
        [
            {
                "common_row_id": "common_larger_partition",
                "common_flow_code": "09.01.03.03,09.02.03.03,09.99",
                "common_flow_name": "Others HP and unrelated flow",
                "common_flow_label": "09.01.03.03,09.02.03.03,09.99 Others HP and unrelated flow",
                "component_esto_flow": structural_label,
            },
            {
                "common_row_id": "common_larger_partition",
                "common_flow_code": "09.01.03.03,09.02.03.03,09.99",
                "common_flow_name": "Others HP and unrelated flow",
                "common_flow_label": "09.01.03.03,09.02.03.03,09.99 Others HP and unrelated flow",
                "component_esto_flow": "09.99 Unrelated flow",
            },
        ]
    )
    label_overrides = pd.DataFrame(
        [
            {
                "rule_sheet": "esto_rollup_rules",
                "rollup_axis": "flow",
                "structural_rollup_label": structural_label,
                "preferred_rollup_code": "09.01.03.03,09.02.03.03",
                "preferred_rollup_name": "Others HP (all producers)",
                "preferred_rollup_label": "Others HP (all producers)",
            }
        ]
    )

    result = apply_rollup_label_overrides_to_common_rows(
        common_rows,
        label_overrides,
    )

    assert result["common_flow_label"].tolist() == common_rows["common_flow_label"].tolist()
