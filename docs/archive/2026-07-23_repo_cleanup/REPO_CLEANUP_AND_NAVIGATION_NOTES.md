# leap_mappings — repo cleanup & navigation TODO (self-contained, for the main-PC repo)

**Generated:** 2026-07-22, on a secondary checkout, for hand-off to the main PC.

## ⚠ Read this first: this file is the ONLY thing that transfers

**This repo's changes will never be git-pushed/pulled to the main-PC repo — there is
deliberately no sync between them, to avoid risk.** That means none of the individual files
this session created or edited (`results/README.md`, `docs/workflow_inventory.md`, etc.) will
ever appear on the main PC on their own. **This single file is the entire deliverable.** It must
contain everything needed to do the equivalent cleanup/navigation work in the main-PC repo —
both "recreate this exact content at this path" items, and genuinely new audit tasks that have
to be run fresh there because they depend on that repo's own file listing, which may differ from
what was observed here (via the zip snapshot).

**How to use this file on the main PC:** work through the numbered task list immediately below,
in order. Each task either says "recreate this file" (copy the content from the numbered section
later in this document into the given path) or "audit and act" (a methodology to run against
that repo's actual current state, since I can't see it from here). Do not assume any file listed
here already exists in that repo unless the task says so explicitly.

## ⚠ Re-verification pass (2026-07-22, same day as the original audit)

After the original audit, this checkout pulled 31 new upstream commits (`git fetch` + `git pull`,
fast-forward, no conflicts) touching 41 files and ~3,150 lines — real changes to core pipeline
code, not just docs: `build_dataset_tree_structure.py` (+355 lines),
`common_esto_validation_orchestration.py` (+586 lines), `run_mapping_pipeline.py` (+69 lines),
plus smaller changes to `build_common_esto_structure.py`, `build_energy_balance_relationships.py`,
`non_expanding_rollups.py`, `parse_leap_balance_export.py`, `source_parent_anchor_validation.py`,
`target_share_allocation.py`, `apply_ninth_to_esto_conversion.py`, `convert_leap_results_to_esto.py`,
`leap_balance_export_resolver.py`, `leap_results_dashboard_balance.py`, and
`for_colleagues_export_workflow.py`. Three new standalone scripts arrived too:
`audit_nonzero_mapping_evidence.py`, `build_leap_mapping_candidates.py`,
`build_valid_nonzero_mapping_candidates.py`.

**Two things worth knowing before you act on anything below:**

1. **The pull silently restored 4 locally-deleted files.** Before the pull, this checkout had
   `config/6AC9DA10`, `config/common_esto_label_overrides.csv`, `config/outlook_mappings_master.xlsx`,
   and `config/outlook_mappings_master no ownuse.xlsx` missing from the working tree (deleted
   outside of git, presumably in preparation for extracting the zip). The fast-forward pull
   recreated the first three on disk (their content changed upstream, so git rewrote them as part
   of applying the new commits) and confirmed the fourth is now genuinely gone (upstream deleted
   it too, matching the local state). **If the main-PC repo has similar locally-deleted files in
   preparation for its own zip extraction, a `git pull` there could do the same thing** —
   silently un-delete files that were deliberately removed as prep work. Check `git status`
   before and after any pull, on either machine, for exactly this reason.
