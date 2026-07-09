# Prompt: Stage 3 / anchor validation performance optimization

Work in `C:\Users\Work\github\leap_mappings`.

## Context

A full `python codebase/run_mapping_pipeline.py` run on 2026-07-04 (log:
`results/logs/full_run_test_stdout.log`, PID 21244) completed Stages 0-2,
LEAP parse, and data convert in under 20 minutes, then spent **7+ hours**
inside Stage 3's `validate_source_parent_anchors` before being killed for
inspection. CPU time tracked wall-clock almost 1:1 throughout (confirmed via
repeated `Get-Process` polling), so it was not hung — it is genuinely this
slow at full scale.

One fix is already applied and verified (uncommitted as of this prompt):
`codebase/mapping_tools/source_parent_anchor_validation.py`'s
`load_raw_source_anchor_inputs` used three row-wise
`ninth[...].apply(lambda row: ..., axis=1)` calls to build `source_flow`,
`source_product`, and the `9th_sector`/`9th_fuel` lookup columns. These were
replaced with vectorized helpers `_join_hierarchy_path` and
`_resolve_most_specific` (column-wise string ops instead of per-row Python).
Verified byte-for-byte identical output against the original row-wise logic
on real data (`data/merged_file_energy_ALL_20251106.csv`, 522,141 rows;
32,870,980 total source rows / 12,609 mapping rows unchanged), and the
`PerformanceWarning: DataFrame is highly fragmented` warning is also gone
(fixed with an explicit `.copy()` before assignment, per pandas' own
suggestion). All 15 existing tests in `tests/test_source_parent_anchor_validation.py`
and `tests/test_reconcile_anchor_validation.py` still pass. Do not redo this
part — build on it.

## Remaining issues to fix

### 1. The dominant bottleneck: nested Python loop in `validate_source_parent_anchors`

`codebase/mapping_tools/source_parent_anchor_validation.py`, roughly lines
178-300. For each `source_system` (LEAP/NINTH/ESTO) and each `axis`
(flow/product), the function iterates `for parent_code in children.items()`
and then `for group_key, parent_group in parent_rows.groupby(group_cols)`
(group_cols = economy, scenario, year, other_axis_value), and *inside that*
loops `for scope in scopes`. With NINTH alone spanning ~21 economies x
several scenarios x ~90 projection years x hundreds of sectors/fuels, this is
plausibly tens of millions of Python-level iterations, each doing dict
lookups, a `.groupby` per parent, and per-group `.isin()` filtering.

Vectorize this. Suggested approach (adapt as the code demands, but preserve
exact status/reason semantics per row):

- Replace the per-group Python loop with a single `groupby(...).agg(...)` (or
  `.sum()`) over the full `axis_source` frame per (source_system, axis) to
  get `parent_value`, `parent_positive`, `parent_negative` for every
  `(parent_code, economy, scenario, year, other_axis_value)` combination in
  one vectorized pass, instead of re-deriving them by filtering per group.
- Precompute the frontier (`frontier_ids` per `(parent_code, other_axis_str,
  scope)`) once per unique key as already partially cached
  (`frontier_cache`, `frontier_ids_cache`) — keep that caching, but stop
  re-entering a Python loop over every `(economy, scenario, year)` combo to
  use it. Instead, build a lookup table of `(parent_code, other_axis_value,
  scope) -> frontier_ids` and join/merge it against the grouped parent-value
  table, then vectorize the comparison-frame lookup with a merge on
  `common_row_id` membership (e.g. explode `frontier_ids` into a join table
  and merge, then `groupby` to re-aggregate `frontier_sum`) rather than
  filtering the comparison frame per group inside the loop.
- The `status`/`reason` classification (`incomplete_frontier`,
  `no_anchorable_common_esto_boundary`, `frontier_rows_absent`,
  `difference_exceeds_tolerance`, `within_tolerance`) must remain row-for-row
  identical to the current logic — implement it as vectorized `np.select` /
  boolean-mask assignment over the merged table, not a per-row Python branch.
- It is acceptable (and likely necessary) to restructure this function
  substantially. It is not acceptable to change any pass/fail/skip
  classification or any numeric total for any existing row.

### 2. Redundant reads/reshapes of the 9th Outlook CSV

`data/merged_file_energy_ALL_20251106.csv` (~522K wide rows, ~23.7M rows
once melted to long format) is independently read and melted from scratch in
at least three places during a full `run_mapping_pipeline.py` run:

- `prepare_ninth_long_format` (`apply_ninth_to_esto_conversion.py`) — used by
  `run_ninth_to_esto()`, filtered to `reference` scenario, 3-level sector
  resolution (sectors/sub1/sub2 only).
- `load_raw_source_anchor_inputs` (`source_parent_anchor_validation.py`) —
  used by Stage 3's anchor validation, all scenarios, 5-level sector
  resolution (sectors through sub4), filtered to `year > leap_var_base_year`.
- `build_ninth_tree` / the various `validate_ninth_*` functions in
  `build_dataset_tree_structure.py` — used by Stage 3's hierarchy validation.

