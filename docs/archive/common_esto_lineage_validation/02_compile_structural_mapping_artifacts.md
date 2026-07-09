# Prompt 2: compile reusable structural mapping artifacts

Work in `C:\Users\Work\github\leap_mappings`. Complete Prompt 1 first.

Read `AGENTS.md` and the relevant sections of `docs/mappings_system.md`.
Inspect the worktree before editing and do not include unrelated workbook
changes in the commit.

## Goal

Create an independent, value-free compilation workflow that builds reusable
mapping artifacts without loading all economies, scenarios, years or values.

## Required outputs

Write narrow CSV artifacts with stable schemas and deterministic ordering:

- `source_pair_to_esto_component.csv`
- `esto_component_to_common_row.csv`
- `source_pair_to_common_row.csv`
- `common_row_to_source_pairs.csv`
- a structural compilation summary CSV;
- unresolved, ambiguous, cyclic and duplicate structural QA CSVs.

The source-pair artifacts must include source system, original pair, effective
rolled pair, comparison scope, relationship/rule identifiers and evidence
type. `common_row_to_source_pairs.csv` represents membership only. It must not
allocate a common-row value back to children.

## Constraints

- Inputs may include the workbook, generated trees, unique category pairs and
  existing Stage 1/2 structural artifacts.
- Do not load complete value tables.
- Refactor and reuse existing Stage 1/2 functions; do not rewrite the mapping
  pipeline.
- Keep compilation callable independently from `run_mapping_pipeline.py` and
  notebook-safe.
- Fail early on missing columns or incompatible artifact versions.
- Record a structural mapping version or reproducible input fingerprint.

## Tests and verification

- Test both mapping directions for LEAP, Ninth and ESTO.
- Test rollup-derived and graph-generated common rows.
- Test deterministic output under shuffled input order.
- Test that reverse membership does not imply value allocation.
- Confirm compilation does not read the large source value files, using mocks
  or dependency injection rather than timing alone.

## Success criteria

- Structural compilation runs independently and quickly.
- Bidirectional membership is inspectable from CSV files.
- No economy/year values are required.
- Tests pass; schemas and output locations are documented.
- Commit only this prompt's changes with a `codex:` commit.

