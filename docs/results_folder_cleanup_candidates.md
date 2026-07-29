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
| `results/common_esto/common_esto_comparison_wide_rebuilt.csv`, `qa_common_esto_partial_coverage_mapping_candidates_rebuilt.csv` | Still present, not actioned. Current code automatically writes a `_rebuilt` fallback when the canonical CSV is locked. Check `common_esto_output_status.csv`, timestamps, and the canonical file before classifying either fallback as stale; the suffix alone is not evidence of a manual copy. |
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

## 2026-07-27 continuation handoff: conservative cleanup plan

This section records the follow-up investigation and the agreed direction for a future agent.
It does **not** mean that the listed files have been moved or deleted. At the time of writing,
this repository's cleanup candidates remain in place. The user asked to proceed cautiously and
not interrupt active work.

### What was checked

- All 45 Markdown files in this repository were reviewed for outstanding work, cleanup notes,
  active prompts, and results-folder ownership.
- The sibling `C:\Users\Work\github\leap_initialisation` repository was inspected read-only
  because it recently performed a similar audit. Its dedicated reference is
  `docs/prompts/repo_cleanup_and_consolidation_plan_20260723.md`.
- Candidate paths in the tables above were rechecked against current `codebase/` and `tests/`
  references. The confirmed-orphan candidates still had no current code references.
- The initial inspection found an active `leap_initialisation`
  `supply_reconciliation_workflow.py` process (PID 48596). No cleanup mutation was made while
  it was active, because that workflow may consume the shared mappings configuration. A later
  check found no related Python/Jupyter process. Future agents must make this check again
  immediately before any filesystem move.

### Measured current candidate inventory

These measurements were taken on 2026-07-26. They are planning evidence only; re-measure before
acting because `results/` can change with a pipeline run.

| Candidate | Files | Approx. size | Proposed treatment |
|---|---:|---:|---|
| `results/tree_structure/anchor_diagnostics/` | 10 | 285 KB | Quarantine after confirming `anchor_reconciliation/` is the current replacement. |
| `source_parent_anchor_MISSING_children.csv` and `_MISSING_parent_pairs.csv` | 2 | 319 KB | Quarantine as obsolete output names. |
| `source_parent_anchor_validation_SLICE.csv` and `_SLICE_summary.csv` | 2 | 14.2 MB | Quarantine as manual slices, not regenerated outputs. |
| `common_esto_validation_baseline_20260708.csv` and its summary | 2 | 63.2 MB | Quarantine as dated comparison snapshots; do not delete until the owner confirms no historical comparison is needed. |
| Top-level `results/missing_mapped_esto_rows/` | 15 | 2.0 MB | Quarantine only after a content/recency comparison with `results/maintenance/missing_mapped_esto_rows/`. |
| `common_esto_comparison_wide_rebuilt.csv` | 1 | 27.0 MB | Leave until diagnostic-consolidation design decides whether it is an archival snapshot or a redundant variant. |
| `qa_common_esto_partial_coverage_mapping_candidates_rebuilt.csv` | 1 | 1.5 KB | Same as the preceding rebuilt variant. |
| `results/common_esto/inverted_conservation.building/` | 4 | 2.7 MB | Strong duplicate candidate, but keep pending byte/content comparison of every file with `inverted_conservation/`. |
| `config/archive/` workbook backups | 79 | 19.6 MB | Keep; introduce a retention policy rather than a one-off purge. |
| Four unreferenced config candidates (`leap_results_expected_sheets.json`, `mapping_coverage_gaps.csv`, `missing_zero_branch_mapping_candidates.xlsx`, `subtotal_labels/subtotal_labels.csv`) | 4 | 327 KB | Quarantine only after one final whole-repo consumer check, including notebooks and documentation. |

The confirmed-orphan and clearly redundant rows total roughly 130 MB if the dated baseline and
rebuilt variants are included. This is useful cleanup but not a disk-emergency; correctness and
recoverability matter more than saving the space.

### Lessons from `leap_initialisation`

The initialisation cleanup is a useful pattern, but it was not a blanket deletion exercise.
Its plan classified candidates as **safe to delete**, **archive candidate**, **protected**, or
**uncertain/human decision**. Only its highest-confidence dead-code subset was executed:
commit `81119c0` deleted four modules after creating a backup ZIP and running the full test
suite. That test run caught two false positives (a supposedly dead utility and a package whose
own `__init__.py` imported apparently unused modules), and those files were restored.

Apply the transferable lessons here:

1. Do not equate “no obvious references” with “safe to delete.” Check code, tests, documented
   manual workflows, and package-level imports where applicable.
2. Keep intentional diagnostic drill-downs (for example summary -> breakdown -> lineage) even
   if they share a subject. Consolidation should remove duplicated *views*, not useful evidence.
3. Make consolidation additive first: create a supported primary output or a compatibility view,
   update consumers and documentation, validate a current run, then retire old outputs.
4. Prefer reversible handling for ignored output: a dated quarantine or external archive before
   any deletion, plus a documented manifest of every move.
5. For accumulating backups, use an explicit retention tool with a dry-run/preview mode. The
   initialisation repository uses both a bounded timing-history pattern and opt-in, dry-run-first
   history pruning. Do not silently auto-delete mapping-workbook backups.

The initialisation-specific proposal to merge diagnostics across parallel economy workers does
**not** transfer directly to this repository. The relevant part is its output-contract and
classification discipline, not its `parallel_economy_merge.py` implementation.

### Recommended execution order

1. **Safety gate.** Run `git status --short`; check for active mapping or initialisation Python
   processes; do not touch `config/`, `results/`, or code while a related workflow is active.
   Preserve unrelated changes. This checkout already has user-owned edits to mapping code,
   workbooks, JSON configuration, and documentation.
