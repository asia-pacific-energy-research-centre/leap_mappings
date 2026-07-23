
C:\Users\Work\github\leap_mappings>C:\Users\Work\AppData\Local\Microsoft\WindowsApps\python3.13.exe c:/Users/Work/github/leap_mappings/codebase/run_mapping_pipeline.py
Running pipeline stages: ['0', '1', '2', 'leap_parse', 'data_convert', '3']

============================================================
STAGE 0  Maintenance
============================================================
Archived workbook copy: C:\Users\Work\github\leap_mappings\config\archive\outlook_mappings_master.maintenance_run_20260630_180507.xlsx
Building paste-ready rows for mapped ESTO pairs missing from source data …
  00APEC_2025_low_with_subtotals.csv: 0 paste-ready rows (always=0, Ninth=0, completion=0), 64 LNG split rows; filter retained=61, removed=162
  00APEC_2024_low_with_subtotals.csv: 0 paste-ready rows (always=0, Ninth=0, completion=0), 48 LNG split rows; filter retained=61, removed=162
Loading subtotal lookups …
  ESTO lookup: 8,487 (flow, product) pairs
  9th lookup:  12,770 (sector, fuel) pairs

Opening C:\Users\Work\github\leap_mappings\config\outlook_mappings_master.xlsx …

Computing LEAP subtotals …
  Full model export: C:\Users\Work\github\leap_initialisation\data\full model export.xlsx
  Export-derived LEAP paths: 104
  WARNING: 72 active mapping path(s) were not found in the full model export-derived path set; using mapping-sheet fallback for those paths.
  Fallback subtotal paths from mapping sheets: 11
  Active LEAP paths: 98  Subtotal paths: 19

Sheet: leap_combined_esto
  leap_is_subtotal     -> updated=1924  skipped_blank_path=0
  esto_pair_is_subtotal -> updated=1560  not_found=364  skipped_blank_key=0

Sheet: leap_combined_ninth
  leap_is_subtotal      -> updated=2085  skipped_blank_path=12
  ninth_pair_is_subtotal -> updated=2009  not_found=78  skipped_blank_key=10

Sheet: ninth_pairs_to_esto_pairs
  ninth_pair_is_subtotal -> updated=2187  not_found=88  skipped_blank_key=135
  esto_pair_is_subtotal  -> updated=2120  not_found=290  skipped_blank_key=0

Saved -> C:\Users\Work\github\leap_mappings\config\outlook_mappings_master.xlsx

Building QA outputs …
  cardinality_leap_esto:  1,893 pairs  (1,573 one-to-one)
  cardinality_leap_ninth: 2,034 pairs  (1,161 one-to-one)
  cardinality_ninth_esto: 2,245 pairs  (1,284 one-to-one)
  many_to_many_allowed_matched:      8
  many_to_many_conflicts:            0
  leap_source_presence_conflicts:    263
  crosswalk_target_conflicts_allowed_matched:20
  crosswalk_target_conflicts:        60
    crosswalk classifications:       {'expected_combined_or_aggregate_target': 25, 'missing_crosswalk_mapping': 24, 'partial_combined_target_review': 11}
  unmapped_esto_pairs:  6,348
  unmapped_ninth_pairs: 10,958
  subtotal_mismatches_allowed_matched: 246  (matched manual allowlist)
  subtotal_mismatches:  95  (not in manual allowlist)

QA outputs written to: C:\Users\Work\github\leap_mappings\results\maintenance

Building dataset tree structures …
Building ESTO tree …
  esto: 197 nodes, 171 leaves -> results\tree_structure\esto_tree.csv
Building 9th Edition tree …
  ninth: 357 nodes, 301 leaves -> results\tree_structure\ninth_tree.csv
Building LEAP tree …
  leap: 186 nodes, 158 leaves -> results\tree_structure\leap_tree.csv
Building Common ESTO tree …
  common_esto: 167 nodes, 152 leaves -> results\tree_structure\common_esto_tree.csv
Stage A — ESTO recursive sum validation …
  All ESTO recursive sum checks passed.
Stage A — Ninth Edition fuel hierarchy validation …
  All Ninth fuel hierarchy checks passed.
Stage A — LEAP sector hierarchy validation …
  15 mismatch rows -> results\tree_structure\leap_validation.csv
Stage B — Common ESTO recursive sum validation …
  22,979 mismatch rows (0 inherited from source, 22,979 potential mapping issues) -> results\tree_structure\common_esto_validation.csv
  Common ESTO non-ESTO parent/child edges: 0 -> results\tree_structure\common_esto_non_esto_parent_child_edges.csv

