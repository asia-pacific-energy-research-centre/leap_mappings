import pandas as pd

from codebase.mapping_tools.power_all_producers_certification import (
    audit_alias_cooccurrence,
    audit_ordinary_esto_component_coverage,
    audit_source_once_delivery,
    audit_structural_component_definitions,
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


def test_power_certification_separates_structural_targets_from_ordinary_esto_coverage() -> None:
    rollups = pd.DataFrame([{"rolled_esto_flow": "09.01,09.02 Combined", "components": "09.01 A|09.02 A"}])
    raw = pd.DataFrame([
        {"economy": "01_AUS", "scenario": "historical", "year": 2023, "esto_flow": "09.01 A", "esto_product": "Coal", "value": 2},
        {"economy": "01_AUS", "scenario": "historical", "year": 2023, "esto_flow": "09.02 A", "esto_product": "Coal", "value": 3},
    ])
    common = pd.DataFrame([{"comparison_scope": "scope", "component_esto_flow": "09.01,09.02 Combined"}])

    structural = audit_structural_component_definitions(common, rollups)
    coverage = audit_ordinary_esto_component_coverage(raw, rollups)

    assert set(structural["status"]) == {"passed"}
    assert coverage.loc[0, "component_total"] == 5
    assert coverage.loc[0, "status"] == "observed_ordinary_esto_component_coverage"
