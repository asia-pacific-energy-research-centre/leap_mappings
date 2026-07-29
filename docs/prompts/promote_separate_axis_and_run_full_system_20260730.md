# Prompt: Promote the separate-axis mappings and validate the full system

Work across:

- `C:\Users\Work\github\leap_mappings`
- `C:\Users\Work\github\leap_dashboard`
- read `C:\Users\Work\github\leap_initialisation` only when needed to resolve
  LEAP export-template or detailed-model-row authority.

## Task type

This is a production integration, controlled mapping-contract promotion,
full-data pipeline run, all-economy dashboard render, and diagnostic audit.
Complete the work rather than only writing a plan.

## Outcome

Merge the completed separate-axis and mapping-diagnostic changes into
`leap_mappings/master`. Make the human-edited single-axis workbook the
upstream mapping authority and generate the pair authority and compatibility
master before the existing mapping stages. Run the complete mapping pipeline
for ESTO, ESTO Extended, LEAP, and Ninth, then render and validate the
production Common ESTO dashboard for every economy present in the successful
new output.

The dashboard must consume the exact Common ESTO run produced by this task.

## Non-negotiable boundaries

- Read each repository's `AGENTS.md` and the mappings documentation before
  editing or running anything.
- Run `git status --short --branch` in every repository and preserve unrelated
  user changes.
- Use `C:\Users\Work\miniconda3\python.exe`.
- Do not push.
- Commits and merges required to integrate these explicitly requested changes
  are authorised. Commit only scoped source, configuration, workbook, test,
  and documentation changes. Do not commit generated run outputs unless the
  repository explicitly tracks the particular evidence file.
- Do not represent a skipped, unavailable, empty, stale, or errored validation
  as passed.
- Do not silently drop non-zero source rows or automatically insert unresolved
  candidates into an editable mapping authority.
- Do not restart or terminate a healthy long-running process because it is
  quiet.
- Do not use Excel checkbox controls or checkbox formatting. Maintained Boolean
  cells must reopen as literal Boolean `TRUE` or `FALSE` values with ordinary
  surrounding-cell formatting.
- Preserve the prior canonical workbook in Git history and record its hash so
  promotion can be reverted directly.

## Phase 1 — Integrate the completed changes

1. Inspect the completed branches and their diffs:
   - `codex/separate-axis-mapping-exploration`
   - `codex/refactor-stage-zero-maintenance`
2. Confirm each branch is clean and identify current `master`.
3. Merge both completed change sets into `leap_mappings/master`. Resolve
   conflicts by preserving:
   - registry-driven multi-dataset orchestration;
   - exact human-confirmed anchor exceptions and the confirmed/unconfirmed
     numerical failure split;
   - review-only focused maintenance after retirement of mutating Stage 0;
   - the separate-axis compiler, generated pair authority, non-expanding
     subtotal rules, source-once checks, and memory-bounded conversion/value
     application.
4. Run focused integration tests before promotion.
5. Record the merge commits and verify `master` contains both branch tips.

Stop for a user decision only if resolving a conflict would change mapping
semantics beyond those already accepted in the two branches.

## Phase 2 — Turn the separate-axis prototype into the production first step

The production ownership contract is:

- one human-edited workbook containing only the six single-axis relation sheets
  and four accepted-extra-pair sheets;
- one generated exact-pair authority workbook in `config/`, visibly marked
  computer-generated and not for editing; and
- `config/outlook_mappings_master.xlsx` as the generated compatibility
  workbook consumed by existing code.

Implement or finish one notebook-safe refresh workflow that:

1. Reads the human-edited single-axis workbook.
2. Refreshes LEAP structural pairs when any contributing economy export
   template or detailed demand/power row inventory fingerprint changes.
3. Uses final-year ESTO non-zero evidence and post-boundary Ninth non-zero
   evidence, plus reviewed extra pairs and valid rollup-derived exact pairs.
4. Generates the pair-authority workbook.
5. Compiles all three pair sheets:
   - `leap_combined_esto`
   - `leap_combined_ninth`
   - `ninth_pairs_to_esto_pairs`
6. Preserves the required non-pair sheets and exact downstream schemas.
7. Writes candidate workbooks to temporary paths, reopens and validates them,
   and only then atomically promotes the compatibility workbook to
   `config/outlook_mappings_master.xlsx`.
