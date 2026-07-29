import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

from codebase.mapping_tools.apply_common_esto_structure import (
    apply_common_structure,
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
from codebase.mapping_tools.hierarchy_subtotal_contract import (
    CallableDatasetAdapter,
    build_contract_frames,
    load_contract,
    write_contract,
)
from codebase.mapping_tools.hierarchy_subtotal_adapters import (
    ADAPTER_VERSION,
    build_declared_csv_hierarchy_adapter,
    current_adapter_registry,
)
from codebase.mapping_tools.mapping_sheet_registry import (
    MAPPING_SHEET_REGISTRY_PATH,
    build_mapping_sheet_configs,
)
from codebase.mapping_tools.value_adapter_registry import (
    VALUE_ADAPTER_REGISTRY_PATH,
    run_registered_value_adapters,
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

    source_values = pd.concat([
        pd.read_csv(FIXTURE_DIR / "synthetic_first_level_esto_values.csv"),
        pd.read_csv(FIXTURE_DIR / "synthetic_detailed_esto_values.csv"),
    ], ignore_index=True)
    comparison, missing, _ = apply_common_structure(
        source_df=source_values,
        common_rows_df=common_rows,
    )

    totals = comparison.groupby("source_system")["value"].sum().to_dict()
    assert missing.empty
    assert totals == {"ESTO": 100.0, "SYNTH_BALANCE": 100.0}


def test_synthetic_acceptance_values_publish_mapped_rows_and_bound_missing() -> None:
    relationships = pd.read_csv(
        FIXTURE_DIR / "synthetic_first_level_esto_mappings.csv"
    )
    common_rows, _, _ = build_common_esto_for_scope(
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
    source_values = pd.read_csv(
        FIXTURE_DIR / "synthetic_first_level_esto_acceptance_values.csv"
    )
    comparison, missing, _ = apply_common_structure(
        source_df=source_values,
        common_rows_df=common_rows,
    )

    assert len(comparison) == 12
    assert len(missing) == 12
    assert set(missing["esto_flow"]) == {"01 Production"}
    assert set(missing["esto_product"]) == {"02 Crude oil"}
    mapped_expected = source_values[
        source_values["esto_flow"].eq("09 Total transformation")
    ]["value"].sum()
    assert comparison["value"].sum() == mapped_expected
    assert comparison["common_row_id"].nunique() == 1
    assert comparison["source_system"].eq("SYNTH_BALANCE").all()
    assert comparison["source_aggregate_group_ids"].astype(str).ne("").all()


def test_synthetic_hierarchy_adapter_publishes_strict_contract(
    tmp_path: Path,
) -> None:
    adapter = CallableDatasetAdapter(
        "synth_balance",
        ADAPTER_VERSION,
        lambda: build_declared_csv_hierarchy_adapter(
            dataset_id="SYNTH_BALANCE",
            source_version="synthetic_v1",
            hierarchy_path=(
                FIXTURE_DIR / "synthetic_first_level_esto_hierarchy.csv"
            ),
            values_path=(
                FIXTURE_DIR / "synthetic_first_level_esto_acceptance_values.csv"
            ),
        ),
    )
    frames, registry = build_contract_frames([adapter])
    manifest = write_contract(
        output_dir=tmp_path / "contract",
        frames=frames,
        registry=registry,
        input_paths=[
            FIXTURE_DIR / "synthetic_first_level_esto_values.csv",
            FIXTURE_DIR / "synthetic_first_level_esto_mappings.csv",
        ],
        repo_root=Path(__file__).parents[1],
        generation_time=datetime(2026, 7, 29, tzinfo=timezone.utc),
    )
    loaded_manifest, loaded_frames = load_contract(
        tmp_path / "contract",
        expected_build_id=manifest["build_id"],
    )

    assert loaded_manifest["validation_result"] == "passed"
    assert loaded_manifest["adapters"][0]["dataset_id"] == "synth_balance"
    pair = loaded_frames["canonical_source_pairs"].loc[
        loaded_frames["canonical_source_pairs"]["axis_1_node_id"].eq(
            "09 Total transformation"
        )
    ].iloc[0]
    assert bool(pair["pair_is_subtotal"])
    assert set(
        loaded_frames["value_conformance_diagnostics"]["status"]
    ) == {"children_incomplete"}


def test_synthetic_dataset_can_be_enabled_without_core_code_changes(
    tmp_path: Path,
) -> None:
    datasets = pd.read_csv(
        DATASET_REGISTRY_PATH,
        dtype=str,
        keep_default_na=False,
    )
    scopes = pd.read_csv(
        COMPARISON_SCOPE_REGISTRY_PATH,
        dtype=str,
        keep_default_na=False,
    )
    mappings = pd.read_csv(
        MAPPING_SHEET_REGISTRY_PATH,
        dtype=str,
        keep_default_na=False,
    )
    adapters = pd.read_csv(
        VALUE_ADAPTER_REGISTRY_PATH,
        dtype=str,
        keep_default_na=False,
    )

    assert "synth_balance_comparison" not in build_comparison_scope_configs()
    assert "synthetic_first_level_esto" not in {
        config["sheet_name"] for config in build_mapping_sheet_configs()
    }

    datasets.loc[datasets["dataset_id"].eq("SYNTH_BALANCE"), "enabled"] = "true"
    datasets.loc[
        datasets["dataset_id"].eq("SYNTH_BALANCE"),
        "hierarchy_input_relative_path",
    ] = "input/synthetic_hierarchy.csv"
    scopes.loc[
        scopes["comparison_scope"].eq("synth_balance_comparison"),
        "enabled",
    ] = "true"
    mappings.loc[
        mappings["sheet_name"].eq("synthetic_first_level_esto"),
        "enabled",
    ] = "true"
    adapters.loc[
        adapters["dataset_id"].eq("SYNTH_BALANCE"),
        "enabled",
    ] = "true"
    adapters.loc[
        adapters["dataset_id"].eq("SYNTH_BALANCE"),
        "input_relative_path",
    ] = "input/synthetic_values.csv"
    adapters.loc[
        adapters["dataset_id"].eq("SYNTH_BALANCE"),
        "output_relative_path",
    ] = "output/synthetic_values.csv"

    dataset_path = tmp_path / "dataset_registry.csv"
    scope_path = tmp_path / "comparison_scopes.csv"
    mapping_path = tmp_path / "mapping_sheet_registry.csv"
    adapter_path = tmp_path / "value_adapter_registry.csv"
    datasets.to_csv(dataset_path, index=False)
    scopes.to_csv(scope_path, index=False)
    mappings.to_csv(mapping_path, index=False)
    adapters.to_csv(adapter_path, index=False)

    input_path = tmp_path / "input" / "synthetic_values.csv"
    input_path.parent.mkdir(parents=True)
    pd.read_csv(
        FIXTURE_DIR / "synthetic_first_level_esto_acceptance_values.csv"
    ).to_csv(input_path, index=False)
    pd.read_csv(
        FIXTURE_DIR / "synthetic_first_level_esto_hierarchy.csv"
    ).to_csv(tmp_path / "input" / "synthetic_hierarchy.csv", index=False)

    scope_configs = build_comparison_scope_configs(
        registry_path=scope_path,
        dataset_registry_path=dataset_path,
    )
    mapping_configs = build_mapping_sheet_configs(
        registry_path=mapping_path,
        dataset_registry_path=dataset_path,
    )
    assert scope_configs["synth_balance_comparison"]["systems"] == [
        "SYNTH_BALANCE",
        "ESTO",
        "LEAP",
        "NINTH",
    ]
    synthetic_mapping_config = next(
        config
        for config in mapping_configs
        if config["sheet_name"] == "synthetic_first_level_esto"
    )
    compiled = build_relationship_rows(
        source_df=pd.read_csv(
            FIXTURE_DIR / "synthetic_first_level_esto_mapping_table.csv"
        ),
        source_mapping_path=(
            FIXTURE_DIR / "synthetic_first_level_esto_mapping_table.csv"
        ),
        sheet_config=synthetic_mapping_config,
    )
    assert len(compiled) == 6
    assert set(compiled["source_system"]) == {"SYNTH_BALANCE"}

    hierarchy_adapters = current_adapter_registry(
        repo_root=tmp_path,
        workbook_path=(
            DATASET_REGISTRY_PATH.parents[2]
            / "config"
            / "outlook_mappings_master.xlsx"
        ),
        dataset_registry_path=dataset_path,
        value_adapter_registry_path=adapter_path,
    )
    assert hierarchy_adapters[-1].dataset_id == "synth_balance"
    assert len(hierarchy_adapters[-1].build().pairs) == 2

    native_calls: list[str] = []
    executed = run_registered_value_adapters(
        adapter_runners={
            "esto_exact_rows": lambda: native_calls.append("ESTO"),
            "esto_extended_exact_rows": lambda: native_calls.append(
                "ESTO_EXTENDED"
            ),
            "leap_to_esto": lambda: native_calls.append("LEAP"),
            "ninth_to_esto": lambda: native_calls.append("NINTH"),
        },
        registry_path=adapter_path,
        dataset_registry_path=dataset_path,
        repo_root=tmp_path,
    )
    published = pd.read_csv(tmp_path / "output" / "synthetic_values.csv")
    assert executed[-1] == "SYNTH_BALANCE"
    assert native_calls == ["ESTO", "ESTO_EXTENDED", "LEAP", "NINTH"]
    assert published.to_dict("records") == (
        pd.read_csv(
            FIXTURE_DIR / "synthetic_first_level_esto_acceptance_values.csv"
        )
        .to_dict("records")
    )
