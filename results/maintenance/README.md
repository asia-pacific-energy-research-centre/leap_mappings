# `results/maintenance/`

Built by Stage 0 (`codebase/archive/outlook_mapping_maintenance_workflow.py`) plus a few
standalone review tools. This is QA on the **mapping workbook itself**
(`config/outlook_mappings_master.xlsx`) — check here before editing mappings, not after.

## Primary — start here

| File | Purpose |
|---|---|
| `maintenance_summary.csv` | Compact row-count/status summary across all Stage 0 + tree-structure QA outputs — the one file to check first after a maintenance run. |

## Mapping-quality QA (Stage 0)

| File | Purpose |
|---|---|
| `duplicate_mappings.csv` | Exact-duplicate active mapping rows. |
| `many_to_many_conflicts.csv` / `_allowed_matched.csv` | Many-to-many mapping conflicts, split into unresolved vs. reviewed-and-allowed. |
| `leap_source_presence_conflicts.csv` / `_allowed_matched.csv` | LEAP sector/fuel pairs active on only one of `leap_combined_esto` / `leap_combined_ninth` (see `AGENTS.md` — this asymmetry is often deliberate, not a bug). |
| `crosswalk_target_conflicts.csv` / `_allowed_matched.csv` | 9th↔ESTO crosswalk target conflicts. |
| `unmapped_nonzero_esto_pairs.csv` / `_allowed_matched.csv` | ESTO (flow, product) pairs with real data but no active mapping row. |
| `unmapped_nonzero_ninth_pairs.csv` / `_allowed_matched.csv` | Same, for 9th Outlook (sector, fuel) pairs. |
| `subtotal_mismatches.csv` / `_allowed_matched.csv` | Leaf LEAP source mapped to an aggregate target outside the allowlist ("M6 rule"). |
| `subtotal_label_overrides_stale.csv` | Subtotal label overrides that no longer match current data — candidates to remove from the workbook. |
| `cardinality_leap_esto.csv`, `cardinality_leap_ninth.csv`, `cardinality_ninth_esto.csv` | Cardinality of each mapping direction — how many-to-many each pairing actually is. |
| `display_names_qa.csv`, `display_names_proposed_updates.csv` | Display-name QA and proposed fixes (from `update_leap_display_names.py`, invoked as part of Stage 0). Never auto-applied to the workbook — review then run `apply_display_name_updates.py`. |
| `esto_row_propagation_preview.csv` / `_written.csv` | Preview/applied output of `codebase/propagate_esto_rows_workflow.py` — a reviewed ESTO row set appended to matching ESTO source files. |

## `missing_mapped_esto_rows/`

Built by `build_missing_mapped_esto_rows.py` (called from Stage 0). One
`<esto_source>_missing_mapped_rows.csv` / `_audit.csv` pair per ESTO source-CSV vintage
(currently `00APEC_2024` and `00APEC_2025`), plus `missing_mapped_esto_rows_summary.csv`. Also
includes a growing set of related coverage-fix outputs from the same script family (e.g.
`_commercial_services_unallocated_updates.csv` / `_validation.csv`, `_lng_split_rows.csv` /
`_audit.csv`, `_ninth_nonzero_filter_audit.csv`) — these are newer additions not individually
traced in this pass; treat the file-name pattern (`<esto_source>_<check>.csv`) as the guide.
Paste-ready proposed ESTO rows — never edits source data directly.

**Note:** there is also a top-level `results/missing_mapped_esto_rows/` folder (outside
`maintenance/`) in some result sets. That is a stale duplicate from an earlier code path —
confirmed 2026-07-23 (its `missing_mapped_esto_rows_summary.csv` is dated weeks older than the
one here, and nothing in `codebase/` references the top-level path). The current script always
writes under `results/maintenance/missing_mapped_esto_rows/`. See
`docs/results_folder_cleanup_candidates.md`.

## Standalone review tools (not run automatically by Stage 0)

- `subtotal_mismatch_suggested_improvements.csv` — `build_subtotal_mismatch_review.py`: proposed subtotal-flag fixes for review. Apply with `apply_subtotal_mismatch_review.py` / `apply_subtotal_mismatch_source_flip.py`.
- `subtotal_draft_esto_pairs.csv`, `subtotal_draft_ninth_pairs.csv`, `subtotal_draft_leap_pairs.csv`, `rollup_consistency.csv` — `infer_subtotal_labels.py`: draft current-vs-proposed subtotal labels derived from the structural tree, plus a rollup-rule consistency check.

Several `apply_*.py` scripts (`apply_display_name_updates.py`, `apply_duplicate_mapping_removal.py`,
`apply_subtotal_mismatch_review.py`, `apply_subtotal_mismatch_source_flip.py`,
`apply_subtotal_updates.py`) **read** the review files above and write their approved changes
directly into `config/outlook_mappings_master.xlsx` (backing up the previous version to
`config/archive/` first) — they don't write anything back into this folder.

`unmapped_ninth_pairs.csv` and `unmapped_esto_pairs.csv` (the un-filtered counterparts of the
documented `unmapped_nonzero_*_pairs.csv` files) and `subtotal_mismatches_including_exceptions.csv`
are substantial files not currently named in any review doc — see
`docs/results_folder_cleanup_candidates.md`.

The `*_copy.csv` / `*_copy 2.csv` / `*_new.csv` variants of several files above
(`display_names_qa copy.csv`, `display_names_qa_new.csv`, `subtotal_draft_*_pairs copy*.csv`,
`subtotal_mismatch_suggested_improvements copy.csv`) look like manual file-explorer duplicates —
flagged in `docs/results_folder_cleanup_candidates.md`, not archived as part of this pass since
they're diagnostic-output files in scope for a separate consolidation task.

## `logs/`

Ad hoc run logs from manual maintenance/validation invocations (anchor validation, structural
compilation, inverted-conservation reruns, etc.) — distinct from `results/logs/`, which only
holds the main pipeline's tee'd log. As of 2026-07-23 these have been moved to
`_archive_2026-07-23/logs/` (see `docs/archive_log.md`) since they were unambiguous ad hoc
scratch, not a current code path's output.
