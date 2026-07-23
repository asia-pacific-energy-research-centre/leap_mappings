# Anchor validator fix session — findings and handoff (2026-07-23)

This continues `docs/prompts/anchor_validator_fixes_findings_20260722.md` (the
prior session's tree-builder fixes) into a second implementation session
focused on `codebase/mapping_tools/source_parent_anchor_validation.py`. Seven
commits landed this session, all on branch `claude/anchor-validator-fixes-ee04bc`,
all pushed to the worktree's local history (not yet merged/pushed further —
check with the user before doing so):

```
97af252 codex: add regression test confirming the source-internal check is dataset-agnostic
1c17af8 codex: flag frontier leaves with self-contradictory source data distinctly
9b75628 codex: raw ESTO tree ignores esto_rollup_rules entirely, not just EXPANDING rows
97e20f5 codex: extend raw fallback to registered-but-dataless frontier components
3fdf592 codex: fall back to raw source value when a frontier component is unregistered
bcb7caf codex: stop EXPANDING rollups from orphaning raw ESTO branches
e23768f codex: fix anchor validator double-counting and frontier-descent bugs   <- end of prior session
```

Read each commit message in full (`git show <hash>`) before touching the
related code — they contain the precise real-data traces, not just summaries.
This note focuses on: (1) the corrected current failure baseline (a real
methodology bug was found and fixed **in how this session verified its own
work**, not in the validator itself — read this first), (2) what's fixed vs.
still open, and (3) concrete next steps.

## Read this first: the verification methodology bug

Every real-data number in this note and in commits `bcb7caf` through `1c17af8`
was produced by a **standalone repro script** (not `run_mapping_pipeline.py`)
that called `validate_source_parent_anchors` directly. That script never
loaded `config/mapping_issue_exception_sets.xlsx`'s `unmodelled_source_ignored`
sheet and never passed `unmodelled_source_codes=` — an exclusion the real
pipeline (`run_mapping_pipeline.py`) always applies. That sheet already
excludes ESTO/9th sector codes `06` (stock changes), `11` (statistical
discrepancy), `18` (electricity output in GWh — a physical power-output
indicator, not an energy balance), `19` (heat output in PJ, same reason), and
fuel codes `19`/`20`/`21` (aggregate fuel columns).

**Practical effect:** every failure count reported in this session's commit
messages before the fix below is inflated by ~200 rows worth of `18`/`19`
sector noise that the real pipeline never even shows a user. The *relative*
before/after deltas within each commit are still valid (both sides of each
A/B comparison omitted the same exclusion consistently), but the **absolute**
numbers are not comparable to the original stocktake's numbers, and a
candidate-mapping-gap CSV built from the inflated data (sent to the user, then
retracted) was entirely spurious — regenerating it against the corrected
baseline found zero remaining candidates.

**The corrected baseline** (same restricted repro — ESTO+NINTH only, no LEAP,
year slice `{esto_base_year, 2030}`, all economies — but now with
`unmodelled_source_codes=load_unmodelled_source_codes()` properly passed):

```
status
skipped    258436
passed      56162
failed       1262
```

929 of the 1,262 failures are `source_system == "NINTH"`, 333 are `"ESTO"`.

**Before doing anything else in the next session:** confirm whatever repro
script you write also loads and passes `unmodelled_source_codes`. The
reference invocation (verified working) is:

```python
from codebase.mapping_issue_exceptions import load_unmodelled_source_codes
unmodelled_source_codes = load_unmodelled_source_codes()
# ... pass unmodelled_source_codes=unmodelled_source_codes to validate_source_parent_anchors
```

Also load `anchor_exclude_parents` (NON_EXPANDING/DETACHED rollup labels +
LEAP interim branches) exactly as `run_mapping_pipeline.py` does — both this
and `unmodelled_source_codes` are required for a repro to be representative;
see `verify_09_fix.py`-style scripts referenced below for the full recipe.

## What's fixed this session (verified against the corrected baseline)

