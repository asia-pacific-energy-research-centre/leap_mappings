# Special rules and design decisions

This is the decision log for `leap_mappings`. Record rules whose correct behaviour cannot be derived from source data, canonical configuration, or the established hierarchy. Keep implementation details in code documentation. Update an existing entry and its history rather than creating a duplicate.

Cross-repository decisions use a `CROSS-###` ID and have one authoritative entry in the repository that owns the implementation. Other affected repositories should link to that entry instead of copying it.

Only settled semantic rules belong here as decisions. Current workbook behaviour,
computer-generated suggestions, temporary workarounds, and mapping plans that still
need row-by-row review must be labelled **provisional** and tracked in
`docs/work_queue.md`. A statement that describes the present workbook is not evidence
that the workbook is correct.

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

**Status:** Existing QA mechanism; subtotal classifications pending full review (MAPQ-030)
**Owner:** leap_mappings
**Type:** Mapping
**Affected areas:** `config/outlook_mappings_master.xlsx`;
`config/mapping_issue_exception_sets.xlsx` sheet
`subtotal_mismatch_allowed`;
`codebase/hierarchy_subtotal_contract_workflow.py`; Stage 1 relationship QA

### Situation

ESTO, the 9th Outlook, and LEAP expose different hierarchy depths. A subtotal on one axis can legitimately represent the same scope as a leaf on another, so subtotal status alone does not determine whether a mapping is wrong.

### Options

- Reject every subtotal-to-non-subtotal mapping. This is simple but incorrectly rejects valid comparisons between datasets with different detail.
- Accept every mismatch. This preserves coverage but can hide a leaf mapped to an unnecessarily broad target.
- Flag only a leaf source mapped to an aggregate target when a more specific target exists at the same flow. This focuses review on avoidable loss of detail.

### Current rule

Use the third option. Reviewed acceptable cases must be listed in `subtotal_mismatch_allowed`; unlisted cases remain review items and are not silently accepted.

This describes how the current QA mechanism separates findings. It does **not**
approve the present `*_is_subtotal` values in the mapping sheets. Those values
need a careful, workbook-wide semantic review before they can be treated as
correct; that work is queued as MAPQ-030.

### Validation

Run the hierarchy/subtotal contract review when structural evidence changes,
then run Stages 1–3. Confirm that workbook subtotal decisions match the
reviewed contract, exception rows remain explicit, and parent/child totals stay
consistent after a mapping change. The archived maintenance helper tests
preserve the old allowlist-splitting behavior as historical coverage; they do
not make `results/maintenance/subtotal_mismatches.csv` current.

### History

- 2026-06-27: Recorded the rule already implemented and described in `docs/mappings_system.md`.

## MAP-002: Rejected mappings do not remain in the maintained mapping sheets

**Status:** Confirmed
**Owner:** leap_mappings
**Type:** Workbook content
**Affected areas:** `config/outlook_mappings_master.xlsx` sheets `leap_combined_esto` and `leap_combined_ninth`; mapping coverage outputs containing `counterpart_presence_state`; mapping maintenance and refresh checks

### Situation

Earlier workbook versions retained rejected mappings with
`duplicate_to_remove = True` as historical guardrails. This mixes known-wrong
relationships with the maintained mapping source and makes it harder to tell
whether every row is intended to be correct.

### Options

- Retain rejected rows in the mapping sheets as inactive guardrails.
- Remove rejected rows from the maintained mapping sheets and preserve review
  history in planning notes, Git history, or QA evidence.
- Replace a rejected relationship with a reviewed correct mapping.

### Current rule

Use the second or third option. The maintained mapping sheets should contain only
relationships believed to be correct. A rejected relationship is removed rather
than retained behind `duplicate_to_remove = True`. Its absence is not evidence
that it should be regenerated; any replacement still requires semantic and
cardinality review.

### Validation

Confirm rejected rows are absent from the maintained mapping sheets. Compare raw
and rollup-aware cardinality before and after each replacement, and check
source-versus-mapped totals; a coverage increase is not sufficient evidence by
itself.

### History

- 2026-06-27: Recorded the earlier retained-guardrail practice.
- 2026-07-28: Superseded that practice. Human direction is that the maintained
  workbook contains only mappings believed to be correct; rejected rows are
  removed rather than kept inactive.

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

## MAP-006: Aggregate ESTO flows are excluded from structural edge creation

