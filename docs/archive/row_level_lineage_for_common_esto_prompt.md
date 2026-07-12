# Prompt: row-level lineage for Common ESTO comparison values

Repo: `C:\Users\Work\github\leap_mappings`. Read `AGENTS.md` first and follow repo
conventions, including the "Prompt docs workflow" section — **once this prompt's work
is complete (implemented, tested, and committed), move this file out of
`docs/prompts/` into `docs/archive/`**, matching the pattern in
`docs/archive/common_esto_lineage_validation/`.

## Background (state as of 2026-07-09)

`leap_dashboard` reads `results/common_esto/common_esto_comparison_data.csv`, keyed by
`comparison_scope` + `common_row_id` + economy/scenario/year. That file only carries
aggregated totals — there is no way today for a user to see which raw LEAP/Ninth/ESTO
source rows fed a given dashboard value, or what share of a one-to-many source
aggregate went where (`codebase/mapping_tools/target_share_allocation.py` already
computes that share during conversion, but the number is applied and then discarded).

Row-level detail is destroyed in the real production pipeline at two confirmed points:

- **Loss point 1**: `convert_leap_results_to_esto()`
  (`codebase/mapping_tools/convert_leap_results_to_esto.py`) and
  `convert_ninth_results_to_esto()`
  (`codebase/mapping_tools/apply_ninth_to_esto_conversion.py`) each build an in-memory
  `merged_df` that joins raw source rows to their ESTO `target_flow`/`target_product`,
  optionally apply `apply_target_dataset_allocation()`, then immediately
  `.groupby(...)["value"].sum()` over columns that exclude the original
  `source_flow`/`source_product` — discarding original-source identity before writing
  `leap_results_converted_to_esto.csv` / `ninth_results_converted_to_esto.csv`.
- **Loss point 2**: `apply_common_esto_structure.py::apply_common_structure()`
  (`codebase/mapping_tools/apply_common_esto_structure.py:713-818`) joins ESTO-shaped
  rows to `common_rows_df` to get `common_row_id` per row (into an in-memory
  `mapped_df`), then `.groupby(...)["value"].sum()` (lines 811-817) drops row-level
  ESTO-component identity before writing `common_esto_comparison_data.csv`.

There is an orphaned prototype, `codebase/mapping_tools/apply_partitioned_common_esto.py`
(`apply_partition_frame()`), that computes a similar lineage schema in one hop — but it
bypasses the real two-stage pipeline entirely, was only ever run on a LEAP-only 20_USA
slice, was never wired for Ninth/ESTO, has no concept of `allocation_share`, and
predates the 2026-07-09 comparison-scope unification fix (all four comparison scopes
now share one structural partition — see `build_common_esto_structure.py`'s
`COMPARISON_SCOPES`). **Do not revive it.** Reviving it means rebuilding and
re-validating a second, parallel computation of the same numbers with no guarantee it
agrees with the real output.

## Goal

Add lineage as a small additive side-output at the two existing loss points, reusing the
exact in-memory frames production code already builds (`merged_df` in the two
converters, `mapped_df` in `apply_common_esto_structure.py`) before they get summed
away. This guarantees the lineage numbers are byte-for-byte consistent with the real
aggregated output — same code path, captured one step earlier. No new partitioned-cache
mechanism is needed: LEAP is ≤1.79M rows/economy and Ninth's long-format frame is
already pre-filtered to mapped pairs before melting (`prepare_ninth_long_format`) —
both well within what today's pipeline already holds in memory for a full run.

## Required work

### 1. `codebase/mapping_tools/convert_leap_results_to_esto.py`

- `convert_leap_results_to_esto(...)`: add `return_lineage: bool = False`. When True,
  before the final groupby, also return a lineage frame sliced from `merged_df`
  (post-rollup, post-allocation) with columns: `source_system, economy, scenario, year,
  source_flow, source_product, target_flow, target_product, relationship_id,
  allocation_share, allocation_source, value` (value = allocation-adjusted
  contribution). Default behavior (no arg) must be unchanged — same single-DataFrame
  return, so existing callers and tests are unaffected.
