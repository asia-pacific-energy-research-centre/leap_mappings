from pathlib import Path

import pandas as pd

from codebase.mapping_tools.parse_leap_balance_export import parse_leap_balance_dir, parse_leap_balance_xlsx


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


def test_parse_leap_balance_xlsx_uses_mapping_workbook_fuel_spellings(
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "fuel_spellings.xlsx"
    raw = pd.DataFrame(
        [
            ['Energy Balance for Area "Test Area"', None, None, None, None],
            ["Scenario: Reference, Year: 2060, Units: Petajoule", None, None, None, None],
            [
                None,
                "Fuelwood and woodwaste",
                "Black liqour",
                "of which Photovoltaics",
                "Solar",
            ],
            ["Production", 1.0, 2.0, 3.0, 4.0],
            ["Total Transformation", 1.0, 2.0, 3.0, 4.0],
        ]
    )
    with pd.ExcelWriter(workbook_path) as writer:
        raw.to_excel(writer, sheet_name="2060", header=False, index=False)

    parsed = parse_leap_balance_xlsx(workbook_path, economy_override="20_USA")

    assert set(parsed["leap_product"]) == {
        "Fuelwood & woodwaste",
        "Black liquor",
        "Solar photovoltaics",
        "Solar",
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