**Status:** Existing implementation; subtotal inputs pending full review (MAPQ-030)
**Owner:** leap_mappings
**Type:** Comparison
**Affected areas:** `codebase/mapping_tools/build_common_esto_structure.py` (`build_source_aggregate_edges`); `codebase/mapping_tools/build_energy_balance_relationships.py` (`RELATIONSHIP_COLUMNS`, `build_relationship_rows`); `config/outlook_mappings_master.xlsx` sheet `leap_combined_esto` column `esto_pair_is_subtotal`

### Situation

The Common ESTO graph connects ESTO (flow, product) pairs into a shared common row whenever a single source observation maps to more than one ESTO target.  This is the correct behaviour for source aggregates that genuinely span multiple ESTO components (for example, a Ninth fuel bucket that maps to several ESTO sub-fuels).

However, some LEAP sectors are mapped simultaneously to their specific ESTO demand-sector flow *and* to a parent aggregate flow via the `tfc_comparison` rollup.  For example, LEAP `Industry` produces both `(14 Industry sector, product)` and `(12 Total final consumption, product)` as ESTO targets.  Without filtering, the graph draws an edge between flows 14 and 12, then transitively pulls in flows 13 and 16.01-16.02, collapsing all four into a single `12,13,14,16.01-16.02 Total final consumption` common row.  That row is inert in the dashboard (its combined flow code matches no page rule) but pollutes the output and obscures the correctly separate rows.

### Options

- Ignore the spurious row.  It causes no dashboard harm but creates noise and makes the Common structure harder to audit.
- Exclude parent aggregate ESTO flows from the graph entirely.  They would lose their own standalone common rows.
- Exclude parent aggregate targets only from *edge creation*, keeping them as standalone common rows.  Subtotal pairs are still recorded in the aggregate-group metadata for diagnostics.

### Current rule

Use the third option.  The `esto_pair_is_subtotal` column in the relationships pipeline carries a `True` flag for any ESTO target that is a known top-level aggregate.  `build_source_aggregate_edges` excludes rows where `esto_pair_is_subtotal = True` when collecting the pairs used to draw structural edges; those targets still appear as their own common rows.

This is the current graph-building behaviour, not approval of every workbook
subtotal flag feeding it. The complete subtotal classification across all three
mapping sheets must be re-derived carefully in MAPQ-030.

### Separate-axis shadow refinement

The generated separate-axis contract may map one source pair directly to
several products under the same subtotal flow. Excluding those direct targets
from edge creation splits one source value across unrelated Common rows. The
separate-axis shadow path therefore enables
`allow_direct_subtotal_edges=True` and applies these narrower rules:

- direct reviewed subtotal targets may define an aggregate edge;
- every rollup-derived target remains excluded from edge creation;
- a declared non-expanding subtotal flow never shares a Common row with its
  child flows; and
- several products on that same protected subtotal flow may remain together
  so one source observation is delivered once.

This is opt-in. The default remains `False`, so the canonical-master path keeps
the rule documented above. Common-row `rollup_mode` is propagated uniformly
across every component in the row; conflicting nonblank modes fail the build
instead of producing ambiguous output metadata.

The following ESTO flows are marked `esto_pair_is_subtotal = True` in `leap_combined_esto`:

| ESTO flow | Reason |
| --- | --- |
| `07 Total primary energy supply` | Top-level supply-side aggregate; not a structural detail row |
| `08 Transfers` | Transfers parent aggregate; sub-flows (interproduct transfers, gas separation, etc.) are the structural detail |
| `09 Total transformation sector` | Top-level transformation aggregate; corresponds to the LEAP-generated `Total transformation - no transfers` rollup (see MAP-010) |
| `09.06 Gas processing plants` | Transformation sub-group aggregate |
| `09.08 Coal transformation` | Transformation sub-group aggregate |
| `09.13 Hydrogen transformation` | Transformation sub-group aggregate |
| `12 Total final consumption` | Top-level demand aggregate; structurally equivalent to the sum of all demand-sector flows |
| `13 Total final energy consumption` | Demand aggregate excluding non-energy use; same structural position as flow 12 |
| `14 Industry sector` | Sector-level demand aggregate |
| `14.03 Manufacturing` | Manufacturing sub-sector aggregate |
| `15 Transport sector` | Sector-level demand aggregate |
| `16.01 Commercial and public services` | Buildings sub-sector; parent of Datacentres and unallocated completion child |
| `16.01-16.02 Buildings` | Combined buildings aggregate used by LEAP Buildings mapping |