- `run_conversion(...)`: add `lineage_output_path: Path | None = None`; when set, call
  the converter with `return_lineage=True` and write the lineage frame via `to_csv`,
  mirroring the existing optional `rollup_audit_path` write already in this function.

### 2. `codebase/mapping_tools/apply_ninth_to_esto_conversion.py`

Mirror the same change on `convert_ninth_results_to_esto(...)` and `run_conversion(...)`.
`run_mapping_pipeline.run_ninth_to_esto()` calls `convert_ninth_results_to_esto()`
directly (not through `run_conversion()`), so that call site needs
`return_lineage=True` passed explicitly, not just the optional path threaded through.

ESTO needs no lineage file at this loss point — an ESTO exact row already *is* the raw
row (`run_esto_exact_rows()`), 1:1, no join to lose.

### 3. `codebase/mapping_tools/apply_common_esto_structure.py`

- `apply_common_structure(source_df, common_rows_df, return_lineage: bool = False)`:
  keep the existing 3-tuple return for all current callers (both call sites in this
  file — `run_common_esto_comparison_fast_path` and `run_apply_common_esto_structure` —
  already unpack exactly 3 values, and existing tests in
  `tests/test_apply_common_esto_structure.py` do the same). When `return_lineage=True`,
  additionally return a 4th frame: a column subset of `mapped_df` (before the groupby)
  with `comparison_scope, source_system, economy, scenario, year, esto_flow,
  esto_product, common_row_id, common_flow_code, common_flow_name, common_flow_label,
  common_product_code, common_product_name, common_product_label, common_row_basis,
  is_exact_row, requires_rollup, source_aggregate_labels, source_aggregate_group_ids,
  component_sign, value` (value = ESTO-component contribution after sign applied). No
  new join is required — `mapped_df` already has every column.
- `run_apply_common_esto_structure(...)`: request `return_lineage=True`, write the 4th
  frame using the same `write_csv_with_locked_fallback()` helper already used for every
  other Stage 3 output, and register it in the `common_esto_output_status.csv` manifest
  loop like the other artifacts. Leave `run_common_esto_comparison_fast_path()`
  unmodified (cached fast-iteration path, not the canonical dashboard-producing path).

### 4. `codebase/run_mapping_pipeline.py`

Add path constants next to `LEAP_ESTO_PATH`/`NINTH_ESTO_PATH`/`COMMON_ESTO_DIR`:

```python
LEAP_SOURCE_LINEAGE_PATH    = RELATIONSHIP_DIR / "leap_source_to_esto_component_lineage.csv"
NINTH_SOURCE_LINEAGE_PATH   = RELATIONSHIP_DIR / "ninth_source_to_esto_component_lineage.csv"
ESTO_COMPONENT_LINEAGE_PATH = COMMON_ESTO_DIR / "esto_component_to_common_row_lineage.csv"
```

- `run_leap_to_esto()`: pass `lineage_output_path=LEAP_SOURCE_LINEAGE_PATH`.
- `run_ninth_to_esto()`: call `convert_ninth_results_to_esto(..., return_lineage=True)`,
  write the returned lineage frame to `NINTH_SOURCE_LINEAGE_PATH` with the same
  `.parent.mkdir(...)` + `.to_csv(...)` idiom already used for `converted_df`
  immediately below it.
- `run_stage_3()`: pass through so `run_apply_common_esto_structure()` writes
  `ESTO_COMPONENT_LINEAGE_PATH`.

All outputs live under the existing `results/common_esto/...` and
`results/mapping_relationships/...` convention — already covered by the blanket
`results/` gitignore entry, no new ignore rule needed.

## Output schemas and the verification join

**`leap_source_to_esto_component_lineage.csv` / `ninth_source_to_esto_component_lineage.csv`**
(one row per raw source row → ESTO target it feeds):
`source_system, economy, scenario, year, source_flow, source_product, target_flow,
target_product, relationship_id, allocation_share, allocation_source, value`

