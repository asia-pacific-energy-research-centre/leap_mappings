# Investigate demand-sector parent/child mismatches (14 Industry, 14.03 Manufacturing, 15 Transport)

Repo: `C:\Users\Work\github\leap_mappings`. Read `AGENTS.md` first and follow repo conventions.

**Diagnose first, then fix if the cause is clear-cut; confirm with the user
before anything high-blast-radius.** The old report-only framing is lifted: once
the diagnosis is solid you may implement the fix, verify it, and commit it in a
focused `codex:` commit. But gate the following behind explicit user confirmation
rather than proceeding unilaterally:

- **Editing `config/outlook_mappings_master.xlsx`** (mapping rows or rollup
  rules). Mapping-boundary decisions are the user's call — propose the exact
  change and get a yes first. The workbook also carries unrelated in-progress
  edits; do not overwrite or reformat it.
- **Editing `config/mapping_issue_exception_sets.xlsx`** or creating the proposed
  `parent_child_mismatch_allowed` sheet — propose the rows, do not add them.
- **Any verdict that is `mixed` or ambiguous**, or a fix whose blast radius you
  cannot bound (e.g. a change to graph partitioning or the comparison-level for a
  whole sector that moves many other rows).

A clear, self-contained **code** fix (e.g. in the tree/child-map, the validator,
or the frontier) that is obviously correct and well-tested may proceed without
asking — that is the point of lifting report-only. When in doubt, ask; a wrong
mapping/boundary change is hard to unwind and distorts comparisons silently.

> **2026-07-21 refresh — this supersedes the stale baseline counts below.** After
> the standalone-rollup validation work landed (commit `4042d5e`), a fresh full
> Stages 1-3 run (`run_id common_esto_20260721T014101`) changed this cluster
> materially:
>
> - **LEAP flow validation now PASSES entirely** — the old baseline's LEAP
>   `14 Industry` (7,493) and LEAP `15 Transport` (1,299) failures are gone.
>   **Scope this task to NINTH only.**
> - **NINTH failures now (main recursive validator,
>   `results/tree_structure/common_esto_validation.csv`, `status == failed`):**
>
>   | parent_code | rows | gap vs parent (median) | Σ abs err | shape |
>   | --- | --- | --- | --- | --- |
>   | `15 Transport sector` | 1,878 | **100%** (all children absent) | **512,058** | wholesale-missing children |
>   | `14 Industry sector` | 941 | ~17% | 15,567 | partial; 90 rows are children-present-but-sum-off |
>   | `14.03 Manufacturing` | 159 | ~7% | 1,931 | granular sub-industries missing |
>   | `16 Other sector` | 47 | 100% | 651 | tiny |
>
> - **~96% of this cluster's error is `15 Transport sector` alone.** Do Transport
>   first and treat it as the primary deliverable; Industry is a secondary
>   partial-coverage question; 14.03 / 16 are a small exception-labelling sweep.
> - Transport's missing children are `15.02 Road`, `15.03 Rail`,
>   `15.04 Domestic navigation`, `15.05 Pipeline transport`, `15.06 Non-specified
>   transport` — **all of them, in every failing row** (median gap = 100% of
>   parent).
>
>   **Do NOT read this as source-unavailability / a frontier gap.** The 9th
>   Outlook carries the *finest* transport detail of any of the three datasets:
>   `15 Transport` splits into `15_01_domestic_air_transport`, `15_02_road`,
>   `15_03_rail`, `15_04_domestic_navigation`, `15_05_pipeline_transport`,
>   `15_06_nonspecified_transport`, and each of those splits further down to the
>   5th level. So the NINTH children **exist in the source** — they are simply not
>   reaching `common_esto_comparison_data.csv` under the ESTO-shaped labels
>   (`15.02 Road`, …) that the tree's child list expects. This is a
>   mapping / partition-label / comparison-level problem, not missing source data,
>   and it will **not** be fixed by marking anything `source_unavailable`.
>
>   The decisive first question: **where do NINTH's detailed transport leaf values
>   actually land in the comparison data?** Trace `15_02_road` (and siblings)
>   through `ninth_pairs_to_esto_pairs` and
>   `results/mapping_relationships/energy_balance_relationships.csv` to their ESTO
>   target, then find that value in `common_esto_comparison_data.csv` for NINTH and
>   read its `common_flow_label`. Likely findings: (a) the leaves are mapped but
>   graph partitioning merged them into a coarser generated common label (because
>   LEAP/ESTO support only a coarser transport level), so the exact `15.02 Road`
>   string the validator looks for never appears; (b) a mapping gap where some
>   `15_0x` NINTH sectors have no ESTO `15.0x` target; or (c) the comparison level
>   for transport is genuinely coarser than `15.0x` and the tree/child-map should
>   not be asserting those leaves as reconcilable children. Distinguish these
>   before proposing any verdict or exception row.
> - `14 Industry` misses `14.03 Manufacturing`, `14.01 Mining and quarrying`,
>   `14.02 Construction` (~17% short). `14.03 Manufacturing` misses granular
>   sub-industries (`14.03.09 Wood`, `14.03.10 Textiles`, `14.03.11 Non-specified`,
>   `14.03.07 Food/beverages/tobacco`, `14.03.02 Chemical`, …) — the classic
>   detail-frontier / unmodelled-by-design shape → likely exception candidates.
>
> The `09.x` transformation failures are handled separately in
> `investigate_ninth_09_total_transformation_reconciliation.md` — still out of
> scope here.

