# Prompt 3: partitioned value application and source lineage

Work in `C:\Users\Work\github\leap_mappings`. Complete Prompts 1 and 2 first.

## Goal

Apply the compiled structural artifacts to large value datasets with bounded
memory while preserving exact source-to-common contribution lineage.

## Processing contract

Use partitions that contain complete validation groups:

```text
source_system x economy x scenario x year
```

Load mapping and tree artifacts once. Process one value partition at a time,
aggregate early, write incrementally and release memory before continuing.

## Required work

1. Add a reusable cache/preparation workflow that converts large source inputs
   to partitioned Parquet. Cache validity must depend on source identity such
   as path, size, modification time and preferably a content fingerprint.
2. Read only required columns and use numeric/categorical or dictionary-backed
   dtypes where practical.
3. Join each partition to `source_pair_to_common_row.csv`; do not rebuild the
   mapping structure during value processing.
4. Preserve a contribution-lineage dataset before final aggregation with:
   - source system, economy, scenario and year;
   - original source flow/product;
   - source parent/child identity where applicable;
   - effective rolled flow/product;
   - rollup and relationship identifiers;
   - ESTO component pair;
   - comparison scope and common row;
   - numeric value.
5. Produce the final human-facing common comparison CSV. Parquet is an
   internal optimization, not a replacement for the final CSV.
6. Produce unmatched-source and value-accounting CSVs. Show mapped, unmatched,
   excluded and input totals by partition.
7. Keep detailed and rolled views distinguishable so they cannot be added
   together accidentally.

Use partitioned pandas first. Introduce DuckDB only if measured pandas runtime
or peak memory remains unacceptable, and document the dependency and reason.

## Tests and verification

- Chunked and single-partition results must be numerically equivalent.
- Passenger + Freight road must produce Road without losing detailed lineage.
- Numeric strings must sum numerically.
- Re-running with a valid cache must avoid reparsing source files.
- Interrupted runs must not leave a final CSV that appears complete.
- Final ordering and numeric formatting must be deterministic.

Run a USA/boundary-year slice and report runtime, peak memory if measurable,
row counts and value-accounting totals. Do not run the full dataset yet.

## Success criteria

- Peak memory is bounded by one partition plus small structural tables.
- Every final common value is traceable to source contribution rows.
- The final CSV remains available and compatible with downstream consumers.
- Tests and the slice pass.
- Commit only this prompt's changes with a `codex:` commit.

