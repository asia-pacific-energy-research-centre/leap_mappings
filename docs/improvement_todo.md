# LEAP mappings improvement todo

This backlog covers improvements outside the deferred regression and verification work in `docs/QA plan.md`. Complete items only after reviewing current generated outputs; existing result files may be stale when mapping workbooks have uncommitted changes.

## 1. Resolve current semantic mapping issues

**Status:** In progress — data-relevance filtering implemented; semantic findings still require review

Rerun mapping maintenance and Stages 1-3 with the intended workbook state before treating the current row counts as authoritative. Then group findings by recurring semantic cause rather than reviewing thousands of rows independently.

Primary review outputs:

- `results/common_esto/qa_common_esto_unresolved_partial_coverage.csv` — actionable high-severity rows after filtering `missing_component_pairs` to components with non-zero ESTO base-year, 9th projection, or LEAP balance evidence.
- `results/common_esto/qa_common_esto_structural_partial_coverage.csv` — full Stage 2 structural candidates before applying value relevance.
- `results/common_esto/qa_common_esto_partial_coverage_components_without_relevance.csv` — structurally missing pairs excluded from the actionable file because they lack qualifying non-zero evidence.
- `results/common_esto/qa_common_esto_existing_components_without_relevance.csv` — existing Common ESTO components that are not needed for the current comparison data; informational only.
- `results/common_esto/qa_nonzero_unmapped_leap_branches.csv` — non-zero LEAP balance branches without direct ESTO mappings, including whether an indirect ESTO pair can be inferred through the 9th crosswalk.
- `results/common_esto/qa_common_esto_partial_coverage_mapping_candidates.csv` — review-only, copy-friendly proposals for the mapping sheet identified by each actionable partial-coverage row.
- `results/common_esto/qa_nonzero_unmapped_leap_branch_mapping_candidates.csv` — review-only ESTO target proposals inferred independently from LEAP branch and fuel evidence.
- `results/common_esto/highly_recommended_mapping_candidates.csv` — combined copy-ready mapping rows; excludes every incomplete, ambiguous, zero-only, or already-targeted source pair.
- `results/maintenance/leap_source_presence_conflicts.csv` — LEAP sector/fuel pairs active on only one of `leap_combined_esto` and `leap_combined_ninth`. Use `presence_status` to separate the two directions. Do not assume every asymmetry is an error; determine whether the comparison scope requires both mappings.
- `results/tree_structure/common_esto_non_esto_parent_child_edges.csv` — Common ESTO hierarchy edges not present in the source ESTO tree. Decide whether each is an intentional extension, a display hierarchy only, or an invalid additive parent-child relationship.

Supporting lineage:

- `results/common_esto/common_esto_rows.csv` — find the labels and scope for a `common_row_id`.
- `results/common_esto/common_esto_row_components.csv` — inspect the full ESTO component membership of that row.
- `results/mapping_relationships/energy_balance_relationships.csv` — trace which LEAP or 9th source relationship produced the component coverage.
- `config/outlook_mappings_master.xlsx` — inspect the owning base mapping and rollup sheets.
- `config/mapping_issue_exception_sets.xlsx` — check whether an apparent conflict is an explicitly reviewed exception.
- `config/esto_external_definition_authority_working_set.xlsx` — check flow/product scope, common mapping mistakes, confidence, and sign meaning before changing a mapping.

Suggested review order:

1. Group partial-coverage findings by `source_system`, `use_case`, and repeated `missing_component_pairs` patterns.
2. For one representative `common_row_id`, compare `common_esto_rows.csv` with `common_esto_row_components.csv`.
3. Trace the source relationship in `energy_balance_relationships.csv`.
4. Inspect the relevant base mapping and rollup rows in `outlook_mappings_master.xlsx`.
5. Classify the cause as missing mapping, over-broad common row, intentional source limitation, invalid rollup, or reviewed exception.
6. Record any required human rule in `docs/special_rules_and_design_decisions.md` before changing behaviour.
7. Apply the narrowest mapping/configuration correction and rerun all affected stages.

Do not prioritize the raw counts in `unmapped_nonzero_esto_pairs.csv`, `unmapped_nonzero_ninth_pairs.csv`, or `common_esto_source_rows_missing_common_map.csv` until they are separated into non-zero relevant rows, subtotals, intentionally excluded scope, and genuine mapping gaps.

## 2. Finish the canonical-workbook migration

**Status:** Pending

