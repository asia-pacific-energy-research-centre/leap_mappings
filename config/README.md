# `config/` — navigation guide

Most active files are directly under `config/`, but the tracked dataset
registries under `config/datasets/` and one historical archive CSV are
exceptions. `config/archive/` is otherwise a local write target for backups,
and `config/subtotal_labels/` is ignored legacy output.

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
| `outlook_mappings_single_axis.xlsx` | Human-maintained mapping contract and preliminary input to the separate-axis refresh. |
| `outlook_mappings_key_pairs_generated.xlsx` | Generated exact-pair evidence consumed by the refresh/compatibility build; never edit it. |
| `outlook_mappings_generation_manifest.json` | Hash/schema/provenance gate for the generated workbooks. |
| `outlook_mappings_master.xlsx` | Generated compatibility workbook read by Stages 1–3 and sibling initialisation consumers. |
| `master_config.xlsx` | Stage 1's fallback workbook (`FALLBACK_WORKBOOK_PATH`). |
| `mapping_issue_exception_sets.xlsx` | Reviewed QA exceptions read by current validation and focused maintenance workflows. Also the authority for "ignored, not modelled" sectors/fuels — see `docs/special_rules_and_design_decisions.md` MAP-011. |
| `source_branch_fallback_rules.csv` | Read during LEAP→ESTO conversion (`data_convert` stage). |
| `all_demand_aggregated_components.json` | Same conversion step. |
| `common_esto_label_overrides.csv` | Read in Stage 2 (`build_common_esto_structure.py`). |
| `datasets/*.csv` | Active dataset, scope, mapping-sheet, rollup-sheet, value-adapter, and diagnostic-adapter registries. |

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
| `source_mismatch_allowed` | Active | Reviewer-confirmed raw-source inconsistencies attached to source-anchor validation. These annotate evidence; they do not make a failed check pass or change its numerical result. Exact source identity is required; `economy`, `scenario`, and `year` may use `all`. |
| `source_mismatch_archive` | Archive | Provenance-only records of superseded, migrated, or insufficiently scoped source reviews. Never used for operational matching. |

The five legacy-only allowlists are not inputs to separate-axis generation or
the active Stages 1–3 pipeline. They remain because
`codebase/archive/outlook_mapping_maintenance_workflow.py`
can still be run for historical comparisons. Do not add new active exceptions to
those sheets; use the active diagnostic's current exception mechanism instead.

For ordinary exception sheets, `enabled = TRUE` activates a row and blank match
fields can broaden a match. `missing_common_map_ignored` also supports `*`
prefix matches. `source_mismatch_allowed` is deliberately stricter: it requires
an enabled, confirmed row with a unique ID, an exact source system/axis/parent/
opposite-axis context, and an exact `parent_value` apart from floating-point
serialization noise for economy-specific reviews. The `economy`, `scenario`,
and `year` fields may be set to the literal `all` when the same reviewed source
issue applies across that dimension. For `economy = all`, `parent_value` is
retained as APEC review evidence but is not a match key, because individual
economies do not equal the APEC aggregate. Do not use `all` in the source
identity fields or `parent_value`. A matching economy-specific review takes
precedence over an `economy = all` review; duplicates at the same specificity
remain invalid.

## `archive/`

Write-only backup target — every script that edits `outlook_mappings_master.xlsx` copies the
previous version here first (`ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)` then
`shutil.copy2(...)`). Not read by anything, not required to pre-exist, accumulates indefinitely
with no automatic pruning (see `docs/results_folder_cleanup_candidates.md`).

## Complete file disposition (audited 2026-08-02)

This inventory traces literal paths, registry-driven loaders, tests, and
sibling-repository consumers across `leap_mappings`, `leap_initialisation`, and
`leap_dashboard`. “Delete candidate” means no executable consumer was found;
it is a review marker, not authorization for an uncoordinated deletion.

