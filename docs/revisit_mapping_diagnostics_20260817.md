# Revisit: mapping diagnostics findings parked on 2026-07-27

Check on or after **2026-08-17**.

These came out of the 2026-07-27 session that fixed the ESTO rollup
source-identity doubling. They are recorded as **probably work-in-progress**,
not defects: the ESTO Extended dataset was actively being built at the time, so
incomplete structure and coverage are expected states rather than regressions.

Nothing here blocks the ordinary ESTO basis. The doubling fix is complete and
verified, and none of the items below affect it.

The value of this note is the evidence: each item records what was measured, so
a future check is a re-measure rather than a re-investigation. If a re-measure
gives the same numbers weeks later with the Extended build finished, that item
has stopped being work-in-progress and is worth treating as real.

## Baseline these were measured against

```text
run_id:   common_esto_20260727T113042584213Z
workbook: config/outlook_mappings_master.xlsx at commit 947742d
run from: the mapping-diagnostics-dashboard worktree, stages 1,2,data_convert,3
```

## 1. Extended flows have no Common ESTO rows

The workbook's 730 `ESTO_EXTENDED` rows target 56 extended-only flows, but the
Common ESTO structure defines rows for only 5 of them, so 55 have nowhere to
land. `09.01.02.01 Coal CHP` works only because it was already in the tree.

| Artifact | Extended-only flows present, of 60 |
| --- | --- |
| `results/tree_structure/esto_extended_tree.csv` | 60 |
| Workbook mapping targets | 56 |
| `results/tree_structure/common_esto_tree.csv` | 5 |

**Re-check:** count distinct extended-only flows appearing as
`common_flow_label` in `results/common_esto/common_esto_comparison_data.csv`.
It was 5 (four of them generated rollup labels, one real detail flow).

**If still 5 once the Extended build is finished**, the structure genuinely is
not admitting Extended flows, and
`docs/prompts/admit_esto_extended_flows_to_common_structure_prompt.md` has the
full diagnosis and a design question to work through.

## 2. Mappings whose target has no Common ESTO row are dropped silently

In the same run, all of these contained zero rows referencing an extended-only
flow, despite 55 mapped targets having no Common ESTO row:

```text
results/common_esto/qa_common_esto_components_missing_from_structure.csv   (0 rows)
results/common_esto/qa_common_esto_excluded_components.csv                 (0 rows)
results/common_esto/structural_artifacts/qa_unresolved_structural.csv     (16 rows, none extended)
results/common_esto/structural_artifacts/qa_ambiguous_structural.csv      (27 rows, none extended)
```

This one is worth a second look even if item 1 resolves on its own. Item 1 is a
temporary state of an unfinished dataset; this is a reporting property that will
persist. It means mapping coverage can be absent while every QA artifact reads
clean — the same shape as the doubling bug, which was also silent until a check
was written for it.

**Re-check:** map a source pair to a deliberately non-existent target flow, run
Stage 2, and see whether any artifact records it.

## 3. Stage 3 crashes when partial coverage is empty — RESOLVED 2026-08-03

**Status: fixed on `master`. Nothing to re-measure on 2026-08-17.**

The fix landed as `329d9a7`, cherry-picked from `claude/zen-pike-39adbf`
(`add312d`) while closing MAPQ-004. `ACTIVE_SOURCE_PAIR_COLUMNS` is now shared,
so an empty summary still exposes the merge columns and yields no candidates
instead of raising. Verified by 8 tests in
`tests/test_mapping_candidate_generation.py`.

The original diagnosis is preserved below as evidence.


`generate_partial_coverage_mapping_candidates()` in
`codebase/mapping_tools/mapping_candidate_generation.py` (around lines 400-417)
filters `issues_df` by `source_system` without checking the frame has columns.
An empty `qa_common_esto_structural_partial_coverage.csv` is a legitimate state
(nothing actionable found), and in that state Stage 3 dies with
`KeyError: 'source_system'`.

Observed on 2026-07-27 in the worktree, where the file was absent. Not yet seen
in a main-checkout run.

**Re-check:** none needed — see the resolution note above.

## 4. Pipeline provenance does not cover the workbook

`leap_dashboard/codebase/mapping_pipeline_provenance.py` compares artifact write
times against `leap_mappings` `codebase/` commit dates. It does not look at
`config/*.xlsx`, so a workbook change is invisible to it.

This bit twice on 2026-07-27: the morning run used
`outlook_mappings_master_combined_esto.xlsx` while the afternoon rebuild used
`outlook_mappings_master.xlsx`, and for most of the day the authoritative
artifacts were built from an uncommitted workbook. The workbook is now committed
(`947742d`), which removes the immediate exposure.

**Re-check:** whether workbook drift has recurred. The extension is small —
compare `config/*.xlsx` mtimes against artifact mtimes and flag uncommitted
workbook changes in the same section that already reports superseded code.

## What is NOT parked

The rollup source-identity fix is complete: ratio 1.0 in all 21 economies for
`09.01.01,09.02.01 Electricity plants` (2023, ordinary ESTO), and
`guard_esto_exact_rows_source_identity()` now fails the run rather than writing a
doubled artifact.

That guard was merged to `master` on 2026-07-27, so a pipeline run from the main
checkout is protected. It had been sitting on the worktree branch, which meant a
run from `master` would have had no protection against the doubling recurring —
worth remembering as a pattern: a fix that only exists on a branch protects
nothing.
