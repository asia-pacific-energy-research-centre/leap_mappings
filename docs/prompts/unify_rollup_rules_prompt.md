# Prompt: unify rollup-rule handling (NINTH/LEAP) and document the rollup system

Repo: `C:\Users\Work\github\leap_mappings`. Read `AGENTS.md` first and follow repo conventions.
Do NOT modify `config/outlook_mappings_master.xlsx` — it is user-maintained.

## Background (state as of 2026-07-09)

The workbook has three rollup-rule sheets with an identical schema (`input_X` → `rolled_X`,
plus `include`, `Note`, `Subtotal`, `parent_flow_label`, ...):

- `esto_rollup_rules`
- `leap_rollup_rules`
- `ninth_rollup_rules`

They are consumed in two different directions in
`codebase/mapping_tools/build_energy_balance_relationships.py`:

1. **Target-side "expand down"** (added 2026-07-09, ESTO axis only):
   `expand_esto_rollup_targets` — when a mapping sheet's `esto_flow` names a
   `rolled_esto_flow` (e.g. `09.08.01 Coke ovens (including own use)`), the row is expanded
   into one relationship per real component flow (`input_esto_flow` values), same product,
   provenance in `notes` (`expanded_from_esto_rollup: <rolled name>`). Because the expanded
   rows share one source pair, Stage 2 merges the components into one common row, and
   `build_preferred_flow_partition_labels` in `build_common_esto_structure.py` makes the
   merged row display the rolled name. A QA output
   `qa_unknown_esto_target_flows.csv` warns about ESTO targets that match no real flow.
   This applies to both ESTO-targeted sheets (`leap_combined_esto`,
   `ninth_pairs_to_esto_pairs`).
2. **Source-side "duplicate up"** (pre-existing): `_apply_leap_rollup_rules` /
   `_apply_ninth_rollup_rules` — leaf relationships are copied under the aggregate source
   label (e.g. every `Gas works plants` LEAP row copied with `source_flow="Gas processing
   plants"`), flagged `is_rollup_derived=True`. These flagged rows are deliberately
   EXCLUDED from common-structure merge edges (see the `build_source_aggregate_edges`
   docstring in `build_common_esto_structure.py`) — that exclusion prevents aggregate
   labels from blob-merging their descendants and must not be weakened.

The missing piece: **NINTH as a target axis**. `leap_combined_ninth` maps LEAP → NINTH, and
its `ninth_sector` column already contains rolled NINTH names (e.g.
`09_06_gas_processing_plants_incl_own_use`, `09_01-09_02,09_x Power sector`) that are not
real NINTH sectors. Nothing expands them, so those comparisons risk being silently
one-sided, exactly like the ESTO axis was before 2026-07-09. `leap_rollup_rules` needs no
target-side role — no sheet has LEAP as its target axis.

## Task 1 — trace the leap_to_ninth_comparison consumer first

Before changing anything, find where `use_case == "leap_to_ninth_comparison"` relationship
rows are consumed downstream (Stage 2/3, `apply_common_esto_structure.py`,
`build_dataset_tree_structure.py`, dashboards). Establish:
- how the NINTH-side value for a target `ninth_sector` label is looked up, and what happens
  today when that label has no NINTH data rows (confirm or refute the "silently one-sided"
  hypothesis with a concrete query on current outputs);
- whether NINTH source-side rollup labels (e.g. `09_08_coal_transformation_incl_own_use`)
  have data rows in the NINTH dataset or are value-less relationship artifacts.
Report findings before implementing.

## Task 2 — implement NINTH target-side expansion (mirror the ESTO one)

In `build_energy_balance_relationships.py`:
- Build a rolled-name → component-sectors lookup from `ninth_rollup_rules`
  (`rolled_9th_sector` → `input_9th_sector` values; respect `include`; support nesting the
  same way `_resolve_rolled_flow_components` does).
- Expand relationship rows with `target_system == "NINTH"` whose `target_flow` names a
  rolled NINTH sector, one row per component, provenance note
  `expanded_from_ninth_rollup: <rolled name>`, new relationship ids/keys. Handle
  fuel-specific rules (`input_9th_fuel` / `rolled_9th_fuel` non-blank) explicitly — if they
  are not needed for target expansion, skip them with a comment saying why.
- Add `qa_unknown_ninth_target_flows.csv`: NINTH targets matching no real NINTH sector and
  no rolled name. Real NINTH sectors must be collected from ALL sector columns of the
  `NINTH unique sectors and fuels` sheet (`sectors`, `sub1sectors` ... `sub4sectors`), not
  just the first. Expect some intentional placeholders (hydrogen family) to remain listed —
  they are pending future data, not errors; do not "fix" them in the workbook.
- Keep the source-side duplicate-up mechanisms and their `is_rollup_derived` exclusion
  untouched.

Verify with a Stage 1 run (`python codebase\run_mapping_pipeline.py --stages 1`, takes a few
minutes): expansion count printed, expanded rows present with provenance notes, unknown-NINTH
QA contains only expected placeholders, and previously-fake targets like
`09_01-09_02,09_x Power sector` are gone from relationship targets. Then decide (and state)
whether a Stage 2+ rerun is needed to validate downstream effects, and if so run it per
`docs/prompts/run_mapping_pipeline_future_prompt.md` conventions (long; poll patiently;
logs buffer — judge liveness by process CPU and output mtimes).

## Task 3 — document the rollup system in docs/

Write `docs/rollup_rules_system.md` explaining, for a maintainer who edits the workbook:
- the shared sheet schema and what each of the three sheets is for;
- the two consumption directions (target-side expand-down vs source-side duplicate-up),
  which sheets/axes each applies to, and WHY the directions differ (source systems have
  aggregate-level data; target axes need real data rows);
- how a merged common row gets its display name (esto_rollup_rules → common_esto_overrides
  → `build_preferred_flow_partition_labels`; exact flow-set match required);
- the `is_rollup_derived` / `esto_pair_is_subtotal` exclusions from merge-edge creation and
  the blob-merging failure mode they prevent;
- how to add a new "(including own use)"-style item end to end (rules row + pointing leaf
  mapping rows at the rolled name, flags FALSE/FALSE);
- the unknown-target QA files and how to read them (placeholders vs typos);
- known intentional placeholders (09.13 hydrogen family etc.).
Link it from the docs index / `mappings_system.md` if one exists. Keep it factual — verify
each claim against the code rather than restating this prompt.

## Constraints

- Report findings from Task 1 before writing Task 2 code.
- If Task 1 shows leap_combined_ninth is consumed in a way that makes expansion wrong or
  unnecessary, stop and say so instead of implementing anyway.
- No changes to the workbook, no changes to the source-side rollup mechanics.
