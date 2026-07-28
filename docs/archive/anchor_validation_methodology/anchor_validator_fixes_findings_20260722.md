# Anchor validator fix session — findings and handoff (2026-07-22, follow-on)

This continues `docs/prompts/holistic_mapping_system_stocktake_findings_20260722.md`
(the earlier stocktake) into an implementation session. Six fixes landed in
`codebase/mapping_tools/source_parent_anchor_validation.py` (plus one in
`codebase/mapping_tools/structural_resolver.py` and wiring in
`codebase/run_mapping_pipeline.py`), each verified against real Stage 3 runs,
not just synthetic tests — verification against real data caught two of the
fixes behaving very differently than their unit tests suggested, so treat
"tests pass" and "verified against real data" as two separate claims
throughout this note.

**Nothing in this session has been committed.** All changes are in the
working tree; `git status --short` at the end of this session shows only:
`codebase/mapping_tools/source_parent_anchor_validation.py`,
`codebase/mapping_tools/structural_resolver.py`, `codebase/run_mapping_pipeline.py`,
`tests/test_source_parent_anchor_validation.py`, `tests/test_structural_resolver.py`
— plus the pre-existing user-owned workbook/doc changes noted in the original
stocktake, untouched. Test suite: `pytest -q tests/test_structural_resolver.py
tests/test_source_parent_anchor_validation.py` → **36/36 passing**.

## Verified real-world impact (all economies/years, final run `common_esto_20260722T120309140906Z`)

| Cluster | Baseline (original stocktake) | Final verified | Change |
|---|---|---|---|
| `Oil Refining` (LEAP flow) | 90 failed | **0 failed** (380 passed, 664 skipped) | Fully resolved |
| `16 Other sector` (ESTO flow) | 303 failed | **37 failed** (453 passed) | ~88% reduction |
| `14 Industry sector` (ESTO flow) | 302 + 288 = 590 failed | **51 failed** (554 passed) | ~91% reduction |
| `16_other_sector` (NINTH flow) | not separately tracked | 111 failed (2,584 passed) | — |
| `14_industry_sector` / `14.03 Manufacturing` (NINTH flow) | 248 failed | 243 failed | small |
| NINTH product axis (aggregate fuels: `12_solar`, `07_petroleum_products`, `15_solid_biomass`, `16_others`) | 3,848 failed | **1,843 failed** | ~52% reduction |
| `09 Total transformation sector` (ESTO flow) | 485-486 failed | **486 failed, unchanged** | See below — different, unfixed mechanism |
| `09_total_transformation_sector/09_06_gas_processing_plants` (NINTH flow) | 462 failed | **462 failed, unchanged** | Same — see below |
| Total genuine failures (all axes/systems) | ~9,100 | **5,574** | ~39% reduction |
| Recursive Common ESTO validator (`common_esto_validation_summary.csv`) | 1 / 2 / 8 mismatches (ESTO/LEAP/NINTH) | 215 / 0 / 403 | **Confirmed unrelated to these fixes** — traced to the user's own concurrent workbook mapping additions (workbook `mtime` changed between the healthy baseline and every run in this session; user confirmed "we created a bunch of new mappings"). Stable across all three reruns in this session with unchanged code between them, so not a regression from anything in this note. |

The two "unchanged, byte-for-byte, across every run" numbers
(`09 Total transformation sector` = 486 exactly, three separate times, across
runs before and after every fix in this session) is the strongest signal in
this whole investigation: it means `09`'s failures are **not** the mechanism
these fixes target at all. See "What's still broken" below.

## Fixes landed, in the order they were made

1. **`exclude_parents` set for NON_EXPANDING/DETACHED rollup labels**
   (`_children_map`, `validate_source_parent_anchors` in
   `source_parent_anchor_validation.py`; wired in `run_stage_3` in
   `run_mapping_pipeline.py` via `non_expanding_rollups.load_rollup_mode_labels`).
   Stops a rolled label (e.g. `09.06 Gas processing plants`) from being
   independently validated as its own additive parent, mirroring the
   recursive Common ESTO validator's existing `exclude_parents` mechanism.

   **This fix shipped with a real bug that was only found and fixed later
   this session** (see fix 7 below) — the first version dropped excluded
   labels entirely out of the raw-tree parent/child edges, not just out of
   independent-parent validation, which broke an unrelated thing (see fix 7).
   Do not re-introduce the old behavior.

