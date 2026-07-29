import pandas as pd

from codebase.mapping_tools.apply_ninth_to_esto_conversion import (
    apply_default_source_conserving_allocation,
    convert_ninth_results_to_esto,
    iter_ninth_results_to_esto_by_economy,
    prepare_ninth_long_format,
    relationships_need_target_dataset_share,
)


def _relationship_rows() -> pd.DataFrame:
    base = {
        "source_system": "NINTH",
        "source_flow": "combined_source",
        "source_product": "fuel",
        "target_system": "ESTO",
        "target_product": "Fuel",
        "relationship_id": "rel-combined-source",
        "allocation_method": "direct",
        "allocation_source": "target_dataset_share",
        "allocation_share": 0.5,
    }
    return pd.DataFrame([
        {**base, "target_flow": "Component A"},
        {**base, "target_flow": "Component B"},
    ])


def _ninth_results() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "source_system": "NINTH",
            "economy": "01_AUS",
            "scenario": "reference",
            "year": 2023,
            "ninth_sector": "combined_source",
            "ninth_fuel": "fuel",
            "value": 100.0,
        }
    ])


def _target_values() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "economy": "01AUS",
            "scenario": "historical",
            "year": 2023,
            "esto_flow": "Component A",
            "esto_product": "Fuel",
            "value": 70.0,
        },
        {
            "economy": "01AUS",
            "scenario": "historical",
            "year": 2023,
            "esto_flow": "Component B",
            "esto_product": "Fuel",
            "value": 30.0,
        },
    ])


def test_ninth_converter_default_returns_dataframe() -> None:
    result = convert_ninth_results_to_esto(_ninth_results(), _relationship_rows())

    assert isinstance(result, pd.DataFrame)


def test_ninth_converter_conserves_source_value_across_unallocated_targets() -> None:
    source = pd.DataFrame([{
        "economy": "01_AAA",
        "scenario": "reference",
        "year": 2023,
        "ninth_sector": "09_total",
        "ninth_fuel": "02_coal_products",
        "value": 100.0,
    }])
    relationships = pd.DataFrame([
        {"source_flow": "09_total", "source_product": "02_coal_products",
         "target_flow": "09 Total transformation sector", "target_product": "02.01 Coke oven coke",
         "allocation_share": ""},
        {"source_flow": "09_total", "source_product": "02_coal_products",
         "target_flow": "09 Total transformation sector", "target_product": "02.03 Coke oven gas",
         "allocation_share": ""},
    ])
    merged = source.merge(
        relationships,
        left_on=["ninth_sector", "ninth_fuel"],
        right_on=["source_flow", "source_product"],
        how="left",
    )

    allocated = apply_default_source_conserving_allocation(merged)

    assert allocated["allocation_share"].tolist() == [0.5, 0.5]
    assert (allocated["value"] * allocated["allocation_share"]).sum() == 100.0


def test_ninth_converter_automatically_uses_target_basis_for_blank_one_to_many_mapping() -> None:
    source = pd.DataFrame([{
        "economy": "01_AUS",
        "scenario": "reference",
        "year": 2023,
        "ninth_sector": "combined_source",
        "ninth_fuel": "fuel",
        "value": 100.0,
    }])
    relationships = pd.DataFrame([
        {"source_flow": "combined_source", "source_product": "fuel",
         "target_flow": "Component A", "target_product": "Fuel",
         "allocation_share": "", "allocation_source": ""},
        {"source_flow": "combined_source", "source_product": "fuel",
         "target_flow": "Component B", "target_product": "Fuel",
         "allocation_share": "", "allocation_source": ""},
    ])
    target_values = pd.DataFrame([
        {"economy": "01AUS", "year": 2023, "esto_flow": "Component A",
         "esto_product": "Fuel", "value": 70.0},
        {"economy": "01AUS", "year": 2023, "esto_flow": "Component B",
         "esto_product": "Fuel", "value": 30.0},
    ])

    assert relationships_need_target_dataset_share(relationships)
    result = convert_ninth_results_to_esto(source, relationships, target_values_df=target_values)

    assert result.set_index("target_flow")["value"].to_dict() == {
        "Component A": 70.0,
        "Component B": 30.0,
    }


