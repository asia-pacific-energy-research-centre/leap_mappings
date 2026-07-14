# Rollup Rules System

This note explains how `config/outlook_mappings_master.xlsx` rollup-rule sheets
are consumed by the mapping pipeline. It is for maintainers editing the
workbook or debugging Stage 1/2 relationship outputs.

> **Implementation status (2026-07-13):** the pipeline now implements the
> `NON_EXPANDING_ROLLUP`, source-branch fallback, and All-demand warning
> behaviour described below, alongside the ordinary duplicate-up,
> target-expansion, and graph-edge behaviour. A rule is treated as
> non-expanding when `rollup_reason = NON_EXPANDING_ROLLUP` **or** the
> workbook's boolean `NON_EXPANDING_ROLLUP` column is truthy (both markers are
> honoured because the maintained workbook currently uses the boolean column).
> Rule loading lives in `codebase/mapping_tools/non_expanding_rollups.py`; the
> source preflight lives in `codebase/mapping_tools/source_branch_preflight.py`.

## Workbook Sheets

The workbook has three rollup-rule sheets with the same basic shape:

| Sheet | Axis | Main purpose |
| --- | --- | --- |
| `leap_rollup_rules` | LEAP sector/fuel | Duplicate detailed LEAP source relationships under reviewed aggregate LEAP labels. |
| `esto_rollup_rules` | ESTO flow/product | Define ESTO target rollups and Common ESTO display-label overrides. |
| `ninth_rollup_rules` | 9th Outlook sector/fuel | Duplicate detailed NINTH source relationships under reviewed aggregate NINTH labels, and expand synthetic NINTH target labels in `leap_combined_ninth`. |

Shared columns are:

- `rollup_context`: routing context for the rule. Stage 1 currently uses relationship `use_case` for downstream routing; do not treat `use_case` as the rollup-rule selector unless the code explicitly does so.
- `input_*`: the real source category or component category.
- `rolled_*`: the synthetic or aggregate label.
- `include`: only truthy rows are active.
- `Note`: human explanation.
- `rollup_reason`: the rule's declared purpose. `NON_EXPANDING_ROLLUP` is a
  special purpose described below.
- `parent_flow_label` and `child_flow_labels`: the declared hierarchy and
  display membership of a named subtotal. Under the target non-expanding
  design, they are not graph-edge instructions.

## Two Directions

Rollup rules are consumed in two different directions.

**Source-side duplicate-up** applies to `leap_rollup_rules` and `ninth_rollup_rules`. Stage 1 copies included leaf relationships under the rolled source label and marks the new rows `is_rollup_derived=True`. This supports source datasets that may report aggregate-level values. Stage 2 deliberately excludes `is_rollup_derived=True` rows from merge-edge creation so shared aggregate labels do not blob-merge unrelated descendants.

**Target-side expand-down** applies to target axes that can contain synthetic labels in mapping sheets:

- ESTO targets in `leap_combined_esto` and `ninth_pairs_to_esto_pairs`.
- NINTH targets in `leap_combined_ninth`.

Target expansion replaces a synthetic target with real data components and adds a provenance note, for example `expanded_from_ninth_rollup: 09_01-09_02,09_x Power sector`. Target axes need this because raw ESTO and raw 9th data do not contain synthetic rolled labels.

LEAP has no target-side expansion today because no base mapping sheet targets LEAP.

## Common ESTO Labels

For ESTO target rollups, Stage 1 builds `results/mapping_relationships/common_esto_overrides.csv` from `esto_rollup_rules`. Stage 2 reads those overrides in `build_preferred_flow_partition_labels`.

The override only applies when the component flow/product set exactly matches the override group. If the actual graph partition contains extra or missing components, Stage 2 keeps the mechanically generated Common ESTO label instead of forcing the preferred label.

The priority is:

1. exact component-set match from `esto_rollup_rules` via `common_esto_overrides.csv`;
2. otherwise generated Common ESTO labels from graph partitioning.

## Graph-edge exclusions and their QA role

