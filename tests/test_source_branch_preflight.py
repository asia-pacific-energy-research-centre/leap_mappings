"""Tests for the early LEAP source-branch preflight (interim fallback + All-demand warning)."""

import json

import pandas as pd

from codebase.mapping_tools.source_branch_preflight import (
    SUPPRESS_PARENT_WHEN_DESCENDANTS_RECONCILE,
    apply_all_demand_detail_fallbacks,
    apply_source_branch_fallbacks,
    build_all_demand_representation_status,
    check_all_demand_aggregated_overlap,
    get_demand_sectors_without_detail,
    load_source_branch_fallback_rules,
    resolve_components_for_economy,
    run_leap_source_branch_preflight,
)


def _rules() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "rule_id": "SBF-002",
                "standard_branch": "CHP plants",
                "interim_branch": "CHP interim",
                "action": "warn_and_zero_interim",
                "include": "True",
                "note": "",
            }
        ]
    )


def _leap_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            # 2030: both branches non-zero -> interim zeroed.
            {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "CHP plants", "leap_product": "Natural gas", "value": 10.0},
            {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "CHP interim", "leap_product": "Natural gas", "value": 4.0},
            {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "CHP interim/CHP interim", "leap_product": "Coal", "value": 2.0},
            # 2040: interim only -> retained.
            {"economy": "20_USA", "scenario": "Reference", "year": 2040, "leap_flow": "CHP plants", "leap_product": "Natural gas", "value": 0.0},
            {"economy": "20_USA", "scenario": "Reference", "year": 2040, "leap_flow": "CHP interim", "leap_product": "Natural gas", "value": 5.0},
            # Unrelated branch untouched.
            {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Oil Refining", "leap_product": "Crude oil", "value": 7.0},
        ]
    )


def _parent_reconciliation_rules() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "rule_id": "SBF-004",
                "standard_branch": "Electricity Generation",
                "interim_branch": "",
                "action": SUPPRESS_PARENT_WHEN_DESCENDANTS_RECONCILE,
                "include": "True",
                "note": "",
            }
        ]
    )


class TestScenario4BothNonZero:
    def test_interim_zeroed_in_working_data_and_audited(self) -> None:
        adjusted, audit = apply_source_branch_fallbacks(_leap_rows(), _rules())

        interim_2030 = adjusted[
            adjusted["leap_flow"].str.startswith("CHP interim") & (adjusted["year"] == 2030)
        ]
        assert (interim_2030["value"] == 0.0).all()
        # Standard branch and unrelated branch unchanged.
        assert adjusted[(adjusted["leap_flow"] == "CHP plants") & (adjusted["year"] == 2030)]["value"].iloc[0] == 10.0
        assert adjusted[adjusted["leap_flow"] == "Oil Refining"]["value"].iloc[0] == 7.0

        zeroed = audit[audit["status"] == "interim_zeroed"]
        assert len(zeroed) == 1
        row = zeroed.iloc[0]
        assert row["rule_id"] == "SBF-002"
        assert row["action"] == "warn_and_zero_interim"
        assert row["standard_total"] == 10.0
        assert row["interim_total_original"] == 6.0
        assert row["interim_total_suppressed"] == 6.0
        assert row["interim_rows_zeroed"] == 2

    def test_input_frame_is_not_mutated(self) -> None:
        original = _leap_rows()
        snapshot = original.copy(deep=True)
        apply_source_branch_fallbacks(original, _rules())
        pd.testing.assert_frame_equal(original, snapshot)


class TestScenario5InterimOnly:
    def test_interim_only_period_is_retained(self) -> None:
        adjusted, audit = apply_source_branch_fallbacks(_leap_rows(), _rules())
        interim_2040 = adjusted[(adjusted["leap_flow"] == "CHP interim") & (adjusted["year"] == 2040)]
        assert interim_2040["value"].iloc[0] == 5.0
        retained = audit[audit["status"] == "interim_only_retained"]
        assert len(retained) == 1
        assert retained.iloc[0]["interim_total_retained"] == 5.0
        assert retained.iloc[0]["interim_total_suppressed"] == 0.0


