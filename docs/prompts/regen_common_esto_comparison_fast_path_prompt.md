# Prompt: create a fast-path regen workflow for `common_esto_comparison_data.csv`

Repo: `C:\Users\Work\github\leap_mappings`. Read `AGENTS.md` first and follow repo conventions.

## Goal

Create a standalone, notebook-safe workflow that regenerates the Common ESTO comparison outputs quickly when the upstream LEAP-converted source tables already exist.

This is a fast path only. It must **not** run:

- Stage 0 workbook maintenance
- Stage 1 relationship building
- Stage 2 common-row structure building
- tree validation
- source-parent anchor validation
- any QA or diagnostic validation that depends on re-deriving the pipeline

The workflow should only rebuild the final comparison outputs from already-prepared intermediate files.

## What the workflow should do

Implement a new workflow entrypoint, likely under `codebase/`, that:

1. Reads the cached Stage 3 input tables already produced by the mapping pipeline.
2. Re-applies the Common ESTO structure to those cached inputs.
3. Writes the final comparison outputs back to `results/common_esto/`.
4. Keeps the runtime as small as possible by avoiding any unused prep, QA, or validation steps.

The intended outputs are:

- `results/common_esto/common_esto_comparison_data.csv`
- `results/common_esto/common_esto_comparison_wide.csv`

Optionally preserve the existing output-status manifest if it is cheap and does not pull in QA logic, but do not add any validation artifacts.

## Expected inputs

Use the already-generated intermediate files, not raw LEAP balance exports and not the source workbook:

- `results/mapping_relationships/leap_results_converted_to_esto.csv`
- `results/mapping_relationships/ninth_results_converted_to_esto.csv`
- `results/mapping_relationships/esto_results_exact_rows.csv`
- `results/common_esto/common_esto_rows.csv`

If the current implementation needs any additional cached file to build the final comparison output, keep that dependency minimal and explain why it is necessary.

## Design constraints

- Preserve the existing output schema and row semantics of `common_esto_comparison_data.csv`.
- Do not change mapping logic.
- Do not change workbook contents.
- Do not add tree generation or recursive consistency checks.
- Do not add extra CSVs unless they are required for the final comparison output and are clearly part of the minimal fast path.
- Keep the workflow notebook-safe with the repo's standard `#%%` block style and top-level toggles.

## Implementation guidance

The cleanest implementation is probably:

1. Refactor the existing Stage 3 application logic so the row-assembly step can be called independently.
2. Add a new small workflow wrapper that calls only that row-assembly step and the final writers.
3. Make sure the normal full pipeline still works unchanged.

If there is a choice between copying logic and extracting a shared function, prefer extraction.

## Verification

Verify the new workflow by running it once against the current cached inputs and confirming that:

- both comparison CSVs are written;
- no QA or validation outputs are produced by the fast path;
- the output row counts are sensible relative to the current Stage 3 outputs;
- the workflow finishes materially faster than the full pipeline path.

If the workflow can reuse existing cached outputs without recomputing the expensive parts, say so explicitly in the report.

## Reporting

At the end, report:

- the new workflow file path;
- the exact inputs it reads;
- the exact outputs it writes;
- what was deliberately excluded from the fast path;
- whether the full pipeline still works unchanged.
