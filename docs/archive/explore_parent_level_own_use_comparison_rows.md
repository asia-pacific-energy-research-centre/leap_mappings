# Explore: should parent-level "(including own use)" comparison rows exist?

Repo: `C:\Users\Work\github\leap_mappings`. Read `AGENTS.md` first. This is a **design
exploration — report only**. Do not change code or workbooks; the deliverable is a written
recommendation the user can act on.

## Background (as of 2026-07-09)

The comparison system merges ESTO own-use/loss flows (`10.01.x`) into their matching
transformation sectors at **leaf level**: `esto_rollup_rules` in
`config/outlook_mappings_master.xlsx` defines groups like
`09.08.01 Coke ovens (including own use)` = `09.08.01 Coke ovens` + `10.01.05 Coke ovens`,
Stage 1 (`expand_esto_rollup_targets` in
`codebase/mapping_tools/build_energy_balance_relationships.py`) expands mapping rows that
point at rolled names into per-component relationships, and Stage 2 merges the components
into one common row with the rolled label
(`build_preferred_flow_partition_labels` in
`codebase/mapping_tools/build_common_esto_structure.py`).

The workbook ALSO contained **parent-level** rolled mappings — e.g. LEAP source flow
`Coal transformation` (a parent whose LEAP value already includes its children) mapped to
`09.08 Coal transformation (including own use)` with components
`{09.08 Coal transformation, 10.01.05 Coke ovens, 10.01.07 Blast furnaces}`. This caused a
double-count: the expansion redirected part of the parent's value onto the leaf flow
`10.01.05`, which belongs to the *leaf* coke-ovens partition, so the parent's total leaked
into the leaf common row (verified 2026-07-09: LEAP coke ovens coking-coal appeared at 3x in
`common_esto_comparison_data.csv`). The interim fix was to point those parent-level LEAP
mapping rows back at the plain parent flow (`09.08 Coal transformation`), leaving own use
accounted for only at leaf level.

## The open question

Was a parent-level own-use comparison row (e.g. a dashboard row
`09.08 Coal transformation (including own use)` whose ESTO side sums
`09.08.01 + 09.08.02 + 10.01.05 + 10.01.07`) ever an actual requirement — and if yes, how
should the design support it without double counting?

## What to investigate

1. **Intent.** Search for evidence the parent-level rolled mappings were deliberate:
   - `git log`/`git blame` on the workbook is useless (binary); instead check
     `docs/prompts/` history (especially `side_prompt_esto_rollup_expansion.md`,
     `unify_rollup_rules_prompt.md`), the `Note` column of `esto_rollup_rules`, and any
     dashboard specs in `C:\Users\Work\github\leap_dashboard` that reference
     "(including own use)" labels or `09.08`-level comparison rows.
   - Check whether the dashboard (leap_dashboard repo) or
     `codebase/utilities/leap_results_dashboard_*` consume parent-level common rows at all,
     or only leaves.
2. **Feasibility if wanted.** The structural constraint: a component ESTO flow can belong to
   exactly ONE flow partition per scope (`build_axis_partition_lookup`), so `10.01.05`
   cannot sit in both the leaf coke-ovens row and a parent 09.08 row as a raw component.
   Evaluate the options:
   - (a) Parent rows as *derived subtotals*: the parent/child validator and/or the tree
     (`build_dataset_tree_structure.py`) learns rollup groups, so
     `09.08 (including own use)` is computed as the sum of its (including own use) leaf
     common rows rather than mapped directly. No new partitions needed; fixes the known
     validator mismatch (`09.08` plain parent vs own-use-inclusive children) at the same time.
   - (b) A separate parent-level comparison scope/output where partitions are built at
     parent granularity (`09.08`+`10.01.05`+`10.01.07` as one partition) — heavier, creates
     a parallel structure.
   - (c) Dashboard-side aggregation only (leave the pipeline leaf-only) — cheapest if the
     dashboard is the only consumer.
3. **Consistency.** Whatever option is preferred must keep: LEAP counted once per common
   row; ESTO components counted once; parent = sum(children) in the hierarchy validator
   (`_validate_common_esto_axis_recursive_sums`). State explicitly how the option achieves
   each.

## Deliverable

A short markdown report (save alongside this file, suffix `_FINDINGS.md`):

1. Verdict on intent: deliberate requirement / accidental artifact of the sheet edit, with
   evidence.
2. If a parent-level row is wanted: recommended option (a/b/c) with the concrete code
   touch-points and estimated blast radius; if not wanted: confirm the plain-parent
   mappings are the end state and list any leftover `(including own use)` parent references
   to clean out of the workbook (`09.08`, `09.06` families in `esto_rollup_rules` — note the
   parent groups themselves may stay, since the NINTH side
   (`09_08_coal_transformation_incl_own_use`) legitimately reports at parent level; check
   `unify_rollup_rules_prompt.md` before proposing deletions).
3. Impact on the parent/child hierarchy validator either way (this is the known
   `09 Total transformation sector` missing-children failure family).

## Out of scope

- The demand-sector (14/15/16) validator failures — separate prompt
  (`investigate_demand_sector_parent_child_mismatches.md`).
- NINTH-target rollup expansion (`unify_rollup_rules_prompt.md`).
- Any implementation.
