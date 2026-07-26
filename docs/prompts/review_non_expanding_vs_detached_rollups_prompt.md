# Prompt: Review `NON_EXPANDING` versus `DETACHED` rollups

Work in `C:\Users\Work\github\leap_mappings`. Read the repository
`AGENTS.md` instructions first. Preserve unrelated working-tree changes,
especially mapping workbooks and generated outputs.

## Purpose

Review every active `NON_EXPANDING` and `DETACHED` rule in the manual ESTO
rollup settings and determine whether the two modes represent a meaningful
semantic distinction or should be merged into one comparison-boundary mode.

This is an evidence and design task first. Do not silently modify the master
mapping workbook, rollup rules, validator semantics, or generated production
outputs.

## Questions to answer

For every active rule, document:

1. The input flow(s), replacement flow, parent label, scope, and stated reason.
2. Whether the input rows remain visible in any output dataset.
3. Whether the replacement row is intended to be a subtotal, an alias, a
   comparison-boundary row, or a detached diagnostic-only row.
4. Whether the input and replacement values can be compared recursively
   without double counting.
5. Whether the distinction affects Common ESTO hierarchy validation, source
   anchor validation, rollup diagnostics, or only presentation.
6. Whether the rule behaves differently for original ESTO and ESTO Extended.

## Required classifications

Classify each rule into one of these proposed semantic categories, or explain
why another category is needed:

- `EXPANDING_HIERARCHY`: source children are retained and should participate
  in parent-child hierarchy checks.
- `REPLACED_COMPARISON_BOUNDARY`: source inputs are intentionally replaced by
  one combined row for cross-dataset comparison and should not be checked as
  ordinary children of that replacement.
- `DETACHED_DIAGNOSTIC_BOUNDARY`: source rows remain conceptually separate
  from the replacement hierarchy and should be reported through a separate
  diagnostic relationship.
- `UNRESOLVED_REVIEW`: the current rule or data is insufficient to decide.

Explicitly test whether the current `NON_EXPANDING` and `DETACHED` modes both
belong to `REPLACED_COMPARISON_BOUNDARY`, with `DETACHED` retained only as a
more specific diagnostic subtype if needed.

## Evidence to inspect

- `config/outlook_mappings_master_combined_esto.xlsx`
  - `esto_rollup_rules`
  - `leap_combined_esto`
  - `ninth_pairs_to_esto_pairs`
- `results/common_esto/common_esto_rollup_explanations.csv`
- `results/tree_structure/common_esto_validation_rollup_diagnosis.csv`
- `results/tree_structure/common_esto_validation_issue_patterns.csv`
- `results/tree_structure/common_esto_tree.csv`
- `results/tree_structure/esto_extended_tree.csv`
- The rollup and validation code in `codebase/mapping_tools/`

Use the gas-processing, oil-refinery, coal-transformation, and any transport
or demand examples as concrete case studies. Check both raw source presence
and final Common ESTO output presence.

## Required outputs

Create a concise review report in `docs/` containing:

- a rule-by-rule inventory;
- a proposed semantic taxonomy;
- examples where the current modes produce different validator behaviour;
- examples where they are functionally identical;
- a recommendation on whether to merge, retain, or rename the modes;
- the exact code and workbook changes that would be required;
- tests needed before changing the canonical rules.

Also create a compact CSV audit table in `results/` with one row per active
rule and fields for the current mode, proposed category, source presence,
replacement presence, hierarchy role, double-counting risk, and review status.

## Safety requirements

- Do not change canonical mappings or rollup rules during the review.
- Do not treat a validation mismatch as proof that a rollup rule is wrong
  until raw input, replacement output, and comparison scope are checked.
- Keep hierarchy edges, mapping routes, and comparison-boundary replacements
  explicitly separate.
- If a rule cannot be classified confidently, mark it `UNRESOLVED_REVIEW`
  rather than inferring intent.
