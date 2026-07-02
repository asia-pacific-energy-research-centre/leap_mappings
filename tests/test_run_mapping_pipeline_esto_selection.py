import pandas as pd

from codebase.run_mapping_pipeline import (
    configured_rollup_reference_pairs,
    select_esto_comparison_rows,
)


def test_configured_rollup_reference_pairs_uses_active_base_targets_only() -> None:
    relationships = pd.DataFrame(
        [
            {
                "include_in_use_case": True,
                "source_system": "LEAP",
                "target_system": "ESTO",
                "is_rollup_derived": False,
                "source_flow": "Total transformation - no transfers",
                "target_flow": "09 Total transformation sector",
                "target_product": "09 Nuclear",
            },
            {
                "include_in_use_case": True,
                "source_system": "LEAP",
                "target_system": "ESTO",
                "is_rollup_derived": True,
                "source_flow": "Total transformation - no transfers",
                "target_flow": "09.01.01 Electricity plants",
                "target_product": "09 Nuclear",
            },
        ]
    )
    rules = pd.DataFrame(
        [
            {
                "include": True,
                "rolled_leap_sector_name_full_path": "Total transformation - no transfers",
            }
        ]
    )

    pairs = configured_rollup_reference_pairs(
        relationships,
        rules,
        {"Total transformation - no transfers"},
    )

    assert pairs == {("09 Total transformation sector", "09 Nuclear")}


def test_select_esto_comparison_rows_keeps_leaves_and_configured_parent_pair() -> None:
    esto_df = pd.DataFrame(
        [
            {
                "flows": "09.01.01 Electricity plants",
                "products": "09 Nuclear",
                "is_subtotal": False,
            },
            {
                "flows": "09 Total transformation sector",
                "products": "09 Nuclear",
                "is_subtotal": True,
            },
            {
                "flows": "12 Total final consumption",
                "products": "09 Nuclear",
                "is_subtotal": True,
            },
        ]
    )

    selected = select_esto_comparison_rows(
        esto_df,
        {("09 Total transformation sector", "09 Nuclear")},
    )

    assert list(zip(selected["flows"], selected["products"])) == [
        ("09.01.01 Electricity plants", "09 Nuclear"),
        ("09 Total transformation sector", "09 Nuclear"),
    ]