Stage 2 excludes two kinds of rows from source-aggregate merge edges:

- `is_rollup_derived=True`;
- `esto_pair_is_subtotal=True`.

These rows still exist in relationship outputs and diagnostics. The exclusion only prevents them from creating graph edges that would merge broad parent rows with descendants. Without these exclusions, subtotal rows such as total final consumption or duplicate-up rollups such as `Transport` could pull many unrelated components into one large Common ESTO row.

Keep these exclusions even after existing mapping conflicts are resolved. A
source duplicate-up row is a newly created comparison view, not independent
evidence that all of its components must form one irreversible Common ESTO
graph component. Stage 2 retains the exclusion and publishes the suppressed
edges to `results/common_esto/qa_common_esto_suppressed_graph_edges.csv`, one
row per suppressed component pair with the source group (use case, system,
flow, product) and an `exclusion_reason` of `is_rollup_derived`,
`esto_pair_is_subtotal`, or both. This makes a new structural risk reviewable
without silently merging sibling rows.

## `NON_EXPANDING_ROLLUP`

> **Short rule:** Use a `NON_EXPANDING_ROLLUP` for a named hierarchy bridge or
> derived subtotal when its detailed children must remain independently
> comparable. Use a normal graph rollup only when the mapping itself proves
> that the components are one indivisible common comparison category.

A normal rollup participates in the Common ESTO graph. Its mapped ESTO
components form graph edges, so the pipeline can derive the smallest safe
common category, record why its components belong together, and use that
membership in the Common ESTO tree and lineage outputs.

`NON_EXPANDING_ROLLUP` is an intentionally different kind of row: a displayed
derived subtotal. Its contributors are summed into its named comparison row,
but it must not add graph edges between those contributors. Its declared
`parent_flow_label` and `child_flow_labels` remain useful reader-facing
hierarchy metadata; they do not make the subtotal an operative graph parent or
child.

Use it when a useful broad subtotal and useful detailed children must both be
available, but allowing the broad subtotal to expand into the graph would join
the parent and child categories into one many-to-many common row. This is the
usual pattern for a category created to bridge a missing hierarchy level in one
dataset.

For example, ESTO `16.03 Agriculture` plus `16.04 Fishing` can be published
as the derived subtotal `16.03-16.04 Agriculture and fishing` to compare with
the combined Ninth category, while the individual ESTO and LEAP Agriculture /
Fishing rows remain separately comparable. Similarly, `Gas processing plants`
can be shown alongside `Gas works plants` and liquefaction/regasification
detail without treating all of those rows as one indivisible Common ESTO
component.

This changes the role of the two hierarchy columns: they are the authoritative
record of the intended subtotal tree for named rollups. The graph remains for
automatically discovered, unavoidable mapping constraints; it is no longer the
mechanism for expressing every intentional parent/children subtotal.

### Product treatment

Products are automatic for a non-expanding rollup. For each source system,
economy, scenario, year, and product, the output includes the union of
products actually present in its mapped contributors and sums the corresponding
values. Editors do not maintain a separate product list. A blank input product
in a workbook rule still means “match all products for that input”; it must not
be interpreted as a blanket expansion to products with no contributor.

### Safety rules

1. Use `rollup_reason = NON_EXPANDING_ROLLUP` consistently for the related
   LEAP, ESTO, and NINTH rule groups.
2. Give the subtotal one stable rolled category identity. A display-label
   override is not enough.
3. Retain direct detailed mappings as well as the subtotal mappings where
   detail is useful. This is intentional alternative-view duplication, not a
   graph-edge reason.
4. Treat the subtotal and its children as alternative comparison rows, not an
   additive frontier. A dashboard or total calculation must not sum both.
5. Run the rollup and Common ESTO QA after any change. The expected result is
   that the detailed children remain separate and the subtotal is traceable to
   its direct contributors, with no parent--child graph component created.

This mechanism is not a shortcut for avoiding ordinary mapping review. If no
separate detailed comparison is defensible and one source observation genuinely
spans several target components, a normal graph rollup remains preferable: it
exposes the unavoidable common component set and preserves the corresponding
graph evidence.

