"""Tests for promoting observed detailed LEAP pairs into compiler authority."""

import pandas as pd

from codebase.mapping_tools.leap_pair_registry import (
    PAIR_COLUMNS,
    add_observed_balance_pairs,
)


def _registry() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "dataset": "LEAP",
                "flow": "All demand aggregated/Road",
                "product": "Motor gasoline",
                "flow_is_parent": False,
                "product_is_parent": False,
                "pair_is_subtotal": False,
                "pair_exists_in_dataset": True,
                "pair_universe_member": True,
                "pair_status": "structurally_eligible_balance_cell",
                "temporal_evidence_status": "structurally_eligible_balance_cell",
                "pair_universe_authority": "template",
                "authority_layer": "deterministic_balance_grid",
                "source_kind": "balance_export_template",
                "template_support_count": 1,
                "template_files": "01_AUS.xlsx",
                "new_rows_sheet_count": 0,
                "new_rows_sheets": "",
                "source_path_count": 1,
                "source_paths": "Demand/All demand aggregated/Road",
            }
        ],
        columns=PAIR_COLUMNS,
    )


def test_nonzero_observed_pairs_extend_registry_without_template_change() -> None:
    observed = pd.DataFrame(
        [
            {
                "flow": "Freight road",
                "product": "Motor gasoline",
                "pair_status": "observed_data_valid",
                "economy_support_count": 1,
            },
            {
                "flow": "Freight road/Trucks/ICE heavy",
                "product": "Motor gasoline",
                "pair_status": "observed_data_valid",
                "economy_support_count": 1,
            },
        ]
    )

    combined, added = add_observed_balance_pairs(_registry(), observed)

    assert set(added["flow"]) == {
        "Freight road",
        "Freight road/Trucks/ICE heavy",
    }
    assert combined.set_index("flow").loc["Freight road", "flow_is_parent"]
    assert combined.set_index("flow").loc["Freight road", "pair_is_subtotal"]
    assert set(added["pair_universe_authority"]) == {
        "observed_nonzero_balance_export"
    }


def test_zero_only_observed_pairs_do_not_create_relationship_authority() -> None:
    observed = pd.DataFrame(
        [
            {
                "flow": "Passenger road/LPVs/BEV small",
                "product": "Electricity for hydrogen",
                "pair_status": "observed_zero_only",
                "economy_support_count": 0,
            }
        ]
    )

    combined, added = add_observed_balance_pairs(_registry(), observed)

    assert added.empty
    assert len(combined) == 1


def test_existing_structural_pair_keeps_original_authority() -> None:
    observed = pd.DataFrame(
        [
            {
                "flow": "All demand aggregated/Road",
                "product": "Motor gasoline",
                "pair_status": "observed_data_valid",
                "economy_support_count": 1,
            }
        ]
    )

    combined, added = add_observed_balance_pairs(_registry(), observed)

    assert added.empty
    assert len(combined) == 1
    assert combined.iloc[0]["pair_universe_authority"] == "template"
