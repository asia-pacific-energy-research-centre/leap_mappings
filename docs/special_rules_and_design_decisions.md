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

## MAP-003: Partial coverage is actionable only for data-relevant components

**Status:** Confirmed
**Owner:** leap_mappings
**Type:** Comparison
**Affected areas:** `codebase/mapping_tools/build_common_esto_structure.py`; `codebase/mapping_tools/apply_common_esto_structure.py`; `results/common_esto/qa_common_esto_unresolved_partial_coverage.csv`; component-relevance and unused-component diagnostics

### Situation

The structural Common ESTO graph can contain component pairs that have no current comparison data. Reporting every uncovered structural component as high-severity partial coverage creates large numbers of findings that cannot affect current totals and obscures gaps with real data behind them.

### Options

- Treat every structural component as required, regardless of observed values.
- Remove inactive components and their mappings entirely.
- Keep the complete structural view, but make partial coverage actionable only when a component has qualifying non-zero evidence; retain inactive components in informational audits.

### Current rule

Use the third option. A component is relevant when it has a non-zero value in the latest available ESTO base year, a non-zero 9th Outlook projection value from 2023 onward, or a non-zero LEAP balance value. A non-zero LEAP branch without a direct ESTO mapping can activate a component only when LEAP-to-9th and 9th-to-ESTO mappings provide an auditable indirect ESTO pair. Otherwise it remains a branch-level mapping review item.

Stage 2 retains the full structural partial-coverage candidates. Stage 3 writes the actionable subset and separate informational outputs for inactive missing components, existing components without relevance evidence, and non-zero unmapped LEAP branches. Inactive mappings are not deleted automatically because they may be needed for other economies or future data.

### Validation

Confirm the ESTO base year recorded by the run is the latest available ESTO year and that 9th evidence uses projection years only. For each actionable missing pair, confirm at least one evidence flag is true. Confirm excluded structural pairs appear in the inactive-component audit and existing but unused pairs appear in the unused-component audit. Identity and zero-value test fixtures should demonstrate that historical-only ESTO values and pre-projection 9th values do not create actionable findings.

### History

- 2026-06-27: Confirmed the data-relevance rule and retained inactive mappings as informational findings rather than deleting them.
- 2026-06-27: Stage 2/3 verification reduced 268 structural partial-coverage rows to 80 actionable rows, with 370 inactive missing components retained for audit. Mapped-source versus Common ESTO totals remained equal within `9.31e-10` PJ.

## Cross-repository references

- **`CROSS-001: Full-model export and LEAP import ID integrity`** is owned by
  `leap_initialisation`. It defines when the canonical LEAP structure export
  must be refreshed, how unresolved `-1` IDs and duplicate logical import keys
  are treated, and which post-refresh checks are required. Mapping maintenance
  consumes that export for hierarchy and subtotal status but does not own LEAP
  import IDs. See
  [`leap_initialisation/docs/special_rules_and_design_decisions.md`](../../leap_initialisation/docs/special_rules_and_design_decisions.md#cross-001-full-model-export-and-leap-import-id-integrity).

## End-to-end run report

Append a dated subsection after each end-to-end run. Report:

- newly discovered decisions;
- unresolved decisions blocking correct output;
- provisional assumptions used to continue;
- rules that should move into configuration;
- rules that should become automated validation;
- the next decisions requiring human guidance.

Also report coverage, dropped rows, source-versus-output totals, hierarchy consistency, mapping cardinality, and semantic review. A successful process exit is not evidence that the comparison is correct.
