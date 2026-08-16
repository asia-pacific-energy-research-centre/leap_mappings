# Using the Common ESTO structure mappings

Consumer-facing guide to the main output of this repository: how to map a
source dataset onto the common comparison structure, and why doing so needs no
allocation, no share assumptions, and no judgement calls.

The canonical design reference is `mappings_system.md`. This document is the
short version aimed at somebody *consuming* the mappings rather than
maintaining them.

The worked reference implementation is `leap_dashboard` — see
`leap_dashboard/docs/common_esto_mapping_consumer.md`.

## What the common structure gives you

A **common row** is a `(common_flow_label, common_product_label)` pair that
every dataset participating in a comparison scope can express **without being
split**.

That is the whole idea. The structure is built at the *lowest common
denominator* of its participating datasets. Where one source is coarser than
another, the finer source is rolled up to the level the coarser one can support
— never the other way around.

`mappings_system.md` states the rule:

> **Do not split a source aggregate unless there is an explicit allocation
> method.**
>
> ...the finer data are rolled up to a comparison level that the coarser source
> can support. The system should not pretend to know a split that the source
> data do not provide.

## Why that matters: mapping to common rows needs no allocation

Consider the 9th Outlook's `01_x_thermal_coal`. ESTO distinguishes three fuels
inside it — `01.02 Other bituminous coal`, `01.03 Sub-bituminous coal`,
`01.04 Anthracite` — so mapping the 9th onto **ESTO's** vocabulary requires
splitting one value three ways, and the split has to be estimated from ESTO's
own observed proportions for that economy and year.

Mapping the 9th onto **common rows** does not, because all three ESTO fuels sit
in the single common row `01.02-01.04 Coal`. The split and the re-aggregation
cancel out.

This is not a happy accident of the current data. It is what the structure is
for, and it holds for every participating source. Measured 2026-08-06 on scope
`esto_leap_ninth`:

| Source | Source pairs | Fan out to ESTO components | Fan out to **common rows** |
|---|---|---|---|
| 9th | 1,920 | 248 | **0** |
| LEAP | 1,108 | 0 | **0** |

Value preservation through the ESTO round trip, checked on 20_USA / 2030 /
reference across 1,743 common rows: **maximum absolute difference 0.0**.

### The practical consequences

- **One merge, not two.** You do not need to pass through ESTO's vocabulary.
- **No allocation logic**, no allocation shares, no dependency on another
  dataset's observed proportions to convert your own.
- **Datasets convert independently.** Changing ESTO's numbers cannot change how
  9th data is distributed, because nothing is being distributed.
- **Different numbers, same structure.** Anyone holding their own version of a
  dataset gets the identical common rows; only the values differ. That is the
  guarantee the mappings exist to provide.

## How to consume it

1. Get your source values in the dataset's native vocabulary.
2. Merge onto the mapping for your `(source_system, comparison_scope)`, keyed on
   the native flow/product pair, to obtain `common_row_id` and its labels.
3. Aggregate values by `common_row_id` (plus economy, scenario, year).

That is the whole operation. `apply_common_structure` in
`codebase/mapping_tools/apply_common_esto_structure.py` is the reference
implementation of step 2–3 — 137 lines, described by its own docstring as
"Join ESTO-shaped source rows to common rows and aggregate values". The
surrounding ~2,150 lines of that module are orchestration, relevance and
coverage QA, diagnostics and output writing, and are **not** part of the
consumer contract.

### Scope awareness is required

The structure is the lowest common denominator **for the datasets participating
in that scope**, so a mapping is only valid for its own scope:

- `esto_leap_ninth` — built to accommodate ESTO, LEAP and the 9th.
- `esto_leap` — built to accommodate ESTO and LEAP only. The 9th is not a
  participant, and does **not** map cleanly here: 151 of its source pairs fan
  out at the common level in this scope. That is the rule working correctly,
  not a defect. Do not convert 9th data in a scope the 9th does not belong to.

Always select the mapping for the scope you are comparing in.

