# Prompt: Implement non-expanding rollups and source-branch fallback QA

Work in `C:\Users\Work\github\leap_mappings`.

## Goal

Implement the reviewed `NON_EXPANDING_ROLLUP` design without losing detailed
Common ESTO comparison rows, and add early LEAP-source safeguards for interim
or aggregate branches that could otherwise double count source values.

The implementation must preserve normal graph rollups for genuinely
indivisible mapping constraints. It must not use the Common ESTO graph to
represent intentionally named parent/child subtotal membership.

## Decisions already made

These are settled design decisions, not questions to reopen during the work.

1. `rollup_reason = NON_EXPANDING_ROLLUP` identifies a named derived subtotal.
   It is formed from its normal mapped contributors but **must not create graph
   edges** between those contributors.
2. `parent_flow_label` and `child_flow_labels` describe hierarchy/display
   membership. They are not graph-edge instructions for a non-expanding
   rollup.
3. Products are automatic. For each source system, economy, scenario, year,
   and available product, include the union of products actually present in
   the rollup's mapped contributors. Do not maintain manual product lists or
   use a blanket synthetic product expansion.
4. A non-expanding subtotal and its detailed children are alternative views.
   They must not be added together by additive-frontier or total checks.
5. Keep the existing Stage 2 exclusion of `is_rollup_derived=True` from graph
   edge creation. Do not remove or comment it out. Instead publish QA showing
   the graph edges that were suppressed by this protection, so new structural
   risks remain visible.
6. `Power` remains a `NON_EXPANDING_ROLLUP`; it is not to be disabled merely
   because it contains interim branches.

## Required context and safety checks

Before editing:

1. Read `AGENTS.md`, `docs/mappings_system.md`, `docs/rollup_rules_system.md`,
   and `docs/guide_outlook_mappings_master.md`.
2. Run `git status --short`; preserve unrelated changes. The shared worktree
   is expected to be dirty.
3. Inspect the actual workbook headings in all three rollup sheets. Use the
   existing `rollup_reason` column; do not add an unreviewed workbook column.
4. Do not edit or save `config/outlook_mappings_master.xlsx` automatically.
   Configuration CSVs and code changes are in scope.

## Part A — Non-expanding Common ESTO rollups

Implement a clean, testable path across the normal pipeline stages.

- Read enabled `rollup_reason = NON_EXPANDING_ROLLUP` rules from the LEAP,
  ESTO, and NINTH rollup sheets.
- Retain the ordinary source mappings and detailed Common ESTO rows.
- Emit one stable, named non-expanding Common ESTO subtotal per declared rolled
  category and product actually represented by its mapped contributors.
- Do not add source-aggregate or manual-override graph edges for these rules.
  Their existence must not union the associated ESTO components or cause
  parent/child closure in global flow/product partitions.
- Give non-expanding rows stable IDs and explicit output flags/provenance so
  they can be distinguished from exact rows and graph-generated rows. Preserve
  reverse lineage to the direct contributing source rows and ESTO components.
- Keep ordinary graph-generated rows unchanged. Do not broadly suppress graph
  edges merely because they are associated with a rollup.
- Treat declared parent/child information as display/tree metadata. Ensure
  validation and presentation code cannot accidentally add a non-expanding
  subtotal to its children.

Prefer the smallest extension to the existing Stage 1 relationship artifacts,
Stage 2 structure build, and Stage 3 application/lineage path. Do not create a
parallel second mapping pipeline.

### Required QA

Write narrow, human-readable QA outputs under the existing normal results
locations. At minimum include:

- every configured non-expanding rollup, its rolled identity, source systems,
  contributors, observed products, and output common-row IDs;
- any non-expanding rule whose expected contributor mapping cannot be resolved;
- the graph edges that `is_rollup_derived` rows would have created but were
  deliberately suppressed, including rollup rule/source provenance;
- a check that no non-expanding subtotal is treated as part of an additive
  frontier with one of its declared children.

Use names consistent with existing `qa_common_esto_*.csv` conventions and
document each new output.

## Part B — Interim/standard LEAP branch handling

Add a configuration-owned early source-data preflight and adjustment step. It
must run after raw LEAP values are parsed but before `apply_source_rollups`,
conversion, or Common ESTO application.

