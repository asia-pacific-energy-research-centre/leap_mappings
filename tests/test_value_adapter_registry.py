from pathlib import Path

from codebase.mapping_tools.value_adapter_registry import (
    get_registered_stage3_source_paths,
    load_value_adapter_registry,
    run_registered_value_adapters,
)


def test_bundled_value_adapters_preserve_order_and_paths(tmp_path: Path) -> None:
    registry = load_value_adapter_registry()
    paths = get_registered_stage3_source_paths(tmp_path)

    assert registry["dataset_id"].tolist() == [
        "ESTO",
        "ESTO_EXTENDED",
        "LEAP",
        "NINTH",
        "SYNTH_BALANCE",
    ]
    assert list(paths) == ["ESTO", "ESTO_EXTENDED", "LEAP", "NINTH"]
    assert paths["LEAP"] == (
        tmp_path
        / "results"
        / "mapping_relationships"
        / "leap_results_converted_to_esto.csv"
    )

    assert registry.set_index("dataset_id").loc[
        "ESTO", "relevance_reference_glob"
    ] == "data/00APEC_*_low_with_subtotals.csv"


def test_registered_value_adapters_run_once_in_order() -> None:
    calls: list[str] = []
    executed = run_registered_value_adapters({
        "esto_exact_rows": lambda: calls.append("ESTO"),
        "esto_extended_exact_rows": lambda: calls.append("ESTO_EXTENDED"),
        "leap_to_esto": lambda: calls.append("LEAP"),
        "ninth_to_esto": lambda: calls.append("NINTH"),
    })

    assert calls == ["ESTO", "ESTO_EXTENDED", "LEAP", "NINTH"]
    assert executed == calls


def test_pipeline_import_uses_registered_stage3_sources() -> None:
    from codebase import run_mapping_pipeline

    paths = get_registered_stage3_source_paths(run_mapping_pipeline.REPO_ROOT)
    assert list(paths) == ["ESTO", "ESTO_EXTENDED", "LEAP", "NINTH"]
    assert run_mapping_pipeline.LEAP_EXPORTS_ROOT.name == "leap balances exports"