### How the pipeline implements it

- **Stage 1** (`build_energy_balance_relationships.py`) splits every rollup
  sheet into ordinary and non-expanding rules. Non-expanding rules are excluded
  from source duplicate-up (`is_rollup_derived` row creation), from ESTO/NINTH
  target fan-out expansion, and from `common_esto_overrides.csv`, so they can
  never contribute graph edges. Their rolled labels are still registered as
  known mapping targets, so mapping rows pointing at them stay whole and do not
  appear in the unknown-target QA. Stage 1 writes the compiled rule catalogue
  to `results/mapping_relationships/non_expanding_rollups.csv` and flags rules
  whose contributors cannot be resolved in
  `results/mapping_relationships/qa_non_expanding_rollup_unresolved.csv`.
- **Source values.** LEAP/NINTH subtotal values keep flowing through the
  existing source rollup + direct-mapping path: `apply_source_rollups` builds
  the rolled source row (e.g. `Power`) from its contributors and the rolled
  label's own direct mapping row delivers it to its named ESTO target. The
  ESTO-side subtotal has no raw row, so the data-convert step derives it:
  `build_esto_non_expanding_subtotal_rows` sums the raw ESTO rows of exactly
  the declared contributor flows per economy/product/year and appends the
  derived rows (tagged `non_expanding_rollup_id`) to
  `esto_results_exact_rows.csv`. Products are automatic — only products present
  in the contributors appear.
- **Stage 2** flags common rows whose component is a non-expanding rolled
  label: `is_non_expanding_rollup = True`,
  `non_expanding_rollup_id = nonexp_<slug>`, and
  `common_row_basis = non_expanding_rollup`. The flags flow through Stage 3
  into `common_esto_comparison_data.csv` and the component lineage output, so
  the subtotal rows are always distinguishable from exact rows and
  graph-generated rows.
- **Stage 2 QA.** `qa_common_esto_non_expanding_rollups.csv` records, per
  scope and subtotal, the rule sheets, mapped source systems, contributor
  inputs, observed products, and output common-row IDs.
  `qa_common_esto_non_expanding_frontier_check.csv` verifies that no
  non-expanding subtotal shares a common row with any other component —
  especially one of its declared children — so it can never join an additive
  frontier with them.

## Alternative/interim LEAP source branches

Some source branches are alternative model structures, not additive children.
They need a source-data decision before any rollup is built. This is especially
important for the `Power` non-expanding subtotal, whose contributors include:

| Standard branch | Interim branch |
| --- | --- |
| `Electricity Generation` | `Electricity interim` |
| `CHP plants` | `CHP interim` |
| `Heat plants` | `Heat plant interim` |

The implementation uses the configuration file
`config/source_branch_fallback_rules.csv`
(`codebase/mapping_tools/source_branch_preflight.py`, called at the start of
the LEAP-to-ESTO conversion). For every enabled pair and each
economy/scenario/year, it checks whole-sector energy before source rollups are
applied. If both branches are non-zero, it records a warning and sets all
interim-product values to zero in the downstream working data. It does not
alter the parsed raw LEAP input. The audit is written to
`results/mapping_relationships/leap_source_branch_fallback_audit.csv`, with
one row per rule and active-interim period (`status` is `interim_zeroed` or
`interim_only_retained`).

This `warn_and_zero_interim` policy ensures that a non-expanding `Power`
subtotal contains either the standard branch or its interim fallback, rather
than their accidental sum. The audit must record standard total, original
interim total, suppressed interim total, action, rule ID, and period. An
interim-only period is retained unchanged.

This is a source-value policy, not a graph rule. It must run before
`apply_source_rollups`, conversion, and Common ESTO application.

## `All demand aggregated` source-overlap warning

`All demand aggregated` is another interim-style LEAP branch, but it cannot be
handled by automatically zeroing it: it may legitimately represent only the
demand sectors not yet modelled elsewhere.

