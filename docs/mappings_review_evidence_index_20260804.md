# Mappings review evidence index — 2026-08-04

Use the Aug 3 run as the sole current evidence baseline. Older files in the
same directories may be useful for history but must not silently replace the
current run.

## Core outputs

| Evidence | Path | Use |
|---|---|---|
| Run manifest | `results/common_esto/stage3_run_manifest.json` | Run ID, hashes, input/output contract, validation summaries |
| Common comparison data | `results/common_esto/common_esto_comparison_data.csv` | Value-level source/comparison evidence |
| Wide comparison data | `results/common_esto/common_esto_comparison_wide.csv` | Human-readable year-oriented checks |
| Missing Common map rows | `results/common_esto/common_esto_source_rows_missing_common_map.csv` | Broad coverage diagnostic; filter to non-zero and relevant rows |
| Source coverage | `results/common_esto/common_esto_source_coverage_check.csv` | Source-to-Common coverage context |
| Total checks | `results/common_esto/qa_common_esto_total_check.csv` | Conservation/source-total evidence |
| Output status | `results/common_esto/common_esto_output_status.csv` | Stage 3 output status and scope records |

## MAPQ-009 semantic coverage files

| File | Current rows | Interpretation |
|---|---:|---|
| `results/common_esto/qa_common_esto_unresolved_partial_coverage.csv` | 48 | Actionable partial coverage after relevance filtering; repeated across scopes |
| `results/common_esto/qa_nonzero_unmapped_leap_branches.csv` | 281 | Non-zero LEAP branches without a direct ESTO pair; many are aggregate or boundary branches |
| `results/common_esto/qa_common_esto_partial_coverage_mapping_candidates.csv` | 4 | Review-only, copy-ready partial-coverage proposals |
| `results/common_esto/qa_nonzero_unmapped_leap_branch_mapping_candidates.csv` | 15 | Review-only, copy-ready unmapped-LEAP proposals |
| `results/common_esto/highly_recommended_mapping_candidates.csv` | combined candidate view | Convenience view; still review-only |
| `results/common_esto/qa_common_esto_partial_coverage_components_without_relevance.csv` | informational | Structural gaps without qualifying non-zero evidence |
| `results/common_esto/qa_common_esto_existing_components_without_relevance.csv` | informational | Existing components with no current relevance evidence |

The largest unmapped-branch groups are `Total Transformation`, `Total Final
Energy Demand`, `All demand aggregated`, `Other loss and own use`, and
`Transfers unallocated`. Treat these as likely hierarchy/boundary families
before treating them as missing leaf mappings.

## MAPQ-010 rollup files

| Evidence | Path | Use |
|---|---|---|
| Active review prompt | `docs/prompts/review_non_expanding_vs_detached_rollups_prompt.md` | Required questions, classifications, safety rules |
| Manual rollup source | `config/outlook_mappings_master.xlsx`, sheet `esto_rollup_rules` | Current active modes and reasons |
| Rollup explanations | `results/common_esto/common_esto_rollup_explanations.csv` | What each generated boundary did |
| Rollup diagnosis | `results/tree_structure/common_esto_validation_rollup_diagnosis.csv` | Boundary-aware validation interpretation |
| Issue patterns | `results/tree_structure/common_esto_validation_issue_patterns.csv` | Grouped patterns such as `child_obscured_by_parent_rollup` and `replaced_by_non_expanding_rollup` |
| Common tree | `results/tree_structure/common_esto_tree.csv` | Current Common hierarchy |
| ESTO Extended tree | `results/tree_structure/esto_extended_tree.csv` | Extended-only hierarchy context |

Current active ESTO rollup inventory: 39 included rules — 8 `EXPANDING`, 24
`NON_EXPANDING`, and 7 `DETACHED`. The review should determine whether
`DETACHED` is a true semantic category or a more explicit diagnostic subtype
of a replaced comparison boundary.

## Anchor-validation files

| Evidence | Path | Use |
|---|---|---|
| Anchor summary | `results/tree_structure/source_parent_anchor_validation_summary.csv` | First-pass counts by scope, source system, and axis |
| Full validation detail | `results/tree_structure/source_parent_anchor_validation_full.csv.gz` | Compressed row-level anchor checks |
| Detailed checks | `results/tree_structure/source_parent_anchor_validation.csv` | Row-level parent/child evidence |
| Child/context values | `results/tree_structure/source_parent_anchor_child_values.csv`, `source_parent_anchor_child_context_values.csv` | Direct child frontier values and contexts |
| Economy examples | `results/tree_structure/source_parent_anchor_economy_examples.csv` | Economy-level examples for targeted review |
| Exception review | `results/tree_structure/source_parent_anchor_exception_review.csv`, `source_parent_anchor_exception_set_review.csv` | Existing exception and allowlist context |
| Reconciliation candidates | `results/tree_structure/source_parent_anchor_leaf_reconciliation_candidates.csv` | Candidate source/leaf reconciliation evidence |
| Common validation summary | `results/tree_structure/common_esto_validation_summary.csv` | Common hierarchy validation status alongside anchors |
| Common validation detail | `results/tree_structure/common_esto_validation.csv` | Row-level Common hierarchy evidence |
| APEC-specific evidence | `results/apec_anchor_validation_raw_source_fix_final/` | Latest APEC-first anchor review work and examples |

## Anchor summary to start from

The Aug 3 run reports the largest anchor failure counts for:

- Ninth flow anchors in `esto_leap_ninth`: 1,114 failures, all marked
  confirmed in the summary.
- LEAP flow anchors in `esto_leap`: 393 failures, all marked confirmed.
- LEAP flow anchors in `esto_leap_ninth`: 338 failures, mostly confirmed with
  a smaller unconfirmed remainder.
- Ninth product anchors in `esto_leap_ninth`: 275 failures, marked confirmed.
- ESTO flow anchors: 16 and 19 failures in the two ESTO-containing scopes,
  marked unconfirmed in the summary.

These counts are triage starting points, not automatic exception approvals.
Review the detailed and raw-source files before deciding whether a failure is
caused by a mapping, a subtotal boundary, a source inconsistency, or an
allowlisted data-quality issue.

## Most useful filters

When reviewing CSVs, filter in this order:

1. `run_id` equal to `common_esto_20260803T114057574740Z` where available.
2. Non-zero source evidence or `confirmed_issue_failed == 1`.
3. One `comparison_scope` and `source_system` at a time.
4. One semantic family: gas processing, oil refining, coal transformation,
   transport/demand, power/CHP/heat, or aggregate/boundary rows.
5. Only then inspect individual economies, scenarios, years, products, and
   source paths.
