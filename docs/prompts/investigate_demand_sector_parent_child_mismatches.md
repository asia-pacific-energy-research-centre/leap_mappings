# Investigate demand-sector parent/child mismatches (14 Industry, 14.03 Manufacturing, 15 Transport)

Repo: `C:\Users\Work\github\leap_mappings`. Read `AGENTS.md` first and follow repo conventions.
This is a **diagnosis task — report only**. Do not edit code, the mapping workbook, or the
exceptions workbook. The deliverable is a written verdict plus proposed exception rows (as text)
for the user to approve.

## Background

Stage 3 of `codebase/run_mapping_pipeline.py` runs an internal Common ESTO parent/child
consistency check (`_validate_common_esto_axis_recursive_sums` in
`codebase/mapping_tools/build_dataset_tree_structure.py`): for each parent node in the flow
hierarchy, per scope/source_system/economy/scenario/year/product, the sum of child rows in
`results/common_esto/common_esto_comparison_data.csv` must equal the parent row within 1%.
Detail output: `results/tree_structure/common_esto_validation.csv`.

On 2026-07-09 the check was changed so that **only a numeric disagreement fails**; a child label
absent from the comparison data while sums still agree now passes with reason
`missing_children_within_tolerance`. The failures that remain in the demand sectors have missing
children AND sums that genuinely disagree (reason `missing_expected_children`, children_sum short
of parent_value).

A frozen pre-fix baseline is saved at
`results/tree_structure/common_esto_validation_baseline_20260708.csv` (same schema). If a fresh
pipeline run has completed since, prefer the current `common_esto_validation.csv`; otherwise use
the baseline and apply the numeric-only failure rule yourself
(`abs_error > 0.01 * max(abs(parent_value), 1)`).

Real-failure counts from the 2026-07-08 baseline, after applying the numeric-only rule
(validation_axis = flow):

| parent_code | source_system | failed checks |
|---|---|---|
| 14 Industry sector | LEAP | 7,493 |
| 14.03 Manufacturing | NINTH | 4,608 |
| 15 Transport sector | NINTH | 1,920 |
| 15 Transport sector | LEAP | 1,299 |
| 14 Industry sector | NINTH | 996 |

These are believed to be pre-existing (unrelated to the 2026-07-09 own-use rollup work). The
question to answer: **are these gaps "subsectors we deliberately do not model" (→ candidates for
an exception), or a mapping/coverage bug (→ needs fixing)?**

## Method

Work one concrete case end-to-end before generalising. Suggested: `14.03 Manufacturing` /
NINTH / one economy (e.g. USA), one mid-range year, one product with a large absolute difference.

1. From the validation detail, list for that case: `missing_expected_children`, `parent_value`,
   `children_sum`, `difference`, and which children ARE present (compare the tree's child list —
   `_common_esto_validation_children_map` — against `common_flow_label` values in the comparison
   data for that scope).
2. For each missing child, check whether it carries nonzero energy in the source balances:
   - NINTH: the converted NINTH dataset used by the pipeline (see Stage `data_convert` outputs).
   - LEAP: the exported LEAP results CSV.
   - ESTO: the ESTO balance CSV.
   If a missing child is ~zero in the source, the gap is cosmetic. If it is materially nonzero,
   determine why it never reaches the comparison data:
   - not present in any mapping sheet in `config/outlook_mappings_master.xlsx` (→ unmodelled by
     choice or by omission — check `results/mapping_relationships/energy_balance_relationships.csv`
     and the QA outputs under `results/mapping_relationships/qa/`), or
   - mapped but excluded (`include_in_use_case` false, coverage exclusions, or dropped in Stage 2 —
     check `results/common_esto/qa_common_esto_components_missing_from_structure.csv` and
     `qa_common_esto_excluded_components.csv`).
3. Quantify materiality per parent: what share of `parent_value` does the unexplained gap
   represent (median and worst case across economies/years)? A systematic ~x% shortfall points to
   a missing subsector; noisy signs point to double counting or misassignment.
4. Repeat the classification (steps 1–3, abbreviated) for `14 Industry sector`/LEAP and
   `15 Transport sector`/NINTH+LEAP — these may have different causes; do not assume 14.03's
   explanation transfers.

## Deliverable

A short report (markdown, save to `docs/prompts/` alongside this file with suffix `_FINDINGS.md`)
containing, per parent × source_system:

1. Verdict: `unmodelled-by-design` / `mapping-bug` / `mixed` / `cosmetic-zero`, with the evidence
   (one worked example each, with numbers).
2. The exact child flows responsible for the bulk of the difference, and their share of it.
3. For every `unmodelled-by-design` verdict: proposed exception rows for a future
   `parent_child_mismatch_allowed` sheet in `config/mapping_issue_exception_sets.xlsx`, in this
   format (the sheet does not exist yet — propose rows only, do not create it):
   `enabled | axis | parent_code | source_system | description`
   Parent codes should be the narrowest prefix that covers the issue (e.g. a specific `14.03.xx`
   child family rather than all of `14.03` if only some subsectors are unmodelled).
4. For every `mapping-bug` verdict: which mapping sheet/row family is wrong or missing, and what a
   fix would look like (do not apply it).

## Known pitfalls

- Several results CSVs are large; read with `chunksize` or `usecols` where practical.
- `results/logs/mapping_pipeline.log` buffers heavily; ignore it for this task.
- A long-running `supply_reconciliation_workflow.py` python process may exist; it is unrelated —
  leave it alone.
- `config/E0E85740` and `config/~$outlook_mappings_master.xlsx` are Excel artifacts; ignore.
- The `09.x` transformation-sector failures visible in the same validation files are a separate,
  known issue tied to the own-use rollup restructure — **out of scope here**; do not analyse or
  "fix" them.

## Out of scope

- Any edits to `config/outlook_mappings_master.xlsx` or `config/mapping_issue_exception_sets.xlsx`.
- Implementing the `parent_child_mismatch_allowed` sheet or its validator hook.
- Re-running the full pipeline (query existing outputs; if the comparison data is stale relative
  to the code, say so in the report rather than rerunning).
