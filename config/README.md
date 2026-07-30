# `config/` — navigation guide

Only files directly under `config/` are git-tracked (see `.gitignore`: `!config/*` then
`config/*/`, which re-ignores every subfolder). Subfolders like `config/archive/` exist locally
but are never committed — they're either write targets (backups) or local scratch.

## How the configuration files fit together

The mapping workbooks and the exception workbook have different jobs:

1. `outlook_mappings_single_axis.xlsx` is the editable mapping authority. Maintain
   the independent sector/flow and fuel/product relationships and the editable
   rollup rules there.
2. `outlook_mappings_master.xlsx` is the compatibility/output workbook. Its pair
   sheets and generated rollup copies are rebuilt from the single-axis workbook;
   do not edit those generated sheets directly. The remaining display/reference
   sheets are currently preserved during generation as documented in
   `docs/mappings_system.md`.
3. `mapping_issue_exception_sets.xlsx` is a reviewed QA decision layer. It does
   not add, remove, or alter a mapping. It tells a named diagnostic how to label
   or set aside a reviewed finding. Workflows may read it, but must not update it
   automatically.
4. Source data under `data/` and the generated mapping/QA results under
   `results/` are evidence and outputs, not substitutes for either workbook.

When a source pair is missing or wrong, fix the relevant mapping workbook (or
rollup rule) first. Use an exception sheet only when the relationship or source
condition is intentionally acceptable and has been reviewed. Exceptions do not
override mapping semantics and should not be used to hide an unresolved mapping
gap.

## Required to run the active pipeline

| File | Used by |
|---|---|
| `outlook_mappings_master.xlsx` | The core editable mapping workbook — read by Stage 0, Stage 1, Stage 3, and most `mapping_tools/*` scripts. |
| `master_config.xlsx` | Stage 1's fallback workbook (`FALLBACK_WORKBOOK_PATH`). |
| `mapping_issue_exception_sets.xlsx` | Reviewed QA exceptions, read by Stage 0 and several `mapping_tools/*` scripts. Also the authority for "ignored, not modelled" sectors/fuels — see `docs/special_rules_and_design_decisions.md` MAP-011. |
| `source_branch_fallback_rules.csv` | Read during LEAP→ESTO conversion (`data_convert` stage). |
| `all_demand_aggregated_components.json` | Same conversion step. |
| `common_esto_label_overrides.csv` | Read in Stage 2 (`build_common_esto_structure.py`). |

`master_config.xlsx` is a legacy fallback still read by Stage 1 when the active
mapping workbook does not supply a value. `config/leap_mappings.xlsx` is a legacy
reference and is not part of the active mapping-maintenance workflow unless a
task explicitly requests it.

## Exception workbook sheet inventory

The workbook currently contains the following sheets. “Active” means that an
active workflow in this repository reads the sheet. “Legacy-only” means it is
retained for the archived maintenance workflow and should not be populated for
new active-pipeline findings. “History” means it is provenance, not an operational
allowlist.

| Sheet | Status | Used for |
| --- | --- | --- |
| `many_to_many_allowed` | Legacy-only | Archived mapping-maintenance many-to-many review. |
| `crosswalk_allowed` | Legacy-only | Archived LEAP/9th-to-ESTO crosswalk conflict review. |
| `subtotal_mismatch_allowed` | Active | Reviewed cross-dataset subtotal mismatch findings. |
| `missing_common_map_ignored` | Active | ESTO flows intentionally excluded from missing-common-map checks. |
| `subtotal_label_exceptions` | Active | Older subtotal-label inference exceptions, still consumed by subtotal review workflows. |
| `leap_source_presence_allowed` | Legacy-only | Archived LEAP source-presence conflict review. |
| `display_names_exceptions` | Active | Exact LEAP display-name cases excluded from display-name QA. |
| `leap_dup_source_allowed` | Active | Reviewed duplicate LEAP source-pair findings in energy-balance relationship QA. |
| `leap_dup_target_allowed` | Active | Reviewed duplicate LEAP target-pair findings in energy-balance relationship QA. |
| `unmapped_esto_nonzero_allowed` | Legacy-only | Archived non-zero unmapped ESTO-pair review. |
| `unmapped_ninth_nonzero_allowed` | Legacy-only | Archived non-zero unmapped 9th-pair review. |
| `subtotal_label_overrides` | Active | Exact subtotal truth overrides used by subtotal contract/review workflows. |
| `unmodelled_source_ignored` | Active | The shared authority for source sectors/fuels intentionally outside the model. |
| `source_mismatch_allowed` | Active | Exact, reviewer-confirmed raw-source inconsistencies attached to source-anchor validation. These annotate evidence; they do not make a failed check pass or change its numerical result. |
| `source_mismatch_history` | History | Preserved legacy source-review records; never used for operational matching. |

The five legacy-only allowlists are not inputs to the active Stage 0–3 mapping
pipeline. They remain because `codebase/archive/outlook_mapping_maintenance_workflow.py`
can still be run for historical comparisons. Do not add new active exceptions to
those sheets; use the active diagnostic's current exception mechanism instead.

For ordinary exception sheets, `enabled = TRUE` activates a row and blank match
fields can broaden a match. `missing_common_map_ignored` also supports `*`
prefix matches. `source_mismatch_allowed` is deliberately stricter: it requires
an enabled, confirmed row with a unique ID and an exact economy, scenario, year,
axis, parent, opposite-axis context, and parent value. New source exceptions must
therefore be copied from an exact reviewed candidate, not written as a broad
wildcard.

## `archive/`

Write-only backup target — every script that edits `outlook_mappings_master.xlsx` copies the
previous version here first (`ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)` then
`shutil.copy2(...)`). Not read by anything, not required to pre-exist, accumulates indefinitely
with no automatic pruning (see `docs/results_folder_cleanup_candidates.md`).

## Files present but not required by the pipeline (verified 2026-07-28)

- Extensionless eight-character hexadecimal files such as `config/176BC200`,
  `config/7EB36010`, `config/9098DA00`, and `config/FDC59700` are Excel
  lock/crash-recovery artifacts with workbook-like binary content. The exact
  filenames change as Excel creates new recovery files.
  `docs/guide_outlook_mappings_master.md` documents these as safe to ignore.
- `outlook_mappings_master todo.xlsx` is an untracked review workbook, not an
  active pipeline input. Preserve it until its owner decides how to integrate
  or retire it.
- `leap_results_expected_sheets.json` is a review/configuration inventory used
  by current mapping planning and documentation, but not loaded by the main
  Stage 0–3 orchestrator. `mapping_coverage_gaps.csv` and
  `missing_zero_branch_mapping_candidates.xlsx` are review artifacts, not
  required main-pipeline inputs.
- `inverted_conservation_target_aliases.json`, `inverted_conservation_target_variants.json` —
  used only by `inverted_conservation_validation.py`, a standalone QA script not imported by
  `run_mapping_pipeline.py`. Needed only if you run that check specifically.

## Legacy

`master_config.xlsx` above is still required (Stage 1 fallback), but its main use is the
superseded refresh path — see `docs/workflow_inventory.md` for the full legacy-vs-live trace.

## Full detail

See `docs/repo_data_slimdown_plan.md` for the complete file-by-file breakdown (including which
files are safe to leave out entirely) and `docs/workflow_inventory.md` for which scripts read
which config files.
