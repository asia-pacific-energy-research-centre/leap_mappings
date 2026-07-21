# Resume prompt: NINTH 09 Total transformation reconciliation gap

You are working in C:\Users\Work\github\leap_mappings on the Common ESTO mapping
pipeline. Read the repository AGENTS.md files and docs/mappings_system.md before
making changes. Start with:

    git status --short
    git log -5 --oneline

Use C:\Users\Work\miniconda3\python.exe for Python. Use apply_patch for source
edits. Commit only files changed for this task, with a `codex:` commit message,
after focused tests pass. Treat existing uncommitted changes as user-owned
unless you can identify them as part of this task.

## Prerequisite / coordination

This task is a follow-on to the standalone-rollup validation work, which is
resolved (commit `4042d5e`, see
docs/prompts/investigate_standalone_rollup_validation.md and the memory note
`project_standalone_rollup_validation`). Do **not** re-open that rollup work.

The rollup-change verification run is **complete**: a full Stages 1-3 run
finished cleanly on 2026-07-21 (`Pipeline complete.`, Stage 3 ~24 min,
`run_id common_esto_20260721T014101`; log
`logs/codex_stages_1_3_20260721_103752_rollup_exclusion.out.log`). The
`results/` outputs referenced below are from that run, so you can inspect them
immediately and are free to launch your own Stages 1-3 run whenever you need to
test a change. Standard hygiene still applies: only run one
`run_mapping_pipeline.py` at a time — two concurrent runs clobber each other's
`results/` outputs.

## Objective

The ordinary recursive Common ESTO validator now cleanly excludes rollup
subtotals, but a genuine reconciliation gap remains and is the largest single
source of failures:

**For source NINTH, `09 Total transformation sector` does not equal the sum of
its ordinary `09.xx` children** (~4,663 failed parent-checks in the last run,
the bulk of the remaining 11,242 total failures; ESTO contributes far fewer).

This is NOT a rollup-boundary artifact. It is a NINTH transformation
data/mapping/emission question. Determine why NINTH's `09 Total` value diverges
from the sum of the `09.xx` transformation children NINTH actually emits into the
Common ESTO comparison data, and fix the mapping/emission (or prove the gap is a
genuine NINTH source inconsistency that must be recorded as an accepted
exception rather than silently failed).

## What is already known

- Raw NINTH sector and fuel hierarchy validation is clean (0 findings in the
  2026-07-17 run). So NINTH's own hierarchy adds up in the raw 9th data; the gap
  is introduced by the Common ESTO mapping/emission layer, not by raw NINTH.
- The recursive validator groups per source system and checks
  `parent_sum` vs `children_sum` per
  (comparison_scope, economy, scenario, opposite-axis value, year). See
  `_validate_common_esto_axis_recursive_sums` in
  `codebase/mapping_tools/build_dataset_tree_structure.py`. Missing children
  alone are not a failure; only a value mismatch beyond tolerance is.
- Strong lead: the diagnostics show the `09 Total` NINTH failures concentrate on
  the children `09.06 Gas processing plants`, `09.07 Oil refineries`, and
  `09.08 Coal transformation`. These base flows have inclusive
  "(including own use)" rollup siblings that fold the `10.01.xx` energy-industry
  own-use rows into transformation. Investigate whether NINTH emits its
  transformation total on an own-use-inclusive boundary while the ordinary
  `09.xx` children are emitted on the own-use-exclusive boundary (or vice
  versa), so the own-use amount is exactly the discrepancy. Quantify: does
  `NINTH 09 Total - sum(NINTH 09.xx children)` equal the NINTH `10.01.xx`
  transformation own-use total per economy/year?
- The rollup boundary itself is now validated separately in
  `results/tree_structure/common_esto_rollup_validation.csv` — use it to see
  where NINTH inclusive rollups reconcile vs not.

## Diagnostic outputs to start from

- `results/tree_structure/common_esto_validation.csv` — full parent/child checks
  (large). Filter `source_system == NINTH`, `parent_code == "09 Total
  transformation sector"`, `status == "failed"`.
- `results/tree_structure/common_esto_validation_child_detail.csv` — per-child
  evidence with a `diagnosis` column.
- `results/tree_structure/common_esto_validation_issue_patterns.csv` — compact
  recurring-pattern rollup of the above.
- `results/tree_structure/common_esto_source_frontier.csv` — per-source
  comparable children (source availability).
- `results/common_esto/common_esto_comparison_data.csv` — the emitted comparison
  values; sum NINTH `09.xx` under a fixed economy/scenario/year and compare to
  `09 Total transformation sector`.
- `results/mapping_relationships/energy_balance_relationships.csv` — how NINTH
  sectors map to ESTO flows (check what `09_total`/transformation and each
  `09_xx` map to, and whether own-use `10.01.xx` is mapped into transformation).

## Recommended investigation

1. Pick one economy/scenario/year with a large NINTH `09 Total` failure. Pull
   NINTH `09 Total` and every NINTH `09.xx` child value from the comparison data;
   compute the residual. Confirm whether the residual matches the NINTH
   `10.01.xx` own-use total (the own-use-boundary hypothesis) or something else
   (a specific missing/duplicated child, a sign error, a partition relabel).
2. Trace the residual back through `energy_balance_relationships.csv` and the
   workbook mapping/rollup sheets to the responsible mapping rule.
3. Decide the correct fix at the mapping layer (do not special-case the
   validator): e.g. a rollup/comparison-boundary rule so NINTH `09 Total` and its
   `09.xx` children are compared on the same own-use boundary, or a corrected
   NINTH-to-ESTO mapping. Follow the "do not split source aggregates" principle
   and keep base mappings simple.
4. If the gap is a genuine NINTH source inconsistency (not a mapping error),
   record it as a reviewed exception in
   `config/mapping_issue_exception_sets.xlsx` rather than leaving it as a silent
   failure, and explain why in the note.

## Focused tests and run

    C:\Users\Work\miniconda3\python.exe -m pytest tests/test_build_dataset_tree_structure.py tests/test_common_esto_validation_orchestration.py -q

Then, once no other pipeline run is active:

    C:\Users\Work\miniconda3\python.exe codebase/run_mapping_pipeline.py --stages 1,2,3

The run is long. Launch it in the background with redirected logs, monitor at
most once every 10 minutes, and do not kill it merely because output is quiet
(stdout is buffered). Check the process, log tail, and final `Pipeline complete.`
marker.

## Success criteria

- The NINTH `09 Total transformation sector` reconciliation is explained with a
  concrete residual decomposition for at least one economy/year, traced to a
  named mapping/rollup rule or a recorded source inconsistency.
- Where it is a mapping/boundary error, it is fixed at the mapping layer and the
  NINTH `09 Total` failures fall accordingly, without reintroducing rollup-as-
  parent artifacts (rollup validation from `4042d5e` must stay intact).
- Where it is a genuine NINTH inconsistency, it is a reviewed exception, not a
  silent failure.
- Focused tests pass; Stages 1-3 completes; changes committed in a focused
  `codex:` commit.
