# Findings: Buildings / Buildings-Services NINTH Counterpart Gaps

Investigation only. `config/outlook_mappings_master.xlsx` was not modified.

## Summary verdict

All 142 `target_without_source` rows for `target_flow in {Buildings, Buildings/Services}`
in `inverted_conservation_no_counterpart.csv` are one structural cause, not missing data
and not missing base mappings:

- LEAP's `Buildings/Services` branch is mapped to the real ESTO parent flow
  **`16.01 Commercial and public services`** (exact row, no rollup).
- NINTH's counterpart sector `16_01_01_commercial_and_public_services` is mapped to
  **`16.01.99 Commercial and public services unallocated`** — a real ESTO *child* of
  `16.01` (the other child is `16.01.01 Datacentres`, fed by NINTH's
  `16_01_03_ai_training` / `16_01_04_traditional_data_centres`).
- `16.01` and its two children are a genuine ESTO parent/child pair in
  `results/tree_structure/esto_tree.csv`, but no rollup rule unifies the parent-level
  LEAP row with the two child-level NINTH rows into one Common ESTO row. LEAP's `16.01`
  row and NINTH's `16.01.99` row land in **different `common_row_id`s** for every
  product, so the inverted-conservation check reports "LEAP has this row, no NINTH
  counterpart" 142 times (71 products x 2 scenarios; year 2023, economy 20USA, the only
  slice this diagnostic currently covers).
- `Buildings` (the LEAP parent, `is_subtotal=True`) shows the same 68 gaps because its
  boundary is the union of `Buildings/Services` + `Buildings/Residential`, and
  `Buildings/Residential` already reconciles cleanly (see below) — so `Buildings`
  inherits exactly the `Services` failure.
- NINTH genuinely has non-zero 2023 data for all three sub-sectors (21 non-zero fuel
  rows for `16_01_01_commercial_and_public_services`, 1 each for the two datacentre
  sectors — electricity only, as expected for a nascent category). This is **not** a
  data-availability gap.
- LEAP has no separate datacentre branch — `Buildings/Services` is LEAP's whole services
  category, semantically equal to NINTH's commercial-services-plus-datacentres total,
  which is exactly what ESTO's real `16.01` parent represents. The fix described below
  is a like-for-like structural rollup, not a new semantic claim.

Verdict: **`rollup_or_hierarchy_duplicate`** for all 142 rows. A single explicit
`esto_rollup_rules` addition (registering `16.01`'s two real children as rolling up to
the real parent code) is expected to resolve the entire gap. No `leap_combined_ninth` or
`ninth_pairs_to_esto_pairs` edits are needed — both base-mapping sheets already have
correct rows for every sector involved.

## Counts by flow / classification

| `target_flow` | rows in `inverted_conservation_no_counterpart.csv` | distinct products | classification |
| --- | --- | --- | --- |
| `Buildings` | 74 (37 products x 2 scenarios) | 37 | `rollup_or_hierarchy_duplicate` |
| `Buildings/Services` | 68 (34 products x 2 scenarios) | 34 | `rollup_or_hierarchy_duplicate` |

All rows: `comparison_scope = leap_vs_esto_vs_ninth`, `economy = 20USA`, `year = 2023`,
`scenario` split evenly `reference`/`target`, `direction = NINTH_TO_LEAP` (the only
direction this file currently reports — see
`codebase/mapping_tools/inverted_conservation_validation.py:38-51`,
`DIRECTION_CONFIG`).

