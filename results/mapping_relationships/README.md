# `results/mapping_relationships/`

Built by Stage 1 (`build_energy_balance_relationships.py`) and the `leap_parse` /
`data_convert` steps of `run_mapping_pipeline.py`. This is the "row-level" layer: relationships
and per-source conversions, before they get grouped into the common ESTO structure
(`results/common_esto/`).

**Note (2026-07-23):** this folder has grown a `leap_missing_esto_*` cluster and a few other
newer QA outputs (`nonzero_mapping_evidence_audit.csv`, `nonzero_source_pair_evidence_audit.csv`,
`proposed_clear_fuel_crosswalk_rows.csv`, `proposed_nonzero_mapping_rows.csv`,
`usa_leap_results_converted_to_esto.csv`) since this guide was last fully rewritten — these look
like the output of newer standalone mapping-candidate/coverage tools in the same family as
`audit_nonzero_mapping_evidence.py` / `build_leap_mapping_candidates.py` below, but weren't
individually traced back to a producing script for this pass. Treat the tables below as the
verified core, not a complete file listing.

## Primary

| File | Purpose |
|---|---|
| `energy_balance_relationships.csv` / `.xlsx` | The core relationship table read from the mapping workbooks — every maintained source→target row, one row per `use_case`. This is what Stage 2/3 and most downstream tools consume. |
| `relationship_catalogue_6_col.csv` | The same relationships, compacted to 6 key columns — easier to skim or diff. |

## Per-source conversion outputs (`data_convert` step)

| File | Purpose |
|---|---|
| `raw_leap_results.csv` | Raw LEAP balance exports parsed to long format (`leap_parse` step). |
| `leap_results_converted_to_esto.csv` | LEAP rows converted onto ESTO-style flow/product rows. |
| `leap_source_rollup_audit.csv`, `leap_source_to_esto_component_lineage.csv` | Audit trail / lineage for the LEAP→ESTO conversion. |
| `leap_source_branch_fallback_audit.csv`, `leap_all_demand_aggregated_overlap_warnings.csv` | From the source-branch fallback preflight — flags interim-branch substitutions and "all demand aggregated" overlaps. |
| `ninth_results_converted_to_esto.csv`, `ninth_source_to_esto_component_lineage.csv` | Same conversion/lineage pattern for 9th Outlook rows. |
| `esto_results_exact_rows.csv` | ESTO's own non-subtotal rows prepared as long-format rows (plus derived non-expanding subtotal rows), for comparison alongside the two conversions above. |

## QA (Stage 1)

Duplicate/coverage/gap checks on the relationship build itself: `coverage_exclusions.csv`,
`esto_combined_rows.csv`, `common_esto_overrides.csv`, `qa_unknown_esto_target_flows.csv`,
`qa_unknown_ninth_target_flows.csv`, `non_expanding_rollups.csv`,
`qa_non_expanding_rollup_unresolved.csv`, `leap_sources_without_esto_target.csv`,
`esto_targets_without_leap_source.csv`, `missing_dataset_pairs_by_use_case.csv`,
`not_considered_esto_rows.csv`, `leap_to_esto_duplicate_source_pairs*.csv`,
`leap_to_esto_duplicate_target_pairs*.csv`,
`one_to_many_mappings_without_allocation_or_combined_target.csv`,
`leap_to_esto_parent_child_risks.csv`, `leap_to_esto_coverage_summary.csv`,
`leap_to_esto_excluded_source_audit.csv`.

Most of the per-name QA files above (`qa_unknown_esto_target_flows.csv`, the
`leap_to_esto_duplicate_*` pairs, `*_audit.csv`, `*_lineage.csv`, etc.) are not currently named
in `docs/improvement_todo.md`'s review list, though their naming suggests they're meant as
review checkpoints — see `docs/results_folder_cleanup_candidates.md`.

## Standalone tools (not part of the main pipeline run)

- `leap_to_esto_coverage/` — `check_leap_to_esto_conversion_coverage.py`: audits included relationships against raw LEAP exports and an optional expected-ESTO-universe file. (Not present in this checkout as of 2026-07-23 — only produced if that tool has been run manually.)
- `no_data_rows_*.csv` — `build_no_data_mapping_rows.py`: flags mapping rows whose key pairs have no non-zero value anywhere in the source data.
- `proposed_leap_combined_ninth_rows.csv` — `build_leap_mapping_candidates.py`: copy-ready LEAP-to-9th mapping rows for verified candidates.
- `proposed_ninth_pairs_to_esto_pairs_coal_products.csv` — `build_valid_nonzero_mapping_candidates.py`: copy-ready mapping rows after `audit_nonzero_mapping_evidence.py` confirms non-zero evidence on both axes. **This one is git-committed**, unlike almost everything else in `results/` — a deliberate exception, not an oversight.

## `economy_scoped/`

Single-economy mirrors of `raw_leap_results.csv`, `leap_results_converted_to_esto.csv`, and
`leap_source_rollup_audit.csv` — written by `regen_common_esto_comparison_fast_path_workflow.py`
when it regenerates comparison outputs for one economy without rerunning the full pipeline. The
matching `results/common_esto/economy_scoped/<economy_id>/` folder holds that tool's downstream
outputs. This is **intentional narrow-scope output, not accidental duplication** — but if you're
not using the fast-path regen tool, ignore this folder; the full, all-economy files above are
the ones the main pipeline produces.
