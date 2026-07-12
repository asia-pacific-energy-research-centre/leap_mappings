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

Reviewed on 2026-07-10.

| Prompt | Type | Status | Basic Details | Notes Before Use |
|---|---|---|---|---|
| `buildings_ninth_counterpart_gap_prompt.md` | Investigation | Valid, active | Investigates whether `Buildings` and `Buildings/Services` NINTH counterpart gaps are expected one-sided granularity limits or missing mappings. | Referenced inverted-conservation, structural-artifact, tree, and workbook paths exist. Do not edit the workbook until the gap is classified fuel-by-fuel or as a justified group. |
| `investigate_demand_sector_parent_child_mismatches.md` | Investigation | Complete; archive pending | Report-only diagnosis of demand-sector parent/child mismatches. Companion findings file now contains detailed verdicts and proposed fixes/exceptions. | Do not rerun as-is unless the findings are challenged by newer outputs. Archive this prompt with `investigate_demand_sector_parent_child_mismatches_FINDINGS.md` after preserving the current uncommitted findings edits. |
| `investigate_demand_sector_parent_child_mismatches_FINDINGS.md` | Findings report | Complete; archive pending | Contains the completed analysis for 14 Industry, 14.03 Manufacturing, and 15 Transport parent/child mismatch families. | File had pre-existing uncommitted edits at review time, so it was not moved by this guide update. Use it as context for follow-up implementation prompts. |
| `regen_common_esto_comparison_fast_path_prompt.md` | Implementation | Partially stale, still useful | Core fast-path workflow exists in `codebase/regen_common_esto_comparison_fast_path_workflow.py`, with coverage in `tests/test_common_esto_fast_path.py`. | Commits `352e6e2` and `e868330` show the main work is complete. The optional dashboard hook names `codebase/common_esto_dashboard_workflow.py`, which does not exist in this repo; rewrite or archive after deciding whether any follow-up remains. |
| `row_level_lineage_for_common_esto_prompt.md` | Implementation | Valid, active, high value | Adds additive lineage side outputs at the LEAP/NINTH-to-ESTO conversion loss points and the ESTO-component-to-common-row loss point. | `return_lineage` and lineage output constants are not present in code yet. Do not revive `apply_partitioned_common_esto.py`; capture lineage from the existing production frames. |
| `run_mapping_pipeline_future_prompt.md` | Long-running execution | Valid, active | Reusable procedure for running `codebase/run_mapping_pipeline.py`, preserving workbook safety, logs, polling cadence, QA reporting, and output links. | Use only when the user actually wants a current pipeline run. Check whether Stage 0 writes the workbook before launching. |

## Recommended Tackling Order

1. `row_level_lineage_for_common_esto_prompt.md`
   - Independent, useful for dashboard/debuggability, and should be implemented from existing production frames.
2. `buildings_ninth_counterpart_gap_prompt.md`
   - Investigation-only; use it to separate genuine mapping gaps from permanent granularity differences.
3. `run_mapping_pipeline_future_prompt.md`
   - Run after code/workbook changes that justify refreshed outputs.
4. `regen_common_esto_comparison_fast_path_prompt.md`
   - Do not rerun as a full implementation prompt. Rewrite or archive after deciding whether the optional dashboard hook is real.
5. `investigate_demand_sector_parent_child_mismatches.md`
   - Do not tackle as an active prompt; use the findings report to create narrower follow-up fix prompts.

## Recently Archived

- `register_rollup_groups_as_tree_nodes_prompt.md` - completed and verified by commits `802858a`, `3ff2684`, and the later handoff update `23d9865`.
- `explore_parent_level_own_use_comparison_rows.md` and `explore_parent_level_own_use_comparison_rows_FINDINGS.md` - report-only design exploration completed 2026-07-10.
- `unify_rollup_rules_prompt.md` - completed and verified by the full mapping pipeline run on 2026-07-12; NINTH unknown target QA is clean and legacy rolled target counts are zero.

## Known Folder Issues

- `docs/archive/` is ignored by `.gitignore` (`**/archive`), so archived prompt files must be force-added.
- Several prompt files contain mojibake artifacts from earlier encoding issues.
- Some prompts still contain point-in-time line numbers or dated assumptions; verify with `rg` before acting.
- `regen_common_esto_comparison_fast_path_prompt.md` is mostly superseded by committed code but has a newer optional hook referencing a missing file.
- `investigate_demand_sector_parent_child_mismatches_FINDINGS.md` and `regen_common_esto_comparison_fast_path_prompt.md` had pre-existing uncommitted edits during this review.
- `row_level_lineage_for_common_esto_prompt.md` was untracked during this review and should be intentionally added or removed by whoever owns it.
