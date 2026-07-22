# Holistic mapping-system stocktake — findings (2026-07-22)

Diagnosis-only. No workbook, code, or config files were edited. No pipeline
run was started; this analysis is based entirely on the most recent existing
Stage 1–3 outputs already on disk (`run_id common_esto_20260722T053902276979Z`
/ `...T061748036214Z`, written 2026-07-22 11:58–15:34 local). Focused tests
(`tests/test_structural_resolver.py`, `tests/test_source_parent_anchor_validation.py`)
pass (25/25). No Stage 3 pipeline process was running at any point during this
investigation (`Get-CimInstance ... run_mapping_pipeline.py` returned nothing;
the only matching python.exe was the unrelated `supply_reconciliation_workflow.py`
in `leap_initialisation`).

Diagnostics for this stocktake (small scratch scripts and their text output,
not committed) live outside the repo, under the session scratchpad
(`.../scratchpad/analyze_anchor.py`, `analyze_failed.py`,
`anchor_breakdown.txt`, `failed_breakdown.txt`). They read but did not modify
`results/tree_structure/source_parent_anchor_validation.csv` and
`results/tree_structure/common_esto_validation_issue_patterns.csv`.

## 1. Current-state summary

Two Stage-3 checks matter, and they tell different stories:

- **Recursive Common-ESTO parent/child validator** (`common_esto_validation.csv`
  / `common_esto_validation_summary.csv`, the one fixed in `4042d5e`) is
  essentially healthy: ESTO flow-axis 582 checks / **1** mismatch, LEAP
  6,906 checks / **2** mismatches, NINTH 145,293 checks / **8** mismatches,
  product-axis fully passed/skipped. This confirms the memory note
  "Standalone rollup validation resolved" still holds — this check is not a
  current problem source.
- **Source-parent anchor validation** (`source_parent_anchor_validation.csv`,
  `..._summary.csv`, `codebase/mapping_tools/source_parent_anchor_validation.py`)
  is a much larger, separate check (~688k rows this run) that reconciles raw
  source parent totals directly against the Common-ESTO frontier. This is
  where essentially all headline "failure" volume lives:

  | axis/scope/system | eligible | passed | failed | skipped |
  |---|---|---|---|---|
  | flow / esto_leap_ninth / NINTH | 388,548 | 22,202 | 1,648 | 364,698 |
  | flow / esto_leap_ninth / ESTO | 2,223 | 875 | 1,348 | – |
  | product / esto_leap_ninth / NINTH | 28,035 | 24,187 | 3,848 | 185,673 |
  | product / esto_leap_ninth / ESTO | 2,673 | 2,214 | 459 | – |
  | flow / esto_leap_ninth / LEAP | 539 | 349 | 190 | – |

  The **skipped** bucket (364,698 + 185,673 ≈ 550k) is overwhelmingly
  `no_anchorable_common_esto_boundary` (≈304k flow + ≈146k product) and
  `no_observed_source_frontier` (≈60k + ≈39k). Per the pre-existing
  `docs/prompts/investigate_anchor_validation_methodology.md` diagnosis, these
  are validator-methodology artifacts, not evidence of 550k real problems —
  and the recent hierarchy-resolver commits (`00dffd5`, `125d367`, `d2d20d7`)
  were an attempt to shrink this bucket by resolving deeper source rows to
  their nearest mapped ancestor. **They only partly worked**: the genuine
  `failed` count is small (≈9.1k combined) relative to `skipped`, but the
  `skipped` bucket did not shrink to zero — deep rows such as passenger-road
  two-wheelers are still unanchorable (see §6).

## 2. Ranked table of the largest failure families

Ranked by `status == failed` row count in `source_parent_anchor_validation.csv`
(the genuine, non-skipped, non-artifact failures):

