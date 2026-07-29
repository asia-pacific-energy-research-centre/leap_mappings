# Mapping pipeline guide

**Verified:** 2026-07-29

**Audience:** mapping analysts and maintainers

This is the reader-friendly route through the current mapping pipeline. The
canonical semantic reference remains [`../mappings_system.md`](../mappings_system.md);
this guide explains the runnable flow and links to that detail.

## Purpose and boundary

`leap_mappings` owns all relationships among LEAP branches/fuels, ESTO
flows/products, and 9th Outlook sectors/fuels. It generates a Common ESTO
structure so unlike hierarchies can be compared without silently choosing one
source as universally authoritative.

It does not own LEAP import IDs or dashboard presentation.

## Inputs and migration workbooks

| Input | Role |
|---|---|
| `config/outlook_mappings_single_axis_prototype.xlsx` | new human-maintained axis semantics and accepted extra exact pairs; shadow until promotion |
| `config/outlook_mappings_key_pairs_generated_prototype.xlsx` | generated exact-pair evidence; do not edit |
| `config/outlook_mappings_master_generated_prototype.xlsx` | generated compatibility master for current consumers; do not edit |
| `config/outlook_mappings_master.xlsx` | current production pair contract plus rollup, name, and reference sheets; bootstrap/comparison baseline during migration |
| `config/mapping_issue_exception_sets.xlsx` | reviewed QA exceptions; not automatic mappings |
| `config/source_coverage_scopes.json` | source/scope relevance |
| `config/all_demand_aggregated_components.json` | declared aggregate-demand membership |
| `config/source_branch_fallback_rules.csv` | reviewed source fallback alternatives |
| `data/00APEC_2025_low_with_subtotals.csv` | current ESTO historical source |
| `data/esto_extended.csv` | ESTO Extended source |
| `data/merged_file_energy_ALL_20251106.csv` | current 9th Outlook source |
| sibling LEAP balance-export tree | LEAP values parsed for comparison |

Legacy `leap_mappings.xlsx`, `master_config.xlsx`, and
`leap_mapping_refresh_workflow.py` are references, not the active mapping
system.

The separate-axis generate stage is the intended new first step. It is still a
shadow boundary: use the generated master explicitly for validation and do not
replace `config/outlook_mappings_master.xlsx` without promotion approval. See
[`../separate_axis_mapping_pipeline.md`](../separate_axis_mapping_pipeline.md).

## Stage flow

| Stage | Entry/module | What it does | Review point |
|---|---|---|---|
| generate | separate-axis prototype and split-workbook workflows | refreshes exact-pair authority and compiles the current pair-sheet interface from editable axes | missing maintained relations, provisional Cartesian additions, within-axis many-to-many, pair authority |
| 1 | `build_energy_balance_relationships.py` | normalizes mapping sheets into directional relationship/use-case rows and applies rollup rules | duplicate, unknown target, missing pair, parent/child QA |
| 2 | `build_common_esto_structure.py` | partitions scope-specific ESTO component graphs into exact/generated common rows | structural coverage, intersections, non-expanding frontier |
| parse | `parse_leap_balance_export.py` | reads LEAP balance exports into long source rows | economy/export discovery and schema |
| convert | LEAP/9th converters plus exact ESTO selectors | creates ESTO-shaped values and source lineage | missing mappings and value preservation |
| 3 | `apply_common_esto_structure.py` and validators | applies components/signs, aggregates values, publishes data/lineage/status | application QA, recursive hierarchy, source anchors |

## Optional maintenance before the pipeline

There is no active Stage 0. The former archived maintenance workflow mixed
several unrelated checks, returned before most of its advertised QA code, and
did not feed Stage 1. Its useful responsibilities now have explicit routes:

| Need | Entry point | When to run | Mutation |
|---|---|---|---|
| Generate mapped ESTO or ESTO Extended rows missing from a source vintage | `codebase/missing_mapped_esto_rows_workflow.py` | after reviewed ESTO-category or structural-completion changes | review files only |
| Build structural subtotal truth and exact workbook-cell review tables | `codebase/hierarchy_subtotal_contract_workflow.py` | after hierarchy, mapping workbook, exception, or structural source changes | contract/review artifacts only |
| Compile and validate relationships | Stage 1 | after mapping or rollup changes | generated relationship/QA outputs only |

The retired implementation remains under
`codebase/archive/outlook_mapping_maintenance_workflow.py` for helper and test
history. Do not use its old `maintenance_summary.csv`, cardinality, unmapped,
or subtotal-mismatch files as evidence of a current run: the live workflow
stopped before regenerating them.

## Relationships and use cases

Stage 1 outputs one row per relationship/use case. A stable relationship ID can
therefore repeat across `mapping_review` and a conversion use case. Status and
use case are part of interpreting the row.

The active directional paths are:

- LEAP → ESTO;
- LEAP → 9th;
- 9th → ESTO.