Tree structure outputs -> results\tree_structure

Maintenance summary: 16 rows -> results\maintenance\maintenance_summary.csv

============================================================
STAGE 1  Build energy balance relationships
============================================================
Base relationship rows (after expansion): 13,614
LEAP rollup rows added: 2,360
NINTH rollup rows added: 784
ESTO override entries: 22
Source rows read from leap_combined_esto: 1,924
Source rows read from ninth_pairs_to_esto_pairs: 2,410
Source rows read from leap_combined_ninth: 2,087
Relationship rows created: 16,758
Relationship catalogue rows: 8,255
Compact six-column catalogue rows: 8,452
leap_to_esto_balance_conversion: included=2,849, excluded=0
ninth_to_esto_balance_conversion: included=2,937, excluded=0
leap_to_ninth_comparison: included=2,593, excluded=0
ninth_to_leap_initialisation: included=0, excluded=0
mapping_review: included=8,379, excluded=0
remove_row true count: 0
Unique LEAP source pairs: 1,906
Unique ESTO target pairs: 1,826
Missing source count: 0
Missing target count: 0
Missing dataset pairs by use case: 8,458
Not-considered ESTO rows: 0
Duplicate source groups: 491
Duplicate target groups: 408
One-to-many allocation/combined-target issues: 0
Parent/child risk count: 68
Wrote relationships CSV: C:\Users\Work\github\leap_mappings\results\mapping_relationships\energy_balance_relationships.csv
Wrote relationships workbook: C:\Users\Work\github\leap_mappings\results\mapping_relationships\energy_balance_relationships.xlsx
Wrote QA files to: C:\Users\Work\github\leap_mappings\results\mapping_relationships

============================================================
STAGE 2  Build common ESTO structure
============================================================
leap_vs_esto exact_esto_components_read: 1826
leap_vs_esto excluded_components: 0
leap_vs_esto leap_defined_aggregate_groups: 452
leap_vs_esto ninth_defined_aggregate_groups: 0
leap_vs_esto manual_override_groups: 0
leap_vs_esto common_rows_created: 1488
leap_vs_esto exact_common_rows: 1369
leap_vs_esto rolled_up_common_rows: 119
leap_vs_esto missing_components: 0
leap_vs_esto duplicate_components: 0
leap_vs_esto unresolved_partial_coverage_rows: 0
leap_vs_esto source_aggregate_split_issues: 115
leap_vs_esto included_conversion_relationships_read: 2849
leap_vs_ninth exact_esto_components_read: 2586
leap_vs_ninth excluded_components: 0
leap_vs_ninth leap_defined_aggregate_groups: 452
leap_vs_ninth ninth_defined_aggregate_groups: 353
leap_vs_ninth manual_override_groups: 0
leap_vs_ninth common_rows_created: 1692
leap_vs_ninth exact_common_rows: 1413
leap_vs_ninth rolled_up_common_rows: 279
leap_vs_ninth missing_components: 0
leap_vs_ninth duplicate_components: 0
leap_vs_ninth unresolved_partial_coverage_rows: 38
leap_vs_ninth source_aggregate_split_issues: 115
leap_vs_ninth included_conversion_relationships_read: 5786
leap_vs_esto_vs_ninth exact_esto_components_read: 2586
leap_vs_esto_vs_ninth excluded_components: 0
leap_vs_esto_vs_ninth leap_defined_aggregate_groups: 452
leap_vs_esto_vs_ninth ninth_defined_aggregate_groups: 353
leap_vs_esto_vs_ninth manual_override_groups: 0
leap_vs_esto_vs_ninth common_rows_created: 1692
leap_vs_esto_vs_ninth exact_common_rows: 1413
leap_vs_esto_vs_ninth rolled_up_common_rows: 279
leap_vs_esto_vs_ninth missing_components: 0
leap_vs_esto_vs_ninth duplicate_components: 0
leap_vs_esto_vs_ninth unresolved_partial_coverage_rows: 38
leap_vs_esto_vs_ninth source_aggregate_split_issues: 115
leap_vs_esto_vs_ninth included_conversion_relationships_read: 5786
esto_only exact_esto_components_read: 2586
esto_only excluded_components: 0
esto_only leap_defined_aggregate_groups: 0
esto_only ninth_defined_aggregate_groups: 0
esto_only manual_override_groups: 0
esto_only common_rows_created: 2586
esto_only exact_common_rows: 2586
esto_only rolled_up_common_rows: 0
esto_only missing_components: 0
esto_only duplicate_components: 0
esto_only unresolved_partial_coverage_rows: 0
esto_only source_aggregate_split_issues: 0
esto_only included_conversion_relationships_read: 5786
before/after total differences: run apply_common_esto_structure.py with source data
Wrote common ESTO structure to: C:\Users\Work\github\leap_mappings\results\common_esto

