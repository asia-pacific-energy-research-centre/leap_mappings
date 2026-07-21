# Findings: demand-sector parent/child mismatches (14 Industry, 14.03 Manufacturing, 15 Transport)

Diagnosis-only. No code, workbook, or exception-set edits were made. No pipeline reruns.

## Which validation file was used

`results/tree_structure/common_esto_validation.csv` (the "fresh" file) is **not usable**: its own
summary (`common_esto_validation_summary.csv`) shows both the `product` and `flow` axis runs were
`skipped` at `2026-07-09T01:17:36Z` with reason *"Stage 3 comparison input modification time does
not match the current run."* — `common_esto_comparison_data.csv` was regenerated after that
validation attempt (later runs at 10:30–10:40 touched `common_esto/*` and
`mapping_relationships/*` without re-running Stage 3's flow-axis validation). The file is
effectively empty (header only).

Per the task's fallback instruction, this report uses
`results/tree_structure/common_esto_validation_baseline_20260708.csv` (63 MB, single
`run_id=common_esto_20260708T135254390147Z`) with the numeric-only rule
(`abs_error > 0.01 * max(abs(parent_value), 1)`) applied. Reapplying that rule reproduced the
task's stated counts exactly (7,493 / 4,608 / 1,920 / 1,299 / 996), confirming the baseline is the
right input and the rule was applied consistently. No newer comparable file exists, so there is
nothing to reconcile a divergence against — the "fresh" file simply isn't a second data point.

All analysis reads `data/merged_file_energy_ALL_20251106.csv` (raw NINTH),
`results/mapping_relationships/raw_leap_results.csv` (raw LEAP, USA only — this run's LEAP export
covers no other economy), `results/mapping_relationships/energy_balance_relationships.csv`,
`results/mapping_relationships/leap_results_converted_to_esto.csv`,
`results/common_esto/common_esto_comparison_data.csv`, and the `ninth_pairs_to_esto_pairs` /
`leap_combined_esto` / `leap_rollup_rules` sheets in `config/outlook_mappings_master.xlsx`.

09.x transformation-sector failures were ignored throughout, as instructed.

---

## 1. `14.03 Manufacturing` / NINTH — verdict: **mixed**

Of 4,608 flagged checks, **4,466 (97%)** already carry
`inherited_source_inconsistency = True` / `sector_hierarchy_status = confirmed_inherited` /
`source_inconsistency_status = confirmed_inherited` in the validation output itself. These are
independently detected by `validate_ninth_sector_recursive_sums()` in
`build_dataset_tree_structure.py`, which checks whether the **raw 9th dataset's own**
`sub1sectors` aggregate (`sub2sectors='x'`) equals the sum of its own `sub2sectors` rows, with no
mapping pipeline involved. Where it doesn't, and a Stage B mismatch lands on the same
(economy, year, sector, fuel), Stage B marks it `confirmed_inherited`: i.e. the 9th Outlook's own
industry sub-sector breakdown does not sum to its own manufacturing subtotal — a pre-existing 9th
Outlook data-quality issue, not a leap_mappings defect. Median share of parent unexplained by this
inherited category: 74% (mean 68%, quite noisy — consistent with a genuine source
inconsistency rather than a clean coverage gap). **Example**: USA, `08.01 Natural gas`, 2050:
parent (14.03 Manufacturing, sub1 aggregate) = 363.78 in the *raw NINTH file itself has no
white-spirit-specific issue here* — see the separate White spirit case below for the real,
non-inherited example; the natural-gas case is a pure sector-hierarchy inherited mismatch
(`source_issue_ids = source_issue::NINTH::sector::20_USA::reference::2050::14_03_manufacturing::08_01_natural_gas`).
This portion is **out of scope for a mapping fix** — it should not get a
`parent_child_mismatch_allowed` exception targeted at leap_mappings either, because it is already
tracked internally as `confirmed_inherited`, not exposed as a raw failure needing separate sign-off.

The remaining **142 (3%)** are *not* inherited and are a genuine coverage bug:

**Worked example**: `14.03 Manufacturing` / NINTH / Japan (`08_JPN`) / year 2050 /
`07.12-07.17 White spirit SBP` (a rolled ESTO product bucket covering 07.12–07.17):
parent_value = 363.78, children_sum (7 of 11 children present) = 341.67, abs_error = 22.11 (6.1%
of parent). Missing children: `14.03.07 Food, beverages and tobacco`, `14.03.09 Wood and wood
products`, `14.03.10 Textiles and leather`, `14.03.11 Non-specified industry`.

Checked `ninth_pairs_to_esto_pairs` for `esto_product = 07.12 White spirit SBP`: rows for
`14.03.07` and `14.03.10` have the `ninth_fuel` set to `07_12_white_spirit_SBP` but **`ninth_sector`
is blank** (rows 1817, 1952) — they never attribute to any sector. `14.03.09` has **no row at
all** for this product. `14.03.11` does have a valid row (`14_03_11_nonspecified_industry` →
`07_x_other_petroleum_products`), so its absence there is closer to cosmetic (the raw NINTH value
for that combination is small/zero for JPN in the years checked).

**Materiality**: economies affected are JPN and Chinese Taipei only (96 + 46 rows); worst-case
share ~9% of parent, i.e. small in absolute PJ terms but a real, reproducible coverage gap, not
noise.

**Exception rows for `parent_child_mismatch_allowed`** (only for the confirmed_inherited 97%,
since that portion is a genuinely accepted pre-existing source inconsistency; the 3% below is a
bug, not an exception candidate):

```
enabled | axis | parent_code           | source_system | description
true    | flow | 14.03 Manufacturing   | NINTH         | 9th Outlook's own sub2sector detail does not sum to its reported 14.03 Manufacturing sub1sector aggregate for some (economy, year, fuel) combinations; already flagged confirmed_inherited by validate_ninth_sector_recursive_sums, not a mapping defect.
```

**Mapping-bug fix (do not apply)**: in `ninth_pairs_to_esto_pairs`, for `ninth_fuel =
07_12_white_spirit_SBP` (and any other `ninth_fuel` codes feeding the "07.12-07.17" combined ESTO
product), add the missing `ninth_sector` values for rows currently blank
(`14_03_07_food_beverages_and_tobacco`, `14_03_10_textiles_and_leather`) and add the missing row
for `14_03_09_wood_and_wood_products`, mirroring the pattern already used for `14_03_11` and for
sibling sectors 14.03.01/.02/.03/.04/.05/.06/.08 on this same product.

---

## 2. `14 Industry sector` / LEAP — verdict: **mapping-bug**

**Worked example**: USA, `08.01 Natural gas`, 2024, scenario Reference: converted
`14 Industry sector` = 46,267.50; children (`14.01 Mining and quarrying` = 89.07,
`14.02 Construction` = 240.01, `14.03 Manufacturing` = 8,656.24) sum to 8,985.32 — an 80.6% shortfall.
Across all 420 "difference_exceeds_tolerance" rows for this parent/source combo (all products,
all years, USA only — LEAP export in this run covers no other economy), the unexplained share is
systematic: median 88%, min 67%, max 99.6% — not noise.

Traced to source: `results/mapping_relationships/raw_leap_results.csv` reports `leap_flow =
"Industry"` = **8,985.32** for this cell — i.e. the raw LEAP export's own "Industry" total
*already agrees* with 14.01+14.02+14.03 (no source-side inconsistency). The inflation is
introduced entirely by the conversion step. `results/mapping_relationships/energy_balance_relationships.csv`
shows three relationships targeting `(14 Industry sector, 08.01 Natural gas)`:

```
source_flow                        is_rollup_derived
Industry                           False   (correct, direct mapping)
Total final consumption            True    (bug)
Total final energy consumption     True    (bug)
```

The `leap_combined_esto` sheet correctly maps `Total final consumption` → `12 Total final
consumption` and `Total final energy consumption` → `13 Total final energy consumption` (rows
1016, 1070) — these whole-economy rollup aggregates have their own correct targets. But
`_apply_leap_rollup_rules()` in `codebase/mapping_tools/build_energy_balance_relationships.py`
(~line 1453–1500) additionally clones **every** existing relationship whose `source_flow` equals a
rollup rule's `input_leap_sector_name_full_path`, renaming only `source_flow` to the rolled label
and copying `target_flow`/`target_product` unchanged. Because `leap_rollup_rules` includes the rule
`input_leap_sector_name_full_path="Industry" → rolled="Total final consumption"` (and the same for
`"Total final energy consumption"`), it clones the *existing* `(Industry → 14 Industry sector)`
relationship into two bogus new relationships: `(Total final consumption → 14 Industry sector)`
and `(Total final energy consumption → 14 Industry sector)`. Since `convert_leap_results_to_esto()`
also builds an actual **value** row for the rolled flow `"Total final consumption"` (summing
Industry + Buildings + Freight road + Passenger road + Other sector + Transport non road — the
whole economy), that huge economy-wide total gets merged straight into `14 Industry sector`
alongside the correct `Industry` contribution, inflating the parent by roughly the size of the
rest of the economy's demand.

**Fix (do not apply)**: `_apply_leap_rollup_rules` should only clone the relationship(s) that
represent the rollup-rule's *own* intended target for the rolled aggregate (i.e. skip cloning when
the matched relationship's `target_flow` is not itself a rollup/total-consumption-style target —
concretely, exclude relationships whose `input_flow` already has an explicit, non-rollup-derived
mapping to a specific demand-sector flow like `14 Industry sector`, `15 Transport sector`, etc.).
Practically: do not fan `Total final consumption` / `Total final energy consumption` out to every
target that any of their six input branches individually maps to — only to `12 Total final
consumption` / `13 Total final energy consumption`, which are already correctly present as direct
rows.

