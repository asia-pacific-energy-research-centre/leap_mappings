# Prompt folder guide

`docs/prompts/` is for active, reusable prompts only. A prompt belongs here
while it describes pending work, a reusable run procedure, or a paused
investigation whose next action is still valid.

When a prompt's work is complete, tested where applicable, and committed, move
the prompt and its companion findings to `docs/archive/`. Update this inventory
in the same commit. Do not carry point-in-time result counts from an archived
prompt into a current decision without re-measuring them.

## Adding prompts

- State the task type, scope, prerequisites, expected outputs, validation, and
  stop conditions.
- Name the workbook, sheet, and pipeline stage precisely.
- Distinguish review/design work from implementation.
- Require source schema verification and `git status --short` before edits.
- Prefer searchable symbol names to line numbers.
- Preserve unrelated changes and require reviewed workbook decisions.
- For any prompt that can add or edit rows in a mapping workbook, require all
  maintained Boolean columns to contain actual Boolean `TRUE` or `FALSE`
  values. Text strings, numbers, blanks on complete active rows, checkbox
  controls, and checkbox glyphs are not acceptable.
- Require a post-save, post-reopen check covering every edited Boolean column.
  Boolean cells must retain the ordinary unfilled style of surrounding cells.
  Reject Excel in-cell checkboxes, black/solid fills, hidden-text number
  formats, font masking, conditional formatting, data validation, or other
  special formatting in Boolean cells.

## Archiving prompts

- Archive only with clear evidence that the work is complete or superseded.
- Move companion findings/status files with the prompt.
- If `docs/archive/` is ignored, force-add only the files for the archival
  change.
- Preserve unresolved follow-ups in `docs/work_queue.md` or a narrower active
  prompt before archiving.

## Current inventory

Verified against local `master` on 2026-07-29 after archiving the out-of-scope
valid-pair authority investigation.

| Prompt | Status | Purpose / next use |
|---|---|---|
| `data_reliability_flag_and_diagnostic_consolidation_design_20260723.md` | Active design input | Reconcile reliability attribution, exception curation, output-contract evidence, and diagnostic retention under MAPQ-012. It is explicitly a proposal, not implemented authority. |
| `complete_hierarchy_subtotal_contract_prompt.md` | Active implementation prompt | Complete MAPQ-030 with an adapter-based, mappings-owned structural contract; keep structural subtotal classification separate from numerical additivity, then integrate the dashboard and initialisation consumers. |
| `admit_esto_extended_flows_to_common_structure_prompt.md` | Deferred — recheck on or after 2026-08-17 | The workbook maps 56 extended-only flows but `common_esto_tree.csv` defines Common ESTO rows for only 5, measured against run `common_esto_20260727T113042584213Z`. Parked as probable work-in-progress: the ESTO Extended dataset was still being built when this was measured. Do not start it without first re-measuring per `docs/revisit_mapping_diagnostics_20260817.md`; if the count has moved off 5 on its own, the premise has changed. |
| `mirror_row_gap_exception_curation_handoff_20260727.md` | Paused | Resume the reviewed NINTH source-mismatch curation only after a clean baseline and the handoff's safety gate. |
| `review_non_expanding_vs_detached_rollups_prompt.md` | Active review | Review every live manual rollup mode under MAPQ-010. Repoint any absent optional evidence to the canonical workbook before use. |
| `run_mapping_pipeline_future_prompt.md` | Reusable run procedure | Use for a requested current run. First reconcile it with the maintained agent runbook and verify workbook/process state. |
| `set_blank_ninth_fuel_mappings_prompt.md` | Active human decision | Review the three blank `ninth_fuel` rows under MAPQ-027; do not write the workbook without approval. |
| `mappings_review_next_agent_20260804.md` | Active review prompt | Run the combined MAPQ-009/MAPQ-010/MAPQ-029/MAPQ-031, anchor-validation, and latest-output review against the 2026-08-03 baseline. |
| `leap_review_tools_portable_release_implementation_prompt_20260803.md` | Active implementation prompt | Build a developer-linked launcher and reproducible portable-release workflow for dashboard and balance-review tools. |

`AGENTS.md` itself is an instruction/inventory file, not a runnable prompt.

## Archived in the 2026-07-28 disposition pass

The audit moved completed, superseded, or fully historical prompt packs to
`docs/archive/` without deleting their contents. This includes the configurable
scope, fast-path, standalone-rollup, anchor-methodology/memory, demand-mismatch,
NINTH transformation, holistic-stocktake, interactive-tree, ESTO Extended
design, and superseded whole-queue prompts. The orphaned Common ESTO lineage
README was moved into its existing archived pack.

The separate-axis mapping exploration prompt and companion findings were moved
to `docs/archive/separate_axis_mapping_contract/` on 2026-07-29 after the
opt-in compiler, generated workbook contract, structural source-once gate, and
bounded Stage 3 value/lineage gate passed. MAPQ-034 retains the remaining
canonical-promotion review.

`rebuild_esto_rollup_source_identity_prompt.md` was archived to `docs/archive/`
on 2026-08-03, harvested from `claude/mapping-diagnostics-dashboard-a55009`
where it had been written but never reached `master`. Its work is complete: run
`common_esto_20260727T113042584213Z` removed the exact 2.0x ordinary-ESTO
doubling (ratio 1.0 in all 21 economies), and the source-identity guard reached
`master` as `82e31f0` on 2026-08-03 under MAPQ-004. Note the prompt's own text
claims the guard was merged on 2026-07-27; it was not — it sat on a worktree
branch until the MAPQ-004 cherry-pick.

The production promotion and full-system run prompt, together with its run
report, was archived at
[`../archive/separate_axis_full_system_run_20260730/`](../archive/separate_axis_full_system_run_20260730/)
after the four-source mapping run and all-economy dashboard audit completed.
Open validation and semantic debt remains in MAPQ-034 and MAPQ-036.

See [`../documentation_disposition_20260728.md`](../documentation_disposition_20260728.md)
for the evidence and destination of every moved file.

The valid sector/fuel pair authority investigation proposed on 2026-07-29 was
archived as out of scope at
[`../archive/investigate_valid_sector_fuel_pair_authority_20260729.md`](../archive/investigate_valid_sector_fuel_pair_authority_20260729.md).