Starting point for this session (prior session's end state,
`e23768f`, measured **without** the `unmodelled_source_codes` bug — i.e. not
directly comparable to the corrected 1,262 above, but internally consistent
across this session's own progression):

| Step | Whole dataset (ESTO+NINTH, same repro, inflated numbers before the methodology fix) |
|---|---|
| Session start | 4,623 failed / 23,819 passed |
| `bcb7caf` (EXPANDING rollup tree fix) | unchanged for `09` (wrong target, real bug, kept) |
| `3fdf592` (raw fallback: unregistered) | 4,195 failed / 38,759 passed |
| `97e20f5` (raw fallback: registered-but-dataless) | 2,293 failed / 58,452 passed |
| `9b75628` (tree fix, all rollup modes) | 2,023 failed / 60,747 passed |
| `1c17af8` (source-internal-inconsistency flagging) | 1,456 failed / 60,200 passed |
| **Corrected baseline** (`unmodelled_source_codes` bug fixed) | **1,262 failed** / 56,162 passed / 258,436 skipped |

1. **`bcb7caf`** — `build_esto_tree` stopped splicing `EXPANDING`-mode
   `esto_rollup_rules` labels (e.g. `09.01-09.02 Power sector`) into the raw
   ESTO tree, which had been reparenting real leaves away from their natural
   branch (`09.01 Main activity producer`/`09.02 Autoproducers` went
   structurally childless). Verified via real-data A/B that this did **not**
   move `09 Total transformation sector`'s failures at all — the doc's own
   documented contingency triggered; kept anyway as a real, independently
   justified fix (`docs/prompts/anchor_validator_fixes_findings_20260722.md`'s
   follow-on section has the full trace).

2. **`3fdf592`** — `frontier_sum` previously could only get a value for a
   resolved frontier component by joining it to a `common_row_id` in
   `common_esto_rows.csv`. A component the validator correctly resolved but
   Common ESTO structure building never registered at all (e.g. ESTO's own
   `09.01 Main activity producer`, which NINTH/LEAP can only report merged
   into `09.01-09.02 Power sector`) silently contributed nothing. Added a raw
   fallback: use the source system's own raw reported value for the exact
   pair instead, gated on at least one sibling of the same parent/product
   already having a genuine common-row match (so a parent with **zero**
   registered components still correctly stays
   `no_anchorable_common_esto_boundary`, not a guess — two existing tests pin
   this).

3. **`97e20f5`** — extended the same fallback to a second shape: a component
   that **is** registered (has a `common_row_id`) but this source system's own
   comparison-data export has zero rows for it in every economy/year (e.g.
   ESTO's `16.01 Biogas` — NINTH's export has a value for the shared common
   row, ESTO's own export just never wrote one). Reused the already-computed
   `has_data_pairs`/`ids_with_data` signal to widen the trigger.

4. **`9b75628`** — generalized `bcb7caf` from EXPANDING-only to **all**
   `esto_rollup_rules` modes. Proved via real data that `10.01 Own Use`'s own
   raw total is *exactly* the sum of all its original raw-tree children,
   including five reattributed to flow `09` for NON_EXPANDING comparison
   purposes (`10.01.02 Gas works plants`, `10.01.03
   Liquefaction/regasification plants`, `10.01.05 Coke ovens`, `10.01.07
   Blast furnaces`, `10.01.11 Oil refineries`) — the reattribution is a
   comparison-boundary relabel, not a redefinition of `10.01 Own Use`'s own
   total, so splicing it into the raw tree was orphaning it exactly like the
   EXPANDING case orphaned `09.01`/`09.02`. `build_esto_tree` no longer takes
   a `workbook_path` at all (it never needs `esto_rollup_rules`); removed the
   now-dead `_non_expanding_rollup_hierarchy` helper and its test. Small,
   understood, accepted regression: 9 rows in `09 Total transformation
   sector` newly exposed a genuine pre-existing gap in raw ESTO's own
   `09.06.02.01/02` sub-flow data for a few China coal products (previously
   silently bypassed via the synthetic detour); net effect strongly positive.

5. **`1c17af8`** — added `_build_source_internal_bad_pairs`: a **pure
   self-consistency check on one source system's own raw file**, no ESTO
   mapping or Common ESTO structure involved. Checks whether an OTHER-axis
   node's own reported value matches the sum of its own other-axis children,
   for a fixed validation-axis code. Traced concretely: NINTH's own
   `09_06_gas_processing_plants` sector declares its own `08_02_lng` subfuel
   as `0`, while its own more granular `09_06_02_liquefaction_regasification_
   plants` sub-sector reports the real `+4218.81` for the exact same subfuel
   — the same physical quantity, reported two different ways at two depths of
   NINTH's own tree. No tree or mapping change in this repo can fix a source
   file disagreeing with itself, so a resolved frontier leaf touching such a
   pair now gets `reason = "source_internal_recursive_sum_inconsistency"`,
   `status = "skipped"`, instead of an ordinary `"failed"`.

   **Deliberately narrow scope, found the hard way:** an earlier version of
   this also checked a row's own `(parent_code, other_axis_value)` pair
   directly, and also tried a symmetric "check both axes' own children"
   version. Both broke 4 existing tests — they re-derive the exact same
   computation the main parent-vs-frontier check already does, so they
   swallow *genuine, single-sided* errors in a parent's own declared value as
   if they were unknowable source contradictions (see
   `test_leaf_remap_onto_ancestor_with_own_row_still_fails_on_real_mismatch`,
   which exists specifically to catch this). The shipped version only
   distrusts **frontier LEAF components** via a genuinely separate tree (the
   OTHER axis), never the row's own pair. **Known, accepted gap:** the
   "mirror" row on the opposite axis (e.g. flow-axis
   `09_06_gas_processing_plants`/`08_02_lng` itself, ~152 rows in the
   corrected baseline) is not caught by this same-iteration check and stays
   `"failed"`. Every attempt to close this gap via cross-axis referencing
   collapsed into the same circularity — see "What's still open" below before
   trying again.

6. **`97af252`** — added a regression test proving the mechanism has zero
   ESTO/NINTH/LEAP-specific code (built entirely from
   `axis_col`/`other_col`/`children`/`other_children`, all already computed
   generically per `source_system`) by rerunning the exact same scenario
   under a fictional `"IEA"` source system using the default flow/product
   axis convention. Confirms it applies to any Nth dataset added to this
   system, per the user's explicit ask.

Full targeted suite (`tests/test_source_parent_anchor_validation.py
tests/test_structural_resolver.py tests/test_build_dataset_tree_structure.py
tests/test_non_expanding_rollups.py tests/test_build_energy_balance_
relationships.py`): **110 passed** as of `97af252`. Full repo suite: 242
passed, 2 pre-existing unrelated failures (missing `pyarrow`, an Excel-lock-
file test — both present before this session too, confirmed via `git stash`).

## What's still open

Ordered roughly by how well-understood each is (best-understood first):

1. **The mirror-row gap (~152 rows, `09_06_gas_processing_plants`/NINTH flow
   axis, plus the structurally identical "row's own pair" variant across
   `15_solid_biomass`/`16_others`/`08_gas`/`14_industry_sector`, ~603-825 rows
   total).** **Attempted a fix in a third follow-on session (still
   2026-07-23): a real, working mechanism was built and verified on real
   data, but it turned out to have zero effect on any of these rows and to
   introduce a new false-positive side effect. Reverted; this remains open,
   now with a concrete negative result on record instead of an untested
   hypothesis.** See "The mirror-row gap: attempted fix and why it was
   reverted" below for the full trace — this consolidates the old items 1,
   3, and 4, which all turned out to be the same underlying question with
   the same answer.

2. **`10.01 Own Use` / `10 Losses & own use` residual (160 rows, ESTO-side,
   `esto_leap_ninth` scope).** **Traced in the follow-on session (still
   2026-07-23); root cause found, but the fix does not belong in this file.**

   Traced concretely: economy `01AUS`, year 2023, parent `10.01 Own Use`. The
   shared-frontier-group mechanism (`docs/prompts/anchor_validator_fixes_
   findings_20260722.md` fix 6, "Oil Refining shared-frontier grouping") *is*
   firing correctly — it groups `other_axis_value`s whose registered
   `common_row_id` set is identical. The actual problem is upstream, in
   `results/common_esto/common_esto_rows.csv` (built by Stage 2's graph
   partitioning): ESTO reports 7 individual raw coal by-products under
   `10.01 Own Use` (`02.01 Coke oven coke`, `02.03 Coke oven gas`, `02.04
   Blast furnace gas`, `02.05 Other recovered gases`, `02.06 Patent fuel`,
   `02.07 Coal tar`, `02.08 BKB/PB`), and Common ESTO structure rolls them
   into one combined `"02.01,02.03-02.08 Coal products"` row **per flow
   child** (`10.01.01`, `.02`, `.05`, `.06`, `.07`, `.11`) — but which of the
   7 products each flow child registers to that combined row is not uniform:

   | flow child | products it registers |
   |---|---|
   | `10.01.01 Electricity, CHP and heat plants` | 02.01, 02.03, 02.07 |
   | `10.01.02 Gas works plants` | 02.03, 02.05 |
   | `10.01.05/06/07` (coke ovens / coal mines / blast furnaces) | all 7 |
   | `10.01.11 Oil refineries` | 02.01 only (as an exact row, not a rollup) |

   That asymmetry splits what "should" be one shared group into four
   distinct signatures: `{02.01, 02.07}`, `{02.03}` alone, `{02.04, 02.06,
   02.08}`, `{02.05}` alone. For `01AUS`/2023, only two flow children
   (`10.01.05`: `-15.810278`, `10.01.07`: `-16.192993`, summing to
   `-32.003271`) have any real ESTO comparison data at all (confirmed via
   `results/common_esto/common_esto_comparison_data.csv`, filtered to
   `source_system == "ESTO"`, `comparison_scope == "esto_leap_ninth"`) — so
   all four signature-groups end up comparing against that same `-32.003271`
   total regardless of which product they check. This is a coincidence of
   arithmetic (two flow children's real data summing to a number every group
   gets compared against), not a value-fetching bug: raw ESTO's own `10.01
   Own Use / 02.01 Coke oven coke` genuinely is `0`, exactly as reported.
   Confirmed the same shape (this coal-by-product family, plus a parallel
   `07.12-07.17` petroleum-by-product family) accounts for effectively all
   160 rows across ~14 economies — only 9-11 distinct `(parent_code,
   other_axis_value)` combinations drive the whole residual, not 160
   independent cases.

   **Fixed in the follow-on session (still 2026-07-23), after the user
   confirmed the asymmetric per-flow-child registration itself is
   intentional and physically correct** (different flow children genuinely
   can't produce every coal by-product, so it's correct that they don't all
   register the same product set) **— the bug was entirely in the
   validator's grouping rule, not in `common_esto_rows.csv`.**
   `validate_source_parent_anchors`'s "Shared-frontier group combination"
   block (`docs/prompts/anchor_validator_fixes_findings_20260722.md` fix 6,
   "Oil Refining shared-frontier grouping") grouped `other_axis_value`s only
   when their registered `common_row_id` signature was **exactly identical**.
   Under the confirmed-intentional asymmetric registration, semantically
   related products end up with *overlapping but not identical* signatures
   (e.g. `02.01`/`02.07` share `{a75b, afdd, 09653c, be35}` and DID group
   under the old rule; `02.03` adds an extra id and `02.05`/`02.04`/`02.06`/
   `02.08` are missing one, so they did NOT group, even though every one of
   these signatures shares `afdd`/`09653c`/`be35` — the three coke-ovens/
   coal-mines/blast-furnaces flow children that register all 7 products).
   The exact-equality rule split what should have been one shared group into
   up to four partial groups, each compared against whichever partial subset
   of flow children happened to have real data — a coincidence of
   arithmetic, not a real reconciliation.

   **The fix:** changed grouping from "identical signature" to **connected
   components over overlapping signatures** (union-find keyed by shared
   `common_row_id`, transitively) — implemented in the same "Shared-frontier
   group combination" block. The exact-equality case is subsumed as the
   special case where every signature in a component happens to be
   identical, so it required no separate code path. The important follow-on
   correctness issue (flagged in advance and verified explicit before
   writing the reconciliation): reusing one member's own `frontier_sum` (safe
   under exact-equality, since every member's frontier_sum already came from
   the identical id set) is WRONG under connected components, since members'
   registered id sets are now genuine subsets of the union — summing each
   member's own frontier_sum would double-count shared ids. The combined
   group's `frontier_sum`/`frontier_positive_sum`/`frontier_negative_sum`/
   `frontier_row_count` (and, orthogonally, any raw-fallback contribution
   from unregistered/dataless members of the same component) are now
   recomputed from the **union of every `common_row_id` touched by any
   member, each counted exactly once**, applied to the primary row via an
   explicit `(group_id, economy, scenario, year)` lookup map rather than
   `pd.merge` (a merge would silently reset `base`'s index, which the
   surrounding boolean masks depend on). `parent_value`/`parent_positive_
   value`/`parent_negative_value` combination across the whole connected
   component reuses the existing `combine_cols`/`groupby(...).transform("sum")`
   logic unchanged — that part was already correct in shape.

   **Verified with a real-data A/B** (restricted repro: ESTO+NINTH, year
   slice `{esto_base_year, 2030}`, all economies, `unmodelled_source_codes`
   and `exclude_parents` both applied — see "Reusable tooling" below):

   | | failed | passed | skipped |
   |---|---|---|---|
   | Before (git-stashed, exact-equality grouping) | 1,262 | 56,162 | 258,436 |
   | After (connected-components grouping) | **760** | 55,636 | 259,464 |

   All 160 of the `10.01 Own Use`/`10 Losses & own use` ESTO-side residual
   rows resolved (0 remaining failures for those two parents, confirmed by
   direct filter on the after-fix detail table) — concretely, `01AUS`/2023's
   `10.01 Own Use` coal-by-products family now collapses into ONE combined
   row (`other_axis_value` = all seven `02.0x` labels joined with `" + "`,
   `parent_value == frontier_sum == -32.003271`, status `passed`) instead of
   three separate `failed` rows plus partial skips. The parallel `07.12`-
   `07.17` petroleum-by-products family under the same parent resolved the
   same way (`07.12 White spirit SBP + 07.13 Lubricants + 07.14 Bitumen +
   07.16 Petroleum coke + 07.17 Other products`, now `passed`).

   **The fix's real-data impact is much larger than just this one family**:
   total failures across the whole dataset dropped by 502 (1,262 → 760), not
   ~160 — grouping by `parent_code`/`comparison_scope`/`source_system`
   showed reductions concentrated in `09 Total transformation sector` (ESTO,
   -56), `14 Industry sector`/`14.03 Manufacturing` (ESTO, -51/-39) and their
   NINTH-side equivalents `14_industry_sector`/`14_03_manufacturing` (NINTH,
   -69/-63), and `16 Other sector`/`16_other_sector` (ESTO/NINTH, -23/-33) —
   i.e. the same asymmetric-registration shape recurs across several other
   flow/sector families that share the "some flow children register a
   partial by-product subset, others register the whole family" structure.
   **No `(parent_code, comparison_scope, source_system)` combination gained
   any new failures** (confirmed by diffing failed-row counts grouped on
   those three keys between the before/after detail tables — every nonzero
   delta was a reduction). `passed` dropped slightly (56,162 → 55,636,
   -526): expected and correct — some `other_axis_value` members that used
   to be evaluated independently (and happened to pass by coincidence
   against a partial frontier sum) are now folded into their group's primary
   row and marked `skipped`/`grouped_with_shared_frontier_sibling` instead,
   since they are no longer independent numeric findings.

   **Known remaining gap: none found in this family.** Every row checked in
   the `10.01`/`10`/`07.12-07.17` shape reconciled after correct grouping;
   this session did not find a case where connected-components grouping
   produced a genuine, still-failing numeric mismatch, though the fix's
   design explicitly allows for that outcome (a real mismatch after correct
   grouping is a valid result, not something to force-pass). The broader
   `14_industry_sector` residual (item 4 below) and NINTH-side items 1/3 are
   unrelated shapes and remain open as documented below.

   Regression coverage: `tests/test_source_parent_anchor_validation.py` gained
   `test_overlapping_but_not_identical_signatures_group_via_connected_components`,
   which mirrors this exact real-data shape (three `other_axis_value`s with
   pairwise-overlapping-but-not-identical signatures) and pins both that they
   now collapse into one group AND that the recomputed `frontier_sum` is the
   deduplicated union (not a double-counted or partial sum). The existing
   `test_shared_frontier_group_is_combined_not_individually_failed` and
   `test_distinct_frontier_scope_is_unaffected_by_shared_scope_grouping`
   (the Oil Refining exact-equality case from `docs/prompts/anchor_validator_
   fixes_findings_20260722.md` fix 6) still pass unchanged, confirming
   connected components subsumes exact-equality grouping without regressing
   it. Full targeted suite (`tests/test_source_parent_anchor_validation.py
   tests/test_structural_resolver.py tests/test_build_dataset_tree_structure.py
   tests/test_non_expanding_rollups.py tests/test_build_energy_balance_
   relationships.py`): **111 passed** (110 baseline + 1 new test), confirmed
   both before and after the fix (before: 110 passed + 1 new test failing as
   expected against the old grouping rule; after: 111 passed).

3. **The mirror-row gap: attempted fix and why it was reverted (consolidates
   the old items 1, 3, and 4 above — same underlying question, same
   answer).** A fourth follow-on session (still 2026-07-23) picked up the
   user's explicit direction: "extend the skip to catch the row's own pair
   too," on condition of finding a way to tell a genuine mirror-row apart
   from the genuine single-sided error `test_leaf_remap_onto_ancestor_
   with_own_row_still_fails_on_real_mismatch` protects.

   **The candidate signal tried:** walk the OTHER-axis tree *past* the
   immediate children `_build_source_internal_bad_pairs` already checks, to
   grandchildren and deeper. Hypothesis: in a genuine mirror-row, the true
   value hasn't vanished, it's just reported at a level deeper than the
   immediate children — so some deep descendant should still show real,
   nonzero evidence for the same validation-axis code. In the protected
   single-sided-error fixture (`_duplicated_rollup_value_fixture`'s "Plants"/
   "Solar" case), "Solar" is a *leaf* with no children of its own, so there
   is no level below the immediate children to search — the signal correctly
   stays silent there, and all 111 existing tests (including the four
   `test_leaf_remap_onto_ancestor_with_own_...` tests) kept passing with this
   change in place. Implemented as two new pure functions,
   `_build_deep_other_descendants` (other-axis node -> descendants strictly
   below its immediate children, memoized DFS) and
   `_build_deep_descendant_evidence` (finds real nonzero raw evidence at
   those deeper nodes for the same validation-axis code), gating a new
   row's-own-pair check that only fires when `_build_source_internal_
   bad_pairs` already flags the row's own `(parent_code, other_axis_value)`
   pair as bad *and* deep evidence corroborates it.

   **Passing the unit-test suite was not enough — real-data A/B is what
   falsified the hypothesis.** Rebuilt the restricted repro from scratch,
   confirmed it reproduced the current baseline exactly
   (`760 failed / 55,636 passed / 259,464 skipped`) with the item-2 fix alone
   before trusting anything from it, then re-ran with the new mechanism
   added on top:

   | | failed | passed | skipped |
   |---|---|---|---|
   | Before (item-2 fix only) | 760 | 55,636 | 259,464 |
   | After (+ deep-descendant-evidence row's-own-pair check) | **760** | 55,624 | 259,476 |

   **Zero of the 760 failing rows were reclassified.** Every one of the 12
   rows that changed status moved `passed` -> `skipped`; none moved out of
   `failed`. Traced both directions concretely:

   - **The signal under-fires on the actual target case.** Direct query of
     `data/merged_file_energy_ALL_20251106.csv` for the exact `01AUS`/
     `16_others`/`09_total_transformation_sector/09_01_electricity_plants`
     row item 3 was built around (still `failed`,
     `parent_child_source_inconsistency`, `parent_value == -12.37876`,
     `frontier_sum == 0.0` in both before and after) shows the true value
     genuinely has no deeper representation *anywhere* in the sector's own
     subtree: every one of its 30 sub-sector/sub-sub-sector/sub-sub-sub-
     sector descendant rows, at every depth down to the leaf, reports
     exactly `0` for fuel `16_others`. The `-12.37876` figure exists only at
     the `09_01_electricity_plants` level itself — the doc's original
     "reported at the wrong depth" theory does not hold for this row once
     checked directly; if it is a mirror-row at all, the true value would
     have to live in a completely different, non-descendant part of NINTH's
     tree, which a same-subtree deep search cannot find by construction.
   - **The signal over-fires on rows that were already correct.** The 12
     `passed` -> `skipped` rows (`08_gas`/`15_transport_sector`, NINTH,
     3 economies x 2 years x 2 scenarios) were already reconciling exactly
     (`parent_value == frontier_sum == 18.879735` for `01AUS`/reference/2023,
     confirmed unchanged in both runs) — a real, correct pass. Direct query
     of the raw file shows why the *unrelated* self-consistency check still
     fired: `15_transport_sector`'s own total for fuel `08_gas`
     (`18.879735`) does not equal the sum of its own immediate sector
     children (`15_01`...`15_06`, summing to only `1.773`), because NINTH's
     transport sector has many more nonzero cells scattered across deeper
     sub-sub-sector rows than its own immediate-child rollups capture (e.g.
     `15_02_road/15_02_02_freight/15_02_02_02_light_commercial_vehicle/..._
     compressed_natual_gas == 0.714903`) — a real, ordinary hierarchical
     rollup gap in the OTHER axis, unrelated to whether the *validated*
     parent/frontier comparison is trustworthy. Since some such deep cell is
     always nonzero for a sufficiently large real sector subtree, "does any
     deep descendant have a nonzero value" was not actually correlated with
     "is the mismatch a mirror-row" — it fired on this already-passing row
     for reasons that have nothing to do with the row being validated.

   **Conclusion: reverted, not shipped.** The deep-descendant-evidence
   signal does not reliably distinguish a genuine mirror-row from a genuine
   single-sided error — it manages to both miss the real target cases (no
   deeper evidence found in the one case checked directly) and produce new
   false positives on unrelated, already-correct rows, while leaving all
   ~760 real failures (including every row in items 1/3/4's original
   `09_06_gas_processing_plants`/`15_solid_biomass`/`16_others`/`08_gas`/
   `14_industry_sector` families) completely unchanged. This matches the
   task's own warning almost exactly: a change that passes the unit-test
   suite by construction (since the one adversarial fixture happens to use a
   leaf child) but produces no real benefit and one confirmed regression
   class on real data is not a safe fix to ship. `codebase/mapping_tools/
   source_parent_anchor_validation.py` and `tests/test_source_parent_anchor_
   validation.py` are both back to their pre-session state (the item-2
   connected-components fix only); nothing from this attempt was kept.
   Full targeted suite re-confirmed at **111 passed** after the revert, and
   the real-data repro re-confirmed the exact `760 / 55,636 / 259,464`
   baseline with the revert in place.

   **What this rules out, and what's left to try.** It rules out "walk
   further down the SAME other-axis node's own subtree" as a general
   distinguishing signal — that specific search space is either empty (the
   `16_others` case) or noisy (the `08_gas`/`15_transport_sector` case) on
   real data, not just in principle. It does NOT rule out every possible
   distinguishing signal — e.g. a signal that also requires the deep
   evidence to itself reconcile numerically against the frontier (not just
   be nonzero) might avoid the `08_gas`/`15_transport_sector` false positive,
   but would still need to somehow locate `16_others`' missing `-12.37876`
   somewhere else in NINTH's tree (a genuinely different search, e.g. across
   sibling sectors rather than descendants) to catch the case items 1/3/4
   were originally built around — and per `1c17af8`'s own commit message,
   every cross-axis/cross-branch variant tried in earlier sessions collapsed
   into the same circularity the shipped, narrow, frontier-leaf-only version
   avoids. If revisited, the right framing may genuinely be the one
   `1c17af8`'s commit message already flagged as the likely real answer:
   "trust the more granular raw data and substitute it as the corrected
   value" is a fundamentally different (and bigger) design decision than
   "detect and skip," and needs explicit user sign-off before attempting —
   detection alone, in every form tried across four sessions now, has not
   produced a safe result.

4. **8 "ambiguous" candidate mapping pairs** surfaced (then retracted along
   with the other 29) by the missing-mapping-gap detector script referenced
   below — these had real NINTH evidence but the sector or fuel maps to more
   than one `esto_flow`/`esto_product` elsewhere in `ninth_pairs_to_esto_
   pairs`, so the detector correctly declined to guess. If the mapping-gap
   angle is revisited, rerun the detector against a **freshly regenerated**
   correct-baseline result set (see caveat below) and hand the 8 ambiguous
   ones to a human for judgment; do not auto-resolve them.

## Reusable tooling from this session (not committed — scratchpad only)

Two scripts were built and iterated on in the scratchpad directory
(session-specific, not on disk in this worktree/repo). If the next session
wants them, rewrite from scratch using this recipe rather than assuming they
still exist:

- **A restricted real-data repro** (`verify_09_fix.py`-equivalent): builds
  all four trees, calls `load_raw_source_anchor_inputs` (ESTO + NINTH, no
  LEAP — `raw_leap_path=None` for speed since LEAP data wasn't the focus this
  session), restricts `years_by_system` to `{esto_base_year, 2030}` per
  system (mirrors `run_mapping_pipeline.py`'s own year-slicing rationale),
  and calls `validate_source_parent_anchors` with **all three** of
  `exclude_parents` (NON_EXPANDING/DETACHED + LEAP interim branches),
  `unmodelled_source_codes` (see the methodology bug above — do not skip
  this), and the real `common_esto_rows.csv`/`common_esto_comparison_data.csv`
  from `results/common_esto/`. Runtime: ~10-15s per call once CSVs are
  cached by the OS, dominated by NINTH's `source_flow`/`source_product`
  resolution. Use this — not the full pipeline, which needs a sibling
  `leap_initialisation` repo checkout this worktree doesn't have — for any
  further real-data verification.

- **A missing-mapping-gap detector**: parses `missing_expected_children` out
  of failed NINTH rows (careful: these are slash-joined full tree paths —
  take the **last segment** for the raw sector/fuel code, a bug that
  produced a false "zero evidence" result the first time this session wrote
  it), cross-references against raw NINTH data for real (nonzero) evidence,
  checks the candidate pair isn't already in `ninth_pairs_to_esto_pairs`,
  and only proposes a row when the inferred `esto_flow` (from how the same
  `ninth_sector` maps elsewhere) and `esto_product` (from how the same
  `ninth_fuel` maps elsewhere) are each unambiguous. **Must be rerun against
  a corrected-baseline result set** (with `unmodelled_source_codes` applied)
  before trusting its output — the first run, against inflated data, found
  29 rows that turned out to be entirely spurious once corrected data showed
  0.

## Test plan for the next session

1. Read this note and the referenced commit messages in full before touching
   anything.
2. Build a repro following the "Reusable tooling" recipe above — confirm it
   reproduces the corrected baseline (1,262 failed / 56,162 passed / 258,436
   skipped) exactly before trusting any further number from it.
3. Pick one item from "What's still open," starting with `10.01 Own Use`
   (best-scoped, most similar in shape to fixes already made this session) —
   trace one concrete row end to end (raw ESTO values, tree structure,
   Common ESTO row/comparison-data values, frontier resolution) before
   writing any code, exactly as every fix this session did.
4. After any fix, verify with an explicit before/after A/B on the *corrected*
   baseline (git stash the change, rerun, compare; pop the stash back) —
   never trust "tests pass" alone, and never trust a number from a repro that
   hasn't been checked against the methodology bug above.
5. Run `pytest -q tests/test_source_parent_anchor_validation.py
   tests/test_structural_resolver.py tests/test_build_dataset_tree_structure.py
   tests/test_non_expanding_rollups.py
   tests/test_build_energy_balance_relationships.py` (110 passing baseline)
   before and after every change.
