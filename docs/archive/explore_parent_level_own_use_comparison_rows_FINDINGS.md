# Findings: parent-level "(including own use)" comparison rows

Report-only investigation. No code or workbook changes were made.

## Verdict

Parent-level `(including own use)` labels were deliberate as comparison-boundary concepts, but the earlier pattern where LEAP parent mapping rows targeted those labels directly was an unsafe sheet-edit artifact, not a design to preserve.

The end state should be:

- leaf LEAP mappings target leaf `(including own use)` rows where LEAP does not split own-use/losses separately;
- LEAP parent mappings such as `Coal transformation` and `Gas processing plants` stay on the plain ESTO parent flows, e.g. `09.08 Coal transformation` and `09.06 Gas processing plants`;
- parent-level own-use rows, when needed, are derived subtotals/frontier rows from child rows, not independent raw-component partitions that reuse `10.01.x` components already claimed by leaf rows.

Recommended option from the prompt: **(a) parent rows as derived subtotals**.

Option (b), a separate parent-granularity comparison scope, is heavier and creates another parallel comparison structure. Option (c), dashboard-only aggregation, is acceptable as a temporary presentation workaround but leaves the mapping pipeline and hierarchy validator without a central source of truth.

## Evidence

`docs/guide_outlook_mappings_master.md` now states the rule most directly:

- leaf mappings target leaf rolled groups, e.g. `09.08.01 Coke ovens (including own use)`;
- parent mappings target the plain parent, e.g. `09.08 Coal transformation`;
- the wrong setup was LEAP `Coal transformation` targeting `09.08 Coal transformation (including own use)`, because that group's components live in different common rows and caused LEAP coke ovens to appear at 3x;
- the parent's own use is not lost, because summing the leaf `(including own use)` rows reproduces the parent-inclusive view.

`docs/archive/side_prompt_esto_rollup_expansion.md` only required leaf-level merged rows such as `09.08.01 Coke ovens (including own use)` and explicitly checked that the coke-ovens partition did not contain `09.08 Coal transformation` or `10.01.07 Blast furnaces`. That supports leaf-level own-use rows, not direct parent-level fan-out.

`docs/prompts/unify_rollup_rules_prompt.md` says NINTH target expansion still needs work because `leap_combined_ninth` contains rolled NINTH labels such as `09_08_coal_transformation_incl_own_use`. This is separate from LEAP parent rows targeting ESTO parent own-use labels directly.

The `esto_rollup_rules` sheet still contains parent-level rolled labels:

- `09.06 Gas processing plants (including own use)`
- `09.08 Coal transformation (including own use)`
- `09.07 Oil refineries (including own use)`
- `09.12 Non-specified transformation (including own use)`

Their `Note` values describe them as explicit comparison-boundary adjustments because LEAP may not report own-use/loss components separately. That means the parent-level concepts are intentional, but it does not imply the source parent row should be split or copied into children. Current code also treats registered rollup labels specially: registered rollup flows are not expanded by `expand_esto_rollup_targets`; they are loaded as synthetic tree nodes by `_load_rollup_hierarchy()`.

The dashboard does not appear to require hard-coded `09.08 ... (including own use)` rows. `leap_dashboard` routes transformation pages by flow prefixes and keywords, and its bespoke transformation-total chart selects by `source_aggregate_labels`, `is_exact_row`, and `requires_rollup`, explicitly avoiding display-label inference. It has a generic `frontier_flow_labels()` helper for non-double-counting frontiers, which aligns better with derived parent subtotals than direct parent target rows.

## Recommended Design

Use parent-level own-use labels as **derived tree/frontier nodes**:

1. Keep leaf own-use rollups as real comparison rows:
   - `09.06.01 Gas works plants (including own use)`
   - `09.06.02 Liquefaction/regasification plants (including own use)`
   - `09.08.01 Coke ovens (including own use)`
   - `09.08.02 Blast furnaces (including own use)`
   - `09.07 Oil refineries (including own use)`
   - `09.12 Non-specified transformation (including own use)`