Rollups reconcile hierarchy granularity. Unknown or overlapping relationships
are surfaced as QA; they are not silently accepted.

## Common ESTO construction

Stage 2 uses explicit components, graph connectivity, comparison scope,
overrides, and rollup metadata. Labels are outputs of structure plus reviewed
name rules. They are not the source of hierarchy.

The current default scopes are:

- `esto_leap`;
- `esto_extended_leap`;
- `esto_leap_ninth`;
- `esto_extended_leap_ninth`.

Exact rows contain one component. Generated rows contain multiple components.
Non-expanding/detached rollups are alternatives or named boundaries that must
not be treated as ordinary additive parents.

## Stage 3 publication

Stage 3 reads:

- LEAP converted rows;
- 9th converted rows;
- exact ESTO rows;
- exact ESTO Extended rows;
- `common_esto_rows.csv`.

It writes:

- `common_esto_comparison_data.csv`;
- `common_esto_comparison_wide.csv`;
- total and source-coverage QA;
- component/source lineage;
- `common_esto_output_status.csv`;
- `stage3_run_manifest.json`;
- on a QA-successful canonical publication,
  `common_esto_output_contract.json`,
  `common_esto_comparison_fact.csv.gz`, and
  `common_esto_row_metadata.csv`;
- recursive and source-parent anchor diagnostics under `results/tree_structure/`.

The long compound key is:

```text
(comparison_scope, source_system, economy, scenario, year, common_row_id)
```

Stage 3’s total checks compare mapped value entering the structure with value
leaving it. Whole-source coverage is a limited diagnostic, not proof of
hierarchy completeness.

The v1 contract members are staged together, the manifest is promoted last,
and member hashes are verified. Review-tagged or failed runs preserve the
previous valid contract generation; compare the selected contract run ID with
the latest Stage 3 attempt rather than assuming they are identical. The current
result directory predates this integrated publication code and needs a fresh
QA-successful run before a production v1 generation exists.

## Validation and severity

| Finding | Blocking or review? | Result |
|---|---|---|
| missing input or invalid required schema | blocking | stage stops |
| mapping application error | blocking for canonical publication | review-tagged files |
| locked output | blocking for canonical refresh | `_rebuilt` fallback |
| structure duplicate/missing required component | blocking or high-priority review, according to producer | inspect Stage 2 QA |
| recursive hierarchy mismatch | failed review evidence | outputs may still exist |
| source-parent anchor mismatch | failed review evidence | outputs may still exist |
| candidate row | review only | never changes workbook |
| skipped validation | not validated | never call it passed |

The latest Stage 3 run finished and published canonical files while several
recursive/anchor groups were failed. Always report both process completion and
validation state.

## Source hierarchy and subtotals

Structural subtotal truth comes from the versioned
[`hierarchy/subtotal contract`](../hierarchy_subtotal_contract.md). Ordinary
declared hierarchy edges determine parenthood. Period-specific ESTO/9th source
flags remain value-filtering or conformance evidence; they do not redefine a
node's structural status.

A label is not enough to determine any of these. Review complete siblings,
raw/after-rollup cardinality, and additive frontiers.

## Mapping candidates

Candidate generation:

1. infers sector/flow and fuel/product axes independently;
2. combines them only for observed relevant non-zero source pairs;
3. excludes rows with an existing source-pair target;
4. reports destination sheet, evidence, support, confidence, ambiguity, and
   cardinality.

Only a human can copy a reviewed row into the workbook. Then run the applicable
optional hierarchy/source review and rerun Stages 1–3.

## Fast path

The fast path reuses cached source conversions and Common ESTO structure and
writes only final long/wide/status outputs. It is suitable for value-only
regeneration when every skipped dependency is current. It is not evidence of:

- current workbook QA;
- rebuilt relationships/structure;
- tree or anchor health;
- candidate generation.

## Real exact-row example

The current workbook maps:

| Source | Source pair | ESTO target |
|---|---|---|
| LEAP | `Production` + `Natural gas` | `01 Production` + `08.01 Natural gas` |
| 9th | `01_production` + `08_01_natural_gas` | `01 Production` + `08.01 Natural gas` |

Stage 1 relationship IDs are `rel_f0097e201a8e745b` and
`rel_2f600a8fcf83fe69`. Stage 2 creates exact common row
`common_esto_2a89a5ac9ea9ac64`. Stage 3 publishes source/scenario/year values
on that row, which the dashboard consumes without redefining membership.

## Related guides

- [Cross-repository start page](README.md)
- [Data contracts](cross_repository_data_contracts.md)
- [Mapping agent guide](mapping_pipeline_agent_guide.md)
- [Canonical mapping-system detail](../mappings_system.md)
- [Mapping workbook guide](../guide_outlook_mappings_master.md)
- [Special rules and decisions](../special_rules_and_design_decisions.md)
