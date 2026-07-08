# Prompt: Investigate Buildings / Buildings-Services Ninth counterpart gap

Work in `C:\Users\Work\github\leap_mappings`.

## Context

While reviewing `results/common_esto/inverted_conservation_variant_verification/inverted_conservation_no_counterpart.csv`
(output of `codebase/mapping_tools/inverted_conservation_validation.py`,
`run_inverted_conservation_validation`) for the NINTH_TO_LEAP direction,
`target_flow` values `Buildings` and `Buildings/Services` account for 71 of
the 676 `counterpart_state == target_without_source` rows (scenario
`reference` only; doubles to ~142 across `reference` + `target` scenarios),
under `comparison_scope == leap_vs_esto_vs_ninth`. This is the single largest
concentration of gaps in that file after the generic `source_without_target`
bucket.

Each row is one (LEAP flow, LEAP fuel) pair with no matching Ninth-side
common row at all — i.e. the structural crosswalk
(`results/common_esto/structural_artifacts/source_pair_to_common_row.csv`)
has a `Buildings` or `Buildings/Services` LEAP component for that fuel, but
no Ninth source row ever joins to it. The fuel list spans nearly LEAP's
entire fuel palette for these two flows (Anthracite, Aviation gasoline, BKB
and PB, Bagasse, Biodiesel, Biogas, Biogasoline, Blast furnace gas,
Charcoal, Coal tar, Coke oven coke, Coke oven gas, Electricity, Fuel oil,
Fuelwood and woodwaste, Gas and diesel oil, Gas works gas, Geothermal, Heat,
Hydrogen, Industrial waste, Kerosene, Kerosene type jet fuel, LPG, Lignite,
Motor gasoline, Municipal solid waste non renewable/renewable, Natural gas,
Other biomass, Other bituminous coal, Other recovered gases, Patent fuel,
Peat, Peat products, Solar nonspecified, Sub bituminous coal — see the file
for the exact list per flow).

This was noticed as a side effect of an unrelated fix (correcting a
Liquefaction/Regasification LEAP-to-ESTO mapping mix-up in
`config/outlook_mappings_master.xlsx`, sheet `leap_combined_esto`, plus
adding a wildcard placeholder-alias mechanism to
`codebase/mapping_tools/inverted_conservation_validation.py` for the Heat
plants / Heat plant interim duplicate-branch pattern). It is **not** caused
by either of those changes — it does not involve Buildings, Services,
Liquefaction, Regasification, CHP, Electricity, or Heat plants mappings at
all. It is a pre-existing gap; nobody has investigated why it exists.

## What is not yet known (this is the actual task)

1. **Is this expected or a real gap?** LEAP's `Buildings`/`Buildings/Services`
   branches may simply model more granular fuel-level detail (e.g. solar,
   geothermal, hydrogen, various biomass sub-types) than the Ninth Outlook
   dataset's residential/commercial sector rows ever report — in which case
   this is a genuine, permanent one-sided granularity gap (analogous to the
   already-understood coal `01_x_thermal_coal` and Transport
   freight/passenger cases documented elsewhere), not a bug.
2. **Or is it a broken/missing mapping?** It's possible some of these fuels
   *do* have Ninth-side data under a residential/commercial sector code that
   simply isn't wired into the `leap_combined_ninth` or
   `ninth_pairs_to_esto_pairs` sheets of
   `config/outlook_mappings_master.xlsx`, in which case this is a real,
   fixable coverage gap.
3. **Why do both `Buildings` and `Buildings/Services` show almost the
   identical fuel list?** Understand what distinguishes these two LEAP flow
   labels (parent/child? subtotal vs. leaf? one is a rollup of the other?)
   using `results/tree_structure/all_dataset_trees.csv` (dataset `leap`,
   axes `sector`/`fuel` — note axis names are `sector`/`fuel`, not
   `flow`/`product`, for the LEAP dataset) and
   `config/outlook_mappings_master.xlsx` sheet `leap_rollup_rules`. If
   `Buildings/Services` rolls up into `Buildings` (or vice versa), some of
   this "gap" may be double-counted noise from checking both levels rather
   than 71 distinct real gaps.

## Where to look

- `results/common_esto/inverted_conservation_variant_verification/inverted_conservation_no_counterpart.csv`
  — filter `target_flow.isin(["Buildings", "Buildings/Services"])` and
  `counterpart_state == "target_without_source"`.
- `results/common_esto/structural_artifacts/source_pair_to_common_row.csv`
  — filter `source_system == "LEAP"` and
  `original_source_flow.isin(["Buildings", "Buildings/Services"])` to see
  which common rows these components landed in, and whether any Ninth-side
  rows exist for the same `common_row_id`.
- `config/outlook_mappings_master.xlsx`, sheets `leap_combined_ninth` and
  `ninth_pairs_to_esto_pairs` — check whether Ninth residential/commercial
  sector codes (e.g. `16_01_residential`, `16_x` variants) are mapped to
  these LEAP flows for any of the listed fuels, and if not, whether Ninth
  actually carries that data anywhere.
- `NINTH unique sectors and fuels` sheet in the same workbook, to see the
  full Ninth sector/fuel vocabulary available for buildings/residential use,
  to compare against what LEAP models.

## Constraints

- Do not change `config/outlook_mappings_master.xlsx` or any mapping
  without first establishing (and stating explicitly) whether each fuel gap
  is a genuine one-sided granularity limit (leave as-is, same as the
  documented coal/transport cases) or a fixable missing link (propose the
  specific new mapping row).
- Do not touch anything related to Liquefaction, Regasification, CHP,
  Electricity, or Heat plants — those are separate, already-resolved issues.
- If you do add new mappings, rerun Stage 1 → Stage 2 →
  `compile_structural_mapping_artifacts` → `run_inverted_conservation_validation`
  (economies `{"20USA"}`, years `{"ESTO": {2023}, "NINTH": {2023}}` is a fast
  sanity-check scope) and confirm the specific Buildings/Buildings-Services
  rows disappear from `inverted_conservation_no_counterpart.csv` without
  changing any other check's `check_difference` or `fully_attributed` value.

## Success criteria

- A clear determination, fuel-by-fuel or as one summary judgement, of which
  Buildings/Buildings-Services gaps are permanent granularity limits versus
  fixable coverage gaps.
- For any fixable gaps, a proposed (or applied, if requested) mapping fix,
  verified not to regress any other `inverted_conservation_*` check.
- An explanation of the `Buildings` vs `Buildings/Services` relationship
  (item 3 above) so future readers of the no-counterpart file understand
  whether they are seeing one gap or two.
