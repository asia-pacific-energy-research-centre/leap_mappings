# Workbook variant row comparison — 2026-07-28

**Question:** does `config/outlook_mappings_master_combined_esto.xlsx` contain
mapping rows that are missing from the canonical
`config/outlook_mappings_master.xlsx`, and should they be added?

**Short answer:** almost nothing. Of 231 candidate rows, **228 are inactive**,
**1 should be rejected**, and **2 are worth adopting** — and those 2 are not
missing rows at all, they are existing canonical rows with a blank fuel that
the variant fills in.

**Status:** review-only. Nothing has been written to the canonical workbook.
Tracked as MAPQ-026 in [`work_queue.md`](work_queue.md).

## Method

Both workbooks were compared sheet by sheet on all 14 sheets, matching rows by
**mapping key** rather than by full-row signature, so that an edited row is not
mistaken for a new one. Rows whose key columns are all blank were excluded as
spreadsheet padding. Column layouts are identical between the two workbooks;
the differing `max_column` reported by openpyxl is formatting, not data.

## Result by sheet

| Sheet | Canonical | Variant | Missing from canonical | Canonical-only |
|---|---:|---:|---:|---:|
| `leap_combined_esto` | 2794 | 2757 | **0** | 37 |
| `ninth_pairs_to_esto_pairs` | 3015 | 2957 | **0** | 58 |
| `esto_rollup_rules` | 47 | 45 | **0** | 2 |
| `ninth_rollup_rules` | 33 | 31 | **0** | 2 |
| `leap_combined_ninth` | 2729 | 2921 | **231** | 39 |
| `leap_rollup_rules`, `rollup_label_overrides`, `other branches`, `deleted rows - might regret`, `NINTH unique sectors and fuels`, `ESTO unique flows and products`, `ninth fuel to esto product`, `Guide` | — | — | **0** | 0 |

**The canonical workbook is a strict superset on every mapping sheet except
`leap_combined_ninth`.** There is no ESTO-axis content to recover: the variant's
name is misleading, since the sheet it is ahead on is the LEAP↔9th axis.

Two earlier apparent differences were artifacts and are not real:

- `esto_rollup_rules` initially showed 11 extra rows in the variant. All 11 are
  blank apart from `esto_dataset_scope = BOTH` — spreadsheet padding, not rules.
- `leap_display_names` initially showed 511 differing rows in both directions.
  The cause is a single column, `IS_LEAP_ROLLUP_NAME` (see §4).

## 1. The 231 rows on `leap_combined_ninth`

`duplicate_to_remove` is a deactivation flag —
`leap_mapping_refresh_workflow.py:708` computes
`is_active = ~remove_row & ~duplicate_to_remove`.

| | Count | Meaning |
|---|---:|---|
| `duplicate_to_remove = True` | **228** | Inactive. Adopting them changes no mapping behaviour. Per `AGENTS.md`, removed rows in `leap_combined_ninth` are often deliberate many-to-many guardrails rather than obsolete data. |
| `duplicate_to_remove = False` | **3** | Would change behaviour. Assessed individually below. |

The 228 are concentrated in `Passenger road` / `Freight road` vehicle-technology
branches (129 rows under `15_02_`), `Iron and steel` process routes (63 rows
under `14_03_`), and CHP/heat-plant processes. These are exactly the branch
families where LEAP models more detail than the 9th edition, which is the
documented reason such rows are deactivated. **Recommend not adopting.**

## 2. Recommended: fill two blank fuels (not new rows)

These two source pairs **already exist and are active in the canonical
workbook**, but with `ninth_fuel` blank. The variant supplies `02_coal_products`.

| Sheet | `leap_sector_name_full_path` | `raw_leap_fuel_name` | `ninth_sector` | `ninth_fuel` (canonical → proposed) |
|---|---|---|---|---|
| `leap_combined_ninth` | `Gas works plants/Gas works plants` | `Blast furnace gas` | `09_06_01_gas_works_plants_incl_own_use` | *(blank)* → `02_coal_products` |
| `leap_combined_ninth` | `Gas works plants/Gas works plants` | `Other recovered gases` | `09_06_01_gas_works_plants_incl_own_use` | *(blank)* → `02_coal_products` |

Evidence, derived on each axis independently as `AGENTS.md` requires:

