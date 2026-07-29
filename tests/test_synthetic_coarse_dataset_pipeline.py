import pandas as pd
from pathlib import Path

from codebase.mapping_tools.apply_common_esto_structure import (
    apply_common_structure,
)
from codebase.mapping_tools.build_common_esto_structure import (
    build_common_esto_for_scope,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_first_level_synthetic_dataset_rolls_detail_to_coarse_common_row() -> None:
    """Run synthetic relationships through Common build and value application."""
    relationships = pd.read_csv(
        FIXTURE_DIR / "synthetic_first_level_esto_mappings.csv"
    )
    common_rows, _, qa = build_common_esto_for_scope(
        comparison_scope="synth_balance_comparison",
        scope_config={
            "systems": ["SYNTH_BALANCE", "ESTO"],
            "use_cases": ["synthetic_to_esto_balance_conversion"],
            "aggregate_source_systems": ["SYNTH_BALANCE"],
        },
        relationships_df=relationships,
        exclusions_df=pd.DataFrame(),
        overrides_df=pd.DataFrame(),
        label_overrides_df=pd.DataFrame(),
        flow_code_to_name={},
        product_code_to_name={},
    )

    assert common_rows["common_row_id"].nunique() == 1
    assert len(common_rows) == 3
    assert qa["qa_common_esto_source_aggregates_split"].empty

    source_values = pd.read_csv(
        FIXTURE_DIR / "synthetic_first_level_esto_values.csv"
    )
    comparison, missing, _ = apply_common_structure(
        source_df=source_values,
        common_rows_df=common_rows,
    )

    totals = comparison.groupby("source_system")["value"].sum().to_dict()
    assert missing.empty
    assert totals == {"ESTO": 100.0, "SYNTH_BALANCE": 100.0}
