"""Focused synthetic tests for original-source parent anchor validation."""

import pandas as pd

from codebase.mapping_tools.source_parent_anchor_validation import (
    DATA_QUALITY_EXCEPTION_SHEET,
    _augment_with_data_quality_exceptions,
    build_failed_anchor_mapped_component_context_values,
    build_failed_anchor_raw_child_context_values,
    build_failed_anchor_raw_child_values,
    summarise_source_parent_anchors,
    validate_source_parent_anchors,
)


def _fixture(child_b_value: float = 6, include_child_b_mapping: bool = True):
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "P", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "P.1", "parent_code": "P"},
        {"dataset": "esto", "axis": "product", "code": "P.2", "parent_code": "P"},
    ])
    source = pd.DataFrame([
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P", "value": 10},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P.1", "value": 4},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P.2", "value": child_b_value},
    ])
    mapping_rows = [
        {"source_system": "ESTO", "source_flow": "F", "source_product": "P.1", "component_esto_flow": "F", "component_esto_product": "P.1"},
    ]
    if include_child_b_mapping:
        mapping_rows.append({"source_system": "ESTO", "source_flow": "F", "source_product": "P.2", "component_esto_flow": "F", "component_esto_product": "P.2"})
    mappings = pd.DataFrame(mapping_rows)
    common = pd.DataFrame([
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "P.1", "common_row_id": "c1"},
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "P.2", "common_row_id": "c2"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "c1", "value": 4},
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "c2", "value": child_b_value},
    ])
    return source, tree, mappings, common, comparison


def test_exact_parent_children_match_without_double_counting() -> None:
    detail = validate_source_parent_anchors(*_fixture())
    row = detail.iloc[0]
    assert row["status"] == "passed"
    assert row["frontier_sum"] == 10
    assert row["frontier_row_count"] == 2


def test_failed_anchor_mapped_component_context_exposes_each_common_component() -> None:
    source, tree, mappings, common, comparison = _fixture(child_b_value=5)
    detail = validate_source_parent_anchors(source, tree, mappings, common, comparison)
    components = build_failed_anchor_mapped_component_context_values(
        detail, tree, mappings, common, comparison,
    )
    assert set(components["common_row_id"]) == {"c1", "c2"}
    assert set(components["mapped_value"]) == {4.0, 5.0}
    assert set(components["raw_child_code"]) == {"P.1", "P.2"}


def test_unregistered_sibling_falls_back_to_raw_value_when_scope_partially_covers_parent() -> None:
    """A resolved child with no common_row_id anywhere still counts toward
    the frontier via its own raw value, as long as a sibling under the same
    parent/product DOES have a registered common row -- mirroring the real
    "09.01 Main activity producer" case, which is only ever registered
    merged into "09.01-09.02 Power sector" because NINTH/LEAP can't report
    it split, even though its own raw value is exact and real.
    """
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "P", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "P.1", "parent_code": "P"},
        {"dataset": "esto", "axis": "product", "code": "P.2", "parent_code": "P"},
    ])
    source = pd.DataFrame([
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P", "value": 10},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P.1", "value": 4},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P.2", "value": 6},
    ])
    mappings = pd.DataFrame([
        {"source_system": "ESTO", "source_flow": "F", "source_product": "P.1", "component_esto_flow": "F", "component_esto_product": "P.1"},
        {"source_system": "ESTO", "source_flow": "F", "source_product": "P.2", "component_esto_flow": "F", "component_esto_product": "P.2"},
    ])
    # Only P.1 is ever registered as a component of any Common ESTO row --
    # P.2 is never modeled at all.
    common = pd.DataFrame([
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "P.1", "common_row_id": "c1"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "c1", "value": 4},
    ])

    row = validate_source_parent_anchors(source, tree, mappings, common, comparison).iloc[0]

    assert row["status"] == "passed"
    assert row["frontier_sum"] == 10
    assert row["frontier_row_count"] == 2


