# Documentation audit — 2026-07-28

## Scope and method

This audit covers all 74 tracked Markdown files found by
`git ls-files '*.md'`:

- 50 files outside `docs/archive/`;
- 24 files already under `docs/archive/`.

It excludes 206 untracked Markdown files under `.codex/` and `node_modules/`
because they are tool/dependency content rather than project documentation.

The review compared each active file's purpose and stated status with:

- local `master`, `origin/master`, and recent commit history;
- all current `leap_mappings` worktrees and their clean/dirty state;
- prompt-folder archival rules;
- current modified documentation;
- a local relative-link check.

The audit is a classification pass, not permission to archive or rewrite files
that overlap unintegrated worktree changes.

## Main findings

1. `docs/prompts/AGENTS.md` is not a reliable current inventory. It was last
   reviewed on 2026-07-23 and contradicts later commits and even resolution
   notes inside several prompts.
2. At least five completed prompt packs remain in the active prompt folder.
3. `docs/prompts/common_esto_lineage_validation/README.md` is an orphaned
   active-folder index: the prompt files it lists were already moved to
   `docs/archive/common_esto_lineage_validation/`.
4. `docs/improvement_todo.md` remains useful source material, but its latest
   full triage predates major ESTO Extended, output storage, anchor validation,
   and coverage-audit work. It should become a historical backlog input rather
   than a second controlling queue.
5. `docs/REPO_CLEANUP_AND_NAVIGATION_NOTES.md` is a 1,000+ line execution
   snapshot that duplicates large portions of current docs. It should be
   archived after its still-open items are represented in `work_queue.md`.
6. The local-link check found one genuine missing target:
   `docs/REPO_CLEANUP_AND_NAVIGATION_NOTES.md` links to the nonexistent
   `docs/diagnostic_file_review_signals.md`. The two reported `QA%20plan.md`
   cases are URL-decoding false positives because `docs/QA plan.md` exists.
7. Several active docs contain mojibake. Encoding cleanup should be mechanical,
   reviewed, and committed separately from semantic rewrites.

## Active-file disposition

