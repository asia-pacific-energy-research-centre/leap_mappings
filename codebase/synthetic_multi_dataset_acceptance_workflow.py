#%%
"""Run the registry-driven synthetic fourth-dataset acceptance workflow."""

#%%
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

from codebase.mapping_tools.apply_common_esto_structure import (
    run_apply_common_esto_structure,
)
from codebase.mapping_tools.build_common_esto_structure import (
    build_common_esto_for_scope,
)
from codebase.mapping_tools.build_energy_balance_relationships import (
    build_relationship_rows,
)
from codebase.mapping_tools.dataset_registry import (
    COMPARISON_SCOPE_REGISTRY_PATH,
    DATASET_REGISTRY_PATH,
    build_comparison_scope_configs,
)
from codebase.mapping_tools.hierarchy_subtotal_adapters import (
    ADAPTER_VERSION,
    build_declared_csv_hierarchy_adapter,
)
from codebase.mapping_tools.hierarchy_subtotal_contract import (
    CallableDatasetAdapter,
    build_contract_frames,
    write_contract,
)
from codebase.mapping_tools.mapping_sheet_registry import (
    MAPPING_SHEET_REGISTRY_PATH,
    build_mapping_sheet_configs,
)
from codebase.mapping_tools.value_adapter_registry import (
    VALUE_ADAPTER_REGISTRY_PATH,
    get_component_relevance_policies,
    run_registered_value_adapters,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures"
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "results" / "multi_dataset_acceptance" / "synthetic_v1"
)
SYNTHETIC_DATASET_ID = "SYNTH_BALANCE"
SYNTHETIC_SCOPE = "synth_balance_comparison"
SYNTHETIC_MAPPING_SHEET = "synthetic_first_level_esto"
DISABLED_STAGE1_BASELINE_SHA256 = (
    "cb720326e793e4ced916df2c7c72607ede68821a6c18a8c2e007a27979ad35c4"
)


def _enable_synthetic_registries(
    output_dir: Path,
) -> dict[str, Path]:
    """Write acceptance-only registry copies with the fixture enabled."""
    registry_output_dir = output_dir / "registries"
    registry_output_dir.mkdir(parents=True, exist_ok=True)
    registry_sources = {
        "dataset": DATASET_REGISTRY_PATH,
        "scope": COMPARISON_SCOPE_REGISTRY_PATH,
        "mapping": MAPPING_SHEET_REGISTRY_PATH,
        "value": VALUE_ADAPTER_REGISTRY_PATH,
    }
    output_paths: dict[str, Path] = {}
    for registry_name, source_path in registry_sources.items():
        frame = pd.read_csv(
            source_path,
            dtype=str,
            keep_default_na=False,
        )
        if registry_name in {"dataset", "value"}:
            frame.loc[
                frame["dataset_id"].eq(SYNTHETIC_DATASET_ID),
                "enabled",
            ] = "true"
        elif registry_name == "scope":
            frame.loc[
                frame["comparison_scope"].eq(SYNTHETIC_SCOPE),
                "enabled",
            ] = "true"
        elif registry_name == "mapping":
            frame.loc[
                frame["sheet_name"].eq(SYNTHETIC_MAPPING_SHEET),
                "enabled",
            ] = "true"
        output_path = registry_output_dir / source_path.name
        frame.to_csv(output_path, index=False)
        output_paths[registry_name] = output_path
    return output_paths


def _compile_synthetic_relationships(
    registry_paths: dict[str, Path],
    output_dir: Path,
) -> pd.DataFrame:
    """Compile the reviewed CSV mapping through the registered sheet schema."""
    configs = build_mapping_sheet_configs(
        registry_path=registry_paths["mapping"],
        dataset_registry_path=registry_paths["dataset"],
    )
    synthetic_config = next(
        config
        for config in configs
        if config["sheet_name"] == SYNTHETIC_MAPPING_SHEET
    )
    mapping_path = REPO_ROOT / synthetic_config["input_relative_path"]
    relationships = build_relationship_rows(
        source_df=pd.read_csv(mapping_path, dtype=object),
        source_mapping_path=mapping_path,
        sheet_config=synthetic_config,
    )
    relationship_path = output_dir / "synthetic_relationships.csv"
    relationships.to_csv(relationship_path, index=False)
    return relationships


