# Resume prompt: source-parent anchor validation methodology (4a)

You are working in C:\Users\Work\github\leap_mappings on the Common ESTO mapping
pipeline. Read the repository AGENTS.md files and docs/mappings_system.md before
making changes. Start with `git status --short` and `git log -5 --oneline`. Use
C:\Users\Work\miniconda3\python.exe for Python. Use apply_patch for source edits.
Commit only files changed for this task, with a `codex:` commit message, after
focused tests pass. Treat existing uncommitted changes as user-owned unless you
can identify them as part of this task.

## Sequencing — do NOT start this before the Transport work

This is the **follow-on job after the demand-sector / Transport investigation**
(`docs/prompts/investigate_demand_sector_parent_child_mismatches.md`). Do that
first. Transport answers, in miniature, the exact question this task needs
answered at scale: *where do a source's detailed leaf values actually land in the
Common ESTO comparison data, and at what level are the three datasets genuinely
comparable?* The comparison-level pattern Transport establishes is the design
input for the fix here. Starting this cold, before Transport, means re-deriving
that pattern from scratch.

## What this is about

Stage 3 runs a **source-parent anchor validation**
(`codebase/mapping_tools/source_parent_anchor_validation.py`,
`validate_source_parent_anchors`) that reconciles each raw source parent total
against the Common ESTO additive frontier it should equal. It is a separate,
much larger check than the internal recursive Common ESTO parent/child validator
(the one fixed in `4042d5e`): ~794k detail rows, ~185s, driven off
`results/common_esto/common_esto_comparison_data.csv` and the raw source inputs.

It reports large failure counts. From the 2026-07-21 run
(`run_id common_esto_20260721T014101`,
`results/tree_structure/source_parent_anchor_validation_summary.csv`), flow axis,
scope `esto_leap_ninth`:

- NINTH: 57,272 failed / 388,548 eligible (~14.7%)
- ESTO: 4,945 failed / 9,492 eligible (6,594 skipped)
- LEAP: 2,381 failed / 10,962 eligible

Product axis NINTH: 33,201 failed / 319,128 eligible.

## Do not inherit a stale premise — re-diagnose first

An earlier write-up
(`docs/archive/common_esto_lineage_validation/PROMPT5_STATUS_AND_ISSUES.md`,
2026-07-03) concluded these failures were a **validator artifact**, not corrupted
data: (1) tree-vocabulary node codes never appear as source flows, so children
are never found; (2) a parent × every-product Cartesian explosion manufactures
false negatives; and it measured the actual human-facing coverage at **89.2%**.
Its recommended fix was to reconcile against the existing conversion outputs
(`leap/ninth/esto_results_converted_to_esto.csv`) rather than tree-walking.

**But that doc describes an older module (`validate_lineage_anchors.py` /
`validate_partition_lineage`).** The current
`source_parent_anchor_validation.py` has since evolved: it resolves each source
row to its **nearest mapped pair** (`structural_resolver.resolve_nearest_mapped_pair`)
and applies an **exceptions mask** (`mapping_issue_exceptions.unmodelled_source_pair_mask`).
So the specific artifact mechanism may be partly addressed already, and the
current 57k/5k failures may have a different character.

**Therefore task 1 is a fresh diagnosis, not an assumed rework.** Do the residual
decomposition (below) on the *current* output before deciding anything. Confirm
whether the remaining failures are still methodology artifacts, now contain
genuine signal, or are a mix — quantify the split. Report a stale-premise finding
explicitly if the old diagnosis no longer holds.

## The likely fix direction (the user's stated preference: the "proper" fix)

If diagnosis confirms the failures are still substantially methodological, the
chosen direction is the **proper** fix, not a cosmetic reclassification:
reconcile source parent totals against the conversion outputs / the real
comparison frontier, at the comparison level the datasets actually share.

