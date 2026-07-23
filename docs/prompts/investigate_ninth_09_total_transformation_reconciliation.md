# Resume prompt: NINTH 09 Total transformation reconciliation gap

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
