# Documentation re-review — 2026-08-17

## Baseline and scope

The baseline was the preservation-first 28 July documentation cluster around
`d49620b`. This pass inventoried every tracked Markdown file, checked relative
links, compared active front doors and the workflow inventory with current
code/configuration, and reviewed material Git changes since that cluster.
Dated findings and archived prompts remain evidence rather than live guidance.

## Material changes since the baseline

- The single-axis design was promoted on 29–30 July and is now the mandatory
  preliminary `generate` stage of `run_mapping_pipeline.py`, guarded by
  `outlook_mappings_generation_manifest.json`. The README, mapping-system
  guide, separate-axis guide, AGENTS rules and config guide already agree on
  this architecture.
- The production Common ESTO table and large diagnostics moved to manifested
  Parquet+Zstandard. Small catalogues and human-review outputs intentionally
  remain CSV/XLSX.
- The orchestrator now publishes the source-to-common map, supports the
  optional ESTO Extended delta contract, and owns mapping-side emissions-factor
  evidence.
- The hierarchy/subtotal implementation brief was complete but remained in the
  active prompt inventory.

## Actions

- Updated the workflow inventory for the generation gate, typed output,
  source-to-common map, emissions-factor evidence and integrated optional
  ESTO Extended delta path.
- Updated the cross-repository start page's verification date and generation
  gate wording.
- Archived the completed hierarchy/subtotal implementation prompt, refreshed
  the prompt inventory, and removed a stale row for an already archived
  portable-release prompt.
- Kept review packs, dated diagnoses and historical audits where they are
  explicitly evidence rather than current operating guidance.

## Validation

- Relative Markdown links were checked after archival and front-door edits.
- Generated pair sheets remain documented as non-editable; no workbook,
  mapping row, result table, code or configuration was changed by this review.
