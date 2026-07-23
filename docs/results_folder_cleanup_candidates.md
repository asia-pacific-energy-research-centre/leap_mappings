# `results/` cleanup candidates (not yet actioned, except where marked done below)

**Status:** mostly observations only — most of this file describes candidates that have **not**
been deleted, moved, or modified. A small number of items (the root-level scratch files and the
`codebase/mapping_code/` duplicate) *were* actioned as part of the 2026-07-23 repo cleanup pass —
see `docs/archive_log.md` for exactly what moved where. Everything diagnostic-CSV-related below
is deliberately left untouched: it overlaps with a separately-queued design task exploring
whether groups of this repo's ~103 diagnostic output files can be consolidated into fewer files
with shared structure. Don't archive/dedupe anything in the "confirmed orphaned" or "likely
clutter" tables below until that design work has landed and can inform whether a file is being
superseded by consolidation rather than just deleted.

## Important safety note before anyone deletes anything here

`results/` (and `config/archive/`, via the `config/*/` rule) is **entirely gitignored** — see
`.gitignore`. That means none of it has git history. Deleting a file under `results/` is **not
recoverable through git** the way deleting a tracked file would be. Before removing anything
flagged below:

1. Confirm it's genuinely regenerable — i.e. either a current script writes it again on the next
   run, or it's clearly superseded by a named replacement (noted per item below).
2. If there's any doubt, move it to a dated quarantine location instead of deleting outright
   (e.g. a zip in a location outside the repo, or a clearly-named `results/_quarantine_<date>/`
   folder excluded from routine use) and note the move here, rather than hard-deleting.
3. Update this file with what was actually done (kept / moved / deleted and why) so the record
   stays trustworthy — don't let it silently drift out of date with reality.

## How these were identified

Two passes: (1) a full survey of every `results/`-writing path in current `codebase/` scripts
(the manifest behind `results/README.md` and its subfolder READMEs); (2) a diff against the
`results/` file listing captured from `config data results leap mappigns.zip` (a snapshot of a
real prior run). Anything present in the zip snapshot with **zero matches** when grepped for in
current `codebase/*.py` is flagged as "confirmed orphaned" below. A few more are flagged as
"likely orphaned" based on naming pattern (manual copies, timestamps, "baseline"/"SLICE"
suffixes) even though this wasn't exhaustively verified for every one — re-verify against this
repo's actual current files before acting, not just this list.

## Confirmed orphaned — zero references anywhere in current `codebase/`