### Validation

After rerunning the Common ESTO structure build, confirm that `12,13,14,16.01-16.02 Total final consumption` no longer appears as a common flow code. Confirm that standalone common rows for flows 07, 09, 12, 13, 14, and 15 are still generated. Confirm that sector-level demand rows (14.xx, 15.xx, 16.01-16.02, etc.) remain correctly grouped by product aggregates from Ninth source data. Review the hierarchy/subtotal contract and current Stage 1 relationship QA after any change to this list; do not use a legacy `subtotal_mismatches.csv` as current evidence.

### History

- 2026-06-28: Identified that the `tfc_comparison` rollup caused LEAP `Industry` and `Buildings` to produce cross-flow graph edges, generating the spurious `12,13,14,16.01-16.02` combined row.  Decided to use `esto_pair_is_subtotal` as the exclusion signal and marked flows 07, 12, and 13 as subtotals in `leap_combined_esto`.
- 2026-06-30: Extended subtotal marking to the full set of parent/aggregate ESTO flows (08, 09, 09.06, 09.08, 09.13, 14.03, 15, 16.01, 16.01-16.02) so that edge exclusion and M6 subtotal-alignment checks apply consistently across supply, transformation, and demand sections.  Marking `09 Total transformation sector` as a subtotal is consistent with MAP-010: LEAP uses a generated frontier (`Total transformation - no transfers`) that sums non-transfer children, so mapping the LEAP total to the ESTO parent aggregate is semantically correct and should not trigger M6 mismatch warnings.
- 2026-07-29: Added the opt-in separate-axis refinement after the source-once
  diagnostic proved that direct subtotal targets on the product axis must
  aggregate while the protected flow parent remains separate from its
  children. The generated shadow result has zero unsafe fan-outs; canonical
  defaults are unchanged.
- 2026-08-03: Retained published `08 Transfers` parent observations in the
  ESTO exact-row extract. Some economies, including the United States, report
  non-zero transfer values on the subtotal parent while its `08.01-08.99`
  child rows are zero or incomplete; dropping the parent removed all ESTO
  transfer history from Common ESTO and the dashboard.

## MAP-008: Commercial services require an unallocated completion child

**Status:** Confirmed
**Owner:** leap_mappings
**Type:** Hierarchy
**Affected areas:** optional missing-ESTO-row review; ESTO flow `16.01`;
Common ESTO hierarchy validation

### Situation

`16.01.01 Datacentres` represents only part of commercial/public services,
while the existing `16.01 Commercial and public services` row contains the
whole parent. Treating Datacentres as the parent's only child makes recursive
validation incomplete and makes parent/detail additive selection unsafe.

### Current rule

`16.01.99 Commercial and public services unallocated` is the structural
completion child for eligible products present under `16.01`. Product
eligibility is established by mapping the ESTO product to its best-supported
Ninth fuel and requiring non-zero data for the exact Ninth sector
`16_01_01_commercial_and_public_services`. The missing-ESTO-row review
calculates every year as
`16.01` minus `16.01.01 Datacentres`; a missing Datacentres row is zero. New
keys go to the insert output. Existing `16.01.99` keys that differ go to a
separate update output and are never silently replaced.

### Validation

Confirm each retained product has exact Ninth sector/fuel evidence. For every
economy/product/year, confirm `16.01.01 + 16.01.99 = 16.01` within tolerance.
Report negative remainders, duplicates, and unresolved keys, and confirm no
rows remain after simulated paste-back.

### History

- 2026-06-29: Confirmed `16.01.99` as the required structural completion child.
- 2026-06-29: Added exact Ninth sector/fuel eligibility, calculated remainder
  values, and separate handling for existing rows requiring replacement.

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