def test_frontier_leaf_with_broken_other_axis_rollup_is_source_internal_not_failed() -> None:
    """A frontier leaf whose OTHER axis rollup contradicts itself is flagged
    distinctly, not "failed" -- mirrors the real NINTH case: sector
    "09_06_gas_processing_plants" declares its own "08_02_lng" subfuel as 0,
    while its own more granular sub-sector "09_06_02_liquefaction" reports
    the real +4218.81 for the same subfuel. No tree or mapping change in
    this repo can reconcile a raw file disagreeing with itself, so the
    "08_gas" product-axis parent must not report an ordinary "failed" here.
    """
    tree = pd.DataFrame([
        {"dataset": "ninth", "axis": "sector", "code": "Sector", "parent_code": ""},
        {"dataset": "ninth", "axis": "sector", "code": "SubSector", "parent_code": "Sector"},
        {"dataset": "ninth", "axis": "fuel", "code": "08_gas", "parent_code": ""},
        {"dataset": "ninth", "axis": "fuel", "code": "08_01_natural_gas", "parent_code": "08_gas"},
        {"dataset": "ninth", "axis": "fuel", "code": "08_02_lng", "parent_code": "08_gas"},
    ])
    source = pd.DataFrame([
        # Sector's own declared subfuel breakdown: natural_gas correctly
        # rolled up, LNG wrongly left at 0 (should be +4218.81, per SubSector
        # below), and the parent "x" total (08_gas) reflects the TRUE net.
        {"source_system": "NINTH", "economy": "E", "scenario": "reference", "year": 2023,
         "source_flow": "Sector", "source_product": "08_gas", "value": -0.0001},
        {"source_system": "NINTH", "economy": "E", "scenario": "reference", "year": 2023,
         "source_flow": "Sector", "source_product": "08_01_natural_gas", "value": -4218.85},
        {"source_system": "NINTH", "economy": "E", "scenario": "reference", "year": 2023,
         "source_flow": "Sector", "source_product": "08_02_lng", "value": 0.0},
        # SubSector reveals the real LNG figure that cancels natural_gas.
        {"source_system": "NINTH", "economy": "E", "scenario": "reference", "year": 2023,
         "source_flow": "SubSector", "source_product": "08_02_lng", "value": 4218.81},
    ])
    mappings = pd.DataFrame([
        {"source_system": "NINTH", "source_flow": "Sector", "source_product": "08_01_natural_gas",
         "component_esto_flow": "F", "component_esto_product": "01.01"},
        {"source_system": "NINTH", "source_flow": "Sector", "source_product": "08_02_lng",
         "component_esto_flow": "F", "component_esto_product": "01.02"},
    ])
    common = pd.DataFrame([
        {"comparison_scope": "esto_leap_ninth", "component_esto_flow": "F", "component_esto_product": "01.01", "common_row_id": "c1"},
        {"comparison_scope": "esto_leap_ninth", "component_esto_flow": "F", "component_esto_product": "01.02", "common_row_id": "c2"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_leap_ninth", "source_system": "NINTH", "economy": "E", "scenario": "reference", "year": 2023, "common_row_id": "c1", "value": -4218.85},
        {"comparison_scope": "esto_leap_ninth", "source_system": "NINTH", "economy": "E", "scenario": "reference", "year": 2023, "common_row_id": "c2", "value": 0.0},
    ])

    detail = validate_source_parent_anchors(source, tree, mappings, common, comparison)
    product_rows = detail[detail["validation_axis"] == "product"]
    row = product_rows[
        (product_rows["parent_code"] == "08_gas") & (product_rows["other_axis_value"] == "Sector")
    ].iloc[0]

    assert row["status"] == "skipped"
    assert row["reason"] == "source_internal_recursive_sum_inconsistency"


def test_source_internal_check_is_not_ninth_specific() -> None:
    """The same detection fires for an arbitrary source system that is
    neither ESTO, NINTH, nor LEAP -- the check is built entirely from
    axis_col/other_col/children/other_children, all already computed
    generically per source_system, with no dataset name ever referenced.
    Uses the default flow/product axis convention (the ``dataset in
    {"leap","ninth"}`` sector/fuel-naming override does not apply here,
    proving this also works for a dataset outside that hardcoded set).
    """
    tree = pd.DataFrame([
        {"dataset": "iea", "axis": "flow", "code": "Sector", "parent_code": ""},
        {"dataset": "iea", "axis": "flow", "code": "SubSector", "parent_code": "Sector"},
        {"dataset": "iea", "axis": "product", "code": "08_gas", "parent_code": ""},
        {"dataset": "iea", "axis": "product", "code": "08_01_natural_gas", "parent_code": "08_gas"},
        {"dataset": "iea", "axis": "product", "code": "08_02_lng", "parent_code": "08_gas"},
    ])
    source = pd.DataFrame([
        {"source_system": "IEA", "economy": "E", "scenario": "reference", "year": 2023,
         "source_flow": "Sector", "source_product": "08_gas", "value": -0.0001},
        {"source_system": "IEA", "economy": "E", "scenario": "reference", "year": 2023,
         "source_flow": "Sector", "source_product": "08_01_natural_gas", "value": -4218.85},
        {"source_system": "IEA", "economy": "E", "scenario": "reference", "year": 2023,
         "source_flow": "Sector", "source_product": "08_02_lng", "value": 0.0},
        {"source_system": "IEA", "economy": "E", "scenario": "reference", "year": 2023,
         "source_flow": "SubSector", "source_product": "08_02_lng", "value": 4218.81},
    ])
    mappings = pd.DataFrame([
        {"source_system": "IEA", "source_flow": "Sector", "source_product": "08_01_natural_gas",
         "component_esto_flow": "F", "component_esto_product": "01.01"},
        {"source_system": "IEA", "source_flow": "Sector", "source_product": "08_02_lng",
         "component_esto_flow": "F", "component_esto_product": "01.02"},
    ])
    common = pd.DataFrame([
        {"comparison_scope": "iea_only", "component_esto_flow": "F", "component_esto_product": "01.01", "common_row_id": "c1"},
        {"comparison_scope": "iea_only", "component_esto_flow": "F", "component_esto_product": "01.02", "common_row_id": "c2"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "iea_only", "source_system": "IEA", "economy": "E", "scenario": "reference", "year": 2023, "common_row_id": "c1", "value": -4218.85},
        {"comparison_scope": "iea_only", "source_system": "IEA", "economy": "E", "scenario": "reference", "year": 2023, "common_row_id": "c2", "value": 0.0},
    ])

    detail = validate_source_parent_anchors(source, tree, mappings, common, comparison)
    product_rows = detail[detail["validation_axis"] == "product"]
    row = product_rows[
        (product_rows["parent_code"] == "08_gas") & (product_rows["other_axis_value"] == "Sector")
    ].iloc[0]

    assert row["status"] == "skipped"
    assert row["reason"] == "source_internal_recursive_sum_inconsistency"


def test_registered_but_dataless_child_falls_back_to_raw_value() -> None:
    """A common row declared for a component still needs the raw fallback
    when THIS source system's own comparison-data export has zero rows for
    it -- mirroring the real "16.01 Biogas" case, where NINTH's export has a
    value for the shared common row but ESTO's own export never wrote one,
    even though ESTO's own raw figure is real and exact.
    """
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "P", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "P.1", "parent_code": "P"},
    ])
    source = pd.DataFrame([
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P", "value": 10},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P.1", "value": 10},
    ])
    mappings = pd.DataFrame([
        {"source_system": "ESTO", "source_flow": "F", "source_product": "P.1", "component_esto_flow": "F", "component_esto_product": "P.1"},
    ])
    common = pd.DataFrame([
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "P.1", "common_row_id": "c1"},
    ])
    # c1 is a genuine, declared common row -- just with no ESTO comparison
    # rows for it at all, in any economy/year.
    comparison = pd.DataFrame(columns=[
        "comparison_scope", "source_system", "economy", "scenario", "year", "common_row_id", "value",
    ])

    row = validate_source_parent_anchors(source, tree, mappings, common, comparison).iloc[0]

    assert row["status"] == "passed"
    assert row["frontier_sum"] == 10


def test_parent_anchor_uses_descendant_mapping_to_roll_deep_other_axis() -> None:
    tree = pd.DataFrame([
        {"dataset": "ninth", "axis": "sector", "code": "Road", "parent_code": ""},
        {"dataset": "ninth", "axis": "sector", "code": "Road/Passenger", "parent_code": "Road"},
        {"dataset": "ninth", "axis": "fuel", "code": "P", "parent_code": ""},
        {"dataset": "ninth", "axis": "fuel", "code": "P/P.1", "parent_code": "P"},
        {"dataset": "ninth", "axis": "fuel", "code": "P/P.2", "parent_code": "P"},
    ])
    source = pd.DataFrame([
        {"source_system": "NINTH", "economy": "E", "scenario": "reference", "year": 2023,
         "source_flow": "Road/Passenger", "source_product": "P", "value": 10},
        {"source_system": "NINTH", "economy": "E", "scenario": "reference", "year": 2023,
         "source_flow": "Road/Passenger", "source_product": "P/P.1", "value": 4},
        {"source_system": "NINTH", "economy": "E", "scenario": "reference", "year": 2023,
         "source_flow": "Road/Passenger", "source_product": "P/P.2", "value": 6},
    ])
    mappings = pd.DataFrame([
        {"source_system": "NINTH", "source_flow": "Road", "source_product": "P/P.1",
         "component_esto_flow": "15.02 Road", "component_esto_product": "P.1"},
        {"source_system": "NINTH", "source_flow": "Road", "source_product": "P/P.2",
         "component_esto_flow": "15.02 Road", "component_esto_product": "P.2"},
    ])
    common = pd.DataFrame([
        {"comparison_scope": "esto_leap_ninth", "component_esto_flow": "15.02 Road",
         "component_esto_product": "P.1", "common_row_id": "c1"},
        {"comparison_scope": "esto_leap_ninth", "component_esto_flow": "15.02 Road",
         "component_esto_product": "P.2", "common_row_id": "c2"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_leap_ninth", "source_system": "NINTH", "economy": "E",
         "scenario": "reference", "year": 2023, "common_row_id": "c1", "value": 4},
        {"comparison_scope": "esto_leap_ninth", "source_system": "NINTH", "economy": "E",
         "scenario": "reference", "year": 2023, "common_row_id": "c2", "value": 6},
    ])
    detail = validate_source_parent_anchors(source, tree, mappings, common, comparison)
    row = detail[(detail["validation_axis"] == "product") & (detail["parent_code"] == "P")].iloc[0]
    assert row["status"] == "passed"
    assert row["frontier_sum"] == 10


