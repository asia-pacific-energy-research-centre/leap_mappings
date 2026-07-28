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

The proposed exact mappings for the newly observed literal labels `Solar` and
`Black liqour` were rejected. A spelling or short label in the supplied
structure is not enough evidence that the branch is semantically equivalent to
the established ESTO or Ninth product.

The 14 proposed demand source pairs were therefore removed from both
`leap_combined_esto` and `leap_combined_ninth`. Existing reviewed power-process
relationships that happen to contain either literal label were not changed by
this removal; their source inventory rows are nevertheless flagged for
targeted modeller follow-up.

`data/temp/new leap rows.xlsx` now has a `FOLLOW-UP` column on the `demand` and
`power` sheets. It flags every supplied occurrence of `Black liqour` or
`Solar`, so the power modellers can confirm or correct the model branch rather
than having the mapping layer silently normalize it. There are 252 flagged
demand rows and four fuel-label follow-ups among the power rows.

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
- The rejected 14 demand source pairs are absent from both LEAP mapping
  directions.
- The inventory has 258 populated `FOLLOW-UP` cells: 252 demand fuel-label
  warnings, four power fuel-label warnings, and two split municipal-waste
  warnings.
- Column widths, freeze panes, filters, data validations, conditional-format
  semantics, and unchanged-row styles match the pre-edit backup.
- Focused tests:
  `29 passed` in `tests/test_esto_extended_test.py` and
  `tests/test_non_expanding_rollups.py`.

The full mapping pipeline has not been run. Synthetic ESTO Extended historical
values remain a separate decision and must not be treated as validated by this
mapping pass.
