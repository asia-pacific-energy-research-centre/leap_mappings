# Prompt: set the blank `ninth_fuel` values in the canonical mapping workbook

**Created:** 2026-07-28 · **Queue IDs:** MAPQ-027 (this work), MAPQ-026 (the
variant-workbook decision that depends on it) · **Status:** active

---

## Your task

There are three rows in `config/outlook_mappings_master.xlsx` that are active
mappings but have a blank `ninth_fuel`. A previous investigation derived a
suggested value for each **by computer**. Those suggestions are candidates
only — some of them may be wrong, and I want to set the correct value with you,
row by row.

Work with me interactively. Your job is to lay out the evidence for each row,
propose options, and then write **only** what I explicitly confirm.

## Two hard constraints — read these before doing anything

### 1. Do not assume what I want

- Every value written to the workbook must be **confirmed by me first**, one row
  at a time. Do not batch them.
- The computer-derived suggestions below are **not** decisions. Treat them as
  one option among several. If the evidence supports an alternative, say so.
- If I say something ambiguous, ask. Do not resolve ambiguity by picking the
  most likely reading and proceeding.
- "Leave it blank" is a legitimate outcome for any of these rows. Do not treat
  filling all three as the goal.
- Do not extend the scope. If you notice other rows that look wrong, list them
  at the end for me to consider separately — do not fix them.

### 2. Do not change the sheet's formatting in any way

This workbook is hand-maintained. Formatting, column widths, colours, data
validations, conditional formatting, freeze panes, and filters all carry
meaning to the humans who edit it.

- **Never** use `pandas.DataFrame.to_excel`, `pd.ExcelWriter`, or anything that
  rewrites a sheet wholesale. That destroys all formatting.
- Write by direct cell assignment only: `ws.cell(row=r, column=c).value = v`.
- Change **only** the specific cells I confirm. Do not touch any other cell, row,
  column, or sheet — including "tidying" blank rows or trailing whitespace.
- Do not add, rename, reorder, or delete sheets.
- Do not sort or re-index anything.

**Before you edit the real workbook, prove the round-trip is lossless.** Copy the
workbook to the scratchpad, `load_workbook` and `save` it with **no** edits, then
compare the saved copy against the original and report to me: sheet names and
order, per-sheet row/column counts, column widths, freeze panes, autofilter
ranges, data validations, conditional formatting rules, and a sample of cell
styles (font, fill, number format) from each sheet. If anything is lost, **stop
and tell me** — we will edit in Excel by hand instead.

## Before you start

1. Read `AGENTS.md` in the repo root. The "LEAP mapping maintenance" and
   "Computer-generated mapping candidates" sections apply directly to this task.
2. Read `docs/workbook_variant_row_comparison_20260728.md` — the investigation
   that produced these candidates, including the full evidence and the reasoning
   for what was rejected.
3. Confirm `config/outlook_mappings_master.xlsx` is **closed in Excel**. If
   `config/~$outlook_mappings_master.xlsx` exists, the workbook is open — ask me
   to close it. Writing to an open workbook fails or corrupts.
4. Back it up first. The repo convention is a `shutil.copy2` into
   `config/archive/` before any workbook edit; follow the existing naming
   pattern there.
5. Use `C:\Users\Work\miniconda3\python.exe` for all Python. The repo `.venv` is
   WSL-created and will not run from Windows shells, and PowerShell's `python`
   alias swallows output.

## The three rows

All are on sheet **`leap_combined_ninth`**, all are active
(`duplicate_to_remove` is not `True`), all have `ninth_sector` populated and
`ninth_fuel` blank. These are the only 3 such rows out of 2,711 active rows.

| # | `leap_sector_name_full_path` | `raw_leap_fuel_name` | `ninth_sector` | `ninth_fuel` | Computer-suggested value |
|---|---|---|---|---|---|
| 1 | `Gas works plants/Gas works plants` | `Blast furnace gas` | `09_06_01_gas_works_plants_incl_own_use` | *(blank)* | `02_coal_products` |
| 2 | `Gas works plants/Gas works plants` | `Other recovered gases` | `09_06_01_gas_works_plants_incl_own_use` | *(blank)* | `02_coal_products` |
| 3 | `Heat plant interim/Heat plant interim` | `Bitumen` | `09_x_heat_plants` | *(blank)* | `07_x_other_petroleum_products` |