| Rank | axis | source | reason | parent_code | count | Root-cause category |
|---|---|---|---|---|---|---|
| 1 | product | NINTH | `parent_child_source_inconsistency` | `08_gas` | 1,220 | Common-ESTO graph/partition (aggregate fuel, see §4) |
| 2 | flow | ESTO | `parent_child_source_inconsistency` | `09 Total transformation sector` | 485 | Validator/frontier-definition (see below) |
| 3 | flow | NINTH | `parent_child_source_inconsistency` | `09_total_transformation_sector/09_06_gas_processing_plants` | 462 | Validator/frontier-definition |
| 4 | product | NINTH | `parent_child_source_inconsistency` | `16_others` | 549 | Common-ESTO graph/partition (aggregate fuel) |
| 5 | flow | NINTH | `parent_child_source_inconsistency` | `09_total_transformation_sector` | 333 | Validator/frontier-definition |
| 6 | flow | ESTO | `difference_exceeds_tolerance` | `16 Other sector` | 303 | Under investigation — needs one more residual pass |
| 7 | flow | ESTO | `frontier_rows_absent` | `14 Industry sector` | 302 | Rollup/partition — total not represented at Industry level |
| 8 | flow | ESTO | `difference_exceeds_tolerance` | `14 Industry sector` | 288 | Rollup/partition |
| 9 | product | NINTH | `parent_child_source_inconsistency` | `07_petroleum_products` | 283 | Common-ESTO graph/partition (aggregate fuel) |
| 10 | product | NINTH | `parent_child_source_inconsistency` | `15_solid_biomass` | 256 | Common-ESTO graph/partition (aggregate fuel) |
| 11 | product | NINTH | `difference_exceeds_tolerance` | `12_solar` | 252 | Mapping/rollup — solar allocated vs unallocated split |
| — | flow | LEAP | `parent_child_source_inconsistency` / `difference_exceeds_tolerance` | `Other loss and own use`, `CHP interim`, `Oil Refining` | 140 / 40 / 90 | Source-branch fallback scope mismatch (see §3) |

**Reading `parent_child_source_inconsistency` (the dominant reason among real
failures):** per the validator source (`source_parent_anchor_validation.py`
lines ~500–540), this fires when a parent's declared children are *fully
resolvable with zero missing nonzero evidence* (i.e. no unmapped nonzero leaf
is silently dropped) but the frontier sum still disagrees beyond tolerance.
That rules out "missing mapping" as the cause for these specific rows — the
mismatch is structural (wrong comparison level / wrong frontier), not a
coverage gap.

## 3. Same underlying problem appearing in several reports — the "09 Total transformation sector" cluster

`results/tree_structure/common_esto_validation_issue_patterns.csv` (a
diagnostic companion of the *recursive* validator, not the anchor validator)
independently explains why `09 Total transformation sector` keeps failing in
the anchor check: its children `09.06 Gas processing plants`,
`09.07 Oil refineries`, and `09.08 Coal transformation` are registered as
`NON_EXPANDING` / `DETACHED` rollups (diagnosis `replaced_by_non_expanding_rollup`,
`replaced_by_detached_rollup`). By design (`docs/rollup_rules_system.md`
§`NON_EXPANDING_ROLLUP`), these do **not** create additive graph edges to the
parent — their detailed component rows remain independently comparable
instead of rolling into the transformation total. The anchor validator's
"sum of resolved children" frontier check, however, still expects the parent
`09 Total transformation sector` to equal the sum of its *direct* declared
children, so it repeatedly reports the same magnitude of shortfall
(`abs_error` values recur almost exactly, e.g. **60,721.17** for
`05PRC`/2023 across multiple `09.0x` child rows and both `esto_leap` and
`esto_leap_ninth` scopes — the identical number appearing under different
`parent_code`/child combinations is itself the signature of one shared root
cause, not several independent bugs). The same signature recurs for
`14 Industry sector` vs `14.03 Manufacturing` and its NINTH sub-branches.

**Classification: validator/frontier-definition problem.** The anchor
validator is not yet non-expanding-rollup-aware at the "Total transformation" /
"Industry sector" level the way the recursive validator already is (per
`4042d5e`). This is very likely the single largest *fixable, systemic* driver
of the `parent_child_source_inconsistency` family for flow-axis ESTO/NINTH
(≈485+462+333+248+238 ≈ 1,766 of the 9.1k genuine failures, before counting
smaller `14.03 Manufacturing` sub-cases) — a generic fix, not a mapping fix.

A second, smaller recurring pattern: LEAP `CHP interim` (40 failures) and the
implied `Electricity interim` / `Heat plant interim` family are governed by
`config/source_branch_fallback_rules.csv` and `warn_and_zero_interim`
(`docs/rollup_rules_system.md` §Alternative/interim LEAP source branches). The
anchor validator appears to compare against **raw** parsed LEAP branch totals,
which still contain the un-zeroed interim values, while the Common-ESTO
frontier reflects the zeroed working data — a scope mismatch between what the
anchor validator reads and what the converter actually emits. Same root-cause
family as `Oil Refining` (LEAP, 90 failures, parent 0 vs frontier ‑14,138 for
`20USA` — looks like the same interim/standard branch duality, not a missing
mapping).

