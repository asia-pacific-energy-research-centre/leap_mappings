# Hierarchy/subtotal contract diagnosis

## Decision

`leap_mappings` owns structural subtotal truth. A node is a structural parent
when the authoritative hierarchy declares at least one ordinary child. A
mapping-side pair is a subtotal when either mapping axis is a structural
parent:

```text
pair_is_subtotal = any(axis_node_is_structural_parent)
```

Numerical additivity is contextual evidence and never changes that boolean.
The structural contract is separate from `common_esto_output_contract_v1`
because component-grain nodes, edges, and diagnostics do not fit its
one-row-per-observed-comparison-row metadata grain. The Common ESTO manifest
now references the selected structural build instead.

## Baseline and current inputs

The MAPQ-030 base is `config/outlook_mappings_master todo.xlsx`, not the
pipeline's canonical workbook. It remains untracked and review-only.
`config/outlook_mappings_master.xlsx` was already modified before this work and
was not written.

No active Python or LEAP process was using shared mapping outputs at baseline.
All three repositories had unrelated dirty work. In particular, the
dashboard Mapping diagnostics implementation and tests were already modified,
so this implementation added a clean strict loader and tests without
overwriting that work.

The prior no-edit workbook round-trip proof for the todo workbook is recorded
in `docs/new_leap_rows_mapping_progress_20260728.md`. It preserved workbook
behaviour, formatting, widths, freeze panes, filters, validations, conditional
formatting semantics, and unchanged-row styles. This run did not write either
mapping workbook.

## Previous derivations and disposition

| Implementation | Inputs and grain | Previous structural rule | Main disagreement | Disposition |
| --- | --- | --- | --- | --- |
| `build_ninth_tree` / `_build_ninth_subtotal_results_sets` | Full Ninth hierarchy columns; node grain | Sector subtotal depended on `subtotal_results` observed on leaf-fuel rows | Declared sector parents could be labelled leaves; sector and period evidence were coupled | Corrected: ordinary edges determine sector parenthood. Preserve layout/results flags as evidence |
| `build_esto_tree` | Full ESTO flow/product code population; node grain | Dot-code parenthood | Sound for raw ESTO; source `is_subtotal` is not structural authority | Retained through the ESTO adapter |
| `build_leap_tree` | Mapping workbook paths; node grain | Slash-path parenthood; flat fuels | Circular and incomplete; mapping-only fuel labels cannot prove a taxonomy | Contract adapter combines the review workbook and supplied branch inventory; incomplete fuel evidence is explicit |
| `infer_subtotal_labels` | Generated trees, rollup-sheet `Subtotal`, workbook rows | Mixed tree and reviewed/current values | First-value behaviour hid cross-sheet conflicts; rollup and hierarchy semantics could mix | Retained only as legacy diagnosis; contract pair table is canonical |
| Stage 0 `_compute_leap_subtotals` and subtotal previews | Non-zero source rows and workbook rows | Observed paths/flags | Observation and mapping coverage could erase declared parents | Mapping QA must consume contract pair status |
| Recursive-sum validators | Economy/scenario/year/fixed opposite axis | Parent equals child sum | Numerically useful, but not a definition of parenthood | Retained as separate value-conformance evidence |
| `_build_source_inconsistency_lookup` and source-parent anchors | Exact source contexts and mapped coverage | Failure attribution | Some paths reclassified or skipped downstream failures | Contract retains failure and adds attribution; it does not convert failure to pass |
| Common ESTO tree and `_rollup_graph_data` | Derived comparison rows and rollup rules | Mix of ordinary tree and declared boundaries | Comparison replacements risked appearing as raw hierarchy | Relationship types are separate; raw source trees are not rewritten |
| Initialisation source subtotal filters | Period-specific value preparation | Source flags | Valid as contextual filters but not structural authority | Remain local value filters; the new loader attaches contract status separately |
| Dashboard Mapping diagnostics | Mapping-owned trees, rollup catalogue, validations | Read-only checking surface | Did not have a strict structural-build identity | New loader fails closed and exposes structural/additivity labels separately |

## Required Ninth regression

The Ninth hierarchy declares:

```text
09_total_transformation_sector
  09_06_gas_processing_plants
    immediate sub2sector children
  09_08_coal_transformation
    immediate sub2sector children
```

Both parents are therefore structural subtotals. The bounded real-data
diagnostic covers 2022, 2023, 2050, and 2070 across all available
economy/scenario/fuel contexts:

| Parent | Passed contexts | Failed contexts |
| --- | ---: | ---: |
| `09_06_gas_processing_plants` | 10,644 | 236 |
| `09_08_coal_transformation` | 10,680 | 200 |

These results are not contradictory: the structure says the nodes have
children; the values say some contexts do not reconcile within tolerance.
The contract does not choose whether parent or child values are more accurate.

## Migration boundary

The adapter registry currently covers raw ESTO, Ninth, partial LEAP model
structure, ESTO Extended, and Common ESTO. Adding a dataset requires a new
adapter entry that emits normalized nodes, edges, pairs, and optional
observations; the shared classifier has no dataset branches.

The remaining blocker is authoritative LEAP evidence. The supplied review
workbook and `data/temp/new leap rows.xlsx` do not constitute a full
cross-economy model tree, and the LEAP fuel taxonomy is not available. The
contract therefore marks those nodes `partial_inventory` or
`unresolved_fuel_taxonomy`; it does not invent parenthood.