def test_missing_child_fails_and_is_reported() -> None:
    # Genuine gap: parent 10 but mapped frontier only explains 4 -> failed.
    detail = validate_source_parent_anchors(*_fixture(include_child_b_mapping=False))
    row = detail.iloc[0]
    assert row["status"] == "failed"
    assert row["reason"] == "incomplete_frontier"
    assert row["missing_expected_children"] == "P.2"


def test_incomplete_frontier_that_reconciles_is_passed() -> None:
    # Parent reconciles to its mapped leaf exactly, but one leaf child is
    # unmapped (an intentional placeholder). "Reconciles wins" -> passed.
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "P", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "P.1", "parent_code": "P"},
        {"dataset": "esto", "axis": "product", "code": "P.2", "parent_code": "P"},
    ])
    source = pd.DataFrame([
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P", "value": 4},
    ])
    mappings = pd.DataFrame([
        {"source_system": "ESTO", "source_flow": "F", "source_product": "P.1", "component_esto_flow": "F", "component_esto_product": "P.1"},
    ])
    common = pd.DataFrame([
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "P.1", "common_row_id": "c1"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "c1", "value": 4},
    ])
    row = validate_source_parent_anchors(source, tree, mappings, common, comparison).iloc[0]
    assert row["status"] == "passed"
    assert row["reason"] == "within_tolerance_zero_only_missing_children"
    assert row["missing_expected_children"] == "P.2"  # still reported for lineage
    assert row["missing_nonzero_child_count"] == 0
    assert row["frontier_sum"] == 4


def test_zero_only_missing_child_is_classified_as_source_inconsistency() -> None:
    source, tree, mappings, common, comparison = _fixture(
        child_b_value=0,
        include_child_b_mapping=False,
    )
    comparison = comparison[comparison["common_row_id"] == "c1"].copy()
    row = validate_source_parent_anchors(source, tree, mappings, common, comparison).iloc[0]
    assert row["status"] == "failed"
    assert row["reason"] == "parent_child_source_inconsistency"
    assert row["missing_nonzero_child_count"] == 0
    assert row["missing_zero_or_absent_child_count"] == 1


def test_tolerance_boundary_and_summary() -> None:
    source, tree, mappings, common, comparison = _fixture(child_b_value=6.01)
    comparison.loc[comparison["common_row_id"] == "c2", "value"] = 6
    detail = validate_source_parent_anchors(
        source, tree, mappings, common, comparison, tolerance=0.001
    )
    assert detail.iloc[0]["status"] == "passed"
    summary = summarise_source_parent_anchors(detail)
    assert summary.iloc[0][["eligible", "passed", "failed", "skipped"]].tolist() == [1, 1, 0, 0]


def test_missing_intermediate_resolves_to_grandchildren() -> None:
    source, tree, mappings, common, comparison = _fixture()
    tree = pd.concat([tree, pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "P.I", "parent_code": "P"},
        {"dataset": "esto", "axis": "product", "code": "P.1", "parent_code": "P.I"},
        {"dataset": "esto", "axis": "product", "code": "P.2", "parent_code": "P.I"},
    ])], ignore_index=True)
    tree = tree[~((tree["code"].isin(["P.1", "P.2"])) & (tree["parent_code"] == "P"))]
    detail = validate_source_parent_anchors(source, tree, mappings, common, comparison)
    parent = detail[detail["parent_code"] == "P"].iloc[0]
    assert parent["status"] == "passed"
    assert parent["frontier_row_count"] == 2


def test_zero_eligible_summary_is_not_passed() -> None:
    summary = summarise_source_parent_anchors(pd.DataFrame())
    assert summary.empty


# --- Focused tests for the vectorized restructure of the anchor loop ---

def _multi_partition_fixture():
    """Parent P over two economies and two years; comparison only for E1."""
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "P", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "P.1", "parent_code": "P"},
        {"dataset": "esto", "axis": "product", "code": "P.2", "parent_code": "P"},
    ])
    source = pd.DataFrame([
        {"source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P", "value": 10},
        {"source_system": "ESTO", "economy": "E2", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P", "value": 20},
        {"source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2023, "source_flow": "F", "source_product": "P", "value": 5},
    ])
    mappings = pd.DataFrame([
        {"source_system": "ESTO", "source_flow": "F", "source_product": "P.1", "component_esto_flow": "F", "component_esto_product": "P.1"},
        {"source_system": "ESTO", "source_flow": "F", "source_product": "P.2", "component_esto_flow": "F", "component_esto_product": "P.2"},
    ])
    common = pd.DataFrame([
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "P.1", "common_row_id": "c1"},
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "P.2", "common_row_id": "c2"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2022, "common_row_id": "c1", "value": 4},
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2022, "common_row_id": "c2", "value": 6},
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2023, "common_row_id": "c1", "value": 2},
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2023, "common_row_id": "c2", "value": 3},
    ])
    return source, tree, mappings, common, comparison


def test_partitions_do_not_bleed_and_absent_frontier_fails() -> None:
    detail = validate_source_parent_anchors(*_multi_partition_fixture())
    by_key = {(r["economy"], r["year"]): r for _, r in detail.iterrows()}
    # Each (economy, year) keeps its own parent total — no cross-partition sum.
    assert by_key[("E1", 2022)]["parent_value"] == 10
    assert by_key[("E1", 2022)]["frontier_sum"] == 10
    assert by_key[("E1", 2022)]["status"] == "passed"
    assert by_key[("E1", 2023)]["parent_value"] == 5
    assert by_key[("E1", 2023)]["frontier_sum"] == 5
    assert by_key[("E1", 2023)]["status"] == "passed"
    # E2 has a resolvable frontier but no comparison rows -> frontier_rows_absent.
    assert by_key[("E2", 2022)]["parent_value"] == 20
    assert by_key[("E2", 2022)]["frontier_sum"] == 0
    assert by_key[("E2", 2022)]["status"] == "failed"
    assert by_key[("E2", 2022)]["reason"] == "frontier_rows_absent"


def test_zero_parent_without_source_frontier_is_unanchorable() -> None:
    source, tree, mappings, common, comparison = _multi_partition_fixture()
    source = source[(source["economy"] == "E2")].copy()
    source["value"] = 0.0
    detail = validate_source_parent_anchors(source, tree, mappings, common, comparison)

    row = detail.iloc[0]
    assert row["status"] == "skipped"
    assert row["reason"] == "no_observed_source_frontier"


