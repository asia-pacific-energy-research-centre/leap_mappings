# ESTO Extended base-plus-delta storage design

## Finding

The recurring finalized artifact
`results/mapping_relationships/esto_extended_results_exact_rows.csv.gz` can be represented exactly
as:

1. `esto_results_exact_rows.csv.gz`, with `source_system` relabelled from `ESTO` to
   `ESTO_EXTENDED`; plus
2. a row overlay containing `upsert` and `delete` operations.

An additions-only delta is not exact. `build_esto_extended()` adds new hierarchy children and then
recomputes `is_subtotal`. `run_esto_exact_rows_for_path()` subsequently excludes subtotal rows.
Consequently, a base ESTO row that was formerly a leaf can disappear from the finalized Extended
exact-row artifact when Extended adds children below it.

`codebase/mapping_tools/esto_extended_delta.py` implements the exact overlay in isolation. It does
not change current output defaults.

## Exact-row contract

The helper operates after both datasets have passed through
`run_esto_exact_rows_for_path()`, which is the boundary consumed by Stage 3.

- Base rows must contain only `source_system == ESTO`.
- Extended rows must contain only `source_system == ESTO_EXTENDED`.
- Both inputs must have identical ordered columns.
- Row identity is every column except `source_system` and `value`. This includes economy,
  scenario, year, flow, product, and `non_expanding_rollup_id` when present.
- Duplicate identities are rejected.
- Base rows are inherited after relabelling their source system.
- `upsert` stores a new row or a row whose value changed.
- `delete` removes an inherited base row absent from Extended.

Reconstruction applies the overlay to relabelled base rows. Row order is deliberately not semantic;
the reconstructed row set, identities, values, metadata, and source identity are exact.

## Downstream semantics

This representation preserves the separate `ESTO_EXTENDED` source axis required by Common ESTO
comparison scopes. Stage 3 can receive the reconstructed frame with the same schema and values it
receives today.

The optimization applies only to the recurring finalized exact-row artifact. It does not replace
`data/esto_extended.csv`, which is still read independently to build the Extended hierarchy and
raw-source anchor inputs.

The current fast-path workflow does not include ESTO Extended among its cached sources, so no
fast-path behavior is changed by this investigation.

## Evidence and limits

The producer and consumer paths were inspected in code. Synthetic samples verify:

- unchanged rows inherited by source relabelling;
- new rows and changed values represented by `upsert`;
- former leaves represented by `delete`;
- rollup IDs retained as part of row identity; and
- exact reconstruction after mixed operations.

The data fixtures and live result artifacts were intentionally not scanned or rewritten. They are
not present in this worktree, and the task excludes live-results scanning. Therefore semantic
feasibility is established, but the real compression ratio and runtime cost are not yet measured.

## Required quiet-window measurement before changing defaults

During a future quiet window:

1. Regenerate the existing base and Extended exact-row gzip files with the same pipeline run.
2. Build the overlay from those two finalized frames without replacing either file.
3. Record inherited, upsert, delete, and value-change row counts.
4. Write the overlay as gzip CSV and compare its compressed size with the current full Extended
   gzip file.
5. Reconstruct Extended, sort both frames by the full row identity, and require exact equality of
   every column and value.
6. Run the existing Stage 3 application once with the full Extended file and once with the
   reconstructed frame; require identical Common ESTO rows and totals for both Extended scopes.
7. Measure reconstruction wall time and peak memory. The change is worthwhile only if the storage
   reduction is material and the extra in-memory copy does not worsen Stage 3 reliability.
8. Retain the full-file path as a fallback during any later migration and add a manifest tying the
   delta to the exact base artifact identity and hash.

No default output or consumer should change until all eight checks pass.
