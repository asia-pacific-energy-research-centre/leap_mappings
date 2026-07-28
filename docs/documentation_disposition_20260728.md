# Markdown documentation disposition — 2026-07-28

## Scope and decision rules

This is the exhaustive disposition register for the 90 Markdown files tracked
at the start of the pass. Every original path appears exactly once below.

The review compared document claims with the current file tree, local
`master`, `origin/master`, worktree state, recent commits, active code/config
symbols, prompt-resolution notes, inbound links, and the repository's prompt
archive policy. Generated result values were treated as dated evidence unless
a current run proved otherwise.

Decision meanings:

- **KEEP** — current canonical/reference material or useful dated evidence;
- **UPDATE** — retained and corrected in this pass;
- **ARCHIVE** — completed/superseded content moved without deletion;
- **KEEP-HISTORICAL** — already correctly archived; do not make it active;
- **DEFER** — useful active material with a user-owned edit that this pass did
  not overwrite.

No document was deleted and no unique information was intentionally removed.
Archived prompts retain their original instructions, counts, findings, and
commit evidence; current navigation now prevents readers from treating them as
fresh work.

## Disposition summary

| Decision | Count |
|---|---:|
| KEEP | 25 |
| UPDATE | 20 |
| ARCHIVE | 20 |
| KEEP-HISTORICAL | 24 |
| DEFER | 1 |
| **Total** | **90** |

## Active and reference documentation

