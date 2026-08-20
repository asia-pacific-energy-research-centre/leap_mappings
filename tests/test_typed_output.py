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


#%%
