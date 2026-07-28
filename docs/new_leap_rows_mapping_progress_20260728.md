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
| Exact mappings for newly observed source fuel labels (`Solar`, `Black liqour`) per direction | 14 |

The one-row difference between the planned and inserted power
Ninth-to-ESTO counts is an existing exact key, not a dropped candidate.

## Intentional non-mappings

- The three detailed iron-and-steel routes remain LEAP/ESTO Extended only.
  They do not have defensible Ninth counterparts.
- Branches ending in `_do not use` are legacy and remain unmapped.
- Raw Other and solid-biomass power children use explicit comparison rollups
  on the Ninth-inclusive axis rather than partial direct sibling mappings.

## Newly observed fuel labels

These rows do not introduce new ESTO or Ninth fuel categories. They make exact
source-label mappings for labels that the initial inventory parser did not
recognize because they were not already present in the mapping workbook.

- `Black liqour` is the misspelled literal label in the supplied LEAP
  structure. It must remain exact on the LEAP side so exported data matches,
  while mapping to the established `15.04 Black liquor` ESTO product and
  `15_04_black_liquor` Ninth fuel. It occurs in 12 reviewed demand sectors.
- `Solar` is distinct from the existing LEAP label `Solar nonspecified`. Its
  two reviewed demand occurrences map to the established ESTO product
  `12 Solar` and Ninth fuel `12_solar`.

This is 14 source sector/fuel pairs in each mapping direction, but only two
newly observed source labels.

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

## Verification completed

- The no-edit `openpyxl` round trip preserved workbook behaviour and formatting;
  only equivalent duplicate conditional-format style IDs were normalized.
- Every applied batch was re-read by exact four-column mapping identity.
- No exact duplicate mapping keys were introduced.
- Every new rolled ESTO Extended mapping target has a declared rollup rule.
- Column widths, freeze panes, filters, data validations, conditional-format
  semantics, and unchanged-row styles match the pre-edit backup.
- Focused tests:
  `29 passed` in `tests/test_esto_extended_test.py` and
  `tests/test_non_expanding_rollups.py`.

The full mapping pipeline has not been run. Synthetic ESTO Extended historical
values remain a separate decision and must not be treated as validated by this
mapping pass.
