import pandas as pd

from codebase.mapping_tools.power_all_producers_certification import (
    audit_alias_cooccurrence,
    audit_component_sums,
    audit_source_once_delivery,
    registered_power_rollups,
)


def test_registered_power_rollups_require_two_components() -> None:
    rules = pd.DataFrame([
        {"include": True, "rollup_context": "power_process_comparison", "ROLLUP_MODE": "EXPANDING", "input_esto_flow": "09.01 A", "rolled_esto_flow": "09.01,09.02 Combined", "rollup_group_id": "g"},
        {"include": True, "rollup_context": "power_process_comparison", "ROLLUP_MODE": "EXPANDING", "input_esto_flow": "09.02 A", "rolled_esto_flow": "09.01,09.02 Combined", "rollup_group_id": "g"},
    ])
    result = registered_power_rollups(rules)
    assert result.loc[0, "component_count"] == 2


def test_source_delivery_and_alias_cooccurrence_are_observation_specific() -> None:
    lineage = pd.DataFrame([
        {"source_system": "LEAP", "economy": "01_AUS", "scenario": "Reference", "year": 2023, "source_flow": "Power", "source_product": "Coal", "target_flow": "09.01,09.02 Combined", "value": 1},
        {"source_system": "LEAP", "economy": "01_AUS", "scenario": "Reference", "year": 2023, "source_flow": "Power", "source_product": "Coal", "target_flow": "other", "value": 1},
    ])
    detail, _ = audit_source_once_delivery(lineage, {"09.01,09.02 Combined"})
    assert detail.loc[0, "status"] == "passed"
    aliases = audit_alias_cooccurrence(pd.DataFrame([
        {"economy": "01_AUS", "scenario": "Reference", "year": 2023, "leap_flow": "Electricity Generation/Battery", "value": 2},
        {"economy": "01_AUS", "scenario": "Reference", "year": 2023, "leap_flow": "Electricity Generation/Batteries", "value": 3},
    ]))
    assert aliases.loc[0, "status"] == "double_count_risk"


def test_component_sum_compares_two_producer_observations_to_one_common_row() -> None:
    rollups = pd.DataFrame([{"rolled_esto_flow": "09.01,09.02 Combined", "components": "09.01 A|09.02 A"}])
    raw = pd.DataFrame([
        {"economy": "01_AUS", "scenario": "historical", "year": 2023, "esto_flow": "09.01 A", "esto_product": "Coal", "value": 2},
        {"economy": "01_AUS", "scenario": "historical", "year": 2023, "esto_flow": "09.02 A", "esto_product": "Coal", "value": 3},
    ])
    common = pd.DataFrame([{"comparison_scope": "scope", "common_row_id": "row", "component_esto_flow": "09.01,09.02 Combined", "component_esto_product": "Coal"}])
    fact = pd.DataFrame([{"comparison_scope": "scope", "source_system": "ESTO_EXTENDED", "common_row_id": "row", "economy": "01_AUS", "scenario": "historical", "year": 2023, "value": 5}])
    result = audit_component_sums(raw, fact, common, rollups)
    assert result.loc[0, "status"] == "passed"
