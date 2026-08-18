"""Tests for discovering raw ESTO vintages, preliminary ones included."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from codebase.build_esto_extended_vintages import (
    available_esto_vintages,
    extended_path_for_vintage,
)


def _write_esto_csv(path: Path) -> Path:
    pd.DataFrame(
        [{"economy": "01AUS", "flows": "17 Electricity", "products": "17 Electricity", "is_subtotal": "FALSE", "2024": 1}]
    ).to_csv(path, index=False)
    return path


def test_a_preliminary_vintage_is_discovered_and_flagged(tmp_path: Path) -> None:
    _write_esto_csv(tmp_path / "00APEC_2024_low_with_subtotals.csv")
    _write_esto_csv(tmp_path / "00APEC_2026_low_with_subtotals_PRELIMINARY.csv")

    vintages = available_esto_vintages(tmp_path)

    assert vintages == [
        (2024, tmp_path / "00APEC_2024_low_with_subtotals.csv", False),
        (2026, tmp_path / "00APEC_2026_low_with_subtotals_PRELIMINARY.csv", True),
    ]


def test_unrelated_files_are_ignored(tmp_path: Path) -> None:
    _write_esto_csv(tmp_path / "00APEC_2024_low_with_subtotals.csv")
    (tmp_path / "00APEC_2024_low_with_subtotals_backup.csv").write_text("economy\n", encoding="utf-8")
    (tmp_path / "esto_extended_2024_low_with_subtotals.csv").write_text("economy\n", encoding="utf-8")

    vintages = available_esto_vintages(tmp_path)

    assert vintages == [(2024, tmp_path / "00APEC_2024_low_with_subtotals.csv", False)]


def test_extended_path_keeps_the_preliminary_tag(tmp_path: Path) -> None:
    assert extended_path_for_vintage(2026, tmp_path, is_preliminary=True) == (
        tmp_path / "esto_extended_2026_low_with_subtotals_PRELIMINARY.csv"
    )
    assert extended_path_for_vintage(2025, tmp_path, is_preliminary=False) == (
        tmp_path / "esto_extended_2025_low_with_subtotals.csv"
    )
