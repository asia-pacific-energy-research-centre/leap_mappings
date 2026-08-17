"""Tests for the early LEAP source-branch preflight (interim fallback + All-demand warning)."""

import json

import pandas as pd

from codebase.mapping_tools.source_branch_preflight import (
    apply_all_demand_detail_fallbacks,
    apply_source_branch_fallbacks,
    check_all_demand_aggregated_overlap,
    get_demand_sectors_without_detail,
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
