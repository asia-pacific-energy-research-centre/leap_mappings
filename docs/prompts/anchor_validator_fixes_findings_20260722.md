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

- `10 Losses & own use` / `10.01 Own Use` (ESTO flow): 196 / 191 failed —
  not investigated this session.
- `01 Coal`, `08 Gas`, `07 Petroleum products`, `15 Solid biomass` (ESTO
  product axis, `frontier_rows_absent`): 104/209/256/94 — likely the ESTO
  side of the same aggregate-fuel family the NINTH product-axis fix
  addressed; worth checking whether the same `literal_pairs`/`has_data_pairs`
  mechanisms apply to the ESTO product axis or whether this needs its own
  trace.
- The passenger-road resolver gap from the original stocktake (66,402 skipped
  `no_anchorable_common_esto_boundary` rows) was not touched this session.

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