| Path | Why it's flagged |
|---|---|
| `results/tree_structure/anchor_diagnostics/` (`reason_breakdown.csv`, `reason_totals_*.csv`, `status_by_economy.csv`, `status_by_year.csv`, `subtotal_fuel_involvement.csv`, `top500_*.csv`) | No current script writes to this path or references these filenames. `reconcile_anchor_validation.py`'s own docstring says it "replaces earlier tree-walk anchor methodology" — this folder is almost certainly that earlier method's output, superseded by `results/common_esto/anchor_reconciliation/`. |
| `results/tree_structure/source_parent_anchor_MISSING_children.csv`, `source_parent_anchor_MISSING_parent_pairs.csv` | Not referenced anywhere; naming doesn't match the current `source_parent_anchor_validation.csv` / `_summary.csv` pair. Likely an older version of that script's output format. |
| `results/tree_structure/source_parent_anchor_validation_SLICE.csv`, `_SLICE_summary.csv` | Not referenced anywhere. Looks like a manually filtered export of the full validation file, not an automatic output. |
| `results/tree_structure/common_esto_validation_baseline_20260708.csv`, `common_esto_validation_summary_baseline_20260708.csv` | Not referenced anywhere; "baseline" naming isn't produced by any current script — looks like a manually saved snapshot for comparison against a later run. |
| `results/missing_mapped_esto_rows/` (top-level, **outside** `results/maintenance/`) | Duplicate of `results/maintenance/missing_mapped_esto_rows/`. `build_missing_mapped_esto_rows.py` only ever writes under `results/maintenance/`. This top-level copy is stale from an earlier code path where the output directory was different. |
| `config/leap_results_expected_sheets.json`, `config/mapping_coverage_gaps.csv`, `config/missing_zero_branch_mapping_candidates.xlsx`, `config/subtotal_labels/subtotal_labels.csv` | (Carried over from the earlier `config`/`data` extraction audit — `docs/repo_data_slimdown_plan.md` — included here too since they're the same class of issue: present in a past snapshot, referenced nowhere in current code.) |

## Likely clutter — manual duplicates / ad hoc artifacts (not exhaustively re-verified)

| Path pattern | Why it's flagged |
|---|---|
| `results/maintenance/*_copy.csv`, `*_copy 2.csv` (e.g. `subtotal_draft_esto_pairs copy.csv`, `subtotal_draft_esto_pairs copy 2.csv`, `subtotal_mismatch_suggested_improvements copy.csv`, and the equivalents for `_ninth_pairs` / `_leap_pairs`) | File-explorer-style manual copies of files that already exist without the `copy` suffix. No script produces a `*_copy*.csv` name. |
| `results/maintenance/display_names_qa copy.csv`, `display_names_qa_new.csv` | Same pattern — manual duplicates of `display_names_qa.csv`. |
| `results/logs/mapping_pipeline_<timestamp>*.log`, `mapping_pipeline_codex_*`, `mapping_pipeline_rollup_tree_nodes_*`, `mapping_pipeline_stage*_codex_*`, `*.pid`, `*.pid.txt`, `run_mapping_pipeline_*.ps1`, `stdin_pipe_test.*`, `stage_runs/*` | **Archived 2026-07-23** to `results/logs/_archive_2026-07-23/` (gitignored, so not recoverable via git — moved rather than deleted for exactly that reason). Only `results/logs/mapping_pipeline.log` (no timestamp) is written by current code (`run_mapping_pipeline.py`'s `_PIPELINE_LOG_PATH`); the rest were manually redirected output from ad hoc terminal sessions during earlier development. |
| `results/maintenance/logs/*` (`anchor_validation_yearslice_*`, `compile_structural_*`, `inverted_conservation_rerun_*`, `pipeline_1_2_dataconvert_3_*`, `stage0_maintenance_*`) | **Archived 2026-07-23** to `results/maintenance/_archive_2026-07-23/logs/` — same category as above, manual run logs. |
| `results/common_esto/common_esto_comparison_wide_rebuilt.csv`, `qa_common_esto_partial_coverage_mapping_candidates_rebuilt.csv` | Still present, not actioned. "`_rebuilt`" variants of files that already exist without that suffix — likely from a manual rebuild/comparison run, not a distinct current output name. Left for the diagnostic-consolidation design task. |
| `results/common_esto/configurable_scopes_stage2.std{out,err}.log`, `configurable_scopes_stage3.std{out,err}.log` | **Archived 2026-07-23** to `results/common_esto/_archive_2026-07-23/` — ad hoc redirected output from a manual run with custom comparison scopes, not a named pipeline output. |
| `config/archive/*.xlsx` (~80 files: `outlook_mappings_master.before_*`, `.maintenance_run_*`, `outlook_mappings_master - Copy.xlsx`, `... backup.xlsx`, `... backuip 207.xlsx`, etc.) | Still present, not actioned. Legitimate backups (each is written by an `ARCHIVE_DIR.mkdir(...)` + `shutil.copy2(...)` call before a workbook edit), but they accumulate indefinitely with no pruning. Worth a retention policy (e.g. keep last N, or keep one per month) rather than deleting outright — these are the one category here that's a genuine safety net, not clutter, so treat with more caution than the rest of this list. |
| `config/E0E85740`, `config/E2F1A260`, `config/6AC9DA10`, `config/FDC59700` | Still present, not actioned. Orphaned binary blobs with hex filenames (zip/xlsx signature) — Office crash-recovery temp files. Not referenced anywhere, but `docs/guide_outlook_mappings_master.md` already documents these as safe to ignore, and moving them doesn't reduce clutter since Excel regenerates them on next open — left in place deliberately, not an oversight. |
| `results/common_esto/inverted_conservation.building/` | Still present, not actioned. `inverted_conservation_summary.csv` inside this folder is byte-size-identical (6,784 B) to the one in `results/common_esto/inverted_conservation/` — strong evidence this is a true redundant duplicate from a repeated manual run with a typo'd/experimental `output_dir`, not a meaningfully different variant. Compare with `inverted_conservation_variant_verification/`, which is a different size and plausibly a genuinely distinct run. |

## `codebase/` findings (from the follow-up codebase/ navigation pass)

Not `results/` files, but the same "stale/diverged, not obviously distinguishable from the live
version" problem, so recorded here too — see `docs/workflow_inventory.md` for full detail:

| Path | Why it's flagged | Status |
|---|---|---|
| `codebase/mapping_code/` (whole folder) | A diverged duplicate "starter prototype" bundle of two `codebase/mapping_tools/` scripts, confirmed via `diff` to not be identical to the live versions. Hardcodes a different machine's Python path and targets the legacy `config/leap_mappings.xlsx`. Zero references anywhere else in `codebase/`. | **Archived 2026-07-23** to `archive/2026-07-23_repo_cleanup/mapping_code/` (git-tracked move, fully recoverable via `git log`). |
| `codebase/utilities/build_canonical_mapping_views.py` | Imports a module (`codebase.scrapbook.utilities`) that doesn't exist anywhere in this repo's git history — currently broken, cannot run. | Not actioned — either restore/replace the missing dependency or remove the script; needs a decision, not a mechanical cleanup. |
| `codebase/functions/unified_name_lookup.py` | Not imported anywhere in `codebase/`. | Not actioned. |

## Root-level scratch files — actioned 2026-07-23

Unlike everything else in this doc, these three were **git-tracked** (`git log -- <file>` showed
real history), so moving them was fully recoverable via git — the caution above about
gitignored, unrecoverable content didn't apply here.

| File | What it actually was | Action taken |
|---|---|---|
| `Untitled-1.md` | A raw console log dump from a full pipeline run on a different machine. Duplicated what `results/logs/mapping_pipeline.log` already captures for any current run. | Moved to `docs/archive/2026-07-23_repo_cleanup/Untitled-1.md`. |
| `old gent chat.txt` | A saved agent/Copilot chat transcript from a previous session. Not read by any code. | Moved to `docs/archive/2026-07-23_repo_cleanup/old_gent_chat.txt`. |
| `prompts 5-7.md` | Recorded a real design rule: ignored sectors/fuels in ESTO/9th source data should be excluded via `config/mapping_issue_exception_sets.xlsx` rather than chased as mapping gaps. | Rule folded into `docs/special_rules_and_design_decisions.md` as **MAP-011** before the file itself was moved to `docs/archive/2026-07-23_repo_cleanup/prompts_5-7.md`, so the content isn't lost. |

## Not flagged (intentionally kept as-is)

- `results/mapping_graph_index/`, `results/for_colleagues/`, `results/common_esto/structural_artifacts/`, `partitioned_application/`, `partition_cache/`, `economy_scoped/`, `anchor_reconciliation/`, `anchor_contribution_breakdown/`, `inverted_conservation/` — all produced by *current*, named standalone scripts (see the relevant `results/*/README.md`). Not part of the main pipeline run, but not orphaned either.
- `results/maintenance/subtotal_mismatch_suggested_improvements.csv`, `subtotal_draft_*_pairs.csv` (without `copy` suffix), `rollup_consistency.csv` — current outputs of standalone review tools, kept.
- `config/outlook_mappings_master new.xlsx`, `config/outlook_mappings_master new_with_other_branches_review.xlsx`, `config/outlook_mappings_master new_with_other_branches_review v2.xlsx` — look like manual scratch variants of the main workbook (zero code references), but **not archived without a human confirming they're not an in-progress review copy someone is actively using**. `outlook_mappings_master new.xlsx` specifically was an active, in-progress review copy as of 2026-07-23 (its content was merged into the canonical workbook that same day) — concrete proof this category needs a human check before touching, not just a "zero references" heuristic.

## Suggested next step (not done here)

For the still-untouched "confirmed orphaned" and "likely clutter" tables above: hold off until
the diagnostic-file-consolidation design task lands, since several of these entries are exactly
the kind of near-duplicate diagnostic file that task is meant to evaluate systematically (dedupe
vs. consolidate vs. archive may have different right answers depending on that design). Treat
`config/archive/` pruning as a separate, lower-risk "retention policy" decision independent of
that design work.