Locate each row by matching all four key columns, not by row number. Confirm the
row index you find with me before writing.

## Evidence already gathered — verify it, don't just trust it

Derived by inferring the two axes independently, as `AGENTS.md` requires.

**Rows 1 and 2 (Gas works plants):**
- `Blast furnace gas` maps to `02_coal_products` in 36 of 36 other active rows.
- `Other recovered gases` maps to `02_coal_products` in 35 of 35 other active rows.
- The same `Gas works plants` block already maps `Coal tar`, `Coke oven coke`,
  and `Coke oven gas` to `09_06_01_gas_works_plants_incl_own_use` /
  `02_coal_products`.
- Filling these makes five LEAP fuels map to one 9th pair. That is many-to-one
  aggregation, not many-to-many — expected where LEAP carries finer fuel detail
  than the 9th edition's `02_coal_products` bucket. **Re-check this cardinality
  claim yourself before I confirm.**

**Row 3 (Heat plant interim):**
- `Bitumen` maps to `07_x_other_petroleum_products` in 23 of 23 other active rows.
- This row is blank in both the canonical workbook and the
  `outlook_mappings_master_combined_esto.xlsx` variant, so unlike rows 1 and 2 no
  second source proposes a value for it. Weigh that.

## Already decided — do not reopen these

From the same investigation, for context only:

- **228 inactive rows** present in the `combined_esto` variant but not in
  canonical will **not** be adopted. They are `duplicate_to_remove = True`,
  concentrated in road vehicle technologies and iron-and-steel process routes —
  branches where LEAP models more detail than the 9th edition, which is the
  documented reason such rows are deactivated.
- **`CHP plants/Processes/Coal CHP` + `Electricity` → `09_02_chp_plants` /
  `17_electricity` is rejected.** Canonical already actively maps the parent
  `CHP plants` + `Electricity` to that same target, and no process-level CHP
  child is mapped anywhere in the workbook. Adding it would double-count.

Do not import rows from `config/outlook_mappings_master_combined_esto.xlsx`. It
carries the 228 unwanted inactive rows. Edit the canonical workbook directly.

## Method

1. Do the lossless round-trip proof described above. Report and wait.
2. For each row in turn:
   - Show me the row as it currently stands, with its sheet row number.
   - Show the independent evidence for each axis, re-derived by you.
   - State the cardinality consequence of filling it (how many LEAP sources
     would then point at that 9th pair, and whether any many-to-many results).
   - Give me the options, including leaving it blank, and your recommendation
     with your confidence.
   - **Wait for my explicit confirmation of the exact value.**
3. Write only the confirmed cells, one at a time, by direct cell assignment.
4. After writing, re-open the workbook and read back every changed cell to
   confirm the value landed and nothing adjacent moved.
5. Report a summary: which cells changed, from what to what, the backup path,
   and anything you noticed but did not touch.

## What "done" looks like

- Every one of the three rows has an explicit decision from me — a value, or a
  deliberate "leave blank".
- No cell other than the confirmed ones has changed.
- The formatting comparison after editing matches the before state.
- `docs/workbook_variant_row_comparison_20260728.md` and `docs/work_queue.md`
  (MAPQ-027) are updated to record what was decided and why.

## Important caveat to carry into the report

These rows are currently **inert on the fuel axis** — a blank `ninth_fuel` means
they contribute nothing. Filling it **activates** a mapping that was not
previously contributing. This is a behaviour change, not a cosmetic edit, and it
needs a validating pipeline rerun (queue item MAPQ-005) before the result is
trusted. Do not run the pipeline yourself unless I ask; it is long-running and
the repo is mid-handover.

## Optional second item — only if I say so

`IS_LEAP_ROLLUP_NAME` on sheet `leap_display_names` is blank in all 605 rows of
the canonical workbook, but populated in the `combined_esto` variant (21 `True`,
490 `False`, 94 blank). No code currently reads the column — it appears only in a
docstring in `codebase/functions/unified_name_lookup.py`, a standalone tool with
no importers. The 21 `True` flags are real metadata worth recovering before that
variant workbook is deleted.

This is a separate decision. Do not start it until the three rows above are
settled and I have asked for it. The same two hard constraints apply.
