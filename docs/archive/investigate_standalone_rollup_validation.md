# Resume prompt: standalone inclusive rollup validation

> **Resolution (2026-07-21).** Implemented the step-3 design: named
> NON_EXPANDING/DETACHED rollup subtotals are excluded from the ordinary
> recursive Common ESTO validator (they are alternative views, never additive
> parents of their tree children), and a dedicated contributor-based rollup
> validator reconciles each inclusive rollup against its declared contributors
> with source-availability awareness. See commit
> `4042d5e codex: validate standalone inclusive rollups against contributors`.
>
> - `_common_esto_validation_children_map` / the recursive validators take
>   `exclude_parents`; Stage 3 orchestration and the Stage 0 tree workflow build
>   the excluded set from the workbook `ROLLUP_MODE` column.
> - New `validate_non_expanding_rollups` writes
>   `results/tree_structure/common_esto_rollup_validation.csv` (+ summary) with
>   statuses passed / failed / incomplete_contributors /
>   no_contributors_available.
> - `_diagnose_child_status` now lets presence in the final output win, so an
>   ordinary child that is a rollup input elsewhere (e.g. 09.07 under 09 Total)
>   is `present_in_final_output`, not a false `replaced_but_value_present`.
>
> Verified on real Stage-2 output: rollup-as-parent failures 0 (was ~3,300),
> total failed rows 13,666 -> 11,242, ESTO inclusive rollups reconcile to ~0
> error, and 614 genuine NINTH `09.07 (incl own use)` boundary mismatches are
> now surfaced by the rollup validator rather than buried in the recursive one.
>
> **Out of scope / still open:** the ~4,663 remaining `09 Total transformation
> sector` failures are a genuine NINTH transformation reconciliation gap (NINTH
> 09 Total does not equal the sum of its 09.xx children), unrelated to rollup
> boundaries. Left for a separate investigation.

You are continuing work in C:\Users\Work\github\leap_mappings on the Common ESTO mapping pipeline. Read the repository AGENTS.md files and docs/mappings_system.md before making changes. Start with:

    git status --short
    git log -5 --oneline

Treat existing uncommitted changes as user-owned unless you can identify them as part of this task. Do not reset, checkout, or broadly reformat the worktree. Use C:\Users\Work\miniconda3\python.exe for Python. Use apply_patch for source edits. Commit only files changed for this task, with a codex: commit message, after focused tests pass.

## Objective

The main double-counting problem has been fixed: synthetic inclusive rollup labels such as 09.07 Oil refineries (including own use) must not be inferred as ordinary children of 09 Total transformation sector merely because their labels begin with 09.07.

Continue making standalone inclusive rollups validate correctly, especially:

- 09.06 Gas processing plants (including own use)
- 09.06.02 Liquefaction/regasification plants (including own use)
- 09.07 Oil refineries (including own use)
- 09.08 Coal transformation (including own use)

Infer source-detail differences programmatically. Do not hard-code that NINTH lacks .01 Liquefaction and .02 Regasification as a special-case list unless a general mechanism is proven impossible.

## Current workbook state

The active workbook is:

C:\Users\Work\github\leap_mappings\config\outlook_mappings_master.xlsx

It was replaced on 2026-07-17 from:

C:\Users\Work\github\leap_mappings\config\outlook_mappings_master new.xlsx

The prior active workbook was archived as:

C:\Users\Work\github\leap_mappings\config\outlook_mappings_master_archive_20260717_164320.xlsx

The active workbook now contains new Buildings mappings. Do not overwrite it or alter workbook cell values unless the task explicitly requires a mapping decision.

Do not change the current inclusive rollups from NON_EXPANDING to DETACHED without evidence. DETACHED means an unrelated rollup boundary; these inclusive rows are intentionally derived from their contributors, so NON_EXPANDING is currently semantically appropriate.

Relevant rules include:

    10.01.11 Oil refineries -> 09.07 Oil refineries (including own use), NON_EXPANDING
    09.07 Oil refineries -> 09.07 Oil refineries (including own use), NON_EXPANDING
    10.01.03 Liquefaction/regasification plants -> 09.06.02 Liquefaction/regasification plants (including own use), NON_EXPANDING
    09.06.02 Liquefaction/regasification plants -> 09.06.02 Liquefaction/regasification plants (including own use), NON_EXPANDING
    09.08 Coal transformation -> 09.08 Coal transformation (including own use), DETACHED

The oil-refinery rules have blank parent_flow_label and child_flow_labels containing 10.01.11 Oil refineries. This is comparison-boundary metadata, not evidence that the inclusive label is a second child of 09 Total.

## Completed commits

- 662814f codex: validate Ninth mapped sector frontiers
  Raw NINTH sector validation now uses direct mapped sub2 frontier rows and skips parent checks when mapped child coverage is incomplete. Raw NINTH sector and fuel findings became 0.

- 448759a codex: preserve Ninth sector detail frontier
  NINTH conversion resolves mappings through the most-specific available hierarchy level (sub4 -> sub3 -> sub2 -> sub1), preventing unmapped detail rows from being relabelled as mapped subtotals and double-counted.

- ba89d78 codex: keep standalone rollups out of inferred tree
  build_dataset_tree_structure now permits a rollup with blank parent_flow_label if it has child_flow_labels. Standalone synthetic rolled labels are excluded from numeric-prefix parent inference. Regression tests cover the 09.07 base/inclusive case.