- **Fuel axis is unambiguous.** Across the canonical workbook, `Blast furnace
  gas` maps to `02_coal_products` in **36 of 36** other active rows, and `Other
  recovered gases` in **35 of 35**. There is no competing target.
- **Sector axis is already established.** The same `Gas works plants` block
  already maps `Coal tar`, `Coke oven coke`, and `Coke oven gas` to
  `09_06_01_gas_works_plants_incl_own_use` / `02_coal_products`.
- **Blank fuel is an anomaly, not a convention.** Only **3 of 2711** active
  canonical rows have a populated `ninth_sector` with a blank `ninth_fuel`, and
  two of them are precisely these. Every other fuel in the same Gas works block
  has its `ninth_fuel` populated.
- **No many-to-many risk.** This makes five LEAP fuels map to one 9th pair,
  which is many-to-one aggregation — the expected shape where LEAP carries finer
  fuel detail than the 9th edition's `02_coal_products` bucket.

**Caveat before applying:** these rows are currently inert on the fuel axis.
Filling the fuel activates a mapping that was not previously contributing, so 
this is a behaviour change requiring a pipeline rerun and validation, not a 
cosmetic edit. Sequence it with MAPQ-005.

## 3. Recommended against: the CHP process row

| `leap_sector_name_full_path` | `raw_leap_fuel_name` | `ninth_sector` | `ninth_fuel` |
|---|---|---|---|
| `CHP plants/Processes/Coal CHP` | `Electricity` | `09_02_chp_plants` | `17_electricity` |

This is a genuinely new source pair, and it should **not** be adopted:

- **No process-level CHP child is mapped anywhere in the canonical workbook** —
  zero active rows and zero inactive rows under `CHP plants/Processes/`. The
  established convention is to map at the `CHP plants` parent level.
- **The parent is already mapped to this exact target.** Canonical actively maps
  `CHP plants` + `Electricity` and `CHP interim/CHP interim` + `Electricity` to
  `09_02_chp_plants` / `17_electricity`. Adding the child alongside the parent
  would double-count the same electricity output.

Its absence from the canonical workbook looks deliberate, not accidental.

## 4. Separate finding: `IS_LEAP_ROLLUP_NAME` is empty in the canonical workbook

On `leap_display_names`, the column `IS_LEAP_ROLLUP_NAME` is **blank in all 605
canonical rows**, but populated in the variant (21 `True`, 490 `False`, 94
blank). `USED_IN_LEAP_INITIALISATION` also differs on 2 rows.

Impact is currently low: the column appears only in the docstring of
`codebase/functions/unified_name_lookup.py`, which is a standalone tool with no
importers, and no code reads the column. But the 21 `True` flags are real
metadata that exists in one workbook and not the other, so recovering them is
cheap insurance if that lookup is ever wired into the pipeline.

## 5. Bonus finding: a third blank fuel neither workbook fills

| `leap_sector_name_full_path` | `raw_leap_fuel_name` | `ninth_sector` | `ninth_fuel` |
|---|---|---|---|
| `Heat plant interim/Heat plant interim` | `Bitumen` | `09_x_heat_plants` | *(blank in both workbooks)* |

`Bitumen` maps to `07_x_other_petroleum_products` in **23 of 23** other active
canonical rows, so the fill is unambiguous. This is a pre-existing gap in the
canonical workbook, unrelated to the variant. Fold into MAPQ-009.

## 6. Consequence for MAPQ-026

The variant holds no ESTO-axis content worth preserving and no genuinely
missing active mappings beyond the two blank fuels. Once those two fills are
decided, the remaining reasons to keep
`config/outlook_mappings_master_combined_esto.xlsx` were originally two
references that blocked its deletion:

- `codebase/run_mapping_pipeline_delayed.ps1:23` (`--mapping-workbook-path`);
  this obsolete runner was later removed by `ac33daa`, so this is historical
  evidence rather than a current dependency.
- `docs/prompts/review_non_expanding_vs_detached_rollups_prompt.md:52` (MAPQ-010
  evidence — note its `esto_rollup_rules` sheet is a **subset** of canonical, so
  canonical serves that prompt at least as well)

The remaining active prompt is repointable at the canonical workbook. After
MAPQ-010 runs and the `IS_LEAP_ROLLUP_NAME` question is resolved, the variant
can be deleted. There is no longer a runner to update.