def test_missing_common_boundary_is_unanchorable_even_when_source_value_is_nonzero() -> None:
    source, tree, mappings, common, comparison = _fixture()
    common = pd.DataFrame([
        {"comparison_scope": "esto_only", "component_esto_flow": "OTHER",
         "component_esto_product": "OTHER", "common_row_id": "cX"},
    ])
    comparison = comparison.iloc[0:0]

    row = validate_source_parent_anchors(source, tree, mappings, common, comparison).iloc[0]

    assert row["status"] == "skipped"
    assert row["reason"] == "no_anchorable_common_esto_boundary"


def test_signed_parent_and_frontier_sums() -> None:
    source, tree, mappings, common, comparison = _multi_partition_fixture()
    # Split E1/2022 parent into a positive and a negative row (nets to 10).
    source = pd.DataFrame([
        {"source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P", "value": 12},
        {"source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P", "value": -2},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2022, "common_row_id": "c1", "value": 13},
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E1", "scenario": "historical", "year": 2022, "common_row_id": "c2", "value": -3},
    ])
    row = validate_source_parent_anchors(source, tree, mappings, common, comparison).iloc[0]
    assert row["parent_value"] == 10
    assert row["parent_positive_value"] == 12
    assert row["parent_negative_value"] == -2
    assert row["frontier_sum"] == 10
    assert row["frontier_positive_sum"] == 13
    assert row["frontier_negative_sum"] == -3
    assert row["status"] == "passed"


def test_unmodelled_source_codes_are_dropped() -> None:
    # Parent product coded "19 ..." (an aggregate fuel) must be dropped when
    # fuel 19 is in the unmodelled-source set, regardless of its numeric outcome.
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "19 Total", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "19.01 A", "parent_code": "19 Total"},
    ])
    source = pd.DataFrame([
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "19 Total", "value": 10},
    ])
    mappings = pd.DataFrame([
        {"source_system": "ESTO", "source_flow": "F", "source_product": "19.01 A", "component_esto_flow": "F", "component_esto_product": "19.01 A"},
    ])
    common = pd.DataFrame([
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "19.01 A", "common_row_id": "c1"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "c1", "value": 999},
    ])
    without = validate_source_parent_anchors(source, tree, mappings, common, comparison)
    assert not without.empty  # normally evaluated and reported
    withx = validate_source_parent_anchors(
        source, tree, mappings, common, comparison,
        unmodelled_source_codes={"sector": set(), "fuel": {19}},
    )
    assert withx.empty  # excepted fuel 19 -> row dropped entirely
    # A non-excepted fuel code is unaffected.
    keep = validate_source_parent_anchors(
        source, tree, mappings, common, comparison,
        unmodelled_source_codes={"sector": set(), "fuel": {99}},
    )
    assert not keep.empty


def _rollup_child_fixture():
    """Parent P with an ordinary child P.1 and a rollup-subtotal child NX.

    NX is itself a genuine raw-ESTO tree node with further tree children
    (NX.1, NX.2), so absent any rollup awareness it is also validated as an
    additive parent. Its own reported value (10) is intentionally not the sum
    of its declared ESTO-tree children (NX.1 + NX.2 = 6) -- exactly the
    NON_EXPANDING/DETACHED semantics, where NX's value comes from an explicit
    rollup-rule contributor sum rather than literal tree additivity. P's own
    frontier still correctly resolves NX as one atomic mapped member (10), so
    P reconciles regardless of the fix.
    """
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "P", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "P.1", "parent_code": "P"},
        {"dataset": "esto", "axis": "product", "code": "NX", "parent_code": "P"},
        {"dataset": "esto", "axis": "product", "code": "NX.1", "parent_code": "NX"},
        {"dataset": "esto", "axis": "product", "code": "NX.2", "parent_code": "NX"},
    ])
    source = pd.DataFrame([
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P", "value": 20},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "P.1", "value": 10},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "NX", "value": 10},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "NX.1", "value": 3},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "NX.2", "value": 3},
    ])
    mappings = pd.DataFrame([
        {"source_system": "ESTO", "source_flow": "F", "source_product": "P.1", "component_esto_flow": "F", "component_esto_product": "P.1"},
        {"source_system": "ESTO", "source_flow": "F", "source_product": "NX", "component_esto_flow": "F", "component_esto_product": "NX"},
        {"source_system": "ESTO", "source_flow": "F", "source_product": "NX.1", "component_esto_flow": "F", "component_esto_product": "NX.1"},
        {"source_system": "ESTO", "source_flow": "F", "source_product": "NX.2", "component_esto_flow": "F", "component_esto_product": "NX.2"},
    ])
    common = pd.DataFrame([
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "P.1", "common_row_id": "c1"},
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "NX", "common_row_id": "c2"},
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "NX.1", "common_row_id": "c3"},
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "NX.2", "common_row_id": "c4"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "c1", "value": 10},
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "c2", "value": 10},
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "c3", "value": 3},
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "c4", "value": 3},
    ])
    return source, tree, mappings, common, comparison


def test_non_expanding_rollup_child_not_validated_as_additive_parent() -> None:
    source, tree, mappings, common, comparison = _rollup_child_fixture()

    # Without rollup awareness, NX is spuriously validated as its own
    # additive parent (10 != NX.1 + NX.2 == 6) and fails.
    baseline = validate_source_parent_anchors(source, tree, mappings, common, comparison)
    nx_rows = baseline[baseline["parent_code"] == "NX"]
    assert len(nx_rows) == 1
    assert nx_rows.iloc[0]["status"] == "failed"
    assert nx_rows.iloc[0]["reason"] == "difference_exceeds_tolerance"
    # P's own additive check is unaffected either way: it resolves NX as one
    # atomic mapped member (10), so P's frontier (P.1 + NX == 10 + 10 == 20)
    # already reconciles without the fix.
    p_row_baseline = baseline[baseline["parent_code"] == "P"].iloc[0]
    assert p_row_baseline["status"] == "passed"
    assert p_row_baseline["frontier_sum"] == 20

    # With NX declared as a NON_EXPANDING/DETACHED rollup label, it must no
    # longer be validated as an additive parent at all.
    fixed = validate_source_parent_anchors(
        source, tree, mappings, common, comparison, exclude_parents={"NX"},
    )
    assert fixed[fixed["parent_code"] == "NX"].empty
    p_row_fixed = fixed[fixed["parent_code"] == "P"].iloc[0]
    assert p_row_fixed["status"] == "passed"
    assert p_row_fixed["frontier_sum"] == 20


def test_ordinary_additive_parent_still_fails_when_genuinely_broken() -> None:
    # Adjacent ordinary-additive case: excluding the unrelated rollup label
    # "NX" must not mask a genuine parent/child mismatch elsewhere.
    source, tree, mappings, common, comparison = _rollup_child_fixture()
    source.loc[source["source_product"] == "P.1", "value"] = 4  # was 10; now P != P.1 + NX
    comparison.loc[comparison["common_row_id"] == "c1", "value"] = 4

    detail = validate_source_parent_anchors(
        source, tree, mappings, common, comparison, exclude_parents={"NX"},
    )
    p_row = detail[detail["parent_code"] == "P"].iloc[0]
    assert p_row["status"] == "failed"
    assert p_row["reason"] == "difference_exceeds_tolerance"


