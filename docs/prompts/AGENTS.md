# Prompt Folder Guide

`docs/prompts/` is for active, reusable prompts only. A prompt belongs here while it describes pending work, a reusable run procedure, or an investigation that has not yet been reported and committed.

When a prompt's work is complete, tested where applicable, and committed, move the prompt to `docs/archive/`. Completed prompts must not remain in this folder. Update this inventory in the same commit that adds, archives, or supersedes a prompt.

## Adding Prompts

- Add or update the inventory row in this file in the same commit.
- State the task type, scope, prerequisites, expected outputs, validation, and stop conditions.
- Name the file for the work, not the agent.
- State workbook, sheet, and pipeline stage precisely.
- Distinguish design decisions from implementation tasks.
- Require source workbook/schema verification before code edits.
- Require `git status --short` and preservation of unrelated changes.
- Avoid stale line numbers where `rg` can find the function or call site.
- Avoid prompts that combine mapping design decisions with production runs.

## Archiving Prompts

- Archive only prompts with clear evidence that the work is complete or superseded.
- Move completed prompt files from `docs/prompts/` to `docs/archive/`.
- Move companion findings/status files with the prompt when they are part of the completed work.
- If `docs/archive/` is ignored, force-add only the archive files that belong to the task.
- Do not archive prompts whose evidence is ambiguous; mark them as stale or needing review instead.

## Current Inventory

Reviewed on 2026-07-23. The 2026-07-13 review only covered 4 of the (now) 13
files in this folder; the rows below fill in the other 9, found stale during a
docs-wide scan for outstanding work. Status is best-available from filename/
header conventions and cross-referencing other docs, not a full fresh
investigation of each — treat any row without a specific commit/date citation
as needing verification before acting on it.

