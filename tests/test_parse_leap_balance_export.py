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

    assert len(parsed) == 4
    assert output_path.exists()
