from pathlib import Path

import pandas as pd
import pytest

from codebase.mapping_tools.parse_leap_balance_export import (
    parse_leap_balance_csv,
    parse_leap_balance_dir,
    parse_leap_balance_xlsx,
)


def _sheet(year: int) -> pd.DataFrame:
    return pd.DataFrame(
        [
            [f'Energy Balance for Area "Test Area"', None, None],
            [f"Scenario: Reference, Year: {year}, Units: Petajoule", None, None],
            [None, "Natural gas", "Total"],
            ["Production", 1.0, 1.0],
            ["Total Transformation", 2.0, 2.0],
        ]
    )


def _detailed_csv_sheet(*, indented: bool) -> pd.DataFrame:
    child = "   Child plant" if indented else "Child plant"
    road = "  Road" if indented else "Road"
    electricity = "    Electricity" if indented else "Electricity"
    return pd.DataFrame(
        [
            ['Energy Balance for Area "AUS test model"', None, None, None],
            ["Scenario: Target, Year: 2022, Units: Petajoule", None, None, None],
            [None, "Electricity", "Natural gas", "Total"],
            ["Production", "-", 10, 10],
            [child, 2, "-", 2],
            ["Parent plant", 2, "-", 2],
            ["Total Transformation", 2, "-", 2],
            ["Demand", 3, 4, 7],
            [road, 3, 4, 7],
            [electricity, 3, "-", 3],
            ["Total Final Energy Demand", 3, 4, 7],
            ["Unmet Requirements", "-", "-", "-"],
        ]
    )


def test_parse_leap_balance_csv_requires_hierarchy_template(tmp_path: Path) -> None:
    csv_path = tmp_path / "balance.csv"
    _detailed_csv_sheet(indented=False).to_csv(csv_path, header=False, index=False)

    with pytest.raises(ValueError, match="no leading-space hierarchy"):
        parse_leap_balance_csv(csv_path, economy_override="01_AUS")


def test_parse_leap_balance_csv_restores_validated_hierarchy(tmp_path: Path) -> None:
    csv_path = tmp_path / "balance.csv"
    template_path = tmp_path / "hierarchy.csv"
    _detailed_csv_sheet(indented=False).to_csv(csv_path, header=False, index=False)
    _detailed_csv_sheet(indented=True).to_csv(
        template_path, header=False, index=False
    )

    parsed = parse_leap_balance_csv(
        csv_path,
        economy_override="01_AUS",
        hierarchy_template_path=template_path,
    )

    assert len(parsed) == 18
    assert "Parent plant/Child plant" in set(parsed["leap_flow"])
    assert "Demand/Road/Electricity" in set(parsed["leap_flow"])
    assert parsed.loc[
        (parsed["leap_flow"] == "Production")
        & (parsed["leap_product"] == "Electricity"),
        "value",
    ].item() == 0.0


def test_parse_leap_balance_xlsx_reads_plain_year_sheets(tmp_path: Path) -> None:
    workbook_path = tmp_path / "leap_export.xlsx"
    with pd.ExcelWriter(workbook_path) as writer:
        _sheet(2060).to_excel(writer, sheet_name="2060", header=False, index=False)
        _sheet(2059).to_excel(writer, sheet_name="2059", header=False, index=False)

    parsed = parse_leap_balance_xlsx(workbook_path, economy_override="02_BD")

    assert sorted(parsed["year"].unique()) == [2059, 2060]
    assert set(parsed["economy"]) == {"02_BD"}
    assert set(parsed["leap_product"]) == {"Natural gas"}


def test_parse_leap_balance_dir_ignores_excel_lock_files(tmp_path: Path) -> None:
    workbook_path = tmp_path / "full model output REF.xlsx"
    with pd.ExcelWriter(workbook_path) as writer:
        _sheet(2060).to_excel(writer, sheet_name="2060", header=False, index=False)
    (tmp_path / "~$full model output REF.xlsx").write_bytes(b"not an Excel workbook")

    output_path = tmp_path / "raw_leap_results.csv"
    parsed = parse_leap_balance_dir(tmp_path, output_path, economy_code="20_USA")

    # Two source rows × one retained fuel; the "Total" fuel column is dropped.
    assert len(parsed) == 2
    assert output_path.exists()


def test_parse_leap_balance_dir_uses_newest_recognized_scenario_export(
    tmp_path: Path,
) -> None:
    old_ref = tmp_path / "RUS REF 0808.xlsx"
    new_ref = tmp_path / "RUS REF 0908.xlsx"
    review = tmp_path / "balance_review_16_RUS_tgt_2023.xlsx"
    with pd.ExcelWriter(old_ref) as writer:
        _sheet(2059).to_excel(writer, sheet_name="2059", header=False, index=False)
    with pd.ExcelWriter(new_ref) as writer:
        _sheet(2060).to_excel(writer, sheet_name="2060", header=False, index=False)
    with pd.ExcelWriter(review) as writer:
        _sheet(2023).to_excel(writer, sheet_name="2023", header=False, index=False)

    output_path = tmp_path / "raw_leap_results.csv"
    with pytest.warns(UserWarning, match="Multiple REF.*RUS REF 0908.xlsx"):
        parsed = parse_leap_balance_dir(
            tmp_path,
            output_path,
            economy_code="16_RUS",
        )

    assert set(parsed["year"]) == {2060}


def test_parse_leap_balance_xlsx_uses_mapping_workbook_fuel_spellings(
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "fuel_spellings.xlsx"
    raw = pd.DataFrame(
        [
            ['Energy Balance for Area "Test Area"', None, None, None, None, None],
            ["Scenario: Reference, Year: 2060, Units: Petajoule", None, None, None, None, None],
            [
                None,
                "Fuelwood and woodwaste",
                "Fuelwood & woodwaste",
                "Black liqour",
                "of which Photovoltaics",
                "Solar Photovoltaics",
            ],
            ["Production", 1.0, 2.0, 3.0, 4.0, 5.0],
            ["Total Transformation", 1.0, 2.0, 3.0, 4.0, 5.0],
        ]
    )
    with pd.ExcelWriter(workbook_path) as writer:
        raw.to_excel(writer, sheet_name="2060", header=False, index=False)

    parsed = parse_leap_balance_xlsx(workbook_path, economy_override="20_USA")

    assert set(parsed["leap_product"]) == {
        "Fuelwood and woodwaste",
        "Black liquor",
        "Solar photovoltaics",
    }


def test_parse_leap_balance_xlsx_normalizes_stock_and_statistical_flow_aliases(
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "balance_flow_aliases.xlsx"
    raw = pd.DataFrame(
        [
            ['Energy Balance for Area "Test Area"', None],
            ["Scenario: Reference, Year: 2022, Units: Petajoule", None],
            [None, "Natural gas"],
            ["From Stocks", 1.0],
            ["Statistical Differences", 2.0],
            ["Total Transformation", 3.0],
        ]
    )
    with pd.ExcelWriter(workbook_path) as writer:
        raw.to_excel(writer, sheet_name="2022", header=False, index=False)

    parsed = parse_leap_balance_xlsx(workbook_path, economy_override="01_AUS")

    assert set(parsed["leap_flow"]) == {
        "Stock Changes",
        "Statistical Differences",
        "Total Transformation",
    }
