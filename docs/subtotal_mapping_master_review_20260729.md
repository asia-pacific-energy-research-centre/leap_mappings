# Subtotal-aware mapping-master review — 2026-07-29

## Outcome

A review-only copy of the current MAPQ-030 review base was generated at:

`outputs/subtotal_mapping_master_review_fad4223/outlook_mappings_master_todo_fad4223_subtotal_review.xlsx`

The source for this run was:

`outputs/subtotal_mapping_master_review_fad4223/outlook_mappings_master_todo_fad4223.xlsx`

The maintained workbook was not modified by this workflow. The review copy
adds a `CHANGED` column to:

- `leap_combined_esto`
- `leap_combined_ninth`
- `ninth_pairs_to_esto_pairs`

## Evidence and safety rule

The review uses canonical hierarchy contract build
`5e8ac25fd91adc1e806eb5ca3e1b6dfdcefbbb0a6e7bf2422322ae0afcced45d`.
The manifest SHA-256 for the source mapping workbook was checked before any
review payload was produced.

The contract identified 3,402 subtotal-flag cells whose current value differs
from the proposed structural classification. The workbook applies only
changes where both axes have complete hierarchy evidence:

- `complete_declared_code_list`
- `complete_declared_schema`
- `derived_declared_structure`

This applies 597 subtotal-flag changes. Another 2,413 suggestions are retained
for review because their evidence is partial or unresolved; 392 complete-source
suggestions conflict with a prior label exception and also remain unapplied.

In particular, LEAP classifications derived from `partial_inventory` or
`unresolved_fuel_taxonomy` are not applied automatically, even when the
contract can produce a deterministic boolean. These require the full LEAP
branch and fuel hierarchy authority tracked by MAPQ-032.

## Workbook interpretation

- `UPDATED` means the copied subtotal cell was changed.
- `REVIEW REQUIRED — NOT APPLIED` means the original flag was retained.
- A blank `CHANGED` cell means no subtotal change was proposed for that row.
- Mapping relationships were not changed. Subtotal evidence can identify
  inconsistent classification, but it cannot by itself prove a different
  source-to-target relationship.

## Counts

The reusable run summary records 2,551 annotated rows, 597 applied cells,
2,413 partial or unresolved suggestions, and 392 suggestions held because of a
prior label exception. Sheet-level detail is available in the review CSVs
beside the generated workbook.

## Verification

- Re-read every affected subtotal cell from the exported workbook.
- Confirmed applied cells equal the canonical proposal.
- Confirmed review-only cells retain their original value.
- Confirmed all 2,551 row annotations survived export.
- Formula-error scan returned no matches.
- Rendered and visually checked every sheet.