def _excluded_label_with_no_own_row_fixture():
    """Grandparent GP -> excluded NON_EXPANDING label NX (no raw row of its
    own, unlike ``_rollup_child_fixture``'s NX) -> real children NX.1/NX.2.

    Mirrors the real ``16 Other sector`` -> ``16.01-16.02 Buildings`` (never
    a literal row in the raw ESTO file) -> ``16.01``/``16.02`` shape. GP's
    frontier can *only* be reconciled by descending through NX into its real
    children -- if excluding NX from independent parent validation also
    removes it from the raw tree's parent/child edges (the bug this test
    guards against), ``_mapped_descendants`` can never reach NX.1/NX.2 at
    all and GP's frontier silently collapses to empty.
    """
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "GP", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "NX", "parent_code": "GP"},
        {"dataset": "esto", "axis": "product", "code": "NX.1", "parent_code": "NX"},
        {"dataset": "esto", "axis": "product", "code": "NX.2", "parent_code": "NX"},
    ])
    source = pd.DataFrame([
        # No row for "NX" itself -- it is never a literal raw source row.
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "GP", "value": 6},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "NX.1", "value": 3},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "F", "source_product": "NX.2", "value": 3},
    ])
    mappings = pd.DataFrame([
        {"source_system": "ESTO", "source_flow": "F", "source_product": "NX.1", "component_esto_flow": "F", "component_esto_product": "NX.1"},
        {"source_system": "ESTO", "source_flow": "F", "source_product": "NX.2", "component_esto_flow": "F", "component_esto_product": "NX.2"},
    ])
    common = pd.DataFrame([
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "NX.1", "common_row_id": "c1"},
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "NX.2", "common_row_id": "c2"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "c1", "value": 3},
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "c2", "value": 3},
    ])
    return source, tree, mappings, common, comparison


def test_excluded_parent_still_descendable_from_a_grandparent() -> None:
    source, tree, mappings, common, comparison = _excluded_label_with_no_own_row_fixture()
    detail = validate_source_parent_anchors(
        source, tree, mappings, common, comparison, exclude_parents={"NX"},
    )
    # NX itself must not be independently validated as a parent.
    assert detail[detail["parent_code"] == "NX"].empty
    # GP must still reconcile by descending through NX into NX.1 + NX.2,
    # not silently collapse to an empty frontier because NX was excluded.
    gp_row = detail[detail["parent_code"] == "GP"].iloc[0]
    assert gp_row["frontier_row_count"] == 2
    assert gp_row["frontier_sum"] == 6
    assert gp_row["status"] == "passed"


def _duplicated_rollup_value_fixture(plants_leaf_value: float = 10):
    """Ninth-shaped fixture reproducing a raw source hierarchy that reports the
    same subtotal as a literal row at two flow depths at once (mirroring the
    real ``12_solar`` / ``09_01_electricity_plants`` case): a leaf sector
    ("Solar") and its parent ("Plants") both carry an explicit "x"-rollup row
    for product "P" with the identical value, because Solar is the only
    contributor under Plants for this product.
    """
    tree = pd.DataFrame([
        {"dataset": "ninth", "axis": "sector", "code": "Total", "parent_code": ""},
        {"dataset": "ninth", "axis": "sector", "code": "Plants", "parent_code": "Total"},
        {"dataset": "ninth", "axis": "sector", "code": "Solar", "parent_code": "Plants"},
        {"dataset": "ninth", "axis": "fuel", "code": "P", "parent_code": ""},
        {"dataset": "ninth", "axis": "fuel", "code": "P.1", "parent_code": "P"},
        {"dataset": "ninth", "axis": "fuel", "code": "P.2", "parent_code": "P"},
    ])
    source = pd.DataFrame([
        # Mapped subfuel detail, literally reported under "Plants".
        {"source_system": "NINTH", "economy": "E", "scenario": "reference", "year": 2023,
         "source_flow": "Plants", "source_product": "P.1", "value": 4},
        {"source_system": "NINTH", "economy": "E", "scenario": "reference", "year": 2023,
         "source_flow": "Plants", "source_product": "P.2", "value": 6},
        # Plants' own "x"-rollup subtotal for P -- a literal row in its own
        # right, not merely a derived total.
        {"source_system": "NINTH", "economy": "E", "scenario": "reference", "year": 2023,
         "source_flow": "Plants", "source_product": "P", "value": 10},
        # Solar (Plants' only child) reports the identical subtotal for P,
        # since it is the sole contributor -- this is the row that must not
        # be silently remapped onto Plants' already-present P row above.
        {"source_system": "NINTH", "economy": "E", "scenario": "reference", "year": 2023,
         "source_flow": "Solar", "source_product": "P", "value": plants_leaf_value},
    ])
    mappings = pd.DataFrame([
        {"source_system": "NINTH", "source_flow": "Plants", "source_product": "P.1",
         "component_esto_flow": "F", "component_esto_product": "P.1"},
        {"source_system": "NINTH", "source_flow": "Plants", "source_product": "P.2",
         "component_esto_flow": "F", "component_esto_product": "P.2"},
    ])
    common = pd.DataFrame([
        {"comparison_scope": "esto_leap_ninth", "component_esto_flow": "F",
         "component_esto_product": "P.1", "common_row_id": "c1"},
        {"comparison_scope": "esto_leap_ninth", "component_esto_flow": "F",
         "component_esto_product": "P.2", "common_row_id": "c2"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "esto_leap_ninth", "source_system": "NINTH", "economy": "E",
         "scenario": "reference", "year": 2023, "common_row_id": "c1", "value": 4},
        {"comparison_scope": "esto_leap_ninth", "source_system": "NINTH", "economy": "E",
         "scenario": "reference", "year": 2023, "common_row_id": "c2", "value": 6},
    ])
    return source, tree, mappings, common, comparison


def test_leaf_remap_onto_ancestor_with_own_literal_row_is_not_double_counted() -> None:
    source, tree, mappings, common, comparison = _duplicated_rollup_value_fixture()
    # "Plants" is excluded from being validated as its own additive *flow*
    # parent here -- irrelevant to this test, which is about the *product*
    # axis parent "P" -- and sidesteps an unrelated, pre-existing edge case
    # in resolve_parent_to_mapped_other_axis (structural_resolver.py) that
    # raises when a flow-axis subtree has zero resolvable other-axis
    # candidates for a top-level (parentless) product code such as "P".
    detail = validate_source_parent_anchors(
        source, tree, mappings, common, comparison, exclude_parents={"Plants"},
    )
    product_rows = detail[detail["validation_axis"] == "product"]

    plants_row = product_rows[
        (product_rows["parent_code"] == "P") & (product_rows["other_axis_value"] == "Plants")
    ].iloc[0]
    # Before the fix this summed Plants' own row (10) plus the Solar leaf
    # remapped onto the same (P, Plants) key (10) -> parent_value 20 against
    # frontier_sum 10 (the exact 0.5 ratio the real 12_solar rows showed).
    assert plants_row["parent_value"] == 10
    assert plants_row["frontier_sum"] == 10
    assert plants_row["status"] == "passed"

    # The Solar leaf must not have been silently folded into Plants' group;
    # it either forms its own unanchorable group or is absent entirely, but
    # it must never contribute to a doubled Plants total.
    solar_rows = product_rows[
        (product_rows["parent_code"] == "P") & (product_rows["other_axis_value"] == "Solar")
    ]
    if not solar_rows.empty:
        assert solar_rows.iloc[0]["status"] == "skipped"

    assert (product_rows["parent_code"] == "P").sum() <= 2


