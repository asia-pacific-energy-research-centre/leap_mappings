# New LEAP rows mapping progress — 2026-07-28

## Scope

Source inventory:
`data/temp/new leap rows.xlsx`

Working mapping workbook:
`config/outlook_mappings_master todo.xlsx`

Pre-edit backup:
`config/archive/outlook_mappings_master_todo_before_new_leap_rows_20260728_152652.xlsx`

The backup SHA-256 is
`CDC38ABF3FB237ACEA9A9905A722284199A1ED38FA9FAB7526917B4C63A17F95`.

## Applied changes

| Change | Count |
| --- | ---: |
| Shifted Buildings product cells corrected | 35 |
| Wrong duplicate Buildings/Bagasse row removed | 1 |
| Initial LEAP-to-ESTO additions | 162 |
| Initial LEAP-to-Ninth additions | 223 |
| Non-zero transport Ninth-to-ESTO Extended additions | 111 |
| Rejected CHP/heat fan-out rows removed | 72 |
| Power LEAP-to-ESTO additions, including rolled rows | 152 |
| Power LEAP-to-Ninth additions | 117 |
| Power Ninth-to-ESTO Extended additions | 116 |
| Power ESTO rollup-rule additions | 60 |
| Power LEAP rollup-rule additions | 6 |
| Power Ninth rollup-rule additions | 7 |
| Rejected demand mappings for newly observed source fuel labels removed from each direction | 14 |

The one-row difference between the planned and inserted power
Ninth-to-ESTO counts is an existing exact key, not a dropped candidate.

## Intentional non-mappings

- The three detailed iron-and-steel routes remain LEAP/ESTO Extended only.
  They do not have defensible Ninth counterparts.
- Branches ending in `_do not use` are legacy and remain unmapped.
- Raw Other and solid-biomass power children use explicit comparison rollups
  on the Ninth-inclusive axis rather than partial direct sibling mappings.

## Newly observed fuel labels

The mapping workbook now uses the spellings emitted by the LEAP balance parser:

- `Fuelwood and woodwaste` becomes `Fuelwood & woodwaste`;
- `Black liqour` becomes `Black liquor`;
- `of which Photovoltaics` becomes `Solar photovoltaics`;
- the literal label `Solar` remains `Solar`.

The literal `Solar` source pairs are deliberately mapped to ESTO
`12.99 Solar nonspecified`. On the Ninth axis they map to the appropriate
nonspecified-solar code for the sector: `12_solar_unallocated` in demand and
the existing `12_x_other_solar` category for the reviewed power technologies.
This is a semantic allocation decision, not a spelling normalization.

`data/temp/new leap rows.xlsx` retains the supplied source labels and has a
`FOLLOW-UP` column on the `demand` and `power` sheets. It asks modellers to
correct `Black liqour` at source and, when practical, rename the generic
`Solar` branch to `Solar nonspecified`. The mapping layer is nevertheless
ready to handle the current export on the next run.

## Municipal-waste source decision

The combined source branch
`Electricity Generation/Processes/Others + Municipal solid waste non and renewable`
has been retired from `data/temp/new leap rows.xlsx`. It is intentionally not
mapped.

The two split branches remain and are mapped:

- `Municipal solid waste non renewable` to ESTO
  `16.04 Municipal solid waste (non-renewable)` and Ninth
  `16_04_municipal_solid_waste_nonrenewable`;
- `Municipal solid waste renewable` to ESTO
  `16.03 Municipal solid waste (renewable)` and Ninth
  `16_03_municipal_solid_waste_renewable`.

The Ninth-inclusive comparison uses the reviewed
`Other and solid biomass` power rollup rather than a partial direct mapping of
the raw `Others` process.

Both retained split municipal-waste rows are also marked in the `FOLLOW-UP`
column so the power modellers know that the combined branch was retired and
must not be reintroduced.

## Verification completed

- The no-edit `openpyxl` round trip preserved workbook behaviour and formatting;
  only equivalent duplicate conditional-format style IDs were normalized.
- Every applied batch was re-read by exact four-column mapping identity.
- No exact duplicate mapping keys were introduced.
- Every new rolled ESTO Extended mapping target has a declared rollup rule.
- All 956 supplied source pairs were checked against both LEAP mapping
  directions.
- LEAP-to-ESTO covers 947 pairs. The remaining nine are the agreed legacy
  `_do not use` power branches.
- LEAP-to-Ninth covers 855 pairs. The remaining 101 are exactly the 63
  detailed iron-route pairs, 29 raw power children handled by explicit
  rollups, and nine `_do not use` branches.
- The inventory has 257 populated `FOLLOW-UP` cells: 252 demand warnings and
  five power warnings, including the two split municipal-waste reminders.
- No mapping row retains `Fuelwood and woodwaste`,
  `of which Photovoltaics`, or `Black liqour`.
- The five changed or added source pairs have one target in each direction and
  a matching Ninth-to-ESTO triangle.
- Column widths, freeze panes, filters, data validations, conditional-format
  semantics, and unchanged-row styles match the pre-edit backup.
- Focused parser, mapping-conversion, maintenance, ESTO Extended, and
  non-expanding-rollup tests: `45 passed`.

The full mapping pipeline has not been run against this todo workbook because
the hierarchy/subtotal contract is being changed concurrently. The canonical
`config/outlook_mappings_master.xlsx` has not been replaced. Synthetic ESTO
Extended historical values remain a separate decision and must not be treated
as validated by this mapping pass.