`Buildings/Residential` does **not** appear in the gap file at all — it reconciles
cleanly. LEAP's `Buildings/Residential` rows and NINTH's `16_01_02_residential` rows
both map straight to the real ESTO flow `16.02 Residential`, which has no child split
(`results/tree_structure/esto_tree.csv`, code `16.02 Residential`, `is_leaf=True`), so
both datasets land on the same `common_row_id` for every product (spot-checked: e.g.
`common_esto_142027bac63f2984`, `common_esto_bc4dac57a28ba940` both appear under LEAP's
`Buildings/Residential` and NINTH's `16_01_02_residential` rows).

## `Buildings` vs `Buildings/Services`

LEAP tree (`results/tree_structure/leap_tree.csv`):

```text
Buildings (is_subtotal=True, no direct fuel mapping to ESTO)
├── Buildings/Services     (is_subtotal=False, leaf)
└── Buildings/Residential  (is_subtotal=False, leaf)
```

`leap_sector_name_full_path` uses the slash-joined full path convention described in
`docs/mappings_system.md`'s LEAP balance-export section, so `Buildings/Services` is the
`Services` child under the `Buildings` parent — not a separate top-level category.

`Buildings` (the bare parent path) has a row in `leap_combined_ninth`
(`Buildings -> 16_01_buildings`, `leap_is_subtotal=1`) but **no** row in
`leap_combined_esto` — the parent has no direct ESTO target. `16_01_buildings` (the
NINTH parent sector) likewise has no row in `ninth_pairs_to_esto_pairs`; only its two
children (`16_01_01_commercial_and_public_services`, `16_01_02_residential`) do.

`inverted_conservation_validation.py` never reads LEAP values directly (module
docstring: "Values are never read from LEAP. Source values are projected through shared
Common-ESTO rows."). Its `target_flow="Buildings"` rows come from
`reconcile_anchor_validation.build_parent_boundaries`, which aggregates the Common ESTO
rows touched by all of a LEAP parent's *mapped descendants* (here: `Services` +
`Residential`) to test the parent-level boundary, not from any direct `Buildings`
mapping row. So `Buildings`'s 74 gap rows are a derived consequence of
`Buildings/Services`'s 68 gap rows, not a second independent problem — this is **not**
a rollup/hierarchy *duplicate* in the sense of two workbook rows describing the same
thing; it's the same underlying gap surfacing at two tree levels of the same
diagnostic. Fixing `Buildings/Services` should clear both.

## Trace to Common ESTO structure

For `comparison_scope=leap_vs_esto_vs_ninth`
(`results/common_esto/structural_artifacts/source_pair_to_common_row.csv`):

| Source | `original_source_flow` | `component_esto_flow` | `is_exact_row` | `requires_rollup` |
| --- | --- | --- | --- | --- |
| LEAP | `Buildings/Services` | `16.01 Commercial and public services` | `True` | `False` |
| NINTH | `16_01_01_commercial_and_public_services` | `16.01.99 Commercial and public services unallocated` | `False` | `True` |
| LEAP | `Buildings/Residential` | `16.02 Residential` | (mixed by product) | (mixed by product) |
| NINTH | `16_01_02_residential` | `16.02 Residential` | (mixed by product) | (mixed by product) |

A full product-by-product join
(`results/common_esto/diagnostics/buildings_ninth_counterpart_gap/buildings_services_flow_split_evidence.csv`,
68 rows) confirms **0 of 68** LEAP/NINTH product pairs share a `common_row_id` for the
`Buildings/Services` case. Every LEAP row sits alone on its own exact `16.01`-flow
common row; every NINTH row sits on a `16.01.99`-flow common row that also independently
rolls up several ESTO products together on the *product* axis (from NINTH fuel
aggregates such as `02_coal_products`) but never merges with `16.01` on the *flow* axis.

ESTO tree (`results/tree_structure/esto_tree.csv`) shows the real parent/child
relationship that isn't being used for this merge:

```text
16.01 Commercial and public services   (level 2, is_subtotal=True)
├── 16.01.01 Datacentres               (level 3, leaf)
└── 16.01.99 Commercial and public services unallocated  (level 3, leaf)
```

`esto_rollup_rules` already has an *unrelated* row rolling `16.01`+`16.02` to a synthetic
`16.01-16.02 Buildings` label (`Note: "merge to buildings"`), but nothing in either base
mapping sheet ever targets that synthetic label, and no source aggregate spans both
`16.01` and `16.02`, so this rule is never invoked in the current structural artifacts
(0 rows anywhere use `common_flow_label = "16.01-16.02 Buildings"`). It is not relevant
to this gap and does not need to change.

## NINTH candidate source data

`data/merged_file_energy_ALL_20251106.csv`, economy `20_USA`, year 2023:

| `sub2sectors` | scenario | non-zero fuel rows / total |
| --- | --- | --- |
| `16_01_01_commercial_and_public_services` | reference | 21 / 51 |
| `16_01_01_commercial_and_public_services` | target | 21 / 51 |
| `16_01_03_ai_training` | reference | 1 / 54 |
| `16_01_03_ai_training` | target | 1 / 54 |
| `16_01_04_traditional_data_centres` | reference | 1 / 54 |
| `16_01_04_traditional_data_centres` | target | 1 / 54 |

NINTH has real, non-zero data under a plausible buildings sector for every affected
product family. This rules out "NINTH has no comparable source row" and "NINTH has no
non-zero data" — the gap is a mapping-boundary issue, not a data-availability issue.

## Classification and evidence table

| `target_flow` | fuel/product scope | classification | evidence |
| --- | --- | --- | --- |
| `Buildings/Services` | all 34 products in the gap file | `rollup_or_hierarchy_duplicate` | LEAP → real ESTO parent `16.01`; NINTH → real ESTO child `16.01.99`; both base mappings correct; no rollup unifies parent with children; NINTH non-zero for all affected sectors |
| `Buildings` | all 37 products in the gap file | `rollup_or_hierarchy_duplicate` (derived) | Parent-boundary check inherits the `Buildings/Services` gap via `build_parent_boundaries`; no independent LEAP→ESTO mapping exists for the bare `Buildings` path |
| `Buildings/Residential` | n/a — not in gap file | n/a (already reconciles) | LEAP and NINTH both map to `16.02 Residential`, a leaf ESTO flow with no child split; common rows match for every product checked |

No `expected_granularity_gap`, `likely_missing_leap_ninth_mapping`, or
`likely_missing_ninth_esto_mapping` rows were found — every base-mapping row already
exists and is correct on both the LEAP↔NINTH side and the NINTH↔ESTO side. The problem
is purely in the ESTO-side rollup layer.

## Proposed fix (review-only — not applied)

Add two rows to the `esto_rollup_rules` sheet, registering `16.01`'s two real ESTO
children as rolling up to the real parent code (per the naming rule in
`docs/mappings_system.md`: "If the group exactly matches a real parent category, use the
real parent category instead of a generated code"):

| `input_esto_flow` | `input_esto_product` | `rolled_esto_flow` | `rolled_esto_product` | `include` | `Note` | `parent_flow_label` | `child_flow_labels` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `16.01.01 Datacentres` | *(blank)* | `16.01 Commercial and public services` | *(blank)* | `TRUE` | Register real children under real parent so LEAP's exact `16.01` row and NINTH's per-child rows land on one Common ESTO row; children are non-overlapping (Datacentres vs unallocated remainder) and together equal the parent, per `results/tree_structure/esto_tree.csv`. | `16 Other sector` | `16.01.01 Datacentres; 16.01.99 Commercial and public services unallocated` |
| `16.01.99 Commercial and public services unallocated` | *(blank)* | `16.01 Commercial and public services` | *(blank)* | `TRUE` | Same as above (paired row for the second child). | `16 Other sector` | `16.01.01 Datacentres; 16.01.99 Commercial and public services unallocated` |

Warnings:

- This creates a subtotal↔leaf merge at the flow level: the rolled group's basis is the
  real parent `16.01`, which is already `is_subtotal=True` in the ESTO tree with exactly
  these two children — a clean, non-overlapping frontier, not a new invented boundary.
- Confirm no other rollup or graph-partition edge already treats `16.01.01 Datacentres`
  or `16.01.99 Commercial and public services unallocated` as a component of a different
  merge group before enabling — a quick rerun of Stage 2's
  `qa_common_esto_rollup_explanations.csv` filtered to these two flows is the fastest
  check.
- This does not touch `leap_combined_esto`, `leap_combined_ninth`, or
  `ninth_pairs_to_esto_pairs` — those sheets are unchanged.

## Follow-up validation commands (after the rollup rows are added and reviewed)

```powershell
# Stage 1 relationships (no data dependency change, just rollup-rule pickup):
C:\Users\Work\miniconda3\python.exe codebase\run_mapping_pipeline.py --stages data_convert,3

# Rebuild structural artifacts and rerun this investigation's join to confirm 68/68 -> 0 remaining mismatches:
C:\Users\Work\miniconda3\python.exe codebase\mapping_tools\compile_structural_mapping_artifacts.py

# Rerun the inverted-conservation check and confirm Buildings / Buildings/Services drop out of
# inverted_conservation_no_counterpart.csv:
C:\Users\Work\miniconda3\python.exe codebase\mapping_tools\inverted_conservation_validation.py
```

See `docs/prompts/run_mapping_pipeline_future_prompt.md` for the full reusable pipeline
run procedure if a broader refresh is warranted at the same time.

## Supporting file

`results/common_esto/diagnostics/buildings_ninth_counterpart_gap/buildings_services_flow_split_evidence.csv`
— one row per ESTO product under `Buildings/Services` / `16_01_01_commercial_and_public_services`,
showing the LEAP-side and NINTH-side `common_row_id` side by side (`same_common_row` is
`False` for all 68 rows).
