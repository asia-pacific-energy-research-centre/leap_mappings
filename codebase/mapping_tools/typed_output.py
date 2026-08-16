#%%
"""Atomic Parquet/Zstandard output helpers for machine-detail diagnostics."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

import pandas as pd


PARQUET_COMPRESSION = "zstd"
TABULAR_ARTIFACT_FORMAT = "leap_mappings_manifested_tabular_artifact"
TABULAR_ARTIFACT_VERSION = 1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_path(path: Path) -> Path:
    path = Path(path)
    return path.with_name(f"{path.name}.manifest.json")


def _write_json_atomic(payload: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def write_manifested_parquet(
    frame: pd.DataFrame,
    path: Path,
    *,
    artifact_type: str,
) -> dict[str, object]:
    """Write one authoritative Parquet table atomically with an integrity sidecar."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        frame.to_parquet(temporary, index=False, compression=PARQUET_COMPRESSION)
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    artifact = {
        "path": path.name,
        "format": "parquet",
        "compression": PARQUET_COMPRESSION,
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "columns": [str(column) for column in frame.columns],
        "dtypes": [str(dtype) for dtype in frame.dtypes],
        "byte_size": int(path.stat().st_size),
        "sha256": sha256_file(path),
    }
    manifest = {
        "storage_format": TABULAR_ARTIFACT_FORMAT,
        "format_version": TABULAR_ARTIFACT_VERSION,
        "artifact_type": str(artifact_type),
        "artifact": artifact,
    }
    _write_json_atomic(manifest, manifest_path(path))
    return manifest


def read_manifested_parquet(path: Path) -> pd.DataFrame:
    """Read one Parquet table after validating its sidecar version and hash."""
    path = Path(path)
    sidecar = manifest_path(path)
    try:
        manifest = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unreadable Parquet artifact manifest: {sidecar}") from exc
    if manifest.get("storage_format") != TABULAR_ARTIFACT_FORMAT:
        raise ValueError(f"Unsupported Parquet artifact manifest: {sidecar}")
    if manifest.get("format_version") != TABULAR_ARTIFACT_VERSION:
        raise ValueError(f"Unsupported Parquet artifact version: {sidecar}")
    artifact = manifest.get("artifact", {})
    if artifact.get("format") != "parquet" or artifact.get("compression") != PARQUET_COMPRESSION:
        raise ValueError(f"Unsupported Parquet artifact storage: {sidecar}")
    if not path.is_file() or sha256_file(path) != artifact.get("sha256"):
        raise ValueError(f"Parquet artifact hash mismatch: {path}")
    frame = pd.read_parquet(path)
    expected_dtypes = artifact.get("dtypes", [])
    for position, dtype_name in enumerate(expected_dtypes):
        if position < len(frame.columns) and str(frame.dtypes.iloc[position]) != dtype_name:
            frame.isetitem(position, frame.iloc[:, position].astype(dtype_name))
    if len(frame) != int(artifact.get("row_count", -1)):
        raise ValueError(f"Parquet artifact row-count mismatch: {path}")
    return frame


#%%
