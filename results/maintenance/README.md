# `results/maintenance/`

This directory contains a mixture of one active optional review output and
historical artifacts from the retired Stage 0 monolith.

## Current output: `missing_mapped_esto_rows/`

Run `codebase/missing_mapped_esto_rows_workflow.py` when reviewed mapping,
Ninth, or ESTO-vintage changes may require new physical ESTO source rows.

The folder contains one
`<esto_source>_missing_mapped_rows.csv` / `_audit.csv` pair per checked ESTO
vintage, a `missing_mapped_esto_rows_summary.csv`, and focused supporting
audits such as LNG split and commercial-services unallocated validation.
Proposed rows are paste-ready for human review; the workflow never edits an
ESTO source file.

A top-level `results/missing_mapped_esto_rows/` folder may exist in old result
sets. Nothing in the active code writes there; see
`docs/results_folder_cleanup_candidates.md`.

## Legacy Stage 0 artifacts

Files directly in this directory such as the following were produced by
`codebase/archive/outlook_mapping_maintenance_workflow.py`:

- `maintenance_summary.csv`
- `cardinality_*.csv`
- `many_to_many_*.csv`
- `leap_source_presence_conflicts*.csv`
- `crosswalk_target_conflicts*.csv`
- `unmapped*_pairs.csv`
- `subtotal_mismatches*.csv`
- `subtotal_change_preview.xlsx`
- `subtotal_label_overrides_stale.csv`

The archived workflow is no longer called by `run_mapping_pipeline.py`.
Therefore these files may remain useful as dated research evidence, but they
are not current-run QA and must not be used as a release gate.

For active checks:

- use Stage 1 relationship QA for cardinality and mapping relationships;
- use `codebase/hierarchy_subtotal_contract_workflow.py` for structural
  hierarchy/subtotal evidence and exact workbook-cell review;
- use Stage 3 outputs for Common ESTO values, lineage, and hierarchy checks.

## Standalone tools and old review files

Some `apply_*.py` and review scripts still read named CSVs in this folder.
Treat them as explicit legacy-input tools: inspect the file timestamp and
provenance before applying anything to the workbook. These scripts back up the
workbook before approved changes, but they do not make an old report current.

Manual `*_copy.csv`, `*_copy 2.csv`, and `*_new.csv` variants and archived logs
are tracked separately in `docs/results_folder_cleanup_candidates.md` and
`docs/archive_log.md`.
