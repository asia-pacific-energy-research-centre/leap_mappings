# Fix: make NINTH emit the `09.01-09.02 Power sector` aggregate (9th source rollup)

Repo: `C:\Users\Work\github\leap_mappings`. Read `AGENTS.md` first and follow repo conventions.
This is an **implementation task** (code + verify). It is the "Fix A" half of a two-part change;
"Fix B" (below) is already implemented — do not undo it.

## Goal

In the Common ESTO comparison data, the NINTH source emits **zero** rows for the flow
`09.01-09.02 Power sector`, while LEAP emits it fine. Because the transformation-sector tree lists
`09.01-09.02 Power sector` as a direct child of `09 Total transformation sector`, its absence for
NINTH shows up as a large `missing_expected_children` gap in the recursive-sum validation
(`results/tree_structure/common_esto_validation.csv`).

Make the 9th source construct/emit `09.01-09.02 Power sector` (the aggregate of its component
sectors) for NINTH, consistently with how the 9th's other rollups already work — so the aggregate
node is present in `results/common_esto/common_esto_comparison_data.csv` for NINTH.

## What is already known (do not re-derive from scratch)

**The 9th rollup path already exists and works for most rollups.** Row counts in the current
`common_esto_comparison_data.csv`, by `common_flow_label` × `source_system`:

| ESTO flow (rolled target) | NINTH | LEAP |
|---|---|---|
| `09.07 Oil refineries (including own use)` | **40,263** | 2,964 |
| `09.06.02 Liquefaction/regasification plants (including own use)` | **6,626** | 456 |
| `09.06.01 Gas works plants (including own use)` | **3,318** | 8 |
| `09.01-09.02 Power sector` | **0** | 2,261 |
| `09.08 Coal transformation (including own use)` | 0 | 0 |
| `09.12 Non-specified transformation (including own use)` | 0 | 234 |

So oil refineries / gas works / liquefaction rollups assemble correctly for NINTH; **Power sector
does not**. This is a targeted breakage, not a missing whole path.

**The rule and mapping both exist.** In `config/outlook_mappings_master.xlsx`:
- `ninth_rollup_rules`: inputs `09_01_electricity_plants; 09_02_chp_plants; 09_x_heat_plants`
  → rolled `09_01-09_02,09_x Power sector` (3 rows, rows 20–22, `include=True`).
- `ninth_pairs_to_esto_pairs`: `09_01-09_02,09_x Power sector` → esto_flow `09.01-09.02 Power sector`.

**The NON_EXPANDING flag was already flipped True→False** on those 3 rows (making the rule
"ordinary"). That alone did **not** make it emit — so the flag is not the blocker. Decide during
this task whether to keep the flip (if the fix needs ordinary classification) or revert it; document
the choice. Note the rolled label is a **composite** — `09_01-09_02,09_x Power sector` (embedded
comma, dash and spaces) — unlike the clean sector-code labels of the working rollups
(`09_07_oil_refineries_incl_own_use`). This is the leading suspect.

**Where it drops out (partial trace).** After the flag flip and a full rebuild:
- `results/mapping_relationships/energy_balance_relationships.csv` **does** contain 114 NINTH rows
  with `source_flow = 09_01-09_02,09_x Power sector` → `target_flow = 09.01-09.02 Power sector`.
- `results/mapping_relationships/ninth_results_converted_to_esto.csv` has **0** rows targeting
  `09.01-09.02 Power sector` — **and also 0 for `09.07 Oil refineries (including own use)`**, even
  though oil refineries ends up with 40k rows in the final comparison data. So the working rollups
  are **not** assembled in the 9th converter; they are assembled later at the **Common ESTO
  structure stage**. The Power sector aggregate is not being assembled at that stage for NINTH.

Conclusion to confirm: the 9th data value for the rolled source flow `09_01-09_02,09_x Power sector`
(sum of the three component sectors) is never constructed, most likely because the composite label
isn't handled the way clean rolled sector codes are in the rollup component
registration / target expansion. Find the exact layer and fix it there.

## Method (work one case end-to-end before generalising)

Use NINTH / economy `05_PRC` / one recent year / product `01.02-01.04 Coal` (the 9th has clear
coal values in the power sectors here: `09_01_electricity_plants` ≈ −46,687 for `01_x_thermal_coal`
in 2023). The mapped aggregate for NINTH should be roughly the sum of the three component sectors'
mapped coal values.

1. **Trace the working case.** Find where `09.07 Oil refineries (including own use)` gets assembled
   into `common_esto_comparison_data.csv` for NINTH (it is absent from the 9th converter output, so
   the assembly is downstream). Likely modules: `build_common_esto_structure.py`,
   `apply_common_esto_structure.py`, `apply_partitioned_common_esto.py`, and the ESTO overrides /
   rollup handling in `build_energy_balance_relationships.py`
   (`_apply_ninth_rollup_rules`, `expand_ninth_rollup_targets`,
   `_build_rolled_ninth_sector_to_components`). Pin the function that emits the NINTH aggregate row.
