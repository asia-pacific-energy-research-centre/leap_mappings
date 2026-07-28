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

The implementation uses bounded hash partitions rather than materializing Python dictionaries for
every row. Full-frame work is limited to compact integer partition IDs. Each partition builds
null-safe, scalar-type-aware identity keys and performs a vectorized one-to-one join; only affected
row positions are retained between partitions. The default target is approximately 100,000 rows
per partition, and tests can provide an explicit `partition_count` without changing the existing
DataFrame input/output API.

## Downstream semantics

This representation preserves the separate `ESTO_EXTENDED` source axis required by Common ESTO
comparison scopes. Stage 3 can receive the reconstructed frame with the same schema and values it
receives today.

The optimization applies only to the recurring finalized exact-row artifact. It does not replace
`data/esto_extended.csv`, which is still read independently to build the Extended hierarchy and
raw-source anchor inputs.

The current fast-path workflow does not include ESTO Extended among its cached sources, so no
fast-path behavior is changed by this investigation.

## Evidence

The producer and consumer paths were inspected in code. Synthetic samples verify:

- unchanged rows inherited by source relabelling;
- new rows and changed values represented by `upsert`;
- former leaves represented by `delete`;
- rollup IDs retained as part of row identity; and
- null identities kept distinct from literal empty/`"nan"`/`"<null>"` strings;
- duplicate identities rejected in base, Extended, and delta inputs; and
- exact reconstruction after mixed operations through multiple partitions.

The 2026-07-28 isolated measurement used matching Stage 3 exact-row artifacts without modifying
the live checkout. The 5,320,932-row Extended file was 24,448,125 compressed bytes. Its exact
552,126-row delta (338,436 deletes and 213,690 upserts) was 3,445,322 bytes, or 14.092% of the
full file. Exact reconstruction passed a bounded identity-and-value comparison across every row.
Reading took 14.726 seconds, delta construction 84.585 seconds, and reconstruction plus comparison
129.897 seconds.

## Remaining requirements before changing defaults

The isolated measurement completes the storage-size and exact-reconstruction gates. Before a
default change:

1. Run the existing Stage 3 application once with the full Extended file and once with the
   reconstructed frame; require identical Common ESTO rows and totals for both Extended scopes.
2. Measure peak memory in that Stage 3 integration; the measured wall time is acceptable, but the
   extra in-memory copy must not worsen reliability.
3. Retain the full-file path as a fallback during migration and add a manifest tying the
   delta to the exact base artifact identity and hash.

No default output or consumer should change until these checks pass.
