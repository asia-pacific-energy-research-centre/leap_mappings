# Admit ESTO Extended flows into the Common ESTO structure

> **Deferred on 2026-07-27; do not start before re-measuring.** The ESTO Extended
> dataset was still being built when this was diagnosed, so the missing structure
> is plausibly just an unfinished state rather than a defect. Re-measure first
> using `docs/revisit_mapping_diagnostics_20260817.md`: if extended-only flows
> present as `common_flow_label` has moved off 5 on its own, this prompt's
> premise no longer holds and it should be rewritten or archived.

## Objective

Make the Common ESTO structure define target rows for the ESTO Extended detail
flows, so that the 730 Extended mapping rows now in the workbook actually reach
Common ESTO output. Then make the pipeline report — rather than silently drop —
any mapping whose target flow has no Common ESTO row.

## Repository

```text
C:\Users\Work\github\leap_mappings
```

Read `AGENTS.md` and its two referenced global instruction files. Inspect
`git status --short` and preserve unrelated changes.

## Confirmed diagnosis (2026-07-27, verified against a clean run)

Run `common_esto_20260727T113042584213Z` was executed with the merged workbook
(commit `947742d`), the source-identity fix, and the source-identity guard all
active. Stages 1, 2, data_convert and 3 all ran. Findings:

The workbook now carries the Extended mappings and they target real flows:

| Sheet | `ESTO_EXTENDED` rows | Distinct extended-only target flows |
| --- | --- | --- |
| `leap_combined_esto` | 313 | 56 |
| `ninth_pairs_to_esto_pairs` | 410 | 56 |
| `esto_rollup_rules` | 7 | 7 |

But those targets mostly do not exist as Common ESTO rows:

| Tree artifact | Extended-only flows present (of 60) |
| --- | --- |
| `results/tree_structure/esto_tree.csv` | 0 |
| `results/tree_structure/esto_extended_tree.csv` | **60** |
| `results/tree_structure/common_esto_tree.csv` | **5** |

So `esto_extended_tree.csv` knows all 60 extended flows, and the mapping rows
point at 56 of them, but the Common ESTO target structure defines only 5.
`09.01.02.01 Coal CHP` works because it was already in the Common ESTO tree;
`09.01.02.02 Gas CHP`, `15.02.02.02.01 BEV large`,
`14.03.01.01 Blast Furnace Basic Oxygen Furnace` and 52 others do not.

**The drop is silent.** In that run these all contained zero rows referencing an
extended-only flow:

```text
results/common_esto/qa_common_esto_components_missing_from_structure.csv   (0 rows)
results/common_esto/qa_common_esto_excluded_components.csv                 (0 rows)
results/common_esto/structural_artifacts/qa_unresolved_structural.csv     (16 rows, none extended)
results/common_esto/structural_artifacts/qa_ambiguous_structural.csv      (27 rows, none extended)
```

A mapping row pointing at an undefined target vanishes with no evidence anywhere.
That is the more serious half of this task: it means coverage can be silently
absent while every QA artifact reads clean.

## Work

1. **Report the drop first, before changing any structure.** Add a QA artifact
   recording every mapping row whose target flow (or flow/product pair) has no
   Common ESTO row, with the source system, sheet, `esto_dataset_scope`, and
   target. Suggested:
   `results/common_esto/qa_common_esto_mapped_targets_without_common_row.csv`.
   Run the pipeline far enough to confirm it lists the 55 missing extended flows.
   Do this first so the fix has a measurable before/after.
2. **Decide how the Extended structure should be admitted.** This is a design
   decision, not a mechanical edit — write it down before implementing:
   - Should the Common ESTO structure be built from `esto_extended_tree.csv`
     when an Extended comparison scope is in play, leaving the ordinary scopes
     built from `esto_tree.csv`?
   - Or should Common ESTO carry one superset structure, with `esto_dataset_scope`
     controlling which rows participate per scope?
   The second keeps one target tree but requires every consumer to respect the
   scope column. The first keeps the bases cleanly separate but means two
   structures must stay consistent. Read `docs/mappings_system.md` and
   `docs/rollup_rules_system.md` before choosing, and record the decision and
   its rationale in `docs/`.
3. **Implement the chosen approach**, keeping the ordinary ESTO basis unchanged.
4. **Do not** create Common ESTO rows for extended flows in the ordinary
   (`esto_leap`, `esto_leap_ninth`) scopes. Ordinary results must not move.

## Validation

1. The new QA artifact lists the missing targets before the fix and is empty (or
   explicitly justified) after.
2. Count extended-only flows present as `common_flow_label` in
   `results/common_esto/common_esto_comparison_data.csv`: 5 before, and after the
   fix it should cover the 56 flows the workbook maps. State the actual number;
   if some remain absent, say which and why.
3. Ordinary-basis regression: for 2023, `09.01.01,09.02.01 Electricity plants`,
   `source_system = ESTO`, scope `esto_leap_ninth`, the Common ESTO value must
   still equal the sum of raw `09.01.01` + `09.02.01` in all 21 economies
   (ratio 1.0). This is the doubling check from the earlier fix — it must not
   regress.
4. Report before/after validation counts per scope and source system. Do not sum
   across overlapping comparison scopes.

## Notes

- The `esto_dataset_scope` column (`BOTH` / `ESTO_EXTENDED`) already exists in
  `leap_combined_esto`, `ninth_pairs_to_esto_pairs` and `esto_rollup_rules`, and
  `build_energy_balance_relationships.py` already reads it, defaulting to `BOTH`.
- A worktree can run the pipeline; see the setup notes in
  `leap_dashboard/docs/handover_mapping_diagnostics.md` (hardlink inputs, copy
  the Stage 1/2 seeds, set `LEAP_BALANCE_EXPORTS_ROOT`). Run stages `1,2` too —
  the Extended mapping rows enter through Stage 1, so a Stage 3-only run does
  not test them.
- Separately queued: `generate_partial_coverage_mapping_candidates()` in
  `codebase/mapping_tools/mapping_candidate_generation.py` raises
  `KeyError: 'source_system'` when the actionable partial-coverage frame is
  empty, which is a legitimate state.
