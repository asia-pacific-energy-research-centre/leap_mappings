"""Write a compact Power all-producers certification from current artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.mapping_tools.power_all_producers_certification import (  # noqa: E402
    audit_alias_cooccurrence,
    audit_ordinary_esto_component_coverage,
    audit_source_once_delivery,
    audit_structural_component_definitions,
    registered_power_rollups,
)


def _resolve(path: str | Path) -> Path:
    return Path(str(path).replace("\\", "/")) if Path(path).is_absolute() else REPO_ROOT / path


def run_certification(output_dir: Path | None = None) -> dict[str, object]:
    output_dir = output_dir or _resolve("outputs/power_all_producers_certification_20260903")
    output_dir.mkdir(parents=True, exist_ok=True)
    axis = _resolve("config/outlook_mappings_single_axis.xlsx")
    relationships = pd.read_csv(_resolve("results/mapping_relationships/energy_balance_relationships.csv"), dtype=str).fillna("")
    rollups = registered_power_rollups(pd.read_excel(axis, sheet_name="esto_rollup_rules", dtype=str))
    targets = set(rollups["rolled_esto_flow"])
    source_lineage = pd.concat([
        pd.read_csv(_resolve("results/mapping_relationships/leap_source_to_esto_component_lineage.csv.gz")),
        pd.read_csv(_resolve("results/mapping_relationships/ninth_source_to_esto_component_lineage.csv.gz")),
    ], ignore_index=True)
    source_detail, source_summary = audit_source_once_delivery(source_lineage, targets)
    raw_leap = pd.read_csv(_resolve("results/mapping_relationships/raw_leap_results.csv"))
    aliases = audit_alias_cooccurrence(raw_leap)
    ordinary_component_coverage = audit_ordinary_esto_component_coverage(
        pd.read_csv(_resolve("results/mapping_relationships/esto_results_exact_rows.csv.gz")),
        rollups,
    )
    structural_components = audit_structural_component_definitions(
        pd.read_csv(_resolve("results/common_esto/common_esto_rows.csv")),
        rollups,
    )
    registered_rollups_ok = (
        len(rollups) == 27
        and rollups["component_count"].eq(2).all()
        and structural_components["component_set_status"].eq("passed").all()
    )
    included = relationships.loc[
        relationships["include_in_use_case"].str.lower().eq("true") & relationships["remove_row"].str.lower().ne("true")
    ]
    esto_targets = included.loc[included["target_system"].eq("ESTO")]
    import_ok = (
        set(esto_targets.loc[esto_targets["source_flow"].eq("Imports"), "target_flow"]) == {"02 Imports"}
        and set(esto_targets.loc[esto_targets["source_flow"].eq("02_imports"), "target_flow"]) == {"02 Imports"}
    )
    coal_h2_ok = set(included.loc[included["source_flow"].eq("Electricity Generation/Coal_H2_blended"), "target_flow"]) == {
        "09.01.01.03,09.02.01.03 Coal hydrogen blended"
    }
    power_rules = pd.read_excel(axis, sheet_name="esto_rollup_rules", dtype=str).fillna("")
    component_targets = set(power_rules.loc[
        power_rules["rollup_context"].eq("power_process_comparison"), "input_esto_flow"
    ])
    producer_components_consumed = included.loc[
        included["source_system"].isin(["LEAP", "NINTH"]) & included["target_flow"].isin(component_targets)
    ]
    other_solid = power_rules.loc[
        power_rules["rollup_context"].eq("power_other_biomass_comparison")
        & power_rules["ROLLUP_MODE"].eq("NON_EXPANDING")
    ]
    other_solid_ok = (
        other_solid.groupby("rolled_esto_flow")["input_esto_flow"].nunique().ge(2).all()
        and not set(other_solid["rolled_esto_flow"]) & set(other_solid["input_esto_flow"])
    )
    frontier = pd.read_csv(_resolve("results/common_esto/qa_common_esto_non_expanding_frontier_check.csv"))
    other_solid_frontier = frontier.loc[
        frontier["non_expanding_rollup_id"].str.contains("other_and_solid_biomass", na=False)
    ]
    other_solid_output_ok = not other_solid_frontier.empty and other_solid_frontier["check_status"].eq("ok").all()
    static_rows = pd.DataFrame([
        {"check": "registered_power_rollups", "status": "passed" if registered_rollups_ok else "failed", "observations": len(rollups)},
        {"check": "imports_only_to_02_imports", "status": "passed" if import_ok else "failed", "observations": int(import_ok)},
        {"check": "coal_h2_within_coal_power", "status": "passed" if coal_h2_ok else "failed", "observations": int(coal_h2_ok)},
        {"check": "no_producer_component_targets_consumed_by_leap_or_ninth", "status": "passed" if producer_components_consumed.empty else "failed", "observations": len(producer_components_consumed)},
        {"check": "other_and_solid_biomass_non_overlapping_boundary", "status": "passed" if other_solid_ok else "failed", "observations": len(other_solid)},
        {"check": "other_and_solid_biomass_common_output_frontier", "status": "passed" if other_solid_output_ok else "failed", "observations": len(other_solid_frontier)},
    ])
    exceptions = pd.concat([
        source_detail.loc[source_detail["status"].eq("failed")],
        structural_components.loc[structural_components["status"].eq("failed")],
        static_rows.loc[static_rows["status"].eq("failed")],
    ], ignore_index=True, sort=False)
    summary = pd.DataFrame([
        {"check": "source_once_delivery", "status": "passed" if source_summary["failures"].sum() == 0 else "failed", "observations": int(source_summary["observations"].sum()), "exceptions": int(source_summary["failures"].sum())},
        {"check": "extended_structural_component_definition", "status": "passed" if structural_components["status"].eq("passed").all() else "failed", "observations": len(structural_components), "exceptions": int(structural_components["status"].eq("failed").sum())},
        {"check": "ordinary_esto_component_coverage", "status": "info", "observations": int(ordinary_component_coverage["status"].eq("full_ordinary_esto_component_coverage").sum()), "exceptions": 0},
        *static_rows.assign(exceptions=0).to_dict("records"),
        {"check": "alias_double_count_risk", "status": "passed" if not aliases["status"].eq("double_count_risk").any() else "review", "observations": len(aliases), "exceptions": int(aliases["status"].eq("double_count_risk").sum())},
    ])
    summary.to_csv(output_dir / "power_all_producers_certification_summary.csv", index=False)
    aliases.to_csv(output_dir / "alias_nonzero_cooccurrence.csv", index=False)
    diagnostics_dir = output_dir / "diagnostics"
    diagnostics_dir.mkdir(exist_ok=True)
    exceptions.to_csv(diagnostics_dir / "power_all_producers_exceptions.csv", index=False)
    manifest = {"status": "passed" if not summary["status"].eq("failed").any() else "failed", "rollup_groups": len(rollups), "summary": summary.to_dict("records")}
    (output_dir / "power_all_producers_certification_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(run_certification(), indent=2))