2. **I re-checked every load-bearing claim in this document against the new code**, not just
   skimmed the diff. Full detail is in section 5 (`docs/workflow_inventory.md`'s new
   "Re-verification note"), but the short version:
   - The `results/tree_structure/` double-write pattern (section 17's item 3a) is **confirmed
     still present** in the new code — not fixed by this batch of commits. This was the
     highest-risk claim to re-check (it's about exact function call sites) and it held up.
   - `common_esto_validation_orchestration.py`'s growth added 6 output files that were actually
     already in the original zip snapshot but got missed in the first documentation pass — a gap
     in the original survey, not a regression from the pull. Fixed in section 9 below.
   - The 3 new scripts are added to section 5 below.
   - Everything else checked (stage wiring, the dashboard-prototype cluster, the diverged
     `codebase/mapping_code/` duplicate, the broken `build_canonical_mapping_views.py` import,
     the orphaned `unified_name_lookup.py`) is confirmed still accurate, unchanged by the pull.

## Task checklist (do these in order)

1. **Recreate 16 files** — see sections 1–14 below for exact content and destination paths (one
   new/modified file per section: root `README.md` additions, `config/README.md`,
   `data/README.md`, `docs/README.md`, `docs/workflow_inventory.md`, 8 `results/*/README.md`
   files, `docs/repo_data_slimdown_plan.md`, `docs/results_folder_cleanup_candidates.md`,
   `docs/diagnostic_file_review_signals.md`, and the `docs/improvement_todo.md` additions).
2. **Fix the same `.gitignore` bug** — see section 18. This is a real bug (nested `results/`
   READMEs silently fail to become trackable), not just a nice-to-have; apply it before
   committing any of the recreated `results/*/README.md` files, or they won't actually get
   tracked there either.
3. **NEW — audit for single-use files and archive them** — see section 19. Not a recreate task;
   run the described audit against the main-PC repo's actual current files.
4. **NEW — audit for near-duplicate diagnostic files and reduce duplication** — see section 20.
   Same: run fresh against that repo's actual files.
5. Everything in `docs/results_folder_cleanup_candidates.md` (section 15) and
   `docs/diagnostic_file_review_signals.md` (section 16) that was flagged from the zip snapshot
   — re-verify against the main-PC repo's actual current files before acting, since that repo is
   the live one and may have moved on since the snapshot was taken.

## What this whole session was about

You asked me to look through a zip (`config data results leap mappigns.zip`) meant to replace
this repo's `config/`, `data/`, and `results/` folders, and figure out exactly what's needed to
run the pipeline vs. what's clutter — with the broader goal of reducing repo size (including
untracked parts) and making the repo easy for a newcomer (or you, returning later) to navigate.
That grew into several rounds:

1. **Extraction plan** — which files from the zip are actually required to run
   `codebase/run_mapping_pipeline.py`, vs. safe to leave out (~93% size reduction, mostly by not
   extracting `results/` at all, since it's fully regenerated).
2. **`results/` navigation** — a README in `results/` and each subfolder, since the pipeline
   produces far more files than a first-time reader needs to see at once.
3. **`codebase/` navigation** — same problem, different folder: live pipeline vs. standalone
   tools vs. legacy vs. dashboard-prototype code (flagged as out-of-scope per `AGENTS.md`) vs.
   a diverged duplicate bundle vs. at least one broken script.
4. **Cleanup candidates** — specific files/folders that look orphaned, duplicated, or stale,
   with a strong safety note since `results/` is gitignored (no git history to recover from).
5. **Diagnostic-file usefulness signals** — two rounds tracing which of the ~150+ QA/diagnostic
   files in `results/` are actually consumed by code (pipeline-internal dependency,
   standalone-tool dependency, or genuinely never read by anything) vs. which are named as
   review priorities in your own docs. Round 2 also surfaced a real correctness question (a
   double-write pattern in `results/tree_structure/`), not just clutter.
6. **Root-level scratch files, `config/`/`data/`/`docs/` in-folder READMEs.**
7. **NEW (this round) — single-use file archiving.** Section 19: a methodology plus a concrete
   starter list for identifying files/folders that look like they were created for one specific
   past task (timestamped backups, "copy"/"new"/"final" variants, ad hoc redirected logs, a
   diverged duplicate prototype bundle) and moving — never deleting — them into a clearly-named
   archive location.
8. **NEW (this round) — diagnostic-file deduplication.** Section 20: a methodology plus a
   concrete starter list of pairs/groups of diagnostic files that look like near-identical
   versions of each other (a filtered vs. unfiltered pair, a `qa_`-prefixed vs. unprefixed pair,
   a `_rebuilt` variant, three near-identical output-directory variants from repeated manual
   runs) so the genuine duplication can be resolved rather than just documented as "there are two
   of these now."

**Working agreement throughout, honored in every round:** docs-only where possible, and even the
two new "act on it" tasks (7 and 8) default to **archive/move, never delete** — nothing here
should ever be destroyed without a human confirming it first. This matters most for `results/`
and `config/archive/`, which are **gitignored** — deleting anything there is not recoverable via
git the way a tracked-file deletion would be. Root-level files (`Untitled-1.md`,
`old gent chat.txt`, `prompts 5-7.md`) are the exception: they're git-tracked, so any future
action on them is fully recoverable — but still prefer archive-move over delete as the default,
consistent with everything else in this document.

## Where each section below actually lives (or should live) in the repo

| Section in this file | Real file path | Status as of merge |
|---|---|---|
| Root README additions | `README.md` (existing file, only the new sections shown here) | Modified |
| `config/` guide | `config/README.md` | New |
| `data/` guide | `data/README.md` | Replaced (old version was stale — see note in that section) |
| `docs/` index | `docs/README.md` | New |
| `codebase/` navigation guide | `docs/workflow_inventory.md` | Rewritten |
| `results/` guide | `results/README.md` | New |
| `results/common_esto/` guide | `results/common_esto/README.md` | New |
| `results/mapping_relationships/` guide | `results/mapping_relationships/README.md` | New |
| `results/tree_structure/` guide | `results/tree_structure/README.md` | New |
| `results/maintenance/` guide | `results/maintenance/README.md` | New |
| `results/logs/` guide | `results/logs/README.md` | New |
| `results/mapping_graph_index/` guide | `results/mapping_graph_index/README.md` | New |
| `results/for_colleagues/` guide | `results/for_colleagues/README.md` | New |
| Repo data slim-down plan | `docs/repo_data_slimdown_plan.md` | New |
| Cleanup candidates | `docs/results_folder_cleanup_candidates.md` | New |
| Diagnostic file review signals | `docs/diagnostic_file_review_signals.md` | New |
| Backlog additions | `docs/improvement_todo.md` (existing file, full current content shown here) | Modified |
| `.gitignore` change (+ bug fix) | `.gitignore` | Modified — see section 18 |
| Single-use file archiving | no fixed path — new audit task | **New task, not yet run against the main-PC repo** — see section 19 |
| Diagnostic-file deduplication | no fixed path — new audit task | **New task, not yet run against the main-PC repo** — see section 20 |

**Important distinction:** sections 1–14 and 18 are "recreate this exact content" — copy/paste
verbatim into the given path. Sections 15 and 16 (cleanup candidates, diagnostic signals) were
built from a **snapshot** (the zip) and should be **re-verified**, not blindly trusted, since the
main-PC repo is the live one and may have changed since. Sections 19 and 20 are **brand new
tasks** that were never run anywhere — they need to be executed fresh against whatever the
main-PC repo actually contains right now.

**Git status as of this merge** (so you know what's new vs. modified when you sync):

```
 M .gitignore
 M README.md
 M data/README.md
 M docs/improvement_todo.md
 M docs/workflow_inventory.md
?? config/README.md
?? docs/README.md
?? docs/diagnostic_file_review_signals.md
?? docs/repo_data_slimdown_plan.md
?? docs/results_folder_cleanup_candidates.md
?? results/README.md
?? results/common_esto/README.md
?? results/for_colleagues/README.md
?? results/logs/README.md
?? results/maintenance/README.md
?? results/mapping_graph_index/README.md
?? results/mapping_relationships/README.md
?? results/tree_structure/README.md
```

None of this has been committed — it's all working-tree changes on the `master` branch, waiting
for you to review and commit when ready.

---

# 1. Root `README.md` — new sections added

The existing root `README.md` (pipeline description, layered workflow, common ESTO structure
explanation, current inputs) is unchanged except for three new sections appended before
"Suggested Improvements To The Guide":

```markdown
## Finding Your Way Around `results/`

The pipeline writes a lot into `results/`. Start with `results/README.md` — it points to the
handful of primary outputs and links to a short guide for each subfolder. See
`docs/results_folder_cleanup_candidates.md` for known clutter/orphaned files flagged for future
cleanup (not yet actioned), and `docs/repo_data_slimdown_plan.md` for which `config/`/`data/`
files are actually required to run the pipeline.

## Finding Your Way Around `codebase/`

`codebase/` mixes the live pipeline with standalone maintenance tools, a legacy refresh
workflow, dashboard-prototype code that (per `AGENTS.md`) belongs in the sibling
`leap_dashboard` repo instead, a diverged duplicate bundle, and at least one currently-broken
script. See `docs/workflow_inventory.md` for which is which before assuming a file is part of
the active pipeline just because it's under `codebase/`.

## Finding Your Way Around the Rest of the Repo

`config/README.md` and `data/README.md` explain what's required to run the pipeline vs. legacy,
right there in each folder. `docs/README.md` indexes every file under `docs/` so you don't have
to open all of them to find the one you need.
```

---

# 2. `config/README.md` (new file)

# `config/` — navigation guide

Only files directly under `config/` are git-tracked (see `.gitignore`: `!config/*` then
`config/*/`, which re-ignores every subfolder). Subfolders like `config/archive/` exist locally
but are never committed — they're either write targets (backups) or local scratch.

## Required to run the pipeline

| File | Used by |
|---|---|
| `outlook_mappings_master.xlsx` | The core editable mapping workbook — read by Stage 0, Stage 1, Stage 3, and most `mapping_tools/*` scripts. |
| `master_config.xlsx` | Stage 1's fallback workbook (`FALLBACK_WORKBOOK_PATH`). |
| `mapping_issue_exception_sets.xlsx` | Reviewed QA exceptions, read by Stage 0 and several `mapping_tools/*` scripts. |
| `source_branch_fallback_rules.csv` | Read during LEAP→ESTO conversion (`data_convert` stage). |
| `all_demand_aggregated_components.json` | Same conversion step. |
| `common_esto_label_overrides.csv` | Read in Stage 2 (`build_common_esto_structure.py`). |

## `archive/`

Write-only backup target — every script that edits `outlook_mappings_master.xlsx` copies the
previous version here first (`ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)` then
`shutil.copy2(...)`). Not read by anything, not required to pre-exist, accumulates indefinitely
with no automatic pruning (see `docs/results_folder_cleanup_candidates.md`).

## Legacy

`master_config.xlsx` above is still required (Stage 1 fallback), but its main use is the
superseded refresh path — see `docs/workflow_inventory.md` for the full legacy-vs-live trace.

## Full detail

See `docs/repo_data_slimdown_plan.md` for the complete file-by-file breakdown (including which
files are safe to leave out entirely) and `docs/workflow_inventory.md` for which scripts read
which config files.

---

# 3. `data/README.md` (replaced — old version was stale)

The version that existed before this session described a much larger set of files and workflow
scripts (`codebase/industry_workflow.py`, `full model export.xlsx`, per-sector LEAP import
templates, etc.) that no longer match the current pipeline. That old content is preserved in git
history (`git log -- data/README.md` on the machine where this was committed) if useful for
archaeology — it was not simply deleted, it was replaced with the accurate version below.

# `data/` — navigation guide

Only `data/README.md` (this file) and any `**/README.md`/`**/.gitkeep` are git-tracked (see
`.gitignore`: `data/*` then explicit exceptions). Everything else here is restored from a shared
archive/zip, not from git.

**Note:** an earlier version of this file described a much larger set of files and workflow
scripts (`codebase/industry_workflow.py`, `full model export.xlsx`, per-sector LEAP import
templates, etc.) that no longer match the current pipeline — that content is stale and available
via `git log -- data/README.md` if useful for archaeology, but don't treat it as current.

## Required to run the pipeline

| File | Used by |
|---|---|
| `00APEC_2025_low_with_subtotals.csv` | Primary ESTO source table — Stage 0, `data_convert`, Stage 3. |
| `00APEC_2024_low_with_subtotals.csv` | Secondary ESTO year, checked by Stage 0 maintenance for missing-mapped-row detection. |
| `merged_file_energy_ALL_20251106.csv` | 9th Outlook source table — Stage 0, `data_convert`, Stage 3. The single largest required input (~288 MB). |

## Not needed for this repo's pipeline

- `archive/leap balances exports/` — raw LEAP exports are owned by the sibling
  `leap_initialisation` repo; this local copy is legacy/reference only (see the root
  `README.md`'s "Current Inputs" section and `codebase/utilities/leap_balance_export_resolver.py`).
- `merged_file_energy_00_APEC_20251106.csv`, `usa_leap_balance_long.csv` — not referenced by any
  current script (the latter is only a legacy fallback in `build_dataset_tree_structure.py`).

## Full detail

See `docs/repo_data_slimdown_plan.md` for the complete file-by-file breakdown and reasoning.

---

# 4. `docs/README.md` (new file — index of `docs/`)

# `docs/` index

If you're new to this repo, read in this order: root `README.md` → `mappings_system.md` →
`guide_outlook_mappings_master.md`. Everything else here is reference material or a working
backlog, not required reading up front.

## System design and reference

| File | What it covers |
|---|---|
| [`mappings_system.md`](../../mappings_system.md) | **Start here.** How the whole mappings system works — why it's structured the way it is, pipeline stages, code entry points, output files. |
| [`guide_outlook_mappings_master.md`](../../guide_outlook_mappings_master.md) | Practical editor's guide to `config/outlook_mappings_master.xlsx` — what to put in the cells, with a rollup deep-dive. |
| [`rollup_rules_system.md`](../../rollup_rules_system.md) | How the workbook's rollup-rule sheets get consumed by Stage 1/2 — for debugging relationship outputs. |
| [`special_rules_and_design_decisions.md`](../../special_rules_and_design_decisions.md) | The decision log — rules whose correct behaviour can't be derived from source data alone. Check here before assuming odd-looking behaviour is a bug. |
| [`workflow_inventory.md`](../../workflow_inventory.md) | Navigation guide for `codebase/` — which scripts are live pipeline vs. standalone tools vs. legacy vs. dashboard-prototype (out of scope per `AGENTS.md`) vs. broken/orphaned. |
| [`QA plan.md`](../../QA%20plan.md) | The smoke-test / regression-verification plan for the pipeline. |

## Repo hygiene (this pass)

| File | What it covers |
|---|---|
| [`repo_data_slimdown_plan.md`](../../repo_data_slimdown_plan.md) | Exactly which `config/`/`data/`/`results/` files are required to run the pipeline (vs. safe to leave out), derived from tracing every input path in the code. |
| [`results_folder_cleanup_candidates.md`](../../results_folder_cleanup_candidates.md) | Files/folders that look stale, orphaned, or duplicated across `results/`, `config/`, and `codebase/` — flagged for future cleanup, nothing acted on yet. |
| [`diagnostic_file_review_signals.md`](../../diagnostic_file_review_signals.md) | Which `results/common_esto/` and `results/maintenance/` diagnostic files are named in project docs / read by other scripts / substantial in size vs. which are produced every run but referenced nowhere — decision support, not a verdict. |

See also `results/README.md` (and the `README.md` in each `results/` subfolder), `config/README.md`,
and `data/README.md` — placed directly in those folders so the guide is right there when you
open them, rather than only discoverable from here.

## Backlog

| File | What it covers |
|---|---|
| [`improvement_todo.md`](../../improvement_todo.md) | The active backlog — semantic mapping issues to resolve, the canonical-workbook migration, hierarchy validation, documentation gaps, and (as of this pass) the `results/` cleanup candidates. |

## `prompts/` and `archive/`

- `prompts/` — active or pending multi-step agent prompts (plan-first implementation tasks,
  investigation prompts). Per `AGENTS.md`: once the work a prompt describes is complete, it
  should move out of here into `archive/`. If a file's been sitting in `prompts/` a long time,
  it's worth checking whether it's actually done and just hasn't been moved yet.
- `archive/` — completed prompt packs, often bundled with their own findings/status/TODO notes
  (see `archive/common_esto_lineage_validation/` for the pattern). Historical record, not
  something to read routinely.

---

# 5. `docs/workflow_inventory.md` (rewritten — `codebase/` navigation guide)

# Workflow Inventory — `codebase/` navigation guide

Last reviewed: 2026-07-22 (re-verified after pulling 31 upstream commits the same day — see the
"Re-verification note" near the end)

`codebase/` mixes several things that look similar at a glance but aren't: the live mapping
pipeline, standalone maintenance/QA tools a researcher runs by hand, an explicitly-legacy
refresh workflow, a cluster of dashboard-prototype code that (per `AGENTS.md`) doesn't belong
in this repo at all, a diverged duplicate of two live scripts, and at least one script that is
currently broken. This guide tells you which bucket each file is in, based on actually tracing
imports and call sites (not just filenames), so you don't have to read all of it to find the one
script you need.

## Start here

`codebase/run_mapping_pipeline.py` is the only script you need to run the whole pipeline
end to end (`python codebase/run_mapping_pipeline.py`). Everything under "Live pipeline" below
is reached from it.

## Live pipeline (canonical — called by `run_mapping_pipeline.py`)

| Script | Stage |
|---|---|
| `codebase/run_mapping_pipeline.py` | Orchestrator |
| `codebase/archive/outlook_mapping_maintenance_workflow.py` | Stage 0 — maintenance/QA on the mapping workbook |
| `codebase/mapping_tools/build_energy_balance_relationships.py` | Stage 1 |
| `codebase/mapping_tools/build_common_esto_structure.py` | Stage 2 |
| `codebase/mapping_tools/parse_leap_balance_export.py` | `leap_parse` |
| `codebase/mapping_tools/convert_leap_results_to_esto.py`, `apply_ninth_to_esto_conversion.py` | `data_convert` |
| `codebase/mapping_tools/apply_common_esto_structure.py`, `build_dataset_tree_structure.py`, `common_esto_validation_orchestration.py`, `source_parent_anchor_validation.py` | Stage 3 |
| `codebase/mapping_tools/source_branch_preflight.py` | invoked from the `data_convert` LEAP conversion step |
| `codebase/mapping_tools/build_missing_mapped_esto_rows.py` | invoked from Stage 0 |
| `codebase/mapping_tools/non_expanding_rollups.py` | invoked directly from `run_mapping_pipeline.py`'s ESTO-exact-rows step |
| `codebase/mapping_tools/mapping_issue_exceptions.py`, `codebase/mapping_issue_exceptions.py` | shared library, read by Stage 0 and several other tools (note: two similarly-named files — the one under `mapping_tools/` re-exports from the top-level one) |
| `codebase/utilities/outlook_mappings_filters.py`, `codebase/utilities/leap_balance_export_resolver.py` | the only two `utilities/` modules the live pipeline actually imports |

See `results/README.md` and its subfolder READMEs for what each stage writes.

## Standalone maintenance / QA tools

Run manually by a researcher — not invoked by `run_mapping_pipeline.py`, but part of the normal
mapping-maintenance workflow (several read/write `config/outlook_mappings_master.xlsx`
directly, backing up to `config/archive/` first):

`apply_display_name_updates.py`, `apply_duplicate_mapping_removal.py`,
`apply_subtotal_mismatch_review.py`, `apply_subtotal_mismatch_source_flip.py`,
`apply_subtotal_updates.py`, `infer_subtotal_labels.py`, `build_subtotal_mismatch_review.py`,
`inverted_conservation_validation.py`, `reconcile_anchor_validation.py`,
`compile_structural_mapping_artifacts.py`, `apply_partitioned_common_esto.py`,
`check_leap_to_esto_conversion_coverage.py`, `build_no_data_mapping_rows.py`,
`update_leap_display_names.py` — all under `codebase/mapping_tools/`.

Helper modules used only by the above (not by the live pipeline): `mapping_candidate_generation.py`,
`source_rollups.py`, `structural_resolver.py`, `target_share_allocation.py`.

**Added since the first pass** (via a same-day upstream pull, 31 commits): three more
standalone, read-mostly mapping-candidate tools under `codebase/mapping_tools/`, none imported
by `run_mapping_pipeline.py`:

- `audit_nonzero_mapping_evidence.py` — read-only, notebook-safe audit checking whether proposed
  9th-source/ESTO-target pairs actually occur with non-zero values in current reference data.
  Does not edit the workbook.
- `build_leap_mapping_candidates.py` — builds copy-ready LEAP-to-9th mapping rows for verified
  candidates; writes `results/mapping_relationships/proposed_leap_combined_ninth_rows.csv`.
- `build_valid_nonzero_mapping_candidates.py` — builds copy-ready mapping rows only after the
  non-zero evidence audit above passes both axes; imports from `audit_nonzero_mapping_evidence.py`.
  This is the source of `results/mapping_relationships/proposed_ninth_pairs_to_esto_pairs_coal_products.csv`,
  which is committed to git (an exception to the "results/ is fully regenerated output" framing
  used elsewhere in this doc set — this particular file was deliberately checked in as a
  copy-ready candidate list, not left as gitignored transient output).

Top-level standalone workflows: `codebase/propagate_esto_rows_workflow.py`,
`codebase/for_colleagues_export_workflow.py` (see `results/for_colleagues/README.md`),
`codebase/regen_common_esto_comparison_fast_path_workflow.py` (fast-path rerun from cached
intermediates, skips Stages 0–2).

`codebase/functions/ninth_projection_mapping.py` is a helper used only by `build_no_data_mapping_rows.py`
and the dashboard-prototype cluster below — not by the live pipeline.

## Dashboard-prototype code — not this repo's job

`AGENTS.md` is explicit: *"Do not use this repo for LEAP dashboard implementation or dashboard
template edits. Use `C:\Users\Work\github\leap_dashboard` for LEAP dashboard work."* The
following modules build dashboard graph indices / comparison engines that duplicate what
`leap_dashboard` should own. None of them are imported by the live pipeline:

- `codebase/utilities/leap_results_dashboard_v2/` — an 11-module subpackage (`atomic_engine.py`,
  `comparison_engine.py`, `config_loader.py`, `derived_transformation_metrics.py`,
  `diagnostics.py`, `leap_loader.py`, `mapping_engine.py`, `models.py`, `output_writer.py`,
  `pathing.py`, `reference_loader.py`, `shadow_compare.py`).
- `codebase/utilities/leap_results_dashboard_balance.py`, `leap_results_dashboard_utils.py`
- `codebase/utilities/ninth_to_esto_mapping_coverage.py`
- `codebase/utilities/energy_balance_template_extractor.py` (~1800 lines; used only by the
  legacy/dashboard cluster below, not by anything live)
- `codebase/mapping_tools/build_dashboard_graph_index.py`, `build_energy_balance_graph_links.py`,
  `convert_leap_combined_esto_to_esto_first.py` — write `results/mapping_graph_index/` (see
  that folder's README)
- `codebase/mappings/canonical_mapping.py` — reads `config/ninth_pairs_to_esto_pairs.xlsx` /
  `config/leap_results_sheet_map.csv`, neither of which are among the files required to run the
  live pipeline (see `docs/repo_data_slimdown_plan.md`)

## `codebase/mapping_code/` — a diverged duplicate, not the live copy

`codebase/mapping_code/codebase/mapping_tools/build_dashboard_graph_index.py` and
`convert_leap_combined_esto_to_esto_first.py` are a self-contained "starter prototype" bundle —
its own `README_dashboard_mapping_starter.md` calls it exactly that, hardcodes a run command
against `C:\Users\Work\miniconda3\python.exe` (a different machine than this checkout), and
targets the legacy `config/leap_mappings.xlsx`. Confirmed via `diff` that these are **not**
identical to the same-named files in `codebase/mapping_tools/` — they've diverged (517 vs 522,
and 815 vs 874 lines respectively). If you need to edit either script, make sure you're editing
the `codebase/mapping_tools/` version — that's the one referenced everywhere else in the repo.

## Legacy (superseded, kept for reference only)

- `codebase/leap_mapping_refresh_workflow.py` — old refresh workflow for
  `config/leap_mappings.xlsx` / `config/master_config.xlsx`, explicitly superseded by
  `config/outlook_mappings_master.xlsx` (see root `README.md`, `AGENTS.md`). This is the sole
  entry point into the whole dashboard-prototype cluster above plus `utilities/master_config.py`.
- `codebase/utilities/master_config.py` — reader for `config/master_config.xlsx`. Used by the
  legacy chain above, and also as Stage 1's `FALLBACK_WORKBOOK_PATH` — so it's not fully dead,
  but its primary consumers are legacy.

## Broken — do not use as-is

- `codebase/utilities/build_canonical_mapping_views.py` — imports
  `codebase.scrapbook.utilities.load_augmented_reference_tables`. No `codebase/scrapbook/`
  directory exists anywhere in this repo's git history. This script cannot currently run.

## Unused / orphaned

- `codebase/functions/unified_name_lookup.py` — not imported anywhere in `codebase/`.

## Re-verification note (after pulling 31 upstream commits, same day as the first pass)

The pull touched `build_dataset_tree_structure.py` (+355 lines), `common_esto_validation_orchestration.py`
(+586 lines), `run_mapping_pipeline.py` (+69 lines), `build_common_esto_structure.py`,
`build_energy_balance_relationships.py`, `non_expanding_rollups.py`, `parse_leap_balance_export.py`,
`source_parent_anchor_validation.py`, `target_share_allocation.py`, `apply_ninth_to_esto_conversion.py`,
`convert_leap_results_to_esto.py`, `leap_balance_export_resolver.py`, `leap_results_dashboard_balance.py`,
and `for_colleagues_export_workflow.py` — i.e. real, substantial changes to core pipeline files,
not just docs/tests. Re-checked the load-bearing claims in this document against the new code:

- **Still accurate:** the Stage 0/1/2/3 wiring in `run_mapping_pipeline.py`, the live-vs-standalone
  split, the dashboard-prototype cluster, the `codebase/mapping_code/` diverged duplicate, the
  broken `build_canonical_mapping_views.py` import, and the orphaned `unified_name_lookup.py`.
- **Still accurate, directly re-checked because it was the highest-risk claim:** Stage 0
  (`archive/outlook_mapping_maintenance_workflow.py` line ~1685) still calls
  `build_dataset_tree_structure.run_tree_structure_workflow()`, and Stage 3
  (`run_mapping_pipeline.py` `run_stage_3`) still independently writes `esto_tree.csv`,
  `ninth_tree.csv`, `leap_tree.csv`, `common_esto_tree.csv`, `all_dataset_trees.csv`,
  `ninth_validation.csv`, `ninth_sector_validation.csv`, `ninth_fuel_validation.csv`,
  `leap_validation.csv` — the `results/tree_structure/` double-write pattern (backlog item 3a)
  is confirmed still present in the current code, not fixed by this batch of commits.
- **New, added above:** the three new standalone mapping-candidate tools.
- **Found stale and fixed separately:** `common_esto_validation_orchestration.py`'s 586-line
  growth added several new output files
  (`common_esto_source_frontier.csv`, `common_esto_validation_child_detail.csv`,
  `common_esto_validation_issue_patterns.csv`, `common_esto_validation_rollup_diagnosis.csv`,
  `common_esto_rollup_validation.csv`, `common_esto_rollup_validation_summary.csv`) that were
  present in the original zip snapshot but missed in the first pass at documenting
  `results/tree_structure/` — not a regression from the pull, a gap in the original survey that
  the pull prompted a re-check to catch. Fixed in `results/tree_structure/README.md` (section 9).

## Notes

- The canonical mapping pipeline is the `run_mapping_pipeline.py` path — treat everything else
  as either a manual maintenance tool (still actively used) or out-of-scope/legacy/broken per
  the buckets above.
- `AGENTS.md` references `codebase/transformation_analysis_workflow.py` as a script that exists;
  it does not currently exist under `codebase/` at any depth — that `AGENTS.md` section appears
  stale and should be corrected or removed next time someone edits that file.
- When the workbook or source data changes, run the maintenance workflow (Stage 0) before the
  main pipeline.

---

# 6. `results/README.md` (new file)

# `results/` — navigation guide

Everything in this folder is **generated output**. Nothing here should be hand-edited — if a
file looks wrong, fix the input (`config/outlook_mappings_master.xlsx`, `data/*.csv`) or the
producing script, then re-run the pipeline. The whole folder is gitignored and safe to delete;
`python codebase/run_mapping_pipeline.py` rebuilds it from scratch (see the "How this gets
built" section below).

This README and the one in each subfolder exist because the pipeline currently produces far
more files than a first-time reader needs to see at once. See
`docs/results_folder_cleanup_candidates.md` for a list of files that look stale/orphaned and
are flagged for future cleanup — nothing has been deleted yet.

## Start here

If you just want the answer — the fully mapped, comparable LEAP / 9th Outlook / ESTO dataset —
these four files are it:

| File | What it is |
|---|---|
| `common_esto/common_esto_comparison_data.csv` | The final long-format comparison table: every source row mapped onto the common ESTO structure. This is what dashboards should read. |
| `common_esto/common_esto_comparison_wide.csv` | Same data, pivoted to one column per year — easier to eyeball or drop into Excel. |
| `common_esto/common_esto_rows.csv` | The common ESTO row structure itself (which exact ESTO components got grouped together, and why). |
| `mapping_relationships/energy_balance_relationships.csv` | The row-level relationships (source → target) that everything downstream is built from — trace a mapping decision back here. |

If a total looks wrong, the QA files under `common_esto/` (prefixed `qa_`) and
`tree_structure/` are where to look next — see those folders' READMEs.

## Folder map

| Folder | Built by (pipeline stage) | Contains |
|---|---|---|
| `common_esto/` | Stage 2 (build) + Stage 3 (apply) | The final comparison data, the common-row structure, and most of the QA/diagnostic output. Start here for almost everything. |
| `mapping_relationships/` | Stage 1 + `data_convert` | Intermediate relationship tables and per-source (LEAP/9th/ESTO) conversion outputs. Mostly lineage/QA, not usually the first stop. |
| `tree_structure/` | Stage 3 | Hierarchy trees for each dataset and recursive-sum validation. Check here when a subtotal doesn't reconcile. |
| `maintenance/` | Stage 0 | QA on the mapping workbook itself (duplicates, unmapped pairs, subtotal-flag issues). Check before editing `outlook_mappings_master.xlsx`. |
| `logs/` | every pipeline run | `mapping_pipeline.log` — the tee'd console output of the last run. Check first when a run fails. |
| `mapping_graph_index/` | standalone dashboard tools, **not** the main pipeline | Graph-index tables for the LEAP comparison dashboard template. Only relevant if you're working on dashboard wiring. |
| `for_colleagues/` | standalone export script | Simplified, trimmed copies of the comparison data for sharing outside the repo. |

## How this gets built

`codebase/run_mapping_pipeline.py` runs the stages in order:

```
0  Maintenance      -> results/maintenance/
1  Relationships    -> results/mapping_relationships/energy_balance_relationships.*
2  Common structure -> results/common_esto/common_esto_rows.*
   leap_parse       -> results/mapping_relationships/raw_leap_results.csv
   data_convert     -> results/mapping_relationships/*_converted_to_esto.csv, esto_results_exact_rows.csv
3  Apply structure  -> results/common_esto/common_esto_comparison_data.csv, results/tree_structure/*
```

A handful of other scripts under `codebase/mapping_tools/` are **standalone** maintenance/QA
tools a researcher runs manually (not part of the automatic pipeline run) — each subfolder
README says which of its files come from the pipeline vs. a standalone script.

See the repo root `README.md` for the full pipeline description and `docs/mappings_system.md`
for the design rationale.

---

# 7. `results/common_esto/README.md` (new file)

# `results/common_esto/`

Built by Stage 2 (`build_common_esto_structure.py`, structure) and Stage 3
(`apply_common_esto_structure.py`, apply-to-data) of `run_mapping_pipeline.py`, plus a few
standalone maintenance/validation tools. This is the folder with the actual answer in it —
start here before `mapping_relationships/` or `tree_structure/`.

## Primary — read these first

| File | Purpose |
|---|---|
| `common_esto_comparison_data.csv` | **The final output.** Every LEAP/9th/ESTO row mapped onto the common structure, long format. (Written as `*_needs_mapping_review.csv` instead if Stage 3 QA errors block the run — that's a signal something upstream needs fixing before this is trustworthy.) |
| `common_esto_comparison_wide.csv` | Same data, one column per year. |
| `common_esto_rows.csv` / `common_esto_rows.xlsx` | The common ESTO row structure: which exact ESTO flow/product components got grouped into each common row, and why (graph-partitioned so a source aggregate is never split). |
| `esto_to_common_esto_map.csv` | Lookup: exact ESTO (flow, product) pair → its common row. |
| `common_esto_output_status.csv` | Manifest of this run's outputs (also gains validation/anchor status rows once Stage 3's validation step runs). |

## QA / diagnostics (Stage 2 + Stage 3, prefixed `qa_`)

These explain *why* the structure or comparison data looks the way it does. Grouped roughly by
what they answer:

- **Is anything missing or duplicated?** `qa_common_esto_components_missing_from_structure.csv`, `qa_common_esto_duplicate_components.csv`, `qa_common_esto_source_rows_missing_common_map.csv` → `common_esto_source_rows_missing_common_map.csv`
- **Did a source aggregate get split (the thing the whole design avoids)?** `qa_common_esto_source_aggregates_split.csv`, `qa_common_esto_rollup_explanations.csv`, `qa_common_esto_non_expanding_rollups.csv`, `qa_common_esto_non_expanding_frontier_check.csv`
- **Coverage gaps that still need a mapping decision** (see `docs/improvement_todo.md` §1 for the recommended review order): `qa_common_esto_unresolved_partial_coverage.csv`, `qa_common_esto_structural_partial_coverage.csv`, `qa_common_esto_partial_coverage_components_without_relevance.csv`, `qa_common_esto_existing_components_without_relevance.csv`, `qa_nonzero_unmapped_leap_branches.csv`
- **Copy-ready mapping candidates** (review-only, never auto-applied): `qa_common_esto_partial_coverage_mapping_candidates.csv`, `qa_nonzero_unmapped_leap_branch_mapping_candidates.csv`, `highly_recommended_mapping_candidates.csv`
- **Did totals survive the mapping?** `common_esto_total_check.csv` / `qa_common_esto_total_check.csv`, `common_esto_source_coverage_check.csv`
- **Axis partitioning internals**: `qa_common_esto_product_axis_partitions.csv`, `qa_common_esto_flow_axis_partitions.csv`, `qa_common_esto_product_intersections_resolved.csv`, `qa_common_esto_flow_intersections_resolved.csv`, `qa_common_esto_axis_partition_skipped_broad_rows.csv`, `qa_common_esto_suppressed_graph_edges.csv`, `qa_common_esto_excluded_components.csv`, `qa_common_esto_structure_summary.csv`

## `diagnostics/`

Deeper trace-level output for "broad" or intersecting common rows (rows spanning unusually
many components) — pruned components, relevance scoring, intersecting axis groups. Only worth
opening when a `qa_*` file above points you here.

Not sure which of the many `qa_*`/`diagnostics/` files above are actually worth reading vs.
which are produced every run but never referenced by anything? See
`docs/diagnostic_file_review_signals.md` — several of the largest files in this folder
(`diagnostics/broad_common_row_affected_output.csv` at 17.5 MB in the sampled run,
`qa_common_esto_product_intersections_resolved.csv` at 4 MB) are flagged there as never named
in any review doc and never read by another script.

## `structural_artifacts/`, `partitioned_application/`, `partition_cache/`, `economy_scoped/`

Outputs of **standalone** tools, not the main pipeline run:

- `structural_artifacts/` — `compile_structural_mapping_artifacts.py`: value-free structural membership only (no numeric data), used as a lighter-weight mapping reference.
- `partitioned_application/`, `partition_cache/leap/` — `apply_partitioned_common_esto.py`: applies the compiled structure partition-by-partition for large/slow reruns.
- `economy_scoped/<economy_id>/` — `regen_common_esto_comparison_fast_path_workflow.py`: fast-path regeneration for a single economy, skipping Stages 0–2.

## `anchor_reconciliation/`, `anchor_contribution_breakdown/`, `inverted_conservation/`

Outputs of standalone validation tools that check totals a different way than Stage 3's
built-in checks:

- `anchor_reconciliation/`, `anchor_contribution_breakdown/` — `reconcile_anchor_validation.py`. This is the **current** anchor-reconciliation method. (`results/tree_structure/anchor_diagnostics/` is an older, no-longer-produced version of a similar check — see `docs/results_folder_cleanup_candidates.md`.)
- `inverted_conservation/` — `inverted_conservation_validation.py`: validates conservation for the direction where LEAP is the *target* system, projected through Common ESTO rows.

Note: `inverted_conservation.building/` and `inverted_conservation_variant_verification/` (if
present) are extra output-directory variants from manual re-runs of the same standalone script
with a different `output_dir` argument, not distinct pipeline stages.

---

# 8. `results/mapping_relationships/README.md` (new file)

# `results/mapping_relationships/`

Built by Stage 1 (`build_energy_balance_relationships.py`) and the `leap_parse` /
`data_convert` steps of `run_mapping_pipeline.py`. This is the "row-level" layer: relationships
and per-source conversions, before they get grouped into the common ESTO structure
(`results/common_esto/`).

## Primary

| File | Purpose |
|---|---|
| `energy_balance_relationships.csv` / `.xlsx` | The core relationship table read from the mapping workbooks — every maintained source→target row, one row per `use_case`. This is what Stage 2/3 and most downstream tools consume. |
| `relationship_catalogue_6_col.csv` | The same relationships, compacted to 6 key columns — easier to skim or diff. |

## Per-source conversion outputs (`data_convert` step)

| File | Purpose |
|---|---|
| `raw_leap_results.csv` | Raw LEAP balance exports parsed to long format (`leap_parse` step). |
| `leap_results_converted_to_esto.csv` | LEAP rows converted onto ESTO-style flow/product rows. |
| `leap_source_rollup_audit.csv`, `leap_source_to_esto_component_lineage.csv` | Audit trail / lineage for the LEAP→ESTO conversion. |
| `leap_source_branch_fallback_audit.csv`, `leap_all_demand_aggregated_overlap_warnings.csv` | From the source-branch fallback preflight — flags interim-branch substitutions and "all demand aggregated" overlaps. |
| `ninth_results_converted_to_esto.csv`, `ninth_source_to_esto_component_lineage.csv` | Same conversion/lineage pattern for 9th Outlook rows. |
| `esto_results_exact_rows.csv` | ESTO's own non-subtotal rows prepared as long-format rows (plus derived non-expanding subtotal rows), for comparison alongside the two conversions above. |

## QA (Stage 1)

Duplicate/coverage/gap checks on the relationship build itself: `coverage_exclusions.csv`,
`esto_combined_rows.csv`, `common_esto_overrides.csv`, `qa_unknown_esto_target_flows.csv`,
`qa_unknown_ninth_target_flows.csv`, `non_expanding_rollups.csv`,
`qa_non_expanding_rollup_unresolved.csv`, `leap_sources_without_esto_target.csv`,
`esto_targets_without_leap_source.csv`, `missing_dataset_pairs_by_use_case.csv`,
`not_considered_esto_rows.csv`, `leap_to_esto_duplicate_source_pairs*.csv`,
`leap_to_esto_duplicate_target_pairs*.csv`,
`one_to_many_mappings_without_allocation_or_combined_target.csv`,
`leap_to_esto_parent_child_risks.csv`, `leap_to_esto_coverage_summary.csv`,
`leap_to_esto_excluded_source_audit.csv`.

Unsure which of the QA files above are worth reading vs. rarely opened? See
`docs/diagnostic_file_review_signals.md` (Round 2) — most of the per-name QA files
(`qa_unknown_esto_target_flows.csv`, the `leap_to_esto_duplicate_*` pairs, `*_audit.csv`,
`*_lineage.csv`, etc.) are never read back by any script and not yet named in
`docs/improvement_todo.md`, though their naming suggests they're meant as review checkpoints.

## Standalone tools (not part of the main pipeline run)

- `leap_to_esto_coverage/` — `check_leap_to_esto_conversion_coverage.py`: audits included relationships against raw LEAP exports and an optional expected-ESTO-universe file.
- `no_data_rows_*.csv` — `build_no_data_mapping_rows.py`: flags mapping rows whose key pairs have no non-zero value anywhere in the source data.
- `proposed_leap_combined_ninth_rows.csv` — `build_leap_mapping_candidates.py`: copy-ready LEAP-to-9th mapping rows for verified candidates.
- `proposed_ninth_pairs_to_esto_pairs_coal_products.csv` — `build_valid_nonzero_mapping_candidates.py`: copy-ready mapping rows after `audit_nonzero_mapping_evidence.py` confirms non-zero evidence on both axes. **This one is git-committed**, unlike almost everything else in `results/` — a deliberate exception, not an oversight.

*(Section added 2026-07-22 — these three tools/outputs arrived via a same-day upstream pull, not present in the original zip snapshot this doc set was first built from.)*

## `economy_scoped/02BD/`

A single-economy (`02BD` = Brunei Darussalam) mirror of `raw_leap_results.csv`,
`leap_results_converted_to_esto.csv`, and `leap_source_rollup_audit.csv` — written by
`regen_common_esto_comparison_fast_path_workflow.py` when it regenerates comparison outputs for
one economy without rerunning the full pipeline. The matching `results/common_esto/economy_scoped/02BD/`
folder holds that tool's downstream outputs. This is **intentional narrow-scope output, not
accidental duplication** — but if you're not using the fast-path regen tool, ignore this folder;
the full, all-economy files above are the ones the main pipeline produces.

*(Added 2026-07-22, Round 3 of the diagnostic audit — a full filename-collision sweep across the
zip snapshot found this and confirmed it's intentional, not accidental duplication.)*

---

# 9. `results/tree_structure/README.md` (new file)

# `results/tree_structure/`

Built by Stage 3 of `run_mapping_pipeline.py`. Holds each dataset's hierarchy (parent/child
structure) and the recursive-sum validations that check whether parent totals actually equal
the sum of their children. Check here when a subtotal in the comparison data doesn't reconcile.

## Trees

| File | Purpose |
|---|---|
| `esto_tree.csv`, `ninth_tree.csv`, `leap_tree.csv`, `common_esto_tree.csv` | Per-dataset structural hierarchy (dataset/axis/code/parent_code). |
| `all_dataset_trees.csv` | All four trees concatenated — the canonical hierarchy source other validations read from. |

## Validation

| File | Purpose |
|---|---|
| `ninth_validation.csv`, `ninth_sector_validation.csv`, `ninth_fuel_validation.csv`, `leap_validation.csv` | Recursive-sum checks per source hierarchy (does a parent equal the sum of its children in the *raw source* data, before any mapping). |
| `common_esto_validation.csv` / `common_esto_validation_summary.csv` | Recursive-sum mismatches within the Common ESTO structure itself, and the summary of that run. |
| `common_esto_validation_by_year.csv`, `common_esto_validation_totals.csv` | Year-by-year and totals breakdowns of the Common ESTO validation. |
| `common_esto_validation_child_detail.csv`, `common_esto_validation_issue_patterns.csv`, `common_esto_validation_rollup_diagnosis.csv` | Deeper detail behind the validation mismatches — per-child breakdown, recurring issue-pattern grouping, and rollup-cause diagnosis, all from `common_esto_validation_orchestration.py`. |
| `common_esto_source_frontier.csv` | The non-overlapping comparison frontier used as the basis for validation (which rows may be summed together without double-counting). |
| `common_esto_rollup_validation.csv` / `common_esto_rollup_validation_summary.csv` | Validates the rollup rules themselves (not just the resulting totals) against their contributor rows. |
| `source_parent_anchor_validation.csv` / `_summary.csv` | Checks converted (mapped) totals against the original raw source parent totals — the main defense against a mapping silently changing a total. |

*(Added 2026-07-22 after a same-day upstream pull grew `common_esto_validation_orchestration.py`
by 586 lines — these six files were present in the original zip snapshot but missed in the first
documentation pass, not a new addition from the pull itself. See section 5's "Re-verification
note".)*

## Also present but not from the current pipeline run

`esto_validation.csv` and `common_esto_non_esto_parent_child_edges.csv` are written only when
`build_dataset_tree_structure.py` is run directly as its own script (`python -m
codebase.mapping_tools.build_dataset_tree_structure`), not by `run_mapping_pipeline.py`'s Stage
3 (which calls the same builder/validator functions but writes the file set above instead). If
you see these, they're from a manual standalone run, not the last full pipeline run.

See `docs/results_folder_cleanup_candidates.md` for files in this folder that look orphaned —
i.e. present in older result sets but not written by any current script (an `anchor_diagnostics/`
subfolder, `source_parent_anchor_MISSING_*.csv`, `*_SLICE*.csv`, and `*_baseline_*.csv` files).

**⚠ Double-write pattern:** `esto_tree.csv`, `ninth_tree.csv`, `leap_tree.csv`,
`common_esto_tree.csv`, `ninth_validation.csv`, `leap_validation.csv`, and
`common_esto_validation.csv` are each written twice per full pipeline run — once by Stage 0
(via `build_dataset_tree_structure.run_tree_structure_workflow()`) and again by Stage 3, which
overwrites them with its own version. In a full run Stage 3's version is what you end up with,
but a partial run that stops after Stage 0 leaves Stage 0's version in place with no marker that
it isn't the Stage 3 version. See `docs/diagnostic_file_review_signals.md` (Round 2) for detail
— this needs a decision, not just a cleanup pass.

Also see that same doc for which files here are genuine human-review checkpoints (the
`common_esto_validation_*` and `source_parent_anchor_validation*` files — never read back by
code, but that's expected, not a sign they're unused) vs. which are never read by anything and
not yet named as a review priority (`common_esto_tree.csv`, `ninth_sector_validation.csv`).

---

# 10. `results/maintenance/README.md` (new file)

# `results/maintenance/`

Built by Stage 0 (`codebase/archive/outlook_mapping_maintenance_workflow.py`) plus a few
standalone review tools. This is QA on the **mapping workbook itself**
(`config/outlook_mappings_master.xlsx`) — check here before editing mappings, not after.

## Primary — start here

| File | Purpose |
|---|---|
| `maintenance_summary.csv` | Compact row-count/status summary across all Stage 0 + tree-structure QA outputs — the one file to check first after a maintenance run. |

## Mapping-quality QA (Stage 0)

| File | Purpose |
|---|---|
| `duplicate_mappings.csv` | Exact-duplicate active mapping rows. |
| `many_to_many_conflicts.csv` / `_allowed_matched.csv` | Many-to-many mapping conflicts, split into unresolved vs. reviewed-and-allowed. |
| `leap_source_presence_conflicts.csv` / `_allowed_matched.csv` | LEAP sector/fuel pairs active on only one of `leap_combined_esto` / `leap_combined_ninth` (see `AGENTS.md` — this asymmetry is often deliberate, not a bug). |
| `crosswalk_target_conflicts.csv` / `_allowed_matched.csv` | 9th↔ESTO crosswalk target conflicts. |
| `unmapped_nonzero_esto_pairs.csv` / `_allowed_matched.csv` | ESTO (flow, product) pairs with real data but no active mapping row. |
| `unmapped_nonzero_ninth_pairs.csv` / `_allowed_matched.csv` | Same, for 9th Outlook (sector, fuel) pairs. |
| `subtotal_mismatches.csv` / `_allowed_matched.csv` | Leaf LEAP source mapped to an aggregate target outside the allowlist ("M6 rule"). |
| `subtotal_label_overrides_stale.csv` | Subtotal label overrides that no longer match current data — candidates to remove from the workbook. |
| `cardinality_leap_esto.csv`, `cardinality_leap_ninth.csv`, `cardinality_ninth_esto.csv` | Cardinality of each mapping direction — how many-to-many each pairing actually is. |
| `display_names_qa.csv`, `display_names_proposed_updates.csv` | Display-name QA and proposed fixes (from `update_leap_display_names.py`, invoked as part of Stage 0). Never auto-applied to the workbook — review then run `apply_display_name_updates.py`. |

## `missing_mapped_esto_rows/`

Built by `build_missing_mapped_esto_rows.py` (called from Stage 0). One
`<esto_source>_missing_mapped_rows.csv` / `_audit.csv` pair per ESTO source-CSV vintage
(currently `00APEC_2024` and `00APEC_2025`), plus `missing_mapped_esto_rows_summary.csv`.
Paste-ready proposed ESTO rows — never edits source data directly.

**Note:** there is also a top-level `results/missing_mapped_esto_rows/` folder (outside
`maintenance/`) in some result sets. That is a stale duplicate from an earlier code path — the
current script always writes under `results/maintenance/missing_mapped_esto_rows/`. See
`docs/results_folder_cleanup_candidates.md`.

## Standalone review tools (not run automatically by Stage 0)

- `subtotal_mismatch_suggested_improvements.csv` — `build_subtotal_mismatch_review.py`: proposed subtotal-flag fixes for review. Apply with `apply_subtotal_mismatch_review.py` / `apply_subtotal_mismatch_source_flip.py`.
- `subtotal_draft_esto_pairs.csv`, `subtotal_draft_ninth_pairs.csv`, `subtotal_draft_leap_pairs.csv`, `rollup_consistency.csv` — `infer_subtotal_labels.py`: draft current-vs-proposed subtotal labels derived from the structural tree, plus a rollup-rule consistency check.

Several `apply_*.py` scripts (`apply_display_name_updates.py`, `apply_duplicate_mapping_removal.py`,
`apply_subtotal_mismatch_review.py`, `apply_subtotal_mismatch_source_flip.py`,
`apply_subtotal_updates.py`) **read** the review files above and write their approved changes
directly into `config/outlook_mappings_master.xlsx` (backing up the previous version to
`config/archive/` first) — they don't write anything back into this folder.

Unsure which of these are worth reading vs. rarely opened? See
`docs/diagnostic_file_review_signals.md` — `unmapped_ninth_pairs.csv` and `unmapped_esto_pairs.csv`
(the un-filtered counterparts of the documented `unmapped_nonzero_*_pairs.csv` files) and
`subtotal_mismatches_including_exceptions.csv` are flagged there as substantial but never named
in any review doc.

## `logs/`

Ad hoc run logs from manual maintenance/validation invocations (anchor validation, structural
compilation, inverted-conservation reruns, etc.) — distinct from `results/logs/`, which only
holds the main pipeline's tee'd log. Useful for debugging a specific past run; not something to
read routinely.

---

# 11. `results/logs/README.md` (new file)

# `results/logs/`

| File | Purpose |
|---|---|
| `mapping_pipeline.log` | Tee'd console output of the **last** `run_mapping_pipeline.py` run (overwritten each run, via `_TeeWriter` in `run_mapping_pipeline.py`). Check this first when a pipeline run fails or produces unexpected output — it has every stage's printed diagnostics in one place. |

Any other, timestamped log files you may see here (`mapping_pipeline_<timestamp>.log`,
`mapping_pipeline_codex_*`, `stage_runs/*`, `*.pid`, `*.ps1`) are leftovers from ad hoc/manual
terminal invocations during earlier development, not something the current code writes as a
matter of course. See `docs/results_folder_cleanup_candidates.md`.

---

# 12. `results/mapping_graph_index/README.md` (new file)

# `results/mapping_graph_index/`

**Not produced by the main pipeline run** (`run_mapping_pipeline.py` never writes here). These
are outputs of standalone dashboard-mapping prototype tools — only relevant if you're working
on dashboard graph-ID wiring, not for the core LEAP/ESTO/9th mapping workflow.

| File | Producing script | Purpose |
|---|---|---|
| `dashboard_graph_index.csv`, `dashboard_graph_flow_index.csv`, `dashboard_graph_product_index.csv`, `dashboard_graph_flow_product_index.csv` | `build_dashboard_graph_index.py` | Graph IDs and index tables built from the LEAP comparison dashboard template. |
| `leap_comparison_dashboard_template_v3_with_graph_ids.json` | same | Graph-ID-stamped copy of the dashboard template (original left untouched). |
| `esto_first_mapping_candidates_dashboard.csv` / `.xlsx` | `convert_leap_combined_esto_to_esto_first.py` | ESTO-first mapping candidate table converted from `leap_combined_esto`. |
| `energy_balance_graph_links.csv` | `build_energy_balance_graph_links.py` | Product-aware dashboard graph links, built from `energy_balance_relationships.csv`. |
| `dashboard_chart_relationships.csv`, `dashboard_relationships_not_used_by_template.csv`, `dashboard_template_flows_without_mapping.csv`, `dashboard_duplicate_source_relationships.csv`, `dashboard_duplicate_target_relationships.csv`, `dashboard_parent_child_risks.csv` | `build_energy_balance_graph_links.py` / `convert_leap_combined_esto_to_esto_first.py` | QA for the dashboard mapping conversion (same filenames get overwritten by whichever script last ran). |

See `codebase/mapping_code/README_dashboard_mapping_starter.md` for the fuller design notes on
this dashboard-graph-index prototype.

---

# 13. `results/for_colleagues/README.md` (new file)

# `results/for_colleagues/`

Not part of the main pipeline run. Built by `codebase/for_colleagues_export_workflow.py` as a
manual step, to produce simplified, trimmed copies of the comparison data safe to share outside
the repo (e.g. by email or a shared drive).

| File | Purpose |
|---|---|
| `common_esto_comparison_wide.csv` | Copy of the final wide Common ESTO comparison output. |
| `source_pair_to_common_row.csv` | Simplified source-to-common membership file, trimmed to the useful review columns (`comparison_scope`, `source_system`, `source_flow`, `source_product`, `common_flow`, `common_product`, `common_row_is_subtotal`, `source_row_is_subtotal`). |

Re-run `codebase/for_colleagues_export_workflow.py` after a pipeline run to refresh these.

---

# 14. `docs/repo_data_slimdown_plan.md` (new file)

# Repo data slim-down plan (config / data / results)

Source: `config data results leap mappigns.zip` (repo root), 485 entries, ~4.9 GB uncompressed.
Goal: extract only what `codebase/run_mapping_pipeline.py` (Stages 0, 1, 2, `leap_parse`,
`data_convert`, 3) and its Stage 0 maintenance workflow actually read as *inputs*. Everything
else in `results/` is a regenerated **output** of running the pipeline, so almost none of it
needs to be extracted at all.

Traced by reading `codebase/run_mapping_pipeline.py` and the modules it imports
(`build_energy_balance_relationships.py`, `build_common_esto_structure.py`,
`apply_common_esto_structure.py`, `convert_leap_results_to_esto.py`,
`apply_ninth_to_esto_conversion.py`, `build_dataset_tree_structure.py`,
`codebase/archive/outlook_mapping_maintenance_workflow.py`, `mapping_issue_exceptions.py`,
`source_branch_preflight.py`), plus grepping the rest of `codebase/` for every other file named
in the zip to confirm it's actually referenced somewhere.

## Bottom line

| Folder | Zip size | Needed for main workflow | Needed size |
|---|---|---|---|
| `config/` | ~20.6 MB | 6 files + 1 empty dir | ~1.45 MB |
| `data/` | ~399.7 MB | 3 files | ~340.9 MB |
| `results/` | ~4,494.9 MB | folder skeleton only, **zero files** | 0 MB |
| **Total** | **~4.9 GB** | | **~342 MB (~93% reduction)** |

`results/` is entirely pipeline output. Every script that writes into it creates its output
directories with `mkdir(parents=True, exist_ok=True)` before writing, so none of the ~350
result files in the zip need to be extracted for the pipeline to run — a clean run from Stage 0
through Stage 3 regenerates all of it. Extract empty `results/` subfolders only if you want the
working tree to look pre-populated; it isn't required.

---

## config/ — extract these files

| File | Why it's required |
|---|---|
| `config/outlook_mappings_master.xlsx` | The core editable mapping workbook. Read by Stage 0, Stage 1, Stage 3, and most `mapping_tools/*` scripts. |
| `config/master_config.xlsx` | `FALLBACK_WORKBOOK_PATH` in `build_energy_balance_relationships.py` (Stage 1). |
| `config/mapping_issue_exception_sets.xlsx` | `EXCEPTION_WORKBOOK_PATH` in `codebase/mapping_issue_exceptions.py`, used by Stage 0 maintenance and several `mapping_tools/*` scripts. |
| `config/source_branch_fallback_rules.csv` | `SOURCE_BRANCH_FALLBACK_RULES_PATH`, read during LEAP→ESTO conversion (`data_convert` stage). |
| `config/all_demand_aggregated_components.json` | `ALL_DEMAND_COMPONENTS_PATH`, same conversion step. |
| `config/common_esto_label_overrides.csv` | `COMMON_ESTO_LABEL_OVERRIDES_PATH`, read in Stage 2 (`build_common_esto_structure.py`). |

## config/ — extract as an empty folder only (no files)

| Folder | Why |
|---|---|
| `config/archive/` | Only used as a **write** target (`ARCHIVE_DIR`) by maintenance scripts (`apply_display_name_updates.py`, `apply_duplicate_mapping_removal.py`, `apply_subtotal_mismatch_review.py`, `apply_subtotal_mismatch_source_flip.py`, `apply_subtotal_updates.py`, Stage 0) when they back up the workbook before editing it. None of the ~80 archived `.xlsx` snapshots in the zip (`outlook_mappings_master.before_*`, `.maintenance_run_*`, etc.) are read by anything — they're historical backups only. Safe to leave out entirely; a re-run will just start a fresh archive history.

## config/ — not needed at all (unreferenced anywhere in `codebase/`)

Confirmed via grep across every `.py` file — none of these paths appear as a load target:

- `config/subtotal_labels/subtotal_labels.csv` (and the `config/subtotal_labels/` folder)
- `config/leap_results_expected_sheets.json`
- `config/mapping_coverage_gaps.csv`
- `config/missing_zero_branch_mapping_candidates.xlsx`
- `config/esto_external_definition_authority_working_set.xlsx` (a copy also sits unused in `config/archive/`)
- `config/inverted_conservation_target_aliases.json` / `config/inverted_conservation_target_variants.json` — used only by `inverted_conservation_validation.py`, which is a standalone QA script, not imported by `run_mapping_pipeline.py`. Skip unless you plan to run that check specifically.
- `config/E0E85740`, `config/E2F1A260`, `config/6AC9DA10` — orphaned binary blobs (zip/xlsx signature, hex filenames, likely Office crash-recovery temp files). Not referenced anywhere. Safe to drop.
- `config/outlook_mappings_master no ownuse.xlsx` — a one-off variant, not a script input.

---

## data/ — extract these files

| File | Why it's required |
|---|---|
| `data/00APEC_2025_low_with_subtotals.csv` | Primary ESTO source table (`ESTO_CSV_PATH`) — Stage 0, `data_convert`, Stage 3. |
| `data/00APEC_2024_low_with_subtotals.csv` | Secondary ESTO year checked by Stage 0 maintenance (`ESTO_SOURCE_DATA_PATHS`) for missing-mapped-row detection. |
| `data/merged_file_energy_ALL_20251106.csv` | 9th Outlook source table (`NINTH_CSV_PATH`) — Stage 0, `data_convert`, Stage 3. This is the single largest required input (~288 MB). |

## data/ — not needed

- `data/archive/leap balances exports/...` (all of it, including `02_BD` and `20_USA` subfolders) — per `README.md` and `leap_balance_export_resolver.py`, raw LEAP exports are owned by the sibling `leap_initialisation` repo; this local copy is explicitly "legacy/reference only and is not selected by the pipeline."
- `data/merged_file_energy_00_APEC_20251106.csv` — not referenced anywhere in `codebase/`.
- `data/usa_leap_balance_long.csv` — only a legacy fallback (`LEGACY_LEAP_DATA_PATH`) used by `build_dataset_tree_structure.py` if the regenerated `results/mapping_relationships/raw_leap_results.csv` is missing. Not needed if the pipeline is run end-to-end (Stage `leap_parse` produces that file from the sibling repo's exports).
- `data/README.md` — documentation only, not a script input (harmless to keep if you want the notes, but not required for the pipeline to run).

---

## results/ — extract as empty folder skeleton only (no files needed)

Every file under `results/` in the zip (`common_esto/`, `mapping_relationships/`, `tree_structure/`,
`maintenance/`, `logs/`, `mapping_graph_index/`, `for_colleagues/`, and the duplicate top-level
`missing_mapped_esto_rows/`) is produced by running `codebase/run_mapping_pipeline.py`. None of
it is read as an input by any pipeline stage except within the same run (e.g. Stage `leap_parse`
writes `raw_leap_results.csv`, which `data_convert`/Stage 3 then read back — both steps run in
the same pipeline invocation). If you extract nothing under `results/`, a full pipeline run
(`python codebase/run_mapping_pipeline.py`) recreates all of it, including the ~630 MB and
~1.46 GB single files (`results/mapping_relationships/ninth_source_to_esto_component_lineage.csv`,
`results/tree_structure/source_parent_anchor_validation.csv`) that account for most of the zip's
4.5 GB `results/` weight.

If you want a pre-populated working tree without a full pipeline re-run (e.g. to inspect existing
outputs immediately), the smallest useful subset would be just the primary comparison outputs
rather than logs/diagnostics/backups:

- `results/common_esto/common_esto_comparison_data.csv`
- `results/common_esto/common_esto_rows.csv`
- `results/mapping_relationships/energy_balance_relationships.csv`

...but this is optional convenience, not a workflow requirement — recommend skipping entirely
for the repo slim-down goal.

---

## Auto-created folders — confirmed

Every folder this plan says to leave empty (`config/archive/`, all of `results/` and its
subfolders) is created on demand by the code itself, via `.mkdir(parents=True, exist_ok=True)`
immediately before the relevant write (checked across all 88 `mkdir` call sites in `codebase/`).
You do not need to pre-create any of these directories — a fresh clone with just the required
`config/` files and `data/` files, and no `results/` folder at all, is sufficient; running
`python codebase/run_mapping_pipeline.py` builds the rest. Only `config/` and `data/` themselves
need to genuinely pre-exist with content, since those are read, not written.

## Summary of clutter to leave out of the repo entirely

- `config/archive/` contents — ~80 historical `.xlsx` backup snapshots (keep the empty folder only).
- The 6 orphaned/unreferenced `config/` files listed above, including 3 unidentified hex-named binary blobs.
- `data/archive/leap balances exports/` — owned by the sibling `leap_initialisation` repo, not this one.
- `data/merged_file_energy_00_APEC_20251106.csv`, `data/usa_leap_balance_long.csv` — unused/legacy.
- All of `results/` (~4.5 GB) — fully regenerated by the pipeline; extracting it just to delete it again on the next run is pure waste.

---

# 15. `docs/results_folder_cleanup_candidates.md` (new file)

# `results/` cleanup candidates (not yet actioned)

**Status:** observations only. Nothing listed here has been deleted, moved, or modified. This
is the output of a docs-only navigation pass (see `results/README.md` and the per-subfolder
READMEs) — cleanup itself is a separate, deliberately deferred decision.

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
suffixes) even though I didn't exhaustively verify every one.

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
| `results/logs/mapping_pipeline_<timestamp>*.log`, `mapping_pipeline_codex_*`, `mapping_pipeline_rollup_tree_nodes_*`, `mapping_pipeline_stage*_codex_*`, `*.pid`, `*.pid.txt`, `run_mapping_pipeline_*.ps1`, `stdin_pipe_test.*`, `stage_runs/*` | Only `results/logs/mapping_pipeline.log` (no timestamp) is written by current code (`run_mapping_pipeline.py`'s `_PIPELINE_LOG_PATH`). The rest look like manually redirected output from ad hoc terminal sessions during earlier development — useful as history, not as an ongoing pattern. |
| `results/maintenance/logs/*` (`anchor_validation_yearslice_*`, `compile_structural_*`, `inverted_conservation_rerun_*`, `pipeline_1_2_dataconvert_3_*`, `stage0_maintenance_*`) | Same category — manual run logs, not from an automatic tee like `results/logs/mapping_pipeline.log`. |
| `results/common_esto/common_esto_comparison_wide_rebuilt.csv`, `qa_common_esto_partial_coverage_mapping_candidates_rebuilt.csv` | "`_rebuilt`" variants of files that already exist without that suffix — likely from a manual rebuild/comparison run, not a distinct current output name. |
| `results/common_esto/configurable_scopes_stage2.std{out,err}.log`, `configurable_scopes_stage3.std{out,err}.log` | Ad hoc redirected output from a manual run with custom comparison scopes, not a named pipeline output. |
| `config/archive/*.xlsx` (~80 files: `outlook_mappings_master.before_*`, `.maintenance_run_*`, `outlook_mappings_master - Copy.xlsx`, `... backup.xlsx`, `... backuip 207.xlsx`, etc.) | Legitimate backups (each is written by an `ARCHIVE_DIR.mkdir(...)` + `shutil.copy2(...)` call before a workbook edit), but they accumulate indefinitely with no pruning. Worth a retention policy (e.g. keep last N, or keep one per month) rather than deleting outright — these are the one category here that's a genuine safety net, not clutter, so treat with more caution than the rest of this list. |
| `config/E0E85740`, `config/E2F1A260`, `config/6AC9DA10` | Orphaned binary blobs with hex filenames (zip/xlsx signature) — look like Office crash-recovery temp files. Not referenced anywhere. |
| `results/common_esto/inverted_conservation.building/` | **Upgraded from "likely clutter" to a stronger candidate** (Round 3 of the diagnostic audit): `inverted_conservation_summary.csv` inside this folder is byte-size-identical (6,784 B) to the one in `results/common_esto/inverted_conservation/` — strong evidence this is a true redundant duplicate from a repeated manual run with a typo'd/experimental `output_dir`, not a meaningfully different variant. Compare with `inverted_conservation_variant_verification/`, which is a different size and plausibly a genuinely distinct run. |

## `codebase/` findings (from the follow-up codebase/ navigation pass)

Not `results/` files, but the same "stale/diverged, not obviously distinguishable from the live
version" problem, so recorded here too — see `docs/workflow_inventory.md` for full detail:

| Path | Why it's flagged |
|---|---|
| `codebase/mapping_code/` (whole folder) | A diverged duplicate "starter prototype" bundle of two `codebase/mapping_tools/` scripts, confirmed via `diff` to not be identical to the live versions. Hardcodes a different machine's Python path and targets the legacy `config/leap_mappings.xlsx`. Candidate for removal once confirmed nothing outside this repo still points at it. |
| `codebase/utilities/build_canonical_mapping_views.py` | Imports a module (`codebase.scrapbook.utilities`) that doesn't exist anywhere in this repo's git history — currently broken, cannot run. |
| `codebase/functions/unified_name_lookup.py` | Not imported anywhere in `codebase/`. |

## Root-level scratch files

Unlike everything else in this doc, these three are **git-tracked** (`git log -- <file>` shows
real history), so deleting or moving them is fully recoverable — the caution above about
gitignored, unrecoverable content doesn't apply here.

| File | What it actually is | Suggested action |
|---|---|---|
| `Untitled-1.md` | A raw console log dump from a full pipeline run on a different machine (`C:\Users\Work\github\leap_mappings`). Duplicates what `results/logs/mapping_pipeline.log` already captures for any current run. | Low value kept at root — candidate to delete (recoverable via git) or move to `docs/archive/` if you want to keep it as a historical reference. |
| `old gent chat.txt` | A saved agent/Copilot chat transcript from a previous session (plain text, includes timestamps like "Wednesday 4:58 PM" and "You stopped after 7h 4m 46s"). Not read by any code. | Candidate to move to `docs/archive/` if the conversation has reference value, otherwise delete (recoverable via git). |
| `prompts 5-7.md` | Short but substantive — records a real design rule: ignored sectors/fuels in ESTO/9th source data should be excluded via `config/mapping_issue_exception_sets.xlsx` rather than chased as mapping gaps. **This rule doesn't appear to be captured in `docs/special_rules_and_design_decisions.md` yet.** | Don't just archive this one — the content looks worth folding into `docs/special_rules_and_design_decisions.md` first, then the original file can move to `docs/archive/` or be deleted. |

None of these three have been moved, edited, or deleted as part of this pass — flagged here so
they don't get lost, since (unlike the rest of this doc) they're a mix of "clearly disposable"
and "contains real content that hasn't been captured elsewhere yet."

## Not flagged (intentionally kept as-is)

- `results/mapping_graph_index/`, `results/for_colleagues/`, `results/common_esto/structural_artifacts/`, `partitioned_application/`, `partition_cache/`, `economy_scoped/`, `anchor_reconciliation/`, `anchor_contribution_breakdown/`, `inverted_conservation/` — all produced by *current*, named standalone scripts (see the relevant `results/*/README.md`). Not part of the main pipeline run, but not orphaned either.
- `results/maintenance/subtotal_mismatch_suggested_improvements.csv`, `subtotal_draft_*_pairs.csv` (without `copy` suffix), `rollup_consistency.csv` — current outputs of standalone review tools, kept.

## Suggested next step (not done here)

When you're ready to action this: start with the "confirmed orphaned" table — those have zero
code references and the highest confidence they're safe to remove. Treat `config/archive/`
pruning as a separate, lower-risk "retention policy" decision rather than a one-time deletion.
Leave the "likely clutter" table for a follow-up pass with a quick visual check of each file
before removal, per the safety note above.

---

# 16. `docs/diagnostic_file_review_signals.md` (new file)

# Which `results/` diagnostic files are actually worth reading?

**This is decision support, not a verdict.** I can't tell you a file is useless — only that
nothing in the project's own documentation or code currently points at it. That might mean it's
safe to ignore, or it might mean it's the one file *you* check by habit that never made it into
a doc. Nothing here has been deleted, hidden, or deprioritized in the code — this is purely a
reading aid for deciding where to look first.

## Method

Every `results/common_esto/` and `results/maintenance/` CSV (the two densest diagnostic
clusters — 128 files) was scored on three signals:

1. **Named in your own review docs?** — cross-referenced against every `.csv` filename
   mentioned in `docs/*.md`, `docs/prompts/*.md`, `AGENTS.md`, and `README.md`.
   `docs/improvement_todo.md` §1 in particular already has a human-authored "primary review
   outputs" list with a suggested review order — that's the strongest positive signal available.
2. **Read back by another script?** — a file that's only ever written, never read as input by
   any `apply_*`/downstream tool, is more likely a one-way debug dump than something the
   pipeline depends on. (Checked by grepping `codebase/` for each filename outside its own
   producing script.)
3. **Volume in the one real run captured** (`config data results leap mappigns.zip`) — file
   size as a rough proxy for row count. Near-empty files (<2 KB) read very differently from
   multi-MB ones.

## Tier 1 — confirmed valuable (named in docs and/or consumed downstream)

Already covered by `docs/improvement_todo.md` §1's review-order list, or read back by an
`apply_*` tool (e.g. `duplicate_mappings.csv` → `apply_duplicate_mapping_removal.py`,
`display_names_proposed_updates.csv` → `apply_display_name_updates.py`,
`subtotal_mismatch_suggested_improvements.csv` → `apply_subtotal_mismatch_review.py`). No
further action — these are doing their job.

## Tier 2 — worth a human second look

Substantial in size (real content, not near-empty), never named by filename in any project doc,
and never read back by another script. Sorted by size — largest first is where a "why does this
exist and is anyone using it" conversation would pay off most:

| File | Size (sampled run) | What it appears to be (from code) |
|---|---|---|
| `results/common_esto/diagnostics/broad_common_row_affected_output.csv` | 17.5 MB | Full row-level output affected by "broad" common rows (rows spanning unusually many components) — the largest diagnostic file in the whole pipeline. |
| `results/common_esto/qa_common_esto_product_intersections_resolved.csv` | 4.0 MB | Product-axis intersection resolution detail. `qa_common_esto_flow_intersections_resolved.csv` (200 KB, same pattern) is its flow-axis counterpart. |
| `results/common_esto/diagnostics/common_esto_components_pruned_not_applicable.csv` | 752 KB | Components pruned as not-applicable during structure build. |
| `results/common_esto/diagnostics/broad_common_row_components.csv` | 538 KB | Component-level detail for broad common rows. |
| `results/maintenance/unmapped_ninth_pairs.csv` | 536 KB | The **un-filtered** version of `unmapped_nonzero_ninth_pairs.csv` (which *is* named in docs) — i.e. every unmapped pair, not just the non-zero ones. Worth checking whether the raw version is ever actually opened, or whether the nonzero-filtered one always supersedes it. |
| `results/common_esto/common_esto_total_check.csv` | 441 KB | Same apparent purpose as `qa_common_esto_total_check.csv` (which *is* named in docs) but without the `qa_` prefix — worth confirming whether both are needed or one is a redundant duplicate written by the same step. |
| `results/common_esto/diagnostics/common_esto_component_relevance.csv` | 438 KB | Relevance scoring behind the partial-coverage QA files. |
| `results/maintenance/unmapped_esto_pairs.csv` | 332 KB | Same pattern as `unmapped_ninth_pairs.csv` above — the un-filtered counterpart to the documented `unmapped_nonzero_esto_pairs.csv`. |
| `results/maintenance/subtotal_mismatches_including_exceptions.csv` | 120 KB | Subtotal mismatches *before* the reviewed-exception allowlist is applied — companion to the documented `subtotal_mismatches.csv`. |
| `results/common_esto/diagnostics/intersecting_common_product_groups.csv` | 90 KB | Groups of common rows with intersecting product scope, flagged for review. |

## Tier 3 — near-empty structural sanity checks (no action needed)

These are consistently tiny (under ~1.2 KB in the sampled run):
`qa_common_esto_axis_partition_skipped_broad_rows.csv` (18 B), `qa_common_esto_duplicate_components.csv`
(115 B), `qa_common_esto_components_missing_from_structure.csv` (66 B),
`qa_common_esto_excluded_components.csv` (606 B), `qa_common_esto_structure_summary.csv` (1.1 KB),
and the `structural_artifacts/qa_{duplicate,cyclic,conflicting}_structural.csv` trio (66 B each).
Reading these as "healthy = stays small" checks rather than clutter — they exist specifically to
catch a problem, and an almost-empty file is the expected/good state, not a sign the check is
unused. No action suggested here.

## Round 2 — `mapping_relationships/` and `tree_structure/`, traced by constant not filename

The Tier 2 list above was built from filename-string matching (does this filename appear
elsewhere in `codebase/`). That under-counts real dependencies: the live pipeline wires stages
together by importing **path constants**, not by re-typing filenames — e.g.
`run_mapping_pipeline.py` imports `COMMON_ROWS_PATH` from `build_common_esto_structure.py` and
passes it into `apply_common_esto_structure.py`, so the filename string may appear only once in
the whole codebase even though the file genuinely is read downstream. Round 2 traced each output
by its constant name (import sites) and by locally-redeclared identical paths, not just string
search — a stricter and more reliable test, applied to `results/mapping_relationships/` and
`results/tree_structure/`.

**Four-way classification** (refined from the two-way "read or not" test, because several
files here are read by nothing yet are clearly not clutter — they're the pipeline's
human-facing checkpoints, not machine inputs):

- **Necessary — pipeline dependency**: read by another stage in the same `run_mapping_pipeline.py` run. Removing it breaks or silently degrades a later stage.
- **Necessary — standalone-tool dependency**: read only by a specific manual tool (e.g. `reconcile_anchor_validation.py`, `infer_subtotal_labels.py`). Needed only if you use that tool.
- **Necessary — human-review checkpoint**: never read by any script, but is itself a validation/summary/audit output whose entire purpose is to be opened by a person. Being "unread by code" here is expected, not a red flag.
- **Unclear necessity**: never read by any script, not named as a review priority anywhere, and not itself framed as a checkpoint. The only genuine "worth asking is anyone using this" list.

### ⚠ Correctness-relevant finding: `results/tree_structure/` double-write pattern

`esto_tree.csv`, `ninth_tree.csv`, `leap_tree.csv`, `common_esto_tree.csv`, `ninth_validation.csv`,
`leap_validation.csv`, and `common_esto_validation.csv` are each written **twice** per full
pipeline run, by two different code paths: once by Stage 0 (via
`outlook_mapping_maintenance_workflow.run()` → `build_dataset_tree_structure.run_tree_structure_workflow()`)
and again by Stage 3 (which builds/validates the trees inline and overwrites the same files with
its own version). In a full `python codebase/run_mapping_pipeline.py` run, Stage 3's version wins
since it runs later — but if Stage 3 is ever skipped or the run stops after Stage 0
(`--stages 0` or a partial run), these files are left holding Stage 0's version with no signal
that they're not the Stage 3 version you'd normally expect. Two files —
`esto_validation.csv` and `common_esto_non_esto_parent_child_edges.csv` — are Stage-0-only
(Stage 3 never touches them), and are read back within Stage 0 itself by
`_write_maintenance_summary`. Worth deciding whether the double-write is intentional
(Stage 3 refines Stage 0's draft) or an accident of two code paths doing similar work — not
something to silently rely on either way.

### `results/mapping_relationships/` — necessity summary

**Necessary (pipeline dependency):** `energy_balance_relationships.csv`, `coverage_exclusions.csv`,
`common_esto_overrides.csv`, `non_expanding_rollups.csv` (read via a derived path next to
`energy_balance_relationships.csv`, not a named constant — exactly the kind of dependency a
plain filename search misses), `raw_leap_results.csv`, `leap_results_converted_to_esto.csv`,
`ninth_results_converted_to_esto.csv`, `esto_results_exact_rows.csv`.

**Necessary (standalone-tool dependency):** `energy_balance_relationships.xlsx` (only
`build_energy_balance_graph_links.py` reads it), `esto_combined_rows.csv` (only
`check_leap_to_esto_conversion_coverage.py`).

**Unclear necessity — never read by anything, pipeline or tool:**
`relationship_catalogue_6_col.csv`, `qa_unknown_esto_target_flows.csv`,
`qa_unknown_ninth_target_flows.csv`, `qa_non_expanding_rollup_unresolved.csv`,
`leap_sources_without_esto_target.csv`, `esto_targets_without_leap_source.csv`,
`missing_dataset_pairs_by_use_case.csv`, `not_considered_esto_rows.csv`,
`leap_to_esto_duplicate_source_pairs.csv` (+ `_allowed_matched`),
`leap_to_esto_duplicate_target_pairs.csv` (+ `_allowed_matched`),
`one_to_many_mappings_without_allocation_or_combined_target.csv`,
`leap_to_esto_parent_child_risks.csv`, `leap_to_esto_coverage_summary.csv`,
`leap_to_esto_excluded_source_audit.csv`, `leap_source_rollup_audit.csv`,
`leap_source_to_esto_component_lineage.csv`, `leap_source_branch_fallback_audit.csv`,
`leap_all_demand_aggregated_overlap_warnings.csv`, `ninth_source_to_esto_component_lineage.csv`.
Most of these are named like review artifacts (`qa_*`, `*_duplicate_*`, `*_lineage`,
`*_audit`) so they're plausibly intended as human-review checkpoints rather than dead weight —
but unlike the tree/validation files above, nothing in `docs/improvement_todo.md` or elsewhere
currently names them as something to check, so I'm not reclassifying them into the
"human-review checkpoint" bucket without your confirmation. This is the real candidate list for
"work through later."

**Not part of the automated pipeline at all:** `build_no_data_mapping_rows.py`'s four
`no_data_rows_*.csv` outputs and `check_leap_to_esto_conversion_coverage.py`'s entire
`leap_to_esto_coverage/` folder (9 files) — neither script is imported or called by
`run_mapping_pipeline.py`; both must be run manually, and the coverage-check tool additionally
needs hand-populated placeholder input files first.

### `results/tree_structure/` — necessity summary

**Necessary (pipeline dependency):** `esto_validation.csv`,
`common_esto_non_esto_parent_child_edges.csv`, `common_esto_validation.csv` (Stage-0-written
version, read back within Stage 0) — see the double-write note above for the nuance.

**Necessary (standalone-tool dependency):** `esto_tree.csv`, `ninth_tree.csv`, `leap_tree.csv`
(all three read by `infer_subtotal_labels.py`), `all_dataset_trees.csv` and
`ninth_fuel_validation.csv` (read by `reconcile_anchor_validation.py` /
`inverted_conservation_validation.py` — both gated behind a module-level flag a human must flip
to run at all).

**Necessary (human-review checkpoint, not read by code — this is expected):**
`common_esto_validation_summary.csv`, `common_esto_validation_by_year.csv`,
`common_esto_validation_totals.csv`, `source_parent_anchor_validation.csv`,
`source_parent_anchor_validation_summary.csv`. These are the pipeline's actual safety net —
totals-preservation and anchor validation. Their content also gets folded into
`results/common_esto/common_esto_output_status.csv` in-memory before the standalone files are
written, which is *why* nothing reads the files back — the summary already traveled elsewhere.
Do not treat "unread by code" here as a signal these are removable.

**Unclear necessity:** `common_esto_tree.csv`, `ninth_validation.csv`, `leap_validation.csv`,
`ninth_sector_validation.csv`. These are genuinely never read by anything (pipeline, tool, or
`_write_maintenance_summary`) and aren't named in `docs/improvement_todo.md` — but note
`ninth_validation.csv`/`leap_validation.csv` still drive the in-memory
`_build_source_inconsistency_lookup` used by Stage 3's validation orchestration, so the
*computation* is load-bearing even though the *file* isn't re-opened. Only `common_esto_tree.csv`
and `ninth_sector_validation.csv` are unclear on both counts (file and computation).

## Suggested next step (not done here)

For each Round 1 Tier 2 file and each Round 2 "unclear necessity" file: a quick "do I ever open
this" gut-check is enough — if the answer is no across the board, that's useful confirmation
they could move to a less-prominent location (or be dropped from generation) in a future, more
invasive pass. If any answer is yes, add it to `docs/improvement_todo.md` §1's review list so
the next person doesn't have to rediscover it the way this pass did.

Separately, the `results/tree_structure/` double-write pattern (see above) is a correctness
question, not a "does anyone read this" question — it needs a decision (is Stage 3's overwrite
intentional refinement of Stage 0's draft, or should Stage 0 stop writing those files at all)
rather than just a usefulness gut-check. Tracked as its own item in
`docs/improvement_todo.md`.

## Round 3 — the rest of the workflow, plus a full duplicate-pattern sweep

Requested explicitly: re-run through the whole workflow (not just the two densest folders) and
specifically hunt for (a) files created where they don't seem necessary, and (b) near-identical
versions of files being produced without a clear reason. This round closes out the pieces Round
1/2 didn't cover, and does a full filename-collision sweep across the entire `results/`/`config/`
listing captured in the zip snapshot (485 entries) rather than only the pairs spotted by chance.

### New since Round 2: the 6 `common_esto_validation_orchestration.py` outputs

These arrived via the same-day upstream pull (see section 5's re-verification note) and were
missing from Round 1/2 entirely — a gap in the original survey, not new code behaviour to
re-flag as a regression.

| File | Read by anything? | Classification |
|---|---|---|
| `common_esto_validation_child_detail.csv`, `common_esto_validation_issue_patterns.csv`, `common_esto_validation_rollup_diagnosis.csv` | No content read; path existence is checked and recorded into `common_esto_output_status.csv`'s manifest (`run_mapping_pipeline.py` lines ~718–739) | **Necessary — human-review checkpoint.** Same pattern as `common_esto_validation_summary.csv` etc. — deep-diagnostic breakdowns meant for a person, not a downstream script. |
| `common_esto_rollup_validation.csv` / `_summary.csv` | No reads found anywhere | **Necessary — human-review checkpoint** (parallel structure to `common_esto_validation.csv`/`_summary.csv`, just validating rollup-rule correctness specifically rather than recursive sums). |
| `common_esto_source_frontier.csv` | No reads found anywhere | **Necessary — supporting reference artifact.** Documents the non-overlapping comparison frontier the validation is based on; not consumed by code, but explains *what* is being validated, not just the result. |

None of these are flagged as removable — but see the new dedup candidate below
(`common_esto_validation.csv` vs. `common_esto_rollup_validation.csv`), since two
similarly-named validation outputs from the same module deserve a closer look at whether they
overlap.

### Full filename-collision sweep (every basename appearing 2+ times anywhere in `results/`+`config/`)

This is the concrete answer to "similar versions of files being created" — every case where the
exact same filename (ignoring extension) appears at more than one path in the zip snapshot,
found by comparing basenames across the whole listing rather than folder-by-folder:

| Basename appearing more than once | Paths | Verdict |
|---|---|---|
| `raw_leap_results`, `leap_results_converted_to_esto`, `leap_source_rollup_audit` | `results/mapping_relationships/*.csv` (full) vs. `results/mapping_relationships/economy_scoped/02BD/*.csv` (single-economy) | **Not accidental duplication.** `economy_scoped/02BD/` is a deliberate single-economy mirror written by `regen_common_esto_comparison_fast_path_workflow.py` — see the new note in section 8 above. Genuinely different scope, not redundant. |
| `common_esto_comparison_data`, `common_esto_comparison_wide`, `common_esto_output_status` | `results/common_esto/*.csv` (full) vs. `results/common_esto/economy_scoped/02BD/*.csv` | Same pattern, same tool, same verdict — intentional. |
| `common_esto_comparison_wide`, `source_pair_to_common_row` | `results/common_esto/` (or `structural_artifacts/`) vs. `results/for_colleagues/` | **Not accidental duplication.** `for_colleagues/` is a deliberate trimmed/simplified export (`for_colleagues_export_workflow.py`) — already documented. |
| `missing_mapped_esto_rows_summary` | `results/maintenance/missing_mapped_esto_rows/` (2,647 B) vs. `results/missing_mapped_esto_rows/` (1,976 B) | **Confirms the existing "stale duplicate folder" finding** (section 15) with new evidence: the two files are *different sizes*, meaning they're from different (older vs. newer) runs, not a live mirror — further support that the top-level folder is genuinely stale, not a second intentional output. |
| `inverted_conservation_summary` | `results/common_esto/inverted_conservation/` (6,784 B) vs. `inverted_conservation.building/` (**also 6,784 B**) vs. `inverted_conservation_variant_verification/` (19,513 B) | **Strengthened finding.** The first two are byte-size-identical — strong evidence `inverted_conservation.building/` is a true redundant duplicate of `inverted_conservation/` from a repeated manual run with a typo'd/experimental `output_dir`, not a meaningfully different variant. The `_variant_verification/` one is a different size, so it's plausibly a genuinely different run (different scope/inputs) rather than a duplicate. **Upgraded from "likely clutter" to a stronger archive candidate for `inverted_conservation.building/` specifically** — reflected in section 15 and section 19. |
| `outlook_mappings_master` | `config/outlook_mappings_master.xlsx` (320,457 B, current) vs. `config/archive/outlook_mappings_master.xlsx` (273,914 B, one of ~80 backups) | Already covered — expected, this is exactly what the archive backup mechanism is for. |

**Also checked and found nothing new:** a sweep for `_v2`/`_final`/`_old`/`_new`/`_temp`/`_wip`/
`_orig`-style suffixes across the whole listing turned up only things already documented
(`config/archive/outlook_mappings_master_NEW.*`, `results/maintenance/display_names_qa_new.csv`,
`results/logs/stdin_pipe_test.*`) — no new undocumented "version" files.

### Updated dedup task: add this pair to section 20

`results/tree_structure/common_esto_validation.csv` vs. `common_esto_rollup_validation.csv` —
both are Common-ESTO validation outputs from the same module, added in the same 586-line growth
that also added the 3 diagnostic-detail files and `common_esto_source_frontier.csv`. Not yet
checked whether `common_esto_rollup_validation.csv` is a genuinely distinct check (rollup-rule
correctness vs. recursive-sum correctness — plausible from the names) or overlaps significantly
with the existing validation. Flagged, not resolved. (Already reflected in section 20's table.)

### `results/mapping_graph_index/` and `results/for_colleagues/` — lightly re-checked

Spot-checked (not exhaustively re-tiered, since both are already fully attributed to specific
standalone tools with no ambiguity about their purpose): `dashboard_graph_flow_product_index.csv`
is read by `convert_leap_combined_esto_to_esto_first.py` (standalone-tool-chain dependency,
already implied by the existing README). Nothing found here that changes their existing
classification as "standalone, use only if you use that tool."

## Still not covered

`results/logs/` (single current file, already trivially covered by its own README) and
`config/archive/`'s ~80 backup files (already covered as a retention-policy question, not a
per-file necessity question, in section 15) weren't re-run through the tiering framework —
neither needs it; the framework is built for "why does this diagnostic exist," not for logs or
backups, which have an obviously different purpose.

As of Round 3, every `results/` subfolder and every near-duplicate filename pattern in the zip
snapshot has been through at least one pass of this audit.

---

# 17. `docs/improvement_todo.md` (modified — full current content)

This is a pre-existing file. The additions from this session are the linked cross-reference in
§1, all of §2's "Done"/"New finding" notes, the entirely new §3a, the "Done" note in §7, and the
entirely new §9. Full current content follows so nothing is lost in translation:

# LEAP mappings improvement todo

This backlog covers improvements outside the deferred regression and verification work in `docs/QA plan.md`. Complete items only after reviewing current generated outputs; existing result files may be stale when mapping workbooks have uncommitted changes.

## 1. Resolve current semantic mapping issues

**Status:** In progress — data-relevance filtering implemented; semantic findings still require review

Rerun mapping maintenance and Stages 1-3 with the intended workbook state before treating the current row counts as authoritative. Then group findings by recurring semantic cause rather than reviewing thousands of rows independently.

See `docs/diagnostic_file_review_signals.md` for a cross-check of which `results/common_esto/`
and `results/maintenance/` diagnostic files below are already covered by this list vs. which
are substantial, currently-produced files never named in any review doc (Tier 2 there) — worth
folding into the review order below if any turn out to matter.

Primary review outputs:

- `results/common_esto/qa_common_esto_unresolved_partial_coverage.csv` — actionable high-severity rows after filtering `missing_component_pairs` to components with non-zero ESTO base-year, 9th projection, or LEAP balance evidence.
- `results/common_esto/qa_common_esto_structural_partial_coverage.csv` — full Stage 2 structural candidates before applying value relevance.
- `results/common_esto/qa_common_esto_partial_coverage_components_without_relevance.csv` — structurally missing pairs excluded from the actionable file because they lack qualifying non-zero evidence.
- `results/common_esto/qa_common_esto_existing_components_without_relevance.csv` — existing Common ESTO components that are not needed for the current comparison data; informational only.
- `results/common_esto/qa_nonzero_unmapped_leap_branches.csv` — non-zero LEAP balance branches without direct ESTO mappings, including whether an indirect ESTO pair can be inferred through the 9th crosswalk.
- `results/common_esto/qa_common_esto_partial_coverage_mapping_candidates.csv` — review-only, copy-friendly proposals for the mapping sheet identified by each actionable partial-coverage row.
- `results/common_esto/qa_nonzero_unmapped_leap_branch_mapping_candidates.csv` — review-only ESTO target proposals inferred independently from LEAP branch and fuel evidence.
- `results/common_esto/highly_recommended_mapping_candidates.csv` — combined copy-ready mapping rows; excludes every incomplete, ambiguous, zero-only, or already-targeted source pair.
- `results/maintenance/leap_source_presence_conflicts.csv` — LEAP sector/fuel pairs active on only one of `leap_combined_esto` and `leap_combined_ninth`. Use `presence_status` to separate the two directions. Do not assume every asymmetry is an error; determine whether the comparison scope requires both mappings.
- `results/tree_structure/common_esto_non_esto_parent_child_edges.csv` — Common ESTO hierarchy edges not present in the source ESTO tree. Decide whether each is an intentional extension, a display hierarchy only, or an invalid additive parent-child relationship.

Supporting lineage:

- `results/common_esto/common_esto_rows.csv` — find the labels and scope for a `common_row_id`.
- `results/common_esto/common_esto_row_components.csv` — inspect the full ESTO component membership of that row.
- `results/mapping_relationships/energy_balance_relationships.csv` — trace which LEAP or 9th source relationship produced the component coverage.
- `config/outlook_mappings_master.xlsx` — inspect the owning base mapping and rollup sheets.
- `config/mapping_issue_exception_sets.xlsx` — check whether an apparent conflict is an explicitly reviewed exception.
- `config/esto_external_definition_authority_working_set.xlsx` — check flow/product scope, common mapping mistakes, confidence, and sign meaning before changing a mapping.

Suggested review order:

1. Group partial-coverage findings by `source_system`, `use_case`, and repeated `missing_component_pairs` patterns.
2. For one representative `common_row_id`, compare `common_esto_rows.csv` with `common_esto_row_components.csv`.
3. Trace the source relationship in `energy_balance_relationships.csv`.
4. Inspect the relevant base mapping and rollup rows in `outlook_mappings_master.xlsx`.
5. Classify the cause as missing mapping, over-broad common row, intentional source limitation, invalid rollup, or reviewed exception.
6. Record any required human rule in `docs/special_rules_and_design_decisions.md` before changing behaviour.
7. Apply the narrowest mapping/configuration correction and rerun all affected stages.

Do not prioritize the raw counts in `unmapped_nonzero_esto_pairs.csv`, `unmapped_nonzero_ninth_pairs.csv`, or `common_esto_source_rows_missing_common_map.csv` until they are separated into non-zero relevant rows, subtotals, intentionally excluded scope, and genuine mapping gaps.

## 2. Finish the canonical-workbook migration

**Status:** Pending — call-site audit now done, see `docs/workflow_inventory.md`

- Complete the intended removal of `config/leap_mappings.xlsx`.
- Audit remaining production call sites for `leap_mappings.xlsx`, `master_config.xlsx`, and legacy `leap_utilities` fallbacks.
  **Done:** `docs/workflow_inventory.md` now traces every `codebase/` import back to whether it's
  live-pipeline, standalone-tool, dashboard-prototype (out of scope per `AGENTS.md`), legacy, or
  orphaned. The legacy chain is exactly `leap_mapping_refresh_workflow.py` →
  `utilities/master_config.py` + the whole `leap_results_dashboard*` / `mappings/canonical_mapping.py`
  cluster; `master_config.py`'s only non-legacy consumer is Stage 1's `FALLBACK_WORKBOOK_PATH`.
- Make canonical workflows use `config/outlook_mappings_master.xlsx` explicitly.
- Fail with a clear message when a required canonical sheet or column is absent rather than silently using legacy data.
- Keep deliberate legacy compatibility isolated and documented.
- **New finding:** `codebase/utilities/build_canonical_mapping_views.py` imports
  `codebase.scrapbook.utilities`, a module that does not exist anywhere in this repo's git
  history — the script cannot currently run. Either restore/replace the missing dependency or
  remove the script.
- **New finding:** `AGENTS.md` references `codebase/transformation_analysis_workflow.py` as an
  existing script; it does not exist under `codebase/` at any depth. Worth fixing next time
  `AGENTS.md` is edited (left as-is here since it's a human-maintained instructions file, not
  touched as part of this docs pass).

## 3a. Resolve the `results/tree_structure/` double-write pattern

**Status:** New finding, needs a decision

`docs/diagnostic_file_review_signals.md` (Round 2) found that `esto_tree.csv`, `ninth_tree.csv`,
`leap_tree.csv`, `common_esto_tree.csv`, `ninth_validation.csv`, `leap_validation.csv`, and
`common_esto_validation.csv` are each written twice per full pipeline run: once by Stage 0 (via
`build_dataset_tree_structure.run_tree_structure_workflow()`, called from
`outlook_mapping_maintenance_workflow.run()`) and again by Stage 3, which independently
builds/validates the same trees and overwrites the same filenames. A full run ends with Stage
3's version; a partial run that stops after Stage 0 leaves Stage 0's version with no marker that
it isn't the Stage 3 version a later reader would expect.

Decide: is Stage 3 meant to refine/supersede Stage 0's draft (in which case this is fine and
just needs a note), or should Stage 0 stop writing these files at all (in which case there's a
real duplicate-computation cost being paid every maintenance run)? Either way, the current
silent double-write isn't documented anywhere in code.

## 3. Complete hierarchy value validation

**Status:** Pending

- Add recursive 9th Outlook sector and fuel value validation.
- Add recursive LEAP branch value validation where result data are available.
- Preserve the distinction between source-defined hierarchy and Common ESTO-only extensions.
- Report parent/detail overlaps that could cause double counting.
- Document any hierarchy edges whose additive meaning requires human confirmation.
- Add an explicit mapped-ESTO-subtotal coverage check: for every raw ESTO parent subtotal, compare its value with the sum of mapped leaf descendants and report mapped, unmapped, excluded, and zero-only child components.
- Make subtotal validation summaries report the number of eligible parents and checks performed, not only mismatch rows, so an empty CSV cannot be mistaken for proof that coverage was tested.
- Define a non-overlapping comparison frontier for each comparison scope. The canonical all-rows dataset must retain parent, child, and generated rollup rows; a separate validated additive view or explicit frontier metadata should identify which rows may be summed together.
- Preserve `common_row_id`, rollup basis, hierarchy status, and component lineage in a machine-readable output so dashboards do not infer subtotal meaning from display labels.
- Decide whether one centrally validated additive dataset is sufficient or whether several named frontiers are required for detail, summary, and rollup contexts.

## 4. Resolve the ESTO definition-authority working set

**Status:** Pending human review

Work through `config/esto_external_definition_authority_working_set.xlsx`:

- Resolve the four rows currently in `review_queue`.
- Review the 109 `product_leaks` and fix their source extraction or classification where applicable.
- Review flow definitions marked `Unknown`, `unclassified`, `needs_review`, or `needs_definition_or_alias`.
- Resolve low-confidence `Others` categories before using them as mapping authority.
- Preserve source references and the history of rejected interpretations.

## 5. Improve researcher mapping maintenance

**Status:** Proposed

Generate a compact review workbook containing actionable findings rather than raw diagnostic volumes. Include:

- source and current target categories;
- definitions, inclusions, and exclusions;
- raw and after-rollup cardinality;
- non-zero example economies and values;
- matched exception details;
- suggested review action;
- owning sheet and row identifier;
- related decision-log ID.

The workbook should support review, not automatically approve or rewrite mappings.

## 6. Make the existing orchestration workflow notebook-safe

**Status:** Proposed

Refactor `codebase/run_mapping_pipeline.py` into a slim Jupyter-friendly workflow with top-level toggles for:

1. Mapping maintenance.
2. Relationship generation.
3. Common ESTO structure generation.
4. Application of the common structure.
5. Tree generation and validation.

Reuse the existing stage functions. Do not duplicate their processing logic. Replace the command-line-only `argparse` entry path with notebook-safe run blocks, and make the selected input workbook and result directories explicit near the top of the workflow.

## 7. Improve explanatory documentation

**Status:** Proposed (partially done — see below)

- Add a compact pipeline diagram.
- Add a worked example showing how a coarse source category forces a common rollup or graph partition.
- Add a glossary for relationship, component, common row, source aggregate, axis partition, and comparison scope.
- Define each `comparison_scope` and its included systems.
- Clearly separate blocking validation failures from review diagnostics.
- Keep `README.md`, `docs/mappings_system.md`, and the implemented pipeline behaviour synchronized.
- **Done:** `results/README.md` plus a `README.md` in each `results/` subfolder now give a
  first-time reader a folder map, a short "start here" primary-output list, and a note on
  which files are pipeline vs. standalone-tool output. `docs/results_folder_cleanup_candidates.md`
  tracks files that look orphaned/duplicated so cleanup can be actioned safely later (see the
  safety note in that file — `results/` is gitignored, so deletions there aren't recoverable via
  git history).

## 9. Clean up `results/` clutter (see `docs/results_folder_cleanup_candidates.md`)

**Status:** Candidate list documented, not yet actioned

A docs-only navigation pass (item 7) surfaced several confirmed-orphaned and likely-duplicate
files/folders under `results/` and `config/archive/` — see
`docs/results_folder_cleanup_candidates.md` for the full list and reasoning. Before acting on
it: confirm each item is genuinely regenerable or superseded, and prefer moving to a dated
quarantine location over hard-deleting, since `results/` has no git history to fall back on.

## 8. Check the LEAP side of no-data mapping rows once full LEAP output sheets exist

**Status:** Proposed

`codebase/mapping_tools/build_no_data_mapping_rows.py` flags `leap_combined_esto` and `leap_combined_ninth` rows whose non-LEAP side (ESTO or 9th Outlook) has no non-zero data anywhere. It currently assumes the LEAP side always has no data, because we do not yet have full LEAP output sheets in a form comparable to the ESTO/9th source tables. Once those output sheets are available:

- Load real LEAP result data and compute non-zero (leap_sector_name_full_path, raw_leap_fuel_name) pairs, the same way `load_nonzero_esto_pairs`/`load_nonzero_ninth_pairs` do for the other two systems.
- Replace the `leap_side_has_data` placeholder (`pd.NA`) with a real boolean.
- Restrict `leap_combined_esto`/`leap_combined_ninth` flags to rows where **both** sides have no data, matching the `ninth_pairs_to_esto_pairs` logic already in place.

---

# 18. `.gitignore` — what changed, and a bug I found and fixed mid-session

Two edits were made to `.gitignore` this session:

1. **First edit** (to make the `results/README.md` files trackable at all): added
   `!results/README.md` and `!results/**/README.md` after the existing `results/` / `.gitkeep`
   rules.
2. **Second edit** (bug fix — the first edit didn't actually work): `results/` as a bare
   directory-match rule makes git skip scanning inside the directory entirely, so nested `!`
   negation patterns are silently ineffective — a well-known gitignore gotcha. Confirmed with
   `git check-ignore`/`git status --untracked-files=all` that the README files weren't actually
   becoming trackable under the first edit. Fixed by changing the pattern from `results/` to
   `results/**` and adding `!results/**/` (so git recurses into every subdirectory) alongside
   the existing `!results/**/README.md`.

**Current relevant `.gitignore` block** (the fixed version):

```gitignore
outputs/
results/**
!outputs/.gitkeep
!results/.gitkeep
!results/**/
!results/**/README.md
```

Verified working via `git status --short --untracked-files=all results/`, which now correctly
lists all 8 new `results/**/README.md` files as trackable (`??`) while everything else under
`results/` remains ignored, as intended.

---

# 19. NEW TASK — identify single-use files/folders and archive them (not yet run)

**Goal:** find files/folders that were clearly created for one specific past task — a one-off
export, a manual backup, a debugging redirect, a superseded prototype — and move them (never
delete) into a clearly-named archive location, so the working tree only shows things that are
either currently produced by running code or genuinely still relevant.

## Why archive, not delete

Same rule as everywhere else in this document: `results/` and `config/archive/` are gitignored,
so anything deleted there has no git history to recover from. Even for git-tracked files, prefer
moving to an obviously-named archive location over deleting outright — it's just as effective at
reducing visible clutter, costs nothing extra, and is trivially reversible if something turns out
to matter. Suggested destinations:

- Inside a gitignored folder (`results/`, `config/archive/`): move to a dated subfolder like
  `results/_archive_2026-07-22/` (preserve the original relative path underneath it) rather than
  deleting. This keeps it out of the way without pretending it never happened.
- Git-tracked files (root-level scratch files, anything under `codebase/`): `git mv` into
  `docs/archive/` (already an established convention in this repo — see `docs/README.md`'s
  description of `docs/archive/` for completed prompt packs) or a new top-level `archive/`
  folder, whichever fits the file better.

## Methodology (run this against the main-PC repo's actual current files — don't reuse the list below blindly, it may be stale)

1. **List every file/folder** under `config/`, `data/`, `results/` (if present), and `codebase/`.
2. **Flag by naming pattern**, the strongest signal for single-use artifacts:
   - Timestamps embedded in the filename (`_20260706_140819`, `.before_*_<timestamp>`,
     `.maintenance_run_<timestamp>`, `_baseline_<date>`)
   - Substrings like `copy`, `copy 2`, `- Copy`, `backup`, `new`, `old`, `final`, `test`, `temp`,
     `todo`, `dummy`, `_rebuilt`, `_SLICE`
   - Ad hoc redirected log/output files whose name doesn't match any `_PATH`/`_DIR` constant
     actually defined in `codebase/` (cross-reference the way `docs/workflow_inventory.md` and
     `docs/repo_data_slimdown_plan.md` were built — grep for the literal filename across
     `codebase/*.py`; zero matches is a strong signal)
   - Hex/random-looking filenames with no extension or a mismatched one (Office crash-recovery
     temp files look like this)
   - Root-level files that aren't part of the established `docs/`, `config/`, `data/`, `results/`,
     `codebase/`, `tests/` structure
   - A whole folder whose own README/docstring describes itself as a "starter", "prototype", or
     "uploaded" bundle rather than the live implementation
3. **Confirm before archiving**: for each flagged item, grep `codebase/*.py` for the literal
   filename/folder name. Zero references anywhere = safe archive candidate. Any reference found
   = investigate what actually reads/writes it before touching it.
4. **Move, log, don't delete.** For each item archived, add one line to a running log (a new
   `docs/archive_log.md` is a reasonable place) recording: original path, new path, date, and the
   one-line reason it was flagged. This is what lets someone recover something later without
   having to ask "wait, where did that file go?"

## Starter candidate list (carried over from the zip snapshot taken on the secondary checkout — re-verify each against the main-PC repo before acting, do not assume it's current)

These were confirmed via the methodology above (zero code references) against the zip snapshot,
and are very likely to still be present in some form in the main-PC repo since the zip was a
copy of that repo's `config`/`data`/`results` folders:

- `config/archive/*.xlsx` — roughly 80 timestamped workbook backups (`outlook_mappings_master.before_*`,
  `.maintenance_run_*`, `... - Copy.xlsx`, `... backup.xlsx`, `... backuip 207.xlsx`, etc.). These
  are a genuine safety net (each one is a real pre-edit backup), so don't blanket-delete — but a
  retention policy (keep the last N, or one per month, move the rest to a dated sub-archive) would
  cut real clutter here without losing recent recovery points.
- `config/E0E85740`, `config/E2F1A260`, `config/6AC9DA10` — orphaned binary blobs, hex filenames,
  zip/xlsx file signature, no code reference anywhere. Look like Office crash-recovery artifacts.
- `results/maintenance/*_copy.csv`, `*_copy 2.csv`, `display_names_qa copy.csv`,
  `display_names_qa_new.csv` — manual file-explorer-style duplicates.
- `results/logs/mapping_pipeline_<timestamp>*.log`, `mapping_pipeline_codex_*`,
  `mapping_pipeline_rollup_tree_nodes_*`, `mapping_pipeline_stage*_codex_*`, `*.pid`,
  `*.pid.txt`, `run_mapping_pipeline_*.ps1`, `stdin_pipe_test.*`, `stage_runs/*` — ad hoc manual
  run artifacts; only `results/logs/mapping_pipeline.log` (no timestamp) is current code output.
- `results/maintenance/logs/*` — same category, manual run logs from anchor validation,
  structural compilation, and inverted-conservation reruns.
- `results/common_esto/common_esto_comparison_wide_rebuilt.csv`,
  `qa_common_esto_partial_coverage_mapping_candidates_rebuilt.csv`,
  `results/common_esto/configurable_scopes_stage2.std{out,err}.log`,
  `configurable_scopes_stage3.std{out,err}.log` — manual rebuild/custom-scope run artifacts.
- `results/tree_structure/anchor_diagnostics/` (whole folder) — output of a superseded
  tree-walk anchor methodology, per `reconcile_anchor_validation.py`'s own docstring; replaced by
  `results/common_esto/anchor_reconciliation/`.
- `results/common_esto/inverted_conservation.building/` (whole folder) — **stronger evidence than
  the other items here**: `inverted_conservation_summary.csv` inside it is byte-size-identical
  (6,784 B) to the one in `results/common_esto/inverted_conservation/`, found via a Round-3
  filename-collision sweep across the whole zip listing. Very likely a true redundant duplicate
  from a repeated manual run with a typo'd/experimental `output_dir`, not a distinct variant —
  unlike `inverted_conservation_variant_verification/` (different size, plausibly genuine).
- `results/tree_structure/source_parent_anchor_MISSING_*.csv`, `*_SLICE*.csv`,
  `*_baseline_<date>*.csv` — older/manual output-format variants, zero current references.
- `results/missing_mapped_esto_rows/` (top-level, outside `results/maintenance/`) — stale
  duplicate of `results/maintenance/missing_mapped_esto_rows/` from an earlier code path.
- `codebase/mapping_code/` (whole folder) — a diverged duplicate "starter prototype" bundle,
  confirmed via `diff` against the live `codebase/mapping_tools/` versions of the same two
  scripts (517 vs 522, 815 vs 874 lines) — not identical, and its own README calls it a
  prototype targeting a different machine's Python path and the legacy workbook.
- Root-level: `Untitled-1.md` (raw console log dump duplicating `results/logs/mapping_pipeline.log`'s
  job), `old gent chat.txt` (saved agent chat transcript). **Exception — don't just archive this
  one:** `prompts 5-7.md` contains a real, apparently-uncaptured design rule (ignored
  sectors/fuels should be excluded via `config/mapping_issue_exception_sets.xlsx` rather than
  chased as mapping gaps) — fold that into `docs/special_rules_and_design_decisions.md` first,
  *then* archive the original file.

---

# 20. NEW TASK — identify near-duplicate diagnostic files and reduce duplication (not yet run)

**Goal:** several diagnostic files look like they're two versions of essentially the same check
— a filtered vs. unfiltered pair, a `qa_`-prefixed vs. unprefixed pair, a `_rebuilt` variant, or
multiple output-directory copies from repeated manual runs of the same standalone tool. Some of
these pairs genuinely serve different purposes and should both stay (just documented more
clearly); others are likely redundant and one side should be dropped from generation. This task
is to work out which is which — it has **not** been done yet, only flagged.

## Methodology (run against the main-PC repo's actual current files)

1. For each suspected pair/group (starter list below, but actively look for more — the pattern
   to search for is "two files whose names differ only by a qualifier: a filter word like
   `nonzero`/`allowed_matched`/`including_exceptions`, a `qa_` prefix, or a `_rebuilt`/`_new`/
   `_copy` suffix"), open both and compare:
   - Column headers — do they match exactly?
   - Row counts and file sizes — wildly different sizes usually means one is a strict subset/filtered
     view of the other (expected and fine); near-identical sizes with the same columns is a
     stronger signal of true redundancy.
   - A spot-check of a handful of rows — are the values actually the same, or does one carry
     extra derived columns/different scope?
2. **Classify each pair:**
   - **Different purpose, keep both** (e.g. a raw file and its nonzero-filtered companion) — but
     make sure the folder's `README.md` explains the relationship clearly (several already do,
     e.g. `results/maintenance/README.md`'s note on `unmapped_ninth_pairs.csv` vs.
     `unmapped_nonzero_ninth_pairs.csv`), so a future reader doesn't have to rediscover this.
   - **Genuinely redundant** — one is a strict, unexplained duplicate of the other (same columns,
     same rows, no scope difference). For these: stop generating the redundant one in code (find
     and remove/consolidate the producing call site), rather than just archiving the file, since
     otherwise it'll just reappear on the next pipeline run.
   - **Accumulating variants from manual reruns** (e.g. multiple `inverted_conservation*`
     directories) — decide on one canonical output location and either parameterize the script to
     overwrite it consistently, or make the variant suffix meaningful and documented (e.g. always
     include the run scope in the folder name) rather than accidental.
3. Record the decision in `docs/diagnostic_file_review_signals.md` (or wherever the main-PC repo
   keeps this doc after recreation) so the next audit doesn't start from scratch.

## Starter candidate list (from the zip snapshot — re-verify against current code and current files before acting)

| Group | Files | What's known so far |
|---|---|---|
| Total-check pair | `results/common_esto/common_esto_total_check.csv` vs. `qa_common_esto_total_check.csv` | Same apparent purpose (totals-preserved check) per code reading; only the `qa_`-prefixed one is named in `docs/improvement_todo.md`. Not yet confirmed whether both are written by the same step for a reason, or one is leftover. |
| Ninth unmapped-pairs pair | `results/maintenance/unmapped_ninth_pairs.csv` vs. `unmapped_nonzero_ninth_pairs.csv` (+ `_allowed_matched` variant) | The `nonzero` one is named in docs and is very likely the intended primary; the un-filtered one is 536 KB, substantial, never named — could be legitimately useful (full picture) or could be dropped since the filtered view supersedes it for practical review. |
| ESTO unmapped-pairs pair | `results/maintenance/unmapped_esto_pairs.csv` vs. `unmapped_nonzero_esto_pairs.csv` (+ `_allowed_matched` variant) | Same pattern as the ninth pair above. |
| Subtotal-mismatch trio | `results/maintenance/subtotal_mismatches.csv` (named in docs) vs. `subtotal_mismatches_including_exceptions.csv` (120 KB, undocumented) vs. `subtotal_mismatches_allowed_matched.csv` | Three related views of the same underlying check — worth documenting the exact relationship between all three explicitly, since right now only one is named anywhere. |
| `_rebuilt` variants | `results/common_esto/common_esto_comparison_wide.csv` vs. `common_esto_comparison_wide_rebuilt.csv`; `qa_common_esto_partial_coverage_mapping_candidates.csv` vs. `..._rebuilt.csv` | The `_rebuilt` suffix isn't produced by any current script (per `docs/results_folder_cleanup_candidates.md`'s "confirmed orphaned" analysis was actually only run on a subset — re-check these two specifically) — looks like a one-off manual regeneration for comparison against the standard output, likely archivable once confirmed stale rather than something to reconcile. |
| `results/tree_structure/` double-write | `esto_tree.csv`, `ninth_tree.csv`, `leap_tree.csv`, `common_esto_tree.csv`, `ninth_validation.csv`, `leap_validation.csv`, `common_esto_validation.csv` | Not two *different* files — the same filename gets written twice per run by two different code paths (Stage 0's `build_dataset_tree_structure.run_tree_structure_workflow()`, then Stage 3 inline). Already tracked as its own backlog item (§3a in `docs/improvement_todo.md`, recreated in section 17 below) — flagging here too since it's the same underlying "duplicate computation, unclear which version survives" problem. |
| Repeated manual-run variants | `results/common_esto/inverted_conservation/`, `inverted_conservation.building/`, `inverted_conservation_variant_verification/` | Three output directories from the same standalone script (`inverted_conservation_validation.py`) run manually with different `output_dir` arguments at different times. Consider standardizing on one canonical output path, or making the variant meaningful (name it after what's actually different about that run) instead of accumulating differently-named copies. |
| Config workbook backup pile | `config/archive/outlook_mappings_master.before_*`, `.maintenance_run_*` (~80 files spanning weeks) | Not pairwise duplicates but a duplication-over-time problem — see the retention-policy suggestion in section 19 above rather than treating each pair individually. |
| Validation-vs-rollup-validation pair (new, spotted during the re-verification pass) | `results/tree_structure/common_esto_validation.csv` vs. `common_esto_rollup_validation.csv` | Both are Common-ESTO-structure validation outputs from the same orchestration module, added in the same 586-line growth that also added `common_esto_validation_child_detail.csv`, `_issue_patterns.csv`, `_rollup_diagnosis.csv`, and `common_esto_source_frontier.csv`. Not yet checked whether `common_esto_rollup_validation.csv` is a genuinely distinct check (rollup-rule correctness vs. recursive-sum correctness) or a near-duplicate view of the same underlying mismatches — this whole cluster of 6 files is new territory for the deduplication task, not something the original audit looked at closely. |

---

# End of merged notes

That's everything written or substantially edited this session, plus the two new audit tasks
(sections 19–20) queued for the main-PC repo. If you're recreating these files by hand on the
main PC instead of syncing via git, use the "Where each section below actually lives" table near
the top as your file-path map, and strip the `# N. path (status)` headers and horizontal rules
when copying each section's content back into its real file. Sections 19 and 20 have no source
file to recreate — they're fresh work to do directly against that repo.
