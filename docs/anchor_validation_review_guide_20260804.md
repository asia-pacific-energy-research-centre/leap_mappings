# Anchor-validation review guide — 2026-08-04

## What an anchor finding means

An anchor check asks whether a parent row and its selected child frontier are
consistent for a particular source system, scope, economy, scenario, year, and
axis. A failed check does not by itself prove that a mapping row is wrong.

The same visible mismatch can arise from:

- a genuine source parent/child inconsistency;
- a subtotal or comparison-boundary replacement;
- a parent row being present while its children are absent or zero;
- a mapping that joins the wrong hierarchy level;
- an expected exception already covered by a curated allowlist;
- an unconfirmed finding that needs source or model evidence.

## Required disposition categories

Use exactly one primary disposition per grouped issue:

| Disposition | Meaning |
|---|---|
| `confirmed_source_issue` | Raw source parent/children directly fail the relevant frontier check |
| `confirmed_mapping_issue` | Source data and hierarchy are sound, but the maintained mapping selects the wrong scope or target |
| `expected_boundary_effect` | The mismatch is created by a reviewed rollup, detached boundary, or parent/detail replacement |
| `allowlisted_data_quality` | The exact issue is covered by a reviewed exception with matching scope and source identity |
| `unconfirmed_review` | Evidence is incomplete or contradictory |
| `no_action` | The finding is structural/informational and does not require a change |

Do not use `confirmed_mapping_issue` merely because the Common hierarchy
validator failed.

## Review procedure

For each grouped failure:

1. Start with `source_parent_anchor_validation_summary.csv` and identify the
   scope, source system, axis, and confirmed/unconfirmed status.
2. Open the matching rows in
   `source_parent_anchor_validation_full.parquet` or
   `source_parent_anchor_validation.csv` to identify economy, scenario, year,
   parent, and child frontier.
3. Inspect the row-level evidence in
   `source_parent_anchor_validation.csv`.
4. If the finding is marked source-related, inspect
   `source_parent_anchor_child_values.csv`,
   `source_parent_anchor_child_context_values.parquet`, and the relevant rows in
   `source_parent_anchor_economy_examples.csv`; compare the raw parent against
   the independent child sum.
5. Check the active rollup rule and the Common rollup explanation. A
   `NON_EXPANDING` or `DETACHED` replacement may intentionally hide children
   from an ordinary parent-child comparison.
6. Check the maintained mapping sheet and the source/target subtotal flags.
7. Check whether the same issue repeats across scopes or is isolated to one
   dataset/economy.
8. Record the disposition, evidence path, and next action in the review pack.

## Practical triage order

Review these families first:

1. Ninth flow failures in `esto_leap_ninth`, especially transformation and gas
   processing families.
2. LEAP flow failures in `esto_leap`, where the summary marks all 393 as
   confirmed.
3. LEAP/Ninth flow failures in `esto_leap_ninth`, separating source issues from
   detailed power or non-expanding boundaries.
4. Ninth product failures in `esto_leap_ninth`.
5. ESTO flow findings marked unconfirmed; these may be source or boundary
   issues rather than maintained mapping defects.

## Special cautions

- Do not restore a removed mapping because a diagnostic mentions it.
- Do not apply a computer-generated candidate while an anchor finding for the
  same family is unresolved.
- Do not count a parent and its detailed children as additive until the
  frontier/rollup policy says they are non-overlapping.
- Keep raw-source inconsistency evidence separate from Common ESTO hierarchy
  evidence.
- Treat zero-only or structurally present-but-unavailable Extended scopes as
  non-numeric evidence unless the validator explicitly marks them eligible.

## Review row template

| Scope | Source system | Axis | Economy/scenario/year | Parent | Frontier/children | Summary status | Raw-source result | Rollup/boundary | Disposition | Evidence | Owner/next action |
|---|---|---|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  |  |  |  |
