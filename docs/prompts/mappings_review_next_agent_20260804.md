# Prompt: Review the current mappings, rollups, ESTO Extended work, and anchor exceptions

Work in `C:\Users\Work\github\leap_mappings`.

## Objective

Use the completed Aug 3 mapping run to perform a review-only pass over:

- MAPQ-009 semantic mapping findings;
- MAPQ-010 `NON_EXPANDING` versus `DETACHED` rollup semantics;
- MAPQ-029 detailed Electricity Generation, CHP, and Heat process mappings;
- MAPQ-031 ESTO Extended mappings and stable category coverage;
- the complete current anchor-validation exception set;
- the latest Common ESTO hierarchy and source-total outputs.

Produce a bounded decision record and exact proposed changes. Do not apply
mapping rows, rollup rules, subtotal flags, exception rows, or category IDs
during this review unless the user separately approves an implementation step.

## Required preflight

1. Read `AGENTS.md`, `docs/prompts/AGENTS.md`, and
   `docs/mappings_review_pack_20260804.md`.
2. Run `git status --short --branch` and preserve every pre-existing change.
   Do not resolve merge conflicts, reset, clean, delete worktrees, or rewrite
   the canonical workbook as part of the review.
3. Confirm the authority run is
   `common_esto_20260803T114057574740Z` and that
   `results/common_esto/stage3_run_manifest.json` reports `completed`.
4. Confirm the active canonical workbook hash is the one recorded in the
   manifest before comparing workbook rows.
5. Read `docs/mappings_review_evidence_index_20260804.md` and
   `docs/anchor_validation_review_guide_20260804.md`.

## Review sequence

### A. Anchor validation first

Review `results/tree_structure/source_parent_anchor_validation_summary.csv`,
then drill into `source_parent_anchor_validation_full.parquet`, the detailed
validation file, child/context values, and exception-review files. Assign each grouped
finding one of:

- `confirmed_source_issue`;
- `confirmed_mapping_issue`;
- `expected_boundary_effect`;
- `allowlisted_data_quality`;
- `unconfirmed_review`;
- `no_action`.

Do not treat all failed checks as mapping defects. Preserve source-system,
scope, axis, economy, scenario, year, parent, frontier, and exception context.

### B. MAPQ-009 semantic findings

Review these files:

- `results/common_esto/qa_common_esto_unresolved_partial_coverage.csv`;
- `results/common_esto/qa_nonzero_unmapped_leap_branches.csv`;
- `results/common_esto/qa_common_esto_partial_coverage_mapping_candidates.csv`;
- `results/common_esto/qa_nonzero_unmapped_leap_branch_mapping_candidates.csv`.

Group rows by semantic cause before judging them. Pay particular attention to
aggregate/boundary flows such as `Total Transformation`, `Total Final Energy
Demand`, `All demand aggregated`, `Other loss and own use`, and `Transfers
unallocated`. The 4 partial-coverage and 15 unmapped-branch candidates are
review-only, even when their axis confidence is high.

### C. MAPQ-010 rollups

Use the active prompt and inspect every included rule in the canonical
workbook's `esto_rollup_rules` sheet. For each rule, record source presence,
replacement presence, hierarchy role, double-counting risk, validator effect,
and whether the same rule behaves differently for ESTO and ESTO Extended.

Classify each rule as `EXPANDING_HIERARCHY`,
`REPLACED_COMPARISON_BOUNDARY`, `DETACHED_DIAGNOSTIC_BOUNDARY`, or
`UNRESOLVED_REVIEW`. Do not change the mode during this pass.

### D. MAPQ-029 and MAPQ-031 together

Review the power-process inventory and proposed mappings as one problem. Check:

- imported electricity versus generation;
- Battery/Batteries/Distributed storage aliases;
- Solar rooftop aliases;
- Coal-H2 placement within coal power;
- parent versus detailed power/CHP/heat outputs;
- Other + solid biomass boundaries;
- main-activity versus autoproducer ESTO rows;
- stable ESTO Extended identifiers;
- complete sibling coverage and raw/rollup-aware cardinality.

Produce an exact proposed row set against the review workbook, not the
canonical workbook. Mark each row `proposed`, `rejected`, `deferred`, or
`needs_user_decision` and explain why.

## Required outputs

Create or update review-only files under `docs/` and, if useful, a compact CSV
under `results/` with:

1. one decision row per semantic issue group;
2. one anchor disposition row per grouped anchor issue;
3. one rule row per active MAPQ-010 rollup;
4. one proposed-change row per MAPQ-029/MAPQ-031 mapping or rollup change;
5. exact evidence paths and current-run identifiers;
6. unresolved decisions and the user decision required.

Do not write to maintained mapping sheets or candidate approval files.

## Stop conditions

Stop and report instead of guessing if:

- the authority run or workbook hash does not match;
- a source/target hierarchy is missing;
- a candidate would create a second target for an existing source pair;
- parent and child rows cannot be separated into a non-overlapping frontier;
- a proposed ESTO Extended identifier would be renumbered;
- the finding is explained only by a label and not by source/hierarchy evidence.

## Final report

Report the number of groups reviewed, accepted/rejected/deferred counts,
anchor dispositions, proposed workbook changes, unresolved user decisions,
and the exact files produced. State clearly that no maintained mapping or
rollup workbook was changed.
