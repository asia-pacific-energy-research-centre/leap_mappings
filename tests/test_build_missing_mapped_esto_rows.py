"""Tests for reviewed, paste-ready ESTO balance rows."""

from pathlib import Path

import pandas as pd

from codebase.mapping_tools.build_missing_mapped_esto_rows import (
    build_commercial_public_services_unallocated_rows,
    build_missing_mapped_esto_rows,
    build_reviewed_flow_product_filter_audit,
    extract_simple_esto_code,
    write_missing_mapped_esto_rows,
)


def _write_mapping_workbook(path: Path) -> None:
    mappings = pd.DataFrame(
        [
            {
                "9th_sector": "09_13_01_electrolysers",
                "9th_fuel": "16_x_hydrogen",
                "esto_flow": "09.13.01 Electrolysers",
                "esto_product": "16.12 Hydrogen",
                "esto_pair_is_subtotal": False,
            },
            {
                "9th_sector": "09_13_02_smr_wo_ccs",
                "9th_fuel": "08_01_natural_gas",
                "esto_flow": "09.13.02 SMR wo CCS",
                "esto_product": "08.01 Natural gas",
                "esto_pair_is_subtotal": False,
            },
            {
                "9th_sector": "09_06_02_liquefaction_regasification_plants",
                "9th_fuel": "07_08_fuel_oil",
                "esto_flow": "09.06.02 Liquefaction/regasification plants",
                "esto_product": "07.08 Fuel oil",
                "esto_pair_is_subtotal": False,
            },
            {
                "9th_sector": "09_06_02_liquefaction_regasification_plants",
                "9th_fuel": "08_01_natural_gas",
                "esto_flow": "09.06.02 Liquefaction/regasification plants",
                "esto_product": "08.01 Natural gas",
                "esto_pair_is_subtotal": False,
            },
            {
                "9th_sector": "09_06_02_liquefaction_regasification_plants",
                "9th_fuel": "08_02_lng",
                "esto_flow": "09.06.02 Liquefaction/regasification plants",
                "esto_product": "08.02 LNG",
                "esto_pair_is_subtotal": False,
            },
            {
                "9th_sector": "09_06_02_liquefaction_regasification_plants",
                "9th_fuel": "01_coal",
                "esto_flow": "09.06.02 Liquefaction/regasification plants",
                "esto_product": "01 Coal",
                "esto_pair_is_subtotal": True,
            },
            {
                "9th_sector": "16_01_01_commercial_and_public_services",
                "9th_fuel": "17_electricity",
                "esto_flow": "16.01 Commercial and public services",
                "esto_product": "17 Electricity",
                "esto_pair_is_subtotal": False,
            },
            {
                "9th_sector": "16_01_01_commercial_and_public_services",
                "9th_fuel": "08_01_natural_gas",
                "esto_flow": "16.01 Commercial and public services",
                "esto_product": "08.01 Natural gas",
                "esto_pair_is_subtotal": False,
            },
            {
                "9th_sector": "16_01_01_commercial_and_public_services",
                "9th_fuel": "09_nuclear",
                "esto_flow": "16.01 Commercial and public services",
                "esto_product": "09 Nuclear",
                "esto_pair_is_subtotal": False,
            },
            {
                "9th_sector": "01_production",
                "9th_fuel": "01_coal",
                "esto_flow": "01 Production",
                "esto_product": "01 Coal",
                "esto_pair_is_subtotal": True,
            },
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        mappings.to_excel(writer, sheet_name="ninth_pairs_to_esto_pairs", index=False)


def _ninth_row(
    economy: str,
    sector: str,
    fuel: str,
    value_2023: float,
) -> dict[str, object]:
    return {
        "economy": economy,
        "sectors": sector,
        "sub1sectors": "x",
        "sub2sectors": "x",
        "sub3sectors": "x",
        "sub4sectors": "x",
        "fuels": fuel,
        "subfuels": "x",
        "2022": 0.0,
        "2023": value_2023,
    }


def _write_ninth_source(path: Path) -> None:
    rows = pd.DataFrame(
        [
            # Reviewed mapping and non-zero: must generate one economy-specific row.
            _ninth_row("01_AAA", "09_13_01_electrolysers", "16_x_hydrogen", 5.0),
            # Reviewed new flow but zero-only: must not generate a Ninth-driven row.
            _ninth_row("01_AAA", "09_13_02_smr_wo_ccs", "08_01_natural_gas", 0.0),
            # Non-zero 09.06 mapping: Fuel oil must be present under both LNG split flows.
            _ninth_row(
                "02_BBB",
                "09_06_02_liquefaction_regasification_plants",
                "07_08_fuel_oil",
                -3.0,
            ),
            _ninth_row(
                "01_AAA",
                "09_06_02_liquefaction_regasification_plants",
                "08_01_natural_gas",
                -4.0,
            ),
            _ninth_row(
                "01_AAA",
                "09_06_02_liquefaction_regasification_plants",
                "08_02_lng",
                4.0,
            ),
            _ninth_row(
                "01_AAA",
                "09_06_02_liquefaction_regasification_plants",
                "01_coal",
                0.0,
            ),
            _ninth_row(
                "01_AAA",
                "16_01_01_commercial_and_public_services",
                "17_electricity",
                10.0,
            ),
            _ninth_row(
                "02_BBB",
                "16_01_01_commercial_and_public_services",
                "08_01_natural_gas",
                2.0,
            ),
            _ninth_row(
                "01_AAA",
                "16_01_01_commercial_and_public_services",
                "09_nuclear",
                0.0,
            ),
            # Non-zero but unreviewed target: no Ninth-driven production row.
            _ninth_row("01_AAA", "01_production", "01_coal", 7.0),
            # Non-zero but unmapped: no invented output row.
            _ninth_row("01_AAA", "09_13_03_smr_w_ccs", "16_x_unmapped", 9.0),
        ]
    )
    rows.to_csv(path, index=False)


def _write_esto_source(path: Path) -> None:
    rows = pd.DataFrame(
        [
            {
                "economy": "01AAA",
                "flows": "16.01 Commercial and public services",
                "products": "17 Electricity",
                "is_subtotal": "FALSE",
                "2022": 10.0,
                "2023": 11.0,
            },
            {
                "economy": "01AAA",
                "flows": "16.01 Commercial and public services",
                "products": "08.01 Natural gas",
                "is_subtotal": "FALSE",
                "2022": 2.0,
                "2023": 3.0,
            },
            {
                "economy": "02BBB",
                "flows": "16.01 Commercial and public services",
                "products": "17 Electricity",
                "is_subtotal": "FALSE",
                "2022": 4.0,
                "2023": 5.0,
            },
            # A non-zero ESTO 09.06 fuel expands the LNG split product set.
            {
                "economy": "01AAA",
                "flows": "09.06.02 Liquefaction/regasification plants",
                "products": "08.01 Natural gas",
                "is_subtotal": "FALSE",
                "2022": -6.0,
                "2023": -7.0,
            },
            {
                "economy": "01AAA",
                "flows": "09.06.02 Liquefaction/regasification plants",
                "products": "01 Coal",
                "is_subtotal": "TRUE",
                "2022": -1.0,
                "2023": -1.0,
            },
            {
                "economy": "01AAA",
                "flows": "09.06.02 Liquefaction/regasification plants",
                "products": "01.01 Coking coal",
                "is_subtotal": "TRUE",
                "2022": -1.0,
                "2023": -1.0,
            },
            # Existing required row must not be duplicated.
            {
                "economy": "01AAA",
                "flows": "09.06.02.01 Liquefaction",
                "products": "08.01 Natural gas",
                "is_subtotal": "FALSE",
                "2022": 0.0,
                "2023": 0.0,
            },
        ]
    )
    rows.to_csv(path, index=False)


def _fixture_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    workbook_path = tmp_path / "mappings.xlsx"
    ninth_path = tmp_path / "ninth.csv"
    esto_path = tmp_path / "esto.csv"
    _write_mapping_workbook(workbook_path)
    _write_ninth_source(ninth_path)
    _write_esto_source(esto_path)
    return workbook_path, ninth_path, esto_path


def test_extract_simple_esto_code_rejects_generated_categories() -> None:
    assert extract_simple_esto_code("16.10 Ammonia") == "16.10"
    assert extract_simple_esto_code("09.01.01,09.02.01 Electricity plants") == ""
    assert extract_simple_esto_code("16.01-16.02 Buildings") == ""


def test_lng_rows_require_nonzero_exact_ninth_sector_fuel_pairs(tmp_path: Path) -> None:
    workbook_path, ninth_path, esto_path = _fixture_paths(tmp_path)

    rows, audit = build_missing_mapped_esto_rows(esto_path, workbook_path, ninth_path)
    always = audit[audit["requirement_source"].eq("always_required")]

    # Only products with non-zero data at the exact reviewed Ninth sector survive.
    expected_products = {
        "07.08 Fuel oil",
        "08.01 Natural gas",
        "08.02 LNG",
    }
    for flow in ["09.06.02.01 Liquefaction", "09.06.02.02 Regasification"]:
        flow_rows = always[always["flows"].eq(flow)]
        assert expected_products.issubset(set(flow_rows["products"]))
        assert set(flow_rows.loc[flow_rows["products"].eq("07.08 Fuel oil"), "economy"]) == {
            "01AAA",
            "02BBB",
        }
        assert not flow_rows["products"].isin(["01 Coal", "01.01 Coking coal"]).any()
        assert set(flow_rows["source_ninth_sector"]) == {
            "09_06_02_liquefaction_regasification_plants"
        }

    # The existing 01AAA liquefaction/natural-gas row is not repeated.
    existing_key = (
        rows["economy"].eq("01AAA")
        & rows["flows"].eq("09.06.02.01 Liquefaction")
        & rows["products"].eq("08.01 Natural gas")
    )
    assert not existing_key.any()

    assert set(flow_rows["is_subtotal"]) == {False}


def test_ninth_driven_rows_require_reviewed_mapping_nonzero_and_missing(tmp_path: Path) -> None:
    workbook_path, ninth_path, esto_path = _fixture_paths(tmp_path)

    rows, audit = build_missing_mapped_esto_rows(esto_path, workbook_path, ninth_path)
    ninth_rows = audit[audit["requirement_source"].eq("ninth_driven")]

    hydrogen = ninth_rows[
        ninth_rows["flows"].eq("09.13.01 Electrolysers")
        & ninth_rows["products"].eq("16.12 Hydrogen")
    ]
    assert hydrogen[["economy", "source_ninth_sector", "source_ninth_fuel"]].to_dict("records") == [
        {
            "economy": "01AAA",
            "source_ninth_sector": "09_13_01_electrolysers",
            "source_ninth_fuel": "16_x_hydrogen",
        }
    ]

    # Zero-only reviewed, unreviewed mapped, and non-zero unmapped rows create nothing.
    assert not ninth_rows["flows"].eq("09.13.02 SMR wo CCS").any()
    assert not ninth_rows["flows"].eq("01 Production").any()
    assert not rows["products"].astype(str).str.contains("unmapped", case=False).any()


def test_structural_completion_covers_every_parent_economy_product_without_ninth_evidence(tmp_path: Path) -> None:
    workbook_path, ninth_path, esto_path = _fixture_paths(tmp_path)

    _rows, audit = build_missing_mapped_esto_rows(esto_path, workbook_path, ninth_path)
    completion = audit[audit["requirement_source"].eq("structural_completion")]

    assert set(map(tuple, completion[["economy", "products"]].to_records(index=False))) == {
        ("01AAA", "17 Electricity"),
        ("01AAA", "08.01 Natural gas"),
        ("02BBB", "17 Electricity"),
    }
    assert completion["flows"].eq("16.01.99 Commercial and public services unallocated").all()
    assert completion["source_ninth_sector"].eq(
        "16_01_01_commercial_and_public_services"
    ).all()


def test_commercial_unallocated_equals_parent_when_datacentres_are_absent(tmp_path: Path) -> None:
    _workbook_path, _ninth_path, esto_path = _fixture_paths(tmp_path)

    insert_rows, update_rows, validation = build_commercial_public_services_unallocated_rows(
        esto_csv_path=esto_path,
        eligible_product_codes={"08.01", "17"},
    )

    assert update_rows.empty
    natural_gas = insert_rows[
        insert_rows["economy"].eq("01AAA")
        & insert_rows["products"].eq("08.01 Natural gas")
    ].iloc[0]
    assert float(natural_gas["2022"]) == 2.0
    assert float(natural_gas["2023"]) == 3.0
    assert validation["reconciles_within_tolerance"].all()


def test_commercial_unallocated_subtracts_datacentres_and_flags_negative_values(tmp_path: Path) -> None:
    _workbook_path, _ninth_path, esto_path = _fixture_paths(tmp_path)
    source = pd.read_csv(esto_path, dtype=object)
    datacentres = pd.DataFrame([
        {
            "economy": "01AAA",
            "flows": "16.01.01 Datacentres",
            "products": "17 Electricity",
            "is_subtotal": "FALSE",
            "2022": 4.0,
            "2023": 12.0,
        }
    ])
    pd.concat([source, datacentres], ignore_index=True).to_csv(esto_path, index=False)

    insert_rows, _update_rows, validation = build_commercial_public_services_unallocated_rows(
        esto_csv_path=esto_path,
        eligible_product_codes={"17"},
    )

    electricity = insert_rows[
        insert_rows["economy"].eq("01AAA")
        & insert_rows["products"].eq("17 Electricity")
    ].iloc[0]
    assert float(electricity["2022"]) == 6.0
    assert float(electricity["2023"]) == -1.0
    issue = validation[
        validation["economy"].eq("01AAA")
        & validation["products"].eq("17 Electricity")
    ].iloc[0]
    assert bool(issue["negative_remainder"])
    assert issue["negative_years"] == "2023"
    assert bool(issue["reconciles_within_tolerance"])


def test_existing_commercial_unallocated_is_written_to_update_output(tmp_path: Path) -> None:
    _workbook_path, _ninth_path, esto_path = _fixture_paths(tmp_path)
    source = pd.read_csv(esto_path, dtype=object)
    existing = pd.DataFrame([
        {
            "economy": "01AAA",
            "flows": "16.01.99 Commercial and public services unallocated",
            "products": "17 Electricity",
            "is_subtotal": "FALSE",
            "2022": 0.0,
            "2023": 0.0,
        }
    ])
    pd.concat([source, existing], ignore_index=True).to_csv(esto_path, index=False)

    insert_rows, update_rows, validation = build_commercial_public_services_unallocated_rows(
        esto_csv_path=esto_path,
        eligible_product_codes={"17"},
    )

    assert not (
        insert_rows["economy"].eq("01AAA")
        & insert_rows["products"].eq("17 Electricity")
    ).any()
    assert len(update_rows) == 1
    assert validation.loc[validation["economy"].eq("01AAA"), "output_action"].iloc[0] == "update"


def test_output_preserves_schema_and_zeroes_ordinary_placeholders(tmp_path: Path) -> None:
    workbook_path, ninth_path, esto_path = _fixture_paths(tmp_path)

    rows, _audit = build_missing_mapped_esto_rows(esto_path, workbook_path, ninth_path)

    assert list(rows.columns) == ["economy", "flows", "products", "is_subtotal", "2022", "2023"]
    ordinary_placeholder = rows[
        rows["flows"].eq("09.13.01 Electrolysers")
        & rows["products"].eq("16.12 Hydrogen")
    ]
    assert (ordinary_placeholder[["2022", "2023"]] == 0).all().all()
    leaf_rows = rows[
        rows["flows"].isin([
            "09.13.01 Electrolysers",
            "16.01.99 Commercial and public services unallocated",
        ])
        | (
            rows["flows"].isin(["09.06.02.01 Liquefaction", "09.06.02.02 Regasification"])
            & rows["products"].isin(["07.08 Fuel oil", "08.01 Natural gas", "08.02 LNG"])
        )
    ]
    assert set(leaf_rows["is_subtotal"]) == {"FALSE"}


def test_simulated_paste_back_produces_no_remaining_rows(tmp_path: Path) -> None:
    workbook_path, ninth_path, esto_path = _fixture_paths(tmp_path)
    rows, _audit = build_missing_mapped_esto_rows(esto_path, workbook_path, ninth_path)

    source = pd.read_csv(esto_path, dtype=object)
    pd.concat([source, rows], ignore_index=True).to_csv(esto_path, index=False)
    rerun_rows, rerun_audit = build_missing_mapped_esto_rows(esto_path, workbook_path, ninth_path)

    assert rerun_rows.empty
    assert rerun_audit.empty


def test_writer_creates_clean_paste_audit_and_summary_files(tmp_path: Path) -> None:
    workbook_path, ninth_path, esto_path = _fixture_paths(tmp_path)
    output_dir = tmp_path / "outputs"

    summary = write_missing_mapped_esto_rows(
        esto_csv_paths=[esto_path],
        mapping_workbook_path=workbook_path,
        ninth_csv_path=ninth_path,
        output_dir=output_dir,
    )

    paste_path = output_dir / "esto_missing_mapped_rows.csv"
    audit_path = output_dir / "esto_missing_mapped_rows_audit.csv"
    assert paste_path.exists()
    assert audit_path.exists()
    assert (output_dir / "esto_ninth_nonzero_filter_audit.csv").exists()
    assert (output_dir / "esto_lng_split_rows.csv").exists()
    assert (output_dir / "esto_lng_split_rows_audit.csv").exists()
    assert (output_dir / "esto_commercial_services_unallocated_updates.csv").exists()
    assert (output_dir / "esto_commercial_services_unallocated_validation.csv").exists()
    assert (output_dir / "missing_mapped_esto_rows_summary.csv").exists()
    assert list(pd.read_csv(paste_path).columns) == list(pd.read_csv(esto_path).columns)
    assert summary.loc[0, "paste_ready_row_count"] > 0
    assert summary.loc[0, "always_required_row_count"] > 0
    assert summary.loc[0, "ninth_driven_row_count"] > 0
    assert summary.loc[0, "structural_completion_row_count"] > 0
    assert summary.loc[0, "commercial_services_negative_remainder_count"] == 0
    assert summary.loc[0, "commercial_services_unresolved_count"] == 0