## 4. Aggregate fuel groups: nonzero coverage vs unanchorable structure

The four aggregate fuel groups the user's design preference explicitly warns
against detail-mapping — `07_petroleum_products`, `08_gas`,
`15_solid_biomass`, `16_others` — are **exactly** the top four NINTH
product-axis `parent_child_source_inconsistency` failures (1,220 / 549 / 283 /
256 = 2,308 of the 3,848 NINTH product failures, i.e. ~60%). This is strong
independent confirmation that the design preference is correctly targeted:
these are not missing-mapping gaps, they are places where the aggregate
parent's raw NINTH total and the resolved frontier disagree because of how
those categories partition across Common ESTO (their children live under
different, sometimes non-expanding, comparison rows — same mechanism as §3,
applied to the fuel/product axis instead of the flow axis).

By contrast, `12_solar` (252 `difference_exceeds_tolerance` failures) shows a
different, real signature: parent value and frontier sum are both nonzero but
in a fixed ~2:1 ratio across many economy/years (`-26,681.34` vs `-13,340.67`,
`-26,530.91` vs `-13,265.45`, …) — consistent with the known
`12_solar` / `12_solar_unallocated` → `Solar nonspecified` remap noted in
`AGENTS.md` (Baseline Seed Validation section). This looks like a genuine,
scoped allocation/rollup gap worth a small follow-up, not an aggregate-fuel
detail-mapping problem and not the same mechanism as §3/§4's aggregate-fuel
cluster.