Create a clearly named CSV configuration file for alternative branches. Seed
it with these reviewed pairs:

| Standard branch | Interim branch | Action when both are non-zero |
| --- | --- | --- |
| `Electricity Generation` | `Electricity interim` | warn and set interim to zero |
| `CHP plants` | `CHP interim` | warn and set interim to zero |
| `Heat plants` | `Heat plant interim` | warn and set interim to zero |

The test is at whole-sector level for each `economy`, `scenario`, and `year`:
when both branches have any non-zero energy, set **all** interim-product values
for that branch and period to zero in the downstream working data. Do not
alter the parsed raw input file. Write an audit row containing the standard
total, original interim total, suppressed interim total, action, and rule ID.

This is intentionally a visible `warn_and_zero_interim` policy, not silent
deduplication. It applies before the `Power` non-expanding rollup is formed,
so Power receives one branch of each alternative pair.

## Part C — `All demand aggregated` warning and declared components

`All demand aggregated` is an interim-style source branch but does not use the
automatic zeroing policy. Create a separate configuration CSV that explicitly
records which LEAP demand sectors are currently included in its aggregation.

Seed/document the intended sector list through configuration rather than
hard-coding it. It must support the source branches represented by the current
Total final energy consumption rollup, including where applicable:

- Buildings
- Freight road
- Industry
- Other sector
- Passenger road
- Transport non road

For each economy/scenario/year, if `All demand aggregated` has non-zero energy
and any configured included demand sector also has non-zero energy, emit a
highly visible warning/audit record. The warning must list:

- the configured sectors declared to be in `All demand aggregated`;
- which of those sectors were non-zero in that period;
- the All-demand total and each observed sector total;
- a clear reminder that the modeller must confirm the configuration reflects
  which values are actually attributed to `All demand aggregated`.

Do not zero `All demand aggregated` or any detailed demand sector
automatically. This is a review warning because the aggregate may legitimately
be configured to contain only sectors not present elsewhere.

## Tests and verification

Add focused tests for at least:

1. Agriculture/Fishing-style non-expanding rollup: individual rows stay
   separate, the combined subtotal exists, and products are derived from
   observed contributors.
2. A normal graph rollup still unions components as before.
3. A non-expanding parent plus child categories does not produce a graph edge
   or additive-frontier violation.
4. Standard/interim branches both non-zero: interim rows are zeroed only in
   working data and an audit is produced.
5. Interim-only branch: values are retained.
6. `All demand aggregated` plus a configured active detailed sector: a warning
   lists the declared and observed sectors, without changing values.
7. `is_rollup_derived` edges remain excluded from the graph and appear in the
   new suppressed-edge QA.

Run the relevant focused tests first, then the complete mapping test suite if
practical. Run the normal pipeline or the smallest safe full Stage 1–3
equivalent after implementation. Do not save the workbook. Report all known
unrelated warnings separately from regressions caused by this change.

## Documentation

Update the documentation as part of the same change:

- `docs/rollup_rules_system.md`: behaviour, product union, graph-edge
  exclusion, interim fallback preflight, and All-demand warning.
- `docs/mappings_system.md`: explain the distinction between a normal graph
  rollup and a named non-expanding subtotal; list new QA outputs and clarify
  that parent/child fields are not graph instructions for this mode.
- `docs/guide_outlook_mappings_master.md`: editor guidance for setting
  `rollup_reason = NON_EXPANDING_ROLLUP`, plus the restriction that Power-like
  alternative branches require the source-branch configuration.

Keep documentation explicit that the mode is not a way to hide ordinary
mapping problems: use it for retained-detail hierarchy bridges, not for a
genuinely indivisible common comparison category.

## Completion and handoff

- Commit only files created or changed for this task, with a `codex:` commit
  message and verification in the commit body.
- Do not include unrelated dirty workbook, code, documentation, or output
  changes.
- After successful implementation and commit, move this prompt from
  `docs/prompts/` to `docs/archive/` and update `docs/prompts/AGENTS.md` in
  that same commit.
- In the handoff, identify the new configuration files, QA outputs, tests run,
  and any rollup groups requiring human classification before they are marked
  `NON_EXPANDING_ROLLUP`.
