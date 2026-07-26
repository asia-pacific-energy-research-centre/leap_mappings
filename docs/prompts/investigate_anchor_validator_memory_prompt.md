# Investigate and reduce source-parent anchor-validator memory use

## Objective

The latest Stage 3 source-parent anchor-validation run was not a clean result.
It was skipped after a `MemoryError`:

```text
results/tree_structure/source_parent_anchor_validation_summary.csv
run_id: common_esto_20260726T071137620288Z
status: skipped
reason: memory_error
```

Investigate where peak memory is consumed in
`codebase/mapping_tools/source_parent_anchor_validation.py`, then implement the
smallest verified reduction that lets the real full validation complete. Do not
weaken the validation, silently omit rows, or turn a failed/unknown run into a
clean result.

## Scope and ownership

Work in `C:\Users\Work\github\leap_mappings`.

Before editing:

1. Read `AGENTS.md`, `C:\Users\Work\.codex\AGENTS_BALANCE_TABLES.md`, and
   `C:\Users\Work\.codex\AGENTS_LEAP_EXPORT.md`.
2. Run `git status --short`, inspect recent commits, and preserve all existing
   workbook, source-coverage, and temporary-file changes as user/other-agent
   work.
3. Treat `config/outlook_mappings_master.xlsx` and the exception workbook as
   read-only for this task. This is a validator-performance investigation, not
   a mapping-design or workbook-maintenance task.
4. Do not overlap a Stage 1–3 run already in progress.

## Required diagnosis

Establish an evidence-backed memory profile before proposing an optimisation.
Use process RSS/working-set measurement (for example `psutil`) around major
phases; `tracemalloc` alone is insufficient for pandas/NumPy allocations.

At minimum measure and record row counts, dataframe memory usage, and peak RSS
after:

1. `load_raw_source_anchor_inputs()` and its long-format raw-source frames;
2. reading/filtering `common_esto_comparison_data.csv` and Common ESTO rows;
3. each source system and validation axis inside
   `validate_source_parent_anchors()`;
4. frontier-ID expansion and comparison merges;
5. raw-fallback merges;
6. building context-detail artifacts, especially
   `build_failed_anchor_mapped_component_context_values()`.

Use a reduced real-data slice first if necessary, then confirm the same
pressure point on the full inputs. Record the run ID/input provenance used.

## Candidate approaches to assess

Choose only the smallest approach supported by the profile. Possible options:

- narrow only locally created dataframes to required columns and numeric dtypes;
- avoid retaining full source frames after their system/axis result is emitted;
- process source system/axis/economy chunks and append output incrementally;
- avoid materialising large Cartesian/expanded join frames when grouped lookup
  or partitioned joins yield the same result;
- calculate summary/detail outputs in separate passes only if that reduces peak
  memory and preserves identical findings;
- defer the large mapped-component context artifact to failed anchor contexts
  only, with the same resolver and data-availability rules as the validator.

Do **not** use these as solutions:

- `MemoryError` catch-and-write-empty-output behaviour;
- reducing checked years, economies, systems, or scopes in the production run;
- changing tolerances, exceptions, mapping rows, or status semantics;
- writing generated candidates into a workbook.

## Correctness and regression requirements

1. Add a focused regression test that proves the memory-oriented code path
   returns the same anchor rows, values, statuses, and frontier totals as the
   pre-change path on a representative fixture.
2. Run `C:\Users\Work\miniconda3\python.exe -m pytest
   tests/test_source_parent_anchor_validation.py -q`.
3. Run any directly affected tests for raw-input loading or Stage 3 orchestration.
4. Execute a reduced real-data validation comparison before/after and report
   equality/differences explicitly.
5. Once the change is stable, run the full Stage 3 validation (or the full
   requested pipeline) once, record elapsed time and peak RSS, and verify that
   `source_parent_anchor_validation_summary.csv` reports a completed status
   with non-zero eligibility where input data exists.
6. Confirm the dashboard-facing anchor artifacts are regenerated and no longer
   make a skipped validation look like zero failures.

## Expected handoff

Commit only files owned by this task using a `codex:` commit message. Provide:

- the measured peak-memory culprit and evidence;
- the chosen optimisation and why alternatives were rejected;
- before/after runtime, peak RSS, and output row-count parity;
- test commands/results;
- resulting completed/skipped anchor-validation summary;
- unrelated files preserved untouched;
- any remaining memory limit or human decision.

## Stop and ask for human input when

- the only viable solution changes mapping semantics or comparison coverage;
- the full run still exhausts available memory after a verified local reduction;
- a required output must be dropped, sampled, or moved to a separate optional
  run;
- ownership overlaps with another active validator or pipeline change.
