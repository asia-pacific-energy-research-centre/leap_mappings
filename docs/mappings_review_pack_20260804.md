# Mappings review pack — 2026-08-04

## Purpose

This is the working pack for the next mapping review. It brings together the
fresh MAPQ-005 baseline, the queued MAPQ-009/MAPQ-010/MAPQ-029/MAPQ-031 work,
the full anchor-validation exception review, and the current Common ESTO QA
outputs.

The review is evidence-first. It may produce decisions, rejected candidates,
or a bounded implementation plan, but it must not write mapping rows or rollup
rules until each proposed change has an explicit human disposition.

## Authority run

| Field | Value |
|---|---|
| Run ID | `common_esto_20260803T114057574740Z` |
| Run status | completed with review findings |
| Source scopes | `esto_extended_leap`, `esto_extended_leap_ninth`, `esto_leap`, `esto_leap_ninth` |
| Canonical workbook | `config/outlook_mappings_master.xlsx` |
| Promoted workbook hash | `f9166812df59f3a2d980c2566599a3a9516da6f28b52a7433deffbdc448c6b2e` |
| Run manifest | `results/common_esto/stage3_run_manifest.json` |
| Git context recorded for the run | `2b374654780ac7eb1e7b68f3fc0ffc2efa1e5300` |

The worktree is not a clean checkout. Inspect `git status --short --branch`
before doing anything, preserve unrelated edits, and do not resolve or reset
the existing pipeline conflict as part of this review.

## Recommended review order

1. Freeze the evidence set: confirm the run ID, workbook hash, and output
   timestamps.
2. Review anchor-validation findings and assign dispositions without changing
   mappings.
3. Review MAPQ-009 semantic candidates and group them into accepted,
   rejected/intentional, or deferred families.
4. Review MAPQ-010 rollup semantics using the same findings, especially
   `NON_EXPANDING` versus `DETACHED` cases.
5. Review MAPQ-029 and MAPQ-031 together for detailed power, CHP, heat,
   aliases, parent/detail scope, and ESTO Extended identifiers.
6. Record exact proposed workbook changes separately from approved changes.
7. Only after approval, create a narrow implementation task and rerun the
   affected checks before a full pipeline rerun.

## Queue review map

| Queue item | Review question | Evidence-led output | Do not do yet |
|---|---|---|---|
| MAPQ-009 | Which non-zero gaps are real missing mappings versus aggregates, aliases, boundary rows, or intentional exclusions? | Bounded decision list grouped by semantic cause | Paste all 15 candidates into the workbook |
| MAPQ-010 | Are `NON_EXPANDING` and `DETACHED` materially different, or are they comparison-boundary variants? | Rule-by-rule rollup audit and proposed taxonomy | Change `ROLLUP_MODE` or validator behaviour |
| MAPQ-029 | How should detailed power/CHP/heat rows, aliases, imports, and Other + biomass boundaries be represented? | Exact row/rollup proposal with cardinality and double-counting checks | Edit canonical power mappings |
| MAPQ-031 | Which new LEAP leaves need ESTO Extended targets, Ninth bridges, stable IDs, or explicit out-of-scope treatment? | Reviewed ESTO Extended change set and sibling-coverage matrix | Invent historical values or renumber categories |
| Anchor validation | Is each finding a confirmed source inconsistency, an unconfirmed hierarchy issue, an expected boundary effect, or an allowlisted exception? | Disposition table with evidence and owner | Treat every failed anchor as a mapping defect |

## Fresh baseline headline numbers

- 48 actionable partial-coverage rows.
- 281 non-zero unmapped LEAP branch rows.
- 4 highly recommended partial-coverage candidates.
- 15 highly recommended non-zero unmapped-LEAP candidates.
- 526,443 source rows without a Common ESTO map; this is a broad diagnostic
  volume, not a decision count.
- Mapped-value preservation remained 100% in the reported scope/source
  combinations, with maximum absolute difference `1.1641532182693481e-10`.
- Common hierarchy validation reported 85 ESTO Extended flow mismatches, 8
  LEAP flow mismatches, and 202 Ninth flow mismatches. These are review
  findings, not automatic mapping edits.
- Anchor validation reported 2,156 failed checks in its summary. The summary
  separates confirmed and unconfirmed failures; use that split before making
  any disposition.

## Decision record template

Use one row per semantic issue, not one row per raw diagnostic row.

| Issue group | Source system/scope | Evidence files | Interpretation | Disposition | Owner | Follow-up |
|---|---|---|---|---|---|---|
|  |  |  |  | `accept` / `reject` / `allowlist` / `defer` / `needs data` |  |  |

For every accepted mapping change, record:

- source branch/fuel and target flow/product on each relevant axis;
- whether the source is parent, leaf, alias, or comparison boundary;
- non-zero source evidence and affected economies/years;
- existing targets and raw/after-rollup cardinality;
- sibling coverage impact;
- whether the change is ordinary ESTO, ESTO Extended, Ninth, or LEAP-only;
- the exact workbook sheet and copy columns;
- the focused tests and rerun required after approval.

## Review completion standard

The review is complete when every high-priority evidence family has a recorded
disposition, unresolved items have a reason and owner, and proposed workbook
changes are separated from approved changes. A non-zero diagnostic count is not
itself a failure of the review.
