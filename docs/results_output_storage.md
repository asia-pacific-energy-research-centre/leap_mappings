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
  dashboard view. It contains numerical failures, rows with
  `source_non_additivity_observed = true`, and exact user-confirmed source
  issues. Automatic source observations and confirmed issues annotate the
  original numerical result; neither changes `status` or `reason`.
- `results/tree_structure/source_parent_anchor_validation_full.csv.gz` retains the complete audit,
  including routine passes and structural skips.

`source_parent_anchor_validation_summary.csv` is always calculated from the complete audit before
the compact findings view is selected. It reports total numerical failures,
confirmed-issue failures, unconfirmed failures, and source-non-additivity
observations separately.

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

## Verified 2026-07-28 output-contract run

An isolated Stage 2/3 run verified the additive Common ESTO contract against the corrected
non-expanding frontier:

- the legacy comparison was 975,673,793 bytes;
- the contract fact, metadata, and manifest totalled 58,162,083 bytes;
- the contract therefore saved 917,511,710 bytes (94.04%);
- the fact contained 3,952,646 rows and metadata contained 6,173 rows;
- member sizes and SHA-256 hashes matched the manifest;
- fact keys were unique and the non-expanding frontier QA had zero violations.

The strict dashboard loader reconstructed exactly the legacy rows selected for `20_USA` and
`02_BD` (462,940 rows). Full isolated renders also matched exactly: 390 charts and 3,427 traces,
with equal manifests, page assignments, sign summaries, normalized series, and zero page-noise
flags. The contract remains explicit opt-in while the legacy output is retained for rollback.

The real ESTO Extended overlay measurement also completed on the isolated exact-row artifacts:

| Artifact | Rows | Compressed size |
|---|---:|---:|
| ESTO base | 5,445,678 | 24,231,019 bytes |
| ESTO Extended | 5,320,932 | 24,448,125 bytes |
| Exact delta | 552,126 | 3,445,322 bytes |

The delta contains 338,436 deletes and 213,690 upserts. It is 14.092% of the full compressed
Extended artifact, an 85.908% reduction for that recurring file. Exact reconstruction was
independently checked by bounded identity partitions. Reading took 14.726 seconds, delta
construction 84.585 seconds, and reconstruction plus comparison 129.897 seconds.

The opt-in Stage 3 integration now publishes a base-bound delta manifest and safely reconstructs
to a temporary input. The corrected real run matched the archived full-file Common ESTO contract
exactly: identical decompressed fact and metadata SHA-256 values, schemas, keys, row counts, and
mapped totals. Round-trip float parsing is required to preserve adjacent float64 values.

The corrected shortened Stage 3 run took 1,912.028 seconds and reached approximately 4.50 GB
sampled working memory / 6.00 GB private memory. Its Common ESTO application step was slower than
the archived full-file run (1,771.377 versus 1,162.107 seconds). The delta therefore remains
explicit opt-in with the full artifact retained as fallback.

## Remaining work queue

1. Run the opt-in Common ESTO contract through one or two normal publication cycles before
   considering retirement of the legacy denormalized comparison.
2. Exercise the hash-bound ESTO Extended delta during normal publication cycles and resolve its
   runtime trade-off before making it the default recurring representation.
3. Add retention rules for `rollup_mode_ab_exploration/`, `common_esto/test_slice/`, and
   `esto_extended_test/`.
4. Resolve or approve the remaining Common ESTO flow-hierarchy issue patterns before treating
   that validation family as clean.