def test_leaf_remap_onto_unmapped_ancestor_still_reconciles() -> None:
    # Adjacent legitimate case: the ancestor has NO literal row of its own,
    # so the leaf's remap onto it is the only source of that group's value
    # and must keep working exactly as before (this is the majority use of
    # the resolver -- e.g. the passenger-road pattern).
    source, tree, mappings, common, comparison = _duplicated_rollup_value_fixture()
    # Drop only Plants' own "x"-rollup row for P -- keep its mapped P.1/P.2
    # detail rows, so Plants has no literal row of its own for P and must
    # rely entirely on the Solar leaf's remap to reconcile.
    source = source[
        ~((source["source_flow"] == "Plants") & (source["source_product"] == "P"))
    ].copy()
    detail = validate_source_parent_anchors(source, tree, mappings, common, comparison)
    product_rows = detail[detail["validation_axis"] == "product"]
    row = product_rows[
        (product_rows["parent_code"] == "P") & (product_rows["other_axis_value"] == "Plants")
    ].iloc[0]
    assert row["status"] == "passed"
    assert row["frontier_sum"] == 10
    assert row["parent_value"] == 10


def test_leaf_remap_onto_ancestor_with_own_row_still_fails_on_real_mismatch() -> None:
    # A genuine mismatch at the ancestor's own literal row must still be
    # reported -- suppressing the leaf's remap must not mask real breakage.
    source, tree, mappings, common, comparison = _duplicated_rollup_value_fixture()
    source.loc[
        (source["source_flow"] == "Plants") & (source["source_product"] == "P"), "value"
    ] = 999
    detail = validate_source_parent_anchors(
        source, tree, mappings, common, comparison, exclude_parents={"Plants"},
    )
    product_rows = detail[detail["validation_axis"] == "product"]
    plants_row = product_rows[
        (product_rows["parent_code"] == "P") & (product_rows["other_axis_value"] == "Plants")
    ].iloc[0]
    assert plants_row["status"] == "failed"
    assert plants_row["reason"] == "difference_exceeds_tolerance"
    assert plants_row["parent_value"] == 999
    assert plants_row["frontier_sum"] == 10


def test_scope_without_anchorable_boundary_is_skipped() -> None:
    source, tree, mappings, common, comparison = _multi_partition_fixture()
    source = source[(source["economy"] == "E1") & (source["year"] == 2022)]
    # Add a second scope that ESTO participates in but whose common rows do NOT
    # cover P.1/P.2 -> frontier resolves to no common_row_id -> skipped.
    common = pd.concat([common, pd.DataFrame([
        {"comparison_scope": "esto_leap", "component_esto_flow": "F", "component_esto_product": "OTHER", "common_row_id": "cX"},
    ])], ignore_index=True)
    detail = validate_source_parent_anchors(source, tree, mappings, common, comparison)
    by_scope = {r["comparison_scope"]: r for _, r in detail.iterrows()}
    assert by_scope["esto_only"]["status"] == "passed"
    assert by_scope["esto_leap"]["status"] == "skipped"
    assert by_scope["esto_leap"]["reason"] == "no_anchorable_common_esto_boundary"


def _pruned_subtotal_fixture():
    """Mirrors the real ``16.01 Commercial and public services`` case.

    ``16.01`` is a genuine raw-ESTO node with its own explicit subtotal row
    and its own identity mapping, but Common ESTO structure building has
    pruned every comparison row for that exact component pair as a duplicate
    of its only real child, ``16.01.99``, whose own value is numerically
    identical. ``16.01`` also has a second declared child, ``16.01.01``,
    that is absent from the raw source entirely (zero/no row). The parent
    ``16`` must still reconcile by descending past ``16.01``'s dataless
    direct row into its real child ``16.01.99``.
    """
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "16", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "16.01", "parent_code": "16"},
        {"dataset": "esto", "axis": "product", "code": "16.02", "parent_code": "16"},
        {"dataset": "esto", "axis": "product", "code": "16.01.01", "parent_code": "16.01"},
        {"dataset": "esto", "axis": "product", "code": "16.01.99", "parent_code": "16.01"},
    ])
    source = pd.DataFrame([
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2023, "source_flow": "F", "source_product": "16", "value": 3287.211173 + 500},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2023, "source_flow": "F", "source_product": "16.01", "value": 3287.211173},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2023, "source_flow": "F", "source_product": "16.01.99", "value": 3287.211173},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2023, "source_flow": "F", "source_product": "16.02", "value": 500},
        # 16.01.01 is absent entirely -- no raw row at all.
    ])
    mappings = pd.DataFrame([
        {"source_system": "ESTO", "source_flow": "F", "source_product": "16.01", "component_esto_flow": "F", "component_esto_product": "16.01"},
        {"source_system": "ESTO", "source_flow": "F", "source_product": "16.01.99", "component_esto_flow": "F", "component_esto_product": "16.01.99"},
        {"source_system": "ESTO", "source_flow": "F", "source_product": "16.02", "component_esto_flow": "F", "component_esto_product": "16.02"},
    ])
    common = pd.DataFrame([
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "16.01", "common_row_id": "c_1601"},
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "16.01.99", "common_row_id": "c_160199"},
        {"comparison_scope": "esto_only", "component_esto_flow": "F", "component_esto_product": "16.02", "common_row_id": "c_1602"},
    ])
    comparison = pd.DataFrame([
        # No row at all for c_1601 -- Common ESTO pruned it as a duplicate of
        # 16.01.99's contribution.
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2023, "common_row_id": "c_160199", "value": 3287.211173},
        {"comparison_scope": "esto_only", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2023, "common_row_id": "c_1602", "value": 500},
    ])
    return source, tree, mappings, common, comparison


def test_parent_reconciles_through_pruned_direct_subtotal_with_real_child_data() -> None:
    source, tree, mappings, common, comparison = _pruned_subtotal_fixture()
    detail = validate_source_parent_anchors(source, tree, mappings, common, comparison)
    row = detail[detail["parent_code"] == "16"].iloc[0]
    assert row["status"] == "passed"
    assert row["frontier_sum"] == 3287.211173 + 500
    # 16.01.01 (absent, zero source evidence) is still surfaced for lineage.
    assert row["missing_expected_children"] == "16.01.01"


