import pandas as pd

from codebase.mapping_tools.esto_exact_rows import normalise_esto_flow_labels


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
