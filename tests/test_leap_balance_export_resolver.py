from pathlib import Path

import pytest

from codebase.utilities.leap_balance_export_resolver import (
    format_balance_export_discovery_report,
    resolve_balance_exports_root,
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

    from codebase.utilities.leap_balance_export_resolver import discover_balance_export_workbooks

    discovery = discover_balance_export_workbooks(
        economies=["20_USA", "02_BD"], exports_root=tmp_path
    )
    report = format_balance_export_discovery_report(discovery)
    assert discovery[("20_USA", "REF")] == [workbook]
    assert discovery[("02_BD", "REF")] == []
    assert "20_USA REF: 1 workbook(s)" in report
    assert "02_BD REF: MISSING" in report