2. Keep LEAP parent mapping rows on plain parents:
   - `Gas processing plants` -> `09.06 Gas processing plants`
   - `Coal transformation` -> `09.08 Coal transformation`
   - equivalent parent rows for refining and non-specified transformation should be reviewed the same way.

3. Define parent own-use rows as subtotals over a non-overlapping child frontier. For coal, the conceptual row should be derived from the selected children, not from raw components that also feed leaf rows. In practice this means the parent-inclusive row should sum child rows like `09.08.01 Coke ovens (including own use)` and `09.08.02 Blast furnaces (including own use)`, plus any other in-scope `09.08.*` children that belong in the parent frontier.

4. Publish that selection as central frontier/hierarchy metadata, not dashboard-specific string logic. This is consistent with `CROSS-002` in `docs/special_rules_and_design_decisions.md`, which says the canonical output can contain parents, descendants, and generated rollups, but consumers need declared non-overlapping frontiers before summing.

## Concrete Touch Points If Implemented

- `config/outlook_mappings_master.xlsx`, `esto_rollup_rules`: keep parent rollup rows, but review the `parent_flow_label` / `child_flow_labels` fields so they describe the intended derived hierarchy. Do not point LEAP parent mapping rows at parent `(including own use)` labels.
- `codebase/mapping_tools/build_dataset_tree_structure.py`: `_load_rollup_hierarchy()` already loads registered rollup nodes. The next step is making the declared hierarchy/frontier explicit enough that validation uses derived child frontiers rather than raw overlapping components.
- `codebase/mapping_tools/build_common_esto_structure.py` and structural artifacts: preserve row metadata that lets consumers distinguish exact rows from rollup-derived rows and avoid selecting overlapping parent/child rows together.
- `leap_dashboard`: continue selecting aggregate charts from declared metadata/frontiers. Do not add special handling that infers own-use parent totals from display-label suffixes.

Estimated blast radius: moderate. The rule is conceptually narrow, but it touches the shared tree/frontier contract that dashboard rendering and recursive validation rely on.

## Workbook References To Review

Do not delete parent-level `(including own use)` groups just because LEAP parent mappings should not target them. They may still be needed as NINTH comparison labels and as derived parent subtotals.

Rows to review after the design is accepted:

- `09.06 Gas processing plants (including own use)`
- `09.08 Coal transformation (including own use)`
- `09.07 Oil refineries (including own use)`
- `09.12 Non-specified transformation (including own use)`

The review question is not "should these labels exist?" It is "what exact non-overlapping child frontier defines each label?" The current `child_flow_labels` cells emphasize the `10.01.x` own-use components; the intended derived parent frontier should be written in terms of rows that can be summed once without reusing a component already present in a leaf row.

## Impact On Hierarchy Validation

The current validator can load registered rollup hierarchy nodes and then validates parent = sum(children) over comparison rows. That is the right direction, but direct parent own-use targets are inconsistent with this model because a raw component such as `10.01.05 Coke ovens` cannot belong to both the leaf coke-ovens row and a parent `09.08` row as an additive component.

With option (a), validation should compare:

- parent inclusive row = sum of selected child frontier rows;
- each child row appears in one selected frontier only;
- LEAP parent rows remain separate plain-parent comparisons unless explicitly selected as a parent/reference row for a named frontier.

This preserves the three consistency requirements:

- LEAP counted once per common row: parent LEAP values are not fanned out into leaf rows.
- ESTO components counted once: each `10.01.x` own-use component appears in the leaf-inclusive row, not again in a parent raw-component row.
- parent = sum(children): the validator can check the derived parent against the declared child frontier instead of trying to reconcile overlapping raw components.

## Recommendation For Next Prompt

Proceed to `unify_rollup_rules_prompt.md` only after accepting this rule: NINTH target expansion may create or expose parent-level own-use labels, but implementation should preserve the same non-overlap principle and should not reintroduce direct parent-row fan-out.
