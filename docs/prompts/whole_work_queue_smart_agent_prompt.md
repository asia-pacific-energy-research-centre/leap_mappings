# Smart-agent prompt: own the LEAP mappings work queue end to end

You are taking full ownership of the remaining LEAP mappings work queue in:

`C:\Users\Work\github\leap_mappings`

Work as a senior maintainer. Build a verified current baseline before making broad changes, preserve unrelated work, and take the queue through implementation, testing, documentation, and coherent commits. Do not treat stale CSV outputs or dated findings as current truth.

## Required reading before action

Read completely:

- `AGENTS.md`
- `C:\Users\Work\.codex\AGENTS_BALANCE_TABLES.md`
- `C:\Users\Work\.codex\AGENTS_LEAP_EXPORT.md`
- `docs/prompts/AGENTS.md`
- `docs/improvement_todo.md`
- `docs/special_rules_and_design_decisions.md`
- `docs/prompts/data_reliability_flag_and_diagnostic_consolidation_design_20260723.md`
- `docs/prompts/anchor_validator_fixes_findings_20260722.md`
- `docs/prompts/investigate_demand_sector_parent_child_mismatches_FINDINGS.md`
- `docs/prompts/investigate_ninth_09_total_transformation_reconciliation.md`

Also inspect the current `git status --short`, recent commits, active prompt inventory, and any uncommitted source-coverage work before editing. Treat all existing uncommitted changes as belonging to the user or another agent until proven otherwise.

## Overall objective

Bring the mapping system from its current partially rebuilt state to a verified, maintainable state. The main workstreams are:

1. finish and verify the active source-coverage audit/candidate work;
2. refresh a clean Stages 1–3 production baseline;
3. resolve the anchor-validator reliability-flag and mirror-row-gap design;
4. re-triage remaining anchor residuals against the current baseline;
5. review genuine semantic mapping gaps and human-review queues;
6. complete canonical-workbook migration and workflow/documentation cleanup.

Do not attempt to solve every item in one speculative edit. Work in phases and stop at human-decision gates.

## Phase 0 — establish ownership and baseline

1. Record the initial worktree state and identify which files are already modified or untracked.
2. Do not overwrite or commit unrelated changes.
3. Confirm the current canonical workbook is `config/outlook_mappings_master.xlsx`.
4. Confirm the current data inputs and pipeline paths.
5. Produce a short baseline report containing:
   - current commit and worktree state;
   - active uncommitted work and likely owner;
   - current output provenance and stale-output warnings;
   - focused test status;
   - current Stage 3 validation status.

If a production run is needed, follow `docs/prompts/run_mapping_pipeline_future_prompt.md`. Use the notebook-safe workflow preferences in `AGENTS.md`; do not launch a destructive or workbook-writing stage without checking what it writes first.

## Phase 1 — source-coverage audit and candidate work

Inspect and finish the currently active source-coverage work, including any uncommitted files such as:

- `codebase/mapping_tools/source_coverage_audit.py`;
- `codebase/mapping_tools/build_source_coverage_mapping_candidates.py`;
- `tests/test_source_coverage_audit.py`;
- `tests/test_source_coverage_mapping_candidates.py`;
- `config/source_coverage_scopes.json`;
- related workbook and `build_missing_mapped_esto_rows.py` changes.

Requirements:

- candidates are review-only;
- never write candidates automatically into `config/outlook_mappings_master.xlsx`;
- keep incomplete, ambiguous, zero-only, or one-axis-only findings unresolved;
- verify raw and after-rollup cardinality, source relevance, hierarchy scope, and exception status;
- keep candidate outputs copy-ready and narrow;
- add tests for every changed inference rule;
- if workbook edits already exist, determine whether they are reviewed, provisional, or unrelated before committing.

Commit this phase separately if it is coherent and verified.

## Phase 2 — clean production baseline

After Phase 1 is settled, run the affected mapping stages and refresh the canonical outputs. Validate provenance and ensure the validation summary refers to the current comparison input modification time.

At minimum inspect:

- `results/common_esto/common_esto_output_status.csv`;
- `results/common_esto/common_esto_comparison_data.csv`;
- `results/tree_structure/common_esto_validation_summary.csv`;
- `results/tree_structure/common_esto_validation.csv`;
- source-parent anchor validation summaries;
- mapping coverage and candidate QA outputs.

