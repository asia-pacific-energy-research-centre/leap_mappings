# Special rules and design decisions

This is the decision log for `leap_mappings`. Record rules whose correct behaviour cannot be derived from source data, canonical configuration, or the established hierarchy. Keep implementation details in code documentation. Update an existing entry and its history rather than creating a duplicate.

Cross-repository decisions use a `CROSS-###` ID and have one authoritative entry in the repository that owns the implementation. Other affected repositories should link to that entry instead of copying it.

## MAP-007: Empty validation detail is not pass evidence

**Status:** Decided
**Owner:** `leap_mappings`
**Type:** Validation orchestration
**Affected areas:** Stage 3 Common ESTO output manifest; Common hierarchy validation outputs

### Situation

An empty mismatch CSV is ambiguous: checks may have passed, no checks may have
been eligible, validation may have been skipped, or the file may belong to an
older run.

### Current rule

Only a current-run summary row with `status=passed`, a positive eligible-parent
count, and provenance matching the Stage 3 comparison file is evidence of a
pass. Zero eligible checks is `skipped`; mismatches are `failed`; exceptions are
`error`. The mismatch detail is replaced for every attempted run, including
skip and error outcomes, and all Stage 3 and validation records share one run ID.

### Validation

Automated tests cover pass, fail, zero eligibility, missing input, exceptions,
stale input provenance, stale detail replacement, and shared Stage 3/validation
run identifiers.

### History

- 2026-06-28: Established the explicit status/provenance contract and automatic
  post-Stage-3 hierarchy validation orchestration.

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
- 2026-06-27: The 80 grouped actionable findings were expanded to 324 one-pair rows so evidence and mapping ownership are unambiguous.

## MAP-004: Mapping candidates use independent axes and require human approval

**Status:** Confirmed
**Owner:** leap_mappings
**Type:** Mapping
**Affected areas:** `codebase/mapping_tools/mapping_candidate_generation.py`; partial-coverage and unmapped-LEAP candidate CSVs; `config/outlook_mappings_master.xlsx`

### Situation

Many missing pair mappings can be inferred from repeated patterns: branches or sectors usually determine the ESTO flow, while fuels usually determine the ESTO product. Combining those axes can reduce manual work, but a technically plausible combination can still be wrong because of hierarchy, context, aggregation, or cardinality.

### Options

- Require every missing pair to be mapped manually without suggestions.
- Generate candidates and insert them automatically.
- Generate copy-friendly candidates from independent axis evidence and observed non-zero source pairs, with explicit confidence and warnings, but require human approval before workbook changes.

### Current rule

Use the third option. Copy-ready candidates are generated only when both axes have evidence, the combined source pair is non-zero, axis confidence is high, and the source pair does not already have a target. Exact source-axis patterns are preferred; LEAP branch inference may fall back to collapsed repeated paths or leaf names. One-axis-only, zero-only, medium/low-confidence, and already-targeted cases remain only in their original QA files. Candidates never update the canonical workbook automatically.

### Validation

Every proposed row must identify its destination sheet, contain the sheet's copy columns, reference a non-zero observed source pair, and expose flow/product support and confidence separately. Flag candidates whose source pair already has a target. Before approval, check semantic definitions, subtotal level, hierarchy, and raw/after-rollup cardinality; then rerun the complete affected pipeline.

### History

- 2026-06-27: Confirmed independent-axis, review-only candidate generation for partial coverage and non-zero unmapped LEAP branches.
- 2026-06-27: Initial generation produced one unique high-confidence partial-coverage proposal and 57 unmapped-LEAP proposals. Of 322 unresolved partial pairs, 282 lacked flow-axis evidence and 40 had both axes separately but no observed non-zero pair combining them; no forced candidates were created.
- 2026-06-27: Restricted candidate CSVs to high-confidence, non-zero, complete, not-already-targeted rows and added a combined `highly_recommended_mapping_candidates.csv`; unresolved findings remain only in their original QA outputs.
- 2026-06-27: The restricted output contains 45 copy-ready rows: one partial-coverage mapping and 44 unmapped-LEAP mappings. Medium-confidence and incomplete rows were removed from candidate CSVs.

## MAP-005: Display labels do not determine subtotal exclusion

**Status:** Confirmed
**Owner:** leap_mappings
**Type:** Presentation
**Affected areas:** `codebase/mapping_tools/apply_common_esto_structure.py`; `codebase/run_mapping_pipeline.py`; `results/common_esto/common_esto_comparison_data.csv`; retired `results/common_esto/common_esto_subtotal_rows_filtered.csv`

### Situation

Stage 3 previously removed every Common ESTO row whose flow or product display label contained `Total` or `Subtotal`. This was intended to reduce parent/detail double-counting, but labels do not encode hierarchy reliably. The rule removed valid graph-generated rollups, including the comparison row containing the mapped `14 Industry sector` component.

### Options

- Continue using label text as a subtotal proxy, which suppresses valid rollups and can still miss parents without those words.
- Remove all parent rows using source hierarchy flags, which would also prevent direct parent-level comparisons.
- Retain every mapped Common row and use explicit hierarchy/frontier metadata for any future additive view.

### Current rule

Use the third option. Stage 3 does not exclude a row because its display label contains `Total` or `Subtotal`. `common_esto_comparison_data.csv` retains exact and generated Common rows. It is not safe to sum the complete file without selecting a non-overlapping comparison frontier.