No exception row proposed — this is a fixable pipeline bug, not a real design gap.

---

## 3. `15 Transport sector` / LEAP — verdict: **mapping-bug** (same root cause as #2, different manifestation)

**Worked example**: USA, `08.01 Natural gas`, 2023, Reference: parent `15 Transport sector` =
1,202.23. Present children: `15.02 Road` = 3.58, `15.05 Pipeline transport` = 2,400.88 (≈2×
parent), `15.06 Non-specified transport` = 1,202.23 (**exactly** equal to the parent). Missing:
`15.01 Domestic air transport`, `15.03 Rail`, `15.04 Domestic navigation`. Across the 114
"difference_exceeds_tolerance" rows for this combo, `abs_error / parent_value` is **exactly 2.0**
with near-zero variance — a clean, deterministic doubling, not noise.

Cause: `leap_rollup_rules` defines `rolled_leap_sector_name_full_path = "Transport"` built from
inputs including `Transport non road/Pipeline transport` and
`Transport non road/Nonspecified transport` (rows 23, 22). `_apply_leap_rollup_rules` clones each
of those two existing relationships — (`Transport non road/Pipeline transport → 15.05 Pipeline
transport`) and (`.../Nonspecified transport → 15.06 Non-specified transport`) — renaming
`source_flow` to `"Transport"`, i.e. creating `(Transport → 15.05 Pipeline transport,
is_rollup_derived=True)` and `(Transport → 15.06 Non-specified transport, is_rollup_derived=True)`.
But `"Transport"` (bare) also has its own correct direct mapping to `15 Transport sector`. The
rolled LEAP value for `"Transport"` equals the parent total; via the merge in
`convert_leap_results_to_esto`, that full parent-equivalent value gets added a second time into
both `15.05 Pipeline transport` and `15.06 Non-specified transport`, on top of their real,
correctly-mapped values — hence child_sum ≈ 2× parent for products dominated by pipeline gas use.
Confirmed in `energy_balance_relationships.csv`: both `15.05` and `15.06` have one
`is_rollup_derived=False` row (correct) and one `is_rollup_derived=True` row with
`source_flow="Transport"` (the bug).

