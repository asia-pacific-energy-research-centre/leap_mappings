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
  maintained Boolean columns to remain real Boolean cells displayed as Excel
  in-cell checkboxes. New rows must copy only the checkbox capability from a
  clean existing Boolean cell on the same sheet, while retaining the ordinary
  unfilled style of surrounding cells. Each required Boolean cell must contain
  `True` or `False`; blanks are not acceptable on complete active rows.
- Require a post-save, post-reopen visual check covering every edited Boolean
  column. If the editing library cannot preserve or create the workbook's
  checkbox representation, stop and use a proven formatting-preserving route
  or request a manual Excel edit; do not leave mixed checkboxes and literal
  Boolean text in one column. Reject black/solid fills, hidden-text number
  formats, font masking, or any other extra formatting in Boolean cells; the
  checkbox is the only special presentation.

## Archiving prompts

- Archive only with clear evidence that the work is complete or superseded.
- Move companion findings/status files with the prompt.
- If `docs/archive/` is ignored, force-add only the files for the archival
  change.
- Preserve unresolved follow-ups in `docs/work_queue.md` or a narrower active
  prompt before archiving.

## Current inventory

Verified against local `master` on 2026-07-28 after the documentation
disposition audit.

| Prompt | Status | Purpose / next use |
|---|---|---|
| `data_reliability_flag_and_diagnostic_consolidation_design_20260723.md` | Active design input | Reconcile reliability attribution, exception curation, output-contract evidence, and diagnostic retention under MAPQ-012. It is explicitly a proposal, not implemented authority. |
| `complete_hierarchy_subtotal_contract_prompt.md` | Active implementation prompt | Complete MAPQ-030 with an adapter-based, mappings-owned structural contract; keep structural subtotal classification separate from numerical additivity, then integrate the dashboard and initialisation consumers. |
| `explore_separate_axis_mapping_contract.md` | Paused at decision gate | MAPQ-033 exploration is measured and documented; decide flow-qualified product semantics and the accepted ESTO dormancy threshold before resuming shadow implementation. |
| `mirror_row_gap_exception_curation_handoff_20260727.md` | Paused | Resume the reviewed NINTH source-mismatch curation only after a clean baseline and the handoff's safety gate. |
| `review_non_expanding_vs_detached_rollups_prompt.md` | Active review | Review every live manual rollup mode under MAPQ-010. Repoint any absent optional evidence to the canonical workbook before use. |
| `run_mapping_pipeline_future_prompt.md` | Reusable run procedure | Use for a requested current run. First reconcile it with the maintained agent runbook and verify workbook/process state. |
| `set_blank_ninth_fuel_mappings_prompt.md` | Active human decision | Review the three blank `ninth_fuel` rows under MAPQ-027; do not write the workbook without approval. |

`AGENTS.md` itself is an instruction/inventory file, not a runnable prompt.

## Archived in the 2026-07-28 disposition pass

The audit moved completed, superseded, or fully historical prompt packs to
`docs/archive/` without deleting their contents. This includes the configurable
scope, fast-path, standalone-rollup, anchor-methodology/memory, demand-mismatch,
NINTH transformation, holistic-stocktake, interactive-tree, ESTO Extended
design, and superseded whole-queue prompts. The orphaned Common ESTO lineage
README was moved into its existing archived pack.

See [`../documentation_disposition_20260728.md`](../documentation_disposition_20260728.md)
for the evidence and destination of every moved file.
