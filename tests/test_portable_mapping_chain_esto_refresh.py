"""Tests for re-extracting ESTO exact rows when a base table is supplied."""

import gzip
from pathlib import Path

import pandas as pd
import pytest

from codebase.portable_mapping_chain import (
    _apply_synthetic_rows,
    _fingerprint,
    prepare_esto_exact_rows,
)


MAPPINGS_ROOT = Path(__file__).resolve().parents[1]
RULES = MAPPINGS_ROOT / "config" / "synthetic_reference_rows.csv"
ESTO_2024 = MAPPINGS_ROOT / "data" / "00APEC_2024_low_with_subtotals.csv"


def _stub(path: Path, text: str = "stub\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_no_base_table_means_the_bundled_rows_are_used_untouched(tmp_path: Path) -> None:
    """The common case: the user supplied nothing, so nothing is regenerated.

    Re-extraction takes minutes, so it must not happen on an ordinary run.
    """
    bundled = _stub(tmp_path / "bundled.csv.gz")
    notes: list[str] = []
    result = prepare_esto_exact_rows(
        bundled_exact_rows=bundled,
        esto_base_table=None,
        synthetic_rules_path=RULES,
        relationships_path=_stub(tmp_path / "rel.csv"),
        mapping_workbook_path=_stub(tmp_path / "wb.xlsx"),
        work_dir=tmp_path / "work",
        notes=notes,
    )
    assert result == bundled
    assert notes == []


def test_a_missing_base_table_falls_back_rather_than_failing(tmp_path: Path) -> None:
    bundled = _stub(tmp_path / "bundled.csv.gz")
    result = prepare_esto_exact_rows(
        bundled_exact_rows=bundled,
        esto_base_table=tmp_path / "absent.csv",
        synthetic_rules_path=RULES,
        relationships_path=_stub(tmp_path / "rel.csv"),
        mapping_workbook_path=_stub(tmp_path / "wb.xlsx"),
        work_dir=tmp_path / "work",
        notes=[],
    )
    assert result == bundled


def test_the_fingerprint_changes_when_any_input_changes(tmp_path: Path) -> None:
    a = _stub(tmp_path / "a.csv", "one\n")
    b = _stub(tmp_path / "b.csv", "two\n")
    before = _fingerprint([a, b])
    assert before == _fingerprint([a, b])

    _stub(tmp_path / "b.csv", "two but longer\n")
    assert _fingerprint([a, b]) != before, "a changed input must invalidate the cache"

    # An absent file is a distinct state, not an error.
    assert _fingerprint([a, None]) != _fingerprint([a, b])


@pytest.mark.skipif(not ESTO_2024.is_file(), reason="ESTO base table not present")
def test_synthetic_rows_are_added_and_tagging_is_stripped(tmp_path: Path) -> None:
    """Rows are injected, and the provenance columns do not reach the extractor.

    The extraction expects the published ESTO column set. The tagging exists for
    provenance and is deliberately dropped on the way through - the record of
    what was added is the returned count and the note, not extra columns in a
    file the extractor will parse.
    """
    prepared, added = _apply_synthetic_rows(ESTO_2024, RULES, tmp_path)
    assert added > 0
    header = pd.read_csv(prepared, nrows=0).columns.tolist()
    assert not [c for c in header if c.startswith("_synthetic")]
    for required in ("economy", "flows", "products"):
        assert required in header


@pytest.mark.slow
@pytest.mark.skipif(not ESTO_2024.is_file(), reason="ESTO base table not present")
def test_a_supplied_table_is_re_extracted_then_cached(tmp_path: Path) -> None:
    """The whole point: a supplied table produces its own exact rows.

    Marked slow because the extraction genuinely takes about two minutes; it is
    the only test that proves the vintage actually flows through.
    """
    rel = MAPPINGS_ROOT / "results" / "mapping_relationships" / "energy_balance_relationships.csv"
    workbook = MAPPINGS_ROOT / "config" / "outlook_mappings_master.xlsx"
    if not rel.is_file() or not workbook.is_file():
        pytest.skip("pipeline artifacts not present in this checkout")

    work = tmp_path / "work"
    notes: list[str] = []
    first = prepare_esto_exact_rows(
        bundled_exact_rows=_stub(tmp_path / "bundled.csv.gz"),
        esto_base_table=ESTO_2024,
        synthetic_rules_path=RULES,
        relationships_path=rel,
        mapping_workbook_path=workbook,
        work_dir=work,
        notes=notes,
    )
    assert first.is_file() and first.stat().st_size > 1_000_000
    assert any("Applied synthetic reference rows" in n for n in notes)
    assert any("Re-extracted ESTO exact rows" in n for n in notes)

    with gzip.open(first, "rt", encoding="utf-8") as handle:
        assert "esto_flow" in handle.readline()

    notes.clear()
    second = prepare_esto_exact_rows(
        bundled_exact_rows=_stub(tmp_path / "bundled.csv.gz"),
        esto_base_table=ESTO_2024,
        synthetic_rules_path=RULES,
        relationships_path=rel,
        mapping_workbook_path=workbook,
        work_dir=work,
        notes=notes,
    )
    assert second == first
    assert any("Reused cached" in n for n in notes)