8. Records input hashes, source fingerprints, output hashes, row counts,
   compiler policy, temporal boundary, provisional relationship count, and
   timestamp in a narrow machine-readable manifest.
9. Leaves editable files untouched during ordinary refreshes.

Before promotion, verify:

- all 7,649 previously maintained relationships are reproduced or any delta is
  deliberately documented;
- all 3,501 provisionally accepted relationships remain labelled
  `provisionally_accepted`;
- the eight within-axis many-to-many components remain explicit review debt;
- all mapping Boolean columns contain real Boolean values after save and
  reopen, with no checkbox or masking formats;
- the generated master has the expected 14 sheets and exact pair-sheet headers;
- the generated and prior canonical workbook hashes and relationship counts
  are recorded;
- direct reviewed subtotal targets use the accepted non-expanding rule, while
  rollup-derived targets do not become manual source-aggregate edges;
- a source pair cannot be delivered to multiple additive Common rows;
- rollback is a documented one-file Git restore plus regeneration procedure.

Do not merely copy the old prototype workbook over the canonical file. The
post-merge compiler must regenerate it and pass these gates first.

## Phase 3 — Run the full mapping pipeline

Run the production workflow from the promoted mapping authority for:

- ESTO
- ESTO Extended
- LEAP
- Ninth
- generated Common ESTO

Do not use the shadow workflow and do not use `skip_deep_validation`. Run every
required production stage, including source parsing/conversion, Common
structure generation, value application, hierarchy validation, parent-anchor
validation, rollup QA, mapping coverage, and structural QA. Use the
memory-bounded economy/source batching already validated by the separate-axis
work.

There is no mutating general Stage 0. Run the separate-axis refresh first, then
the maintained focused review/preview workflows where relevant, followed by
the production mapping stages.

### Monitoring

Run each long step in the background with a clearly named process and its own
log. Poll only once every 20 minutes while it is healthy. At a poll, inspect
only process state, a simple CPU/progress signal, memory headroom, and the last
20–40 log lines. Unchanged output is not itself a failure.

If a process actually fails, diagnose the smallest in-scope cause, record the
failure and intervention, rerun the affected stage, and continue. Stop rather
than guessing when a fix would make a new mapping-semantic decision.

### Mapping and registry gates

Verify all of the following against the new run:

1. Every required mapping stage completed for all four source systems. No
   skipped or errored validation is reported as passed.
2. The selected output contract, timestamps, hashes, and run provenance refer
   to this run rather than a preserved earlier run.
3. The production dataset manifest enables `ESTO`, `ESTO_EXTENDED`, `LEAP`,
   `NINTH`, and generated `COMMON_ESTO`.
4. `SYNTH_BALANCE` and `synth_balance_comparison` remain disabled and are
   absent from the production run manifest and published rows.
5. These four comparison scopes were rebuilt:
   - `esto_leap`
   - `esto_extended_leap`
   - `esto_leap_ninth`
   - `esto_extended_leap_ninth`
6. Every scope contains exactly its registered source systems. No unknown
   source or scope is admitted through fallback behaviour.
7. The manifest records the dataset, value-adapter, mapping-sheet,
   rollup-sheet, diagnostic-adapter, comparison-scope, scenario-policy, and
   period-policy versions.
8. Manifest provenance covers the current registry CSVs, promoted mapping
   workbook, source datasets, and generated Common ESTO contract.
9. All registered Stage 3 artifacts are present, non-empty, readable, and
   consumed:
   - ESTO exact rows
   - ESTO Extended exact rows
   - LEAP converted rows
   - Ninth converted rows
10. Value is conserved for every source system by economy, scenario, and
    period before and after Common ESTO application. Report maximum absolute
    error and every group outside tolerance.
11. Mapped source aggregates are not allocated into finer Common rows. A
    detailed dataset may roll up to a coarser boundary, but a coarse value must
    never be split.
12. Stage 3 lineage retains source system, native pair, canonical component,
    aggregate group, Common row, scenario, economy, period, unit, and run ID
    wherever applicable.
13. Normalised values are PJ. Every non-PJ source has registered conversion
    provenance.
14. Unmapped non-zero rows remain in bounded review outputs. They are not
    silently dropped, force-mapped, or counted as successful coverage.