## Identifying leaves: use the published hierarchy, not the labels

Common rows form a hierarchy, so a consumer summing them must first pick a
non-overlapping frontier. **Do not derive parenthood by parsing codes out of
display labels.** It is already declared, for the common axis as well as the
native ones:

`results/hierarchy_subtotal_contract/current/axis_nodes.csv`, rows with
`dataset_id = common_esto` — 104 flow and 75 product nodes carrying `is_leaf`,
`is_structural_parent`, `parent_node_id`, `depth` and `child_count`.
`leap_dashboard/codebase/hierarchy_subtotal_contract_loader.py` is a strict
reference consumer.

### Row metadata stays separate

The universal mapping CSV deliberately stays at seven columns. Subtotal and
hierarchy properties belong in `common_esto_row_metadata.csv`, keyed by
`(comparison_scope, common_row_id)`. Consumers that need a non-overlapping
frontier join that metadata explicitly; consumers that only need category
mapping do not carry structural-review columns on every source pair.

## The any-dataset → common map

`source_to_common_esto_map.csv` covers every dataset participating in each
scope: ESTO or ESTO_EXTENDED, LEAP, and NINTH where applicable. It has one
unique row per `(scope, system, source_flow, source_product)`
and exactly seven columns:

```text
scope, system, source_flow, source_product,
common_row_id, common_flow_label, common_product_label
```

The complete component/rule derivation remains available for pipeline and audit
use as manifested Parquet at
`results/common_esto/structural_artifacts/source_pair_to_common_row.parquet`.
Ordinary consumers should not need that 27-column table.

### Two caveats that remain regardless

Even with the flags shipped, a consumer still has to handle these, and this
repository cannot answer either:

- **Leaf-ness is structural, not per-source.** One source may report only
  `14 Industry sector` while another reports its children. A consumer that
  simply drops every non-leaf will silently lose the first source's values. The
  frontier has to be resolved against the rows a source actually reported.
- **Some generated rollups sit outside the declared tree.** On scope
  `esto_leap_ninth`, 97 of 98 common flow labels and 52 of 54 product labels
  appear in `axis_nodes`. The exceptions are
  `16.03-16.05,17 Other sector including non-energy (all demand aggregate)`,
  `02.01-02.08 Coal products` and `06.03-06.04 Crude oil and NGL` — generated
  aggregates that cut across the tree rather than sitting in it. The first
  overlaps both `16 Other sector` and `17 Non-energy use`, so no set of declared
  parents reveals the overlap.

**Open question for maintainers (raised 2026-08-06):** is that exclusion
deliberate? If spanning rollups are intentionally not tree nodes, say so here so
consumers know to handle them. If it is an oversight, declaring them removes a
class of consumer-side double counting.

## If a source ever fans out at the common level

That is a bug in the structure build, not a case for a consumer to handle.

Do **not** add allocation or a fallback downstream — that turns a loud upstream
failure into a quiet approximation, and silently wrong comparison totals are the
exact failure this system exists to prevent.

This repository already asserts the invariant and publishes the check:
`results/common_esto/qa_common_esto_source_aggregates_split.csv`, which is
expected to be **empty**. If it is not, fix the structure here.

## Status summary

| Thing | Status |
|---|---|
| The no-split / lowest-common-denominator guarantee | **Current**, asserted by `qa_common_esto_source_aggregates_split.csv` |
| Declared common-axis hierarchy (`axis_nodes.csv`, `dataset_id = common_esto`) | **Current** |
| ESTO → common map (`esto_to_common_esto_map.csv`) | **Current** |
| LEAP → common and 9th → common maps | **Current** in the universal source map |
| `source_to_common_esto_map.csv` (any dataset, one merge) | **Current**; seven columns, participating systems only |
| Subtotal/leaf flags | **Separate** in `common_esto_row_metadata.csv` / hierarchy contract |

See `leap_dashboard/docs/prompts/measure_aware_dashboard_and_mapping_inversion_plan.md`
(Phase A step 6, Phase C) for the plan. Update this table when each lands.
