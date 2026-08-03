# Rebuild ESTO artifacts with the rollup source-identity fix

## Objective

Rebuild the mapping-pipeline artifacts so that generated ESTO rollup rows carry
the correct `source_system`, then prove that the resulting ordinary-ESTO
comparison values are no longer exactly doubled.

The fix is already committed. The artifacts on disk are not.

## Repository

```text
C:\Users\Work\github\leap_mappings
```

Read the repository `AGENTS.md` and its two referenced global instruction files
before editing. Inspect `git status --short` first and preserve unrelated
changes. Do not stage or commit unrelated files.

## Confirmed diagnosis (2026-07-27, no re-investigation needed)

Commit `eb3a293` ("codex: preserve ESTO Extended rollup source identity") passes
`source_system` through `build_esto_non_expanding_subtotal_rows()` in
`codebase/mapping_tools/non_expanding_rollups.py`, called from
`run_esto_exact_rows_for_path()` in `codebase/run_mapping_pipeline.py`. Before
that fix, every generated rollup row was hard-coded to `source_system = "ESTO"`,
including the rows generated while building the Extended dataset.

The current artifacts predate the fix:

| Item | Local time |
| --- | --- |
| `esto_extended_results_exact_rows.csv` written | 2026-07-27 12:39 |
| Stage 3 run `common_esto_20260727T034511926826Z` finished | 2026-07-27 13:38 |
| Commit `eb3a293` | 2026-07-27 14:14 |

Evidence in the current `results/mapping_relationships/esto_extended_results_exact_rows.csv`:

- 840,378 rows carry `source_system = ESTO` instead of `ESTO_EXTENDED`.
- They belong to exactly 15 generated rollup flows, all with a
  `non_expanding_rollup_id`, including `09.01.01,09.02.01 Electricity plants`,
  `09.01-09.02 Power sector`, `09.07 Oil refineries (including own use)`,
  `16.01-16.02 Buildings`, and `15.01,15.03-15.06 Transport non-road`.

Consequence in `results/common_esto/common_esto_comparison_data.csv`: those
flows are counted once from the ordinary file and once from the Extended file,
so ordinary-ESTO values are exactly 2x. Verified for 2023,
`09.01.01,09.02.01 Electricity plants`, in **all 21 economies**, ratio exactly
`2.0` in every case. For `20USA`: raw `09.01.01` + `09.02.01` = `-17,096.581085`,
Common ESTO combined row = `-34,193.162170`.

This is not a dashboard defect. `leap_dashboard` renders the artifact faithfully.

## Work

1. Confirm the fix is present in the working tree (`rg "source_system: str" codebase/mapping_tools/non_expanding_rollups.py`)
   and that `tests/test_non_expanding_rollups.py` passes.
2. Add a regression guard that fails loudly rather than silently double-counting.
   The natural place is where the exact-rows artifact is written in
   `codebase/run_mapping_pipeline.py`: assert that every row written to an
   Extended output carries the Extended `source_system`, and write a QA artifact
   (suggested: `results/mapping_relationships/qa_esto_exact_rows_source_identity.csv`)
   recording row counts per `source_system` per output file. A pure in-memory
   assertion is not enough — the dashboard needs a file it can read.
3. Rerun the pipeline stages needed to regenerate, in order:
   `esto_results_exact_rows.csv`, `esto_extended_results_exact_rows.csv`, then
   Stage 3 (`common_esto_comparison_data.csv` and its validation outputs).
   Follow the existing procedure in
   `docs/prompts/run_mapping_pipeline_future_prompt.md` for run mechanics,
   logging, polling cadence, and workbook safety. Do not re-derive that
   procedure here.
4. Confirm the run wrote a fresh `results/common_esto/stage3_run_manifest.json`
   with a new `run_id`.

## Validation (all must pass before reporting complete)

1. No row in `esto_extended_results_exact_rows.csv` has
   `source_system != "ESTO_EXTENDED"`.
2. For 2023, `09.01.01,09.02.01 Electricity plants`, ordinary ESTO, scope
   `esto_leap_ninth`: the Common ESTO value equals the sum of raw
   `09.01.01 Electricity plants` and `09.02.01 Electricity plants` within
   tolerance, for all 21 economies. The 2.0 ratio must be gone, not merely
   smaller.
3. Repeat check 2 for at least three more of the 15 affected flows, including
   one demand-side flow (`16.01-16.02 Buildings`) and one transport flow
   (`15.01,15.03-15.06 Transport non-road`).
4. Re-check the flow-axis hierarchy and rollup validation summaries. Failure
   counts are expected to move; state the before/after numbers explicitly rather
   than asserting improvement.
5. Report whether the Extended-basis anchor scopes (`esto_extended_leap`,
   `esto_extended_leap_ninth`) changed, and whether ordinary-ESTO anchor
   failures changed. Do not sum failure counts across overlapping comparison
   scopes.

## Stop conditions

- Stop and report if the rebuild does not remove the exact 2.0 ratio: that would
  mean a second, independent double-count path exists.
- Stop if the rerun would overwrite the mapping workbook. This task changes no
  workbook rows.
- Do not "fix" the doubling by adjusting dashboard rendering, by filtering
  duplicate labels at read time, or by adding a workbook exception.

## Downstream handoff

After a clean rebuild, the sibling repo must be re-rendered before its numbers
mean anything:

```text
C:\Users\Work\github\leap_dashboard
C:\Users\Work\miniconda3\python.exe scripts\render_transformation_rollup_diagnostics_prototype.py
C:\Users\Work\miniconda3\python.exe scripts\render_mapping_pipeline_health_report.py
```

`render_mapping_pipeline_health_report.py` compares artifact write times against
`leap_mappings` `codebase/` commit dates and will say "artifacts match current
code" once the rebuild is genuinely current. Use it as the completion check.
