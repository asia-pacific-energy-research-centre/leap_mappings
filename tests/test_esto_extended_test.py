#%%
"""Focused tests for the non-destructive ESTO Extended prototype."""

#%%
import pandas as pd

from codebase.mapping_tools.build_esto_extended_test import (
    EXTENSION_RULES,
    _esto_code,
    _normalise_path,
    apply_parent_minus_children_rule,
)


#%%
def test_normalisation_helpers_keep_hierarchy_stable():
    assert _normalise_path(r"Transformation\CHP plants\Coal CHP") == "Transformation/CHP plants/Coal CHP"
    assert _esto_code("16.01.99 Commercial and public services unallocated") == "16.01.99"


def test_parent_minus_children_generates_named_residual_with_provenance():
    source = pd.DataFrame(
        [
            {
                "economy": "20USA",
                "flows": "16.01 Commercial and public services",
                "products": "17 Electricity",
                "is_subtotal": True,
                "2022": 100.0,
            },
            {
                "economy": "20USA",
                "flows": "16.01.01 Datacentres",
                "products": "17 Electricity",
                "is_subtotal": False,
                "2022": 25.0,
            },
        ]
    )
    generated, summary = apply_parent_minus_children_rule(
        source,
        EXTENSION_RULES[0],
        source_leap_paths="Demand/Buildings/Commercial and public services",
    )

    assert len(generated) == 1
    row = generated.iloc[0]
    assert row["flows"] == "16.01.99 Commercial and public services unallocated"
    assert row["2022"] == 75.0
    assert row["esto_extended_row_origin"] == "generated"
    assert row["esto_extended_rule_id"] == "commercial_services_residual"
    assert row["esto_extended_source_leap_paths"] == "Demand/Buildings/Commercial and public services"
    assert summary.iloc[0]["generated_rows"] == 1


#%%
