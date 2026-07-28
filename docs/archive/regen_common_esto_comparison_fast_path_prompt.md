# Prompt: fast-path regen for `common_esto_comparison_data.csv`

Repo: `C:\Users\Work\github\leap_mappings`. Read `AGENTS.md` first and follow the repo conventions.

## Goal

Create a notebook-safe fast path that regenerates the Common ESTO comparison outputs from already-prepared intermediate files.

This prompt is for the **regen-only** path. It must not re-run expensive upstream stages or any validation that depends on re-deriving the pipeline:

- Stage 0 workbook maintenance
- Stage 1 relationship building
- Stage 2 common-row structure building
- tree generation
- recursive consistency checks
- source-parent anchor validation
- QA outputs that are only meaningful when the pipeline is rebuilt from scratch

## Required behavior

Implement a small workflow entrypoint, likely under `codebase/`, that:

1. Reads the cached intermediate files already produced by the main mapping pipeline.
2. Reconstructs the Common ESTO comparison tables from those cached inputs only.
3. Writes the final comparison outputs back to `results/common_esto/`.
4. Avoids all unnecessary prep, diagnostics, and validation work.

Expected outputs:

- `results/common_esto/common_esto_comparison_data.csv`
- `results/common_esto/common_esto_comparison_wide.csv`

If the existing pipeline also writes a lightweight manifest or status file and it can be preserved without pulling in QA logic, keep it. Do not add new diagnostics.

## Inputs to use

Use the already-generated cached files, not raw exports and not the source workbook:

- `results/mapping_relationships/leap_results_converted_to_esto.csv`
- `results/mapping_relationships/ninth_results_converted_to_esto.csv`
- `results/mapping_relationships/esto_results_exact_rows.csv`
- `results/common_esto/common_esto_rows.csv`

If another cached file is truly required for the final comparison output, keep that dependency minimal and explain why.

## Constraints

- Preserve the existing schema and row semantics of `common_esto_comparison_data.csv`.
- Do not change mapping logic.
- Do not change workbook contents.
- Do not add tree generation or recursive validation.
- Do not add extra CSVs unless they are clearly part of the minimal fast path.
- Keep the workflow notebook-safe with the repo's `#%%` block style and top-level toggles.

## Implementation approach

Prefer extraction over duplication:

1. Refactor the existing Stage 3 row assembly so it can be called independently.
2. Add a thin workflow wrapper that calls only the row assembly and final writers.
3. Confirm the full pipeline still works unchanged.

## Verification

Run the new fast path once against the current cached inputs and confirm:

- both comparison CSVs are written;
- no QA or validation artifacts are produced by the fast path;
- row counts look sensible relative to the current Stage 3 outputs;
- the fast path is materially faster than the full pipeline.

If the workflow reuses existing cached outputs without recomputing the expensive parts, state that explicitly.

## Reporting

Report:

- the new workflow file path;
- the exact inputs it reads;
- the exact outputs it writes;
- what was deliberately excluded from the fast path;
- whether the full pipeline still works unchanged.

## Extra item

If it is low-risk and does not make the dashboard slow by default, add a small opt-in hook in the Common ESTO dashboard workflow so `codebase/common_esto_dashboard_workflow.py` can trigger this fast-path regen before rendering when explicitly requested.

Keep that hook minimal and gated behind a clear flag or environment variable. Do not make dashboard rendering depend on a regen run by default.