15. QA distinguishes manually specified rollups from graph-generated Common
    aggregation. Generated groupings are not written back as unreviewed manual
    rollups.
16. Common-row IDs, relationship IDs, source-system names, scope names, and
    dashboard-facing fields have not been unexpectedly renamed.
17. Record new Stage 1, Stage 2, Stage 3, component, relationship, fact,
    metadata, and lineage counts. Explain every material delta from the last
    accepted baseline; do not require the old hash blindly because promotion
    intentionally changes relationship membership.

### Anchor and hierarchy gates

Verify:

- anchor detail contains `exception_review_status`, `exception_id`, and
  `source_non_additivity_observed`;
- anchor summary contains `failed`, `confirmed_issue_failed`,
  `unconfirmed_failed`, and `source_non_additivity_observed`;
- for every summary scope,
  `failed = confirmed_issue_failed + unconfirmed_failed`;
- confirmed source issues remain numerical failures rather than being converted
  to passed or skipped rows;
- only exact, enabled, human-confirmed contexts are confirmed;
- removed PRC contexts have not resurfaced as confirmed;
- automatically observed source non-additivity is evidence only and does not
  confirm an exception;
- hierarchy, anchor, rollup, mapping-coverage, and structural outputs are
  present and readable;
- zero-result or empty validations are labelled skipped, unavailable, or
  errored—not passed.

Report material failures and unresolved findings; do not hide them.

## Phase 4 — Render and validate every dashboard economy

Use the successfully published Common ESTO data to derive the available
economy list. Do not rely on a hard-coded economy list.

Render every available economy with:

- main dashboard HTML;
- economy-specific diagnostics page;
- Plotly assets;
- `chart_manifest.csv`; and
- `page_assignment_summary.csv`.

Then verify:

1. The dashboard input manifest and displayed provenance select the exact new
   mapping run ID, not an independently selected older “latest” artifact.
2. Each diagnostics page is scoped to its own economy. Failure cards, ranked
   failure tables, confirmed issues, unconfirmed failures, and exception
   candidates contain no rows from another economy.
3. Wording does not claim that a confirmed source issue proves a mapping is
   correct or caused an anchor mismatch.
4. The pipeline-health report uses the confirmed/unconfirmed review split while
   retaining every numerical failure in critical-status assessment.
5. Publication-readiness and page-noise checks run for all outputs; report
   every failure and warning.
6. Logs contain no unreported exceptions, missing artifacts, unexpected
   row-count collapse, duplicate output, or memory-related failure.

## Phase 5 — Evidence, documentation, and completion

Write a concise run report under `docs/` or the repository's maintained run
evidence location containing:

- integration and promotion commit IDs;
- prior and promoted mapping-workbook hashes;
- mapping and dashboard run IDs and timestamps;
- every economy rendered;
- new relationship/Common/fact/metadata/lineage counts and explained baseline
  deltas;
- total, confirmed, and unconfirmed anchor failures by comparison scope and
  source system;
- every failed, skipped, unavailable, or empty validation;
- value-conservation and source-once results;
- unresolved mapping, hierarchy, rollup, coverage, semantic, and publication
  findings;
- publication-readiness and page-noise results;
- commands or stages that failed or required intervention;
- paths to primary mapping artifacts, dashboards, diagnostics pages,
  pipeline-health report, logs, and error outputs;
- confirmation of exactly what was committed and that nothing was pushed.

After the run is genuinely complete:

1. update the mapping and dashboard documentation to describe the production
   separate-axis first step and the shared run-provenance contract;
2. move this prompt and its findings into `docs/archive/` according to the
   prompt-folder policy;
3. run focused tests and repository-appropriate final checks;
4. commit only the completed scoped changes; and
5. leave both repositories clean, or document every intentional uncommitted
   file.

## Completion definition

This task is complete only when:

- both mapping feature sets are in `leap_mappings/master`;
- the regenerated separate-axis compatibility workbook is the production
  mapping contract with a tested rollback;
- the full non-shadow four-source mapping pipeline has completed;
- deep mapping, hierarchy, anchor, rollup, coverage, registry, provenance,
  value-conservation, and source-once diagnostics have been audited;
- every economy in the new data has a validated dashboard and diagnostics page;
- the health/publication checks use the same new run;
- material failures and semantic review debt are explicitly reported; and
- scoped changes are committed locally with no push.
