# `docs/` index

If you're new to this repo, read in this order: root `README.md` → `mappings_system.md` →
`guide_outlook_mappings_master.md`. Everything else here is reference material or a working
backlog, not required reading up front.

## Work queue and handover

| File | What it covers |
|---|---|
| [`work_queue.md`](work_queue.md) | **Current work starts here.** Dated repository/worktree status, prioritized queue, and four-week handover plan. This is the controlling backlog — nothing else is. |
| [`cross_repository_handover_index.md`](cross_repository_handover_index.md) | Ownership boundary with `leap_dashboard` and `leap_initialisation`: produced/consumed files, schemas, refresh order, and failure ownership. |
| [`documentation_audit_20260728.md`](documentation_audit_20260728.md) | File-by-file Markdown audit with keep/update/archive actions, plus a dated verification addendum. |

## System design and reference

| File | What it covers |
|---|---|
| [`mappings_system.md`](mappings_system.md) | **Start here.** How the whole mappings system works — why it's structured the way it is, pipeline stages, code entry points, output files. |
| [`guide_outlook_mappings_master.md`](guide_outlook_mappings_master.md) | Practical editor's guide to `config/outlook_mappings_master.xlsx` — what to put in the cells, with a rollup deep-dive. |
| [`rollup_rules_system.md`](rollup_rules_system.md) | How the workbook's rollup-rule sheets get consumed by Stage 1/2 — for debugging relationship outputs. |
| [`special_rules_and_design_decisions.md`](special_rules_and_design_decisions.md) | The decision log — rules whose correct behaviour can't be derived from source data alone. Check here before assuming odd-looking behaviour is a bug. |
| [`workflow_inventory.md`](workflow_inventory.md) | Navigation guide for `codebase/` — which scripts are live pipeline vs. standalone tools vs. legacy. |
| [`QA plan.md`](QA%20plan.md) | The smoke-test / regression-verification plan for the pipeline. |

## Repo hygiene (2026-07-23 pass)

| File | What it covers |
|---|---|
| [`repo_data_slimdown_plan.md`](repo_data_slimdown_plan.md) | Exactly which `config/`/`data/`/`results/` files are required to run the pipeline (vs. safe to leave out), derived from tracing every input path in the code. |
| [`results_folder_cleanup_candidates.md`](results_folder_cleanup_candidates.md) | Files/folders that look stale, orphaned, or duplicated across `results/`, `config/`, and `codebase/` — flagged for future cleanup, nothing acted on yet (some deliberately left for a separate diagnostic-file-consolidation task — see that file's note). |
| [`archive_log.md`](archive_log.md) | Running record of what's been moved (never deleted) into `docs/archive/`, a top-level `archive/`, or a gitignored `_archive_<date>/` subfolder, and why. |

See also `results/README.md` (and the `README.md` in each `results/` subfolder), `config/README.md`,
and `data/README.md` — placed directly in those folders so the guide is right there when you
open them, rather than only discoverable from here.

Not yet created: a dedicated `docs/diagnostic_file_review_signals.md` tracing which
`results/common_esto/`/`results/maintenance/` diagnostic CSVs are actually consumed vs. never
read — that work is intentionally being designed together with a separate anchor-validator
data-reliability-flag task (see `docs/prompts/` for that design task once it lands), rather than
done in isolation here.

## Backlog

| File | What it covers |
|---|---|
| [`improvement_todo.md`](improvement_todo.md) | **Historical backlog — not the controlling queue.** Source material for semantic mapping issues, the canonical-workbook migration, hierarchy validation, documentation gaps, and `results/` cleanup candidates. Its live items are represented in [`work_queue.md`](work_queue.md); go there for current status. Note that `codebase/mapping_tools/build_no_data_mapping_rows.py` still cites this file's item 8 — see MAPQ-019 before archiving it. |

## `prompts/` and `archive/`

- `prompts/` — active or pending multi-step agent prompts (plan-first implementation tasks,
  investigation prompts). Per `AGENTS.md`: once the work a prompt describes is complete, it
  should move out of here into `archive/`. If a file's been sitting in `prompts/` a long time,
  it's worth checking whether it's actually done and just hasn't been moved yet.
- `archive/` — completed prompt packs and archived root-level scratch files, often bundled with
  their own findings/status/TODO notes (see `archive/common_esto_lineage_validation/` for the
  pattern, and `archive/2026-07-23_repo_cleanup/` for this pass's archived root-level files).
  Historical record, not something to read routinely.
