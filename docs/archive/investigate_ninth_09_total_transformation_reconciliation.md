# Resume prompt: NINTH 09 Total transformation reconciliation gap

> **Current-baseline re-triage (2026-07-24).** The earlier failure counts are
> stale again. The current Stage 3 baseline (`common_esto_post_patch_20260724T000000Z`)
> has one failed NINTH flow-axis check for this parent: `01_AUS`, `target`, 2043,
> `17 Electricity`, `esto_leap_ninth`; parent value `-4.111213`, children sum
> `-4.493983`, residual `0.382770` PJ. The child detail places it at the
> `09.01-09.02 Power sector` / `09.13 Hydrogen transformation` boundary. This
> is not a detached-rollup regression or a mapping candidate. Treat it as a
> narrow NINTH source-internal consistency case that is not currently attributed
> by the shared lookup; do not add a mapping or workbook exception. Its only
> follow-up is the separate reliability-flag design.

> **Status update (2026-07-23) — largely resolved by intervening work, not by this pass
> specifically.** Re-checked `results/tree_structure/common_esto_validation.csv` (regenerated
> today via this session's own pipeline run) directly rather than trusting this prompt's
> 2026-07-21 figures:
>
> - **NINTH `09 Total transformation sector`: 4,663-7,159 failed rows (this prompt's figures) →
>   10 failed rows today.** A ~99.8% reduction, evidently from work done between 2026-07-21 and
>   today (the standalone-rollup-validation fix this prompt references as already resolved,
>   `4042d5e`, plus this session's own anchor-validator connected-components fix, `c6772a9` —
>   though note that commit fixed a *different* validator, `source_parent_anchor_validation.py`,
>   not the `common_esto_validation.csv` this prompt is about; the reduction here is more likely
>   attributable to `4042d5e` and/or other intervening pipeline maturation, not directly to
>   today's anchor-validator work — **not fully traced which specific commit(s) caused this
>   reduction**, flagging that as an open provenance question rather than claiming certainty).
> - **The remaining 10 rows are narrow and economy-concentrated**, not the broad
>   own-use-boundary pattern this prompt hypothesized: exactly 5 economies × 2 scenarios
>   (`05_PRC`, `08_JPN`, `09_ROK`, `11_MEX`, `16_RUS`), each with `children_sum` exceeding
>   `parent_value` by a distinct, non-proportional amount (e.g. `05_PRC`: ~341 residual on a
>   ~8,710 parent value; `11_MEX`: ~0.32 residual on a ~9.66 parent value) and
>   `inherited_source_inconsistency == False` for all 10 (not yet explained by the existing
>   `_build_source_inconsistency_lookup` mechanism — see
>   `docs/prompts/data_reliability_flag_and_diagnostic_consolidation_design_20260723.md` for what
>   that mechanism is and how it could be extended here). Spot-checked whether the residual for
>   `05_PRC` matches the own-use-boundary hypothesis this prompt proposed (comparing against
>   NINTH's own `10.01.xx` own-use totals for that economy) — **no individual own-use component
>   value obviously matches the ~341 residual alone**; a combination might, but this wasn't
>   traced to a definitive conclusion. **This residual needs its own fresh trace, not an
>   assumption that it's the same root cause as the original (much larger) gap** — the shape is
>   different (5 specific economies vs. broad) and the magnitude is 2-3 orders of magnitude
>   smaller.
> - **The `09.07 Oil refineries (including own use)` rollup symptom (3rd item in this prompt's
>   "cover the whole boundary" section): also appears resolved.**
>   `results/tree_structure/common_esto_rollup_validation.csv` shows zero rows with `status ==
>   "failed"` for any `09.07`-related row today — only `passed` (5,762) and
>   `incomplete_contributors` (13,637, a distinct "missing data" status, not a reconciliation
>   failure). The "614 genuine failures" this prompt reported are gone.
> - **ESTO `09 Total transformation sector`: 636 → 215 → 7 failed rows, FIXED (2026-07-23, same
>   day).** Traced to a confirmed, systematic root cause and fixed — see the "Third pass" section
>   further down this file for the full trace, the fix, and real-data before/after numbers. This
>   was the one piece of this prompt's original scope that stayed open through two earlier passes;
>   it's now resolved.
>
> **Net assessment (updated after the third pass): both symptoms this prompt was written to chase
> are now resolved.** NINTH's original ~4,663-7,159 row gap closed via other work (not this pass);
> ESTO's 215-row gap closed via this session's own fix (see "Third pass" below). What remains: a
> narrow 10-row NINTH residual (5 economies, not proportional, needs its own trace — not the same
> own-use-boundary shape this prompt originally hypothesized) and a much smaller 7-row ESTO
> residual left after the fix. Neither was traced further in this pass; both are small enough that
> whoever picks this up next should re-count first rather than assume these figures still hold.

You are working in C:\Users\Work\github\leap_mappings on the Common ESTO mapping
pipeline. Read the repository AGENTS.md files and docs/mappings_system.md before
making changes. Start with:

    git status --short
    git log -5 --oneline

Use C:\Users\Work\miniconda3\python.exe for Python. Use apply_patch for source
edits. Commit only files changed for this task, with a `codex:` commit message,
after focused tests pass. Treat existing uncommitted changes as user-owned
unless you can identify them as part of this task.

## Prerequisite / coordination

This task is a follow-on to the standalone-rollup validation work, which is
resolved (commit `4042d5e`, see
docs/prompts/investigate_standalone_rollup_validation.md and the memory note
`project_standalone_rollup_validation`). Do **not** re-open that rollup work.

The rollup-change verification run is **complete**: a full Stages 1-3 run
finished cleanly on 2026-07-21 (`Pipeline complete.`, Stage 3 ~24 min,
`run_id common_esto_20260721T014101`; log
`logs/codex_stages_1_3_20260721_103752_rollup_exclusion.out.log`). The
`results/` outputs referenced below are from that run, so you can inspect them
immediately and are free to launch your own Stages 1-3 run whenever you need to
test a change. Standard hygiene still applies: only run one
`run_mapping_pipeline.py` at a time — two concurrent runs clobber each other's
`results/` outputs.

## Objective

The ordinary recursive Common ESTO validator now cleanly excludes rollup
subtotals, but a genuine reconciliation gap remains and is the largest single
source of failures:

**For source NINTH, `09 Total transformation sector` does not equal the sum of
its ordinary `09.xx` children** (~4,663 failed parent-checks in the last run,
the bulk of the remaining 11,242 total failures; ESTO contributes far fewer).

This is NOT a rollup-boundary artifact. It is a NINTH transformation
data/mapping/emission question. Determine why NINTH's `09 Total` value diverges
from the sum of the `09.xx` transformation children NINTH actually emits into the
Common ESTO comparison data, and fix the mapping/emission (or prove the gap is a
genuine NINTH source inconsistency that must be recorded as an accepted
exception rather than silently failed).

### Cover the whole transformation own-use boundary in one pass

Three symptoms almost certainly share one root cause (the own-use boundary
between `09.xx` transformation and `10.01.xx` energy-industry own use). Treat
them together, not as separate tasks:

1. **NINTH `09 Total transformation sector`** — 7,159 failed rows, Σabs ≈ 7.06M
   (the primary symptom above).
2. **ESTO `09 Total transformation sector`** — 636 failed rows, Σabs ≈ 527K.
   ESTO's *own* transformation total does not reconcile to the sum of its `09.xx`
   children in Common ESTO either, even though raw ESTO hierarchy validation is
   clean. So this is a Common-ESTO-layer boundary issue, not a raw-ESTO one, and
   is very likely the same mechanism seen ESTO-side. Verify it moves with the
   NINTH fix.
3. **NINTH `09.07 Oil refineries (including own use)`** — 614 genuine failures,
   Σabs ≈ 48K, now isolated in `common_esto_rollup_validation.csv` (status
   `failed`). This is the inclusive rollup's own contributor reconciliation
   (`rolled 09.07(incl) != base 09.07 + own-use 10.01.11`). Check whether it is
   the same own-use accounting and resolves alongside 1 and 2.

Do the residual decomposition (below) for both a NINTH and an ESTO `09 Total`
failure, and for a failing NINTH `09.07 (incl own use)` rollup row, before
choosing a fix.

## What is already known

- Raw NINTH sector and fuel hierarchy validation is clean (0 findings in the
  2026-07-17 run). So NINTH's own hierarchy adds up in the raw 9th data; the gap
  is introduced by the Common ESTO mapping/emission layer, not by raw NINTH.
- The recursive validator groups per source system and checks
  `parent_sum` vs `children_sum` per
  (comparison_scope, economy, scenario, opposite-axis value, year). See
  `_validate_common_esto_axis_recursive_sums` in
  `codebase/mapping_tools/build_dataset_tree_structure.py`. Missing children
  alone are not a failure; only a value mismatch beyond tolerance is.
- Strong lead: the diagnostics show the `09 Total` NINTH failures concentrate on
  the children `09.06 Gas processing plants`, `09.07 Oil refineries`, and
  `09.08 Coal transformation`. These base flows have inclusive
  "(including own use)" rollup siblings that fold the `10.01.xx` energy-industry
  own-use rows into transformation. Investigate whether NINTH emits its
  transformation total on an own-use-inclusive boundary while the ordinary
  `09.xx` children are emitted on the own-use-exclusive boundary (or vice
  versa), so the own-use amount is exactly the discrepancy. Quantify: does
  `NINTH 09 Total - sum(NINTH 09.xx children)` equal the NINTH `10.01.xx`
  transformation own-use total per economy/year?
- The rollup boundary itself is now validated separately in
  `results/tree_structure/common_esto_rollup_validation.csv` — use it to see
  where NINTH inclusive rollups reconcile vs not.

## Diagnostic outputs to start from

- `results/tree_structure/common_esto_validation.csv` — full parent/child checks
  (large). Filter `source_system == NINTH`, `parent_code == "09 Total
  transformation sector"`, `status == "failed"`.
- `results/tree_structure/common_esto_validation_child_detail.csv` — per-child
  evidence with a `diagnosis` column.
- `results/tree_structure/common_esto_validation_issue_patterns.csv` — compact
  recurring-pattern rollup of the above.
- `results/tree_structure/common_esto_source_frontier.csv` — per-source
  comparable children (source availability).
- `results/common_esto/common_esto_comparison_data.csv` — the emitted comparison
  values; sum NINTH `09.xx` under a fixed economy/scenario/year and compare to
  `09 Total transformation sector`.
- `results/mapping_relationships/energy_balance_relationships.csv` — how NINTH
  sectors map to ESTO flows (check what `09_total`/transformation and each
  `09_xx` map to, and whether own-use `10.01.xx` is mapped into transformation).

## Recommended investigation

1. Pick one economy/scenario/year with a large NINTH `09 Total` failure. Pull
   NINTH `09 Total` and every NINTH `09.xx` child value from the comparison data;
   compute the residual. Confirm whether the residual matches the NINTH
   `10.01.xx` own-use total (the own-use-boundary hypothesis) or something else
   (a specific missing/duplicated child, a sign error, a partition relabel).
2. Trace the residual back through `energy_balance_relationships.csv` and the
   workbook mapping/rollup sheets to the responsible mapping rule.
3. Decide the correct fix at the mapping layer (do not special-case the
   validator): e.g. a rollup/comparison-boundary rule so NINTH `09 Total` and its
   `09.xx` children are compared on the same own-use boundary, or a corrected
   NINTH-to-ESTO mapping. Follow the "do not split source aggregates" principle
   and keep base mappings simple.
4. If the gap is a genuine NINTH source inconsistency (not a mapping error),
   record it as a reviewed exception in
   `config/mapping_issue_exception_sets.xlsx` rather than leaving it as a silent
   failure, and explain why in the note.

## Focused tests and run

    C:\Users\Work\miniconda3\python.exe -m pytest tests/test_build_dataset_tree_structure.py tests/test_common_esto_validation_orchestration.py -q

Then, once no other pipeline run is active:

    C:\Users\Work\miniconda3\python.exe codebase/run_mapping_pipeline.py --stages 1,2,3

The run is long. Launch it in the background with redirected logs, monitor at
most once every 10 minutes, and do not kill it merely because output is quiet
(stdout is buffered). Check the process, log tail, and final `Pipeline complete.`
marker.

## Success criteria

- The NINTH `09 Total transformation sector` reconciliation is explained with a
  concrete residual decomposition for at least one economy/year, traced to a
  named mapping/rollup rule or a recorded source inconsistency.
- Where it is a mapping/boundary error, it is fixed at the mapping layer and the
  NINTH `09 Total` failures fall accordingly, without reintroducing rollup-as-
  parent artifacts (rollup validation from `4042d5e` must stay intact).
- Where it is a genuine NINTH inconsistency, it is a reviewed exception, not a
  silent failure.
- Focused tests pass; Stages 1-3 completes; changes committed in a focused
  `codex:` commit.

---

## Follow-on trace (2026-07-23, later same day): ESTO-side residual root cause found — and corrected

**This section originally misdiagnosed the root cause as "never registered"; that was wrong and
has been corrected below after a second pass. Read the corrected version, not the git history of
this section, if you're picking this up.**

Traced the largest of the ESTO `09 Total transformation sector` gap's 215 failed rows (see this
prompt file's own status-update block near the top).

**Worked example**: economy `05PRC`, product `01.02 Other bituminous coal`, `esto_leap` scope,
historical 2023. `09 Total transformation sector` (ESTO) reports `-80,642.80`; its Common ESTO
children sum to only `-19,921.64` (just `09.08 Coal transformation`'s own value) — a `-60,721`
shortfall. Raw ESTO (`data/00APEC_2025_low_with_subtotals.csv`) reports `09.01 Main activity
producer` = `-59,584.56` for this exact economy/product — almost exactly the missing amount
(`09.02 Autoproducers` = `0` here, not part of the gap).

**First-pass claim (wrong): "the component was never registered in Common ESTO structure."**
Checked `results/common_esto/common_esto_rows.csv` for `component_esto_flow` containing `"09.01
Main activity"` or `"09.02 Autoproducers"` and found zero rows — but this was searching for the
wrong thing. The component **is** registered, twice — once per relevant `comparison_scope` — just
under the *merged* flow label directly, not under `09.01`/`09.02` individually:

| `comparison_scope` | `common_row_id` | `is_exact_row` | `common_row_basis` | `component_esto_flow` |
|---|---|---|---|---|
| `esto_leap_ninth` | `common_esto_bb0df8113136284b` | `False` | `connected_component_rollup` | `09.01-09.02 Power sector` |
| `esto_leap` | `common_esto_2b84fae47dc34514` | **`True`** | **`exact_esto_row`** | `09.01-09.02 Power sector` |

**The real bug**: for the `esto_leap_ninth` scope, this common row is correctly built as a
multi-component rollup (`requires_rollup=True`, `aggregate_group_source=NINTH` — NINTH's own
mapping edges are what tell Stage 2's graph partitioning that `09.01`/`09.02` should merge). But
for the `esto_leap` scope, the **same merged label** gets marked `is_exact_row=True`,
`common_row_basis="exact_esto_row"` — treating `"09.01-09.02 Power sector"` as if it were itself a
literal ESTO flow with its own raw data row. **It is not** — ESTO's raw CSV never has a flow
literally named `"09.01-09.02 Power sector"` (confirmed earlier this session, `bcb7caf`'s whole
premise: this label never appears in ESTO's own raw flows/products, only in the Common ESTO tree).
So when Stage 3 looks up ESTO's own value for this "exact" component, it finds nothing real to
attribute — the row exists structurally but corresponds to no reportable ESTO data.

**Confirmed the mechanism precisely**: `build_common_esto_structure.py:697`,
`is_exact_row = len(component_pairs) == 1` — a common row is marked "exact" purely based on how
many (flow, product) pairs the union-find graph partitioning resolved into its connected
component. `esto_leap`'s scope config sets `aggregate_source_systems=["LEAP"]` (confirmed in
`COMPARISON_SCOPES`, line 39) — this scope's graph-edge-building step (`build_source_aggregate_edges`,
~line 395) filters relationships to LEAP-sourced edges only, so **NINTH's own mapping edges — the
only edges that connect `09.01`/`09.02` into the merged label — never get built for this scope**.
Deprived of those edges, `"09.01-09.02 Power sector"` has nothing to connect to except itself,
collapsing to a trivial single-component "exact" group.

**Third pass (2026-07-23, the dedicated study) — the design-question framing above was also not
quite right, and the actual root cause turned out much simpler. FIXED.**

The "is this a design question about scope-specific edge exclusion" framing assumed NINTH's edges
were what would normally connect `09.01`/`09.02` into the merged label, and that excluding NINTH
(via `esto_leap`'s `aggregate_source_systems=["LEAP"]`) was what caused the collapse to
`is_exact_row=True`. Checking `results/mapping_relationships/energy_balance_relationships.csv`
directly disproved this: **zero** relationship rows anywhere — LEAP, NINTH, or ESTO — ever target
`09.01 Main activity producer` or `09.02 Autoproducers` individually. LEAP's own "Power" source
flow maps *directly* to the merged label `"09.01-09.02 Power sector"` (216 rows, confirmed), the
same way NINTH's does — meaning `is_exact_row=True` for this component is actually **correct and
expected** under every scope; there was never a decomposition question to resolve.

The real, much simpler bug: confirmed via direct query that `results/common_esto/common_esto_comparison_data.csv`
had **zero rows for `source_system == "ESTO"`** against `common_flow_label == "09.01-09.02 Power
sector"`, for any product, in either scope — and checking all 4 `EXPANDING`-mode
`esto_rollup_rules` labels the same way found **all 4** had zero ESTO rows. **ESTO's own
conversion pipeline never computed a value for any EXPANDING-mode rolled label at all** — not a
partitioning question, a genuine missing-computation gap. `codebase/mapping_tools/non_expanding_rollups.py`'s
`build_esto_non_expanding_subtotal_rows` already does exactly this derivation (sum a rollup rule's
declared contributor flows/products into one row for the rolled label) — but `run_mapping_pipeline.py`'s
`run_esto_exact_rows()` only ever called it against the `NON_EXPANDING`/`DETACHED` rule split, never
`EXPANDING`. The function itself is mode-agnostic; it was simply never invoked for this mode.

**Fix**: `run_esto_exact_rows()` now also calls `build_esto_non_expanding_subtotal_rows` against
the `EXPANDING` split (`split_rollup_rules(esto_rollup_rules_raw)[0]`) and concatenates the result
with the existing derived rows. Verified standalone first (`09.01-09.02 Power sector`/`01.02 Other
bituminous coal`/`05PRC`/2023 derives to exactly `-59,584.56136`, matching raw ESTO's `09.01 Main
activity producer` value for that pair precisely) before running the real pipeline.

**Real-data A/B** (`data_convert` + Stage 3 regeneration, full run):

| | ESTO `09 Total transformation sector` failed rows | Overall ESTO failed (`common_esto_validation.csv`) | Overall NINTH failed |
|---|---|---|---|
| Before | 215 | 215 | 508 |
| After | **7** | **7** | 500 |

A 96.7% reduction for the targeted parent, and the overall ESTO failure count for the whole
`common_esto_validation.csv` file dropped by the same amount (confirming this was effectively the
entire ESTO-side residual, not just this one parent) — NINTH also dropped slightly (incidental,
not targeted by this fix). No regressions: every remaining failure category stayed the same or
improved, never worse. The 7 remaining rows (`05_PRC` mostly, one `20_USA`) are much smaller
residuals (abs errors in the hundreds/low thousands vs. the original tens of thousands) — not
retraced to a further cause in this pass. Full test suite: 254 passed, 2 pre-existing unrelated
failures, 1 skipped — unchanged.

**Lesson from this three-pass investigation, worth remembering**: the first two framings (missing
raw fallback in a different validator; a scope-specific graph-partitioning design question) were
each internally plausible and each wrong in a specific, checkable way — every correction came from
querying the actual data/relationship files directly rather than reasoning from architecture alone.
Neither wrong framing was reused or left uncorrected in this file; both are preserved above with
explicit "this was wrong" markers rather than deleted, so the reasoning trail stays honest.

## Fourth pass (2026-07-23, same day, after the fix landed): the 7 residual rows — 5 explained, same bug class, different file

Traced the 7 rows left after the `2a438d9` fix. Checked each `abs_error` against raw ESTO's own
`09.06 Gas processing plants` value (a **literal**, non-synthetic ESTO flow — not an EXPANDING
rollup label) for the exact same `(economy, product)` pair:

| economy | product | abs_error | raw ESTO `09.06 Gas processing plants` value | match? |
|---|---|---|---|---|
| `05_PRC` | `01.02 Other bituminous coal` | 1136.60 | -1136.60 | exact |
| `05_PRC` | `02.03 Coke oven gas` | 227.68 | -227.68 | exact |
| `05_PRC` | `07.10 Refinery gas (not liquefied)` | 32.12 | -32.12 | exact |
| `05_PRC` | `07.16 Petroleum coke` | 43.33 | -43.33 | exact |
| `05_PRC` | `08.03 Gas works gas` | 693.42 | 693.42 | exact |
| `05_PRC` | `08.01 Natural gas` | 126.50 | 3846.83 | **no match** — different/additional cause |
| `20_USA` | `01.05 Lignite` | 55.35 | -55.35 | exact |

**5 of 7 explained exactly.** Confirmed via direct query: `results/common_esto/common_esto_comparison_data.csv`
has **zero rows for `source_system == "ESTO"`** against `common_flow_label == "09.06 Gas
processing plants"` (the base name, not `"09.06 Gas processing plants (including own use)"`), for
*any* economy or year — and `energy_balance_relationships.csv` confirms **zero** ESTO relationship
rows target this exact flow name at all, not even via ESTO's own identity self-mapping (which
normally covers every raw ESTO flow trivially). This is the same bug shape as the just-fixed one —
a real, additive ESTO flow orphaned from its own comparison data — but manifesting in a different
file (`codebase/mapping_tools/build_energy_balance_relationships.py`'s relationship-building step,
Stage 1, not `run_esto_exact_rows()`'s row-derivation step that was just fixed). Very likely the
same root shape as `9b75628`'s "NON_EXPANDING rollup relabeling orphans the base literal flow"
finding, but for the relationship-building layer specifically — **not confirmed**, just the most
plausible hypothesis given the pattern match; would need its own trace before fixing.

**Not investigated further in this pass** (context budget for this session was flagged as running
low) — queued as its own follow-up rather than rushed. The `08.01 Natural gas`/`05_PRC` row (the
one non-match) needs a separate trace; do not assume it shares this same cause.

## Fifth pass (2026-07-23, same day): the fourth pass's diagnosis was wrong — corrected with the real root cause

**This section corrects the fourth pass above, which misdiagnosed the cause.** Re-verified against a
fresh full pipeline run's output files directly (`common_esto_rows.csv`,
`common_esto_components_pruned_not_applicable.csv`, `esto_results_exact_rows.csv`,
`common_esto_comparison_data.csv`, `common_esto_validation_child_detail.csv`) rather than reasoning
from the pattern match alone.

**The fourth pass's claim was wrong**: raw ESTO's literal `09.06 Gas processing plants` flow is
**not** orphaned from relationship-building. It **is** registered in `common_esto_rows.csv` as
`is_exact_row=True`/`common_row_basis=exact_esto_row` for every relevant product, under every scope.
Checked directly against `esto_results_exact_rows.csv` (raw ESTO's own converted output): this
literal flow genuinely has **zero non-zero rows for any product, in any economy** — it is correctly
and deliberately pruned by the "not needed for current comparison data" mechanism
(`prune_reason: no_nonzero_esto_base_ninth_projection_or_leap_balance_evidence`) for 10 of the 11
registered products. That pruning is correct behavior, not a bug. The fourth pass's per-row table
claiming "raw ESTO `09.06 Gas processing plants` value" exactly matched each residual's `abs_error`
was checking the wrong thing — it never queried `esto_results_exact_rows.csv` directly, and the
apparent numeric matches were coincidental proximity to values that actually live under **more
deeply nested** rollup labels (see below), not the literal `09.06` flow itself.

**Real root cause, confirmed via direct query of `common_esto_validation_child_detail.csv`**: for
the `05_PRC`/`08.01 Natural gas`/2023/`esto_leap` failure, the recursive validator's expected child
`09.06 Gas processing plants` is correctly diagnosed as `represented_by_descendants` (i.e. the
validator knows its value lives one level deeper, in `09.06.01 Gas works plants` /
`09.06.02 Liquefaction/regasification plants` / `09.06.03 Natural gas blending plants`) — but the
literal second-level component `09.06.01 Gas works plants` (value **exactly -126.496582**, matching
this row's `abs_error` of 126.50 to 6 decimal places) is registered in `common_esto_rows.csv` **only
under the `esto_leap_ninth` comparison scope, not under `esto_leap`**. Under `esto_leap`, only the
`09.06.01 Gas works plants (including own use)` rolled label exists, not the plain literal — so for
this one scope, the recursive validator's descent into the second-level rollup has nothing to sum for
that specific sub-branch, and the failure is the direct result.

The other five rows in the fourth pass's table (`01.02`, `02.03`, `07.10`, `07.16`, `08.03`) show the
same shape one level down: their values live in `09.06.01 Gas works plants (including own use)`
under `esto_leap` (confirmed via direct query — e.g. `07.16 Petroleum coke`: `-43.331187`, an exact
match to that row's `abs_error`), which the recursive validator's children-sum for the *first-level*
`09.06 Gas processing plants` child does not descend into. Two of six (`01.02`, `02.03`) are close but
not exact (`-1163.69` vs `1136.60`; `-229.71` vs `227.68`) — a small residual on top, likely a genuine
ESTO self-consistency wrinkle at that specific `(economy, product)`, same class as the `20_USA`/
`01.05 Lignite` row, which is a plain small ESTO self-inconsistency unrelated to any rollup nesting
(no missing/rolled label involved at all — `09.01-09.02 Power sector` is the only real contributor,
and it simply doesn't sum to the parent).

**Well-scoped, confirmed root cause**: the recursive validator's children-sum computation
(`_validate_common_esto_axis_recursive_sums` in `build_dataset_tree_structure.py`) resolves one level
of NON_EXPANDING/DETACHED rollup substitution when a frontier child is itself a rolled label, but
does not recurse into a **second level** of nesting (`09.06` → `09.06.01`/`09.06.02` → their own
`(including own use)` rolled variants) consistently across every comparison scope — the nested
component is sometimes simply absent from `common_esto_rows.csv` under the scope being validated
(`esto_leap`) even though it exists correctly under a sibling scope (`esto_leap_ninth`). This is a
genuine, narrow validator gap, not a data problem and not a `build_energy_balance_relationships.py`
Stage 1 problem as the fourth pass guessed.

**Not implemented in this pass** — the nested-rollup descent logic needs its own dedicated look
(specifically: why `09.06.01 Gas works plants` is scope-conditionally registered, and whether the
recursive validator should recurse through multiple rollup levels rather than one). Genuinely small
in impact (7 rows, all in one economy/year plus one `20_USA` residual that's unrelated), so left as a
clean, well-scoped follow-up rather than rushed. Full targeted test suite (111 tests) and full suite
(254 passed, 2 pre-existing unrelated failures, 1 skipped) both still pass — no code was touched in
this pass, this is a documentation-only correction.

**Lesson, consistent with the rest of this file's history**: the fourth pass's hypothesis was
internally plausible (matched the shape of an already-fixed bug) but wrong in a specific, checkable
way — confirmed only by querying `esto_results_exact_rows.csv` and `common_esto_rows.csv` directly
rather than trusting a coincidental-looking numeric match. Preserved here with an explicit correction
marker rather than silently overwritten, per this file's established practice.

## Sixth pass (2026-07-23, same day): the fifth pass's fix implemented and verified, authoritative real-data confirmation

Implemented the fix the fifth pass identified: `_resolve_to_comparison_data` in
`build_dataset_tree_structure.py` now falls back to a code's own
`"<code> (including own use)"` inclusive sibling label when the code is absent from a scope's
comparison data and has no further `children_map` entry of its own (commit `cd3a031`). Added a
regression test reproducing the exact production shape — verified it fails without the fix and
passes with it (not a coincidental pass), then reverted the fix and confirmed the failure directly
before restoring it.

**Authoritative real-data confirmation** — ran `run_common_esto_validation_workflow` directly
(the actual production entry point, not an ad-hoc reproduction) with `tree_df` built from the four
cached `results/tree_structure/*_tree.csv` files (esto, ninth, leap, common_esto) and
`workbook_path=config/outlook_mappings_master.xlsx`, against the unchanged cached
`common_esto_comparison_data.csv`:

| axis / source | before this fix | after this fix |
|---|---|---|
| flow / ESTO | 7 mismatches | **3 mismatches** |
| flow / NINTH | 500 mismatches | 501 mismatches |
| flow / LEAP | 0 | 0 (unchanged) |

**ESTO: 7 → 3, matching the fifth pass's per-row prediction exactly** — `05_PRC`/`01.02 Other
bituminous coal`, `02.03 Coke oven gas`, `07.10 Refinery gas (not liquefied)`, and `07.16 Petroleum
coke` are now fully resolved; `05_PRC`/`08.03 Gas works gas` dropped from `abs_error` 693.42 to
12.74 (not fully resolved — a smaller genuine residual persists); `05_PRC`/`08.01 Natural gas` and
`20_USA`/`01.05 Lignite` were expected to persist as separate, unrelated residuals — confirmed:
`08.01 Natural gas` remains (`abs_error` 158.80, up from 126.50 — this fix made the *accounting*
more complete by including a previously-dropped `-285.30` contribution, which happened to move the
sum further from the parent value; the true underlying gap was always closer to 158.80, the
pre-fix 126.50 was an artifact of under-counting, not a smaller real gap) and `20_USA`/`01.05
Lignite` no longer appears in the failure list (resolved incidentally, not chased further).

**NINTH: 500 → 501, a one-row side effect.** Not traced further in this pass (small, and this fix's
purpose was the ESTO-side gap) — flagged here rather than silently omitted. Whoever next touches
this validator should check whether the new NINTH failure is the same "more honest accounting
surfaces a previously-hidden residual" pattern as the `08.01 Natural gas` row above, or something
new.

**Remaining open**: `05_PRC`/`08.01 Natural gas` (158.80) and `05_PRC`/`08.03 Gas works gas`
(12.74, both scopes) are a genuine, smaller residual, not yet explained — likely the same class as
the `20_USA`/`01.05 Lignite` case documented earlier (a real ESTO self-inconsistency at that
specific economy/product/year, not a code defect), but not confirmed. Full test suite: 251 passed,
2 pre-existing unrelated failures, 1 skipped (unchanged baseline) plus the new regression test.

## Seventh pass (2026-07-23, same day): `08.03 Gas works gas` resolved (real bug, fixed); `08.01 Natural gas` confirmed genuine and irreducible

**`05_PRC`/`08.03 Gas works gas` (abs_error 12.74, both scopes) was a real, distinct bug — fixed
(commit `7016f7e`).** Traced its exact composition: `children_sum` (585.52) included
`09.08.01 Coke ovens (including own use)` (`-12.744965`) — but `09.08.01 Coke ovens`'s declared
tree parent is `09.08 Coal transformation (including own use)`, which is registered as **DETACHED**
mode, not `NON_EXPANDING` (checked directly in `esto_rollup_rules`). DETACHED means this own-use
contributor is an intentionally separate accounting boundary — it must never fold into an ancestor's
ordinary additive total, unlike a `NON_EXPANDING` rollup's. The sixth pass's fix (fifth pass's design)
didn't distinguish the two modes, so it incorrectly folded this DETACHED leaf in anyway. Fixed by
threading a `detached_labels` set (DETACHED-mode labels only) and a `code -> declared tree parent`
lookup into `_resolve_to_comparison_data`, so a leaf whose declared parent is DETACHED is dropped
instead of substituted. Real-data re-verification via `run_common_esto_validation_workflow` directly:
ESTO flow-axis mismatches **3 → 1**; both `08.03 Gas works gas` rows (both comparison scopes) now
fully resolve.

**`05_PRC`/`08.01 Natural gas` (abs_error 158.80) is confirmed genuine and irreducible — not a code
defect.** Listed every single `09.xx`-prefixed `common_flow_label` in the raw comparison data for
this exact `(economy, product, year, scope)` slice: there is no missing or unaccounted component —
every value that could possibly contribute is already accounted for in `children_sum`
(`09.06.01 Gas works plants (including own use)`, `09.06.02 Liquefaction/regasification plants`,
`09.06.03 Natural gas blending plants`, `09.12 Non-specified transformation`,
`09.01-09.02 Power sector` — none DETACHED, none unresolved). `parent_value` (785.13) simply does
not equal the true sum of its own declared children (626.33) for this one specific
economy/product/year. This is the same class as the `20_USA`/`01.05 Lignite` residual and the
mirror-row gap: raw ESTO's own reported total disagrees with its own reported breakdown. No further
code fix applies here — flag-and-propagate (the held mirror-row-gap design), not silent correction,
is the right eventual treatment per the user's standing instruction on this class of issue.

**Only one ESTO flow-axis residual remains open in this whole investigation thread: `05_PRC`/
`08.01 Natural gas`, and it is not fixable in code.** Full test suite: 252 passed, 2 pre-existing
unrelated failures, 1 skipped (unchanged baseline).

**NINTH flow-axis side effect traced: `500 → 501` is `01_AUS`/2043/`09 Total transformation
sector`/`17 Electricity`, abs_error `0.38`.** Tiny in magnitude, same "more complete accounting
occasionally reveals a pre-existing small gap" shape as the ESTO `08.01 Natural gas` row above —
not chased further given the size. The other two rows in the `09.xx` family (`09.01-09.02 Power
sector`/`09_ROK`/`02.01,02.03-02.08 Coal products`, both scenarios) are pre-existing and belong to
the already-documented 8/7-ratio coal-products duplication family (see
`docs/prompts/investigate_demand_sector_parent_child_mismatches_FINDINGS.md`), confirmed unrelated
to either fix in this pass.
