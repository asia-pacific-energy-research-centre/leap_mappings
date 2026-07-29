#%%
"""Refresh and promote the production separate-axis mapping contract.

The editable single-axis workbook is never rebuilt during an ordinary refresh.
This workflow compiles fresh evidence, prepares narrow workbook source tables,
uses the maintained artifact-tool builder, reopens the generated workbooks,
and promotes the validated compatibility workbook to the canonical filename.
"""

#%%
from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
from pathlib import Path


# --- Stable paths -----------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
ARTIFACT_BUILDER_PATH = (
    REPO_ROOT / "codebase" / "separate_axis_mapping_workbooks_artifact_builder.mjs"
)
EDITABLE_AXIS_WORKBOOK_PATH = (
    REPO_ROOT / "config" / "outlook_mappings_single_axis.xlsx"
)
GENERATED_PAIR_WORKBOOK_PATH = (
    REPO_ROOT / "config" / "outlook_mappings_key_pairs_generated.xlsx"
)
CANONICAL_MASTER_PATH = (
    REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
)
GENERATION_MANIFEST_PATH = (
    REPO_ROOT / "config" / "outlook_mappings_generation_manifest.json"
)
REFRESH_OUTPUT_ROOT = (
    REPO_ROOT / "outputs" / "separate_axis_mapping_refresh"
)
BUILDER_LOG_PATH = REFRESH_OUTPUT_ROOT / "workbooks" / "artifact_builder.log"


# --- Functions --------------------------------------------------------------

def _resolve_node_executable(node_executable: str | Path | None) -> Path:
    """Resolve the explicitly supplied artifact-tool Node runtime."""
    candidate = (
        Path(node_executable)
        if node_executable is not None
        else Path(
            os.environ.get(
                "CODEX_ARTIFACT_NODE",
                (
                    "C:/Users/Work/.cache/codex-runtimes/"
                    "codex-primary-runtime/dependencies/node/bin/node.exe"
                ),
            )
        )
    )
    if not candidate.exists():
        raise FileNotFoundError(
            "Artifact-tool Node executable not found. Pass node_executable "
            f"explicitly or set CODEX_ARTIFACT_NODE: {candidate}"
        )
    return candidate.resolve()


def _tail_text(path: Path, line_count: int = 40) -> str:
    """Return a bounded log tail for failures and notebook feedback."""
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-line_count:])