**Fix (do not apply)**: same as #2 — `_apply_leap_rollup_rules` should not clone relationships for
input branches that are themselves leaves feeding a rollup aggregate when that aggregate already
has its own direct target (`Transport → 15 Transport sector`); it should not additionally propagate
the rolled aggregate value down into the individual children's targets (`15.05`, `15.06`).

The remaining 1,185 `missing_expected_children` rows for this combo are the flip side of the same
issue (children like `15.01`, `15.03`, `15.04` reported "missing" purely because `child_count`
bookkeeping treats the run as failed once any numeric mismatch/duplication exists in the group);
not a separate, unrelated bug.

No exception row proposed.

---

## 4. `14 Industry sector` / NINTH — verdict: **mapping-bug**

996 failures, 0% inherited (unlike the same parent under LEAP, and unlike 14.03/NINTH — this is a
plain coverage gap in `ninth_pairs_to_esto_pairs`, not a source-hierarchy issue).

**Worked example (dominant cause, 738/996 = 74%)**: `07.01 Motor gasoline`, e.g. China
(`05_PRC`), 2023: parent (`14 Industry sector`) = 274.09, children_sum (`14.01`+`14.02` only) =
230.18, abs_error = 43.91 — exactly the raw NINTH value for
`14_03_manufacturing`/`07_01_motor_gasoline` (confirmed directly in
`merged_file_energy_ALL_20251106.csv`: 43.91 in 2023). `ninth_pairs_to_esto_pairs` has rows for
`14_01_mining_and_quarrying` and `14_02_construction` → `07.01 Motor gasoline`, and rows for every
`14.03.xx` sub-sector → `07.01 Motor gasoline`, but **no row at all** for
`14_03_manufacturing` (the sub1sector aggregate) → `14.03 Manufacturing` / `07.01 Motor gasoline` —
even though the identical row exists for other fuels (e.g. `07.12 White spirit SBP`). This is a
missing-row omission, not deliberate exclusion (not present in `coverage_exclusions.csv`).

