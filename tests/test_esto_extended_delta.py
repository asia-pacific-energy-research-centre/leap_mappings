"""Tests for exact ESTO-base plus ESTO-Extended row overlays."""

import pandas as pd
import pytest

from codebase.mapping_tools.esto_extended_delta import (
    DELTA_OPERATION_COLUMN,
    build_esto_extended_exact_row_delta,
    reconstruct_esto_extended_exact_rows,
)


COLUMNS = [
    "economy",
    "esto_flow",
    "esto_product",
    "year",
    "value",
    "source_system",
    "scenario",
    "non_expanding_rollup_id",
]


def _row(
    flow: str,
    value: float,
    source_system: str,
    product: str = "17 Electricity",
) -> dict[str, object]:
    return {
        "economy": "20USA",
        "esto_flow": flow,
        "esto_product": product,
        "year": 2022,
        "value": value,
        "source_system": source_system,
        "scenario": "historical",
        "non_expanding_rollup_id": "",
    }


def _sort(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_values(
        ["economy", "esto_flow", "esto_product", "year"],
        kind="stable",
    ).reset_index(drop=True)


def test_delta_reconstructs_add_change_and_former_leaf_removal_exactly() -> None:
    base = pd.DataFrame(
        [
            _row("09.01 Unchanged", 10, "ESTO"),
            _row("09.02 Changed", 20, "ESTO"),
            _row("09.03 Former leaf", 30, "ESTO"),
        ],
        columns=COLUMNS,
    )
    extended = pd.DataFrame(
        [
            _row("09.01 Unchanged", 10, "ESTO_EXTENDED"),
            _row("09.02 Changed", 22, "ESTO_EXTENDED"),
            _row("09.03.01 New child", 30, "ESTO_EXTENDED"),
        ],
        columns=COLUMNS,
    )

    delta = build_esto_extended_exact_row_delta(base, extended)
    reconstructed = reconstruct_esto_extended_exact_rows(base, delta)

    assert delta[DELTA_OPERATION_COLUMN].value_counts().to_dict() == {
        "upsert": 2,
        "delete": 1,
    }
    assert "09.01 Unchanged" not in set(delta["esto_flow"])
    pd.testing.assert_frame_equal(_sort(reconstructed), _sort(extended))


def test_identical_dataset_needs_no_delta_beyond_source_relabelling() -> None:
    base = pd.DataFrame([_row("09.01 Unchanged", 10, "ESTO")], columns=COLUMNS)
    extended = base.copy()
    extended["source_system"] = "ESTO_EXTENDED"

    delta = build_esto_extended_exact_row_delta(base, extended)
    reconstructed = reconstruct_esto_extended_exact_rows(base, delta)

    assert delta.empty
    pd.testing.assert_frame_equal(_sort(reconstructed), _sort(extended))


def test_delta_preserves_rollup_identity_as_part_of_the_row_key() -> None:
    base = pd.DataFrame([_row("09 Rollup", 10, "ESTO")], columns=COLUMNS)
    extended = pd.DataFrame(
        [
            _row("09 Rollup", 10, "ESTO_EXTENDED"),
            {
                **_row("09 Rollup", 4, "ESTO_EXTENDED"),
                "non_expanding_rollup_id": "rollup_1",
            },
        ],
        columns=COLUMNS,
    )

    delta = build_esto_extended_exact_row_delta(base, extended)

    assert len(delta) == 1
    assert delta.loc[0, DELTA_OPERATION_COLUMN] == "upsert"
    assert delta.loc[0, "non_expanding_rollup_id"] == "rollup_1"


def test_delta_rejects_schema_source_and_duplicate_identity_ambiguity() -> None:
    base = pd.DataFrame([_row("09.01 Row", 10, "ESTO")], columns=COLUMNS)
    extended = pd.DataFrame(
        [_row("09.01 Row", 10, "ESTO_EXTENDED")],
        columns=COLUMNS,
    )

    with pytest.raises(ValueError, match="identical ordered columns"):
        build_esto_extended_exact_row_delta(
            base,
            extended.drop(columns="non_expanding_rollup_id"),
        )
    wrong_source = extended.copy()
    wrong_source["source_system"] = "ESTO"
    with pytest.raises(ValueError, match="ESTO_EXTENDED"):
        build_esto_extended_exact_row_delta(base, wrong_source)
    with pytest.raises(ValueError, match="duplicate row identity"):
        build_esto_extended_exact_row_delta(
            pd.concat([base, base], ignore_index=True),
            extended,
        )


def test_reconstruction_rejects_unknown_delete_and_operation() -> None:
    base = pd.DataFrame([_row("09.01 Row", 10, "ESTO")], columns=COLUMNS)
    unknown = pd.DataFrame(
        [
            {
                DELTA_OPERATION_COLUMN: "delete",
                **_row("09.99 Missing", 1, "ESTO_EXTENDED"),
            }
        ],
        columns=[DELTA_OPERATION_COLUMN, *COLUMNS],
    )
    with pytest.raises(ValueError, match="absent from the base"):
        reconstruct_esto_extended_exact_rows(base, unknown)

    unknown[DELTA_OPERATION_COLUMN] = "replace"
    with pytest.raises(ValueError, match="Unsupported"):
        reconstruct_esto_extended_exact_rows(base, unknown)