| Original file | Role, evidence, and unique information | Decision / action |
|---|---|---|
| `AGENTS.md` | Canonical repository instructions; unique safety, workbook, economy-code, and cross-repo rules. Two local paths were absent and the baseline-seed section actually belongs to the sibling initialisation repo. | **UPDATE** — corrected the maintenance path, retired transfer-script instruction, and sibling ownership. |
| `README.md` | Repository entry point and concise Stage 0–3 overview. Its “suggested improvements” were completed by the handover set. | **UPDATE** — replaced the stale suggestions with maintained handover links. |
| `config/README.md` | Config ownership and required-input navigation. Named deleted scratch variants and a fixed set of changing Office recovery filenames. | **UPDATE** — current artifact classes and review-workbook status. |
| `data/README.md` | Current 2025/2024 ESTO and 9th input inventory; matches live mapping defaults. | **KEEP**. |
| `docs/archive_log.md` | Recovery record for tracked and gitignored moves. | **UPDATE** — recorded every preservation move in this pass. |
| `docs/cross_repository_handover_index.md` | Dated evidence snapshot of ownership, contracts, local-only risk, and handover dependencies. Maintained contracts now live under `docs/handover/`. | **KEEP** as explicitly dated evidence. |
| `docs/diagnostic_file_review_signals.md` | Status/navigation placeholder that explicitly says the detailed diagnostic-consumption study is incomplete. | **KEEP**; avoids the former broken historical link without overstating completion. |
| `docs/documentation_audit_20260728.md` | Initial 74-file audit and same-day verification addendum; useful decision provenance but no longer exhaustive. | **UPDATE** — historical banner points to this 90-file register. |
| `docs/esto_extended_category_creation_considerations.md` | Current working rules for stable ESTO Extended categories and mapping review. | **KEEP**; status is already provisional/working. |
| `docs/esto_extended_delta_storage_design.md` | Focused exact-delta storage design tied to implemented/prototyped delta work. | **KEEP**; implementation status remains visible in the queue/worktree. |
| `docs/guide_outlook_mappings_master.md` | Handover-critical workbook editing guide, safeguards, rollup fields, and QA practice. | **UPDATE** — corrected two completed-prompt archive paths; workbook sheet-renaming decisions remain queued rather than silently rewritten here. |
| `docs/handover/README.md` | Level-1 start-here, glossary, repository chooser, and worked example. | **KEEP**. |
| `docs/handover/agent_operations_guide.md` | Cross-repo operational runbook, mutation boundaries, recovery, and validation routing. | **KEEP**. |
| `docs/handover/cross_repository_data_contracts.md` | Maintained producer/consumer contracts, keys, staleness, provenance, and coordinated changes. | **KEEP**. |
| `docs/handover/end_to_end_system_guide.md` | Detailed end-to-end architecture and real USA natural-gas trace. | **KEEP**. |
| `docs/handover/mapping_pipeline_agent_guide.md` | Exact mapping rerun/validation/human-stop guidance. | **KEEP**. |
| `docs/handover/mapping_pipeline_guide.md` | Reader-friendly Stage 0–3 mapping guide. | **KEEP**. |
| `docs/improvement_todo.md` | Older semantic backlog with unique rationale and a live code citation to item 8; point-in-time statuses are stale. | **UPDATE** — prominent historical/not-controlling banner; content retained. |
| `docs/mappings_system.md` | Canonical deep system reference, including structure, stages, rollups, schemas, and validations. Its full-model-export section conflicted with the current initialisation inventory: both hard-coded workbooks are retired and absent, while the per-economy templates are not yet wired into the archived Stage 0 resolver. | **UPDATE** — retain the uniquely useful long-form reference while documenting the actual mapping-sheet fallback and current template ownership. |
| `docs/new_leap_rows_mapping_progress_20260728.md` | Dated evidence of current new-row mapping work and backup path. | **KEEP** as dated progress, not canonical instructions. |
| `docs/prompts/AGENTS.md` | Active-prompt rules and inventory. The old table contradicted prompt resolution notes and current master. | **UPDATE** — now lists exactly the five runnable/paused prompts and archival results. |
| `docs/prompts/data_reliability_flag_and_diagnostic_consolidation_design_20260723.md` | Active design proposal; uniquely connects reliability attribution and diagnostic consolidation. Explicitly not implemented authority. | **UPDATE** — retained active; corrected its archived findings path. |
| `docs/prompts/mirror_row_gap_exception_curation_handoff_20260727.md` | Paused, safety-gated exception-curation handoff with raw-data verification rules. | **UPDATE** — retained active/paused; corrected archived investigation paths. |
| `docs/prompts/review_non_expanding_vs_detached_rollups_prompt.md` | Pending semantic review of all manual rollup modes. | **KEEP**; canonical-workbook evidence path remains to be repointed when executed. |
| `docs/prompts/run_mapping_pipeline_future_prompt.md` | Reusable long-running pipeline procedure and polling/safety details. | **KEEP**; maintained runbook takes precedence where they differ. |
| `docs/prompts/set_blank_ninth_fuel_mappings_prompt.md` | Active human decision prompt for the three blank fuel rows. | **KEEP**. |
| `docs/QA plan.md` | Focused opt-in real-data smoke test and its coverage. | **UPDATE** — clarified it is not the full release QA plan and linked the agent runbook. |
| `docs/README.md` | Canonical documentation navigation. | **UPDATE** — added exhaustive register and archived cleanup-snapshot routing. |
| `docs/repo_data_slimdown_plan.md` | File-by-file data/config storage evidence and restoration planning. | **KEEP**; dated storage analysis remains useful alongside newer contract docs. |
| `docs/results_folder_cleanup_candidates.md` | Detailed cleanup evidence, including an unresolved missing-row comparison; currently modified by the user/another agent. | **DEFER** — reviewed but deliberately not edited, staged, or committed here. |
| `docs/results_output_storage.md` | Current compressed-output and retention contract. | **KEEP**. |
| `docs/rollup_rules_system.md` | Canonical rollup semantics, modes, exclusions, and pipeline boundaries. | **KEEP**. |
| `docs/source_coverage_audit.md` | Current source-first coverage workflow/config/output guide. | **KEEP**. |
| `docs/special_rules_and_design_decisions.md` | Authoritative settled/provisional semantic decision log with stable IDs. Its cross-repository note still described the retired shared full-model workbook as a live mapping input. | **UPDATE** — preserve the decisions while recording per-economy template ownership and the current Stage 0 mapping-sheet fallback. |
| `docs/subtotal_columns_rebuild_plan.md` | Review-only MAPQ-030 plan; clearly says no subtotal cells were changed. | **KEEP**. |
| `docs/work_queue.md` | Controlling backlog and dated handover plan. Its repository/prompt/contract state preceded more than twenty later commits. | **UPDATE** — current-state addendum and obsolete delayed-runner correction; detailed historical rationale retained. |
| `docs/workbook_variant_row_comparison_20260728.md` | Unique measured row-level comparison supporting MAPQ-026/027. | **UPDATE** — delayed runner is now historical after `ac33daa`; remaining evidence preserved. |
| `docs/workflow_inventory.md` | Live/standalone/legacy/broken code navigation. | **UPDATE** — current date, contract/storage/delta/coverage tools, and new archive path. |
| `results/common_esto/README.md` | Primary Stage 2/3 outputs and diagnostic-family navigation; already warns it is not exhaustive. | **KEEP**. |
| `results/for_colleagues/README.md` | Manual trimmed-export contract. | **KEEP**. |
| `results/logs/README.md` | Canonical current log and archived ad-hoc-log distinction. | **KEEP**. |
| `results/maintenance/README.md` | Stage 0 workbook-QA output navigation. | **KEEP**. |
| `results/mapping_graph_index/README.md` | Explicitly standalone dashboard-prototype outputs and producer list. | **UPDATE** — link follows moved prototype note. |
| `results/mapping_relationships/README.md` | Stage 1/conversion/lineage output navigation and tracked candidate exception. | **KEEP**. |
| `results/README.md` | Results start page. Its claim that the entire folder was safe to delete ignored tracked files, costly artifacts, and evidence retention. | **UPDATE** — preservation-safe cleanup guidance. |
| `results/tree_structure/README.md` | Current tree and recursive-validation output guide, with historical-artifact caveat. | **UPDATE** — routes current interpretation to the handover runbook and completed findings to the archive. |

