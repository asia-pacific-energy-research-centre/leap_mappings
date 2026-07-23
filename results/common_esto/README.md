# `results/common_esto/`

Built by Stage 2 (`build_common_esto_structure.py`, structure) and Stage 3
(`apply_common_esto_structure.py`, apply-to-data) of `run_mapping_pipeline.py`, plus a few
standalone maintenance/validation tools. This is the folder with the actual answer in it —
start here before `mapping_relationships/` or `tree_structure/`.

**Note (2026-07-23):** this folder currently has more files than the tables below name
individually (the pipeline has grown since this guide was last fully rewritten) — treat this as
"here's how to find your way to the primary outputs and the main QA categories," not as an
exhaustive file listing. A dedicated file-by-file usefulness audit
(`docs/diagnostic_file_review_signals.md`) is intentionally being designed together with a
separate anchor-validator data-reliability-flag task rather than done here — see
`docs/README.md`.

## Primary — read these first

| File | Purpose |
|---|---|
| `common_esto_comparison_data.csv` | **The final output.** Every LEAP/9th/ESTO row mapped onto the common structure, long format. (Written as `*_needs_mapping_review.csv` instead if Stage 3 QA errors block the run — that's a signal something upstream needs fixing before this is trustworthy.) |
| `common_esto_comparison_wide.csv` | Same data, one column per year. |
| `common_esto_rows.csv` / `common_esto_rows.xlsx` | The common ESTO row structure: which exact ESTO flow/product components got grouped into each common row, and why (graph-partitioned so a source aggregate is never split). |
| `esto_to_common_esto_map.csv` | Lookup: exact ESTO (flow, product) pair → its common row. |
| `common_esto_output_status.csv` | Manifest of this run's outputs (also gains validation/anchor status rows once Stage 3's validation step runs). |

## QA / diagnostics (Stage 2 + Stage 3, prefixed `qa_`)

These explain *why* the structure or comparison data looks the way it does. Grouped roughly by
what they answer:

- **Is anything missing or duplicated?** `qa_common_esto_components_missing_from_structure.csv`, `qa_common_esto_duplicate_components.csv`, `common_esto_source_rows_missing_common_map.csv`
- **Did a source aggregate get split (the thing the whole design avoids)?** `qa_common_esto_source_aggregates_split.csv`, `qa_common_esto_rollup_explanations.csv`, `qa_common_esto_non_expanding_rollups.csv`, `qa_common_esto_non_expanding_frontier_check.csv`
- **Coverage gaps that still need a mapping decision** (see `docs/improvement_todo.md` §1 for the recommended review order): `qa_common_esto_unresolved_partial_coverage.csv`, `qa_common_esto_structural_partial_coverage.csv`, `qa_common_esto_partial_coverage_components_without_relevance.csv`, `qa_common_esto_existing_components_without_relevance.csv`, `qa_nonzero_unmapped_leap_branches.csv`
- **Copy-ready mapping candidates** (review-only, never auto-applied): `qa_common_esto_partial_coverage_mapping_candidates.csv`, `qa_nonzero_unmapped_leap_branch_mapping_candidates.csv`, `highly_recommended_mapping_candidates.csv`
- **Did totals survive the mapping?** `common_esto_total_check.csv` / `qa_common_esto_total_check.csv`, `common_esto_source_coverage_check.csv`
- **Axis partitioning internals**: `qa_common_esto_product_axis_partitions.csv`, `qa_common_esto_flow_axis_partitions.csv`, `qa_common_esto_product_intersections_resolved.csv`, `qa_common_esto_flow_intersections_resolved.csv`, `qa_common_esto_axis_partition_skipped_broad_rows.csv`, `qa_common_esto_suppressed_graph_edges.csv`, `qa_common_esto_excluded_components.csv`, `qa_common_esto_structure_summary.csv`

## `diagnostics/`

Deeper trace-level output for "broad" or intersecting common rows (rows spanning unusually
many components) — pruned components, relevance scoring, intersecting axis groups. Only worth
opening when a `qa_*` file above points you here.

## `structural_artifacts/`, `economy_scoped/`

Outputs of **standalone** tools, not the main pipeline run:

- `structural_artifacts/` — `compile_structural_mapping_artifacts.py`: value-free structural membership only (no numeric data), used as a lighter-weight mapping reference.
- `economy_scoped/<economy_id>/` — `regen_common_esto_comparison_fast_path_workflow.py`: fast-path regeneration for a single economy, skipping Stages 0–2.

(An `apply_partitioned_common_esto.py`-driven `partitioned_application/`/`partition_cache/` pair
is documented elsewhere as an occasional standalone output for large/slow reruns — not present
in this checkout as of 2026-07-23.)

## `anchor_reconciliation/`, `anchor_contribution_breakdown/`, `inverted_conservation/`

Outputs of standalone validation tools that check totals a different way than Stage 3's
built-in checks:

- `anchor_reconciliation/`, `anchor_contribution_breakdown/` — `reconcile_anchor_validation.py`. This is the **current** anchor-reconciliation method. (`results/tree_structure/anchor_diagnostics/` is an older, no-longer-produced version of a similar check — see `docs/results_folder_cleanup_candidates.md`.)
- `inverted_conservation/` — `inverted_conservation_validation.py`: validates conservation for the direction where LEAP is the *target* system, projected through Common ESTO rows.

Note: `inverted_conservation.building/` and `inverted_conservation_variant_verification/` are
extra output-directory variants from manual re-runs of the same standalone script with a
different `output_dir` argument, not distinct pipeline stages — see
`docs/results_folder_cleanup_candidates.md` for which one looks like a true duplicate.

## `common_esto_comparison_wide_rebuilt.csv`, `qa_common_esto_partial_coverage_mapping_candidates_rebuilt.csv`

`_rebuilt` variants of files that already exist without that suffix, from a manual rebuild run —
see `docs/results_folder_cleanup_candidates.md`. Not produced by any current script path as far
as this pass could confirm.