2. **Trace the Power sector case through the same path** and find where it diverges from oil
   refineries. Test the composite-label hypothesis directly: does
   `_build_rolled_ninth_sector_to_components` / the rollup target expansion register
   `09_01-09_02,09_x Power sector` and its 3 components correctly, or does the comma/dash/space break
   parsing or a prefix/label match?
3. **Fix at the layer where the working rollups are assembled**, so Power sector is handled by the
   same machinery (honor the principle: source rollups apply uniformly across datasets). Prefer the
   minimal change that makes the existing mechanism handle the composite/pure-aggregation case over a
   parallel code path. If the composite label is genuinely unparseable, consider whether the correct
   fix is to normalise/rename the rolled label to a clean form in both `ninth_rollup_rules` and
   `ninth_pairs_to_esto_pairs` (keep the two sheets consistent) — but confirm that is the real cause
   first.
4. Once Power sector emits, re-check `09.08 Coal transformation (including own use)` and
   `09.12 Non-specified transformation (including own use)` (also currently 0 for NINTH) — the same
   root cause may fix them; if not, note them as separate follow-ups (out of scope to fix here unless
   trivial).

## Verification / acceptance criteria

Re-run the affected stages (`python codebase/run_mapping_pipeline.py --stages 1,2,data_convert,3`,
or the full pipeline) and confirm:

1. **Emission:** `common_esto_comparison_data.csv` has nonzero NINTH rows for
   `09.01-09.02 Power sector`, with magnitude ≈ the sum of the three component sectors' mapped values
   (spot-check `05_PRC` / `01.02-01.04 Coal`).
2. **No double counting / reconciliation not worsened:** In `common_esto_validation.csv`, the
   `09 Total transformation sector` × NINTH checks must not get worse. With Fix B in place, once the
   aggregate is present the resolver keeps it instead of expanding to the leaves
   (`09.01.01,09.02.01 Electricity plants`, …), so the aggregate and its leaves must **not** both be
   summed as children of `09`. Compare `parent_value` vs `children_sum` for the PRC coal case before
   and after; the residual should shrink or hold, never balloon.
3. **Partition sizes (the reason it was NON_EXPANDING):** inspect the Common ESTO partition / QA
   outputs (e.g. `results/mapping_relationships/qa/`, `non_expanding_rollups.csv`, and any
   partition-size report from Stage 2). Confirm no oversized "mega-partition" was reintroduced.
   Report the largest partition sizes before vs after.
4. **No collateral:** LEAP Power sector count stays ~2,261; other sources/flows unaffected.
5. Full pipeline completes; spot-check the 20_USA dashboard render
   (`leap_dashboard`, `COMMON_ESTO_ECONOMIES=20_USA python codebase/common_esto_dashboard_workflow.py`).

## Context — the already-done "Fix B" (do not undo)

`_validate_common_esto_axis_recursive_sums` in
`codebase/mapping_tools/build_dataset_tree_structure.py` was changed so recursive-sum resolution is
**per source system**: presence of an intermediate subtotal is decided against each source's own
emitted labels (`data_codes_by_system`) instead of a global union. This stops one source's aggregate
(LEAP's Power sector) from masking another source's need to expand to the leaves it emits (NINTH's
electricity/heat plants). Verified: it collapsed the PRC transformation×coal gap from ≈ −180,058 to
≈ −3,020. This fix composes with the present task: emitting the aggregate makes the resolver keep it;
leaving it absent makes the resolver expand to leaves. Either way the parent reconciles.

## Known pitfalls

- `config/outlook_mappings_master.xlsx` is frequently open in Excel — a lock file
  `config/~$outlook_mappings_master.xlsx` appears and `openpyxl` saves fail with `PermissionError`.
  Likewise `results/tree_structure/common_esto_validation.csv` open in Excel makes Stage 3 fail on
  write. Ensure both are closed before running.
- Do not confuse the **ESTO-side** Power sector rollup (`esto_rollup_rules`: inputs
  `09.01 Main activity producer + 09.02 Autoproducers`, already ordinary) with the **9th-side** one
  (`09_01 + 09_02 + 09_x`). The 9th one additionally includes `09_x_heat_plants`.
- Some `codebase/*.py` files carry a UTF-8 BOM; read as `utf-8-sig` for AST/regex tooling.
- Large results CSVs — read with `usecols`/`chunksize` where practical.

## Out of scope

- Fix B (already implemented).
- The `(including own use)` variants' membership as children of `09` in the tree (handled separately
  by blanking `parent_flow_label` in `esto_rollup_rules`).
- Broader redesign of the rollup architecture — make Power sector work within the existing machinery.