def _shared_frontier_fixture():
    """Two raw products (other_axis_value A/B) under one parent P.

    Mirrors the real LEAP "Oil Refining" case: at the ``distinct`` scope each
    raw product maps onto its OWN Common ESTO row (a genuine 1:1 mapping), but
    at the ``shared`` scope Common ESTO legitimately collapses both products'
    only child (``P.1``) onto a SINGLE aggregate row (e.g. because the source
    that scope's raw data comes from cannot distinguish the sub-products).
    The true combined total (A's 6 + B's 4 == 10) matches the shared row's
    comparison value exactly, but individually neither 6 nor 4 does.
    """
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "P", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "P.1", "parent_code": "P"},
    ])
    source = pd.DataFrame([
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "A", "source_product": "P", "value": 6},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "A", "source_product": "P.1", "value": 6},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "B", "source_product": "P", "value": 4},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "B", "source_product": "P.1", "value": 4},
    ])
    mappings = pd.DataFrame([
        {"source_system": "ESTO", "source_flow": "A", "source_product": "P.1", "component_esto_flow": "FA", "component_esto_product": "P.1"},
        {"source_system": "ESTO", "source_flow": "B", "source_product": "P.1", "component_esto_flow": "FB", "component_esto_product": "P.1"},
    ])
    common = pd.DataFrame([
        # distinct scope: each raw product's own exact Common ESTO row.
        {"comparison_scope": "distinct", "component_esto_flow": "FA", "component_esto_product": "P.1", "common_row_id": "id_a"},
        {"comparison_scope": "distinct", "component_esto_flow": "FB", "component_esto_product": "P.1", "common_row_id": "id_b"},
        # shared scope: both products collapse onto one aggregate row.
        {"comparison_scope": "shared", "component_esto_flow": "FA", "component_esto_product": "P.1", "common_row_id": "id_shared"},
        {"comparison_scope": "shared", "component_esto_flow": "FB", "component_esto_product": "P.1", "common_row_id": "id_shared"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "distinct", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "id_a", "value": 6},
        {"comparison_scope": "distinct", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "id_b", "value": 4},
        {"comparison_scope": "shared", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "id_shared", "value": 10},
    ])
    return source, tree, mappings, common, comparison


def test_shared_frontier_group_is_combined_not_individually_failed() -> None:
    source, tree, mappings, common, comparison = _shared_frontier_fixture()
    detail = validate_source_parent_anchors(source, tree, mappings, common, comparison)

    shared_rows = detail[
        (detail["comparison_scope"] == "shared") & (detail["parent_code"] == "P")
    ]
    # No row is silently dropped -- one combined/primary row plus one skipped.
    assert len(shared_rows) == 2
    primary = shared_rows[shared_rows["status"] != "skipped"].iloc[0]
    skipped = shared_rows[shared_rows["status"] == "skipped"].iloc[0]

    assert primary["status"] == "passed"
    assert primary["parent_value"] == 10  # combined A (6) + B (4)
    assert primary["frontier_sum"] == 10
    assert set(primary["other_axis_value"].split(" + ")) == {"A", "B"}

    assert skipped["reason"] == "grouped_with_shared_frontier_sibling"


def test_distinct_frontier_scope_is_unaffected_by_shared_scope_grouping() -> None:
    # The non-grouped case (each other_axis_value resolves to its own
    # distinct common_row_id) must reconcile individually and completely
    # unaffected by the shared-frontier grouping happening in another scope.
    source, tree, mappings, common, comparison = _shared_frontier_fixture()
    detail = validate_source_parent_anchors(source, tree, mappings, common, comparison)

    distinct_rows = detail[
        (detail["comparison_scope"] == "distinct") & (detail["parent_code"] == "P")
    ]
    assert len(distinct_rows) == 2
    by_other = {r["other_axis_value"]: r for _, r in distinct_rows.iterrows()}
    assert by_other["A"]["status"] == "passed"
    assert by_other["A"]["parent_value"] == 6
    assert by_other["A"]["frontier_sum"] == 6
    assert by_other["B"]["status"] == "passed"
    assert by_other["B"]["parent_value"] == 4
    assert by_other["B"]["frontier_sum"] == 4