class TestScenario4ReconciledParent:
    def test_parent_action_is_accepted_by_the_rule_loader(self, tmp_path) -> None:
        rules_path = tmp_path / "source_branch_fallback_rules.csv"
        _parent_reconciliation_rules().to_csv(rules_path, index=False)

        loaded = load_source_branch_fallback_rules(rules_path)

        assert loaded["action"].tolist() == [
            SUPPRESS_PARENT_WHEN_DESCENDANTS_RECONCILE
        ]

    def test_exact_multi_product_detail_suppresses_parent_without_mutating_input(self) -> None:
        source = pd.DataFrame(
            [
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Electricity Generation", "leap_product": "Coal", "value": 10.0},
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Electricity Generation", "leap_product": "Gas", "value": 20.0},
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Electricity Generation/Coal plants", "leap_product": "Coal", "value": 10.0},
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Electricity Generation/Gas plants", "leap_product": "Gas", "value": 20.0},
            ]
        )
        snapshot = source.copy(deep=True)

        adjusted, audit = apply_source_branch_fallbacks(source, _parent_reconciliation_rules())

        pd.testing.assert_frame_equal(source, snapshot)
        assert adjusted.loc[adjusted["leap_flow"].eq("Electricity Generation"), "value"].tolist() == [0.0, 0.0]
        assert adjusted.loc[adjusted["leap_flow"].str.contains("/"), "value"].tolist() == [10.0, 20.0]
        row = audit.iloc[0]
        assert row["status"] == "parent_zeroed_detailed_reconciled"
        assert row["reconciliation_status"] == "exact_product_reconciliation"
        assert row["interim_rows_zeroed"] == 2

    def test_value_mismatch_retains_parent(self) -> None:
        source = pd.DataFrame(
            [
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Electricity Generation", "leap_product": "Coal", "value": 10.0},
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Electricity Generation/Coal plants", "leap_product": "Coal", "value": 9.0},
            ]
        )

        adjusted, audit = apply_source_branch_fallbacks(source, _parent_reconciliation_rules())

        assert adjusted.loc[adjusted["leap_flow"].eq("Electricity Generation"), "value"].iloc[0] == 10.0
        assert audit.iloc[0]["status"] == "parent_retained_descendants_incomplete_or_mismatch"
        assert audit.iloc[0]["reconciliation_status"] == "product_set_or_value_mismatch"

    def test_missing_descendant_product_retains_parent(self) -> None:
        source = pd.DataFrame(
            [
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Electricity Generation", "leap_product": "Coal", "value": 10.0},
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Electricity Generation", "leap_product": "Gas", "value": 20.0},
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Electricity Generation/Coal plants", "leap_product": "Coal", "value": 10.0},
            ]
        )

        adjusted, audit = apply_source_branch_fallbacks(source, _parent_reconciliation_rules())

        assert adjusted.loc[adjusted["leap_flow"].eq("Electricity Generation"), "value"].tolist() == [10.0, 20.0]
        assert audit.iloc[0]["status"] == "parent_retained_descendants_incomplete_or_mismatch"

    def test_descendant_only_extra_product_retains_parent(self) -> None:
        source = pd.DataFrame(
            [
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Electricity Generation", "leap_product": "Coal", "value": 10.0},
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Electricity Generation/Coal plants", "leap_product": "Coal", "value": 10.0},
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Electricity Generation/Gas plants", "leap_product": "Gas", "value": 0.0},
            ]
        )

        adjusted, audit = apply_source_branch_fallbacks(source, _parent_reconciliation_rules())

        assert adjusted.loc[adjusted["leap_flow"].eq("Electricity Generation"), "value"].iloc[0] == 10.0
        assert audit.iloc[0]["status"] == "parent_retained_descendants_incomplete_or_mismatch"

    def test_parent_selection_is_isolated_by_scenario_and_year(self) -> None:
        source = pd.DataFrame(
            [
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Electricity Generation", "leap_product": "Coal", "value": 10.0},
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Electricity Generation/Coal plants", "leap_product": "Coal", "value": 10.0},
                {"economy": "20_USA", "scenario": "Target", "year": 2030, "leap_flow": "Electricity Generation", "leap_product": "Coal", "value": 10.0},
                {"economy": "20_USA", "scenario": "Target", "year": 2030, "leap_flow": "Electricity Generation/Coal plants", "leap_product": "Coal", "value": 8.0},
                {"economy": "20_USA", "scenario": "Reference", "year": 2040, "leap_flow": "Electricity Generation", "leap_product": "Coal", "value": 10.0},
                {"economy": "20_USA", "scenario": "Reference", "year": 2040, "leap_flow": "Electricity Generation/Coal plants", "leap_product": "Coal", "value": 8.0},
            ]
        )

        adjusted, audit = apply_source_branch_fallbacks(source, _parent_reconciliation_rules())

        parents = adjusted[adjusted["leap_flow"].eq("Electricity Generation")].set_index(["scenario", "year"])["value"].to_dict()
        assert parents == {("Reference", 2030): 0.0, ("Target", 2030): 10.0, ("Reference", 2040): 10.0}
        assert audit.set_index(["scenario", "year"])["status"].to_dict() == {
            ("Reference", 2030): "parent_zeroed_detailed_reconciled",
            ("Target", 2030): "parent_retained_descendants_incomplete_or_mismatch",
            ("Reference", 2040): "parent_retained_descendants_incomplete_or_mismatch",
        }