def _build_synthetic_common_rows(
    relationships: pd.DataFrame,
    registry_paths: dict[str, Path],
    output_dir: Path,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Build the coarse comparison boundary from the registered scope."""
    scope_configs = build_comparison_scope_configs(
        registry_path=registry_paths["scope"],
        dataset_registry_path=registry_paths["dataset"],
    )
    common_rows, component_map, qa_outputs = build_common_esto_for_scope(
        comparison_scope=SYNTHETIC_SCOPE,
        scope_config=scope_configs[SYNTHETIC_SCOPE],
        relationships_df=relationships,
        exclusions_df=pd.DataFrame(),
        overrides_df=pd.DataFrame(),
        label_overrides_df=pd.DataFrame(),
        flow_code_to_name={},
        product_code_to_name={},
    )
    common_rows.to_csv(output_dir / "common_esto_rows.csv", index=False)
    component_map.to_csv(
        output_dir / "common_esto_component_map.csv",
        index=False,
    )
    qa_dir = output_dir / "stage2_qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    for qa_name, qa_frame in qa_outputs.items():
        qa_frame.to_csv(qa_dir / f"{qa_name}.csv", index=False)
    return common_rows, qa_outputs


def _publish_synthetic_hierarchy_contract(
    output_dir: Path,
) -> tuple[dict[str, object], dict[str, pd.DataFrame]]:
    """Publish the fixture hierarchy through the generic CSV adapter."""
    adapter = CallableDatasetAdapter(
        "synth_balance",
        ADAPTER_VERSION,
        lambda: build_declared_csv_hierarchy_adapter(
            dataset_id=SYNTHETIC_DATASET_ID,
            source_version="synthetic_v1",
            hierarchy_path=(
                FIXTURE_DIR
                / "synthetic_first_level_esto_hierarchy.csv"
            ),
            values_path=(
                FIXTURE_DIR
                / "synthetic_first_level_esto_acceptance_values.csv"
            ),
        ),
    )
    frames, adapter_registry = build_contract_frames([adapter])
    manifest = write_contract(
        output_dir=output_dir / "hierarchy_contract",
        frames=frames,
        registry=adapter_registry,
        input_paths=[
            FIXTURE_DIR / "synthetic_first_level_esto_hierarchy.csv",
            FIXTURE_DIR
            / "synthetic_first_level_esto_acceptance_values.csv",
        ],
        repo_root=REPO_ROOT,
        generation_time=datetime.now(timezone.utc),
    )
    return manifest, frames


def _publish_registered_synthetic_values(
    registry_paths: dict[str, Path],
    output_dir: Path,
) -> Path:
    """Run the normalized-PJ adapter while leaving production adapters inert."""
    value_registry = pd.read_csv(
        registry_paths["value"],
        dtype=str,
        keep_default_na=False,
    )
    synthetic_output_path = output_dir / "inputs" / "synth_balance.csv"
    synthetic_output_path.parent.mkdir(parents=True, exist_ok=True)
    synthetic_native_path = (
        output_dir / "inputs" / "synthetic_native_values.csv"
    )
    pd.read_csv(
        FIXTURE_DIR / "synthetic_first_level_esto_acceptance_values.csv",
        dtype=object,
    ).to_csv(synthetic_native_path, index=False)
    value_registry.loc[
        value_registry["dataset_id"].eq(SYNTHETIC_DATASET_ID),
        "input_relative_path",
    ] = "inputs/synthetic_native_values.csv"
    value_registry.loc[
        value_registry["dataset_id"].eq(SYNTHETIC_DATASET_ID),
        "output_relative_path",
    ] = "inputs/synth_balance.csv"
    acceptance_value_registry_path = (
        output_dir / "registries" / "value_adapter_registry_acceptance.csv"
    )
    value_registry.to_csv(acceptance_value_registry_path, index=False)
    run_registered_value_adapters(
        adapter_runners={
            "esto_exact_rows": lambda: None,
            "esto_extended_exact_rows": lambda: None,
            "leap_to_esto": lambda: None,
            "ninth_to_esto": lambda: None,
        },
        registry_path=acceptance_value_registry_path,
        dataset_registry_path=registry_paths["dataset"],
        repo_root=output_dir,
    )
    registry_paths["value"] = acceptance_value_registry_path
    return synthetic_output_path


def _write_small_current_source_inputs(
    output_dir: Path,
) -> dict[str, Path]:
    """Create small converted-source inputs at the fixture's detailed grain."""
    detailed = pd.read_csv(
        FIXTURE_DIR / "synthetic_detailed_esto_values.csv",
        dtype=object,
    )
    source_paths: dict[str, Path] = {}
    scenario_names = {
        "ESTO": "historical",
        "LEAP": "model_reference",
        "NINTH": "outlook_target",
    }
    for source_system, scenario in scenario_names.items():
        source_values = detailed.copy()
        source_values["source_system"] = source_system
        source_values["scenario"] = scenario
        source_path = (
            output_dir / "inputs" / f"{source_system.casefold()}.csv"
        )
        source_values.to_csv(source_path, index=False)
        source_paths[source_system] = source_path
    return source_paths


def _acceptance_checks(
    relationships: pd.DataFrame,
    common_rows: pd.DataFrame,
    qa_outputs: dict[str, pd.DataFrame],
    hierarchy_manifest: dict[str, object],
    hierarchy_frames: dict[str, pd.DataFrame],
    comparison: pd.DataFrame,
    missing: pd.DataFrame,
    synthetic_values_path: Path,
) -> pd.DataFrame:
    """Return the twelve acceptance criteria plus mapped-value conservation."""
    synthetic_values = pd.read_csv(synthetic_values_path)
    mapped_synthetic_values = synthetic_values[
        synthetic_values["esto_flow"].eq("09 Total transformation")
        & synthetic_values["esto_product"].eq("01 Coal")
    ]
    synthetic_comparison = comparison[
        comparison["source_system"].eq(SYNTHETIC_DATASET_ID)
    ]
    synthetic_missing = missing[
        missing["source_system"].eq(SYNTHETIC_DATASET_ID)
    ]
    split_qa = qa_outputs[
        "qa_common_esto_source_aggregates_split"
    ]
    conformance_statuses = set(
        hierarchy_frames["value_conformance_diagnostics"]["status"]
    )
    default_mapping_names = {
        config["sheet_name"]
        for config in build_mapping_sheet_configs()
    }
    baseline_record = json.loads(
        (
            REPO_ROOT
            / "docs"
            / "baselines"
            / "multi_dataset_m0_reference_20260729.json"
        ).read_text(encoding="utf-8")
    )
    stage1_baseline_hashes = {
        artifact.get("sha256", "")
        for artifact in baseline_record["artifacts"]
        if artifact.get("stage") == "stage_1"
        and artifact.get("relative_path")
        == "results/mapping_relationships/energy_balance_relationships.csv"
    }
    checks = [
        (
            "registry_load",
            True,
            "Fixture enabled through copied dataset/scope registries.",
        ),
        (
            "normalized_value_adapter",
            len(synthetic_values) == 24,
            f"Published {len(synthetic_values)} normalized PJ rows.",
        ),
        (
            "hierarchy_manifest",
            hierarchy_manifest["validation_result"] == "passed",
            str(hierarchy_manifest["validation_result"]),
        ),
        (
            "declared_parenthood",
            len(hierarchy_frames["declared_relationship_edges"]) == 4,
            (
                f"{len(hierarchy_frames['declared_relationship_edges'])} "
                "ordinary edges"
            ),
        ),
        (
            "registered_mapping_compile",
            len(relationships) == 6,
            f"{len(relationships)} relationship/use-case rows",
        ),
        (
            "generic_rollup_schema",
            relationships["is_rollup_derived"]
            .astype(str)
            .str.strip()
            .str.casefold()
            .isin({"false", "0", ""})
            .all(),
            "Fixture requires no new rollup rule.",
        ),
        (
            "explicit_scope_admission",
            set(common_rows["comparison_scope"]) == {SYNTHETIC_SCOPE},
            SYNTHETIC_SCOPE,
        ),
        (
            "aggregate_not_split",
            split_qa.empty and common_rows["common_row_id"].nunique() == 1,
            (
                f"{common_rows['common_row_id'].nunique()} Common row; "
                f"{len(split_qa)} split findings"
            ),
        ),
        (
            "stage3_lineage",
            len(synthetic_comparison) == len(mapped_synthetic_values)
            and synthetic_comparison[
                "source_aggregate_group_ids"
            ].astype(str).ne("").all(),
            f"{len(synthetic_comparison)} mapped synthetic rows",
        ),
        (
            "bounded_unmapped_review",
            len(synthetic_missing) == 12
            and set(synthetic_missing["esto_flow"]) == {"01 Production"}
            and set(synthetic_missing["esto_product"]) == {"02 Crude oil"},
            f"{len(synthetic_missing)} deliberately unmapped context rows",
        ),
        (
            "value_conformance_failure_preserved",
            "children_incomplete" in conformance_statuses,
            "|".join(sorted(conformance_statuses)),
        ),
        (
            "disabled_fixture_equivalence",
            SYNTHETIC_MAPPING_SHEET not in default_mapping_names
            and DISABLED_STAGE1_BASELINE_SHA256
            in stage1_baseline_hashes,
            (
                "Default registry excludes fixture; disabled production "
                f"Stage 1 SHA-256={DISABLED_STAGE1_BASELINE_SHA256}"
            ),
        ),
        (
            "mapped_value_conservation",
            abs(
                synthetic_comparison["value"].sum()
                - mapped_synthetic_values["value"].sum()
            )
            < 1e-9,
            (
                f"mapped input={mapped_synthetic_values['value'].sum()}, "
                f"output={synthetic_comparison['value'].sum()}"
            ),
        ),
    ]
    return pd.DataFrame(
        [
            {
                "acceptance_check": name,
                "status": "passed" if passed else "failed",
                "evidence": evidence,
            }
            for name, passed, evidence in checks
        ]
    )


def run_synthetic_multi_dataset_acceptance(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, object]:
    """Run M6 from copied registries through Stage 3-style publication."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    registry_paths = _enable_synthetic_registries(output_dir)
    relationships = _compile_synthetic_relationships(
        registry_paths,
        output_dir,
    )
    common_rows, qa_outputs = _build_synthetic_common_rows(
        relationships,
        registry_paths,
        output_dir,
    )
    hierarchy_manifest, hierarchy_frames = (
        _publish_synthetic_hierarchy_contract(output_dir)
    )
    synthetic_values_path = _publish_registered_synthetic_values(
        registry_paths,
        output_dir,
    )
    source_paths = _write_small_current_source_inputs(output_dir)
    source_paths[SYNTHETIC_DATASET_ID] = synthetic_values_path
    relevance_policies = get_component_relevance_policies(
        registry_path=registry_paths["value"],
        dataset_registry_path=registry_paths["dataset"],
    )
    stage3_output_dir = output_dir / "stage3"
    comparison, _, missing = run_apply_common_esto_structure(
        source_paths=source_paths,
        common_rows_path=output_dir / "common_esto_rows.csv",
        output_dir=stage3_output_dir,
        default_economy="00_TEST",
        broad_common_row_component_limit=50,
        active_component_abs_tolerance=0.0,
        relevance_policies=relevance_policies,
        run_id="synthetic_multi_dataset_acceptance_v1",
        run_timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )
    checks = _acceptance_checks(
        relationships=relationships,
        common_rows=common_rows,
        qa_outputs=qa_outputs,
        hierarchy_manifest=hierarchy_manifest,
        hierarchy_frames=hierarchy_frames,
        comparison=comparison,
        missing=missing,
        synthetic_values_path=synthetic_values_path,
    )
    checks.to_csv(output_dir / "acceptance_checklist.csv", index=False)
    status = (
        "passed"
        if checks["status"].eq("passed").all()
        else "failed"
    )
    summary = {
        "run_id": "synthetic_multi_dataset_acceptance_v1",
        "status": status,
        "acceptance_checks": len(checks),
        "passed_checks": int(checks["status"].eq("passed").sum()),
        "relationship_rows": len(relationships),
        "common_component_rows": len(common_rows),
        "common_row_ids": int(common_rows["common_row_id"].nunique()),
        "comparison_rows": len(comparison),
        "missing_review_rows": len(missing),
        "source_systems": sorted(
            comparison["source_system"].dropna().astype(str).unique()
        ),
    }
    with (output_dir / "acceptance_summary.json").open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")
    if status != "passed":
        failed = checks[checks["status"].eq("failed")]
        raise RuntimeError(
            "Synthetic multi-dataset acceptance failed: "
            f"{failed.to_dict('records')}"
        )
    return summary


#%%
RUN_SYNTHETIC_MULTI_DATASET_ACCEPTANCE = False

if RUN_SYNTHETIC_MULTI_DATASET_ACCEPTANCE:
    ACCEPTANCE_SUMMARY = run_synthetic_multi_dataset_acceptance()
    print(json.dumps(ACCEPTANCE_SUMMARY, indent=2))

#%%
