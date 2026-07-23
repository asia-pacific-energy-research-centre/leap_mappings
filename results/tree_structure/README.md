# `results/tree_structure/`

Built by Stage 3 of `run_mapping_pipeline.py`. Holds each dataset's hierarchy (parent/child
structure) and the recursive-sum validations that check whether parent totals actually equal
the sum of their children. Check here when a subtotal in the comparison data doesn't reconcile.

## Trees

| File | Purpose |
|---|---|
| `esto_tree.csv`, `ninth_tree.csv`, `leap_tree.csv`, `common_esto_tree.csv` | Per-dataset structural hierarchy (dataset/axis/code/parent_code). |
| `all_dataset_trees.csv` | All four trees concatenated — the canonical hierarchy source other validations read from. |

## Validation

| File | Purpose |
|---|---|
| `ninth_validation.csv`, `ninth_sector_validation.csv`, `ninth_fuel_validation.csv`, `leap_validation.csv` | Recursive-sum checks per source hierarchy (does a parent equal the sum of its children in the *raw source* data, before any mapping). |
| `common_esto_validation.csv` / `common_esto_validation_summary.csv` | Recursive-sum mismatches within the Common ESTO structure itself, and the summary of that run. |
| `common_esto_validation_by_year.csv`, `common_esto_validation_totals.csv` | Year-by-year and totals breakdowns of the Common ESTO validation. |
| `common_esto_validation_child_detail.csv`, `common_esto_validation_issue_patterns.csv`, `common_esto_validation_rollup_diagnosis.csv` | Deeper detail behind the validation mismatches — per-child breakdown, recurring issue-pattern grouping, and rollup-cause diagnosis, all from `common_esto_validation_orchestration.py`. |
| `common_esto_source_frontier.csv` | The non-overlapping comparison frontier used as the basis for validation (which rows may be summed together without double-counting). |
| `common_esto_rollup_validation.csv` / `common_esto_rollup_validation_summary.csv` | Validates the rollup rules themselves (not just the resulting totals) against their contributor rows. |
| `source_parent_anchor_validation.csv` / `_summary.csv` | Checks converted (mapped) totals against the original raw source parent totals — the main defense against a mapping silently changing a total. This system has been under active development — see `docs/prompts/anchor_validator_fixes_findings_20260722.md` (and its `_20260723.md` follow-up if present) for the latest detail rather than treating this README as the full picture. |

## Also present but not from the current pipeline run

`esto_validation.csv` and `common_esto_non_esto_parent_child_edges.csv` are written only when
`build_dataset_tree_structure.py` is run directly as its own script (`python -m
codebase.mapping_tools.build_dataset_tree_structure`), not by `run_mapping_pipeline.py`'s Stage
3 (which calls the same builder/validator functions but writes the file set above instead). If
you see these, they're from a manual standalone run, not the last full pipeline run.

See `docs/results_folder_cleanup_candidates.md` for files in this folder that look orphaned —
i.e. present in older result sets but not written by any current script (an `anchor_diagnostics/`
subfolder, `source_parent_anchor_MISSING_*.csv`, `*_SLICE*.csv`, and `*_baseline_*.csv` files).
These are deliberately left for a separate diagnostic-file-consolidation design task rather than
archived here — see `docs/README.md`'s note.

**⚠ Double-write pattern:** `esto_tree.csv`, `ninth_tree.csv`, `leap_tree.csv`,
`common_esto_tree.csv`, `ninth_validation.csv`, `leap_validation.csv`, and
`common_esto_validation.csv` are each written twice per full pipeline run — once by Stage 0
(via `build_dataset_tree_structure.run_tree_structure_workflow()`) and again by Stage 3, which
overwrites them with its own version. In a full run Stage 3's version is what you end up with,
but a partial run that stops after Stage 0 leaves Stage 0's version in place with no marker that
it isn't the Stage 3 version. Tracked as `docs/improvement_todo.md` §3a — this needs a decision,
not just a cleanup pass.
