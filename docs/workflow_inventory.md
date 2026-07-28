# Workflow Inventory — `codebase/` navigation guide

Last reviewed: 2026-07-28

`codebase/` mixes several things that look similar at a glance but aren't: the live mapping
pipeline, standalone maintenance/QA tools a researcher runs by hand, an explicitly-legacy
refresh workflow, a cluster of dashboard-prototype code that (per `AGENTS.md`) doesn't belong
in this repo at all, and at least one script that is currently broken. This guide tells you
which bucket each file is in, based on tracing imports and call sites (not just filenames), so
you don't have to read all of it to find the one script you need.

## Start here

`codebase/run_mapping_pipeline.py` is the only script you need to run the whole pipeline
end to end (`python codebase/run_mapping_pipeline.py`). Everything under "Live pipeline" below
is reached from it.

## Live pipeline (canonical — called by `run_mapping_pipeline.py`)

| Script | Stage |
|---|---|
| `codebase/run_mapping_pipeline.py` | Orchestrator |
| `codebase/archive/outlook_mapping_maintenance_workflow.py` | Stage 0 — maintenance/QA on the mapping workbook |
| `codebase/mapping_tools/build_energy_balance_relationships.py` | Stage 1 |
| `codebase/mapping_tools/build_common_esto_structure.py` | Stage 2 |
| `codebase/mapping_tools/parse_leap_balance_export.py` | `leap_parse` |
| `codebase/mapping_tools/convert_leap_results_to_esto.py`, `apply_ninth_to_esto_conversion.py` | `data_convert` |
| `codebase/mapping_tools/apply_common_esto_structure.py`, `build_dataset_tree_structure.py`, `common_esto_validation_orchestration.py`, `source_parent_anchor_validation.py` | Stage 3 |
| `codebase/mapping_tools/source_branch_preflight.py` | invoked from the `data_convert` LEAP conversion step |
| `codebase/mapping_tools/build_missing_mapped_esto_rows.py` | invoked from Stage 0 |
| `codebase/mapping_tools/non_expanding_rollups.py` | invoked directly from `run_mapping_pipeline.py`'s ESTO-exact-rows step |
| `codebase/mapping_tools/result_storage.py` | resolves compressed `.csv.gz` inputs/outputs for the live pipeline |
| `codebase/mapping_tools/common_esto_output_contract.py` | publishes and certifies the versioned Common ESTO contract used by Stage 3/dashboard consumers |
| `codebase/mapping_tools/mapping_issue_exceptions.py`, `codebase/mapping_issue_exceptions.py` | shared library, read by Stage 0 and several other tools (note: two similarly-named files — the one under `mapping_tools/` re-exports from the top-level one) |
| `codebase/utilities/outlook_mappings_filters.py`, `codebase/utilities/leap_balance_export_resolver.py` | the only two `utilities/` modules the live pipeline actually imports |

See `results/README.md` and its subfolder READMEs for what each stage writes.

## Standalone maintenance / QA tools

Run manually by a researcher — not invoked by `run_mapping_pipeline.py`, but part of the normal
mapping-maintenance workflow (several read/write `config/outlook_mappings_master.xlsx`
directly, backing up to `config/archive/` first):

`apply_display_name_updates.py`, `apply_duplicate_mapping_removal.py`,
`apply_subtotal_mismatch_review.py`, `apply_subtotal_mismatch_source_flip.py`,
`apply_subtotal_updates.py`, `infer_subtotal_labels.py`, `build_subtotal_mismatch_review.py`,
`inverted_conservation_validation.py`, `reconcile_anchor_validation.py`,
`compile_structural_mapping_artifacts.py`, `apply_partitioned_common_esto.py`,
`check_leap_to_esto_conversion_coverage.py`, `build_no_data_mapping_rows.py`,
`update_leap_display_names.py` — all under `codebase/mapping_tools/`.

Helper modules used only by the above (not by the live pipeline): `mapping_candidate_generation.py`,
`source_rollups.py`, `structural_resolver.py`, `target_share_allocation.py`.

Three more standalone, read-mostly mapping-candidate tools under `codebase/mapping_tools/`, none
imported by `run_mapping_pipeline.py`:

- `audit_nonzero_mapping_evidence.py` — read-only, notebook-safe audit checking whether proposed
  9th-source/ESTO-target pairs actually occur with non-zero values in current reference data.
  Does not edit the workbook.
- `build_leap_mapping_candidates.py` — builds copy-ready LEAP-to-9th mapping rows for verified
  candidates; writes `results/mapping_relationships/proposed_leap_combined_ninth_rows.csv`.
- `build_valid_nonzero_mapping_candidates.py` — builds copy-ready mapping rows only after the
  non-zero evidence audit above passes both axes; imports from `audit_nonzero_mapping_evidence.py`.
  This is the source of `results/mapping_relationships/proposed_ninth_pairs_to_esto_pairs_coal_products.csv`,
  which is committed to git (an exception to the "results/ is fully regenerated output" framing
  used elsewhere in this doc set — this particular file was deliberately checked in as a
  copy-ready candidate list, not left as gitignored transient output).
- `source_coverage_audit.py` and `build_source_coverage_mapping_candidates.py`
  — source-first coverage inventory and review-only candidate generation using
  `config/source_coverage_scopes.json`.
- `verify_ninth_mirror_row_candidates.py` — verifies paused NINTH
  source-mismatch candidates against raw source rows; use with the active
  mirror-row-gap handoff rather than as an automatic exception writer.