The corrected tree has ordinary 09.07 Oil refineries under 09 Total transformation sector, while 09.07 Oil refineries (including own use) is standalone with its contributor edge to 10.01.11 Oil refineries.

## Latest successful Stages 1–3 run

Log:

C:\Users\Work\github\leap_mappings\logs\codex_stages_1_3_20260717_tree_rollup.out.log

Key results:

- Raw NINTH sector validation findings: 0.
- Raw NINTH fuel validation findings: 0.
- Mapped-row aggregation coverage: 100% for ESTO, LEAP, and NINTH.
- NINTH Common ESTO flow failed validation rows: 13,666.
- 09 Total transformation sector: 7,159 failed rows.
- 09.07 Oil refineries (including own use): 614 difference rows; this is now isolated to standalone inclusive-boundary validation rather than duplicate membership under 09 Total.
- 09.06 Gas processing plants (including own use): 2,350 missing-expected-child rows.
- 09.06.02 Liquefaction/regasification plants (including own use): 3,824 validation rows, with the key issue concentrated in standalone inclusive-rollup validation.
- 14.03 Manufacturing: 159 missing-expected-child rows. Raw NINTH hierarchy validation is clean, so this is now a Common ESTO mapping/detail-frontier issue.

Important outputs:

- results/tree_structure/common_esto_validation.csv
- results/tree_structure/common_esto_source_frontier.csv
- results/tree_structure/common_esto_validation_child_detail.csv
- results/tree_structure/common_esto_validation_issue_patterns.csv
- results/tree_structure/common_esto_validation_rollup_diagnosis.csv
- results/common_esto/common_esto_comparison_data.csv
- results/common_esto/qa_common_esto_non_expanding_frontier_check.csv

## Unfinished code and warning

codebase/mapping_tools/common_esto_validation_orchestration.py contains an uncommitted source-frontier implementation. It initially inferred comparability from active source-to-ESTO mappings and added rollup aliases. That was too permissive and increased NINTH failures from 15,203 to 27,319 because overlapping base and replacement rows were counted together. After the standalone-tree fix, the full Stages 1–3 run produced 13,666 failed NINTH flow rows, but the frontier logic still needs careful review before it is considered complete.

Do not blindly commit or rewrite this frontier code. Distinguish:

1. the canonical Common ESTO structural tree;
2. a source-specific additive comparison frontier;
3. a synthetic rollup boundary validated separately against contributors;
4. a source-unavailable leaf excluded from a cross-source check.

## Recommended investigation

1. Inspect common_esto_tree.csv and confirm that enabled standalone rollup labels with blank parent_flow_label are not ordinary numeric-prefix children.

2. Inspect esto_rollup_rules, ninth_rollup_rules, and generated Common ESTO lineage and rollup QA outputs. Determine whether each inclusive rollup identifies its base contributor, own-use/loss contributor, ordinary structural parent, and standalone-boundary status.

3. Design a rollup-aware validation representation. It may add an explicit catalogue with:

    rollup_label
    rollup_mode
    structural_parent
    contributors
    ordinary_tree_membership
    source_frontier_role

The ordinary recursive validator must not count a standalone synthetic rollup as a sibling of its base contributor. A separate rollup validator or diagnostic should compare the synthetic value with declared contributors when those contributors are available.

4. For NINTH liquefaction/regasification, confirm:

- ESTO and LEAP .01 Liquefaction and .02 Regasification remain active and comparable.
- NINTH direct mappings to those leaves are disabled because NINTH does not report them.
- NINTH maps the broader 09.06.02 Liquefaction/regasification plants category.
- The inclusive own-use mapping remains available for cross-source comparison.
- Validation infers NINTH unavailability from actual mapped/emitted source coverage, rather than a hard-coded hierarchy-depth list.

5. Add focused tests for:

- base plus inclusive rollup not double-counted under the ordinary parent;
- standalone rollup validated separately against contributors;
- source-missing detail leaves classified as source_unavailable, not missing_expected_children;
- source having a broader rollup but not its leaves remaining comparable at the broader boundary;
- ordinary 09.07 remaining a child of 09 Total.

6. Run focused tests:

    C:\Users\Work\miniconda3\python.exe -m pytest tests/test_build_dataset_tree_structure.py tests/test_common_esto_validation_orchestration.py tests/test_non_expanding_rollups.py -q

7. Run Stages 1–3 before a full pipeline run:

    C:\Users\Work\miniconda3\python.exe codebase/run_mapping_pipeline.py --stages 1,2,3

The run is long. Launch it in the background with redirected logs, monitor at most once every 10 minutes, and do not kill it merely because output is quiet. Check the process, log tail, and final Pipeline complete. marker.

## Success criteria

Complete only when:

- standalone inclusive rows no longer appear as duplicate ordinary children;
- rollup boundaries validate using declared contributors and source availability;
- NINTH unavailable liquefaction/regasification leaves are not false missing-child failures;
- ordinary 09 Total and 09.07 validation remains stable or improves;
- diagnostics distinguish source-unavailable, rollup-replaced, structurally incomparable, and genuine value mismatch;
- focused tests pass;
- Stages 1–3 complete successfully;
- code changes are committed in a focused codex: commit.

Do not alter workbook rollup modes or add new mappings unless evidence shows the current configuration cannot express the intended comparison boundary.

