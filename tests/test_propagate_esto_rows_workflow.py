"""Tests for guarded propagation of reviewed ESTO rows."""

from pathlib import Path

import pandas as pd

from codebase.propagate_esto_rows_workflow import (
    propagate_chosen_esto_rows,
    propagate_chosen_esto_rows_by_vintage,
)


def _write_target(path: Path, include_2023: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "economy": "01AAA",
        "flows": "01 Production",
        "products": "01 Coal",
        "is_subtotal": "FALSE",
        "2022": 1.0,
    }
    if include_2023:
        row["2023"] = 2.0
    pd.DataFrame([row]).to_csv(path, index=False)


def test_propagation_is_dry_run_by_default_and_preserves_each_target_schema(tmp_path: Path) -> None:
    chosen_path = tmp_path / "chosen.csv"
    pd.DataFrame([
        {
            "economy": "01AAA",
            "flows": "16.01.99 Commercial and public services unallocated",
            "products": "17 Electricity",
            "is_subtotal": "FALSE",
            "2022": 8.0,
        }
    ]).to_csv(chosen_path, index=False)
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    target_a = repo_a / "data/00APEC_2024_low_with_subtotals.csv"
    target_b = repo_b / "data/00APEC_2025_low_with_subtotals.csv"
    _write_target(target_a, include_2023=False)
    _write_target(target_b, include_2023=True)

    preview = propagate_chosen_esto_rows(chosen_path, [repo_a, repo_b])

    assert set(preview["status"]) == {"dry_run"}
    assert preview["append_row_count"].eq(1).all()
    assert len(pd.read_csv(target_a)) == 1
    assert len(pd.read_csv(target_b)) == 1

    written = propagate_chosen_esto_rows(
        chosen_rows_path=chosen_path,
        repository_roots=[repo_a, repo_b],
        write_to_source_files=True,
    )

    assert set(written["status"]) == {"rows_appended"}
    result_a = pd.read_csv(target_a)
    result_b = pd.read_csv(target_b)
    assert list(result_a.columns) == ["economy", "flows", "products", "is_subtotal", "2022"]
    assert list(result_b.columns) == ["economy", "flows", "products", "is_subtotal", "2022", "2023"]
    assert float(result_b.iloc[-1]["2023"]) == 0.0


def test_repeated_propagation_skips_existing_keys_without_replacement(tmp_path: Path) -> None:
    chosen_path = tmp_path / "chosen.xlsx"
    chosen = pd.DataFrame([
        {
            "economy": "01_AAA",
            "flows": "16.01.99 Commercial and public services unallocated",
            "products": "17 Electricity",
            "is_subtotal": "FALSE",
            "2022": 8.0,
        }
    ])
    with pd.ExcelWriter(chosen_path, engine="openpyxl") as writer:
        chosen.to_excel(writer, sheet_name="All economies rows", index=False)
    repo = tmp_path / "repo"
    target = repo / "data/00APEC_2024_low_with_subtotals.csv"
    _write_target(target, include_2023=False)

    first = propagate_chosen_esto_rows(chosen_path, [repo], write_to_source_files=True)
    second = propagate_chosen_esto_rows(chosen_path, [repo], write_to_source_files=True)

    assert first.loc[0, "append_row_count"] == 1
    assert second.loc[0, "append_row_count"] == 0
    assert second.loc[0, "status"] == "complete"
    result = pd.read_csv(target)
    assert len(result) == 2
    assert float(result.iloc[-1]["2022"]) == 8.0


def test_vintage_sets_are_written_only_to_matching_target_files(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    data_dir = repository / "data"
    data_dir.mkdir(parents=True)
    columns = ["economy", "flows", "products", "is_subtotal", "2022"]
    for vintage in ("2024", "2025"):
        pd.DataFrame(columns=columns).to_csv(
            data_dir / f"00APEC_{vintage}_low_with_subtotals.csv",
            index=False,
        )
    rows_2024 = tmp_path / "rows_2024.csv"
    rows_2025 = tmp_path / "rows_2025.csv"
    pd.DataFrame([{
        "economy": "01AAA", "flows": "16.01.99 Unallocated",
        "products": "17 Electricity", "is_subtotal": "FALSE", "2022": 24,
    }]).to_csv(rows_2024, index=False)
    pd.DataFrame([{
        "economy": "01AAA", "flows": "16.01.99 Unallocated",
        "products": "17 Electricity", "is_subtotal": "FALSE", "2022": 25,
    }]).to_csv(rows_2025, index=False)

    summary = propagate_chosen_esto_rows_by_vintage(
        chosen_rows_by_vintage={"2024": rows_2024, "2025": rows_2025},
        repository_roots=[repository],
        write_to_source_files=True,
    )

    written_2024 = pd.read_csv(data_dir / "00APEC_2024_low_with_subtotals.csv")
    written_2025 = pd.read_csv(data_dir / "00APEC_2025_low_with_subtotals.csv")
    assert written_2024.loc[0, "2022"] == 24
    assert written_2025.loc[0, "2022"] == 25
    assert set(summary["chosen_vintage"]) == {"2024", "2025"}