`highly_recommended_mapping_candidates.csv` (Stage 2/3 output, 2026-07-22
15:20) currently contains **zero** rows — only the header. Under the existing
strict acceptance rule ("only complete, non-zero, high-confidence candidates…
belong…"), the system is correctly not proposing any mapping additions right
now. That is itself useful evidence: nothing in the current failure set is a
simple "add this workbook row" fix.

## 5. Internal consistency checks

- Recursive parent/child hierarchy: effectively consistent (§1) — 11
  mismatches total across 152,781 checks.
- `common_esto_rollup_validation_summary.csv`: most `NON_EXPANDING` rollup
  rules pass their available checks (e.g. `09.06.01 Gas works plants`: 364/364
  NINTH passed, 4/4 ESTO passed). `09.08 Coal transformation`
  (`DETACHED` mode) shows 5 failed ESTO checks (abs_error up to 1,056) and 2
  failed NINTH checks — small, real, worth a follow-up but far smaller than
  the transformation-sector cluster in §3. `16.03-16.04 Agriculture and
  fishing` shows `no_contributors_available = 11,851` for NINTH — a structural
  scope gap (Agriculture/Fishing likely not separately represented in NINTH),
  not a numeric error.
- `qa_common_esto_duplicate_components.csv` is 115 bytes (effectively empty) —
  no evidence of widespread duplicate-mapping or cardinality corruption in the
  current compiled structure.
- I did not find evidence in the sampled failure rows of exact mappings being
  silently superseded by fallback/resolver logic — the resolver
  (`resolve_nearest_mapped_pair`) is only invoked when a row has no direct
  hit, per the code path read in `source_parent_anchor_validation.py`.

## 6. Does the hierarchy resolver choose the nearest valid ancestor?

Tested with a passenger-road case as requested: **no, not yet, for the anchor
validator's boundary check.** Every one of 66,402 sampled rows involving
`15_02_01_passenger` sub-branches (e.g.
`15_transport_sector/15_02_road/15_02_01_passenger/15_02_01_01_two_wheeler`)
is still `skipped` / `no_anchorable_common_esto_boundary`, exactly matching
the handoff prompt's warning that "deep passenger-road rows still appeared as
`no_anchorable_common_esto_boundary`" even after the three resolver commits.
This confirms the resolver fix is **too narrow, not too broad** for this
family: it did not make passenger-road eligible at all (contrast with §4,
where the aggregate-fuel rows became newly *eligible but failing* — the
opposite failure mode). The transformation-sector case (§3) shows a related
but distinct failure mode: eligible and resolvable, but the frontier
definition itself doesn't yet respect non-expanding-rollup semantics. The
`14.03.02 Chemical (incl. petrochemical)` exact-mapping case in the issue
patterns file shows `present_in_final_output` status with small residual
error (max abs_error 870.98, likely rounding/units) — i.e. the exact detailed
mapping is not being overridden by fallback logic, consistent with the user's
"preserve exact detailed mappings" requirement.

## 7. Ordered backlog (fix-first, lowest risk)

1. **Make `source_parent_anchor_validation.py`'s frontier resolution
   non-expanding/detached-rollup aware**, reusing the same
   `rollup_mode` / `NON_EXPANDING_ROLLUP` / `DETACHED` knowledge the recursive
   validator and `non_expanding_rollups.py` already have, instead of assuming
   every declared child is an additive graph edge. This is a generic system
   fix (no workbook changes), targets the single largest coherent failure
   cluster (§3, ~1,766+ of 9.1k genuine failures, plus a meaningful share of
   §4's aggregate-fuel product failures which share the same mechanism on the
   other axis), and has essentially no risk to the already-healthy recursive
   validator (`4042d5e`) or to real data, since it only changes what the
   *anchor validator* expects to sum, not any value in the pipeline. Lowest
   risk, highest yield — do this first.
2. Re-diagnose the passenger-road / deep-transport `no_anchorable_common_esto_boundary`
   skip bucket specifically (§6) as its own follow-on: confirm whether the
   nearest-mapped-ancestor resolver used in `source_parent_anchor_validation.py`
   is actually being invoked for these paths, or whether a hierarchy build
   step (tree depth, alias canonicalisation) is excluding them before the
   resolver ever runs.
3. Investigate the LEAP interim-branch scope mismatch (`CHP interim`,
   `Oil Refining`, §3) — confirm whether the anchor validator should read the
   zeroed working data (post `source_branch_preflight`) instead of raw parsed
   LEAP, so interim/standard duality doesn't manufacture false failures.
4. Small, scoped follow-up on `12_solar` (§4) — likely a genuine
   allocated/unallocated rollup gap, not an aggregate-fuel detail-mapping
   case; needs its own before/after evidence, separate from items 1–3.
5. Only after 1–3 are resolved, re-run the full failure-family ranking to see
   what residue (if any) is left that would justify actual workbook mapping
   additions — do not add mapping rows before this, since the evidence here
   shows essentially no current family is a "missing mapping" problem.

## Uncertainty and what would resolve it

- The `flow`/ESTO `difference_exceeds_tolerance` / `16 Other sector` family
  (303 failures, rank 6) was not decomposed to a specific mechanism in this
  pass — resolving it needs the same one-parent/one-economy/one-year residual
  trace the `investigate_anchor_validation_methodology.md` prompt describes,
  applied specifically to `16 Other sector`.
- I have not verified from source code whether the anchor validator can
  cheaply consume the existing `rollup_mode` column already used elsewhere
  (`build_common_esto_structure.py`, `non_expanding_rollups.py`) or whether a
  small refactor is needed to expose it at the point the frontier is built in
  `source_parent_anchor_validation.py` (~line 355 onward, `frontier_cache`
  construction). That would need to be scoped before starting item 1.
- I have not re-run Stage 3 to see the effect of any fix — by instruction,
  this stocktake stops before implementation.

## Test plan for the recommended fix (item 1)

- Add a focused unit test in `tests/test_source_parent_anchor_validation.py`
  covering a synthetic parent with one `NON_EXPANDING` child and one ordinary
  child, asserting the frontier includes the non-expanding child's summed
  contribution without treating it as a missing/absent child.
- Re-run `pytest -q tests/test_structural_resolver.py
  tests/test_source_parent_anchor_validation.py` before touching Stage 3.
- Re-run `codebase/run_mapping_pipeline.py --stages 1,2,3` in the background
  (per repo convention, ~24 min for Stage 3), then diff
  `source_parent_anchor_validation_summary.csv` before/after: expect the
  `parent_child_source_inconsistency` count for `09 Total transformation
  sector` / `14 Industry sector` and their aggregate-fuel product-axis
  counterparts to drop sharply, `passed`/`skipped` counts to shift
  accordingly, and the recursive `common_esto_validation_summary.csv` mismatch
  counts to stay at 1/2/8 (unchanged) — a regression there would mean the fix
  leaked into the wrong validator.
- Confirm conservation: total nonzero source values reaching Common ESTO
  should be unchanged (this is a read-only reclassification of how the
  *anchor check* interprets already-correct pipeline output, not a change to
  any emitted value).

## Confirmation

`git status --short` at the end of this session shows only the pre-existing
user-owned changes noted at task start
(`config/outlook_mappings_master.xlsx` modified;
`config/176BC200`, the `outlook_mappings_master new*.xlsx` variants and their
`~$` lock files, `docs/REPO_CLEANUP_AND_NAVIGATION_NOTES.md` untracked) plus
this new findings file. No workbook, code, or `results/` file was modified by
this investigation.
