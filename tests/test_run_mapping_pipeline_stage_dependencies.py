from codebase.run_mapping_pipeline import expand_requested_stages


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