| File | Classification | Action |
|---|---|---|
| `AGENTS.md` | Canonical instructions | Keep. Update only when repository-wide agent rules genuinely change. |
| `archive/2026-07-23_repo_cleanup/mapping_code/README_dashboard_mapping_starter.md` | Misplaced historical artifact | Verify no consumer depends on this nonstandard archive path, then move under the tracked `docs/archive/2026-07-23_repo_cleanup/` structure or document why it remains here. |
| `config/README.md` | Navigation reference | Keep; revalidate after canonical-workbook cleanup. |
| `data/README.md` | Navigation reference | Keep; revalidate after data slim-down decisions. |
| `docs/archive_log.md` | Canonical archive record | Keep and update in the same commit as any quarantine/archive move. |
| `docs/guide_outlook_mappings_master.md` | Handover-critical guide | Keep; add a short current schema/version verification date and link it from the future handover start page. |
| `docs/improvement_todo.md` | Stale parallel backlog | Preserve as source history, but point readers to `docs/work_queue.md` as the controlling queue. Archive or rename it after every live item is represented in the new queue. |
| `docs/interactive_anchor_tree_explorer_findings.md` | Completed design exploration with possible dashboard follow-up | Pair with its prompt; archive after confirming any implementation follow-up is recorded in the dashboard queue. |
| `docs/mappings_system.md` | Canonical system reference | Keep. Add the missing compact diagram, glossary, worked example, scope definitions, and validation-severity explanation through MAPQ-014. |
| `docs/prompts/AGENTS.md` | Stale active-prompt inventory | Rewrite after branch reconciliation. It must reflect the 2026-07-28 statuses and list every active prompt exactly once. |
| `docs/prompts/anchor_validator_fixes_findings_20260722.md` | Completed historical findings | Archive with the methodology/follow-on chain after all still-live issues are linked to current queue IDs. Do not carry its old row counts into current decisions. |
| `docs/prompts/anchor_validator_fixes_findings_20260723.md` | Completed historical findings with extracted follow-up | Archive after verifying the mirror-row-gap and reliability follow-ups are represented by MAPQ-011/MAPQ-012. The prompt guide's claim that this file is not on `master` is false. |
| `docs/prompts/common_esto_lineage_validation/README.md` | Orphaned index | Move into the existing archived prompt-pack folder or delete it from the active folder after confirming the archived pack already has the needed context. |
| `docs/prompts/configurable_comparison_scopes_prompt.md` | Completed prompt | Archive. Its own 2026-07-23 resolution records implementation and 49 passing targeted tests. Keep any stale structural-artifact regeneration as a separate bounded queue item if it still reproduces. |
| `docs/prompts/data_reliability_flag_and_diagnostic_consolidation_design_20260723.md` | Partially superseded design | Keep temporarily. Reconcile it with later exception curation, grouped validation, compressed storage, output contracts, and dashboard health reporting under MAPQ-012; then archive the superseded design. |
| `docs/prompts/esto_extended_dataset_design.md` | Completed design; implementation advanced | Keep only until MAPQ-007 produces a current implementation/status note, then archive with the original handoff prompt. |
| `docs/prompts/esto_extended_dataset_prompt.md` | Original design prompt, completed | Archive with the design note after current ESTO Extended follow-up work is separately represented. |
| `docs/prompts/holistic_mapping_system_stocktake_findings_20260722.md` | Completed/superseded findings | Archive with its prompt. Current queue and later baselines supersede its counts. |
| `docs/prompts/holistic_mapping_system_stocktake_prompt.md` | Completed prompt | Archive with findings. |
| `docs/prompts/interactive_anchor_tree_explorer_prompt.md` | Completed exploration prompt | Archive with `docs/interactive_anchor_tree_explorer_findings.md` after recording any dashboard implementation task. |
| `docs/prompts/investigate_anchor_validation_methodology.md` | Superseded origin prompt | Archive with the two findings reports after live follow-ups are linked to MAPQ-011/MAPQ-012. |
| `docs/prompts/investigate_anchor_validator_memory_prompt.md` | Completed prompt | Archive after confirming patch-equivalent commit `03c9405` is the intended `master` integration. Remove the stale worktree separately. |
| `docs/prompts/investigate_demand_sector_parent_child_mismatches.md` | Completed prompt | Archive with findings. |
| `docs/prompts/investigate_demand_sector_parent_child_mismatches_FINDINGS.md` | Completed findings | Archive. The file itself says nothing remains actionable, and later commits reduced/resolved the listed families. |
| `docs/prompts/investigate_ninth_09_total_transformation_reconciliation.md` | Historical investigation with one reliability follow-up | Extract the current narrow residual into MAPQ-012, then archive the long prompt rather than treating old failure counts as current. |
| `docs/prompts/investigate_standalone_rollup_validation.md` | Completed prompt | Archive immediately after branch reconciliation; its own resolution cites implemented and verified work. |
| `docs/prompts/mirror_row_gap_exception_curation_handoff_20260727.md` | Active paused handoff | Keep. Add queue ID MAPQ-011 and resume only after its clean-window gate. |
| `docs/prompts/regen_common_esto_comparison_fast_path_prompt.md` | Mostly completed, reusable fragments remain | Replace with a short current runbook section or archive after confirming the optional dashboard hook and structural-artifact regeneration status. |
| `docs/prompts/review_non_expanding_vs_detached_rollups_prompt.md` | Active review prompt | Keep and execute as MAPQ-010. |
| `docs/prompts/run_mapping_pipeline_future_prompt.md` | Active reusable run procedure | Keep, but synchronize it with compressed outputs, output-contract publication, workbook hashing, and current process-naming rules before MAPQ-005. |
| `docs/prompts/whole_work_queue_smart_agent_prompt.md` | Superseded orchestration prompt | Archive after adding a short pointer to `docs/work_queue.md`; its phases predate substantial work landed on 2026-07-24 through 2026-07-28. |
| `docs/QA plan.md` | Inadequate active QA reference | Expand or merge into the handover runbook. It is too short to represent the current pipeline, contracts, and validation gates. |
| `docs/README.md` | Canonical documentation index | Keep and update now to link the queue and audit; refresh again after prompt archival. |
| `docs/REPO_CLEANUP_AND_NAVIGATION_NOTES.md` | Completed execution snapshot plus duplicated backlog | Extract any unique open item, fix/remove the broken link, then archive. Do not maintain this in parallel with the queue and focused cleanup docs. |
| `docs/repo_data_slimdown_plan.md` | Active storage plan | Keep until MAPQ-013 reconciles it with compression and output-contract work, then mark complete or archive. |
| `docs/results_folder_cleanup_candidates.md` | Active cleanup evidence; locally modified | Keep. Do not overwrite the current uncommitted verification pass. Resolve the blocked `missing_mapped_esto_rows` comparison before moving that folder. |
| `docs/results_output_storage.md` | Canonical storage reference with newer worktree edits | Keep. Reconcile the clean output-contract worktree before further edits. |
| `docs/rollup_rules_system.md` | Canonical technical reference; locally modified | Keep and preserve the current uncommitted demand-scope edit. Revalidate after MAPQ-010. |
| `docs/source_coverage_audit.md` | Canonical workflow reference; locally modified | Keep and preserve the current uncommitted demand-scope edit. Revalidate after MAPQ-005/MAPQ-009. |
| `docs/special_rules_and_design_decisions.md` | Canonical decision log | Keep. Resolve open cross-repository frontier ownership under MAPQ-021 and add dated end-to-end run reports. |
| `docs/workflow_inventory.md` | Canonical navigation reference | Keep; re-audit after worktree integration and notebook-safe orchestration work. |
| `README.md` | Repository entry point | Keep; add a concise handover/start-here link after MAPQ-014 creates the final structure. |
| `results/common_esto/README.md` | Generated-output reference | Keep; update after output-contract integration and a clean baseline. |
| `results/for_colleagues/README.md` | Generated-output reference | Keep; verify current comparison-scope names and producer path. |
| `results/logs/README.md` | Generated-output reference | Keep; ensure it documents the single canonical log plus archive policy. |
| `results/maintenance/README.md` | Generated-output reference | Keep; update after cleanup and canonical-workbook migration. |
| `results/mapping_graph_index/README.md` | Generated-output reference | Keep; revalidate producer and current files. |
| `results/mapping_relationships/README.md` | Generated-output reference with unmerged guard edit | Keep; reconcile the source-identity guard worktree update. |
| `results/README.md` | Generated-output navigation index | Keep; update after MAPQ-003/MAPQ-013. |
| `results/tree_structure/README.md` | Generated-output reference | Keep; update after old tree artifacts are quarantined and the clean baseline is produced. |

