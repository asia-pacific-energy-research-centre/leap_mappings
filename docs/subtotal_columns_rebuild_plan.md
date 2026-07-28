# Subtotal columns rebuild plan

## Purpose

Re-derive every `leap_is_subtotal`, `ninth_pair_is_subtotal`, and
`esto_pair_is_subtotal` value in the three maintained mapping sheets from
auditable hierarchy evidence. Do not treat current mapping values or existing
exception rows as authority.

This is the detailed plan for MAPQ-030. It is a review plan only; no subtotal
cells have been changed.

## What the current investigation found

The current todo workbook contains conflicting subtotal values for identical
source pairs across mapping sheets:

| Source system | Identical pairs with conflicting flags |
| --- | ---: |
| LEAP | 210 |
| Ninth | 167 |
| ESTO / ESTO Extended | 151 |

The problem is therefore workbook-wide. It cannot be corrected safely by
copying one sheet over another or by accepting the most frequent value.

The current exception workbook contains three overlapping subtotal mechanisms:

| Sheet | Enabled rows | Current role |
| --- | ---: | --- |
| `subtotal_mismatch_allowed` | 434 | Allows reviewed source/target subtotal mismatches in QA |
| `subtotal_label_exceptions` | 118 | Stops the older inference tool proposing a different label |
| `subtotal_label_overrides` | 2,408 | Overrides Stage 0 computed flags for exact mapping rows |

Most entries have generic notes such as “retain current mapping subtotal
values” or “reviewed subtotal decision”. Those entries record prior workflow
state, but do not contain enough hierarchy evidence to prove the retained
classification is correct.

The existing tree and maintenance code also use different definitions:

- the ESTO tree uses code-prefix parent/child structure;
- the Ninth tree currently leaves 14 sector nodes with children marked
  `is_subtotal=False`, because its flagging logic depends on
  `subtotal_results` evidence rather than parenthood alone;
- the LEAP tree is built from the mapping workbook itself, so it is circular
  and can miss branches absent from the mappings;
- the LEAP fuel tree is flat and cannot identify aggregate fuel labels;
- Stage 0 uses non-zero source rows and raw subtotal flags, while
  `infer_subtotal_labels.py` uses the generated trees and rollup-sheet values;
- the inference tool keeps the first current value it encounters for a pair,
  so it does not expose every cross-sheet disagreement;
- Stage 0 currently writes only a preview. Its old automatic workbook-write
  path is intentionally unreachable because it previously overwrote reviewed
  values.

## Definition to use

A mapping-side pair is a subtotal when either axis of that exact source pair is
an additive parent in that source system:

```text
pair_is_subtotal = primary_axis_is_parent OR secondary_axis_is_parent
```

This definition is independent of mapping direction. The same LEAP pair must
have the same LEAP flag in both LEAP mapping sheets; the same Ninth pair must
have the same Ninth flag in both Ninth mapping sheets; and the same ESTO pair
must have the same ESTO flag in both ESTO mapping sheets.

The boolean mapping columns should contain only `True` or `False`.
`MIXED` is useful as a rollup-review diagnostic, but should not be written into
these pair-level boolean columns.

Synthetic rollups need a separate classification before their pair flag is
assigned:

- an additive rollup output is a subtotal;
- an exact alias or renamed leaf is not;
- a non-expanding or detached comparison-boundary row must be reviewed against
  its declared rollup mode rather than inferred from the number of inputs.

## Proposed work

### 1. Freeze the review inputs

- Use `config/outlook_mappings_master todo.xlsx` as the mapping base after the
  current new-row mapping pass is stable.
- Back it up and repeat the lossless workbook round-trip proof.
- Record exact hashes and source vintages for the ESTO balance, Ninth balance,
  full LEAP structure export, `data/temp/new leap rows.xlsx`, and the exception
  workbook.

### 2. Build authoritative axis tables

Create one evidence table per system and axis, with code, full hierarchy path,
parent, children, depth, structural-parent status, raw subtotal signals, and
source provenance.

- **ESTO:** derive flow and product parenthood from the complete code hierarchy,
  then reconcile it with the maintained ESTO subtotal mapping and raw
  `is_subtotal`. Do not restrict the hierarchy to non-zero observations.
