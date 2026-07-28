# Results output storage

This note records the supported storage contract for the largest generated mapping outputs and the
remaining output-reduction work.

## Current contract

The following internal pipeline artifacts are gzip-compressed CSVs. Their schemas and row semantics
are unchanged, and `pandas.read_csv()` reads them directly:

- `results/mapping_relationships/ninth_results_converted_to_esto.csv.gz`
- `results/mapping_relationships/esto_results_exact_rows.csv.gz`
- `results/mapping_relationships/esto_extended_results_exact_rows.csv.gz`
- `results/mapping_relationships/leap_source_to_esto_component_lineage.csv.gz`
- `results/mapping_relationships/ninth_source_to_esto_component_lineage.csv.gz`
- `results/common_esto/esto_component_to_common_row_lineage.csv.gz`

The anchor validator has two detail outputs:

- `results/tree_structure/source_parent_anchor_validation.csv` is the primary reviewer and
  dashboard view. It contains failures, `source_internal_recursive_sum_inconsistency` rows, and
  reviewed data-quality exceptions.
- `results/tree_structure/source_parent_anchor_validation_full.csv.gz` retains the complete audit,
  including routine passes and structural skips.

`source_parent_anchor_validation_summary.csv` is always calculated from the complete audit before
the compact findings view is selected.

## Compatibility boundary

`results/common_esto/common_esto_comparison_data.csv` remains the canonical production dashboard
input with its existing denormalized schema. It is intentionally not compressed or normalized in
this transition because `leap_dashboard` and mapping diagnostics read its labels and structural
fields directly.

Stage 3 and the Common ESTO fast path now also publish an additive v1 output contract:

- `common_esto_comparison_fact.csv.gz` contains observed values keyed by comparison scope, source,
  economy, scenario, year, and Common-row ID.
- `common_esto_row_metadata.csv` contains one row per comparison-scope/Common-row-ID key.
- `common_esto_output_contract.json` records the ordered schemas, keys, row counts, byte sizes, and
  SHA-256 values. It is promoted last and is the commit marker for the two data artifacts.

Only certified, QA-successful runs replace this canonical contract. A review-tagged run preserves
the previous contract and records that decision in `common_esto_output_status.csv`.

The legacy comparison remains unchanged while the dashboard loader migrates to the joined
fact/metadata representation and verifies rendered equivalence.

## Cleanup archives

Multi-file cleanup archives live under:

`results/_quarantine_archives/<date>/`

ZIP members use repository-relative paths. Each ZIP contains `archive_manifest.json` with the
restore root, original paths, sizes, and SHA-256 values. Extract at the repository root to restore
the archived paths.

## Verified 2026-07-27 run

The full `1,2,data_convert,3` pipeline retry completed with status `completed`. Stage 3 took
4,261.4 seconds, including 1,414.4 seconds for source-parent anchor validation. Every gzip output
below passed a complete decompression/CRC read after the run.

| Logical artifact | Previous plain CSV | Current gzip CSV | Reduction |
|---|---:|---:|---:|
| 9th converted results | 658.1 MB | 49.7 MB | 92.4% |
| ESTO exact rows | 466.2 MB | 23.1 MB | 95.0% |
| ESTO_EXTENDED exact rows | 504.3 MB | 23.3 MB | 95.4% |
| LEAP source lineage | 49.0 MB | 2.9 MB | 94.0% |
| 9th source lineage | 1,434.4 MB | 173.5 MB | 87.9% |
| Common-row lineage | 1,316.6 MB | 118.8 MB | 91.0% |
| **Total** | **4,428.7 MB** | **391.3 MB** | **91.2%** |

The compact anchor findings file contains 10,837 rows and is 5.6 MB. The complete 1,345,038-row
audit is retained in `source_parent_anchor_validation_full.csv.gz` at 18.7 MB; its decompressed
CSV is about 1,057.4 MB.

The six stale plain CSVs were archived before removal from their live paths:

`results/_quarantine_archives/2026-07-27/legacy_uncompressed_pipeline_outputs_pre_20260727.zip`

The archive is 471.7 MB. Its members retain repository-relative paths, and every entry was
read back and SHA-256 checked against the embedded manifest. The originals were then sent to the
Windows Recycle Bin, so they can also be recovered there until it is emptied. Including the
archive, `results/` measured 3.47 GB after cleanup, down from approximately 7.7 GB before the
work.

The run did not silently clear existing hierarchy findings. Its manifest still reports flow-axis
parent/child failures for ESTO, ESTO_EXTENDED, and NINTH. The generated rollup diagnosis attributes
most diagnosed rows to children intentionally obscured or replaced by `NON_EXPANDING` or
`DETACHED` rollups; the remaining `present_in_final_output` and related patterns remain review
work. They are preserved in `results/tree_structure/common_esto_validation*.csv` and are not
changed by the storage-format work.

## Remaining work queue

1. Migrate the `leap_dashboard` loader and fixtures to the additive Common ESTO v1 contract, verify
   rendered equivalence, and only then consider retiring the legacy denormalized comparison.
2. Test whether ESTO_EXTENDED can be represented as ESTO base rows plus a delta rather than a
   second full dataset.
3. Add retention rules for `rollup_mode_ab_exploration/`, `common_esto/test_slice/`, and
   `esto_extended_test/`.
4. Resolve or approve the remaining Common ESTO flow-hierarchy issue patterns before treating
   that validation family as clean.
