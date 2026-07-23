from pathlib import Path

import pandas as pd
import pytest

import codebase.run_mapping_pipeline as run_mapping_pipeline
from codebase.run_mapping_pipeline import run_leap_parse


def _write_workbook(export_dir: Path, filename: str, economy_title: str, year: int = 2060) -> None:
    export_dir.mkdir(parents=True, exist_ok=True)
    sheet = pd.DataFrame(
        [
            [f'Energy Balance for Area "{economy_title}"', None, None],
            [f"Scenario: Reference, Year: {year}, Units: Petajoule", None, None],
            [None, "Natural gas", "Total"],
            ["Production", 1.0, 1.0],
            ["Total Transformation", 2.0, 2.0],
        ]
    )
    with pd.ExcelWriter(export_dir / filename) as writer:
        sheet.to_excel(writer, sheet_name=str(year), header=False, index=False)


@pytest.fixture
def exports_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "leap balances exports"
    root.mkdir()
    monkeypatch.setattr(run_mapping_pipeline, "LEAP_EXPORTS_ROOT", root)
    raw_leap_path = tmp_path / "raw_leap_results.csv"
    monkeypatch.setattr(run_mapping_pipeline, "RAW_LEAP_PATH", raw_leap_path)
    return root


def test_explicit_economies_list_is_respected(exports_root: Path) -> None:
    _write_workbook(exports_root / "20_USA", "full model output all years 10072026 REF.xlsx", "USA")
    _write_workbook(exports_root / "12_NZ", "full model output all years 10072026 REF.xlsx", "NZ")

    run_leap_parse(economies=["12_NZ"])

    combined = pd.read_csv(run_mapping_pipeline.RAW_LEAP_PATH)
    assert set(combined["economy"]) == {"12_NZ"}


def test_auto_discovery_finds_available_economies_without_hardcoding(exports_root: Path) -> None:
    _write_workbook(exports_root / "20_USA", "full model output all years 10072026 REF.xlsx", "USA")
    _write_workbook(exports_root / "02_BD", "full model output all years 10072026 REF.xlsx", "BD")
    # A directory present with no recognized workbook must not be swept into
    # the auto-discovered default (mirrors real fixture-only economy dirs).
    (exports_root / "99_EMPTY").mkdir()

    run_leap_parse()

    combined = pd.read_csv(run_mapping_pipeline.RAW_LEAP_PATH)
    assert set(combined["economy"]) == {"20_USA", "02_BD"}


def test_missing_requested_economy_warns_and_continues(
    exports_root: Path, capsys: pytest.CaptureFixture
) -> None:
    _write_workbook(exports_root / "20_USA", "full model output all years 10072026 REF.xlsx", "USA")

    run_leap_parse(economies=["20_USA", "02_BD"])

    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "02_BD" in captured.out

    combined = pd.read_csv(run_mapping_pipeline.RAW_LEAP_PATH)
    assert set(combined["economy"]) == {"20_USA"}


def test_combined_output_contains_all_parsed_economies(exports_root: Path) -> None:
    _write_workbook(exports_root / "20_USA", "full model output all years 10072026 REF.xlsx", "USA")
    _write_workbook(exports_root / "12_NZ", "full model output all years 10072026 REF.xlsx", "NZ")

    run_leap_parse(economies=["20_USA", "12_NZ"])

    combined = pd.read_csv(run_mapping_pipeline.RAW_LEAP_PATH)
    assert set(combined["economy"]) == {"20_USA", "12_NZ"}
    assert len(combined) == 4  # 2 rows per economy


def test_no_economies_available_warns_without_writing_output(
    exports_root: Path, capsys: pytest.CaptureFixture
) -> None:
    run_leap_parse()

    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert not run_mapping_pipeline.RAW_LEAP_PATH.exists()
