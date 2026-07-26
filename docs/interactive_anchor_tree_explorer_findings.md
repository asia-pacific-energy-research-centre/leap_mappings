# Interactive anchor-tree explorer: initial findings and visual grammar

## Scope and evidence snapshot

This is an exploration-only design checkpoint for the full all-level tree
explorer described in `docs/prompts/interactive_anchor_tree_explorer_prompt.md`.
It does not change the mapping workbook, exception workbook, validator, or the
existing `mapping_diagnostics.html` page.

The evidence below comes from the generated artifacts available on 2026-07-26:

- `results/tree_structure/source_parent_anchor_validation.csv` — authoritative
  anchor status and validator totals;
- `results/tree_structure/source_parent_anchor_child_context_values.csv` — raw
  immediate-child values, but only for failed anchors;
- `results/tree_structure/source_parent_anchor_mapped_component_context_values.csv`
  — raw-node-to-component routes and Common ESTO IDs, again only for failed
  anchors;
- `results/common_esto/structural_artifacts/source_pair_to_common_row.csv` —
  structural source-to-component/Common ESTO mapping evidence;
- `results/tree_structure/{leap,ninth,esto}_tree.csv` — the actual source and
  ESTO hierarchy edges; and
- `results/mapping_relationships/raw_leap_results.csv` — raw LEAP values for
  the fan-out case below.

The artifacts have two scope vocabularies: the anchor validator uses
`esto_leap` / `esto_leap_ninth`, while the structural artifact currently uses
`leap_vs_esto` / `leap_vs_esto_vs_ninth`. A prototype must display the source
artifact and its scope verbatim, rather than silently treating the labels as
identical.

## Required visual grammar

| Element | Meaning | Must not mean |
| --- | --- | --- |
| Left solid tree edge | Actual source parent/child edge from the LEAP, NINTH, or ESTO tree artifact. | A mapping relationship. |
| Centre dashed arrow | A route from a raw parent or child to a Common ESTO row. It carries its raw-node label and route/component identifiers. | A target hierarchy edge or an allocated share of a common-row value. |
| Right solid tree edge | An actual `parent_code -> code` edge in `esto_tree.csv` between two displayed target rows with the same product. | Evidence that the source parent maps to a target parent. |
| Right unconnected target rows | Direct mapping fan-out. These are siblings/unrelated rows unless the real ESTO edge above exists. | A target roll-up. |
| Common ESTO row pill | One `common_row_id`, counted once in the validator total. Repeated route arrows terminate at the same pill. | A separate additive value for each route. |
| Value column | A single scale for the selected context, calculated from unrounded data. The label names the scale. | Independently rounded values that may cease to add up. |

The detail drawer should always show, in this order: raw source convention,
validator-only normalised source convention, unique Common ESTO row total,
and difference. It should separately state status/reason, source-data warning,
exception state, incomplete-frontier state, and whether the anchor is
actionable.

## Concrete cases identified

### 1. LEAP direct fan-out: `Other loss and own use` / `Natural gas`

Context: `20USA`, `Reference`, 2060, validator scope `esto_leap`.

| Measure | Value |
| --- | ---: |
| Raw LEAP parent | 2,704.624995 PJ |
| Raw immediate children sum | 2,704.624995 PJ |
| Validator source convention | -2,704.624995 PJ |
| Unique Common ESTO total | -2,704.624995 PJ |
| Difference | 0 PJ |
| Status/reason | passed / `within_tolerance_zero_only_missing_children` |

The non-zero raw children are `Coal mines` (0.980366 PJ) and `Oil and gas
extraction` (2,703.644629 PJ). Their mapping routes reach `10.01.06 Coal
mines / 08.01 Natural gas` and `10.01.12 Oil and gas extraction / 08.01
Natural gas` respectively. Both flows have `10.01 Own Use` as their ESTO
parent, but that parent is not itself one of the mapped target rows. The right
panel must therefore show **Direct mapping fan-out**, not an invented target
roll-up called `Other loss and own use`.

### 2. NINTH source-tree contradiction

Context: `20USA`, `target`, 2070, `08_gas/08_02_lng`, parent
`09_total_transformation_sector`, scope `esto_leap_ninth`.

| Measure | Value |
| --- | ---: |
| Raw NINTH parent | 0 PJ |
| Raw immediate children sum | 0 PJ in the raw-child context artifact |
| Unique Common ESTO total | 20,642.697230 PJ |
| Difference | -20,642.697230 PJ |
| Status/reason | failed / `parent_child_source_inconsistency` |

This is a valuable counterexample: the mapping evidence must not hide a source
contradiction. Its component artifact records both missing child mappings and
`mapped_but_no_context_value` rows, so the prototype needs to state that the
frontier is incomplete/non-actionable rather than visually imply an ordinary
one-to-one reconciliation.

### 3. Genuine target hierarchy

Context: ESTO `20USA`, `historical`, 2023, `02.03 Coke oven gas`, parent
`09 Total transformation sector`, scope `esto_leap`.

| Measure | Value |
| --- | ---: |
| Source parent | 45.044567 PJ |
| Unique Common ESTO total | 47.811163 PJ |
| Difference | -2.766596 PJ |
| Status/reason | failed / `parent_child_source_inconsistency` |

The mapped target rows include `09 Total transformation sector` and
`09.08 Coal transformation` for the same product. `esto_tree.csv` records the
latter as a child of the former, so this is the required positive example for
displaying a right-side hierarchy edge.

## Prototype data contract and limitation

The full explorer needs a context-level payload for both passed and failed
anchors. It can be produced without changing validation semantics by exporting
the same inspection fields that the current failed-only helpers derive:

1. one selected anchor detail record;
2. raw parent and immediate-child values;
3. raw-node-to-component routes, including unresolved/missing routes;
4. de-duplicated `common_row_id` values and their comparison values; and
5. target tree parent codes for every included component flow.

The current `source_parent_anchor_*_context_values` artifacts intentionally
provide (2) and (3) only for failures. That is sufficient for the two failed
cases, but not for the requested passed direct-fan-out case. A first prototype
can use the LEAP raw-results and structural artifacts above to demonstrate that
case, provided it visibly labels it as an artifact-composed inspection rather
than a validator-exported context. A production-quality explorer should add a
read-only, selected-context inspection export upstream; that needs a separate
review because it is an API/output-contract expansion, not a dashboard-only
presentation change.

## Recommendation at this checkpoint

Do not replace the current paired diagnostic cards yet. A separate prototype
is feasible and should augment them only after it proves the selected-context
payload can distinguish: source edges, routes, target edges, and de-duplicated
totals at usable screen sizes. The prototype should initially ship as a
separately named page and retain the cards as the compact, all-case summary.