def test_ninth_converter_uses_equal_shares_when_automatic_target_basis_is_unavailable() -> None:
    source = pd.DataFrame([{
        "economy": "01_AUS",
        "scenario": "reference",
        "year": 2023,
        "ninth_sector": "combined_source",
        "ninth_fuel": "fuel",
        "value": 100.0,
    }])
    relationships = pd.DataFrame([
        {"source_flow": "combined_source", "source_product": "fuel",
         "target_flow": "Component A", "target_product": "Fuel", "allocation_share": ""},
        {"source_flow": "combined_source", "source_product": "fuel",
         "target_flow": "Component B", "target_product": "Fuel", "allocation_share": ""},
    ])

    result = convert_ninth_results_to_esto(source, relationships)

    assert result.set_index("target_flow")["value"].to_dict() == {
        "Component A": 50.0,
        "Component B": 50.0,
    }


def test_ninth_lineage_sums_to_aggregated_values_and_keeps_allocation_share() -> None:
    converted_df, lineage_df = convert_ninth_results_to_esto(
        _ninth_results(),
        _relationship_rows(),
        target_values_df=_target_values(),
        return_lineage=True,
    )

    converted_values = converted_df.set_index("target_flow")["value"].to_dict()
    lineage_values = lineage_df.groupby("target_flow")["value"].sum().to_dict()

    assert converted_values == {"Component A": 70.0, "Component B": 30.0}
    assert lineage_values == converted_values
    assert lineage_df.set_index("target_flow")["allocation_share"].to_dict() == {
        "Component A": 0.7,
        "Component B": 0.3,
    }
    assert set(lineage_df["relationship_id"]) == {"rel-combined-source"}


def test_economy_chunked_conversion_matches_single_pass() -> None:
    source = pd.concat(
        [
            _ninth_results(),
            _ninth_results().assign(economy="02_BD", value=40.0),
        ],
        ignore_index=True,
    )
    target_values = pd.concat(
        [
            _target_values(),
            pd.DataFrame(
                [
                    {
                        "economy": "02BD",
                        "scenario": "historical",
                        "year": 2023,
                        "esto_flow": "Component A",
                        "esto_product": "Fuel",
                        "value": 20.0,
                    },
                    {
                        "economy": "02BD",
                        "scenario": "historical",
                        "year": 2023,
                        "esto_flow": "Component B",
                        "esto_product": "Fuel",
                        "value": 80.0,
                    },
                ]
            ),
        ],
        ignore_index=True,
    )
    expected_converted, expected_lineage = convert_ninth_results_to_esto(
        source,
        _relationship_rows(),
        target_values_df=target_values,
        return_lineage=True,
    )
    chunks = list(
        iter_ninth_results_to_esto_by_economy(
            source,
            _relationship_rows(),
            target_values_df=target_values,
        )
    )
    actual_converted = pd.concat(
        [converted for _, converted, _ in chunks],
        ignore_index=True,
    )
    actual_lineage = pd.concat(
        [lineage for _, _, lineage in chunks],
        ignore_index=True,
    )

    converted_sort = [
        "economy",
        "scenario",
        "year",
        "target_flow",
        "target_product",
    ]
    lineage_sort = [
        "economy",
        "scenario",
        "year",
        "source_flow",
        "source_product",
        "target_flow",
        "target_product",
    ]
    pd.testing.assert_frame_equal(
        actual_converted.sort_values(converted_sort).reset_index(drop=True),
        expected_converted.sort_values(converted_sort).reset_index(drop=True),
    )
    pd.testing.assert_frame_equal(
        actual_lineage.sort_values(lineage_sort).reset_index(drop=True),
        expected_lineage.sort_values(lineage_sort).reset_index(drop=True),
    )


def test_ninth_preparation_keeps_deeper_sector_detail_separate(tmp_path) -> None:
    """A sub3 row must not be relabelled as its mapped sub2 subtotal."""
    path = tmp_path / "ninth.csv"
    pd.DataFrame([
        {
            "scenarios": "reference", "economy": "20_USA",
            "sectors": "14_industry_sector", "sub1sectors": "14_03_manufacturing",
            "sub2sectors": "14_03_02_chemical_incl_petrochemical",
            "sub3sectors": "x", "sub4sectors": "x", "fuels": "01_coal",
            "subfuels": "01_x_thermal_coal", "2023": 5.0,
        },
        {
            "scenarios": "reference", "economy": "20_USA",
            "sectors": "14_industry_sector", "sub1sectors": "14_03_manufacturing",
            "sub2sectors": "14_03_02_chemical_incl_petrochemical",
            "sub3sectors": "14_03_02_01_fs", "sub4sectors": "x", "fuels": "01_coal",
            "subfuels": "01_x_thermal_coal", "2023": 5.0,
        },
    ]).to_csv(path, index=False)

    result = prepare_ninth_long_format(path)

    assert set(result["ninth_sector"]) == {
        "14_03_02_chemical_incl_petrochemical",
        "14_03_02_01_fs",
    }