### Validation

Confirm that generated rollups with `Total` in their labels appear in `common_esto_comparison_data.csv`, mapped-universe total preservation remains within tolerance, and the retired label-filter output is not produced. Unit coverage verifies that a generated total label survives Common structure application.

### History

- 2026-06-28: Removed the label-based Stage 3 filter after confirming it suppressed valid generated rollups.

## MAP-008: Commercial services require an unallocated completion child

**Status:** Confirmed
**Owner:** leap_mappings
**Type:** Hierarchy
**Affected areas:** Stage 0 missing ESTO row generation; ESTO flow `16.01`; Common ESTO hierarchy validation

### Situation

`16.01.01 Datacentres` represents only part of commercial/public services,
while the existing `16.01 Commercial and public services` row contains the
whole parent. Treating Datacentres as the parent's only child makes recursive
validation incomplete and makes parent/detail additive selection unsafe.

### Current rule

`16.01.99 Commercial and public services unallocated` is the structural
completion child for every economy/product present under `16.01`. Stage 0 may
generate zero-valued, manual-paste placeholders for missing `16.01.99` rows,
but it does not calculate the residual values. A later allocation step must
populate the child so `16.01.01` plus `16.01.99` reconciles to `16.01`.

### Validation

Confirm Stage 0 requires one `16.01.99` row for every existing `16.01`
economy/product key, does not require Ninth non-zero evidence, and produces no
rows after simulated paste-back. Do not treat a zero placeholder as evidence
that the completed child hierarchy already reconciles.

### History

- 2026-06-29: Confirmed `16.01.99` as the required structural completion child.

## CROSS-002: Ownership of additive comparison frontiers

**Status:** Open
**Owner:** Cross-repository
**Type:** Comparison
**Affected areas:** `leap_mappings` Stage 2/3 Common ESTO outputs; `leap_dashboard` grouping and totals; Common ESTO hierarchy and rollup validation

### Situation

The canonical Common ESTO output can legitimately contain exact parents, descendants, and generated rollups for different comparison purposes. Retaining them preserves information, but summing them indiscriminately can double count. The current output does not identify a validated, non-overlapping set of rows for each presentation context.

### Options

- Make each dashboard infer and remove subtotals. This allows presentation-specific choices but duplicates semantic logic and risks inconsistent totals.
- Make Stage 3 publish only one additive frontier. This is simple for consumers but discards valid alternative detail and summary views.
- Make Stage 3 publish all rows plus centrally validated frontier metadata or separate named additive views. Dashboards select an appropriate declared view but do not infer hierarchy from labels.

### Current rule

No additive frontier rule selected. Stage 3 publishes all mapped Common rows. Until a frontier is implemented, consumers must not treat the complete dataset as one additive table and must not infer subtotal status from display names.

### Decision needed

Should the mapping pipeline publish one additive frontier or several named frontiers for different detail and rollup contexts, and which views are required by the dashboard?

### Validation

For each proposed frontier and each economy/scenario/year/product grouping, confirm that no selected row is an ancestor, descendant, or overlapping rollup of another selected row. Reconcile the frontier total to its declared parent total and report selected, excluded, and unavailable rows.

### History

- 2026-06-28: Opened after retiring the label-based subtotal filter; recommended central frontier metadata with dashboard view selection.

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

### 2026-06-28: Stage 3 after retiring label-based subtotal filtering

- **Newly discovered decisions:** `CROSS-002` was opened because the canonical all-rows dataset needs centrally defined, non-overlapping frontier metadata or named additive views before dashboards can calculate totals safely.
- **Unresolved decisions blocking correct additive output:** decide which detail, summary, and rollup frontiers are required and whether generated aggregate values should be compared alongside, rather than added to, their components.
- **Provisional assumptions used to continue:** Stage 3 now preserves every mapped Common row. The output is treated as canonical comparison data, not as one additive table.
- **Rules that should become configuration:** named comparison-frontier contexts, once agreed, should be explicit configuration rather than inferred from codes or display labels.
- **Rules that should become automated validation:** each frontier must reject ancestor/descendant and overlapping-rollup selections, reconcile to its declared parent, and report eligible checks as well as mismatches.
- **Next decisions requiring human guidance:** approve one central additive frontier or several named frontiers and identify the dashboard views that require them.
- **Coverage and dropped rows:** Stage 3 read 5,490,424 ESTO-shaped rows, used 629,921 non-zero rows, wrote 990,684 Common comparison rows, and reported 39,306 source rows missing a Common map after configured exclusions. It retained 324 actionable partial-coverage rows and 370 inactive findings.
- **Totals:** mapped-universe preservation passed with maximum absolute difference `9.313225746154785e-10` PJ.
- **Hierarchy consistency:** rerunning Common recursive validation after restoring total-labelled rows exposed 4,677 mismatches: 4,672 Ninth product checks (`15 Solid biomass` and `16 Others`) and 5 LEAP flow checks (`09 Total transformation sector`). Industry produced no mismatches; the USA Reference 2060 natural-gas Manufacturing parent differed from its 11 direct children by only `1.82e-12` PJ. The validation still does not report its total eligible-check count.
- **Mapping cardinality and semantics:** Stage 3 warned of 22 product-axis and 27 flow-axis overlapping Common groups. These remain review findings; total preservation alone does not establish that the overlaps are semantically correct or additive-safe.
