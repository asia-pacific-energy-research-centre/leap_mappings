# %% [markdown]
# ## leap_mappings pipeline smoke run
#
# Run stage-by-stage from a Jupyter-compatible notebook or IDE cell runner.
# Stops at the first failure. Set PYTHONPATH to the repo root before running.

# %%
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(r"C:\Users\Work\github\leap_mappings")
os.chdir(REPO_ROOT)

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def run(cmd: list[str], *, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess:
    merged_env = os.environ.copy()
    merged_env["PYTHONPATH"] = str(REPO_ROOT)
    if env:
        merged_env.update(env)
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=REPO_ROOT, env=merged_env, text=True, capture_output=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed (exit {result.returncode}): {' '.join(cmd)}")
    return result


def assert_files_exist(paths: list[Path]) -> None:
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing expected outputs:\n" + "\n".join(str(p) for p in missing))
    print("All expected files exist.")


def show_csv_head(path: Path, n: int = 5) -> None:
    import pandas as pd
    df = pd.read_csv(path)
    print(f"\n{path.name}: {len(df):,} rows")
    try:
        display(df.head(n))  # noqa: F821  # available in Jupyter
    except NameError:
        print(df.head(n).to_string())


# %% [markdown]
# ### Preflight — confirm inputs exist

# %%
run(["git", "status", "--short"], check=False)

required_inputs = [
    REPO_ROOT / "config" / "outlook_mappings_master.xlsx",
    REPO_ROOT / "config" / "mapping_issue_exception_sets.xlsx",
    REPO_ROOT / "data" / "00APEC_2025_low_with_subtotals.csv",
    REPO_ROOT / "data" / "merged_file_energy_ALL_20251106.csv",
]
assert_files_exist(required_inputs)

# %% [markdown]
# ### Unit gate — per-stage tests must pass before running stages

# %%
run(["python", "-m", "pytest", "-q", "tests/test_outlook_mapping_maintenance_workflow.py"])
run(["python", "-m", "pytest", "-q", "tests/test_build_energy_balance_relationships.py"])
run(["python", "-m", "pytest", "-q", "tests/test_build_dataset_tree_structure.py"])
run(["python", "-m", "pytest", "-q",
     "tests/test_apply_common_esto_structure.py",
     "tests/test_common_esto_validation_orchestration.py"])

# %% [markdown]
# ### Stage 0 — maintenance workflow

# %%
run(["python", "codebase/outlook_mapping_maintenance_workflow.py"])

stage0_outputs = [
    REPO_ROOT / "results" / "maintenance" / "maintenance_summary.csv",
    REPO_ROOT / "results" / "maintenance" / "cardinality_leap_esto.csv",
    REPO_ROOT / "results" / "maintenance" / "cardinality_leap_ninth.csv",
    REPO_ROOT / "results" / "maintenance" / "cardinality_ninth_esto.csv",
    REPO_ROOT / "results" / "maintenance" / "subtotal_mismatches.csv",
    REPO_ROOT / "results" / "maintenance" / "unmapped_esto_pairs.csv",
    REPO_ROOT / "results" / "maintenance" / "unmapped_ninth_pairs.csv",
]
assert_files_exist(stage0_outputs)
show_csv_head(stage0_outputs[0])

# %% [markdown]
# ### Stage 1 — build energy balance relationships

# %%
run(["python", "codebase/mapping_tools/build_energy_balance_relationships.py"])

stage1_outputs = [
    REPO_ROOT / "results" / "mapping_relationships" / "energy_balance_relationships.csv",
    REPO_ROOT / "results" / "mapping_relationships" / "energy_balance_relationships.xlsx",
]
assert_files_exist(stage1_outputs)
show_csv_head(stage1_outputs[0])

# %% [markdown]
# ### Stage 2 — build common ESTO structure

# %%
run(["python", "codebase/mapping_tools/build_common_esto_structure.py"])

stage2_outputs = [
    REPO_ROOT / "results" / "common_esto" / "common_esto_rows.csv",
    REPO_ROOT / "results" / "common_esto" / "esto_to_common_esto_map.csv",
]
assert_files_exist(stage2_outputs)
show_csv_head(stage2_outputs[0])

# %% [markdown]
# ### Stage 3 — apply common ESTO structure

# %%
run(["python", "codebase/mapping_tools/apply_common_esto_structure.py"])

stage3_outputs = [
    REPO_ROOT / "results" / "common_esto" / "common_esto_comparison_data.csv",
]
assert_files_exist(stage3_outputs)
show_csv_head(stage3_outputs[0])

# %% [markdown]
# ### End-to-end wrapper

# %%
run(["python", "codebase/run_mapping_pipeline.py"])

# %% [markdown]
# ### Final summary

# %%
summary_files = [
    REPO_ROOT / "results" / "maintenance" / "maintenance_summary.csv",
    REPO_ROOT / "results" / "mapping_relationships" / "energy_balance_relationships.csv",
    REPO_ROOT / "results" / "common_esto" / "common_esto_rows.csv",
    REPO_ROOT / "results" / "common_esto" / "common_esto_comparison_data.csv",
]

for path in summary_files:
    status = "OK" if path.exists() else "MISSING"
    print(f"[{status}]  {path.relative_to(REPO_ROOT)}")