============================================================
LEAP PARSE  Parse LEAP balance exports
============================================================
  Parsing full model output all years 24042026 REF.xlsx …
    43,928 rows (year=2060, scenario=Reference)
  Parsing full model output all years 27052026 TGT.xlsx …
    2,546 rows (year=2060, scenario=Target)
  Combined LEAP long-format: 46,474 rows -> results\mapping_relationships\raw_leap_results.csv

============================================================
DATA CONVERT  LEAP, 9th, ESTO -> common input format
============================================================

----------------------------------------
  LEAP -> ESTO conversion
Warning: LEAP result rows without included ESTO mapping: 44,701
Raw LEAP rows read: 46,474
Conversion relationships used: 2,849
Converted ESTO rows written: 1,907
Wrote converted results: C:\Users\Work\github\leap_mappings\results\mapping_relationships\leap_results_converted_to_esto.csv

----------------------------------------
  9th -> ESTO conversion
  Preparing 9th long-format data …
  9th long-format rows: 23,760,464
Warning: 9th result rows without included ESTO mapping: 20,314,203
  Conversion relationships used: 2,937
  Converted ESTO rows written: 4,032,574
  Wrote: results\mapping_relationships\ninth_results_converted_to_esto.csv

----------------------------------------
  ESTO exact rows
  ESTO exact rows: 4,519,620 -> results\mapping_relationships\esto_results_exact_rows.csv
  Configured rollup reference pairs retained: 55

============================================================
STAGE 3  Apply common ESTO structure to source data
============================================================
LEAP ESTO-shaped rows read: 1,907
NINTH ESTO-shaped rows read: 4,032,574
ESTO ESTO-shaped rows read: 4,519,620
WARNING: Broad common ESTO rows are present. Broad rows: 1; max exact components in one row: 96. Diagnostics written to: C:\Users\Work\github\leap_mappings\results\common_esto\diagnostics
WARNING: Intersecting common ESTO axis groups are present. Product group overlaps: 23; flow group overlaps: 29. Diagnostics written to: C:\Users\Work\github\leap_mappings\results\common_esto\diagnostics
ESTO-shaped source rows read: 8,554,101
ESTO base year used for component relevance: 2023
NINTH projection start year used for component relevance: 2023
Data-relevant ESTO component pairs: 2,252
Actionable partial-coverage rows: 218
Inactive partial-coverage component findings: 18
Nonzero LEAP branches without direct ESTO mappings: 719
Highly recommended partial-coverage mapping rows: 0
Highly recommended unmapped LEAP mapping rows: 45
HIGHLY RECOMMENDED COPY-READY MAPPINGS: C:\Users\Work\github\leap_mappings\results\common_esto\highly_recommended_mapping_candidates.csv
Nonzero ESTO-shaped source rows used: 1,132,626
Common ESTO components pruned as not applicable: 1,753
Common comparison rows written without label-based subtotal filtering: 1,794,916
Wide year rows written: 22,465
Source rows missing common map: 43,913
before/after total differences max abs: 3.725290298461914e-09
Error tag applied to output filenames: False
Wrote common ESTO comparison output to: C:\Users\Work\github\leap_mappings\results\common_esto
  Running projection-only source hierarchy validation ...
  Ninth sector validation findings: 12,530
  Ninth fuel validation findings: 0
  Validation detail rows: 18,099
  product / ESTO: passed (55 checks, 3 eligible parents, 0 mismatches)
  product / LEAP: skipped (0 checks, 0 eligible parents, 0 mismatches)
  product / NINTH: passed (5,604 checks, 2 eligible parents, 0 mismatches)
  flow / ESTO: failed (1,128 checks, 3 eligible parents, 249 mismatches)
  flow / LEAP: passed (231 checks, 3 eligible parents, 0 mismatches)
  flow / NINTH: failed (93,910 checks, 6 eligible parents, 17,850 mismatches)

============================================================
Pipeline complete.
============================================================