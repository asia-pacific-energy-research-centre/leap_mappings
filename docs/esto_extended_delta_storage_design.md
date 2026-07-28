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

The subsequent Stage 3 integration binds the base and delta sizes, schemas, row counts, operation
counts, and SHA-256 values in
`esto_extended_results_exact_rows.delta.json`. The manifest is promoted after exact reconstruction
verification. Stage 3 can explicitly materialize that contract into a temporary gzip CSV; an
invalid contract falls back to the retained full Extended artifact, while an invalid contract
without a full fallback stops the run.

The first real integration comparison exposed an important precision boundary: pandas' default CSV
parser collapsed adjacent float64 text values such as `2.7068499999999998` and `2.70685`. Reading
delta inputs with `float_precision="round_trip"` preserves those distinct values. A regression test
covers this case.

After that correction, the isolated delta-backed Stage 3 run produced exactly the full-file
baseline:

- 3,952,646 fact rows and 6,173 metadata rows;
- identical fact schema, compound key, and decompressed fact SHA-256
  (`7f51fc59af69d938d48501cc6f98b4acf8e07a07afb9776d1a2463d8cd278536`);
- identical metadata SHA-256
  (`46d41147f63d7e9ec147c71c8f58037be6e8b3217a07f66d265ce4c026ea7892`);
- 100% mapped-row aggregation preservation for every scope/source pair.

The shortened corrected run took 1,912.028 seconds, including 1,771.377 seconds for Common ESTO
application and temporary materialization. The maximum sampled process memory was approximately
4.50 GB working set and 6.00 GB private bytes. The prior full-file run's application step was
1,162.107 seconds, so the storage saving currently carries a material runtime cost and remains
opt-in.

## Remaining requirements before changing defaults

The storage, exact reconstruction, and Stage 3 output-equivalence gates are complete. Before a
default change:

1. Exercise the opt-in path during one or two normal publication cycles.
2. Decide whether the 85.9% storage saving justifies the observed Stage 3 runtime increase, or
   optimize materialization/application before enabling it by default.
3. Retain the full-file fallback through that migration period.

No default output or consumer should change until these checks pass.