## Background

Stage 3 of `codebase/run_mapping_pipeline.py` runs an internal Common ESTO parent/child
consistency check (`_validate_common_esto_axis_recursive_sums` in
`codebase/mapping_tools/build_dataset_tree_structure.py`): for each parent node in the flow
hierarchy, per scope/source_system/economy/scenario/year/product, the sum of child rows in
`results/common_esto/common_esto_comparison_data.csv` must equal the parent row within 1%.
Detail output: `results/tree_structure/common_esto_validation.csv`.

On 2026-07-09 the check was changed so that **only a numeric disagreement fails**; a child label
absent from the comparison data while sums still agree now passes with reason
`missing_children_within_tolerance`. The failures that remain in the demand sectors have missing
children AND sums that genuinely disagree (reason `missing_expected_children`, children_sum short
of parent_value).

A frozen pre-fix baseline is saved at
`results/tree_structure/common_esto_validation_baseline_20260708.csv` (same schema). If a fresh
pipeline run has completed since, prefer the current `common_esto_validation.csv`; otherwise use
the baseline and apply the numeric-only failure rule yourself
(`abs_error > 0.01 * max(abs(parent_value), 1)`).

Real-failure counts from the 2026-07-08 baseline, after applying the numeric-only rule
(validation_axis = flow):

| parent_code | source_system | failed checks |
|---|---|---|
| 14 Industry sector | LEAP | 7,493 |
| 14.03 Manufacturing | NINTH | 4,608 |
| 15 Transport sector | NINTH | 1,920 |
| 15 Transport sector | LEAP | 1,299 |
| 14 Industry sector | NINTH | 996 |

These are believed to be pre-existing (unrelated to the 2026-07-09 own-use rollup work). The
question to answer: **are these gaps "subsectors we deliberately do not model" (→ candidates for
an exception), or a mapping/coverage bug (→ needs fixing)?**

## Method

Work one concrete case end-to-end before generalising. Suggested: `14.03 Manufacturing` /
NINTH / one economy (e.g. USA), one mid-range year, one product with a large absolute difference.

1. From the validation detail, list for that case: `missing_expected_children`, `parent_value`,
   `children_sum`, `difference`, and which children ARE present (compare the tree's child list —
   `_common_esto_validation_children_map` — against `common_flow_label` values in the comparison
   data for that scope).
2. For each missing child, check whether it carries nonzero energy in the source balances:
   - NINTH: the converted NINTH dataset used by the pipeline (see Stage `data_convert` outputs).
   - LEAP: the exported LEAP results CSV.
   - ESTO: the ESTO balance CSV.
   If a missing child is ~zero in the source, the gap is cosmetic. If it is materially nonzero,
   determine why it never reaches the comparison data:
   - not present in any mapping sheet in `config/outlook_mappings_master.xlsx` (→ unmodelled by
     choice or by omission — check `results/mapping_relationships/energy_balance_relationships.csv`
     and the QA outputs under `results/mapping_relationships/qa/`), or
   - mapped but excluded (`include_in_use_case` false, coverage exclusions, or dropped in Stage 2 —
     check `results/common_esto/qa_common_esto_components_missing_from_structure.csv` and
     `qa_common_esto_excluded_components.csv`).
