# Side prompt: verify ESTO rollup expansion + preferred labels (2026-07-09)

Send this together with `run_mapping_pipeline_future_prompt.md`. It describes code changes made on
2026-07-09 and what to verify after the run. Follow the main prompt for how to launch, poll, and
where outputs live; this file only adds run-specific context and acceptance checks.

## What changed in the code (already committed to the working tree)

1. **Stage 1 — `codebase/mapping_tools/build_energy_balance_relationships.py`**
   - New `expand_esto_rollup_targets`: mapping rows whose `esto_flow` names a
     `rolled_esto_flow` from the `esto_rollup_rules` sheet (e.g.
     `09.08.01 Coke ovens (including own use)`) are expanded into one relationship per real
     component flow (e.g. `09.08.01 Coke ovens` + `10.01.05 Coke ovens`), same product.
     Expanded rows carry `notes` = `expanded_from_esto_rollup: <rolled name>`.
   - New QA output `results/mapping_relationships/qa/qa_unknown_esto_target_flows.csv`
     listing ESTO target flows that match no real ESTO flow (their comparisons have no ESTO
     data). A stdout WARNING prints when non-empty. This list is expected to be non-empty
     (hydrogen placeholders etc.) — see acceptance checks.
2. **Stage 2 — `codebase/mapping_tools/build_common_esto_structure.py`**
   - New `build_preferred_flow_partition_labels` + optional
     `preferred_partition_labels` argument on `build_axis_partition_lookup`: when a flow-axis
     partition's component set exactly matches an override group from
     `common_esto_overrides.csv`, the group's `preferred_common_flow_label` is used as the
     partition label instead of the mechanical compressed label
     (previously `09.08.01,10.01.05 Coke ovens`). Such partitions have
     `partition_created_by = manual_override_preferred_label` in the flow-partition QA output.
3. The 2026-07-08 experimental patches to these two files were reverted; the two small crash
   fixes elsewhere were kept (`run_mapping_pipeline.py` final-summary `detail_df` count;
   `codebase/archive/outlook_mapping_maintenance_workflow.py` repo-root resolver).

The workbook `config/outlook_mappings_master.xlsx` was edited by the user (mapping rows now
point at rolled `(including own use)` names). Do not modify the workbook.

## Acceptance checks after the run

Run these after Stage 2 completes (do not wait for Stage 3 to finish to check 1–4).

1. **Expansion fired.** Stage 1 stdout/log contains a line like
   `ESTO rollup target expansion: N -> M rows` with M > N. In
   `results/mapping_relationships/energy_balance_relationships.csv` there are rows with
   `notes` containing `expanded_from_esto_rollup`, and **no** rows whose `target_flow`
   contains `(including own use)`.
2. **Unknown-target QA is only expected placeholders.**
   `qa_unknown_esto_target_flows.csv` should list only known LEAP-only placeholders
   (the `09.13`/`10.01.19` hydrogen family, `09.06.02.01 Liquefaction`,
   `09.06.02.02 Regasification`, `16.01.99 Commercial and public services unallocated`).
   `16.01-16.02 Buildings`, `09.01-09.02 Power sector`, and
   `16.03-16.04 Agriculture and fishing` must NOT appear any more (they are now defined
   rollups and get expanded). Anything else unexpected = report it, do not "fix" the workbook.
3. **Merged rows exist with the preferred labels.** `results/common_esto/common_esto_rows.csv`
   contains rows with `common_flow_label` = `09.08.01 Coke ovens (including own use)` whose
   `component_esto_flow` values include both `09.08.01 Coke ovens` and `10.01.05 Coke ovens`
   (in every scope whose mappings include the edited LEAP rows — at minimum `leap_vs_esto`).
   Spot-check the same for the other own-use sectors the user edited (gas works plants
   `09.06.01`+`10.01.02`, blast furnaces `09.08.02`+`10.01.07`, oil refineries
   `09.07`+`10.01.11`, non-specified `09.12`+`10.01.17`) — check which ones the workbook
   actually points at rolled names before flagging a missing one.
4. **No blob-merging regression.** The merged coke-ovens partition contains exactly the two
   flows, not `09.08 Coal transformation` or `10.01.07 Blast furnaces` as well. If a partition
   unexpectedly contains extra flows, check
   `qa_common_esto_flow_intersections_resolved.csv` and report — do not patch.
5. **No LEAP double counting.** In `results/common_esto/common_esto_comparison_data.csv`, for
   one economy/year, the LEAP value of the `09.08.01 Coke ovens (including own use)` row must
   equal LEAP's raw Coke ovens value (not 2x). The ESTO value should equal
   `09.08.01` + `10.01.05` from the ESTO balance.
6. **Buildings now actually compares.** The Buildings common row(s) should now have ESTO-system
   rows in the comparison data (previously LEAP-only).

## Known pitfalls from the 2026-07-08 session (do not re-diagnose these)

- The pipeline's own log (`results/logs/mapping_pipeline.log`) buffers heavily; an empty or
  stale tail does NOT mean the run is stuck. Judge liveness by process CPU time and output-file
  mtimes (`results/common_esto`, `results/tree_structure`).
- Stage 3 takes roughly an hour; the final source-parent anchor validation previously hit
  `ArrowMemoryError` and was skipped with a "skipped" summary once. If that recurs, note it and
  continue — it does not invalidate the Stage 2/3 comparison outputs.
- A separate long-running `supply_reconciliation_workflow.py` python process may exist; it is
  unrelated — leave it alone.
- `config/E0E85740` and `config/~$outlook_mappings_master.xlsx` are Excel artifacts; ignore.

If an acceptance check fails, capture the evidence (query output, file, log lines) and stop —
report rather than iterating on further code changes.

## Out of scope tonight

Rolled NINTH names in `leap_combined_ninth` (e.g. `09_06_gas_processing_plants_incl_own_use`)
are NOT expanded yet — that is planned separately (see `unify_rollup_rules_prompt.md`). Do not
implement NINTH-target expansion or edit that sheet in this run.
