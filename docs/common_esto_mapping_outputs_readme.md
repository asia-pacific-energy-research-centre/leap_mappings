# Common ESTO mapping outputs — a non-coder's guide

Two files, both under `results/common_esto/` (generated, not tracked in git —
regenerate with the commands at the bottom of this doc), produced by
`codebase/mapping_tools/build_source_to_common_esto_map.py` and
`codebase/mapping_tools/emissions_factor_resolution.py`. Both are plain
CSVs — open them in Excel or Google Sheets, no code required.

## `source_to_common_esto_map.csv` — "which native row becomes which common row"

**One row = one native (source_flow, source_product) pair, and the single
common category it belongs to.** Every column you need to read a row is on
that row:

| Column | What it means |
|---|---|
| `comparison_scope` | Which comparison this row applies to. There are four: `esto_leap`, `esto_leap_ninth`, `esto_extended_leap`, `esto_extended_leap_ninth`. **Filter to one scope before reading anything else** — the same native pair can map to a different common row in a different scope. |
| `source_system` | `LEAP` or `NINTH` (the 9th edition). ESTO is not in this file — it has its own, separate map (`esto_to_common_esto_map.csv`), because ESTO is what everything else is being compared against. |
| `source_flow` / `source_product` | The native LEAP or 9th-edition flow and product, exactly as that source reports it. |
| `common_flow_label` / `common_product_label` | The common category this native pair rolls up to. This is the human-readable answer — most readers only need these two columns plus the two above. |
| `common_row_id` | A stable internal ID for the common category. Only useful for joining this file to another one by code; ignore it if you are reading by eye. |

**How many native pairs share one common row?** However many the data
actually has — this file does not force a 1:1 shape. What it *does*
guarantee is the reverse: **one native pair never maps to more than one
common row.** That is checked automatically every time this file is
generated (`build_source_to_common_esto_map.py` raises an error and refuses
to write the file if it is ever violated) — a native pair mapping to two
different common rows would mean the same reported value gets counted in two
places, which is exactly the kind of error this map exists to prevent.

**The one thing not to do:** do not try to split a `source_flow` /
`source_product` pair into finer pieces than this file gives you. If LEAP or
the 9th only reported a combined total, there is no hidden detail underneath
it in this map — inventing a split would be guessing, and the source
mapping system's own rule (see `docs/mappings_system.md`) is "do not split a
source aggregate unless there is an explicit allocation method." This map
has none, on purpose.

**What's *not* in this file:** rows the mapping system could not place
anywhere. See `source_to_common_esto_map_coverage.csv` (next to the map) — it
lists every excluded native pair with a reason, rather than silently
dropping them. Most of those are legitimate: parent/rollup/total rows whose
detail is what actually gets mapped (e.g. "Total Primary Supply" is excluded
because its components — Production, Imports, Exports — are each mapped
individually; including the total too would double-count). A minority need
a human look before anyone builds further on this map — see
`leap_dashboard/outputs/overnight_20260806/w1_finding_unmapped_leap_links.md`
for the full breakdown and the specific pairs flagged for review.

## `emissions_factor_resolution.csv` — "how much CO2e per unit of each fuel"

**One row = one common product, and the CO2e factor to apply to it.**

| Column | What it means |
|---|---|
| `common_product_label` | The common fuel/product this factor applies to. |
| `emissions_factor` | The CO2e factor. Multiply a demand value in this product by this number to get its emissions. |
| `emissions_unit` | The unit the factor produces (`Mt CO2e`). |
| `derived_from` | **Where this factor actually came from.** Today every row says `ninth` — these factors are derived from the 9th edition's fuel-level CO2e table, carried through to the common axis. If this ever says something else, that means a different, independently-sourced set of factors is in play — check before assuming these are interchangeable with an older download of this file. |
| `esto_components` | Which ESTO product(s) fed into this row, for traceability. |
| `factor_source_keys` | Which 9th-edition fuel code(s) fed into this row, for traceability. |
| `factor_set_key` / `mapping_axis` | Internal bookkeeping — which configured factor set produced this row, and what axis it was keyed on. Not needed to use the numbers. |

**The one thing not to do:** do not assume this factor list changes only
when the underlying 9th-edition data changes. `derived_from` is the thing to
check, not an assumption — a future factor set could point somewhere else
entirely (e.g. real ESTO-native factors, once those exist), and this column
is exactly how a reader is meant to notice that without re-deriving the
whole chain.

## Regenerating either file

```bash
# from the leap_mappings repo root
C:\Users\Work\miniconda3\python.exe codebase\mapping_tools\build_source_to_common_esto_map.py
C:\Users\Work\miniconda3\python.exe codebase\mapping_tools\emissions_factor_resolution.py
```

Both are deterministic given the same upstream mapping files — running twice
with no upstream change produces byte-identical output.