def _git_head_mapping_hash() -> str | None:
    """Hash the canonical workbook committed at HEAD when Git is available."""
    completed = subprocess.run(
        [
            "git",
            "show",
            "HEAD:config/outlook_mappings_master.xlsx",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        return None
    import hashlib

    return hashlib.sha256(completed.stdout).hexdigest()


def _run_artifact_builder(
    node_executable: Path,
    promote_master: bool,
    rebuild_editable_workbook: bool,
) -> None:
    """Build, reopen, validate, and optionally promote the workbooks."""
    BUILDER_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(
        {
            "SEPARATE_AXIS_REPO_ROOT": str(REPO_ROOT),
            "BUILD_EDITABLE": str(bool(rebuild_editable_workbook)).lower(),
            "BUILD_PAIRS": "true",
            "BUILD_MASTER": "true",
            "VERIFY_PAIRS": "true",
            "PROMOTE_MASTER": str(bool(promote_master)).lower(),
        }
    )
    git_head_mapping_hash = _git_head_mapping_hash()
    if git_head_mapping_hash is not None:
        environment["ORIGINAL_CANONICAL_MASTER_SHA256"] = git_head_mapping_hash
    with BUILDER_LOG_PATH.open("w", encoding="utf-8") as log_file:
        completed = subprocess.run(
            [str(node_executable), str(ARTIFACT_BUILDER_PATH)],
            cwd=REPO_ROOT,
            env=environment,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
        )
    if completed.returncode != 0:
        print(_tail_text(BUILDER_LOG_PATH))
        raise RuntimeError(
            "Separate-axis artifact builder failed with exit code "
            f"{completed.returncode}. See {BUILDER_LOG_PATH}"
        )
    print(_tail_text(BUILDER_LOG_PATH, line_count=12))


def run_separate_axis_mapping_refresh(
    node_executable: str | Path | None = None,
    historical_boundary_year: int = 2023,
    force_leap_registry_refresh: bool = False,
    promote_master: bool = True,
    rebuild_editable_workbook: bool = False,
) -> dict[str, object]:
    """Refresh the generated authorities and promote the canonical workbook."""
    if not EDITABLE_AXIS_WORKBOOK_PATH.exists():
        raise FileNotFoundError(
            "The human-edited single-axis workbook is missing: "
            f"{EDITABLE_AXIS_WORKBOOK_PATH}"
        )

    # Imports are local so importing this central workflow has no side effects.
    from codebase.separate_axis_mapping_master_prototype_workflow import (
        run_single_axis_master_prototype,
    )
    from codebase.separate_axis_mapping_split_workbooks_workflow import (
        prepare_split_workbook_sources,
    )

    compiler_manifest = run_single_axis_master_prototype(
        historical_boundary_year=historical_boundary_year,
        force_leap_registry_refresh=force_leap_registry_refresh,
    )
    split_manifest = prepare_split_workbook_sources()
    _run_artifact_builder(
        node_executable=_resolve_node_executable(node_executable),
        promote_master=promote_master,
        rebuild_editable_workbook=rebuild_editable_workbook,
    )

    if promote_master:
        if not GENERATION_MANIFEST_PATH.exists():
            raise FileNotFoundError(
                "Promotion completed without a generation manifest: "
                f"{GENERATION_MANIFEST_PATH}"
            )
        generation_manifest = json.loads(
            GENERATION_MANIFEST_PATH.read_text(encoding="utf-8")
        )
        if generation_manifest.get("status") != "promoted_and_reopened":
            raise ValueError(
                "Generated workbook promotion did not pass reopen validation: "
                f"{generation_manifest.get('status')!r}"
            )
    else:
        generation_manifest = {
            "status": "candidate_generated_not_promoted",
        }

    result = {
        "status": generation_manifest["status"],
        "compiler_manifest": compiler_manifest,
        "split_manifest": split_manifest,
        "generation_manifest": generation_manifest,
        "editable_axis_workbook_path": str(EDITABLE_AXIS_WORKBOOK_PATH),
        "generated_pair_workbook_path": str(GENERATED_PAIR_WORKBOOK_PATH),
        "canonical_master_path": str(CANONICAL_MASTER_PATH),
        "builder_log_path": str(BUILDER_LOG_PATH),
    }
    print(json.dumps(result, indent=2))
    return result


# --- Frequently changed run flags ------------------------------------------

RUN_SEPARATE_AXIS_MAPPING_REFRESH = True
HISTORICAL_BOUNDARY_YEAR = 2023
FORCE_LEAP_REGISTRY_REFRESH = False
PROMOTE_MASTER = True
# Use True only for an intentional editable-workbook format/README migration.
REBUILD_EDITABLE_WORKBOOK = False
NODE_EXECUTABLE = (
    "C:/Users/Work/.cache/codex-runtimes/"
    "codex-primary-runtime/dependencies/node/bin/node.exe"
)


#%%
if __name__ == "__main__" and RUN_SEPARATE_AXIS_MAPPING_REFRESH:
    try:
        REFRESH_RESULT = run_separate_axis_mapping_refresh(
            node_executable=NODE_EXECUTABLE,
            historical_boundary_year=HISTORICAL_BOUNDARY_YEAR,
            force_leap_registry_refresh=FORCE_LEAP_REGISTRY_REFRESH,
            promote_master=PROMOTE_MASTER,
            rebuild_editable_workbook=REBUILD_EDITABLE_WORKBOOK,
        )
    except Exception:
        print("Separate-axis production refresh failed.")
        traceback.print_exc()
        raise

#%%
