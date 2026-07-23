# `config/` — navigation guide

Only files directly under `config/` are git-tracked (see `.gitignore`: `!config/*` then
`config/*/`, which re-ignores every subfolder). Subfolders like `config/archive/` exist locally
but are never committed — they're either write targets (backups) or local scratch.

## Required to run the pipeline

| File | Used by |
|---|---|
| `outlook_mappings_master.xlsx` | The core editable mapping workbook — read by Stage 0, Stage 1, Stage 3, and most `mapping_tools/*` scripts. |
| `master_config.xlsx` | Stage 1's fallback workbook (`FALLBACK_WORKBOOK_PATH`). |
| `mapping_issue_exception_sets.xlsx` | Reviewed QA exceptions, read by Stage 0 and several `mapping_tools/*` scripts. Also the authority for "ignored, not modelled" sectors/fuels — see `docs/special_rules_and_design_decisions.md` MAP-011. |
| `source_branch_fallback_rules.csv` | Read during LEAP→ESTO conversion (`data_convert` stage). |
| `all_demand_aggregated_components.json` | Same conversion step. |
| `common_esto_label_overrides.csv` | Read in Stage 2 (`build_common_esto_structure.py`). |

## `archive/`

Write-only backup target — every script that edits `outlook_mappings_master.xlsx` copies the
previous version here first (`ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)` then
`shutil.copy2(...)`). Not read by anything, not required to pre-exist, accumulates indefinitely
with no automatic pruning (see `docs/results_folder_cleanup_candidates.md`).

## Files present but not required by the pipeline (as of 2026-07-23)

Confirmed via grep across `codebase/`: none of these appear as a load target from any current
script.

- `config/176BC200`, `config/6AC9DA10`, `config/E0E85740`, `config/E2F1A260`, `config/FDC59700` —
  Excel lock/crash-recovery artifacts (hex filenames, `.xlsx`-signature binary content).
  `docs/guide_outlook_mappings_master.md` already documents these as safe to ignore.
- `outlook_mappings_master new.xlsx`, `outlook_mappings_master new_with_other_branches_review.xlsx`,
  `outlook_mappings_master new_with_other_branches_review v2.xlsx` — look like manual scratch
  variants of the main workbook, not a script input. Not archived without confirming they aren't
  an in-progress review copy someone is using — see the repo-cleanup report for this pass.
- `leap_results_expected_sheets.json`, `mapping_coverage_gaps.csv`,
  `missing_zero_branch_mapping_candidates.xlsx`, `subtotal_labels/subtotal_labels.csv` — present
  but unreferenced anywhere in current `codebase/`.
- `inverted_conservation_target_aliases.json`, `inverted_conservation_target_variants.json` —
  used only by `inverted_conservation_validation.py`, a standalone QA script not imported by
  `run_mapping_pipeline.py`. Needed only if you run that check specifically.

## Legacy

`master_config.xlsx` above is still required (Stage 1 fallback), but its main use is the
superseded refresh path — see `docs/workflow_inventory.md` for the full legacy-vs-live trace.

## Full detail

See `docs/repo_data_slimdown_plan.md` for the complete file-by-file breakdown (including which
files are safe to leave out entirely) and `docs/workflow_inventory.md` for which scripts read
which config files.
