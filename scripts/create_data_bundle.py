#%%
"""Create the portable source-data ZIP used to set up leap_mappings."""

from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


# --- Stable bundle contract ---

REPO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_NAME = "leap_mappings"
SIBLING_REPOSITORY_NAME = "leap_initialisation"
MANIFEST_NAME = "bundle_manifest.json"
SCHEMA_VERSION = 1
SOURCE_TABLE_PATHS = (
    Path("data/00APEC_2024_low_with_subtotals.csv"),
    Path("data/00APEC_2025_low_with_subtotals.csv"),
    Path("data/merged_file_energy_ALL_20251106.csv"),
    Path("data/esto_extended.csv"),
    Path("data/temp/new leap rows.xlsx"),
)


def _require_sibling_repository(repo_root: Path) -> Path:
    """Return the sibling initialisation checkout required for paired bundle refreshes."""
    sibling_root = Path(repo_root).resolve().parent / SIBLING_REPOSITORY_NAME
    if not (sibling_root / ".git").exists():
        raise FileNotFoundError(
            "Coordinated data-bundle refresh requires the sibling "
            f"{SIBLING_REPOSITORY_NAME!r} repository at {sibling_root}. "
            "Clone it beside leap_mappings before creating bundles."
        )
    return sibling_root


def _load_sibling_bundle_module(sibling_root: Path):
    module_path = sibling_root / "scripts" / "create_data_bundle.py"
    if not module_path.is_file():
        raise FileNotFoundError(f"Sibling bundle creator not found: {module_path}")
    if str(sibling_root) not in sys.path:
        sys.path.insert(0, str(sibling_root))
    spec = importlib.util.spec_from_file_location("leap_initialisation_create_data_bundle", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load sibling bundle creator: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git_commit(repo_root: Path) -> str:
    """Return the commit recorded in the manifest without requiring Git to exist."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unknown"


def collect_bundle_files(repo_root: Path = REPO_ROOT) -> list[dict[str, object]]:
    """Collect the external source files required by the maintained pipeline."""
    records = []
    missing = []
    for relative_path in SOURCE_TABLE_PATHS:
        source_path = repo_root / relative_path
        if not source_path.is_file():
            missing.append(source_path)
            continue
        records.append(
            {
                "path": relative_path.as_posix(),
                "role": "source_table",
                "size_bytes": source_path.stat().st_size,
            }
        )
    if missing:
        missing_text = "\n".join(str(path) for path in missing)
        raise FileNotFoundError(f"Required bundle inputs are missing:\n{missing_text}")
    records.sort(key=lambda record: str(record["path"]).casefold())
    return records


def default_bundle_path(repo_root: Path = REPO_ROOT) -> Path:
    commit = _git_commit(repo_root)
    short_commit = commit[:8] if commit != "unknown" else "uncommitted"
    date_text = datetime.now(timezone.utc).date().isoformat()
    return repo_root / "data_bundles" / f"{REPOSITORY_NAME}_data_{date_text}_{short_commit}.zip"


def create_data_bundle(
    repo_root: Path = REPO_ROOT,
    bundle_path: Path | None = None,
    replace_existing: bool = False,
) -> Path:
    """Write the ZIP atomically and return its resolved path."""
    repo_root = Path(repo_root).resolve()
    bundle_path = Path(bundle_path or default_bundle_path(repo_root)).resolve()
    if bundle_path.exists() and not replace_existing:
        raise FileExistsError(f"Bundle already exists: {bundle_path}")

    records = collect_bundle_files(repo_root=repo_root)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "repository_name": REPOSITORY_NAME,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_git_commit": _git_commit(repo_root),
        "file_count": len(records),
        "total_uncompressed_bytes": sum(int(record["size_bytes"]) for record in records),
        "files": records,
    }

    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{bundle_path.stem}_",
            suffix=".tmp",
            dir=bundle_path.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

        with zipfile.ZipFile(
            temporary_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
            allowZip64=True,
        ) as archive:
            archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2) + "\n")
            for record in records:
                relative_path = Path(str(record["path"]))
                archive.write(repo_root / relative_path, arcname=relative_path.as_posix())

        os.replace(temporary_path, bundle_path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise

    print(f"Created {bundle_path}")
    print(f"Files: {manifest['file_count']:,}")
    print(f"Uncompressed data: {manifest['total_uncompressed_bytes'] / 1_000_000:.1f} MB")
    print(f"ZIP size: {bundle_path.stat().st_size / 1_000_000:.1f} MB")
    return bundle_path


def create_coordinated_data_bundles(
    repo_root: Path = REPO_ROOT,
    *,
    bundle_path: Path | None = None,
    sibling_bundle_path: Path | None = None,
    replace_existing: bool = False,
) -> dict[str, Path]:
    """Create both sibling repositories' bundles as one visible refresh operation."""
    repo_root = Path(repo_root).resolve()
    sibling_root = _require_sibling_repository(repo_root)
    print(
        "[INFO] Coordinated bundle refresh: creating leap_mappings and "
        "leap_initialisation bundles together."
    )
    sibling_module = _load_sibling_bundle_module(sibling_root)
    # Check both source inventories before publishing either bundle.
    collect_bundle_files(repo_root)
    sibling_module.collect_bundle_files(sibling_root)
    paths = {
        REPOSITORY_NAME: create_data_bundle(
            repo_root=repo_root,
            bundle_path=bundle_path,
            replace_existing=replace_existing,
        ),
        SIBLING_REPOSITORY_NAME: sibling_module.create_data_bundle(
            repo_root=sibling_root,
            bundle_path=sibling_bundle_path,
            replace_existing=replace_existing,
        ),
    }
    print(f"[INFO] Coordinated bundle refresh complete: {paths}")
    return paths


#%%
# --- Frequently changed run settings ---

CREATE_BUNDLE = True
BUNDLE_PATH: Path | None = None
REPLACE_EXISTING_BUNDLE = False

if __name__ == "__main__" and CREATE_BUNDLE:
    create_coordinated_data_bundles(
        repo_root=REPO_ROOT,
        bundle_path=BUNDLE_PATH,
        replace_existing=REPLACE_EXISTING_BUNDLE,
    )

#%%