**Secondary cause (192/996 = 19%)**: `07.12-07.17 White spirit SBP`, e.g. Australia, all years:
missing child is `14.02 Construction`. `ninth_pairs_to_esto_pairs` has no `14.02 Construction` row
for any product in the 07.12–07.17 range (checked the full `esto_flow == '14.02 Construction'`
row set — only `07.17 Other products` appears, not 07.12–07.16), while `14.01` and `14.03` do have
entries for this range. Given Construction genuinely uses bitumen/paving materials, this may be a
real omission rather than a deliberate design choice, but was not independently confirmed against
raw 9th values for Construction in this pass (materiality is small: ~6–9% of parent per the JPN
example pattern above).

**Fix (do not apply)**: add the missing `14_03_manufacturing → 14.03 Manufacturing /
07.01 Motor gasoline` row to `ninth_pairs_to_esto_pairs` (and check the other petroleum products
for the same 14.03-aggregate gap — motor gasoline is the majority but likely not the only one).
Separately, review whether `14.02 Construction` should have rows for the 07.12–07.16 product
codes; if 9th data shows genuine nonzero construction-sector bitumen/lubricant/wax use, add them.

No exception row proposed for the dominant cause (clear coverage bug). If, after checking raw 9th
values, Construction truly has zero white-spirit-family energy in the underlying data, a narrow
exception could be proposed for that specific product family only — not attempted here since the
underlying values were not checked for this secondary cause.

---

## 5. `15 Transport sector` / NINTH — verdict: **mapping-bug**

1,920 failures, 100% concentrated in a single product, `07.04-07.05 Gasoline type jet fuel`,
uniformly across all 20 economies present in the data (96 rows each) — a structural bug, not
economy-specific noise.

**Worked example**: USA, 2023: parent `15 Transport sector` = 2,716.67; only child present is
`15.01 Domestic air transport` = **5,433.35 — exactly 2× the parent**. Missing (cosmetically, not
materially — see below): `15.02 Road`, `15.03 Rail`, `15.04 Domestic navigation`, `15.05 Pipeline
transport`, `15.06 Non-specified transport` (these genuinely have ~zero gasoline/kerosene jet fuel
use, consistent with the product being jet fuel).

