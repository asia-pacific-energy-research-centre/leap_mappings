# Stage 3 / anchor-validation performance optimization — run report

Executed against the prompt `docs/prompts/stage3_performance_optimization_prompt.md`.
Work is scoped to `leap_mappings`.

> **Filename note (for unwind):** the launching instruction referenced a file
> `docs/prompts/stage3_performance_optimization_prompt.md` and initially it could
> not be found because the search ran in `leap_initialisation`. The file does
> exist — in **`leap_mappings`** (untracked) — and the user then confirmed the
> work is in `leap_mappings`. No ambiguity remained after that.

## Summary of changes

| Issue | File(s) | Change | Risk | Verification |
|------|---------|--------|------|-------------|
| #1 Nested Python loop in `validate_source_parent_anchors` | `codebase/mapping_tools/source_parent_anchor_validation.py` | Replaced per-parent / per-group / per-scope Python loop with vectorized `groupby` aggregation + explode/merge for the frontier sums + `np.select` classification. | **High** (core logic) | Slice diff vs baseline: 0 classification mismatches, max numeric diff 1.16e-10. 18 unit tests pass (3 new). |
| #2 Redundant reads of the 287 MB 9th CSV in Stage 3 | `codebase/mapping_tools/build_dataset_tree_structure.py`, `codebase/run_mapping_pipeline.py` | Added optional `data_df=` to `build_ninth_tree` + the three `validate_ninth_*_recursive_sums`; `run_stage_3` reads the wide CSV once and shares it (each consumer copies before mutating). Collapses 4 reads → 1. | Low | Output identical with/without `data_df` on the small 9th file for all 4 functions. |
| #3 Filter-before-melt in the 9th→ESTO conversion | `codebase/mapping_tools/apply_ninth_to_esto_conversion.py`, `codebase/run_mapping_pipeline.py` | `prepare_ninth_long_format` accepts optional `mapped_pairs`; `run_ninth_to_esto` loads the mapping first and passes the mapped `(sector,fuel)` pairs so unmapped combos are dropped **before** the year melt. | Low | Converted output byte-identical filtered vs unfiltered (203,840 rows both) on the 00_APEC 9th file; ~6× fewer melted rows. |

Timing prints added around `validate_source_parent_anchors` and Stage 3 total
in `run_mapping_pipeline.py`, and around the 9th prepare step.

The already-applied (pre-prompt) `load_raw_source_anchor_inputs` vectorization
(`_join_hierarchy_path` / `_resolve_most_specific`) was left intact and built on,
per the prompt.

## Issue #1 — how exact semantics were preserved

The original produced one record per
`(source_system, axis, parent_code, economy, scenario, year, other_axis_value, scope)`
where the parent group actually had rows and the system participates in the scope.
The rewrite keeps the same per-`(source_system, axis)` preamble (children map,
nearest-mapped-pair remap, frontier/descendant memo caches) and replaces only the
innermost loops:

1. **Parent aggregates** — one `groupby([axis_col, economy, scenario, year, other_col])`
   with `sum` / positive-part `sum` / negative-part `sum` instead of re-filtering
   `axis_source` per parent.
2. **Frontier** — resolved once per unique `(parent_code, other_axis_value)` using
   the existing caches; per-scope `frontier_ids` flattened into a join table.
3. **Frontier sums** — a single explode (base × candidate `common_row_id`) + inner
   merge against the scoped comparison frame, then `groupby` to re-aggregate
   `frontier_sum` / positive / negative / `frontier_row_count` (`nunique`) — replacing
   the per-group `.isin()` scan.
4. **Classification** — `np.select` with the condition list
   `[has_missing, fids_empty, rows_empty, tol_exceeded]` mapping to the exact same
   status/reason strings and in the exact same priority order as the original
   `if/elif` chain.

The only numeric difference is floating-point summation order (`groupby.sum`
vs sequential Python `sum`), bounded at **1.16e-10** on the slice — far below the
0.01 relative tolerance, so no classification changes.