| Prompt | Type | Status | Basic Details | Notes Before Use |
|---|---|---|---|---|
| `investigate_demand_sector_parent_child_mismatches.md` | Investigation | Complete; archive pending | Report-only diagnosis of demand-sector parent/child mismatches. Companion findings file now contains detailed verdicts and proposed fixes/exceptions. | Do not rerun as-is unless the findings are challenged by newer outputs. Archive this prompt with `investigate_demand_sector_parent_child_mismatches_FINDINGS.md` after preserving the current uncommitted findings edits. |
| `investigate_demand_sector_parent_child_mismatches_FINDINGS.md` | Findings report | Complete; archive pending | Contains the completed analysis for 14 Industry, 14.03 Manufacturing, and 15 Transport parent/child mismatch families (LEAP double-counting, NINTH coverage gaps, jet-fuel double-count). | Diagnosis only — no corresponding fix commits found in git log as of 2026-07-23. Queued as its own follow-up task (verify still reproduces before fixing; workbook has changed since this was written). |
| `regen_common_esto_comparison_fast_path_prompt.md` | Implementation | Partially stale, still useful | Core fast-path workflow exists in `codebase/regen_common_esto_comparison_fast_path_workflow.py`, with coverage in `tests/test_common_esto_fast_path.py`. | Commits `352e6e2` and `e868330` show the main work is complete. The optional dashboard hook names `codebase/common_esto_dashboard_workflow.py` — that file exists, but in the sibling `leap_dashboard` repo, not here; rewrite the note to clarify the cross-repo boundary rather than "does not exist," or archive after deciding whether any follow-up remains. |
| `run_mapping_pipeline_future_prompt.md` | Long-running execution | Valid, active | Reusable procedure for running `codebase/run_mapping_pipeline.py`, preserving workbook safety, logs, polling cadence, QA reporting, and output links. | Use only when the user actually wants a current pipeline run. Check whether Stage 0 writes the workbook before launching. |
| `investigate_anchor_validation_methodology.md` | Investigation (resume prompt, "4a") | Substantially executed, ongoing | Origin prompt for the whole anchor-validator fix chain; substantively carried forward by `anchor_validator_fixes_findings_20260722.md` and `anchor_validator_fixes_findings_20260723.md` across multiple sessions. | Not archived because follow-on work is still active (see next two rows and the queued mirror-row-gap design task); do not treat as a fresh starting point, read the two findings docs first. |
| `anchor_validator_fixes_findings_20260722.md` | Findings report | Complete for its own session; several flagged residuals never followed up | Session that fixed anchor-validator double-counting/frontier-descent bugs. Flagged several residuals as explicitly "not investigated this session" (passenger-road skip bucket ~66k rows, ESTO `10 Losses`/`10.01 Own Use`, product-axis `frontier_rows_absent`, `12_solar` allocation gap, a silent-exception logging bug). | Row counts in this doc are stale relative to 2026-07-23's baseline (760 failed dataset-wide) — the residuals above are queued as their own re-triage task; several may already be resolved by later work. |
| `anchor_validator_fixes_findings_20260723.md` | Findings report | Active — lives on branch `claude/anchor-validator-fixes-ee04bc`, not yet on `master` | Follow-on session: fixed the "10.01 Own Use" shared-frontier-group signature bug (connected-components grouping, commit `c6772a9` on that branch), added one workbook mapping row (now on `master`, commit `9b5e31d`), and did substantial real-data tracing on the "mirror-row gap" (NINTH's own data disagreeing with itself) without a safe code fix — that's now a separately queued design task (propagate a flag rather than guess/substitute a corrected value). | This file does not exist on `master` yet — it's only in the `anchor-validator-fixes-ee04bc` worktree. Decide whether/when to merge that branch's validator-code commits to `master`, separate from this housekeeping pass. |
| `holistic_mapping_system_stocktake_prompt.md` | Investigation | Complete; archive pending | Handoff prompt for a whole-system stocktake before further local fixes. | Paired with the findings doc below; archive together once confirmed no further follow-up is pending from it beyond what's already been split into other prompts. |
| `holistic_mapping_system_stocktake_findings_20260722.md` | Findings report | Complete (2026-07-22) | Stocktake findings — informed the candidate-mapping-gap detector work referenced in `anchor_validator_fixes_findings_20260723.md` (which found the stocktake's own candidate list was built on inflated pre-fix data and mostly evaporated once corrected). | Treat its specific candidate/row counts as superseded by the 2026-07-23 corrected-baseline rerun. |
| `investigate_ninth_09_total_transformation_reconciliation.md` | Investigation | Re-triaged 2026-07-24; reliability attribution pending | The current Stage 3 baseline has one NINTH flow-axis residual (`01_AUS`, target 2043, electricity; 0.382770 PJ), not the historical thousands of rows. | The residual is at the power-sector / hydrogen-transformation boundary and is a NINTH source-internal consistency case, not a detached-rollup regression or mapping candidate. Do not add a workbook exception; resolve only through the separate reliability-flag design after its dashboard-meaning gate. |
| `investigate_standalone_rollup_validation.md` | Investigation (resume prompt) | **Complete (2026-07-21)** — has its own "Resolution" note at the top of the file | Implemented the step-3 design: NON_EXPANDING/DETACHED rollup subtotals excluded from the ordinary recursive validator; a dedicated contributor-based rollup validator added. | Per this folder's own archiving rule ("completed prompts must not remain in this folder"), this should be archived to `docs/archive/` — left in place during this housekeeping pass since archiving wasn't in scope, but it's the most overdue archival candidate in this table. |
| `configurable_comparison_scopes_prompt.md` | Implementation (design + rename) | Not started | Make comparison scopes configurable; give `esto_leap` genuine non-NINTH-influenced granularity (currently all 4 scopes produce byte-identical `common_row_id` sets). | Oldest prompt in this folder (last touched 2026-07-14) — re-verify the core premise still holds before implementing; queued as its own scoping task. |
| `esto_extended_dataset_prompt.md` | Design (gates implementation) | Not started | Scopes a new "ESTO extended" dataset/detail extension; explicitly requires a design note (`esto_extended_dataset_design.md`) before any implementation. | The gating design note does not exist yet. Queued as its own task — produce the design note first, do not implement directly. |
| `whole_work_queue_smart_agent_prompt.md` | Master implementation prompt | Ready | End-to-end smart-agent handoff covering source-coverage candidates, clean Stage 1–3 baseline, anchor reliability flags, semantic review queues, canonical migration, and workflow/documentation cleanup. | Use as an orchestrating prompt, not as permission to make ambiguous workbook or dashboard decisions without review. |

| `investigate_anchor_validator_memory_prompt.md` | Investigation + performance fix | Active | Profile and reduce the `MemoryError` that skipped the latest source-parent anchor validation, without changing validation coverage or semantics. | The dashboard currently displays zero failures for this skipped run; do not treat that as a clean anchor result. Requires real-data parity checks and a successful full validation before completion. |

## Recommended Tackling Order

1. `run_mapping_pipeline_future_prompt.md`
   - Run after code/workbook changes that justify refreshed outputs, including the
     `esto_rollup_rules` fix proposed in the archived
     `buildings_ninth_counterpart_gap_FINDINGS.md`, once reviewed.
2. `regen_common_esto_comparison_fast_path_prompt.md`
   - Do not rerun as a full implementation prompt. Rewrite or archive after deciding whether the optional dashboard hook is real.
3. `investigate_demand_sector_parent_child_mismatches.md`
   - Do not tackle as an active prompt; use the findings report to create narrower follow-up fix prompts.

## Recently Archived

- `fix_ninth_power_sector_rollup_emission_prompt.md` - implemented 2026-07-16: `apply_ninth_to_esto_conversion.py` now applies the NON_EXPANDING subset of `ninth_rollup_rules` via `apply_source_rollups` before the ESTO merge, so NINTH emits the `09.01-09.02 Power sector` aggregate (37,928 rows, was 0). Verified against `common_esto_validation.csv`: the flow no longer appears in `missing_expected_children` for the PRC/coal case, and the parent-vs-children residual is ≈-2,950 (matches the documented post-Fix-B target, not the pre-fix ≈-180,058 gap). Full pipeline re-run and dashboard spot-check (acceptance items 3 and 5) were not re-verified after this commit.
- `implement_non_expanding_rollups_and_source_fallbacks_prompt.md` - implemented and verified 2026-07-13: non-expanding rollups (no graph edges, flagged subtotal common rows, derived ESTO subtotal rows), `config/source_branch_fallback_rules.csv` interim preflight, `config/all_demand_aggregated_components.csv` overlap warning, suppressed-edge QA, focused tests, and Stage 1-3 pipeline run.
- `register_rollup_groups_as_tree_nodes_prompt.md` - completed and verified by commits `802858a`, `3ff2684`, and the later handoff update `23d9865`.
- `explore_parent_level_own_use_comparison_rows.md` and `explore_parent_level_own_use_comparison_rows_FINDINGS.md` - report-only design exploration completed 2026-07-10.
- `unify_rollup_rules_prompt.md` - completed and verified by the full mapping pipeline run on 2026-07-12; NINTH unknown target QA is clean and legacy rolled target counts are zero.
- `row_level_lineage_for_common_esto_prompt.md` - completed and verified by focused tests, full tests, and real `data_convert,3` lineage reconciliation on 2026-07-12.
- `buildings_ninth_counterpart_gap_prompt.md` and `buildings_ninth_counterpart_gap_FINDINGS.md` - investigation completed 2026-07-13; all 142 gap rows classified `rollup_or_hierarchy_duplicate` with one proposed `esto_rollup_rules` fix (not yet applied — needs human review before pasting into the workbook).

## Known Folder Issues

- `docs/archive/` is ignored by `.gitignore` (`**/archive`), so archived prompt files must be force-added.
- Several prompt files contain mojibake artifacts from earlier encoding issues.
- Some prompts still contain point-in-time line numbers or dated assumptions; verify with `rg` before acting.
- `regen_common_esto_comparison_fast_path_prompt.md` is mostly superseded by committed code but has a newer optional hook referencing a missing file.
- `investigate_demand_sector_parent_child_mismatches_FINDINGS.md` and `regen_common_esto_comparison_fast_path_prompt.md` had pre-existing uncommitted edits during this review.
