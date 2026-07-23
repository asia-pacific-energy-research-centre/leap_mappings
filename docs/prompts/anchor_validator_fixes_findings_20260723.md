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
   axis and structurally identical cases elsewhere).** Well-diagnosed, proven
   *not* safely fixable via same-session cross-referencing without
   reintroducing the exact regression `1c17af8` avoided. If revisited, the
   right framing is probably not "detect and skip" but "trust the more
   granular raw data and substitute it as the corrected value" (discussed at
   length in-session but not implemented — deliberately out of scope, since
   the user asked to *flag* these, not auto-correct them; auto-correction is
   a bigger, riskier design decision that needs explicit sign-off first).

2. **`10.01 Own Use` / `10 Losses & own use` residual (160 rows, ESTO-side,
   `esto_leap_ninth` scope).** Found but **not traced**: multiple `other_
   axis_value` rows (e.g. `02.01 Coke oven coke + 02.07 Coal tar`, `02.03
   Coke oven gas`, `02.04 Blast furnace gas + 02.06 Patent fuel + 02.08
   BKB/PB`) share an identical `frontier_sum` (`-32.003271` for one group of
   four economy-01AUS rows) while each has a different, smaller
   `parent_value` — looks like the shared-frontier-group mechanism (see
   `docs/prompts/anchor_validator_fixes_findings_20260722.md` fix 6,
   "Oil Refining shared-frontier grouping") either isn't collapsing these
   into one primary+skipped group the way it should under this specific
   scope, or a *different* set of products is being incorrectly bucketed
   into the same signature. `missing_expected_children` only ever shows
   `10.01.19 Hydrogen transformation`, which cannot explain a ~32-unit gap.
   **Next step:** trace one concrete row exactly like every fix this session
   did — pick economy `01AUS`, `other_axis_value = "02.01 Coke oven coke +
   02.07 Coal tar"`, dump `frontier_ids_cache`/`frontier_signatures`/
   `shared_groups` for that `(parent_code, oas)` key and see why grouping
   isn't producing the expected single-primary-row outcome, or why
   `frontier_sum` is `-32` when the raw ESTO `10.01 Own Use` value for `02.01
   Coke oven coke` is `0`.

3. **`15_solid_biomass` (183), `16_others` (148), `08_gas` (98) NINTH-side
   residuals, post-`1c17af8`.** Some fraction of these are almost certainly
   more instances of the same source-internal-inconsistency pattern
   `1c17af8` targets, just not caught because the specific (leaf, other-axis)
   pair isn't a frontier *leaf* of the failing row (i.e. they're the "mirror
   row" shape from item 1, or a variant one level removed). Worth sampling a
   handful before assuming they're all copies of the same known gap — do not
   assume; verify each with a real-data trace the way every fix this session
   did.

4. **`14_industry_sector` family (79+75+51+39 ≈ 244 rows across ESTO/NINTH
   variants).** Not investigated at all this session beyond confirming (via
   the retracted candidate CSV's correction) that it is *not* a missing-
   mapping-row gap. Needs its own fresh trace.

5. **8 "ambiguous" candidate mapping pairs** surfaced (then retracted along
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
