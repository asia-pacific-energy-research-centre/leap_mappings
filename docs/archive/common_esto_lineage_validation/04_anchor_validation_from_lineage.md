# Prompt 4: anchor validation from contribution lineage

Work in `C:\Users\Work\github\leap_mappings`. Complete Prompts 1-3 first.

## Goal

Validate that parent totals from LEAP, Ninth and ESTO survive mapping into the
common structure, using exact contribution lineage rather than reconstructing
frontiers from strings or summing broad common rows blindly.

## Required coverage

For all three source systems, validate both applicable axes:

- flow/sector parents;
- fuel/product parents.

Checks must operate by source system, economy, scenario, year and comparison
scope. A source anchor may be validated only where its lineage represents a
complete common boundary. Broad common rows containing unrelated contributions
must not be used as substitutes for exact source descendants.

## Validation modes

1. `structural`: no values; mapping/tree/lineage-template checks only.
2. `slice`: one economy and selected boundary years; default numeric mode.
3. `full`: all requested partitions; explicit expensive mode.

Process slice and full validation partition by partition. Maintain summaries
incrementally. Do not accumulate all detail records in memory.

## Outputs

Always produce final CSVs for:

- validation summary;
- failure detail;
- unmatched/unanchorable boundaries;
- partition status and value accounting.

Full passed-row detail must be optional. The default should store counts and a
small deterministic sample of passes rather than tens of millions of rows.

Use actionable reasons such as incomplete lineage, missing mapped child,
common boundary contamination, rows absent, difference outside tolerance,
source-tree inconsistency and no anchorable boundary.

## Preserve prior work

Retain Claude's verified performance improvements where they still apply:
caches, indexed lookups, scope-loop hoisting, economy normalization and slice
selection. Remove any now-obsolete duplicate frontier logic.

## Tests and verification

- Exact parent/children pass.
- Missing child fails with the child identified.
- Broad common-row contamination is rejected rather than overcounted.
- LEAP Road validates through explicit rollup evidence.
- Ninth and ESTO validate through tree evidence.
- Both axes are covered.
- Slice/full partition results match a small in-memory reference.
- Empty validation is not reported as passed.

Run the USA slice and classify remaining failures. Do not call a high failure
rate acceptable without inspecting representative records from every reason.

## Success criteria

- No prefix inference remains.
- Anchor validation covers LEAP, Ninth and ESTO.
- It uses exact lineage and bounded memory.
- Slice results are semantically credible and tests pass.
- Commit only this prompt's changes with a `codex:` commit.