- Complete the intended removal of `config/leap_mappings.xlsx`.
- Audit remaining production call sites for `leap_mappings.xlsx`, `master_config.xlsx`, and legacy `leap_utilities` fallbacks.
- Make canonical workflows use `config/outlook_mappings_master.xlsx` explicitly.
- Fail with a clear message when a required canonical sheet or column is absent rather than silently using legacy data.
- Keep deliberate legacy compatibility isolated and documented.

## 3. Complete hierarchy value validation

**Status:** Pending

- Add recursive 9th Outlook sector and fuel value validation.
- Add recursive LEAP branch value validation where result data are available.
- Preserve the distinction between source-defined hierarchy and Common ESTO-only extensions.
- Report parent/detail overlaps that could cause double counting.
- Document any hierarchy edges whose additive meaning requires human confirmation.
- Add an explicit mapped-ESTO-subtotal coverage check: for every raw ESTO parent subtotal, compare its value with the sum of mapped leaf descendants and report mapped, unmapped, excluded, and zero-only child components.
- Make subtotal validation summaries report the number of eligible parents and checks performed, not only mismatch rows, so an empty CSV cannot be mistaken for proof that coverage was tested.
- Define a non-overlapping comparison frontier for each comparison scope. The canonical all-rows dataset must retain parent, child, and generated rollup rows; a separate validated additive view or explicit frontier metadata should identify which rows may be summed together.
- Preserve `common_row_id`, rollup basis, hierarchy status, and component lineage in a machine-readable output so dashboards do not infer subtotal meaning from display labels.
- Decide whether one centrally validated additive dataset is sufficient or whether several named frontiers are required for detail, summary, and rollup contexts.

## 4. Resolve the ESTO definition-authority working set

**Status:** Pending human review

Work through `config/esto_external_definition_authority_working_set.xlsx`:

- Resolve the four rows currently in `review_queue`.
- Review the 109 `product_leaks` and fix their source extraction or classification where applicable.
- Review flow definitions marked `Unknown`, `unclassified`, `needs_review`, or `needs_definition_or_alias`.
- Resolve low-confidence `Others` categories before using them as mapping authority.
- Preserve source references and the history of rejected interpretations.

## 5. Improve researcher mapping maintenance

**Status:** Proposed

Generate a compact review workbook containing actionable findings rather than raw diagnostic volumes. Include:

- source and current target categories;
- definitions, inclusions, and exclusions;
- raw and after-rollup cardinality;
- non-zero example economies and values;
- matched exception details;
- suggested review action;
- owning sheet and row identifier;
- related decision-log ID.

The workbook should support review, not automatically approve or rewrite mappings.

## 6. Make the existing orchestration workflow notebook-safe

**Status:** Proposed

Refactor `codebase/run_mapping_pipeline.py` into a slim Jupyter-friendly workflow with top-level toggles for:

1. Mapping maintenance.
2. Relationship generation.
3. Common ESTO structure generation.
4. Application of the common structure.
5. Tree generation and validation.

Reuse the existing stage functions. Do not duplicate their processing logic. Replace the command-line-only `argparse` entry path with notebook-safe run blocks, and make the selected input workbook and result directories explicit near the top of the workflow.

## 7. Improve explanatory documentation

**Status:** Proposed

- Add a compact pipeline diagram.
- Add a worked example showing how a coarse source category forces a common rollup or graph partition.
- Add a glossary for relationship, component, common row, source aggregate, axis partition, and comparison scope.
- Define each `comparison_scope` and its included systems.
- Clearly separate blocking validation failures from review diagnostics.
- Keep `README.md`, `docs/mappings_system.md`, and the implemented pipeline behaviour synchronized.

## 8. Check the LEAP side of no-data mapping rows once full LEAP output sheets exist

**Status:** Proposed

`codebase/mapping_tools/build_no_data_mapping_rows.py` flags `leap_combined_esto` and `leap_combined_ninth` rows whose non-LEAP side (ESTO or 9th Outlook) has no non-zero data anywhere. It currently assumes the LEAP side always has no data, because we do not yet have full LEAP output sheets in a form comparable to the ESTO/9th source tables. Once those output sheets are available:

- Load real LEAP result data and compute non-zero (leap_sector_name_full_path, raw_leap_fuel_name) pairs, the same way `load_nonzero_esto_pairs`/`load_nonzero_ninth_pairs` do for the other two systems.
- Replace the `leap_side_has_data` placeholder (`pd.NA`) with a real boolean.
- Restrict `leap_combined_esto`/`leap_combined_ninth` flags to rows where **both** sides have no data, matching the `ninth_pairs_to_esto_pairs` logic already in place.