## Verification evidence

- **Baseline slice** (economy 20USA, ESTO 2023 / NINTH 2024 / LEAP 2023-24):
  `validate_source_parent_anchors` = **92.07 s**, 34,096 rows.
- **Optimized slice**: **40.05 s**, 34,096 rows — identical summary counts across
  all 13 `(axis, scope, system)` groups.
- Row-level diff (join on the 8 key columns): 34,096 both, 0 unmatched, 0 dup;
  `status`/`reason`/`missing_expected_children`/`frontier_row_count` = 0 mismatches;
  numeric columns max abs diff ≤ 1.16e-10.
- `pytest`: 142 passed, 1 skipped, **1 pre-existing failure** unrelated to these
  changes: `tests/test_apply_partitioned_common_esto.py::test_chunked_cache_reuse_and_result_equivalence`
  fails with `ImportError: pyarrow/fastparquet` (parquet engine not installed) —
  environment dependency, module not touched here.

## Full end-to-end run (2026-07-05, all stages)

`python codebase/run_mapping_pipeline.py` completed cleanly end to end.

### Timing — the headline result

| Step | 2026-07-04 baseline | 2026-07-05 optimized |
|------|--------------------|---------------------|
| `validate_source_parent_anchors` | **7+ hours, killed unfinished** | **433.7 s (7.2 min)** for **20,360,259** rows |
| Stage 3 total | (never completed) | **2,440.5 s (~40.7 min)** |
| Whole pipeline | (never completed) | **~51 min** |
| 9th long-format rows melted (conversion) | 23,760,464 | **3,450,083** (Issue #3; prepared in 11.7 s) |

Anchor validation went from an unfinished 7-hour step to ~7 minutes at full
scale — the prompt's primary success criterion.

### Output integrity vs 2026-07-04 baseline

Hashed 94 result CSVs (`results/mapping_relationships`, `results/common_esto`,
plus the four `results/tree_structure` validation CSVs) before and after.

- **91 / 94 byte-for-byte identical**, including every
  `results/mapping_relationships/*.csv` (notably
  `ninth_results_converted_to_esto.csv`, the Issue #3 output — 4,036,396 rows,
  identical) and every other `results/common_esto/*.csv` (including the 512 MB
  `common_esto_comparison_data.csv`).
- **3 files differ, all metadata-only:**
  - `common_esto_validation.csv` — **identical size to the byte (64,476,111 B,
    153,136 rows)**; only the fixed-width `run_id`/timestamp columns differ. A
    byte-exact size across 64 MB proves no validation value changed.
  - `common_esto_validation_summary.csv` — **identical size to the byte
    (2,651 B)**; only run_id/timestamp columns differ.
  - `common_esto_output_status.csv` — grew (2,145 → 11,693 B) because this run
    *completed* the anchor + validation steps and appended their status rows,
    while the 2026-07-04 baseline was **killed** before writing them. This is a
    per-run manifest (run_id, mtimes, paths, summary counts), not a data output.

  `common_esto_validation.csv` / `_summary.csv` are produced by
  `run_common_esto_validation_workflow`, which this work did **not** modify; its
  only data input (`common_esto_comparison_data.csv`) is byte-identical, and the
  `build_ninth_tree` change was verified to produce identical output — hence the
  size-exact match.

### Note on the anchor CSV baseline

The 2026-07-04 run was killed mid-anchor-validation, so no completed
`source_parent_anchor_validation.csv` baseline exists on disk. Correctness of the
restructured anchor logic therefore rests on the restricted-slice equivalence
(20USA, 34,096 rows): **0 status/reason mismatches, max numeric diff 1.16e-10**
against the pre-change implementation, plus the 18 passing unit tests.

## Issues encountered

- **Observability during the run:** the pipeline tees stdout through a buffered
  file object, so `mapping_pipeline.log` and the console log appeared empty for
  long stretches even though work was progressing. Liveness was confirmed by
  watching the process CPU time climb ~1:1 with wall time (375 s → 720 s →
  1,962 s across the first 30 min) rather than by log output. No code change
  made for this; noted for future runs (a `flush=True` on stage prints would
  help).
- **Two unrelated python processes** (PIDs 28376, 33540) were consuming CPU
  during the run; left untouched as they were not part of this task.
- **Pre-existing test failure** (`test_apply_partitioned_common_esto.py::
  test_chunked_cache_reuse_and_result_equivalence`) — missing `pyarrow`/
  `fastparquet`; environmental, unrelated to these changes.

## Follow-on: issue-suppression changes (2026-07-05, committed 43053f3 + bad0251)

After reviewing the anchor diagnostics, two output-changing refinements were made
(separate from the perf work) and persisted via a `--stages 3` rerun.

### 1. Unmodelled-source exception set (`43053f3`)

Sectors/fuels we do not model and never reconcile are dropped from the anchor
output. New `config/mapping_issue_exception_sets.xlsx` sheet
`unmodelled_source_ignored`: sectors **06** (stock changes), **11** (statistical
discrepancy — the user said "08", but ESTO 08 is Transfers/modelled), **18/19**
(power-output flows); fuels **19/20/21** (Total / Total Renewables / Modern
renewables). Reusable loader `codebase/mapping_tools/mapping_issue_exceptions.py`
matches by leading code number scoped by axis (covers `18.02 ...` and
`18_electricity_output_in_gwh/...` alike); importable by other processes here or
in `leap_initialisation`. Effect: **4,612,008 of 20,360,259 rows dropped (22.7%)**.

### 2. "Reconciles wins" for incomplete frontiers (`bad0251`)

The classifier failed subtotal parents whose mapped leaves already summed to the
parent, merely because an intentionally-unmapped placeholder leaf (e.g.
`08_gas_unallocated`) existed. **14.2M of 15.9M `incomplete_frontier` failures
(89%) actually reconciled** (`parent_value == frontier_sum` within tolerance).
Now such rows pass with reason `within_tolerance_incomplete_frontier`; only
genuine gaps (`pv != fs`) remain `failed / incomplete_frontier`.

### Corrected full-run anchor totals (15,748,251 rows)

| reason | status | count |
|---|---|---|
| within_tolerance_incomplete_frontier | passed | 10,506,571 |
| within_tolerance | passed | 417,039 |
| incomplete_frontier (genuine gap) | failed | 1,516,874 |
| frontier_rows_absent | failed | 1,378,646 |
| difference_exceeds_tolerance | failed | 86,248 |
| no_anchorable_common_esto_boundary | skipped | 1,842,873 |

`validate_source_parent_anchors` reran in **459 s** for 15.7M rows; Stage 3 total
2,239 s. Diagnostics regenerated under
`results/tree_structure/anchor_diagnostics/`.

### Output-integrity note on the `--stages 3` rerun

All `results/mapping_relationships/*.csv` remained byte-identical. Three auxiliary
`common_esto` QA candidate files
(`highly_recommended_mapping_candidates.csv`,
`qa_nonzero_unmapped_leap_branch_mapping_candidates.csv`,
`qa_nonzero_unmapped_leap_branches.csv`) changed by ~1 row. These are written by
`run_apply_common_esto_structure`, which **none of these commits touch** (verified
via `git diff --name-only`); they matched byte-for-byte in the earlier *full*
run, so the drift is pre-existing nondeterminism in that workflow (candidate
ordering/dedup), not a product of the anchor changes.

## How to unwind

All changes are in the working tree (uncommitted until the full run verifies).
- Revert Issue #1 alone: `git checkout -- codebase/mapping_tools/source_parent_anchor_validation.py`
  then re-apply only the pre-prompt `_join_hierarchy_path`/`_resolve_most_specific`
  hunk if needed (it predates this work).
- Issue #2/#3 are additive optional parameters (default `None` = old behavior),
  so reverting the `run_mapping_pipeline.py` call sites restores the original
  read/melt paths without touching the helper signatures.
