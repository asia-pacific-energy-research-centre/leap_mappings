# Source-to-LEAP coverage audit

`codebase/mapping_tools/source_coverage_audit.py` is the reusable checker for
finding non-zero source fuels that are missing from LEAP or from the canonical
mapping workbook.

## What it checks

The audit is source-first:

1. Read non-zero 9th Outlook rows for the configured scope and reference
   scenario.
2. Drop only 9th rows with `subtotal_results == True`.
3. Keep valid parent-level rows where `subfuel == "x"`.
4. Read non-zero ESTO rows for the configured scope.
5. Drop only ESTO rows with `is_subtotal == True`.
6. Preserve negative values, including international bunker rows.
7. Apply the canonical mapping only after the source inventory exists.
8. Check the exact mapped path in each economy's LEAP template.

An unmapped source row is retained in the output. It is never silently removed
because the mapping workbook lacks a row.

## Configuration

Scopes are defined in `config/source_coverage_scopes.json`. The initial scope is
`all_demand_aggregated`, with the six components below:

```text
Demand\All demand aggregated
├── Road
├── International transport
├── Transport non road
├── Industry
├── Other sector
└── Buildings
```

To reuse the checker for another sector, add another scope and its source
selectors to that JSON. The Python module should not receive new hardcoded
sector lists.

## Outputs

Running `run_coverage_audit()` writes four CSVs under
`results/source_coverage/`:

- `*_source_inventory.csv`: all non-zero source fuel rows before mapping.
- `*_coverage_detail.csv`: source rows plus mapping and LEAP presence status.
- `*_coverage_gaps.csv`: only rows that need review.
- `*_coverage_summary.csv`: counts by economy, component, source, and status.

Important statuses are:

- `OK`: mapped fuel exists at the exact LEAP path.
- `MISSING_LEAP_FUEL`: mapping exists, but the exact nested LEAP fuel path is
  absent.
- `UNMAPPED_SOURCE_FUEL`: non-zero source fuel has no active mapping.
- `AMBIGUOUS_MAPPING`: active mappings produce more than one LEAP fuel name.
- `REMOVED_MAPPING_ONLY`: only deliberately removed mapping rows exist.
- `LEAP_TEMPLATE_MISSING`: the economy's LEAP structure export was not found.

The LEAP template lookup accepts both ordinary economy filenames such as
`leap_export_template 20_USA.xlsx` and generic filenames such as
`leap_export_template 03_CDA_COMP_GEN.xlsx`; the latter is normalized to
`03_CDA` before comparison.

## Current smoke result

The initial all-demand run read all 21 economies. Before the six nested LEAP
branches are created, the expected result is a large `MISSING_LEAP_FUEL` set;
that is the actionable list for the LEAP structure handoff. Separate unmapped
and ambiguous rows identify mapping work and are not confused with missing
LEAP branches.

## Mapping candidates and cardinality review

`codebase/mapping_tools/build_source_coverage_mapping_candidates.py` converts
coverage detail into review-only rows for the three canonical mapping sheets.
It does not edit `outlook_mappings_master.xlsx`.

The generated pack is split into:

- `*_safe_candidates.csv`: one-to-one and many-to-one additions.
- `*_conflicts_candidates.csv`: one-to-many, many-to-many, and parent/child
  overlap rows that require an explicit hierarchy/subtotal decision.
- `*_candidates.csv`: the complete annotated set for auditability.

Cardinality is evaluated against active existing rows and all sibling candidate
rows. A row is therefore not labelled safe merely because it is unique by
itself. If adding it would leave both a source with multiple targets and a
target with multiple sources, it is classified as `MANY_TO_MANY_CONFLICT`.
Many-to-one rows are not many-to-many, but they still add another source to an
existing target and should be checked for subtotal or parent-child semantics
before manual insertion.

The generator now performs that parent-child check using LEAP path ancestry and
the numeric hierarchy codes in the 9th/ESTO labels. Those rows receive
`PARENT_CHILD_OVERLAP_CONFLICT` and are excluded from the safe files, even when
their ordinary cardinality would otherwise be many-to-one.

Each candidate also includes two context columns:

- `existing_mappings_to_same_target`: active source branch/flow rows already
  mapped to the candidate target.
- `existing_mappings_from_same_source`: active target branch/flow rows already
  mapped from the candidate source.

These make the remaining many-to-one additions inspectable without opening the
mapping workbook separately.