2. **Create a tracked cleanup manifest.** For every candidate, record source path, replacement
   path (if any), producing script, known consumers, size, classification, and action. Update
   this document and `docs/archive_log.md` in the same commit as an actual move.
3. **Conservative quarantine batch.** After rechecking the path list, move only the
   evidence-backed orphaned tree artifacts into a dated, clearly ignored quarantine location,
   such as `results/_quarantine_YYYY-MM-DD/`. Do not use a recursive glob; resolve and verify
   every absolute source and destination path first. Do not hard-delete in this batch.
4. **Diagnostic-file design.** Build a producer/consumer inventory for the approximately 103
   diagnostic/QA CSVs. Group them by reviewer question and identify the supported primary output,
   optional detail/lineage outputs, one-off snapshots, and obsolete aliases. This is a separate
   code/output-contract task, not a file-moving task.
5. **Implement consolidation only where it is real.** Keep compatibility outputs where a script,
   notebook, dashboard, or human procedure may consume the old name. Validate with focused tests
   and a current relevant pipeline run before stopping production of an old diagnostic.
6. **Retention policy.** Treat `config/archive/` separately. Design a preview/dry-run-first
   policy (for example, retain recent backups plus periodic snapshots) and ask for confirmation
   before applying it. These are a safety net for workbook edits, not ordinary clutter.
7. **Final cleanup and handoff.** Only after the design and validation should rebuilt variants,
   copy-suffixed diagnostics, and experimental inverted-conservation folders be quarantined or
   removed. Update README links, this file, and the archive log with exact actions.

### Explicitly out of scope for the first conservative batch

- `config/outlook_mappings_master new*.xlsx` variants: one was recently an active review copy;
  a human must confirm each is no longer in use.
- Hex-named Office recovery files (`config/E0E85740`, `E2F1A260`, `6AC9DA10`, `FDC59700`, and
  any new equivalent): leave them alone. They can reappear when Excel is opened, so moving them
  has little practical benefit.
- Active result directories, current `mapping_pipeline.log`, named standalone-tool outputs, and
  the separate `inverted_conservation_variant_verification/` output.
- Broken/unused code (`build_canonical_mapping_views.py`, `unified_name_lookup.py`) until a
  dedicated code review verifies imports, tests, and intended manual use. Do not combine that
  work with output cleanup.

### Estimated scope and success criteria

- Conservative audit + quarantine + documentation: about one working day.
- Diagnostic-output contract/design and any compatible writer changes: roughly one to three
  further working days, depending on current consumers and the required pipeline verification.

The first phase is complete only when every moved item is recoverable, the manifest records the
old and new paths and reason, no active workflow was disturbed, and the generated-output folder
still has a clear current path for each routine diagnostic. The wider consolidation is complete
only when its supported output set is documented, consumers are updated or deliberately retained,
and a relevant current run verifies the new contract.

## 2026-07-27 verification pass — ready-to-quarantine vs. one blocked item

Re-checked the three tree-artifact candidates from the "conservative quarantine batch" (step 3
above) against current `codebase/` and `tests/`, and confirmed `results/common_esto/
anchor_reconciliation/` exists as the documented replacement. **These three are confirmed safe to
quarantine mechanically, no further comparison needed:**

- `results/tree_structure/anchor_diagnostics/` (10 files)
- `results/tree_structure/source_parent_anchor_MISSING_children.csv` and
  `_MISSING_parent_pairs.csv`
- `results/tree_structure/source_parent_anchor_validation_SLICE.csv` and `_SLICE_summary.csv`

### The top-level `results/missing_mapped_esto_rows/` item is NOT a clean duplicate — needs a human call

The doc above (and the "confirmed orphaned" table) classifies the top-level
`results/missing_mapped_esto_rows/` as a stale duplicate of `results/maintenance/
missing_mapped_esto_rows/`. A byte-for-byte diff of all 15 files against the maintenance/ version
shows that's only true for 6 of them — **9 files differ substantially**, e.g.:

| File | Top-level (2026-06-29) | `maintenance/` (2026-07-27, this morning) |
|---|---:|---:|
| `00APEC_2024_low_with_subtotals_missing_mapped_rows.csv` | 307,888 bytes | 201 bytes |
| `00APEC_2024_low_with_subtotals_missing_mapped_rows_audit.csv` | 528,599 bytes | 145 bytes |
| `00APEC_2025_low_with_subtotals_missing_mapped_rows.csv` | 315,811 bytes | 206 bytes |
| `00APEC_2025_low_with_subtotals_missing_mapped_rows_audit.csv` | 528,599 bytes | 145 bytes |

(plus smaller diffs in the `_commercial_services_unallocated_validation.csv`,
`_ninth_nonzero_filter_audit.csv`, and `missing_mapped_esto_rows_summary.csv` files — same
pattern, maintenance/ version much smaller/near-empty).

The `maintenance/` files are current — written by today's run of
`codebase/mapping_tools/build_missing_mapped_esto_rows.py` — while the top-level files are from a
run nearly a month prior and hold real data the current run doesn't. This means either:

1. Today's run legitimately found far fewer missing-mapped rows than the June run (a genuine
   improvement) — in which case the top-level copy really is obsolete and safe to quarantine, or
2. Something is wrong with the current run producing near-empty `missing_mapped_rows`/`_audit`
   output — in which case the top-level copy is the last good reference and should be kept, and
   the near-empty current output investigated as a possible regression.

**Do not quarantine the top-level `results/missing_mapped_esto_rows/` folder as part of the
mechanical batch above until a human (or an agent with access to explain what changed in the
pipeline between 2026-06-29 and 2026-07-27) resolves which of these two explanations is correct.**
The other three candidates in this section are unaffected by this and can proceed independently.