## Newly archived in this pass

| Original file | Role, evidence, and unique information | Decision / destination |
|---|---|---|
| `archive/2026-07-23_repo_cleanup/mapping_code/README_dashboard_mapping_starter.md` | Historical dashboard-mapping prototype note; unique run order/output inventory, but misplaced outside the documentation archive. | **ARCHIVE** → `docs/archive/2026-07-23_repo_cleanup/mapping_code/README_dashboard_mapping_starter.md`. |
| `docs/REPO_CLEANUP_AND_NAVIGATION_NOTES.md` | 1,000+ line self-contained 2026-07-22 transfer snapshot; unique archaeology but its “only deliverable” instruction is obsolete and maintained docs now contain the live material. | **ARCHIVE** → `docs/archive/2026-07-23_repo_cleanup/REPO_CLEANUP_AND_NAVIGATION_NOTES.md`. |
| `docs/interactive_anchor_tree_explorer_findings.md` | Completed feasibility findings and prototype assessment; possible future visualization value. | **ARCHIVE** → `docs/archive/interactive_anchor_tree_explorer_findings.md`. |
| `docs/prompts/anchor_validator_fixes_findings_20260722.md` | Completed first-session anchor-validator findings; unique root-cause/history, stale counts. | **ARCHIVE** → `docs/archive/anchor_validation_methodology/anchor_validator_fixes_findings_20260722.md`. |
| `docs/prompts/anchor_validator_fixes_findings_20260723.md` | Completed follow-on findings and mirror-row-gap trace; current follow-up is MAPQ-011/012. | **ARCHIVE** → `docs/archive/anchor_validation_methodology/anchor_validator_fixes_findings_20260723.md`. |
| `docs/prompts/common_esto_lineage_validation/README.md` | Index for a prompt pack whose seven prompts/status/TODO were already archived. | **ARCHIVE** → `docs/archive/common_esto_lineage_validation/README.md`. |
| `docs/prompts/configurable_comparison_scopes_prompt.md` | Own resolution says fully implemented and verified, including 49 targeted tests and differentiated real-data scopes. | **ARCHIVE** → `docs/archive/configurable_comparison_scopes_prompt.md`. |
| `docs/prompts/esto_extended_dataset_design.md` | Original gating design with valuable candidate analysis; later focused designs and implementations supersede it as active guidance. | **ARCHIVE** → `docs/archive/esto_extended_dataset/esto_extended_dataset_design.md`. |
| `docs/prompts/esto_extended_dataset_prompt.md` | Original design prompt; its required design was written and implementation advanced. | **ARCHIVE** → `docs/archive/esto_extended_dataset/esto_extended_dataset_prompt.md`. |
| `docs/prompts/holistic_mapping_system_stocktake_findings_20260722.md` | Completed stocktake whose counts were superseded by corrected baselines; unique historical diagnosis retained. | **ARCHIVE** → `docs/archive/holistic_mapping_system_stocktake_findings_20260722.md`. |
| `docs/prompts/holistic_mapping_system_stocktake_prompt.md` | Completed origin prompt paired with the stocktake findings. | **ARCHIVE** → `docs/archive/holistic_mapping_system_stocktake_prompt.md`. |
| `docs/prompts/interactive_anchor_tree_explorer_prompt.md` | Completed exploration prompt paired with the findings above. | **ARCHIVE** → `docs/archive/interactive_anchor_tree_explorer_prompt.md`. |
| `docs/prompts/investigate_anchor_validation_methodology.md` | Superseded origin prompt for the completed two-session methodology chain. | **ARCHIVE** → `docs/archive/anchor_validation_methodology/investigate_anchor_validation_methodology.md`. |
| `docs/prompts/investigate_anchor_validator_memory_prompt.md` | Memory fix is patch-equivalent on master as `03c9405`; prompt no longer active. | **ARCHIVE** → `docs/archive/investigate_anchor_validator_memory_prompt.md`. |
| `docs/prompts/investigate_demand_sector_parent_child_mismatches.md` | Completed investigation prompt. | **ARCHIVE** → `docs/archive/investigate_demand_sector_parent_child_mismatches.md`. |
| `docs/prompts/investigate_demand_sector_parent_child_mismatches_FINDINGS.md` | Findings say the five cases are resolved or dramatically reduced; unique evidence retained. | **ARCHIVE** → `docs/archive/investigate_demand_sector_parent_child_mismatches_FINDINGS.md`. |
| `docs/prompts/investigate_ninth_09_total_transformation_reconciliation.md` | Multi-pass historical investigation; implemented fix and narrow remaining reliability question are represented elsewhere. | **ARCHIVE** → `docs/archive/investigate_ninth_09_total_transformation_reconciliation.md`. |
| `docs/prompts/investigate_standalone_rollup_validation.md` | Own 2026-07-21 resolution and commit list state the work was implemented. | **ARCHIVE** → `docs/archive/investigate_standalone_rollup_validation.md`. |
| `docs/prompts/regen_common_esto_comparison_fast_path_prompt.md` | Fast path exists, is tested, and is documented in maintained handover runbooks; original implementation prompt is complete. | **ARCHIVE** → `docs/archive/regen_common_esto_comparison_fast_path_prompt.md`. |
| `docs/prompts/whole_work_queue_smart_agent_prompt.md` | Superseded orchestration prompt; the controlling queue and focused active prompts now own its remaining work. | **ARCHIVE** → `docs/archive/whole_work_queue_smart_agent_prompt.md`. |