- **`CROSS-001: LEAP template and import ID integrity`** is owned by
  `leap_initialisation`. It defines when an economy's LEAP export template must
  be refreshed, how unresolved `-1` IDs and duplicate logical import keys are
  treated, and which post-refresh checks are required. The archived mapping
  maintenance resolver still names two retired `full model export.xlsx`
  locations; because neither is present, it currently falls back to
  mapping-sheet hierarchy rather than consuming the maintained per-economy
  templates. Mapping maintenance does not own LEAP import IDs. See
  [`leap_initialisation/docs/special_rules_and_design_decisions.md`](../../leap_initialisation/docs/special_rules_and_design_decisions.md#cross-001-leap-template-and-import-id-integrity).

## MAP-010: Total transformation uses a generated LEAP frontier and exact reference parent

**Status:** Confirmed
**Owner:** leap_mappings
**Type:** Comparison
**Affected areas:** `leap_rollup_rules`; ESTO source-row preparation; Common ESTO source-aggregate metadata; dashboard aggregate overview

### Current rule

`Total transformation - no transfers` is a generated LEAP rollup. It is the
sum of the configured non-transfer transformation branches and is not expected
to exist in raw LEAP balance exports. For the aggregate comparison, LEAP uses
that generated detail frontier while ESTO and Ninth use their exact
`09 Total transformation sector` parent rows.

Stage 3 preserves `common_row_id`, row-basis flags, and source-aggregate
membership so consumers can pair those representations without matching a
display label. ESTO source preparation retains the exact parent/product pairs
explicitly mapped by this rollup in addition to the ordinary non-subtotal
frontier. No other rollup parent receives this exception unless it is reviewed
and added explicitly.

The exact `09` parent remains useful for direct comparison even where the
available child hierarchy is incomplete. It must not be added to its generated
detail frontier in the same total.

### Validation

- Confirm LEAP rows selected for this comparison have `requires_rollup = True`.
- Confirm ESTO and Ninth rows have `is_exact_row = True`.
- Confirm all selected rows carry source-aggregate membership for
  `Total transformation - no transfers`.
- Treat parent-versus-incomplete-children validation differences as visible
  hierarchy diagnostics, not permission to replace the direct parent value.

### History

- 2026-06-29: Confirmed the source rollup/reference-parent pairing and added
  stable metadata so the dashboard no longer relies on the shared display label.

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

### 2026-07-29: Separate-axis generated-master shadow gate

- **Newly discovered decisions:** direct reviewed subtotal targets must be
  eligible to group products on the separate-axis shadow path, while
  rollup-derived edges stay suppressed and protected parent flows remain
  separate from their children.
- **Unresolved decisions blocking canonical promotion:** approve or narrow the
  changed Common partition, 3,501 provisional relationships, eight within-axis
  many-to-many components, and 29 broad Common rows.
- **Provisional assumptions used to continue:** the provisional Cartesian
  relationships remain enabled for end-to-end testing; they are review debt,
  not production approval.
- **Rules that became automated validation:** structural source-once results
  distinguish protected parent/detail alternatives from unsafe fan-out;
  conflicting Common-row rollup modes fail; converted Ninth values and Common
  application are bounded by economy; and lineage is published atomically.
- **Coverage and dropped rows:** Stage 3 read 18,657,595 source rows after
  configured exclusions, applied 2,579,778 non-zero relevant rows, wrote
  1,658,315 Common fact rows, and reported 520,964 rows outside the exact
  component map. The dominant ESTO/ESTO Extended groups are source parents,
  combined flows, and subtotals, while other out-of-contract pairs remain
  reviewable; 598 rows are one Extended-only Ninth pair in the base-ESTO
  scope. This is coverage review, not source-once failure.
- **Totals and source-once:** all ten mapped scope/source combinations preserve
  100% of mapped values; maximum absolute difference is
  `1.1641532182693481e-10`. The generated structure has 54 protected
  parent/detail alternatives and zero unsafe source fan-outs.
- **Output contract:** ten Stage 3 artifact/status records passed; the atomic
  fact contract contains 1,658,315 rows, metadata contains 2,365 unique keys,
  and component lineage is a 259,058,883-byte gzip.
- **Hierarchy consistency:** all 30 non-expanding frontier checks pass and
  Stage 2 has zero missing or duplicate components. The recursive source-tree
  and parent-anchor suite was skipped explicitly during this RAM-constrained
  shadow value gate and remains part of a future production-promotion
  rehearsal.
- **Mapping cardinality and semantics:** 29 broad Common rows remain, with a
  maximum of 126 exact components. There are 14 unresolved partial-coverage
  rows in each three-source scope and 178 non-zero LEAP branches without a
  direct ESTO mapping; none generated a copy-ready high-confidence candidate.

## MAP-011: Ignored sectors/fuels are excluded via the exception set, not chased as mapping gaps

**Status:** Decided
**Owner:** `leap_mappings`
**Type:** Mapping / QA scope
**Affected areas:** `config/mapping_issue_exception_sets.xlsx`; ESTO and 9th Outlook source data; the sibling `leap_initialisation` repo (shares the same exception set for its own equivalent processes)

### Situation

ESTO and 9th Outlook source data contain sectors/fuels that are deliberately not modelled (not represented in LEAP or the comparison scope at all). Left unhandled, these show up as unmapped-nonzero findings and get chased as if they were missing mappings, when in fact there is nothing to map them to.

### Current rule

Record these sectors/fuels in `config/mapping_issue_exception_sets.xlsx` so QA and maintenance tooling can exclude them from unmapped/coverage findings, rather than treating every appearance as a gap to close. Other processes — in this repo or in the sibling `leap_initialisation` repo — that need to recognise the same "not modelled, ignore" scope should also read from this exception set instead of re-deriving their own list.

### History

- 2026-07-22 (approx.): Rule captured in a standalone working note (`prompts 5-7.md`, since archived to `docs/archive/`) during the same session that reviewed the mapping-issue exception workflow; folded into this decision log on 2026-07-23 so it doesn't rely on a loose root-level file for discoverability.

## MAP-012: Provisional working directions for detailed power processes

**Status:** Provisional; row-by-row review in progress
**Owner:** `leap_mappings`
**Type:** Mapping / comparison boundary
**Affected areas:** `config/outlook_mappings_master.xlsx`; ESTO Extended power
categories; LEAP-to-Ninth and Ninth-to-ESTO mappings; power-source fallback
rules

### Situation

The consolidated LEAP power structure contains detailed Electricity Generation,
CHP, and Heat plant processes. It also contains alternative names and legacy
branches that must not be treated as additive processes. Some LEAP `Others`
processes still contain biomass, biogas, and waste fuels despite the presence
of dedicated solid-biomass processes, so those branches cannot always be
separated cleanly at the Ninth Outlook's biomass/other boundary.

### Working directions from the current review

The points below are starting directions for building ESTO Extended mappings,
not proof that the current workbook, subtotal flags, rollups, or proposed rows
are correct. They must be tested against complete sibling coverage and reviewed
again while MAPQ-029/MAPQ-031 are enacted.

The detailed category-creation and coarse-crosswalk rules are maintained in
[`esto_extended_category_creation_considerations.md`](esto_extended_category_creation_considerations.md).

- `Electricity Generation/Processes/Imported electricity` is an electricity
  import, not a generation technology. Map it to Ninth `02_imports` and ESTO
  `02 Imports`, with the electricity fuel/product. Do not map it to
  `09_01_electricity_plants` or an ESTO electricity-plant flow.
- Treat `Battery`, `Batteries`, and `Distributed storage` as alternative LEAP
  names for the same storage concept, targeting Ninth `09_01_12_storage`.
  They are not additive categories. A future LEAP structure cleanup should
  retain one canonical process name and retire the aliases.
- Treat `Solar_rooftop` and `Solar rooftop` as alternative names for the same
  rooftop-solar process. They are not additive categories. A future LEAP
  structure cleanup should retain one canonical spelling.
- Map `Coal_H2_blended` within the coal-power family, rather than the Ninth
  other-fuel category. Its initial Ninth comparison target is
  `09_01_01_coal_power`; preserve the hydrogen fuel mapping on the product
  axis.
- Use an explicit combined **Other + solid biomass** comparison boundary where
  a LEAP `Others` process still overlaps the dedicated solid-biomass process.
  For CHP this combines Ninth `09_02_04_biomass` and `09_02_05_others`; for
  Heat plants it combines `09_x_04_biomass` and `09_x_05_others`. The LEAP
  contributors are the corresponding `Solid Biomass` and `Others` process
  branches. This is a declared rollup, not a direct many-to-many base mapping.
  Apply the same principle to Electricity Generation after confirming the
  exact Ninth contributor set, because its `Others` branch spans biomass,
  other-renewable, and other-fuel products.
- Branches whose names end in `_do not use` are legacy/alternative structures.
  Do not activate them alongside their replacement branches.

Main-activity and autoproducer ESTO power children must be combined through
reviewed ESTO/ESTO_EXTENDED rollups before mapping LEAP or Ninth categories
that do not distinguish producer type. Do not express that mismatch as two
active direct targets from one source pair.

### Validation required before implementation

- Confirm alias pairs are mutually exclusive, or add a source fallback that
  selects one branch per economy/scenario/year.
- Confirm every detailed power comparison uses a non-overlapping source
  frontier; parent and detailed process rows must not be counted together.
- Confirm the Other + solid biomass contributor sets reconcile to the
  corresponding source parent for every available economy.
- Preserve ESTO Extended child identifiers through a stable registry; adding
  a new alphabetically sorted LEAP process must not renumber existing
  categories.
- Rerun mapping cardinality, source-total preservation, and parent/child
  validation after the mappings and rollups are implemented.

### History

- 2026-07-28: Recorded the decisions from the read-only review of
  `data/temp/new demand branches remapping plan.xlsx` and
  `data/temp/new leap rows.xlsx`. No mapping workbook changes were made.

## MAP-013: ESTO Extended pair authority is structural, and suspicious global axis components block promotion

**Status:** Decided and implemented
**Owner:** `leap_mappings`
**Type:** Mapping authority / compiler safety
**Affected areas:** `config/outlook_mappings_single_axis.xlsx`;
`codebase/separate_axis_mapping_exploration_functions.py`;
`codebase/separate_axis_mapping_master_prototype_workflow.py`

### Situation

ESTO Extended categories describe model detail that can legitimately be zero
in every currently available year. Requiring final-year ESTO non-zero evidence
therefore removed valid detailed flow mappings. During the same review, a
one-row shift in the old Buildings subtotal mapping block propagated 36
incorrect fuel/product relationships into the global fuel axis and collapsed
37 products into one connected component.

### Decision

- Ordinary ESTO continues to require final-year non-zero evidence or an
  explicit reviewed-extra pair.
- ESTO Extended accepts every structurally present exact pair plus reviewed
  extras, regardless of current values.
- A product-axis component spanning multiple numbered target fuel families is
  a blocking compiler error.
- Any axis component with more than 12 source-plus-target nodes is a blocking
  compiler error.
- Small many-to-many hierarchy bridges remain visible for semantic review; they
  are not silently treated as equivalent to a broad global fuel collapse.
- A context-specific relationship must stay at pair/context level. It must not
  be promoted to a global axis merely because it appeared in one sector block.

### Verification

The 2026-07-30 corrective run removed all 36 shifted relationships, restored
56 Extended flow-axis and 33 Extended product-axis relations, generated 331
Extended LEAP-to-ESTO rows, and preserved 100% of mapped values in every
scope/source combination. The former 37-product Common component and its
20USA dashboard heading are absent.

## MAP-014: Keep nonspecified non-road transport on the nonspecified ESTO flow

**Status:** Decided
**Owner:** `leap_mappings`
**Type:** Mapping simplification / cardinality control
**Affected areas:** `config/outlook_mappings_single_axis.xlsx`;
LEAP-to-ESTO transport flow axis

### Situation

The modelling workflow moves some fuels from implausible detailed transport
flows, and from some other demand flows, into
`Transport non road/Nonspecified transport` to reduce the number of modelled
fuel-flow combinations. Mapping that aggregate LEAP flow to all three ESTO
transport flows (`15.02 Road`, `15.03 Rail`, and
`15.06 Non-specified transport`) created a many-to-many flow-axis component.

### Decision

Map `Transport non road/Nonspecified transport` only to
`15.06 Non-specified transport`. Do not restore its former mappings to
`15.02 Road` or `15.03 Rail` merely to mirror the source-side redistribution.

This deliberately accepts a small residual allocation error in the final
comparison in exchange for a simpler, interpretable mapping and no artificial
many-to-many transport-flow relationship.

### History

- 2026-07-30: Removed the Road and Rail mappings from the editable single-axis
  workbook; retained only the ESTO nonspecified-transport mapping.

## MAP-015: LEAP refinery output uses the inclusive own-use boundary

**Status:** Decided
**Owner:** `leap_mappings`
**Type:** Comparison-boundary alignment
**Affected areas:** `config/outlook_mappings_single_axis.xlsx`; Common ESTO
Refining comparisons

### Decision

Map `Oil Refining/Oil Refining` directly to
`09.07 Oil refineries (including own use)` on both the ESTO and Ninth axes.
LEAP reports the refinery process at this inclusive boundary and does not
publish refinery own use as a separately additive observation. Remove the
maintained `Other loss and own use/Oil refineries` flow-axis relationships so
a future structural placeholder cannot be added to the already-inclusive LEAP
refinery amount.

ESTO continues to derive the inclusive comparison row from its exact
`09.07 Oil refineries` and `10.01.11 Oil refineries` contributors. Ninth
continues to use its maintained inclusive refinery rollup. Exact source rows
may remain available upstream for audit, but the shared Refining comparison
boundary is the inclusive category.

### History

- 2026-08-09: Confirmed against current LEAP balance exports, which contain
  non-zero `Oil Refining/Oil Refining` observations and no reported
  `Other loss and own use/Oil refineries` observations.

## MAP-016: Keep base ESTO and ESTO Extended anchor hierarchies separate

**Status:** Decided
**Owner:** `leap_mappings`
**Type:** Validation provenance / temporary numerical-scope policy
**Affected areas:** dataset-tree compilation; source-parent anchor validation;
APEC-first diagnostics

### Situation

Both ESTO-format input files were previously compiled with `dataset=esto`.
Consequently, base ESTO anchor checks could expand through technology branches
that exist only in ESTO Extended. This produced false missing-child findings,
including base `09 Total transformation sector` checks whose valid native ESTO
children reconciled exactly.

ESTO Extended is currently structurally populated but numerically zero-filled,
so its numerical anchors are not meaningful yet.

### Decision

- Compile the ordinary source as `esto` and the Extended source as
  `esto_extended`; validators must select the tree using explicit source-system
  provenance.
- Do not run numerical anchor checks for `esto_extended_leap` or
  `esto_extended_leap_ninth` while Extended remains zero-filled. Emit explicit
  `skipped_esto_extended_unpopulated` scope records instead.
- Continue structural validation of Extended codes, hierarchy edges, IDs, and
  mapping relationships.
- If a comparison scope has data for a source/scenario in other periods but
  not the period being checked, classify the row as
  `skipped_no_comparable_scope_period`, not as a numerical failure.
- Use an absolute `0.01 PJ` tolerance for the summed APEC gate. Retain the
  existing relative tolerance for the targeted economy attribution that runs
  only after an APEC issue is found. The former one-percent APEC tolerance
  diluted material gaps against the much larger regional parent value.
- A missing active-scope Common ESTO boundary must not suppress an independently
  demonstrable raw-source hierarchy mismatch. When a maintained direct mapping
  and literal source-parent row exist, compare that parent with its resolved raw
  child frontier and retain a mismatch as
  `parent_child_source_inconsistency`. Report `raw_source_frontier_sum`,
  `raw_source_difference`, and the raw mismatch flag separately from the Common
  ESTO frontier. Shared raw categories with the same maintained direct ESTO
  target remain one grouped APEC signature, and that signature is expanded back
  to its members before economy attribution.
- Re-enable Extended numerical scopes only after a reviewed data-population
  milestone and a fresh real-data verification.

## MAP-017: Build LEAP TFC from domestic demand children

**Status:** Decided
**Owner:** `leap_mappings`
**Type:** Final-demand comparison boundary
**Affected areas:** `config/outlook_mappings_single_axis.xlsx`; LEAP-to-ESTO
conversion; Common ESTO flow 12

### Decision

Generate LEAP `12 Total final consumption` from the five domestic children of
`All demand aggregated`: Buildings, Industry, Road, Transport non-road, and
Other sector. Do not use the `All demand aggregated` parent because that parent
also contains International transport. International marine and aviation
bunker demand remains mapped separately to flows `04-05`.

The exact child paths are used instead of also adding separately modelled
top-level demand sectors. This keeps the generated TFC source frontier
non-overlapping and prevents detailed-sector values from being counted twice.
If the required children are absent, the broader parent is not a valid
fallback for TFC.

### History

- 2026-08-10: Russia exposed the boundary error: the former LEAP TFC total
  exceeded its domestic sector and fuel frontiers by exactly its mapped bunker
  demand. The same review identified missing registered source pairs for
  Buildings/Crude oil and Other sector/Hydrogen. Their normalized LEAP source
  pairs were added to the maintained key-pair registry. Because the matching
  ESTO pairs are historically zero-only, those targets were also registered as
  reviewed extras for ESTO and ESTO Extended; this lets the single-axis
  compiler generate the comparison rows without bypassing its temporal gate.