2. **`literal_pairs` remap-suppression** (same file, the pair-remap block in
   `validate_source_parent_anchors`). Raw NINTH/ESTO source hierarchies often
   report the same numeric total as a literal row at multiple hierarchy
   depths at once (a leaf whose "x"-rollup subtotal duplicates its own
   parent's "x"-rollup subtotal). The nearest-mapped-ancestor resolver used to
   remap an unmapped leaf onto such an ancestor, double-counting against the
   ancestor's own already-present row. Now suppressed when the resolved
   target already has its own literal row for that exact pair. This is what
   fixed the four aggregate-fuel NINTH product families.

3. **Crash guard in `structural_resolver.py`**
   (`resolve_parent_to_mapped_other_axis`, line ~200). `nested_candidates`
   used `all(...)` over an empty generator (vacuously `True`) when zero
   candidates resolved, skipping the early-return guard and crashing on
   `max()` over an empty set. This is what killed the first Stage 3 rerun
   attempt this session; now guarded (`bool(candidates) and all(...)`).

4. **LEAP interim-branch exclusion** (`run_stage_3` in
   `run_mapping_pipeline.py`). `CHP interim` / `Electricity interim` /
   `Heat plant interim` (declared in `config/source_branch_fallback_rules.csv`)
   are an alternative-representation branch, not an independent additive
   total — same semantic as a NON_EXPANDING label, just from a different
   config source. Added to the same `exclude_parents` set. Verified: `CHP
   interim` now produces **zero** anchor rows at all (fully excluded, per
   `df[df['parent_code']=='CHP interim']` returning empty in the final run).

5. **`has_data_pairs` data-availability check in `_mapped_descendants`**
   (`source_parent_anchor_validation.py`). ESTO's raw `with_subtotals` file
   carries an explicit subtotal row at every hierarchy level, so an
   intermediate code (`16.01 Commercial and public services`) can have its
   own direct raw-data match that duplicates its only real child's value
   (`16.01.99 ... unallocated`) — and Common ESTO structure building prunes
   the intermediate row's own comparison data as a redundant duplicate for a
   given source system, without the anchor validator knowing to fall through
   to the surviving child. Fix: only trust a direct match as-is if it has
   real comparison data *somewhere* (built once per source system, not
   per-row); otherwise descend into children if any exist. This required two
   attempts — the first attempt (structural heuristic: "descend if any child
   also has its own direct row") regressed the NX/NON_EXPANDING test case and
   was reverted; the second, correct attempt checks actual data availability
   instead of tree structure.

6. **Oil Refining shared-frontier grouping** (`validate_source_parent_anchors`,
   after the `base["_matched"]` block). For `esto_leap_ninth` scope, several
   distinct LEAP products can legitimately collapse onto one shared Common
   ESTO aggregate row (e.g. `07.12-07.17 Petroleum products`) because NINTH
   can't distinguish them — correct and intentional. But the validator was
   comparing each product's own individual raw value against that shared
   combined frontier, which can only pass for one product. Fix: detect
   `other_axis_value`s under the same `parent_code`/scope that resolve to an
   identical frontier signature (same set of `common_row_id`s), combine their
   raw values into one "primary" check, and mark the rest `skipped` with
   reason `grouped_with_shared_frontier_sibling`.

7. **Fixed a real regression introduced by fix 1** — the most important
   correction this session. `_children_map`'s original `exclude_parents`
   implementation dropped excluded labels **entirely** out of the
   `children` dict, not just out of `parents_present`. But that same dict is
   also used by `_mapped_descendants` to descend *into* a code's children
   while resolving a *different* ancestor's frontier (e.g. descending into
   `16.01-16.02 Buildings` while resolving `16 Other sector`'s own frontier).
   Once a label was excluded, it could never be descended into again from
   anywhere — collapsing dependent frontiers to empty
   (`frontier_row_count=0`) across ~97% of `16 Other sector`'s rows in the
   first post-fix-5/6 Stage 3 rerun. Root-caused via direct reproduction
   against real pickled pipeline inputs (not just re-reading CSVs), confirmed
   with monkeypatch tracing of `_mapped_descendants` calls. Fixed by keeping
   `_children_map` exclude-agnostic (always returns full tree edges) and
   applying the exclusion only where it belongs:
   `parents_present = set(children.keys()) - (exclude_parents or set())`.
   Added `test_excluded_parent_still_descendable_from_a_grandparent` as a
   permanent regression guard — the existing NX-based tests did not catch
   this because that fixture's NX had its own real comparison data and never
   needed the children-dict lookup at all.

   This retroactively explains **why fix 1 first appeared to have "zero
   real-world impact"** on `09`/`14` in the very first verification rerun:
   `run_stage_3`'s `try/except Exception: anchor_exclude_parents = set()`
   around loading rollup-mode labels swallows failures silently with no
   logging. It's plausible (not confirmed) that the very first post-fix
   Stage 3 run hit an exception there (workbook was being actively edited by
   the user at the time) and ran with an empty `exclude_parents`, making that
   run's "zero impact" result look like a diagnosis failure when it may have
   just been a silent no-op. **Recommended follow-up, not done this
   session:** add a `print`/log line in that except-block so a silent
   fallback is never invisible again.

## What's still broken — the actual next backlog item

**`09 Total transformation sector` (ESTO flow, 486 failures) and its NINTH
sibling `09_total_transformation_sector/09_06_gas_processing_plants` (462
failures) are unchanged by every fix in this session, unlike `14 Industry
sector` and `16 Other sector` which share the exact same subtotal-short-circuit
mechanism and dropped ~90%.** That means `09`'s dominant failure mode is a
**separate, still-unfixed mechanism** already identified earlier this session
but never acted on:

`results/tree_structure/all_dataset_trees.csv` (dataset=`esto`, axis=`flow`)
shows `09.01 Main activity producer` and `09.02 Autoproducers` as
**childless** — their true children (`09.01.01 Electricity plants` etc.)
instead point to a synthetic *merged* parent code
`"09.01.01,09.02.01 Electricity plants"` that concatenates both branches. Raw
ESTO's identity self-mapping still gives `09.01 Main activity producer` a
"direct" match, so `_mapped_descendants` resolves it immediately — but
`common_esto_rows.csv` has zero rows mapping `09.01`/`09.02` for most
products; the real component is a Common-ESTO-only merged label
`"09.01-09.02 Power sector"` that doesn't exist in the raw tree at all, so
it's structurally unreachable regardless of any anchor-validator logic. This
is a genuine **tree-construction defect**, not a validator bug — it lives in
whatever builds `all_dataset_trees.csv` (search
`codebase/mapping_tools/build_dataset_tree_structure.py` for how ESTO's flow
tree assigns `09.01.01`/`09.02.01`'s `parent_code`, and find where the
`"09.01.01,09.02.01 Electricity plants"` merged code gets synthesized versus
where Common ESTO's `"09.01-09.02 Power sector"` label gets built — they need
to agree, or the merge needs to happen consistently on both sides).

Confidence this is the right target: high. `14 Industry sector`/`16 Other
sector` prove the subtotal-short-circuit fix generalizes cleanly when that's
the actual mechanism; `09`'s exact, unmoved count across three different code
states is the cleanest possible signal that something else entirely is
driving it.

### Smaller, lower-priority residuals also visible in the final run

> **Re-triaged 2026-07-23 (a follow-on session, same day the connected-components
> shared-frontier fix landed — `c6772a9` on branch `claude/anchor-validator-fixes-ee04bc`).
> Checked all four items below directly against the current corrected baseline (759 failed /
> 55,517 passed / 259,584 skipped) rather than trusting these 2026-07-22 figures.**

- ~~`10 Losses & own use` / `10.01 Own Use` (ESTO flow): 196 / 191 failed~~ — **fully resolved,
  0 failed rows today.** Almost certainly resolved by the connected-components shared-frontier
  fix (`c6772a9`) — this is exactly the flow family that fix's own real-data trace centered on.
- ~~`01 Coal`, `08 Gas`, `07 Petroleum products`, `15 Solid biomass` (ESTO product axis,
  `frontier_rows_absent`): 104/209/256/94~~ — **fully resolved, 0 rows today** for any of these
  four parents with this reason. Same likely cause as above.
- **The passenger-road/transport `no_anchorable_common_esto_boundary` bucket: down from 66,402 to
  35,369 rows (~47% reduction, cause not traced — likely incidental to other fixes rather than a
  targeted change), but — more importantly — confirmed this is *not a bug to fix at all*.**
  Checked ESTO's own raw flow list directly: ESTO has exactly one flat `15.02 Road` flow, with
  zero vehicle-type breakdown. NINTH, by contrast, reports ~15 distinct vehicle-type sub-sectors
  under road transport alone (`15_02_01_passenger/car`, `.../bus`, `.../sports_utility_vehicle`,
  `.../light_truck`, `15_02_02_freight/two_wheeler_freight`, `.../medium_truck`,
  `.../heavy_truck`, etc. — confirmed via the current failed-detail table, 33,122 of the 35,369
  rows are NINTH). **ESTO structurally cannot represent this level of detail; there is no
  "Common ESTO boundary" for these rows to anchor against because none should exist.**
  `no_anchorable_common_esto_boundary` is the validator working exactly as designed here — this
  is a genuine representation-granularity ceiling, not a resolver gap, a missing mapping, or
  anything actionable in this codebase. Recommend closing this out as "expected, not a bug" rather
  than carrying it forward as an open item; if finer ESTO-side transport detail is ever wanted,
  that's a much bigger, separate ask (see `docs/prompts/esto_extended_dataset_design.md`'s
  headline finding for the general shape of that kind of question, though transport-by-vehicle-
  type wasn't itself checked against ESTO's tree as part of that note).
- **`12_solar` allocation gap (~252 failures, ~2:1 ratio)**: down to **8 failures today**
  (~97% reduction), all NINTH, all tiny in magnitude (0.09-1.6 units), and all involving the same
  `14_industry_sector/14_03_manufacturing/14_03_11_nonspecified_industry` other-axis pairing
  already extensively documented as an instance of the mirror-row gap (see
  `docs/prompts/anchor_validator_fixes_findings_20260723.md`'s consolidated items 1/3/4 section
  and the 2026-07-23 design doc on flag propagation). **Not a new, distinct issue** — folding this
  into the already-tracked mirror-row-gap backlog rather than treating it as its own open item.

**Net result: 2 of these 4 items are fully resolved, 1 (transport) is confirmed to be correct,
expected behavior rather than a bug, and 1 (12_solar) has shrunk to a tiny residual that's the
same already-documented mirror-row pattern, not a new problem.** Nothing new to investigate from
this list — the only genuinely-open item across the whole 2026-07-22/23 anchor-validator thread at
this point is the mirror-row gap itself (deliberately deferred, design doc written, see the
2026-07-23 findings doc), and the separately-tracked `09 Total transformation sector` ESTO-side
gap (215 rows, see `docs/prompts/investigate_ninth_09_total_transformation_reconciliation.md`'s
own 2026-07-23 update — note that's a different validator, `common_esto_validation.csv`, not this
one).

## Test plan for the next session

1. Read this note and the tree-construction code
   (`build_dataset_tree_structure.py`'s ESTO flow-tree builder) before
   touching anything — confirm the `09.01`/`09.02` merged-code mechanism
   precisely, the same way `16.01`/`16.01.99` was confirmed before its fix
   (trace one concrete economy/year row end to end: raw tree children, raw
   source values, Common ESTO row components, actual comparison data).
2. Fix should very likely land in the tree builder, not
   `source_parent_anchor_validation.py` — this is a different file/subsystem
   than every fix in this session.
3. After fixing, rerun `pytest -q tests/test_structural_resolver.py
   tests/test_source_parent_anchor_validation.py` (36 passing baseline) plus
   whatever tree-builder tests exist, then a full Stage 3 rerun. Check
   specifically whether `09 Total transformation sector` (currently frozen at
   486) finally moves — if it doesn't, the merged-code theory is wrong and
   needs re-diagnosis, the same lesson learned twice this session already.
4. Add the missing log line in `run_stage_3`'s
   `except Exception: anchor_exclude_parents = set()` block before trusting
   any future "this fix had zero impact" result at face value.

## Follow-on session (2026-07-22, continued): the merged-code theory was wrong

Per the test plan above, the `09.01`/`09.02` merged-code mechanism was
confirmed precisely, a real bug was found and fixed in the tree builder for
it — **and it did not move `09 Total transformation sector`'s 486 failures at
all** (confirmed byte-for-byte identical status counts, 486 failed / 403
passed / 2513 skipped, running `validate_source_parent_anchors` directly
against real data with the old vs. new tree builder as an explicit A/B
control). The doc's own contingency in step 3 above was triggered: the
merged-code theory was the wrong target for `09`'s specific 486 failures,
even though the underlying tree bug it describes was real.

**The tree bug fixed this session (real, verified, kept):**
`build_esto_tree`'s flow tree spliced the *entire* `esto_rollup_rules`
hierarchy (`_load_rollup_hierarchy`) into the raw per-source ESTO tree,
including `EXPANDING`-mode rows like `09.01-09.02 Power sector`. That
family's declared children cross-cut two branches (`09.01 Main activity
producer`'s and `09.02 Autoproducers`' own plant-type leaves) that are each
independently real and additive on their own. Splicing it into the *raw*
tree reparented every one of those real leaves onto the merged/rollup nodes,
leaving `09.01`/`09.02` structurally childless in the raw ESTO tree — even
though their raw data and real children were completely intact, and even
though ESTO's own identity self-mapping never looks up the merged labels at
all (confirmed: they never appear as `component_esto_flow` for
`source_system == "ESTO"` in `common_esto_rows.csv`; they're only reached
via LEAP/NINTH's mapping). Fixed by tagging each rollup entry with its
`ROLLUP_MODE` in `_load_rollup_hierarchy` and adding
`_non_expanding_rollup_hierarchy()`, which the raw `build_esto_tree` flow
tree now filters through before splicing — `NON_EXPANDING`/`DETACHED` rows
(the real cross-branch reattribution cases, e.g. own-use gas/coal/oil plants
moved from flow `10` to flow `09`, which `exclude_parents` already
complements) still splice exactly as before; only `EXPANDING` rows are held
back from the raw tree. `build_common_esto_tree` is untouched and still
receives the full, unfiltered hierarchy — verified the Common ESTO tree
still has `09.01-09.02 Power sector` → merged nodes → real leaves intact,
which is where NINTH/LEAP's combined power-sector rows actually need to
resolve. New regression tests:
`test_non_expanding_rollup_hierarchy_drops_only_expanding_entries` and
`test_build_esto_tree_keeps_natural_children_under_an_expanding_rollup_branch`
in `tests/test_build_dataset_tree_structure.py`. Full suite (excluding four
pre-existing, unrelated collection errors caused by this worktree lacking
the sibling `leap_initialisation` repo, and two pre-existing failures —
`test_apply_partitioned_common_esto.py::test_chunked_cache_reuse_and_result_equivalence`
missing `pyarrow`, and
`test_parse_leap_balance_export.py::test_parse_leap_balance_dir_ignores_excel_lock_files`
— both confirmed present before this session's changes too, via
`git stash`): 237 passed.

**The real mechanism behind `09`'s 486 failures, found while tracing one
concrete row end to end** (economy `01_AUS`, year 2023, scope `esto_leap`,
product `01.02 Other bituminous coal`): `09 Total transformation sector`
itself has a real Common ESTO comparison row (`value = -566.185988`), but
**none of its ~13 declared children (`09.01`–`09.13`) have any
`common_esto_rows.csv` entry for that exact product at all** — not `09.01`,
not `09.02`, not `09.06`–`09.08`, not `09.12`/`09.13`. The same pattern
repeats for `06.01 Crude oil` (-527.4), `08.01 Natural gas` (-464.7), `17
Electricity` (984.9), `10 Hydro` (-56.8), `12.01 Photovoltaics` (-151.1),
`14 Wind` (-113.0), and about a dozen other flow-09/product combinations
just for this one economy/year — the frontier is empty (`frontier_row_count
= 0`) because **no mapping row exists at all** connecting any of `09`'s
children to these primary-energy-input/output products, not because the
tree can't reach real data. This is a **mapping-coverage gap in the
workbook** (missing `esto_flow`/`esto_product` mapping rows for `09.01`–
`09.13` against these products), not a code or tree-structure bug — no code
fix can close it. `missing_expected_children` also consistently flags
`09.13.01 Electrolysers` / `09.13.02 SMR wo CCS` / `09.13.03 SMR w CCS`
(hydrogen production) as missing regardless of product, suggesting that
whole flow branch has zero mapping coverage in `common_esto_rows.csv` yet,
even though the raw ESTO data already carries real `09.13.x` rows.

**Recommended next step, not done this session:** this needs mapping work
(new `esto_flow`/`esto_product` rows in the workbook covering `09.01`–
`09.13` against the primary coal/oil/gas/electricity/renewable products that
currently have zero coverage), not further anchor-validator or tree-builder
code changes. Verifying via one economy/year at a time (as done here) is
far cheaper than a full Stage 3 rerun and should be the default first step
before assuming any future "still unchanged" result implicates the code.