**`esto_component_to_common_row_lineage.csv`**
(one row per ESTO component → common row it feeds):
`comparison_scope, source_system, economy, scenario, year, esto_flow, esto_product,
common_row_id, common_flow_code, common_flow_name, common_flow_label,
common_product_code, common_product_name, common_product_label, common_row_basis,
is_exact_row, requires_rollup, source_aggregate_labels, source_aggregate_group_ids,
component_sign, value`

**To answer "what fed this dashboard cell?"** for a given `(comparison_scope,
common_row_id, economy, scenario, year)`:

1. Filter `esto_component_to_common_row_lineage.csv` on those 5 keys →
   `(source_system, esto_flow, esto_product, value)` rows. Their `value` sum equals the
   dashboard's displayed number (same aggregation key, same in-memory frame the real
   output came from).
2. For each row where `source_system` is LEAP or NINTH, join into that system's
   `source_to_esto_component_lineage.csv` on `(source_system, economy, scenario, year,
   target_flow=esto_flow, target_product=esto_product)` to get the raw contributing
   rows, `allocation_share`, and `relationship_id`. For `source_system == "ESTO"`, skip
   this hop — the ESTO row already is the raw row.

No fabricated splits and no re-derived numbers anywhere in this chain — both hops
reuse values the pipeline already computed and trusts.

## Known gap — do not try to fix in this prompt

`apply_source_rollups()` returns original rows plus additional derived rows under a
rolled label, with no back-pointer from a derived row to the original raw rows it was
built from. So `source_flow`/`source_product` in the lineage file is "the flow/product
actually used for the ESTO join," which may already be a rollup label rather than the
fully-raw export value. Exploding further into individual raw branches would need
`leap_source_rollup_audit.csv` joined in as a later enhancement — out of scope here.

## Explicitly out of scope

- Reviving `apply_partitioned_common_esto.py`.
- The separate common_sector/common_fuel-only dimension-crosswalk idea (a prior,
  distinct discussion — raise a new prompt for that if pursued).
- Any `leap_dashboard` UI/drill-down changes (separate repo, separate prompt).
- Adding lineage to `run_common_esto_comparison_fast_path()`.

## Tests to add

- `tests/test_convert_leap_results_to_esto.py` (new): lineage sums to the aggregated
  value; lineage carries a real (non-1.0) `allocation_share` when target-dataset-share
  allocation fires; default call (no `return_lineage`) still returns a single
  DataFrame.
- `tests/test_apply_ninth_to_esto_conversion.py`: same three, mirrored.
- `tests/test_apply_common_esto_structure.py` (extend): lineage sums to the matching
  `comparison_df` row; a genuine fan-in (two ESTO components → one common row) produces
  >1 lineage row against 1 aggregated row; default call still returns exactly a
  3-tuple.
- Extend the existing pipeline smoke test to confirm the three new lineage CSVs are
  created by a tiny fixture run and reconcile with their corresponding aggregated CSVs.

## Success criteria / verification

1. `C:\Users\Work\miniconda3\python.exe -m pytest -q tests` passes, including the new
   tests above.
2. Run the real conversion + Stage 3 functions on the existing 20_USA / current data and
   confirm: the three new lineage CSVs are written; each lineage file's `value`,
   grouped by its aggregation key, exactly reproduces the corresponding existing
   aggregated CSV's `value` (the core correctness property — lineage must never
   disagree with production output).
3. Manually pick one dashboard cell's `(comparison_scope, common_row_id, economy,
   scenario, year)` from `common_esto_comparison_data.csv`, follow the two-hop join
   above by hand (small pandas snippet), and confirm the raw rows found sum back to
   the displayed value.
4. Commit only this prompt's files with a `codex:` commit and report the commit.
5. Move this prompt file from `docs/prompts/` to `docs/archive/` once the above is done
   and committed.
