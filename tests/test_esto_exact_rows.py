import pandas as pd
import pytest

from codebase.mapping_tools.esto_exact_rows import (
    ESTO_RETAINED_SUBTOTAL_FLOW_LABELS,
    _filter_extended_to_native_rows,
    normalise_esto_flow_labels,
    select_esto_comparison_rows,
)


def test_normalise_esto_flow_labels_corrects_extended_td_loss_typo() -> None:
    source = pd.DataFrame({
        "flows": [
            "10.02 Transmision and distribution losses",
            "10.02 Transmission and distribution losses",
        ],
        "products": ["17 Electricity", "08.01 Natural gas"],
    })

    result = normalise_esto_flow_labels(source)

    assert result["flows"].tolist() == [
        "10.02 Transmission and distribution losses",
        "10.02 Transmission and distribution losses",
    ]


def test_select_esto_comparison_rows_keeps_published_road_parent() -> None:
    source = pd.DataFrame({
        "flows": ["15.02 Road", "15.02.01 Freight road"],
        "products": ["07.01 Motor gasoline", "07.01 Motor gasoline"],
        "is_subtotal": [True, False],
    })

    result = select_esto_comparison_rows(
        source,
        rollup_reference_pairs=set(),
        retained_flow_labels=ESTO_RETAINED_SUBTOTAL_FLOW_LABELS,
    )

    assert result["flows"].tolist() == ["15.02 Road", "15.02.01 Freight road"]


def test_extended_native_rows_restore_native_subtotal_classification(tmp_path) -> None:
    native_path = tmp_path / "00APEC_2024_low_with_subtotals.csv"
    pd.DataFrame(
        [
            {
                "economy": "05PRC", "flows": "16.02 Residential",
                "products": "17 Electricity", "is_subtotal": False,
            },
            {
                "economy": "05PRC", "flows": "16.02 Residential",
                "products": "19 Total", "is_subtotal": True,
            },
        ]
    ).to_csv(native_path, index=False)
    extended = pd.DataFrame(
        [
            {
                "economy": "05PRC", "flows": "16.02 Residential",
                "products": "17 Electricity", "is_subtotal": True,
            },
            {
                "economy": "05PRC", "flows": "16.02 Residential",
                "products": "19 Total", "is_subtotal": True,
            },
            {
                "economy": "05PRC", "flows": "16.02.99 Added category",
                "products": "17 Electricity", "is_subtotal": False,
            },
        ]
    )

    result = _filter_extended_to_native_rows(
        extended,
        tmp_path / "esto_extended_2024_low_with_subtotals.parquet",
    )

    assert result[["products", "is_subtotal"]].to_dict("records") == [
        {"products": "17 Electricity", "is_subtotal": False},
        {"products": "19 Total", "is_subtotal": True},
    ]
    selected = select_esto_comparison_rows(result, set(), set())
    assert selected["products"].tolist() == ["17 Electricity"]


def test_extended_native_filter_rejects_conflicting_native_subtotal_flags(
    tmp_path,
) -> None:
    native_path = tmp_path / "00APEC_2024_low_with_subtotals.csv"
    pd.DataFrame(
        [
            {
                "economy": "05PRC", "flows": "16.02 Residential",
                "products": "17 Electricity", "is_subtotal": False,
            },
            {
                "economy": "05PRC", "flows": "16.02 Residential",
                "products": "17 Electricity", "is_subtotal": True,
            },
        ]
    ).to_csv(native_path, index=False)
    extended = pd.DataFrame(
        [{
            "economy": "05PRC", "flows": "16.02 Residential",
            "products": "17 Electricity", "is_subtotal": True,
        }]
    )

    with pytest.raises(ValueError, match="conflicting is_subtotal"):
        _filter_extended_to_native_rows(
            extended,
            tmp_path / "esto_extended_2024_low_with_subtotals.parquet",
        )