## Files already correctly archived

| File | Unique historical information | Decision |
|---|---|---|
| `docs/archive/2026-07-23_repo_cleanup/prompts_5-7.md` | Raw short note behind settled ignored-sector/fuel rule MAP-011. | **KEEP-HISTORICAL**. |
| `docs/archive/2026-07-23_repo_cleanup/Untitled-1.md` | Raw 2026-06-30 pipeline console evidence. | **KEEP-HISTORICAL**. |
| `docs/archive/buildings_ninth_counterpart_gap_FINDINGS.md` | Completed Buildings/Services granularity diagnosis and proposed follow-up. | **KEEP-HISTORICAL**. |
| `docs/archive/buildings_ninth_counterpart_gap_prompt.md` | Investigation scope and stop conditions paired with findings. | **KEEP-HISTORICAL**. |
| `docs/archive/common_esto_lineage_validation/01_shared_rollup_and_hierarchy_resolver.md` | Prompt 1 architecture requirements. | **KEEP-HISTORICAL**. |
| `docs/archive/common_esto_lineage_validation/02_compile_structural_mapping_artifacts.md` | Prompt 2 artifact schemas and compilation criteria. | **KEEP-HISTORICAL**. |
| `docs/archive/common_esto_lineage_validation/03_partitioned_value_application_and_lineage.md` | Prompt 3 partitioning/lineage contract. | **KEEP-HISTORICAL**. |
| `docs/archive/common_esto_lineage_validation/04_anchor_validation_from_lineage.md` | Prompt 4 anchor-validation requirements. | **KEEP-HISTORICAL**. |
| `docs/archive/common_esto_lineage_validation/05_full_integration_benchmark_and_documentation.md` | Prompt 5 integration/benchmark requirements. | **KEEP-HISTORICAL**. |
| `docs/archive/common_esto_lineage_validation/06_reconcile_anchor_validation_against_conversion_outputs.md` | Prompt 6 reconciliation design. | **KEEP-HISTORICAL**. |
| `docs/archive/common_esto_lineage_validation/07_leap_base_conservation_validation_flavor_a.md` | Prompt 7 LEAP conservation design. | **KEEP-HISTORICAL**. |
| `docs/archive/common_esto_lineage_validation/PROMPT5_STATUS_AND_ISSUES.md` | Prompt-5 implementation status and known issues. | **KEEP-HISTORICAL**. |
| `docs/archive/common_esto_lineage_validation/TODO.md` | Residual lineage-pack task record. | **KEEP-HISTORICAL**. |
| `docs/archive/explore_parent_level_own_use_comparison_rows.md` | Completed own-use design exploration prompt. | **KEEP-HISTORICAL**. |
| `docs/archive/explore_parent_level_own_use_comparison_rows_FINDINGS.md` | Own-use exploration verdict/evidence. | **KEEP-HISTORICAL**. |
| `docs/archive/fix_common_esto_rollup_resolution_prompt.md` | Historical rollup-resolution implementation prompt. | **KEEP-HISTORICAL**. |
| `docs/archive/fix_ninth_power_sector_rollup_emission_prompt.md` | Implemented NINTH power rollup prompt and acceptance criteria. | **KEEP-HISTORICAL**. |
| `docs/archive/implement_non_expanding_rollups_and_source_fallbacks_prompt.md` | Implemented non-expanding/fallback design requirements. | **KEEP-HISTORICAL**. |
| `docs/archive/register_rollup_groups_as_tree_nodes_prompt.md` | Implemented tree-node registration prompt. | **KEEP-HISTORICAL**. |
| `docs/archive/row_level_lineage_for_common_esto_prompt.md` | Implemented row-lineage requirements and verification. | **KEEP-HISTORICAL**. |
| `docs/archive/side_prompt_esto_rollup_expansion.md` | Historical side investigation into ESTO rollup expansion. | **KEEP-HISTORICAL**. |
| `docs/archive/stage3_performance_optimization_prompt.md` | Performance task requirements. | **KEEP-HISTORICAL**. |
| `docs/archive/stage3_performance_optimization_REPORT.md` | Performance measurements and implementation report. | **KEEP-HISTORICAL**. |
| `docs/archive/unify_rollup_rules_prompt.md` | Implemented rollup-unification prompt and acceptance criteria. | **KEEP-HISTORICAL**. |

## Remaining uncertainties

- This pass did not change the user-owned
  `docs/results_folder_cleanup_candidates.md`; its missing-mapped-row regression
  question remains unresolved.
- The queue is a same-day snapshot with an explicit current-state addendum.
  It still needs item-by-item consolidation after the dirty checkout,
  unintegrated safety branches, and clean baseline are settled.
- Active design prompts remain proposals until their corresponding MAPQ items
  are reviewed and implemented.
- Historical archived files intentionally retain stale paths, counts, and
  instructions as evidence. Their archive location and this register, rather
  than silent rewriting, prevent those claims from being mistaken for current
  guidance.
