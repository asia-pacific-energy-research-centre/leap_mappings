# Workflow Inventory

Last reviewed: 2026-07-07

This repo is primarily a mapping pipeline, not a loose collection of independent
workflow scripts. The inventory below focuses on the active entrypoints that
drive the canonical mapping pipeline and its maintenance checks.

## Active Entry Points

| Script | Bucket | Purpose |
|---|---|---|
| `codebase/run_mapping_pipeline.py` | Pipeline orchestrator | End-to-end Common ESTO / LEAP mapping pipeline. Runs maintenance, relationship building, common ESTO structure, LEAP parse, and the conversion stages. |
| `codebase/outlook_mapping_maintenance_workflow.py` | Maintenance / Stage 0 | Updates subtotal flags, produces mapping QA outputs, and supports workbook maintenance for `outlook_mappings_master.xlsx`. |
| `codebase/propagate_esto_rows_workflow.py` | Maintenance utility | Appends a reviewed ESTO row set to matching ESTO source files, usually for controlled maintenance or propagation of approved rows. |

## Legacy / Archive

These are retained for reference, but they are not the canonical active path for
the current pipeline.

| Script | Bucket | Purpose |
|---|---|---|
| `codebase/leap_mapping_refresh_workflow.py` | Legacy / archive | Old-workbook refresh workflow for `config/leap_mappings.xlsx` and `config/master_config.xlsx`. Kept only as a reference while the canonical pipeline uses `outlook_mappings_master.xlsx`. |

## Supporting Pipeline Modules

The pipeline stages are implemented by helper modules under `codebase/mapping_tools/`.
They are not separate user-facing workflows, but they are part of the active
runtime surface:

- `build_energy_balance_relationships.py`
- `build_common_esto_structure.py`
- `apply_common_esto_structure.py`
- `parse_leap_balance_export.py`
- `convert_leap_results_to_esto.py`
- `apply_ninth_to_esto_conversion.py`
- `build_dataset_tree_structure.py`
- `compile_structural_mapping_artifacts.py`
- `common_esto_validation_orchestration.py`
- `check_leap_to_esto_conversion_coverage.py`
- `build_missing_mapped_esto_rows.py`
- `build_no_data_mapping_rows.py`
- `apply_duplicate_mapping_removal.py`
- `apply_display_name_updates.py`
- `apply_subtotal_updates.py`
- `apply_subtotal_mismatch_review.py`
- `apply_subtotal_mismatch_source_flip.py`
- `infer_subtotal_labels.py`
- `source_rollups.py`
- `structural_resolver.py`
- `reconcile_anchor_validation.py`
- `source_parent_anchor_validation.py`
- `mapping_candidate_generation.py`
- `inverted_conservation_validation.py`

## Notes

- The canonical mapping pipeline is the `run_mapping_pipeline.py` path.
- The old refresh workflow is intentionally retained as a legacy reference.
- When the workbook or source data changes, run the maintenance workflow before
  the main pipeline.

