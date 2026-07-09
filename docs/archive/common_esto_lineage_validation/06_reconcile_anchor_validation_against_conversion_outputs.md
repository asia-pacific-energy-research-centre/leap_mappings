# Prompt 6: reconcile anchor validation against existing conversion outputs

Work in `C:\Users\Work\github\leap_mappings`. Complete Prompts 1-3 first. This
prompt **replaces the tree-walk methodology introduced in Prompt 4**
(`codebase/mapping_tools/validate_lineage_anchors.py`). See
`PROMPT5_STATUS_AND_ISSUES.md` for why: the tree walk manufactures mass false
failures from source-tree vocabulary that does not match the mapped vocabulary,
and from crossing each parent against every unrelated other-axis value.

Use `C:\Users\Work\miniconda3\python.exe` (the system Python 3.13 lacks pyarrow).

## Goal

Verify that parent totals from LEAP, Ninth and ESTO survive mapping into the
common structure by **reconciling raw source parent totals against the
already-correct conversion outputs**, not by re-deriving each source system's
hierarchy from its tree.

## Interpretation and assumptions (read first, and document in the code)

This check treats **"the mapped children sum back to the raw source parent
total"** as evidence that the parent's data was mapped cleanly. State this
explicitly in the module docstring and in `docs/mappings_system.md`:

- This is a **necessary, not sufficient**, condition. Children summing to the
  parent does not *prove* every child was individually mapped to the correct
  common row — in principle offsetting errors could still sum correctly.
- We accept it as the working verification because producing a correct parent
  total by any *other* route would be very hard: to make independently-mapped
  children add back up to the raw parent, the mapping almost certainly has to be
  right. A clean reconciliation is therefore strong (if not absolute) evidence.
- Where a parent total reconciles, report `passed` but do not claim per-child
  correctness beyond this. Where it does not reconcile, that is a real signal.

Do not weaken this into a tautology: the parent total must come from the **raw
source data**, and the children total must come from the **converted output**,
so the two sides are independently derived and can genuinely disagree.

## Trusted inputs (the "already-correct" side)

The upstream pipeline already applies every mapping, rollup and aggregation and
writes converted-to-ESTO results. Reconcile against these rather than
recomputing frontiers:

- `results/mapping_relationships/leap_results_converted_to_esto.csv`
  — columns: `economy, scenario, year, target_flow, target_product, value`
  (source system is implicitly LEAP; no `source_system` column).
- `results/mapping_relationships/ninth_results_converted_to_esto.csv`
  — columns: `source_system, economy, scenario, year, target_flow, target_product, value`.
- `results/mapping_relationships/esto_results_exact_rows.csv`
  — columns: `economy, esto_flow, esto_product, year, value, source_system, scenario`
  (uses `esto_flow`/`esto_product`, not `target_flow`/`target_product`).

Normalize all three to one shape
`source_system, economy, scenario, year, esto_flow, esto_product, value` before
use. Do not assume identical schemas; map the column names per file.

The raw source parent totals come from the same partitioned source caches used
in Prompt 3 (`results/common_esto/partition_cache/...`), read one partition at a
time.

## Required work

1. **Enumerate parents from the tree, nothing more.** Use
   `results/tree_structure/all_dataset_trees.csv` only to list which parent
   nodes exist per `dataset` and `axis`. Never use the tree (or string prefixes)
   to reconstruct a parent's descendants, frontier or expected children.
2. **Left side — raw parent total.** For each parent node, sum the raw source
   values under that parent, per `source_system x economy x scenario x year` and
   per validated axis (flow/sector and product/fuel). The parent's descendant
   set for *summation of raw values* may use the source tree's explicit
   parent/child edges — but only to sum raw source rows, never to predict what
   the mapped output should contain.
3. **Right side — converted total.** From the normalized conversion output, sum
   the value over the common boundary that the parent maps into, for the same
   `source_system, economy, scenario, year` and axis.
