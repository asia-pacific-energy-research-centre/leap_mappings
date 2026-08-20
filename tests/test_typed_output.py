#%%
"""Round-trip and integrity tests for manifested mapping-detail Parquet files."""

from pathlib import Path

import pandas as pd
import pytest

from codebase.mapping_tools.typed_output import (
    read_manifested_parquet,
    write_manifested_parquet,
)


def test_manifested_parquet_preserves_order_values_nulls_and_dtypes(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "name": pd.Series(["first", pd.NA], dtype="string"),
            "year": pd.Series([2022, 2023], dtype="int64"),
            "value": pd.Series([1.5, float("nan")], dtype="float64"),
        }
    )
    path = tmp_path / "detail.parquet"

    write_manifested_parquet(frame, path, artifact_type="test_detail")
    restored = read_manifested_parquet(path)

    pd.testing.assert_frame_equal(restored, frame)


def test_manifested_parquet_rejects_corruption(tmp_path: Path) -> None:
    path = tmp_path / "detail.parquet"
    write_manifested_parquet(pd.DataFrame({"value": [1]}), path, artifact_type="test")
    path.write_bytes(path.read_bytes() + b"corrupt")

    with pytest.raises(ValueError, match="hash mismatch"):
        read_manifested_parquet(path)


def test_manifested_parquet_projects_requested_columns_and_restores_dtypes(
    tmp_path: Path,
) -> None:
    frame = pd.DataFrame({
        "label": pd.Series(["a", "b"], dtype="string"),
        "year": pd.Series([2022, 2023], dtype="int64"),
        "value": pd.Series([1.0, 2.0], dtype="float64"),
    })
    path = tmp_path / "detail.parquet"
    write_manifested_parquet(frame, path, artifact_type="test_detail")

    restored = read_manifested_parquet(path, columns=["value", "label"])

    pd.testing.assert_frame_equal(restored, frame[["value", "label"]])


def test_manifested_parquet_rejects_unknown_requested_column(tmp_path: Path) -> None:
    path = tmp_path / "detail.parquet"
    write_manifested_parquet(pd.DataFrame({"value": [1]}), path, artifact_type="test")

    with pytest.raises(ValueError, match="absent from Parquet artifact"):
        read_manifested_parquet(path, columns=["missing"])


def test_manifested_parquet_applies_validated_row_filters(tmp_path: Path) -> None:
    frame = pd.DataFrame({
        "source_system": ["ESTO", "NINTH"],
        "value": [1.0, 2.0],
    })
    path = tmp_path / "detail.parquet"
    write_manifested_parquet(frame, path, artifact_type="test")

    restored = read_manifested_parquet(
        path,
        columns=["value"],
        filters=[("source_system", "==", "NINTH")],
    )

    assert restored.to_dict("records") == [{"value": 2.0}]


def test_manifested_parquet_rejects_unknown_filter_column(tmp_path: Path) -> None:
    path = tmp_path / "detail.parquet"
    write_manifested_parquet(pd.DataFrame({"value": [1]}), path, artifact_type="test")

    with pytest.raises(ValueError, match="filters reference absent"):
        read_manifested_parquet(path, filters=[("missing", "==", "x")])


def test_manifested_parquet_reuses_run_scoped_integrity_check(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "detail.parquet"
    write_manifested_parquet(pd.DataFrame({"value": [1, 2]}), path, artifact_type="test")
    from codebase.mapping_tools import typed_output as typed_output_module

    real_sha256 = typed_output_module.sha256_file
    calls: list[Path] = []

    def count_sha256(target: Path) -> str:
        calls.append(Path(target))
        return real_sha256(target)

    monkeypatch.setattr(typed_output_module, "sha256_file", count_sha256)
    integrity_cache: dict[str, tuple[int, int, str]] = {}

    read_manifested_parquet(path, columns=["value"], integrity_cache=integrity_cache)
    read_manifested_parquet(
        path,
        columns=["value"],
        filters=[("value", ">", 1)],
        integrity_cache=integrity_cache,
    )

    assert calls == [path]


#%%