- `esto_extended_delta.py` — exact ESTO Extended delta/reconstruction support.
  The module is committed, but integration into the main orchestrator remains
  active in a separate worktree; do not classify it as a live Stage 0–3 path
  until that work is integrated and verified.

Top-level standalone workflows: `codebase/propagate_esto_rows_workflow.py`,
`codebase/for_colleagues_export_workflow.py` (see `results/for_colleagues/README.md`),
`codebase/regen_common_esto_comparison_fast_path_workflow.py` (fast-path rerun from cached
intermediates, skips Stages 0–2).

`codebase/functions/ninth_projection_mapping.py` is a helper used only by `build_no_data_mapping_rows.py`
and the dashboard-prototype cluster below — not by the live pipeline.

## Dashboard-prototype code — not this repo's job

`AGENTS.md` is explicit: *"Do not use this repo for LEAP dashboard implementation or dashboard
template edits. Use `C:\Users\Work\github\leap_dashboard` for LEAP dashboard work."* The
following modules build dashboard graph indices / comparison engines that duplicate what
`leap_dashboard` should own. None of them are imported by the live pipeline:

- `codebase/utilities/leap_results_dashboard_v2/` — an 11-module subpackage (`atomic_engine.py`,
  `comparison_engine.py`, `config_loader.py`, `derived_transformation_metrics.py`,
  `diagnostics.py`, `leap_loader.py`, `mapping_engine.py`, `models.py`, `output_writer.py`,
  `pathing.py`, `reference_loader.py`, `shadow_compare.py`).
- `codebase/utilities/leap_results_dashboard_balance.py`, `leap_results_dashboard_utils.py`
- `codebase/utilities/ninth_to_esto_mapping_coverage.py` — currently broken, see below.
- `codebase/utilities/energy_balance_template_extractor.py` (~1800 lines; used only by the
  legacy/dashboard cluster below, not by anything live)
- `codebase/utilities/workflow_outputs.py` — shared output-path helper used only by
  `energy_balance_template_extractor.py` and `ninth_to_esto_mapping_coverage.py` above.
- `codebase/mapping_tools/build_dashboard_graph_index.py`, `build_energy_balance_graph_links.py`,
  `convert_leap_combined_esto_to_esto_first.py` — write `results/mapping_graph_index/` (see
  that folder's README). No generated graph-index files are currently present
  in this checkout; the folder contains only its tracked README. The last known
  output of this style lived in the now-archived `codebase/mapping_code/`
  prototype bundle (see below).
- `codebase/mappings/canonical_mapping.py` — reads `config/ninth_pairs_to_esto_pairs.xlsx` /
  `config/leap_results_sheet_map.csv`, neither of which are among the files required to run the
  live pipeline (see `docs/repo_data_slimdown_plan.md`). Also imported by
  `codebase/utilities/build_canonical_mapping_views.py` (see "Broken" below).

## `codebase/mapping_code/` — archived, no longer in the working tree

As of 2026-07-23 this folder (a self-described "starter prototype" bundle diverged from the live
`codebase/mapping_tools/build_dashboard_graph_index.py` / `convert_leap_combined_esto_to_esto_first.py`,
confirmed via `diff` to not be identical to those live versions, and hardcoding a different
machine's Python path and the legacy `config/leap_mappings.xlsx`) was moved to
`archive/2026-07-23_repo_cleanup/mapping_code/` — see `docs/archive_log.md`.
The prototype's Markdown starter note was consolidated under
`docs/archive/2026-07-23_repo_cleanup/mapping_code/` on 2026-07-28; the
non-Markdown prototype files remain in the top-level archive. It was never
referenced from anywhere else in `codebase/`, so nothing else needed updating.

## Legacy (superseded, kept for reference only)

- `codebase/leap_mapping_refresh_workflow.py` — old refresh workflow for
  `config/leap_mappings.xlsx` / `config/master_config.xlsx`, explicitly superseded by
  `config/outlook_mappings_master.xlsx` (see root `README.md`, `AGENTS.md`). This is the sole
  entry point into the whole dashboard-prototype cluster above plus `utilities/master_config.py`.
- `codebase/utilities/master_config.py` — reader for `config/master_config.xlsx`. Used by the
  legacy chain above, and also as Stage 1's `FALLBACK_WORKBOOK_PATH` — so it's not fully dead,
  but its primary consumers are legacy.

## Broken — do not use as-is

- `codebase/utilities/ninth_to_esto_mapping_coverage.py` — imports
  `codebase.scrapbook.utilities.load_augmented_reference_tables`. No `codebase/scrapbook/`
  directory exists anywhere in this repo. This script cannot currently run. **Note:** an earlier
  pass of this doc (2026-07-22, on a different checkout) attributed this same broken import to
  `codebase/utilities/build_canonical_mapping_views.py` — that script's imports have since
  changed and it no longer references `scrapbook` at all; the broken import is only in
  `ninth_to_esto_mapping_coverage.py` as of this review. Neither script is imported by anything
  else, so this doesn't affect the live pipeline.

## Unused / orphaned

- `codebase/functions/unified_name_lookup.py` — not imported anywhere in `codebase/`.

## Notes

- The canonical mapping pipeline is the `run_mapping_pipeline.py` path — treat everything else
  as either a manual maintenance tool (still actively used), out-of-scope/legacy/broken per the
  buckets above, or archived.
- `AGENTS.md` used to reference `codebase/transformation_analysis_workflow.py` as a script that
  exists (it never did, at any depth under `codebase/`) — already fixed earlier the same day
  (2026-07-23, commit `18b1989`), so this note is historical, not an outstanding item.
- When the workbook or source data changes, run the maintenance workflow (Stage 0) before the
  main pipeline.
