from pathlib import Path

import pytest

from codebase.utilities.leap_balance_export_resolver import (
    discover_available_economies,
    discover_balance_export_workbooks,
    format_balance_export_discovery_report,
    resolve_balance_exports_root,
    scenario_code_from_balance_export_filename,
    select_latest_balance_export_workbooks,
)


def test_default_root_is_sibling_initialisation_repo() -> None:
    root = resolve_balance_exports_root(require_exists=False)
    assert root == Path(__file__).resolve().parents[1].parent / "leap_initialisation" / "data" / "leap balances exports"


def test_environment_override_is_used(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LEAP_BALANCE_EXPORTS_ROOT", str(tmp_path))
    assert resolve_balance_exports_root() == tmp_path


def test_missing_root_has_actionable_diagnostic(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(FileNotFoundError, match="LEAP_BALANCE_EXPORTS_ROOT"):
        resolve_balance_exports_root(missing)


def test_discovery_report_lists_found_and_missing(tmp_path: Path) -> None:
    economy_dir = tmp_path / "20_USA"
    economy_dir.mkdir()
    workbook = economy_dir / "full model output all years 10072026 REF.xlsx"
    workbook.touch()

    discovery = discover_balance_export_workbooks(
        economies=["20_USA", "02_BD"], exports_root=tmp_path
    )
    report = format_balance_export_discovery_report(discovery)
    assert discovery[("20_USA", "REF")] == [workbook]
    assert discovery[("02_BD", "REF")] == []
    assert "20_USA REF: 1 workbook(s)" in report
    assert "02_BD REF: MISSING" in report


def test_prefix_scenario_filename_convention_is_discovered(tmp_path: Path) -> None:
    aus_dir = tmp_path / "01_AUS"
    prc_dir = tmp_path / "05_PRC"
    aus_dir.mkdir()
    prc_dir.mkdir()
    aus_ref = aus_dir / "REF 29072026 AUS.xlsx"
    aus_tgt = aus_dir / "TGT 29072026 AUS.xlsx"
    prc_ref = prc_dir / "REF 3007.xlsx"
    for path in [aus_ref, aus_tgt, prc_ref]:
        path.touch()

    discovery = discover_balance_export_workbooks(
        economies=["01_AUS", "05_PRC"],
        exports_root=tmp_path,
    )

    assert discovery[("01_AUS", "REF")] == [aus_ref]
    assert discovery[("01_AUS", "TGT")] == [aus_tgt]
    assert discovery[("05_PRC", "REF")] == [prc_ref]
    assert discover_available_economies(tmp_path) == ["01_AUS", "05_PRC"]
    assert scenario_code_from_balance_export_filename(aus_ref) == "REF"


def test_economy_prefix_is_discovered_and_newest_duplicate_wins(tmp_path: Path) -> None:
    rus_dir = tmp_path / "16_RUS"
    rus_dir.mkdir()
    old_ref = rus_dir / "RUS REF 0808.xlsx"
    new_ref = rus_dir / "RUS REF 0908.xlsx"
    target = rus_dir / "RUS TGT 0908.xlsx"
    for path in [old_ref, new_ref, target]:
        path.touch()

    discovery = discover_balance_export_workbooks(
        economies=["16_RUS"],
        exports_root=tmp_path,
    )

    assert discovery[("16_RUS", "REF")] == [old_ref, new_ref]
    assert discovery[("16_RUS", "TGT")] == [target]
    assert discover_available_economies(tmp_path) == ["16_RUS"]
    with pytest.warns(UserWarning, match="Multiple REF.*Using newest: RUS REF 0908.xlsx"):
        selected = select_latest_balance_export_workbooks(
            rus_dir,
            economy="16_RUS",
        )
    assert selected == [new_ref, target]


def test_date_economy_scenario_is_discovered_without_generated_reviews(tmp_path: Path) -> None:
    aus_dir = tmp_path / "01_AUS"
    aus_dir.mkdir()
    reference = aus_dir / "1708 AUS REF.xlsx"
    target = aus_dir / "1708 AUS TGT.xlsx"
    generated_review = aus_dir / "balance_review_01_AUS_tgt_2022.xlsx"
    for path in [reference, target, generated_review]:
        path.touch()

    discovery = discover_balance_export_workbooks(
        economies=["01_AUS"],
        exports_root=tmp_path,
    )

    assert discovery[("01_AUS", "REF")] == [reference]
    assert discovery[("01_AUS", "TGT")] == [target]
    assert scenario_code_from_balance_export_filename(target) == "TGT"
    assert select_latest_balance_export_workbooks(
        aus_dir,
        economy="01_AUS",
    ) == [reference, target]


def test_short_ddmm_export_can_be_newer_than_full_ddmmyyyy_name(tmp_path: Path) -> None:
    rus_dir = tmp_path / "16_RUS"
    rus_dir.mkdir()
    old_ref = rus_dir / "full model output all years 13072026 REF.xlsx"
    new_ref = rus_dir / "RUS REF 0908.xlsx"
    old_ref.touch()
    new_ref.touch()

    with pytest.warns(UserWarning, match="Using newest: RUS REF 0908.xlsx"):
        selected = select_latest_balance_export_workbooks(
            rus_dir,
            economy="16_RUS",
            scenarios=("REF",),
        )

    assert selected == [new_ref]