def _overlapping_signature_fixture():
    """Three raw flows (X, Y, Z) under parent product ``P``, mirroring the
    real ``10.01 Own Use`` coal-by-products shape: their registered
    ``common_row_id`` sets overlap but are NOT identical, because one flow
    (X) additionally has its own extra, non-shared component (analogous to
    ``10.01.11 Oil refineries`` registering only ``02.01`` as an exact row
    while every other flow child registers the whole family into one shared
    row). Under the old exact-signature-equality rule this fails to fully
    group: X (signature ``{shared, distinct}``) would stay standalone while
    Y and Z (signature ``{shared}`` each) would group with each other only.
    Under connected components all three belong in ONE group, since X's
    signature overlaps both Y's and Z's via the shared id.
    """
    tree = pd.DataFrame([
        {"dataset": "esto", "axis": "product", "code": "P", "parent_code": ""},
        {"dataset": "esto", "axis": "product", "code": "P.1", "parent_code": "P"},
        {"dataset": "esto", "axis": "product", "code": "P.2", "parent_code": "P"},
    ])
    source = pd.DataFrame([
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "X", "source_product": "P", "value": 70},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "Y", "source_product": "P", "value": 20},
        {"source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "source_flow": "Z", "source_product": "P", "value": 15},
    ])
    mappings = pd.DataFrame([
        # X registers BOTH the shared component (like every ordinary flow
        # child) AND its own extra, non-shared component (like
        # "10.01.11 Oil refineries" registering only "02.01" as an exact row).
        {"source_system": "ESTO", "source_flow": "X", "source_product": "P.1", "component_esto_flow": "FX1", "component_esto_product": "P.1"},
        {"source_system": "ESTO", "source_flow": "X", "source_product": "P.2", "component_esto_flow": "FX2", "component_esto_product": "P.2"},
        # Y and Z only ever register the shared component.
        {"source_system": "ESTO", "source_flow": "Y", "source_product": "P.1", "component_esto_flow": "FY", "component_esto_product": "P.1"},
        {"source_system": "ESTO", "source_flow": "Z", "source_product": "P.1", "component_esto_flow": "FZ", "component_esto_product": "P.1"},
    ])
    common = pd.DataFrame([
        {"comparison_scope": "mixed", "component_esto_flow": "FX1", "component_esto_product": "P.1", "common_row_id": "id_shared"},
        {"comparison_scope": "mixed", "component_esto_flow": "FY", "component_esto_product": "P.1", "common_row_id": "id_shared"},
        {"comparison_scope": "mixed", "component_esto_flow": "FZ", "component_esto_product": "P.1", "common_row_id": "id_shared"},
        {"comparison_scope": "mixed", "component_esto_flow": "FX2", "component_esto_product": "P.2", "common_row_id": "id_distinct"},
    ])
    comparison = pd.DataFrame([
        {"comparison_scope": "mixed", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "id_shared", "value": 100},
        {"comparison_scope": "mixed", "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022, "common_row_id": "id_distinct", "value": 5},
    ])
    return source, tree, mappings, common, comparison


def test_overlapping_but_not_identical_signatures_group_via_connected_components() -> None:
    source, tree, mappings, common, comparison = _overlapping_signature_fixture()
    detail = validate_source_parent_anchors(source, tree, mappings, common, comparison)

    rows = detail[(detail["comparison_scope"] == "mixed") & (detail["parent_code"] == "P")]
    # All three (X, Y, Z) collapse into one group -- one primary row plus two
    # skipped, not "X standalone" + "Y+Z grouped" as exact-equality grouping
    # would have produced.
    assert len(rows) == 3
    primary_rows = rows[rows["status"] != "skipped"]
    skipped_rows = rows[rows["status"] == "skipped"]
    assert len(primary_rows) == 1
    assert len(skipped_rows) == 2

    primary = primary_rows.iloc[0]
    assert set(primary["other_axis_value"].split(" + ")) == {"X", "Y", "Z"}
    # Combined raw total: X (70) + Y (20) + Z (15) == 105.
    assert primary["parent_value"] == 105
    # Recomputed frontier_sum is the UNION of common_row_ids touched by any
    # member, each counted once -- id_shared (100) + id_distinct (5) == 105,
    # NOT id_shared counted three times (one per member) or omitted entirely.
    assert primary["frontier_sum"] == 105
    assert primary["frontier_row_count"] == 2
    assert primary["status"] == "passed"

    for _, skipped in skipped_rows.iterrows():
        assert skipped["reason"] == "grouped_with_shared_frontier_sibling"


def test_non_expanding_direct_match_with_real_data_is_not_descended() -> None:
    # Regression guard for the previously-reverted structural heuristic: a
    # node with its OWN real comparison data must never be discarded in favor
    # of descending into its children just because a child also has a direct
    # row -- NON_EXPANDING rollup values are legitimately different from the
    # literal sum of their raw-tree children by design (see
    # test_non_expanding_rollup_child_not_validated_as_additive_parent).
    source, tree, mappings, common, comparison = _rollup_child_fixture()
    detail = validate_source_parent_anchors(source, tree, mappings, common, comparison)
    p_row = detail[detail["parent_code"] == "P"].iloc[0]
    # NX resolves to its own real, atomic value (10), not NX.1 + NX.2 (6).
    assert p_row["frontier_sum"] == 20


def _write_data_quality_exception_workbook(tmp_path, **overrides) -> "Path":
    from pathlib import Path

    workbook_path = Path(tmp_path) / "exceptions.xlsx"
    row = {
        "enabled": True,
        "source_system": "NINTH",
        "validation_axis": "product",
        "parent_code": "16_others",
        "other_axis_value": "09_total_transformation_sector/09_01_electricity_plants",
        "economy": "",
        "parent_value": "-12.37876",
        "notes": "known NINTH self-inconsistency, reviewed 2026-07-24",
    }
    row.update(overrides)
    pd.DataFrame([row]).to_excel(workbook_path, sheet_name=DATA_QUALITY_EXCEPTION_SHEET, index=False)
    return workbook_path


def _data_quality_candidate_rows() -> pd.DataFrame:
    base = {
        "source_system": "NINTH",
        "validation_axis": "product",
        "parent_code": "16_others",
        "other_axis_value": "09_total_transformation_sector/09_01_electricity_plants",
    }
    return pd.DataFrame([
        {**base, "status": "failed", "parent_value": -12.37876},
        # A different parent_value at the same code/label key -- must NOT
        # inherit the exception meant for the -12.37876 case.
        {**base, "status": "failed", "parent_value": -999.0},
        # Already-passing rows are never checked against the sheet.
        {**base, "status": "passed", "parent_value": -12.37876},
    ])


def test_data_quality_exception_flags_matching_failed_row_without_changing_status(tmp_path) -> None:
    workbook_path = _write_data_quality_exception_workbook(tmp_path)
    result = _data_quality_candidate_rows()

    augmented = _augment_with_data_quality_exceptions(result, workbook_path=workbook_path)

    assert augmented["status"].tolist() == ["failed", "failed", "passed"]
    assert bool(augmented.iloc[0]["known_data_quality_exception"]) is True
    assert "known NINTH self-inconsistency" in augmented.iloc[0]["data_quality_exception_notes"]


def test_data_quality_exception_does_not_match_a_different_parent_value(tmp_path) -> None:
    """A stale exception (or a fresh, unrelated bug landing on the same
    code/label key) must not silently inherit an old sign-off."""
    workbook_path = _write_data_quality_exception_workbook(tmp_path)
    result = _data_quality_candidate_rows()

    augmented = _augment_with_data_quality_exceptions(result, workbook_path=workbook_path)

    assert bool(augmented.iloc[1]["known_data_quality_exception"]) is False
    assert augmented.iloc[1]["data_quality_exception_notes"] == ""


def test_data_quality_exception_never_checks_already_passing_rows(tmp_path) -> None:
    workbook_path = _write_data_quality_exception_workbook(tmp_path)
    result = _data_quality_candidate_rows()

    augmented = _augment_with_data_quality_exceptions(result, workbook_path=workbook_path)

    assert bool(augmented.iloc[2]["known_data_quality_exception"]) is False


def test_data_quality_exception_disabled_row_never_matches(tmp_path) -> None:
    workbook_path = _write_data_quality_exception_workbook(tmp_path, enabled=False)
    result = _data_quality_candidate_rows()

    augmented = _augment_with_data_quality_exceptions(result, workbook_path=workbook_path)

    assert bool(augmented.iloc[0]["known_data_quality_exception"]) is False


def test_data_quality_exception_missing_sheet_is_a_no_op(tmp_path) -> None:
    from pathlib import Path

    workbook_path = Path(tmp_path) / "empty.xlsx"
    pd.DataFrame([{"placeholder": 1}]).to_excel(workbook_path, sheet_name="unrelated", index=False)
    result = _data_quality_candidate_rows()

    augmented = _augment_with_data_quality_exceptions(result, workbook_path=workbook_path)

    assert (~augmented["known_data_quality_exception"]).all()


def test_failed_anchor_child_values_show_each_immediate_raw_child() -> None:
    source, tree, _, _, _ = _fixture(child_b_value=6)
    detail = pd.DataFrame([{
        "status": "failed", "validation_axis": "product", "comparison_scope": "esto_only",
        "source_system": "ESTO", "economy": "E", "scenario": "historical", "year": 2022,
        "other_axis_value": "F", "parent_code": "P", "parent_value": 10.0,
        "frontier_sum": 8.0, "difference": 2.0, "abs_error": 2.0,
    }])

    child_values = build_failed_anchor_raw_child_values(detail, source, tree)

    assert set(child_values["child_code"]) == {"P.1", "P.2"}
    by_child = child_values.set_index("child_code")
    assert by_child.loc["P.1", "raw_child_total"] == 4.0
    assert by_child.loc["P.2", "raw_child_total"] == 6.0
    assert (by_child["parent_total"] == 10.0).all()
    assert (by_child["frontier_total"] == 8.0).all()

    context_values = build_failed_anchor_raw_child_context_values(detail, source, tree)
    assert len(context_values) == 2
    assert set(context_values["raw_child_value"]) == {4.0, 6.0}
