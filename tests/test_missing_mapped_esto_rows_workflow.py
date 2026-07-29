from pathlib import Path

import pandas as pd
import pytest

import codebase.missing_mapped_esto_rows_workflow as workflow


def test_review_workflow_resolves_inputs_and_forwards_to_builder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    esto_2024 = tmp_path / "esto_2024.csv"
    esto_2025 = tmp_path / "esto_2025.csv"
    mapping_workbook = tmp_path / "mappings.xlsx"
    ninth_source = tmp_path / "ninth.csv"
    output_dir = tmp_path / "review"
    for path in [esto_2024, esto_2025, mapping_workbook, ninth_source]:
        path.write_text("test", encoding="utf-8")

    expected = pd.DataFrame([{"status": "complete"}])
    received: dict[str, object] = {}

    def fake_write_missing_mapped_esto_rows(
        esto_csv_paths: list[Path],
        mapping_workbook_path: Path,
        ninth_csv_path: Path,
        output_dir: Path,
    ) -> pd.DataFrame:
        received.update({
            "esto_csv_paths": esto_csv_paths,
            "mapping_workbook_path": mapping_workbook_path,
            "ninth_csv_path": ninth_csv_path,
            "output_dir": output_dir,
        })
        return expected

    monkeypatch.setattr(
        workflow,
        "write_missing_mapped_esto_rows",
        fake_write_missing_mapped_esto_rows,
    )

    actual = workflow.run_missing_mapped_esto_rows_review(
        esto_source_paths=(esto_2024, esto_2025),
        mapping_workbook_path=mapping_workbook,
        ninth_source_path=ninth_source,
        output_dir=output_dir,
    )

    assert actual is expected
    assert received == {
        "esto_csv_paths": [esto_2024, esto_2025],
        "mapping_workbook_path": mapping_workbook,
        "ninth_csv_path": ninth_source,
        "output_dir": output_dir,
    }


def test_review_workflow_fails_before_writing_when_an_input_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fail_if_called(**_kwargs: object) -> pd.DataFrame:
        nonlocal called
        called = True
        return pd.DataFrame()

    monkeypatch.setattr(
        workflow,
        "write_missing_mapped_esto_rows",
        fail_if_called,
    )

    with pytest.raises(FileNotFoundError, match="Missing input"):
        workflow.run_missing_mapped_esto_rows_review(
            esto_source_paths=(tmp_path / "missing_esto.csv",),
            mapping_workbook_path=tmp_path / "missing_mappings.xlsx",
            ninth_source_path=tmp_path / "missing_ninth.csv",
            output_dir=tmp_path / "review",
        )

    assert called is False