These use genuinely different filters and column semantics (different
scenario scope, different sector-level depth), so they cannot simply share
one melted frame without risk of behavior drift. Investigate whether
`run_mapping_pipeline.py`'s `run_stage_3()` can read the raw wide CSV once
and pass it (or a shared intermediate) into each consumer, avoiding at least
the repeated `pd.read_csv` of the same file, without changing any consumer's
filtering logic or output. If a safe shared-melt refactor is not achievable
without risk, it is fine to only dedupe the raw CSV read and leave the melts
separate — note explicitly which option was chosen and why.

### 3. Filter-before-melt for the 9th->ESTO *conversion* path only

In the observed run, `run_ninth_to_esto()` melted 23,760,464 rows and then
discarded 20,310,381 (85%) for having no included ESTO mapping. Filter the
wide 9th dataframe to only `(source_flow, source_product)` — i.e.
`(ninth_sector, ninth_fuel)` — pairs that have an included mapping (join
against `relationships_df`) *before* melting across ~90 year columns, so
unmapped sector/fuel combinations are not expanded across every year for
nothing.

**This optimization applies only to `run_ninth_to_esto` /
`prepare_ninth_long_format` / `convert_ninth_results_to_esto`.** Do **not**
apply it to `load_raw_source_anchor_inputs`'s raw source loading — anchor
validation needs the complete unfiltered raw values to compute true parent
totals for the "does the mapped frontier explain the whole parent" check;
pre-filtering there would silently corrupt that check by dropping rows from
the "actual total" side of the comparison, not just the "mapped" side.

## Constraints (all three issues)

- `results/mapping_relationships/*.csv` and `results/common_esto/*.csv`
  numeric columns and row counts must match the current run byte-for-byte.
  Do not treat "close enough" totals as sufficient — compare exactly.
- Do not change any pass/failed/skipped classification in
  `source_parent_anchor_validation.csv`,
  `source_parent_anchor_validation_summary.csv`,
  `common_esto_validation.csv`, or `common_esto_validation_summary.csv`.
- Preserve all existing tests; add focused tests for any new vectorized
  logic (especially issue #1's restructure — this is the highest-risk
  change).
- Add `time.perf_counter` timing prints around `validate_source_parent_anchors`
  (and around Stage 3 as a whole in `run_mapping_pipeline.py`) so the
  before/after win is directly visible in the run log, not just inferred.

## Verification plan

1. Before touching issue #1, run `validate_source_parent_anchors` against a
   restricted slice using its own `economies` and `years_by_system`
   parameters (already supported by the function signature) to get a fast
   reference result and baseline timing on a small scope.
2. After each change, re-run the same restricted slice and diff the output
   frame against the pre-change reference (`pd.DataFrame.equals` or an exact
   merge-and-compare) before ever attempting a full-scale run.
3. Only once the restricted-slice diff is clean, run the full
   `run_mapping_pipeline.py` end to end as the final check. Compare
   `results/common_esto/common_esto_output_status.csv`,
   `results/tree_structure/source_parent_anchor_validation_summary.csv`, and
   `results/tree_structure/common_esto_validation_summary.csv` against last
   night's run (2026-07-04, already on disk) to confirm identical pass/fail
   counts and identical (or explainably rounding-only) totals.
4. Record the Stage 3 wall-clock time from tonight's baseline run
   (7+ hours, killed before completion — so use the timing prints from step
   1-2's restricted slice, scaled, as the primary "before" evidence, plus
   whatever wall-clock the full run reaches tonight) against the optimized
   full run's actual completion time.

## Process management and polling

Launch long-running verification/test processes (the restricted-slice check,
and the final full `run_mapping_pipeline.py` run) as background processes,
each with its own log file, and manage each one on this schedule
independently, per unique process:

- Poll 2 times at 5-minute intervals after launch.
- Then poll 2 times at 10-minute intervals.
- Then poll every 20 minutes until that process completes.

At each scheduled poll, inspect only: whether the process is still alive,
its CPU time (to distinguish "still computing" from "stalled" — CPU time
should keep climbing roughly 1:1 with wall time), and the last 20-40 lines
of its log. Do not poll more frequently than the schedule above, and do not
inspect process state, logs, CPU, or output files between scheduled polls.
If more than one such process is running at once (e.g. a restricted-slice
check and a full run, or a baseline-vs-optimized comparison pair), track
each one's own independent 5/5/10/10/20/20/... schedule rather than a single
shared schedule.

If a process appears stalled (CPU time stops climbing between two
consecutive polls), say so explicitly rather than continuing to wait
silently, and investigate before waiting further.

## Success criteria

- Stage 3 completes in a small fraction of tonight's 7+ hour (and still
  unfinished) baseline — ideally minutes, not hours, for the anchor
  validation step specifically.
- No output CSV's numeric values or pass/fail classifications differ from
  tonight's baseline run.
- Existing tests still pass; new tests cover the restructured vectorized
  logic in `validate_source_parent_anchors`.
- A clear before/after timing comparison is recorded (in the run log and/or
  a short note in this prompt's directory) so the win is verifiable without
  re-deriving it.
- Commit with a `codex:` commit message, scoped only to this prompt's
  changes (the already-applied `load_raw_source_anchor_inputs` vectorization
  plus the new Stage 3 work).