| File | Disposition | Consumer or reason |
|---|---|---|
| `README.md` | Keep — documentation | This inventory and operating guidance. |
| `outlook_mappings_single_axis.xlsx` | Keep — editable authority | Preliminary source for separate-axis generation. |
| `outlook_mappings_key_pairs_generated.xlsx` | Keep — generated authority | Exact-pair evidence used by the refresh. |
| `outlook_mappings_generation_manifest.json` | Keep — generated gate | Hashes, schema, counts, and promotion provenance. |
| `outlook_mappings_master.xlsx` | Keep — generated compatibility | Stages 1–3 and initialisation loaders. |
| `mapping_issue_exception_sets.xlsx` | Keep — reviewed QA authority | Active validators and focused maintenance workflows. |
| `master_config.xlsx` | Keep — legacy fallback | Stage 1 fallback plus legacy readers; not an editing authority. |
| `all_demand_aggregated_components.json` | Keep — active | LEAP conversion/preflight and dashboard availability logic. |
| `source_branch_fallback_rules.csv` | Keep — active | LEAP source-branch preflight/conversion. |
| `common_esto_label_overrides.csv` | Keep — active | Stage 2 display-label construction. |
| `source_coverage_scopes.json` | Keep — standalone active | Source-coverage audit and candidate generation. |
| `inverted_conservation_target_aliases.json` | Keep — optional QA | Standalone inverted-conservation validation. |
| `inverted_conservation_target_variants.json` | Keep — optional QA | Standalone inverted-conservation validation. |
| `esto_external_definition_authority_working_set.xlsx` | Keep — human research authority | Required review evidence before accepting generated mapping candidates; not machine-loaded. |
| `datasets/dataset_registry.csv` | Keep — active registry | Dataset registration and orchestration. |
| `datasets/comparison_scopes.csv` | Keep — active registry | Comparison-scope construction. |
| `datasets/mapping_sheet_registry.csv` | Keep — active registry | Mapping-sheet routing. |
| `datasets/rollup_sheet_registry.csv` | Keep — active registry | Rollup-sheet routing. |
| `datasets/value_adapter_registry.csv` | Keep — active registry | Dataset value adapters. |
| `datasets/diagnostic_adapter_registry.csv` | Keep — active registry | Diagnostic adapter routing. |
| `datasets/README.md` | Keep — documentation | Registry schema and maintenance notes. |
| `outlook_mappings_master_combined_esto.xlsx` | Review, then delete | No executable consumer remains. Repoint the queued review prompt and deliberately recover any still-needed reviewed values first (MAPQ-026/027). |
| `leap_results_expected_sheets.json` | Delete candidate | The similarly named initialisation config is separate; no code resolves this mappings-repo copy. |
| `mapping_coverage_gaps.csv` | Delete candidate | Static review output with no executable reader. |
| `missing_zero_branch_mapping_candidates.xlsx` | Delete candidate | Static candidate output; the sibling scrapbook workflow writes elsewhere and does not read this copy. |
| `archive/common_esto_flow_tree_parents.csv` | Delete candidate | Tracked historical archive file with no executable reader. |
| `176BC200`, `6AC9DA10`, `E0E85740`, `E2F1A260` | Delete candidate | Office crash-recovery ZIP/workbook blobs, not project configuration. Add a narrow ignore rule after removal because new names can recur. |
| `subtotal_labels/subtotal_labels.csv` (ignored/local) | Delete candidate | Legacy output with no current executable reader. |
| `archive/*.xlsx` (ignored/local) | Keep with retention policy | Safety backups written before workbook edits; prune by an agreed age/count policy rather than a one-off purge. |

The master workbook itself has two sheet-level deletion candidates:
`other branches` and `deleted rows - might regret`. They have no executable
consumer in any of the three repositories. They remain in place until a
coordinated workbook-contract migration; see
`docs/guide_outlook_mappings_master.md`.

## Legacy

`master_config.xlsx` above is still required (Stage 1 fallback), but its main use is the
superseded refresh path — see `docs/workflow_inventory.md` for the full legacy-vs-live trace.

## Full detail

See `docs/repo_data_slimdown_plan.md` for the complete file-by-file breakdown (including which
files are safe to leave out entirely) and `docs/workflow_inventory.md` for which scripts read
which config files.
