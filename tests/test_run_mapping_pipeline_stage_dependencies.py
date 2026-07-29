import pandas as pd

from codebase.run_mapping_pipeline import (
    _ALL_STAGES,
    _stage3_completion_status,
    expand_requested_stages,
)


def test_default_pipeline_excludes_retired_stage_zero() -> None:
    assert _ALL_STAGES == ["1", "2", "leap_parse", "data_convert", "3"]


def test_abbreviated_full_run_includes_conversion_dependencies() -> None:
    assert expand_requested_stages(["1", "2", "3"], set()) == [
        "1", "2", "leap_parse", "data_convert", "3"
    ]


def test_explicit_conversion_stage_is_not_duplicated() -> None:
    requested = ["1", "2", "leap_parse", "data_convert", "3"]
    assert expand_requested_stages(requested, set()) == requested


def test_explicit_skip_is_honoured() -> None:
    assert expand_requested_stages(["1", "2", "3"], {"data_convert"}) == [
        "1", "2", "leap_parse", "3"
    ]


def test_stage3_manifest_reports_validation_errors() -> None:
    summary = pd.DataFrame([
        {"validation_axis": "product", "status": "passed"},
        {"validation_axis": "flow", "status": "error"},
    ])

    assert _stage3_completion_status(summary) == "completed_with_validation_errors"


def test_stage3_manifest_keeps_completed_for_non_error_validation_results() -> None:
    summary = pd.DataFrame([
        {"validation_axis": "product", "status": "passed"},
        {"validation_axis": "flow", "status": "failed"},
    ])

    assert _stage3_completion_status(summary) == "completed"