Cause, confirmed in `ninth_pairs_to_esto_pairs`: the 9th Outlook does not split jet fuel into
gasoline-type vs kerosene-type (single raw `ninth_fuel = 07_x_jet_fuel`). For
`15_01_domestic_air_transport`, this single fuel is mapped to **both** `07.04 Gasoline type jet
fuel` **and** `07.05 Kerosene type jet fuel` (two separate rows, same source). Both targets fold
into the same combined `common_product_label` ("07.04-07.05 Gasoline type jet fuel"), so the
child's single raw value is counted twice. For `15_transport_sector` (the parent), there is only
**one** row for `07_x_jet_fuel` (→ `07.05 Kerosene type jet fuel` only) — so the parent is counted
once. The parent/child inconsistency in how many times the same undifferentiated fuel is
replicated across the split product codes produces the exact, uniform 2× ratio.

**Fix (do not apply)**: make the `15_01_domestic_air_transport` treatment of `07_x_jet_fuel`
consistent with `15_transport_sector`'s: either map it to a single one of `07.04`/`07.05` (matching
the parent's convention), or if both rows are intentionally kept to preserve information for other
comparison scopes, ensure downstream rollup into the combined `07.04-07.05` `common_product_label`
de-duplicates same-source-fuel contributions rather than summing both target rows. Given the
parent already uses the single-row convention, the simplest fix is to drop one of the two
`15_01_domestic_air_transport` rows (keep `07.05 Kerosene type jet fuel`, matching the parent) or
add a `07.04`/`07.05` counterpart row to `15_transport_sector` if dual-counting is actually the
intended design elsewhere — check for consistency with sibling transport sub-sectors before
picking a direction.

No exception row proposed — clean, deterministic bug with an obvious fix once the mapping-sheet
convention is picked.

---

## Summary table

| parent_code | source_system | verdict | dominant cause |
|---|---|---|---|
| 14.03 Manufacturing | NINTH | mixed | 97% confirmed_inherited (9th internal sector-hierarchy inconsistency, out of scope); 3% missing/blank ninth_sector rows for 14.03.07/.09/.10 on 07.12-07.17 product family |
| 14 Industry sector | LEAP | mapping-bug | `_apply_leap_rollup_rules` clones "Industry"'s target onto rollup-derived "Total final consumption"/"Total final energy consumption" source rows, injecting whole-economy totals into the sector |
| 15 Transport sector | LEAP | mapping-bug | same function clones Pipeline/Non-specified transport's targets onto the rolled "Transport" source, double-adding the parent-level rolled total into those two children (exact 2x) |
| 14 Industry sector | NINTH | mapping-bug | missing `14_03_manufacturing → 14.03 Manufacturing` row for motor gasoline (74% of failures); missing `14.02 Construction` rows for 07.12-07.17 product family (19%) |
| 15 Transport sector | NINTH | mapping-bug | `15_01_domestic_air_transport` maps one undifferentiated 9th fuel to both halves of a combined product bucket, doubling the child vs. the parent's single mapping (exact 2x, all economies) |

---

## 2026-07-21 refresh — Transport verification

The fresh Stage 1–3 output changes the presentation, but not the Transport
diagnosis. NINTH's detailed `15_0x` sectors are present in the source and reach
the expected Common ESTO labels: the source frontier marks all six direct
children comparable, and `ninth_pairs_to_esto_pairs` has active mappings such
as `15_02_road -> 15.02 Road` (rows 1811–1826).

In `common_esto_20260721T022306466013Z`, Australia / reference / 2023 /
`07.04-07.05 Petroleum products` has parent 150.581352 PJ and children
301.162703 PJ. `15.01 Domestic air transport` alone is 301.157560 PJ. This is
the same unallocated one-to-many jet-fuel mapping described above: the 150.581
PJ `15_01_domestic_air_transport × 07_x_jet_fuel` source value is emitted once
to each half of the common jet-fuel product bucket, then summed.

An uncommitted converter change already in the workspace applies equal default
source-conserving shares to unallocated one-to-many NINTH mappings. Its focused
tests pass (4 passed), and it should reduce this worked child value to the
parent-equivalent 150.581352 PJ. This investigation did not modify or commit
those in-progress converter, test, or workbook changes. Re-run Stages 1–3 once
they are ready before deciding whether any residual Transport rows remain; no
Transport exception or mapping-workbook change is proposed.