4. **Determine the anchorable boundary from the structural artifacts**, not from
   strings. Use `source_pair_to_common_row.csv` / `esto_component_to_common_row.csv`
   to find the common row(s) a parent's members map to. Classify:
   - **exact boundary** — parent maps onto exact ESTO rows
     (`is_exact_row = True`); reconciliation is clean.
   - **rollup boundary** — parent only lands inside a combined/rolled common row
     (`is_exact_row = False`, `connected_component_rollup`) whose value also
     includes unrelated contributors; the parent total cannot be cleanly
     separated. Report these `unanchorable`, not `failed`.
5. **Compare and classify** per parent, axis, system, economy, scenario, year:
   - `passed` — left ≈ right within tolerance.
   - `failed` — anchorable boundary but totals differ beyond tolerance (the real
     signal). Record both totals and the difference.
   - `unanchorable` — no clean common boundary (rollup contamination, or the
     parent maps nowhere in the converted output). A known limitation, never a
     pass and never a hard failure.
   - Empty validation must never be reported as `passed`.

## Coverage

- All three source systems: LEAP, Ninth, ESTO.
- Both axes: flow/sector and fuel/product.
- LEAP note: the source tree does not bridge `Road` to `Passenger road`/`Freight
  road`. Do not try to fix that in the tree — the conversion output already
  contains the bridged result, so reconciling against it is correct by
  construction.

## Validation modes (unchanged contract)

1. `structural`: no values; check inputs, schemas and that every tree parent
   resolves to an anchorable or explicitly-unanchorable boundary.
2. `slice`: one economy and selected boundary years; default numeric mode.
3. `full`: all requested partitions; explicit expensive mode.

Process partition by partition, maintain summaries incrementally, and keep
memory bounded to one partition plus the small structural tables. Reuse the
existing partition/caching, economy-normalization and slice-selection work from
Prompts 3-4; discard only the tree-walk descendant/contamination logic.

## Outputs (keep the existing CSV contract)

- `validation_summary.csv`
- `validation_failures.csv`
- `unmatched_unanchorable_boundaries.csv`
- `partition_status_and_value_accounting.csv`
- a bounded pass sample (counts + small deterministic sample, not millions of rows)

Use actionable reasons: `within_tolerance`, `difference_outside_tolerance`,
`rollup_boundary_not_separable`, `parent_absent_from_converted_output`,
`no_anchorable_boundary`, `empty_validation`.

## Tests and verification

- A parent whose raw total equals its converted total passes.
- A parent with an injected discrepancy fails, with both totals and the
  difference recorded.
- A parent that only maps into a rolled/combined common row is reported
  `unanchorable`, not `failed` and not `passed`.
- LEAP `Road` reconciles via the converted output despite the tree gap.
- Ninth and ESTO reconcile on both axes.
- The raw (left) and converted (right) totals are read from different files, so a
  fabricated mismatch is actually detectable (guard against tautology).
- Slice and full partition results match a small in-memory reference.
- Empty validation is not reported as passed.
- No test depends on string-prefix or tree-derived descendant reconstruction.

Run the USA slice and classify remaining outcomes. Do not call any failure or
unanchorable rate acceptable without inspecting representative records from every
reason.

## Success criteria

- No hierarchy or frontier is inferred from the tree or from string prefixes;
  the tree is used only to enumerate parents.
- Anchor validation covers LEAP, Ninth and ESTO on both axes, reconciling raw
  source parent totals against the converted outputs.
- The `passed`/`failed`/`unanchorable` split is semantically credible on the USA
  slice — the artifact-driven `missing_mapped_child` explosion from Prompt 4 is
  gone.
- The assumption in "Interpretation and assumptions" is documented in code and in
  `docs/mappings_system.md`.
- Memory stays bounded; tests and the slice pass.
- Commit only this prompt's changes with a `codex:` commit; do not edit, stage or
  commit `config/outlook_mappings_master.xlsx` or the Excel lock file.
