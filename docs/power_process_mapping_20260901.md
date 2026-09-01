# Power process mapping update — 2026-09-01

Status: implemented and verified.

- Electricity-generation process branches now map to stable ESTO Extended
  `09.01.01.xx` and `09.02.01.xx` flows through the editable single-axis
  authority workbook.
- Their target flow/product pairs are explicitly registered, including the
  storage branch for future workbooks.
- `Processes` is treated as an optional structural LEAP path segment during
  conversion, so clean exports and older relationship paths resolve to the
  same process without changing source lineage.
- CHP and heat-plant relationships use the same canonical-path rule.

Verification:

- Separate-axis refresh completed with no duplicate cleanup or formula errors.
- Mapping pipeline Stages 1–2 completed with zero fan-out assertions passing.
- Focused conversion and single-axis tests pass.