class TestScenario6AllDemandWarning:
    def _components(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"economy": "", "aggregated_branch": "All demand aggregated", "component_branch": "Industry", "include": "True", "note": ""},
                {"economy": "", "aggregated_branch": "All demand aggregated", "component_branch": "Buildings", "include": "True", "note": ""},
            ]
        )

    def test_overlap_emits_warning_without_changing_values(self) -> None:
        leap_df = pd.DataFrame(
            [
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "All demand aggregated", "leap_product": "Electricity", "value": 100.0},
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Industry/Manufacturing", "leap_product": "Electricity", "value": 30.0},
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Buildings", "leap_product": "Electricity", "value": 0.0},
            ]
        )
        snapshot = leap_df.copy(deep=True)
        warnings = check_all_demand_aggregated_overlap(leap_df, self._components())
        pd.testing.assert_frame_equal(leap_df, snapshot)

        assert len(warnings) == 1
        row = warnings.iloc[0]
        assert row["aggregated_branch"] == "All demand aggregated"
        assert row["aggregated_total"] == 100.0
        assert row["component_branch"] == "Industry"
        assert row["component_total"] == 30.0
        assert row["nonzero_configured_components"] == "Industry"
        assert "Industry" in row["configured_components"]
        assert "Buildings" in row["configured_components"]
        assert "confirm" in row["reminder"].lower() or "Confirm" in row["reminder"]

    def test_no_warning_when_aggregate_is_zero(self) -> None:
        leap_df = pd.DataFrame(
            [
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "All demand aggregated", "leap_product": "Electricity", "value": 0.0},
                {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Industry", "leap_product": "Electricity", "value": 30.0},
            ]
        )
        warnings = check_all_demand_aggregated_overlap(leap_df, self._components())
        assert warnings.empty


