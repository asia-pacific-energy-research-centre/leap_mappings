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

## All-producers comparison boundary — 2026-09-03

Undifferentiated LEAP and Ninth Power sources now map once to the registered
comma-joined target which combines the main-activity and autoproducer ESTO
components. The components remain real ESTO contributors and are combined by
the reviewed expanding `power_process` rollups; the source is therefore not
duplicated across producer types. The review workbook records 53 component-row
replacements, 27 combined targets, 54 retained rollup-lineage component rows,
and 146 removed erroneous `843` blank-field sentinels.

The single-axis compiler now re-expands registered rollups after reviewed
extra exact pairs are merged. This preserves compiler-generated pair and
master-workbook output for a reviewed mapping rather than treating that row as
an unexpanded exception. The focused regression suite passes (31 tests). The
2026-09-03 stages 1–3 run completed: the Stage 1 zero-fan-out assertion passed
for every scope; Stage 2 found no missing/duplicate components and kept the
43 non-expanding subtotal frontiers separate; Stage 3 preserved mapped source
totals at 100% in every comparison scope (maximum before/after difference
`1.1641532182693481e-10`). Existing unknown-target, unresolved-rollup,
partial-coverage, and unmapped-source QA files remain findings for review, not
pipeline blockers.
