# Handoff prompt: holistic mapping-system stocktake and prioritisation

You are taking over work in `C:\Users\Work\github\leap_mappings`. The goal is
to understand the mapping system as a whole and identify the biggest remaining
problems before making more local fixes. Do not assume that the latest reported
failure count is a list of mappings to add.

Use `C:\Users\Work\miniconda3\python.exe` for Python. Read the repository
`AGENTS.md` instructions, `docs/mappings_system.md`,
`docs/rollup_rules_system.md`, and the relevant prompt/archive notes before
editing anything. Use `apply_patch` for edits. Do not delete or revert
user-owned files.

## Immediate coordination

Start with:

```powershell
git status --short
git log -12 --oneline
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*run_mapping_pipeline.py*' } |
  Select-Object ProcessId,CommandLine
```

There may be an active Stage 3 run. Do not start another pipeline while one is
running, and do not interrupt it. Inspect its log and outputs only at the
repository's permitted polling cadence. Treat generated `results/` files as
reproducible outputs, not source inputs.

The current work may contain user-owned workbook/config/document changes.
Preserve them and do not include them in a commit unless explicitly requested.
In particular, inspect rather than automatically altering:

- `config/outlook_mappings_master.xlsx`
- newly supplied workbook variants or extensionless Excel/Office artifacts in
  `config/`
- `docs/REPO_CLEANUP_AND_NAVIGATION_NOTES.md`

## Current context

The mapping pipeline now uses `config/outlook_mappings_master.xlsx` as its
canonical workbook. The usual command is:

```powershell
C:\Users\Work\miniconda3\python.exe codebase\run_mapping_pipeline.py --stages 1,2,3
```

The CLI currently expands `--stages 1,2,3` to include LEAP parsing and
`data_convert`, unless those dependencies are explicitly skipped. Stage 0 is
preview-only; `--apply-maintenance` is a deprecated no-op.

Recent agent commits introduced hierarchy-aware source parent validation:

- `00dffd5` — canonicalise tree labels to structural paths.
- `125d367` — use descendant mappings to resolve a parent row's deep opposite
  axis.
- `d2d20d7` — prefer the deepest compatible nested mapped ancestor.

Focused tests pass, but the latest full Stage 3 run showed that the fallback is
not yet a complete solution: NINTH product failures increased from about
2,047 to 3,848 because previously unanchorable rows became eligible, while
deep passenger-road rows still appeared as
`no_anchorable_common_esto_boundary`. Treat this as diagnostic evidence, not a
successful final fix. Determine whether the implementation is too broad,
whether the remaining issue is target/Common-row resolution, or whether both
are true.

The user’s design preference is important:

- Prefer improving canonical mappings, hierarchy handling, rollup mechanics,
  and diagnostics.
- Do not add fuel-parent exceptions merely to silence failures.
- Do not add detailed mappings for aggregate fuels such as
  `07_petroleum_products`, `08_gas`, `15_solid_biomass`, or `16_others` when a
  source/target hierarchy rollup is the correct representation.
- Preserve exact detailed mappings. For example,
  `14_03_02_chemical_incl_petrochemical` already has mappings and must not be
  unnecessarily rolled to `14_03_manufacturing`.
- ESTO often stops at a coarser boundary than the 9th Outlook. A detailed 9th
  source sector such as `15_02_01_passenger` should be carried to the nearest
  mapped ESTO-supported parent such as `15.02 Road`, with lineage and
  double-counting protection.

## Holistic stocktake objective

Produce an evidence-based assessment of the mapping system’s largest problems,
ranked by impact and confidence. Before changing code or the workbook, answer:

1. Which failure families dominate current outputs by source system, comparison
   scope, axis, economy, year, fuel/flow family, and reason?
2. For each major family, is the root cause primarily:
   - a missing human mapping;
   - a valid but unimplemented hierarchy rollup;
   - a mapping compiler/relationship expansion problem;
   - a Common ESTO graph/partition problem;
   - a data-conversion or allocation problem;
   - a validator/frontier-definition problem;
   - a genuine source-data inconsistency; or
   - stale/duplicate/generated output?
3. Which issues are the same underlying problem appearing in several reports?
   Look especially for parent/child failures, subtotal-vs-leaf overlaps,
   own-use boundaries, source-side detail vs ESTO coarse boundaries, and
   target-side rollups.
4. Which four aggregate fuel groups are genuinely missing nonzero coverage,
   and which failures are zero-only or unanchorable structural cases?
5. Are the current mapping files and generated relationship outputs internally
   consistent? Check cardinality, duplicate mappings, source conservation,
   rollup provenance, and whether exact mappings are being superseded by
   fallback logic.
6. Does the current hierarchy resolver choose the nearest valid ancestor for
   every comparable source row, while rejecting unrelated or conflicting
   ancestors? Test this with at least one passenger-road case, one
   transformation case, and one exact detailed mapping.
7. Which problems should be fixed first to reduce the most real errors with the
   least risk? Give a small ordered backlog, not a long undifferentiated list.

## Required investigation outputs

Do not edit the canonical workbook or implement a fix until the stocktake is
written. Produce a concise report in the response or in a new findings note
under `docs/prompts/` containing:

- a current-state summary;
- a ranked table of the largest failure families;
- representative examples with exact source pair, mapped target pair, source
  value, Common ESTO row, and reason;
- a mapping-vs-system-vs-source-data classification for each example;
- a list of mappings that are genuinely clear enough to propose, with the
  destination sheet and all required columns;
- a list of cases where a generic system improvement is preferable to adding
  workbook rows;
- explicit uncertainty and what evidence would resolve it;
- a proposed test plan and a safe next sequence of changes.

Keep debug-heavy extracts in a clearly named diagnostics folder. Do not create
large duplicate copies of existing 600MB-scale outputs unless necessary.

## Verification expectations

Use focused, reproducible checks first. At minimum inspect:

```powershell
rg -n "outlook_mappings_master|master_config|leap_mappings.xlsx|anchor_diagnostics|tree_structure|run_stage_3|expand_requested_stages" codebase docs tests
pytest -q tests/test_structural_resolver.py tests/test_source_parent_anchor_validation.py
git diff --check
```

Only after the stocktake identifies a specific low-risk fix should you edit
code or mappings. If you do implement a fix, add a focused regression test,
run the relevant test suite, rerun the affected pipeline stage, compare before
and after failure classifications, and commit only your own files with a
`codex:`-prefixed message. Do not treat a lower failure count alone as proof of
correctness: verify conservation, lineage, cardinality, and the absence of
double counting.
