"""Tests for paste-ready rows required by mapped ESTO pairs."""

from pathlib import Path

import pandas as pd

from codebase.mapping_tools.build_missing_mapped_esto_rows import (
    build_missing_mapped_esto_rows,
    extract_simple_esto_code,
    write_missing_mapped_esto_rows,
)


def _write_mapping_workbook(path: Path) -> None:
    leap_rows = pd.DataFrame(
        [
            {
                "leap_sector_name_full_path": "Production",
                "raw_leap_fuel_name": "Ammonia",
                "esto_flow": "01 Production",
                "esto_product": "16.10 Ammonia",
                "esto_pair_is_subtotal": False,
            },
            {
                "leap_sector_name_full_path": "Total final consumption",
                "raw_leap_fuel_name": "E-fuel",
                "esto_flow": "12 Total final consumption",
                "esto_product": "16.11 E-fuel",
                "esto_pair_is_subtotal": False,
            },
            {
                "leap_sector_name_full_path": "Buildings",
                "raw_leap_fuel_name": "E-fuel",
                "esto_flow": "16.01-16.02 Buildings",
                "esto_product": "16.11 E-fuel",
                "esto_pair_is_subtotal": False,
            },
        ]
    )
    ninth_rows = pd.DataFrame(
        [
            {
                "9th_sector": "09_total_transformation_sector",
                "9th_fuel": "16_x_efuel",
                "esto_flow": "09 Total transformation sector",
                "esto_product": "16.11 E-fuel",
                "esto_pair_is_subtotal": True,
            },
            {
                "9th_sector": "01_production",
                "9th_fuel": "06_x_other_hydrocarbons",
                "esto_flow": "01 Production",
                "esto_product": "06.04 Additives/ oxygenates",
                "esto_pair_is_subtotal": False,
            },
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        leap_rows.to_excel(writer, sheet_name="leap_combined_esto", index=False)
        ninth_rows.to_excel(writer, sheet_name="ninth_pairs_to_esto_pairs", index=False)


def _write_esto_source(path: Path) -> None:
    rows = pd.DataFrame(
        [
            {
                "economy": "01AAA",
                "flows": "01 Production",
                "products": "16.10 Ammonia",
                "is_subtotal": False,
                "2022": 0.0,
                "2023": 0.0,
            },
            {
                "economy": "01AAA",
                "flows": "01 Production",
                "products": "06.04 Additives and oxygenates",
                "is_subtotal": False,
                "2022": 1.0,
                "2023": 2.0,
            },
            {
                "economy": "02BBB",
                "flows": "01 Production",
                "products": "06.04 Additives and oxygenates",
                "is_subtotal": False,
                "2022": 3.0,
                "2023": 4.0,
            },
        ]
    )
    rows.to_csv(path, index=False)


def test_extract_simple_esto_code_rejects_generated_categories() -> None:
    assert extract_simple_esto_code("16.10 Ammonia") == "16.10"
    assert extract_simple_esto_code("09.01.01,09.02.01 Electricity plants") == ""
    assert extract_simple_esto_code("16.01-16.02 Buildings") == ""


def test_build_missing_rows_is_minimal_and_paste_ready(tmp_path: Path) -> None:
    workbook_path = tmp_path / "mappings.xlsx"
    source_path = tmp_path / "esto.csv"
    _write_mapping_workbook(workbook_path)
    _write_esto_source(source_path)

    rows, audit = build_missing_mapped_esto_rows(source_path, workbook_path)

    assert list(rows.columns) == ["economy", "flows", "products", "is_subtotal", "2022", "2023"]
    assert len(rows) == 5
    assert set(rows["economy"]) == {"01AAA", "02BBB"}
    assert (rows[["2022", "2023"]] == 0).all().all()

    # Ammonia already exists for 01AAA, so only the missing 02BBB row is added.
    ammonia = rows[rows["products"].eq("16.10 Ammonia")]
    assert ammonia["economy"].tolist() == ["02BBB"]

    # A punctuation-only label difference has the same ESTO code and adds no row.
    assert not rows["products"].str.contains("Additives", case=False).any()

    # Generated range/list categories are not physical ESTO source rows.
    assert not rows["flows"].str.contains("16.01-16.02", regex=False).any()

    transformation = rows[rows["flows"].eq("09 Total transformation sector")]
    assert len(transformation) == 2
    assert transformation["is_subtotal"].eq(True).all()  # noqa: E712
    assert len(audit) == 3


def test_writer_creates_one_source_shaped_csv_and_summary(tmp_path: Path) -> None:
    workbook_path = tmp_path / "mappings.xlsx"
    source_path = tmp_path / "esto.csv"
    output_dir = tmp_path / "outputs"
    _write_mapping_workbook(workbook_path)
    _write_esto_source(source_path)

    summary = write_missing_mapped_esto_rows([source_path], workbook_path, output_dir)

    output_path = output_dir / "esto_missing_mapped_rows.csv"
    assert output_path.exists()
    assert (output_dir / "missing_mapped_esto_rows_summary.csv").exists()
    assert summary.loc[0, "missing_pair_count"] == 3
    assert summary.loc[0, "paste_ready_row_count"] == 5


def test_build_missing_rows_supports_source_without_subtotal_column(tmp_path: Path) -> None:
    workbook_path = tmp_path / "mappings.xlsx"
    source_path = tmp_path / "esto_without_subtotals.csv"
    _write_mapping_workbook(workbook_path)
    source = pd.DataFrame(
        [
            {
                "economy": "01AAA",
                "flows": "01 Production",
                "products": "06.04 Additives and oxygenates",
                "2022": 1.0,
            }
        ]
    )
    source.to_csv(source_path, index=False)

    rows, _audit = build_missing_mapped_esto_rows(source_path, workbook_path)

    assert list(rows.columns) == ["economy", "flows", "products", "2022"]
    assert "is_subtotal" not in rows.columns
    assert (rows["2022"] == 0).all()
