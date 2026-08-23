import pandas as pd

from codebase.mapping_tools.esto_exact_rows import (
    ESTO_RETAINED_SUBTOTAL_FLOW_LABELS,
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