3. Quantify materiality per parent: what share of `parent_value` does the unexplained gap
   represent (median and worst case across economies/years)? A systematic ~x% shortfall points to
   a missing subsector; noisy signs point to double counting or misassignment.
4. Repeat the classification (steps 1–3, abbreviated) for `14 Industry sector`/LEAP and
   `15 Transport sector`/NINTH+LEAP — these may have different causes; do not assume 14.03's
   explanation transfers.

## Deliverable

Still produce the written report first (markdown, save to `docs/prompts/` alongside this file with
suffix `_FINDINGS.md`) — it is the evidence trail whether or not you go on to fix. Per parent ×
source_system:

1. Verdict: `unmodelled-by-design` / `mapping-bug` / `comparison-level` / `mixed` / `cosmetic-zero`,
   with the evidence (one worked example each, with numbers).
2. The exact child flows responsible for the bulk of the difference, and their share of it.
3. For every `unmodelled-by-design` verdict: proposed exception rows for a future
   `parent_child_mismatch_allowed` sheet in `config/mapping_issue_exception_sets.xlsx`, in this
   format (the sheet does not exist yet — propose rows only, do not create it):
   `enabled | axis | parent_code | source_system | description`
   Parent codes should be the narrowest prefix that covers the issue (e.g. a specific `14.03.xx`
   child family rather than all of `14.03` if only some subsectors are unmodelled).
4. For every `mapping-bug` / `comparison-level` verdict: which mapping sheet/row family or which
   piece of code (tree/child-map, validator, frontier, partitioning) is wrong or missing, and what
   the fix is.

**Then act on the report:**

- Where the fix is a clear, self-contained **code** change (per the top-of-file rule), implement
  it, add/extend focused tests, run them, verify against a fresh pipeline run, and commit it.
- Where the fix needs the **mapping workbook** or the **exception sheet**, or the verdict is
  `mixed`/ambiguous, present the proposed change and **ask the user to confirm before applying**.
- Keep the `_FINDINGS.md` report and the fix in view together so the reasoning behind the change is
  auditable.

## Known pitfalls

- Several results CSVs are large; read with `chunksize` or `usecols` where practical.
- `results/logs/mapping_pipeline.log` buffers heavily; ignore it for this task.
- A long-running `supply_reconciliation_workflow.py` python process may exist; it is unrelated —
  leave it alone.
- `config/E0E85740` and `config/~$outlook_mappings_master.xlsx` are Excel artifacts; ignore.
- The `09.x` transformation-sector failures visible in the same validation files are a separate,
  known issue tied to the own-use rollup restructure — **out of scope here**; do not analyse or
  "fix" them.

## Scope boundaries

- **Confirm before editing** `config/outlook_mappings_master.xlsx` or
  `config/mapping_issue_exception_sets.xlsx` (see top-of-file rule). Never overwrite or reformat
  the workbook; it carries unrelated in-progress edits.
- Implementing the `parent_child_mismatch_allowed` sheet or its validator hook is a larger piece —
  propose it and confirm scope before building it.
- **Re-running the full pipeline is now allowed** to verify a fix, but only one
  `run_mapping_pipeline.py` at a time (concurrent runs clobber `results/`); launch it in the
  background with redirected logs and check for the `Pipeline complete.` marker. If the comparison
  data is stale relative to the code and you are only diagnosing, say so rather than rerunning.
- Do not touch the recursive-validator rollup exclusion / rollup validator from `4042d5e`, or the
  `09.x` transformation cluster (that is
  `investigate_ninth_09_total_transformation_reconciliation.md`).

## Next job after this

Once Transport (and the rest of this cluster) is diagnosed and its fix decided,
the planned follow-on is the **source-parent anchor validation methodology (4a)**:
`docs/prompts/investigate_anchor_validation_methodology.md`. That task depends on
this one — the comparison-level pattern Transport establishes (where a source's
detailed leaves land in the comparison data, and at what level the three datasets
are genuinely comparable) is the design input for reworking the anchor validator.
Do not start 4a before this is done.