The implementation maintains
`config/all_demand_aggregated_components.json`, a human-owned record of exactly
which LEAP demand sectors are currently included in `All demand aggregated`.
Each component has an `include_by_default` flag applied to every economy plus
an optional `economy_overrides` map keyed by economy code, so a specific
economy can be marked as no longer aggregate-only once it gains detailed
source data without affecting other economies.
`get_demand_sectors_without_detail(components_df, economy)` exposes the
resolved per-economy list to downstream consumers — the Common ESTO dashboard
workflow uses it to skip rendering demand-sector pages (Buildings, Industry,
Transport, Other demand) that would otherwise show no LEAP detail for that
economy.
At the same early raw-source stage, it checks every economy/scenario/year. If
`All demand aggregated` and any configured included sector are both non-zero,
it writes a warning to
`results/mapping_relationships/leap_all_demand_aggregated_overlap_warnings.csv`
(and prints it prominently) without changing values.

The warning must show the configured component list, the components observed
as non-zero, the All-demand total, each observed component total, and a
reminder to verify that the configured attribution matches the LEAP model. The
initial configuration should cover the Total final energy consumption rollup
branches where applicable: Buildings, Freight road, Industry, Other sector,
Passenger road, and Transport non road.

## Own-Use Rollups

For `(including own use)` items, prefer leaf-level rolled mapping targets. Example: point a leaf mapping at `09.08.01 Coke ovens (including own use)` or `09_08_01_coke_ovens_incl_own_use`, not at a parent-level inclusive row unless the parent row has a declared non-overlapping child frontier.

Parent-level own-use rows must be derived from child inclusive rows, not from overlapping raw parent plus own-use component rows. Stage 1 NINTH target expansion follows this rule when child inclusive rollups are available: `09_08_coal_transformation_incl_own_use` expands through `09_08_01_coke_ovens_incl_own_use` and `09_08_02_blast_furnaces_incl_own_use`, then resolves those children to real NINTH component sectors.

Do not point LEAP parent mappings directly at parent-level `(including own use)` targets unless the non-overlap frontier is defined and reviewed.

## Adding A New Inclusive Item

1. Add active rows to the appropriate rollup sheet. Use real `input_*` categories and the synthetic `rolled_*` label.
2. For leaf own-use items, point the leaf base mapping rows at the rolled label.
3. Set subtotal flags in base mapping rows consistently after running the maintenance workflow; do not hand-edit computed fields.
4. If a parent inclusive row is needed, define it via child inclusive rollups or another non-overlapping frontier.
5. Run Stage 1 and inspect:
   - `energy_balance_relationships.csv`;
   - `qa_unknown_esto_target_flows.csv`;
   - `qa_unknown_ninth_target_flows.csv`;
   - provenance notes containing `expanded_from_esto_rollup:` or `expanded_from_ninth_rollup:`.
6. Run Stage 2/3 only when Common ESTO structure or converted comparison outputs can change.

## Unknown-Target QA

`qa_unknown_esto_target_flows.csv` lists ESTO target flow labels that are neither real ESTO flows nor handled by ESTO target expansion or registered hierarchy rollups.

`qa_unknown_ninth_target_flows.csv` lists NINTH target sector labels that are neither real NINTH sector labels nor handled by NINTH target expansion. Real NINTH labels are read from all sector hierarchy columns: `sectors`, `sub1sectors`, `sub2sectors`, `sub3sectors`, and `sub4sectors`.

Unknown rows are not automatically workbook errors. They can be:

- typos in a mapping target;
- synthetic labels missing a rollup rule;
- intentional future placeholders.

Hydrogen-family `09.13` rows are known future-data placeholders in related QA workflows. Do not "fix" them by inventing data or workbook rows; classify them separately from misspellings or missing rollup rules.

## Current Pipeline Boundary

The Common ESTO Stage 2/3 path uses ESTO-shaped converted source rows. Direct `leap_to_ninth_comparison` relationships are preserved and QA-normalized in Stage 1, but current Common ESTO value outputs primarily compare LEAP and NINTH through their ESTO component mappings.