- **Ninth:** derive sector parenthood directly from
  `sectors` through `sub4sectors`, and fuel parenthood from
  `fuels`/`subfuels`. Keep `subtotal_layout` and `subtotal_results` as evidence
  columns and investigate disagreements, but do not let a period-specific flag
  erase a structural parent.
- **LEAP:** derive branches from the full model structure plus the supplied new
  branch inventory, not from already mapped rows. Build the actual sector/fuel
  pair frontier and a reviewed fuel taxonomy for aggregate labels rather than
  assuming every LEAP fuel is a leaf.
- **Synthetic rows:** join all active rollup rules and the process-category
  registry, retaining rollup mode and contributor evidence.

### 3. Produce one canonical pair classification per system

For each unique LEAP, Ninth, and ESTO pair:

- calculate both axis classifications;
- calculate the pair boolean;
- record the rule and evidence that produced it;
- mark incomplete, contradictory, synthetic, or mixed-mode cases for review;
- never choose a value based on which mapping sheet was read first.

### 4. Audit the exception workbook against the new evidence

Treat the three subtotal-related exception sheets differently:

- `subtotal_label_overrides` is a temporary exact-cell override layer. Test
  every enabled row against the new canonical classification; remove entries
  that merely reproduce the correct computed value, and review every genuine
  disagreement.
- `subtotal_label_exceptions` belongs to the old inference proposal mechanism.
  Re-evaluate all 118 rows, especially because they all preserve LEAP `True`
  where the old tool proposed `False`.
- `subtotal_mismatch_allowed` does not define either side's subtotal truth. It
  only says that a correctly classified subtotal-to-leaf or leaf-to-subtotal
  relationship is acceptable. Rebuild this QA allowlist only after both sides'
  flags are correct.

Require specific structural or semantic reasons for retained exceptions.
Generic “retain current value” notes are not sufficient evidence.

### 5. Generate a cell-level review workbook

Create a narrow review workbook containing:

- a summary by system, mapping sheet, proposed change, and confidence;
- one row per unique pair with both axis evidence;
- one row per affected mapping cell with sheet, Excel row, current value,
  proposed value, and reason;
- coherent sibling-group views;
- synthetic/rollup cases;
- exception rows classified as confirmed, redundant, stale, or unresolved;
- all cross-sheet conflicts, which must resolve to one canonical pair value.

No mapping workbook writes occur at this stage.

### 6. Review by coherent hierarchy groups

Review parents with all immediate children together. Prioritize:

- total and combined demand sectors;
- aggregate fuels/products;
- Electricity, CHP, Heat, and their new detailed processes;
- imported electricity and other boundary categories;
- transport vehicle/drive rollups;
- ESTO Extended synthetic flows;
- non-expanding and detached rollups.

This prevents the partial-child problem where only some children of a mapped
parent are treated consistently.

### 7. Apply only approved changes

After review:

- write the approved canonical flag to every occurrence of the pair in every
  mapping sheet;
- update or remove the related exception rows in the same change;
- preserve workbook layout, formulas, validations, filters, and formatting;
- re-read every changed cell by exact mapping identity.

### 8. Validate the result

The acceptance checks are:

- zero cross-sheet flag conflicts for identical LEAP, Ninth, and ESTO pairs;
- no blank or non-boolean subtotal cells on complete active mapping rows;
- every `True` has hierarchy or approved synthetic-rollup evidence;
- every structural parent is classified consistently across its sibling group;
- the subtotal mismatch report contains only real, specifically justified
  cross-system differences;
- raw and rollup-aware cardinality are unchanged except where an approved
  subtotal correction intentionally changes graph treatment;
- additive frontiers contain no parent-plus-child double count;
- source totals and parent/child recursive checks pass before and after
  Stages 1–3;
- the workbook formatting-preservation proof still passes.

## Recommended implementation order

First correct and test the common classification engine and review output.
Then audit the exception workbook. Only after both are stable should the
approved flags be written into the mapping workbook. The current Stage 0
preview is useful evidence, but it should not become an automatic bulk writer
until these definitions and exception rules are reconciled.