class TestStructuralOverlapConsoleWarnings:
    def test_both_overlap_types_are_prominent_and_audited(self, tmp_path, capsys) -> None:
        rules_path = tmp_path / "source_branch_fallback_rules.csv"
        _rules().to_csv(rules_path, index=False)
        components_path = tmp_path / "all_demand_aggregated_components.json"
        components_path.write_text(
            json.dumps(
                {
                    "aggregated_branch": "All demand aggregated",
                    "components": [
                        {
                            "component_branch": "Industry",
                            "include_by_default": True,
                            "note": "Included in the aggregate placeholder.",
                            "economy_overrides": {},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        leap_df = pd.concat(
            [
                _leap_rows(),
                pd.DataFrame(
                    [
                        {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "All demand aggregated", "leap_product": "Electricity", "value": 100.0},
                        {"economy": "20_USA", "scenario": "Reference", "year": 2030, "leap_flow": "Industry", "leap_product": "Electricity", "value": 30.0},
                    ]
                ),
            ],
            ignore_index=True,
        )

        run_leap_source_branch_preflight(
            leap_df=leap_df,
            fallback_rules_path=rules_path,
            all_demand_components_path=components_path,
            audit_output_dir=tmp_path,
        )

        output = capsys.readouterr().out
        assert "LEAP SOURCE STRUCTURE OVERLAP [INTERIM + STANDARD]" in output
        assert "LEAP SOURCE STRUCTURE OVERLAP [AGGREGATED + DETAILED DEMAND]" in output
        assert "raw LEAP balance export was not changed" in output
        assert (tmp_path / "leap_source_branch_fallback_audit.csv").exists()
        assert (tmp_path / "leap_all_demand_aggregated_overlap_warnings.csv").exists()


class TestEconomyScopedComponents:
    def _components(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                # Wildcard default: every economy lacks Buildings/Industry detail...
                {"economy": "", "aggregated_branch": "All demand aggregated", "component_branch": "Buildings", "include": "True", "note": ""},
                {"economy": "", "aggregated_branch": "All demand aggregated", "component_branch": "Industry", "include": "True", "note": ""},
                # ...except 20_USA, which now has detailed Industry data.
                {"economy": "20_USA", "aggregated_branch": "All demand aggregated", "component_branch": "Industry", "include": "False", "note": "Detailed Industry data added 2026-07-14."},
            ]
        )

    def test_wildcard_applies_when_no_economy_override(self) -> None:
        resolved = resolve_components_for_economy(self._components(), "02_BD")
        assert set(resolved["component_branch"]) == {"Buildings", "Industry"}

    def test_economy_override_replaces_wildcard_for_that_pair_only(self) -> None:
        resolved = resolve_components_for_economy(self._components(), "20_USA")
        # Industry is overridden away (include=False for 20_USA); Buildings still
        # falls back to the wildcard default.
        assert set(resolved["component_branch"]) == {"Buildings"}

    def test_get_demand_sectors_without_detail_is_economy_scoped(self) -> None:
        components_df = self._components()
        assert get_demand_sectors_without_detail(components_df, "02_BD") == ["Buildings", "Industry"]
        assert get_demand_sectors_without_detail(components_df, "20_USA") == ["Buildings"]


class TestMixedPlaceholderAndDetailedDemand:
    def _components(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "economy": "",
                    "aggregated_branch": "All demand aggregated",
                    "component_branch": "Road",
                    "detailed_branches": "Freight road;Passenger road",
                    "detail_activation": "all_present",
                    "include": "True",
                    "note": "",
                }
            ]
        )

    def test_placeholder_only_export_is_retained(self) -> None:
        rows = pd.DataFrame(
            [
                {"economy": "01_AUS", "scenario": "Target", "year": 2030, "leap_flow": "All demand aggregated/Road", "leap_product": "Electricity", "value": 9.0},
            ]
        )
        adjusted, audit = apply_all_demand_detail_fallbacks(rows, self._components())
        assert adjusted["value"].tolist() == [9.0]
        assert audit.iloc[0]["status"] == "placeholder_only_retained"

    def test_complete_detail_suppresses_only_the_road_placeholder(self) -> None:
        rows = pd.DataFrame(
            [
                {"economy": "01_AUS", "scenario": "Target", "year": 2030, "leap_flow": "All demand aggregated/Road", "leap_product": "Electricity", "value": 9.0},
                {"economy": "01_AUS", "scenario": "Target", "year": 2030, "leap_flow": "All demand aggregated/Buildings", "leap_product": "Electricity", "value": 4.0},
                {"economy": "01_AUS", "scenario": "Target", "year": 2030, "leap_flow": "Freight road", "leap_product": "Electricity", "value": 3.0},
                {"economy": "01_AUS", "scenario": "Target", "year": 2030, "leap_flow": "Freight road/Trucks/BEV heavy", "leap_product": "Electricity", "value": 3.0},
                {"economy": "01_AUS", "scenario": "Target", "year": 2030, "leap_flow": "Passenger road", "leap_product": "Electricity", "value": 6.0},
            ]
        )
        snapshot = rows.copy(deep=True)
        adjusted, audit = apply_all_demand_detail_fallbacks(rows, self._components())
        pd.testing.assert_frame_equal(rows, snapshot)
        assert adjusted.loc[adjusted["leap_flow"] == "All demand aggregated/Road", "value"].iloc[0] == 0.0
        assert adjusted.loc[adjusted["leap_flow"] == "All demand aggregated/Buildings", "value"].iloc[0] == 4.0
        assert adjusted.loc[adjusted["leap_flow"] == "Freight road", "value"].iloc[0] == 3.0
        assert audit.iloc[0]["status"] == "detailed_preferred"
        assert audit.iloc[0]["placeholder_total_suppressed"] == 9.0

    def test_complete_detail_without_placeholder_is_available(self) -> None:
        rows = pd.DataFrame(
            [
                {"economy": "01_AUS", "scenario": "Target", "year": 2030, "leap_flow": "Freight road", "leap_product": "Electricity", "value": 3.0},
                {"economy": "01_AUS", "scenario": "Target", "year": 2030, "leap_flow": "Passenger road", "leap_product": "Electricity", "value": 6.0},
            ]
        )
        adjusted, audit = apply_all_demand_detail_fallbacks(rows, self._components())
        pd.testing.assert_frame_equal(adjusted, rows)
        assert audit.iloc[0]["status"] == "detailed_only_used"
        assert audit.iloc[0]["placeholder_rows_zeroed"] == 0

    def test_partial_detail_retains_placeholder(self) -> None:
        rows = pd.DataFrame(
            [
                {"economy": "01_AUS", "scenario": "Target", "year": 2030, "leap_flow": "All demand aggregated/Road", "leap_product": "Electricity", "value": 9.0},
                {"economy": "01_AUS", "scenario": "Target", "year": 2030, "leap_flow": "Freight road", "leap_product": "Electricity", "value": 3.0},
            ]
        )
        adjusted, audit = apply_all_demand_detail_fallbacks(rows, self._components())
        assert adjusted.iloc[0]["value"] == 9.0
        assert audit.iloc[0]["status"] == "partial_detail_placeholder_retained"

    def test_selection_is_independent_for_each_economy(self) -> None:
        rows = pd.DataFrame(
            [
                {"economy": "01_AUS", "scenario": "Target", "year": 2030, "leap_flow": "All demand aggregated/Road", "leap_product": "Electricity", "value": 9.0},
                {"economy": "01_AUS", "scenario": "Target", "year": 2030, "leap_flow": "Freight road", "leap_product": "Electricity", "value": 3.0},
                {"economy": "01_AUS", "scenario": "Target", "year": 2030, "leap_flow": "Passenger road", "leap_product": "Electricity", "value": 6.0},
                {"economy": "20_USA", "scenario": "Target", "year": 2030, "leap_flow": "All demand aggregated/Road", "leap_product": "Electricity", "value": 8.0},
            ]
        )
        adjusted, audit = apply_all_demand_detail_fallbacks(rows, self._components())
        values = adjusted.set_index(["economy", "leap_flow"])["value"]
        assert values.loc[("01_AUS", "All demand aggregated/Road")] == 0.0
        assert values.loc[("20_USA", "All demand aggregated/Road")] == 8.0
        statuses = audit.set_index("economy")["status"].to_dict()
        assert statuses == {
            "01_AUS": "detailed_preferred",
            "20_USA": "placeholder_only_retained",
        }

    def test_representation_status_marks_missing_component_data_unavailable(self) -> None:
        rows = pd.DataFrame(
            [
                {"economy": "01_AUS", "scenario": "Target", "year": 2030, "leap_flow": "All demand aggregated/Road", "leap_product": "Electricity", "value": 9.0},
                {"economy": "01_AUS", "scenario": "Target", "year": 2030, "leap_flow": "Unrelated", "leap_product": "Electricity", "value": 1.0},
            ]
        )
        components = pd.concat(
            [
                self._components(),
                pd.DataFrame(
                    [{"economy": "", "aggregated_branch": "All demand aggregated", "component_branch": "Buildings", "detailed_branches": "Buildings", "detail_activation": "all_present", "include": "True", "note": ""}]
                ),
            ],
            ignore_index=True,
        )
        _, audit = apply_all_demand_detail_fallbacks(rows, components)
        status = build_all_demand_representation_status(rows, components, audit)
        values = status.set_index("component_branch")["representation_status"].to_dict()
        assert values == {
            "Road": "placeholder_only_retained",
            "Buildings": "no_data_unavailable",
        }


class TestInternationalTransportNonzeroFrontier:
    """Regression contract for combined versus Air/Shipping bunker inputs."""

    @staticmethod
    def _components() -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "economy": "",
                    "aggregated_branch": "All demand aggregated",
                    "component_branch": "International transport",
                    "placeholder_branches": (
                        "All demand aggregated/International transport;"
                        "International transport"
                    ),
                    "detailed_branches": (
                        "Transport non road/International transport/Air;"
                        "Transport non road/International transport/Shipping"
                    ),
                    "detail_activation": "all_nonzero",
                    "nonzero_tolerance": 1e-9,
                    "include": "True",
                    "note": "",
                }
            ]
        )

    @staticmethod
    def _row(year: int, flow: str, value: float, scenario: str = "Target") -> dict:
        return {
            "economy": "05_PRC",
            "scenario": scenario,
            "year": year,
            "leap_flow": flow,
            "leap_product": "Fuel oil",
            "value": value,
        }

    def test_zero_structural_air_and_shipping_keep_combined_placeholder(self) -> None:
        rows = pd.DataFrame(
            [
                self._row(2022, "International transport", -10.0),
                self._row(2022, "Transport non road/International transport/Air", 0.0),
                self._row(2022, "Transport non road/International transport/Shipping", 0.0),
            ]
        )

        adjusted, audit = apply_all_demand_detail_fallbacks(rows, self._components())

        assert adjusted.set_index("leap_flow")["value"].to_dict() == {
            "International transport": -10.0,
            "Transport non road/International transport/Air": 0.0,
            "Transport non road/International transport/Shipping": 0.0,
        }
        result = audit.iloc[0]
        assert result["status"] == "partial_detail_placeholder_retained"
        assert result["present_detailed_branches"] == (
            "Transport non road/International transport/Air;"
            "Transport non road/International transport/Shipping"
        )
        assert result["nonzero_detailed_branches"] == ""
        assert result["placeholder_branch"] == "International transport"

    def test_both_negative_detail_branches_replace_combined_placeholder(self) -> None:
        rows = pd.DataFrame(
            [
                self._row(2030, "All demand aggregated/International transport", -10.0),
                self._row(2030, "Transport non road/International transport/Air", -4.0),
                self._row(2030, "Transport non road/International transport/Shipping", -6.0),
            ]
        )
        snapshot = rows.copy(deep=True)

        adjusted, audit = apply_all_demand_detail_fallbacks(rows, self._components())

        pd.testing.assert_frame_equal(rows, snapshot)
        values = adjusted.set_index("leap_flow")["value"].to_dict()
        assert values["All demand aggregated/International transport"] == 0.0
        assert values["Transport non road/International transport/Air"] == -4.0
        assert values["Transport non road/International transport/Shipping"] == -6.0
        result = audit.iloc[0]
        assert result["status"] == "detailed_preferred"
        assert result["nonzero_detailed_branches"] == (
            "Transport non road/International transport/Air;"
            "Transport non road/International transport/Shipping"
        )
        assert result["placeholder_rows_zeroed"] == 1

    def test_one_nonzero_detail_branch_keeps_combined_and_suppresses_partial_detail(self) -> None:
        rows = pd.DataFrame(
            [
                self._row(2030, "International transport", -10.0),
                self._row(2030, "Transport non road/International transport/Air", -4.0),
                self._row(2030, "Transport non road/International transport/Shipping", 0.0),
            ]
        )

        adjusted, audit = apply_all_demand_detail_fallbacks(rows, self._components())

        values = adjusted.set_index("leap_flow")["value"].to_dict()
        assert values["International transport"] == -10.0
        assert values["Transport non road/International transport/Air"] == 0.0
        assert values["Transport non road/International transport/Shipping"] == 0.0
        result = audit.iloc[0]
        assert result["status"] == "partial_detail_placeholder_retained"
        assert result["nonzero_detailed_branches"] == (
            "Transport non road/International transport/Air"
        )
        assert result["detailed_rows_zeroed"] == 2
        assert result["detailed_total_suppressed"] == -4.0

    def test_representation_switches_independently_by_year_without_overlap(self) -> None:
        rows = pd.DataFrame(
            [
                self._row(2022, "International transport", -10.0),
                self._row(2022, "Transport non road/International transport/Air", 0.0),
                self._row(2022, "Transport non road/International transport/Shipping", 0.0),
                self._row(2030, "International transport", -10.0),
                self._row(2030, "Transport non road/International transport/Air", -4.0),
                self._row(2030, "Transport non road/International transport/Shipping", -6.0),
            ]
        )

        adjusted, audit = apply_all_demand_detail_fallbacks(rows, self._components())

        selected = adjusted.assign(
            representation=adjusted["leap_flow"].eq("International transport").map(
                {True: "combined", False: "detail"}
            )
        )
        active_representations = (
            selected.loc[selected["value"].abs().gt(1e-9)]
            .groupby(["year", "representation"])["value"]
            .sum()
            .reset_index()
        )
        assert active_representations.to_dict("records") == [
            {"year": 2022, "representation": "combined", "value": -10.0},
            {"year": 2030, "representation": "detail", "value": -10.0},
        ]
        assert audit.set_index("year")["status"].to_dict() == {
            2022: "partial_detail_placeholder_retained",
            2030: "detailed_preferred",
        }

    def test_alternate_placeholders_are_priority_selected_and_never_additive(self) -> None:
        rows = pd.DataFrame(
            [
                self._row(2030, "All demand aggregated/International transport", -10.0),
                self._row(2030, "International transport", -10.0),
                self._row(2030, "Transport non road/International transport/Air", -4.0),
                self._row(2030, "Transport non road/International transport/Shipping", -6.0),
            ]
        )

        adjusted, audit = apply_all_demand_detail_fallbacks(rows, self._components())

        assert adjusted.loc[
            adjusted["leap_flow"].isin(
                ["All demand aggregated/International transport", "International transport"]
            ),
            "value",
        ].eq(0.0).all()
        result = audit.iloc[0]
        assert result["placeholder_branch"] == "All demand aggregated/International transport"
        assert result["multiple_placeholder_branches_active"]
