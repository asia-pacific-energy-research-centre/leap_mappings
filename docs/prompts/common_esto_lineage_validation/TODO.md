# Common ESTO lineage — follow-up TODO

Companion to `PROMPT5_STATUS_AND_ISSUES.md`. Prompt 5 is not certifiable until
issue #1 (validator methodology) is decided — that item is tracked in the status
doc. The two items below are the ones flagged for follow-up.

## [low priority — verify] Transient disappearance of `results/common_esto/` outputs

During the 2026-07-03 session, `ls`/`find`/`stat` intermittently reported
`structural_artifacts/`, `diagnostics/`, and the 495 MB
`common_esto_comparison_data.csv` as missing, then present again.

**Current read: no data was actually lost.** `common_esto_comparison_data.csv`
still carries its original mtime (2026-07-02 18:05), i.e. it was never deleted or
rewritten — the "missing" readings were most likely transient I/O errors from an
antivirus/search-indexer lock on large files (repo is not under OneDrive).
`structural_artifacts/` was regenerated deterministically (2.4 s) and is present.

Quick checks if it recurs / to confirm nothing in-code clears the dir:
- [ ] Confirm no pipeline stage clears `results/common_esto/` at start. Leads found:
      - `codebase/mapping_tools/apply_common_esto_structure.py` — `save_outputs()`,
        `error_tagged_path()` (renames to `*_needs_mapping_review.csv` on QA error,
        line ~1182), and `legacy_filtered_path.unlink()` (line ~1230).
      - `codebase/run_mapping_pipeline.py` — Stage-3 orchestration writing
        `common_esto_comparison_data.csv` (line ~447).
- [ ] Check whether a test invokes any stage with the *default* (real) `results/`
      output dir instead of a tmp dir (would rewrite/replace real outputs during `pytest`).
- [ ] If it recurs, add a Defender exclusion for the repo `results/` dir and re-test.

## [known work] Wire Ninth and ESTO into the partitioned application

Prompt 3's partitioned apply (`apply_partitioned_common_esto.py` run block) only
prepares/consumes `raw_leap_results.csv`, which is **entirely economy `20_USA`**
(LEAP only). Prompts 4–5 require all three source systems across all economies.

- [ ] Add source caches + apply passes for Ninth
      (`ninth_results_converted_to_esto.csv`, ~330 MB, 21 economies) and ESTO
      (`esto_results_exact_rows.csv`), each with `default_source_system` set.
- [ ] Ensure `source_tree_path=all_dataset_trees.csv` is passed so source-parent
      lineage is populated for Ninth/ESTO (tree-consistent, unlike LEAP).
- [ ] Only after all three are applied can a real "full" scope run be attempted —
      and only once issue #1 (validator) is resolved, since full validation is
      currently ~26 s/partition and artifact-dominated.
