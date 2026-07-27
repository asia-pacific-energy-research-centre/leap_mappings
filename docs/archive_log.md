# Archive log

Running record of files/folders moved (never deleted) out of their working location because they
were identified as single-use/scratch artifacts, not because they were judged worthless. See
`docs/results_folder_cleanup_candidates.md` for candidates that were *documented but not moved*
(mostly diagnostic-output files, deliberately left for the separate diagnostic-consolidation
design task — see that file's note).

Format: date, original path, new path, one-line reason.

## 2026-07-27

Gitignored and recoverable from a verified ZIP:

| Original path | New path | Reason |
|---|---|---|
| Six stale plain recurring outputs: `ninth_results_converted_to_esto.csv`, both `esto*_results_exact_rows.csv`, both source-lineage CSVs, and `esto_component_to_common_row_lineage.csv` | `results/_quarantine_archives/2026-07-27/legacy_uncompressed_pipeline_outputs_pre_20260727.zip` | Superseded by verified `.csv.gz` outputs. The 4,428.7 MB of plain CSVs were stored in a 471.7 MB ZIP with repository-relative paths and an embedded SHA-256 manifest; every entry was read back and hash-verified before the live copies were sent to the Windows Recycle Bin. |
| `results/tree_structure/anchor_diagnostics/` | `results/_quarantine_archives/2026-07-27/results_tree_artifacts_20260727.zip` | Outputs from the superseded tree-walk anchor methodology. ZIP members retain repository-relative paths and SHA-256 values in `archive_manifest.json`. |
| `results/tree_structure/source_parent_anchor_MISSING_children.csv`, `source_parent_anchor_MISSING_parent_pairs.csv` | Same ZIP | Obsolete output names not written or consumed by current code. |
| `results/tree_structure/source_parent_anchor_validation_SLICE.csv`, `source_parent_anchor_validation_SLICE_summary.csv` | Same ZIP | Manual slices superseded by the current validator output and dashboard findings view. |

Extract the ZIP at the repository root to restore every original path. All 14 entries were read
back and hash-verified before they were moved out of the live tree. A redundant uncompressed copy
is temporarily retained under the same dated quarantine folder because direct deletion was blocked
by the execution environment.

## 2026-07-23

Git-tracked (fully recoverable via `git log`/`git mv` history regardless of this log):

| Original path | New path | Reason |
|---|---|---|
| `Untitled-1.md` | `docs/archive/2026-07-23_repo_cleanup/Untitled-1.md` | Raw console-log dump from a full pipeline run on a different machine; duplicates what `results/logs/mapping_pipeline.log` already captures for any current run. |
| `old gent chat.txt` | `docs/archive/2026-07-23_repo_cleanup/old_gent_chat.txt` | Saved agent/Copilot chat transcript, not read by any code. |
| `prompts 5-7.md` | `docs/archive/2026-07-23_repo_cleanup/prompts_5-7.md` | Short working note. Its one real content item (ignored sectors/fuels are excluded via `config/mapping_issue_exception_sets.xlsx`, not chased as mapping gaps) was folded into `docs/special_rules_and_design_decisions.md` as **MAP-011** before archiving, so the rule isn't lost. |
| `codebase/mapping_code/` (whole folder) | `archive/2026-07-23_repo_cleanup/mapping_code/` | Self-described ("starter prototype") diverged duplicate of two `codebase/mapping_tools/` scripts — confirmed via `diff` to not be identical to the live versions, hardcodes a different machine's Python path, targets the legacy `config/leap_mappings.xlsx`. Zero references anywhere else in `codebase/`. |

Gitignored (not recoverable via git — moved rather than deleted for exactly that reason; these are
ad hoc run logs, not the pipeline's current tee'd log or any diagnostic CSV):

| Original path | New path | Reason |
|---|---|---|
| `results/logs/*` (all timestamped/`codex_*`/`*.pid`/`*.pid.txt`/`*.ps1`/`stdin_pipe_test.*`/`stage_runs/` etc.) — everything except `mapping_pipeline.log` | `results/logs/_archive_2026-07-23/` | Ad hoc manual terminal-run logs from earlier development. Only `results/logs/mapping_pipeline.log` (no timestamp) is written by current code (`run_mapping_pipeline.py`'s `_PIPELINE_LOG_PATH`). |
| `results/maintenance/logs/*` | `results/maintenance/_archive_2026-07-23/logs/` | Same category — manual run logs from anchor-validation/structural-compilation/inverted-conservation reruns, not from an automatic tee. |
| `results/common_esto/configurable_scopes_stage2.std{out,err}.log`, `configurable_scopes_stage3.std{out,err}.log` | `results/common_esto/_archive_2026-07-23/` | Ad hoc redirected output from a manual run with custom comparison scopes, not a named pipeline output. |

## Left in place, not archived (see report for full reasoning)

- `config/176BC200`, `config/6AC9DA10`, `config/E0E85740`, `config/E2F1A260`, `config/FDC59700` —
  Excel lock/crash-recovery artifacts. `docs/guide_outlook_mappings_master.md` already documents
  these as safe to ignore. Left as-is: moving them doesn't reduce clutter since Excel regenerates
  them on next open, and an explicit doc already tells readers to ignore them.
- `config/outlook_mappings_master new.xlsx`, `config/outlook_mappings_master new_with_other_branches_review.xlsx`,
  `config/outlook_mappings_master new_with_other_branches_review v2.xlsx` — look like manual
  scratch variants of the main workbook (zero code references), but not archived without a human
  confirming they're not an in-progress review copy someone is actively using. Flagged in the
  report as an uncertain candidate.
- Everything diagnostic-CSV-related (`results/tree_structure/anchor_diagnostics/`,
  `results/maintenance/*_copy*.csv`, `results/missing_mapped_esto_rows/` top-level stale
  duplicate, `results/common_esto/inverted_conservation.building/`, etc.) — deliberately left for
  the separate diagnostic-consolidation design task per this task's scope note. Documented in
  `docs/results_folder_cleanup_candidates.md` instead of acted on here.
