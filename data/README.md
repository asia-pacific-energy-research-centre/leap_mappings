# `data/` — navigation guide

Only `data/README.md` (this file) and any `**/README.md`/`**/.gitkeep` are git-tracked (see
`.gitignore`: `data/*` then explicit exceptions). Everything else here is restored from a shared
archive/zip, not from git.

**Note:** an earlier version of this file described a much larger set of files and workflow
scripts (`codebase/industry_workflow.py`, `full model export.xlsx`, per-sector LEAP import
templates, etc.) that no longer match the current pipeline — none of those files or scripts exist
in this repo any more (verified 2026-07-23). That old content is available via `git log --
data/README.md` if useful for archaeology, but don't treat it as current; this replaces it.

## Required to run the pipeline

| File | Used by |
|---|---|
| `00APEC_2025_low_with_subtotals.csv` | Primary ESTO source table — Stage 0, `data_convert`, Stage 3. |
| `00APEC_2024_low_with_subtotals.csv` | Secondary ESTO year, checked by Stage 0 maintenance for missing-mapped-row detection. |
| `merged_file_energy_ALL_20251106.csv` | 9th Outlook source table — Stage 0, `data_convert`, Stage 3. The single largest required input (currently several hundred MB). |

## Not needed for this repo's pipeline

- `archive/leap balances exports/` — raw LEAP exports are owned by the sibling
  `leap_initialisation` repo; this local copy is legacy/reference only (see the root
  `README.md`'s "Current Inputs" section and `codebase/utilities/leap_balance_export_resolver.py`).
- `merged_file_energy_00_APEC_20251106.csv`, `usa_leap_balance_long.csv` — not referenced by any
  current script (the latter is only a legacy fallback in `build_dataset_tree_structure.py`).

## Full detail

See `docs/repo_data_slimdown_plan.md` for the complete file-by-file breakdown and reasoning.