## Existing archived Markdown

The 24 files already under `docs/archive/` are correctly historical and should
remain immutable except for clear factual corrections. Their presence is not
active work:

- `docs/archive/2026-07-23_repo_cleanup/prompts_5-7.md`
- `docs/archive/2026-07-23_repo_cleanup/Untitled-1.md`
- `docs/archive/buildings_ninth_counterpart_gap_FINDINGS.md`
- `docs/archive/buildings_ninth_counterpart_gap_prompt.md`
- `docs/archive/common_esto_lineage_validation/01_shared_rollup_and_hierarchy_resolver.md`
- `docs/archive/common_esto_lineage_validation/02_compile_structural_mapping_artifacts.md`
- `docs/archive/common_esto_lineage_validation/03_partitioned_value_application_and_lineage.md`
- `docs/archive/common_esto_lineage_validation/04_anchor_validation_from_lineage.md`
- `docs/archive/common_esto_lineage_validation/05_full_integration_benchmark_and_documentation.md`
- `docs/archive/common_esto_lineage_validation/06_reconcile_anchor_validation_against_conversion_outputs.md`
- `docs/archive/common_esto_lineage_validation/07_leap_base_conservation_validation_flavor_a.md`
- `docs/archive/common_esto_lineage_validation/PROMPT5_STATUS_AND_ISSUES.md`
- `docs/archive/common_esto_lineage_validation/TODO.md`
- `docs/archive/explore_parent_level_own_use_comparison_rows.md`
- `docs/archive/explore_parent_level_own_use_comparison_rows_FINDINGS.md`
- `docs/archive/fix_common_esto_rollup_resolution_prompt.md`
- `docs/archive/fix_ninth_power_sector_rollup_emission_prompt.md`
- `docs/archive/implement_non_expanding_rollups_and_source_fallbacks_prompt.md`
- `docs/archive/register_rollup_groups_as_tree_nodes_prompt.md`
- `docs/archive/row_level_lineage_for_common_esto_prompt.md`
- `docs/archive/side_prompt_esto_rollup_expansion.md`
- `docs/archive/stage3_performance_optimization_prompt.md`
- `docs/archive/stage3_performance_optimization_REPORT.md`
- `docs/archive/unify_rollup_rules_prompt.md`

## Documentation cleanup sequence

1. Reconcile the unmerged worktrees so active documentation does not erase
   useful branch-only status notes.
2. Update `docs/prompts/AGENTS.md` from repository evidence.
3. Archive the clearly completed prompt packs in small, coherent commits.
4. Move the orphaned Common ESTO prompt-pack README into its archived folder.
5. Convert `docs/improvement_todo.md` into a historical pointer once its live
   items are confirmed in `docs/work_queue.md`.
6. Extract unique items from
   `docs/REPO_CLEANUP_AND_NAVIGATION_NOTES.md`, fix its broken link, and archive
   the snapshot.
7. Reconcile the storage/cleanup docs with the output-contract worktree and a
   current pipeline run.
8. Perform a separate encoding-normalization pass for mojibake; do not mix that
   mechanical diff with substantive documentation changes.
9. Build the concise handover set in MAPQ-014 and test it from a clean checkout.