Separate:

- real mapping defects;
- inherited source-data inconsistencies;
- intentional detached/non-expanding rollup boundaries;
- stale or skipped validations;
- small numerical noise.

Do not fix a failure merely because it appears in an old report.

## Phase 3 — anchor-validator reliability and mirror-row-gap work

Use the design document as a design gate, not as permission to implement blindly.

Investigate and then implement, if justified:

- source inconsistency flag propagation for mirror-row gaps;
- the distinction between genuine failures and unreliable comparisons;
- the existing `inheritance_eligible` gate;
- whether the anchor validator should augment results with flags rather than reclassify rows as skipped;
- compatibility with all current consumers of `source_internal_recursive_sum_inconsistency`;
- diagnostic-file consolidation only after exact filename readers have been audited.

Before changing status semantics, grep the whole repository for every consumer and add regression tests. Verify with real-data A/B comparisons that no genuine current failures are silently reclassified. The desired states are:

1. passed/reconciles;
2. failed/action required;
3. unreliable/flagged, not silently treated as passed or skipped.

The dashboard impact belongs in the sibling `leap_dashboard` repository and should be documented as a cross-repo follow-up unless explicitly requested.

## Phase 4 — re-triage anchor residuals

Recheck the old residual families against the fresh baseline before fixing anything:

- passenger-road skip bucket;
- ESTO `10 Losses` / `10.01 Own Use`;
- product-axis `frontier_rows_absent`;
- `12_solar` allocation gap;
- silent-exception logging;
- any remaining shared-frontier or component-lineage anomalies.

Use representative rows, raw data, tree structure, rollup metadata, mapping relationships, and lineage. Prefer narrow fixes with real-data regression tests. Do not port branch changes from `claude/anchor-validator-fixes` wholesale; compare commits and cherry-pick or reimplement only the verified pieces.

## Phase 5 — semantic mapping and human-review queues

Review, but do not silently approve:

- the 4-row `review_queue` in `config/esto_external_definition_authority_working_set.xlsx`;
- the 109 `product_leaks` rows;
- actionable partial-coverage findings;
- non-zero unmapped LEAP branches;
- source presence conflicts;
- Common ESTO edges absent from the raw ESTO tree.

For each proposed mapping change, record the decision in `docs/special_rules_and_design_decisions.md` when it is a human semantic rule. Use the narrowest mapping/configuration correction and rerun the affected stages. Never populate the canonical workbook from generated candidates without explicit review authority.

## Phase 6 — canonical migration and workflow quality

Audit and, where safe, complete:

- remaining `master_config.xlsx` references;
- legacy `leap_utilities` fallbacks;
- required canonical sheet/column validation;
- notebook-safe orchestration for `codebase/run_mapping_pipeline.py`;
- explicit top-level workflow toggles and path resolution;
- configurable comparison scopes;
- glossary and pipeline diagrams;
- prompt archiving and results-folder cleanup.

Do not combine these housekeeping changes with semantic mapping changes in one commit.

## Required verification and handoff

For every implementation phase:

1. add or update focused tests;
2. run the focused tests;
3. run the broader relevant test suite;
4. verify real-data output where the change affects pipeline behavior;
5. inspect the diff for unrelated edits;
6. commit only files owned by this phase;
7. report remaining failures and whether they are code defects, source inconsistencies, human-review items, or stale artifacts.

Use commit messages prefixed with `codex:`. Preserve unrelated worktree modifications and explicitly list them in the handoff. Archive completed prompts from `docs/prompts/` into `docs/archive/` only when the work is genuinely complete, tested, and committed, and update `docs/prompts/AGENTS.md` in the same commit.

## Stop conditions

Stop and ask the user for a decision when:

- a workbook mapping change is semantically ambiguous;
- multiple valid comparison frontiers are possible;
- a proposed reliability flag would alter dashboard meaning;
- a branch contains changes that may belong to another active agent;
- a destructive cleanup would remove potentially useful diagnostics;
- a full production run requires a materially different input or external coordination.

The final handoff should state what was completed, what remains, the exact validation evidence, commit IDs, and any preserved unrelated changes.
