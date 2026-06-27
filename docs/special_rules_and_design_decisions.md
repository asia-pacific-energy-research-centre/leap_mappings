# Special rules and design decisions

This is the decision log for `leap_mappings`. Record rules whose correct behaviour cannot be derived from source data, canonical configuration, or the established hierarchy. Keep implementation details in code documentation. Update an existing entry and its history rather than creating a duplicate.

Cross-repository decisions use a `CROSS-###` ID and have one authoritative entry in the repository that owns the implementation. Other affected repositories should link to that entry instead of copying it.

## MAP-001: Subtotal-to-non-subtotal mappings need a narrower-target test

**Status:** Confirmed
**Owner:** leap_mappings
**Type:** Mapping
**Affected areas:** `config/outlook_mappings_master.xlsx`; `config/mapping_issue_exception_sets.xlsx` sheet `subtotal_mismatch_allowed`; `codebase/outlook_mapping_maintenance_workflow.py`; `results/maintenance/subtotal_mismatches.csv`

### Situation

ESTO, the 9th Outlook, and LEAP expose different hierarchy depths. A subtotal on one axis can legitimately represent the same scope as a leaf on another, so subtotal status alone does not determine whether a mapping is wrong.

### Options

- Reject every subtotal-to-non-subtotal mapping. This is simple but incorrectly rejects valid comparisons between datasets with different detail.
- Accept every mismatch. This preserves coverage but can hide a leaf mapped to an unnecessarily broad target.
- Flag only a leaf source mapped to an aggregate target when a more specific target exists at the same flow. This focuses review on avoidable loss of detail.

### Current rule

Use the third option. Reviewed acceptable cases must be listed in `subtotal_mismatch_allowed`; unlisted cases remain review items and are not silently accepted.

### Validation

Run the mapping maintenance workflow. Confirm that `subtotal_mismatches.csv` contains only unapproved cases, allowlisted rows are separated as allowed, and parent/child totals remain consistent after any mapping change. Unit coverage for allowlist splitting is in `tests/test_outlook_mapping_maintenance_workflow.py`.

### History

- 2026-06-27: Recorded the rule already implemented and described in `docs/mappings_system.md`.

## MAP-002: Removed-only counterparts are unavailable guardrails

**Status:** Confirmed
**Owner:** leap_mappings
**Type:** Exception
**Affected areas:** `config/outlook_mappings_master.xlsx` sheets `leap_combined_esto` and `leap_combined_ninth`; mapping coverage outputs containing `counterpart_presence_state`; mapping maintenance and refresh checks

### Situation

Some removed rows are retained to document mappings that would create many-to-many relationships. Their presence in the workbook can look like a missing active counterpart even though reactivation would change mapping cardinality and totals.

### Options

- Treat `removed_only` as a mapping gap and restore a row, risking many-to-many aggregation.
- Treat it as unavailable, preserving the guardrail while leaving the source without that counterpart.
- Add a narrower active mapping after an explicit cardinality review.

### Current rule

Treat `counterpart_presence_state == removed_only` as unavailable, not as an instruction to restore the row. Add or reactivate a mapping only after showing that the narrowest proposed relationship does not introduce unintended many-to-many coverage.

### Validation

Compare raw and rollup-aware cardinality before and after a proposed change. Check duplicate/conflict outputs and source-versus-mapped totals; a coverage increase is not sufficient evidence by itself.

### History

- 2026-06-27: Recorded the existing guardrail from repository guidance.

## End-to-end run report

Append a dated subsection after each end-to-end run. Report:

- newly discovered decisions;
- unresolved decisions blocking correct output;
- provisional assumptions used to continue;
- rules that should move into configuration;
- rules that should become automated validation;
- the next decisions requiring human guidance.

Also report coverage, dropped rows, source-versus-output totals, hierarchy consistency, mapping cardinality, and semantic review. A successful process exit is not evidence that the comparison is correct.