Strong reuse candidate: the recursive validator now builds a
**`source_frontier`** (`build_source_comparison_frontier` in
`codebase/mapping_tools/common_esto_validation_orchestration.py`, written to
`results/tree_structure/common_esto_source_frontier.csv`) that already encodes
per-source comparable children from actual mapped/emitted coverage — the same
"reconcile against real coverage" idea PROMPT5 asked for. Assess whether the
anchor validator can consume or share that frontier instead of re-deriving
frontiers itself. Do not duplicate the frontier logic in a second place; share it.

Fallback tier if the proper fix proves too large in one pass: at minimum
reclassify tree-vocabulary and cross-product-Cartesian cases as `unanchorable`
rather than `failed`, so the output is honest. Prefer the proper fix; record why
if you fall back.

## Genuine (non-artifact) residue to check — may have changed since 2026-07-03

- **~27 ambiguous rollup assignments** (`qa_ambiguous_structural.csv`): source
  nodes that could roll into two aggregate parents (e.g. `Gas works plants` →
  {Gas processing plants, Total transformation}; `Freight road`/`Passenger road`
  → {Road, Transport, Total final consumption}). These need **human rollup
  decisions** and are real regardless of the validator rework.
- **~14 `component_missing_common_row`** (`qa_unresolved_structural.csv`): all
  concerned `06.04 Additives/oxygenates` / `06_x_other_hydrocarbons` lacking a
  common row — a small specific structural gap.

Re-generate/re-read these and confirm the counts still stand before surfacing
them for decisions.

## Method (residual decomposition, mirror the Transport approach)

1. Pick one high-failure case: source NINTH, one economy, one mid-range year, one
   parent flow with a large `abs_error` in
   `results/tree_structure/source_parent_anchor_validation.csv` (or the `_SLICE`
   file). List `parent_value`, `frontier_sum`, `difference`,
   `missing_expected_children`, `frontier_row_count`.
2. Determine why the frontier falls short: is the "missing" child a
   tree-vocabulary label that never appears as a source flow (artifact), a real
   nonzero source value that never reaches the comparison data (mapping/coverage),
   or a value that reached the data under a coarser partition label (comparison
   level)? Use `energy_balance_relationships.csv`,
   `common_esto_source_frontier.csv`, and `common_esto_comparison_data.csv`.
3. Quantify the split of the 57k NINTH / ~5k ESTO failures across those causes.
4. Decide: proper fix (share the frontier / reconcile against conversion outputs),
   minimal reclassification (`unanchorable`), or a mix — with numbers.

## Focused tests and run

    C:\Users\Work\miniconda3\python.exe -m pytest tests/test_build_dataset_tree_structure.py tests/test_common_esto_validation_orchestration.py -q

Any anchor-validator-specific tests should be run too (search
`tests/` for `anchor`). Then, once no other pipeline run is active:

    C:\Users\Work\miniconda3\python.exe codebase/run_mapping_pipeline.py --stages 1,2,3

The run is long (~24 min for Stage 3 alone). Launch it in the background with
redirected logs, monitor at most once every 10 minutes, and do not kill it for
quiet output (stdout is buffered). Check the process, log tail, and final
`Pipeline complete.` marker. Only one pipeline run at a time — concurrent runs
clobber `results/`.

## Success criteria

- A fresh, quantified diagnosis of the current anchor failures (artifact vs
  genuine vs mixed), explicitly stating whether the 2026-07-03 premise still
  holds.
- If methodological: the proper fix applied, ideally sharing `source_frontier`
  rather than re-deriving frontiers, with anchor failure counts falling for the
  right reason (not by loosening tolerance) and the recursive-validator behaviour
  from `4042d5e` untouched.
- The genuine residue (ambiguous rollups, `06.04` common-row gap) surfaced with
  current counts for human decision.
- Focused tests pass; Stages 1-3 completes; changes committed in a focused
  `codex:` commit.

## Do not

- Do not start before the Transport diagnosis is done (see Sequencing).
- Do not loosen tolerances to make failures disappear.
- Do not duplicate `source_frontier` logic in a second location.
- Do not touch the recursive-validator rollup exclusion / rollup validator from
  `4042d5e`; this is a different check.
