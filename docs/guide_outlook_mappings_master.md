# Editor's guide: `config/outlook_mappings_master.xlsx`

A practical guide for editing the master mapping workbook, with a deep-dive on rollups.
For the system architecture (pipeline stages, code entry points, output files) see
[mappings_system.md](mappings_system.md). This guide is about **what to put in the cells and
why**, and what goes wrong when the rules below are broken — every "common mistake" here is
one we actually made.

Ground rules:

- The workbook is the single source of truth for structure. **The pipeline never writes it**;
  only humans edit it. Rerun `codebase/run_mapping_pipeline.py` after any edit.
- Close Excel before running the pipeline if possible; at minimum, save. Automation reads the
  file on disk — unsaved buffers have burned us (a "fixed" sheet that was never saved).
- `config/E0E85740`-style files and `~$outlook_mappings_master.xlsx` are Excel lock artifacts;
  ignore them.

## 1. The sheets at a glance

| Sheet | Role |
|---|---|
| `leap_combined_esto` | LEAP (sector path, fuel) → ESTO (flow, product) mappings. The main mapping sheet. |
| `ninth_pairs_to_esto_pairs` | 9th-edition (sector, fuel) → ESTO (flow, product) mappings. |
| `leap_combined_ninth` | LEAP (sector path, fuel) → 9th (sector, fuel) mappings. |
| `leap_rollup_rules` | Rollups applied to **raw LEAP data** before conversion (build synthetic parent rows). |
| `esto_rollup_rules` | Definitions of **virtual ESTO flows** (e.g. "(including own use)" groups) that mapping sheets may target. |
| `ninth_rollup_rules` | Rollups applied to raw 9th data (analogue of `leap_rollup_rules`). |
| `rollup_label_overrides` | Override the auto-generated code/name/label of a rollup group. |
| `leap_display_names` | code → LEAP display name (consumed by `leap_initialisation` too; respect `USED_IN_LEAP_INITIALISATION`). |
| `ESTO unique flows and products`, `NINTH unique sectors and fuels` | Reference lists of *real* labels. Stage 1 uses the ESTO list to detect mapping targets that match no real flow (`qa_unknown_esto_target_flows.csv`). |
| `ninth fuel to esto product` | Fuel-level crosswalk. |
| `Guide` | In-workbook notes. Keep it short; this file is the maintained guide. |
| `Sheet1`, `exceptons`, `deleted rows - might regret` | Scratch/leftovers — not read by the pipeline. Don't add new data here. |

Validation/QA exceptions do **not** live in this workbook — they live in
`config/mapping_issue_exception_sets.xlsx` (see mappings_system.md §exception sets).

## 2. Mapping sheets: the basics

Each row of a mapping sheet says "this source pair's value belongs to this target pair".
Conversion is a join-and-sum: every source data row is matched against mapping rows, its value
is delivered along **every matching row**, then summed per target.

Consequences to keep in mind:

- **A source pair mapped to N targets delivers its value N times** (unless allocation shares
  say otherwise — see §4). One-to-many mappings are only safe when the pipeline knows how to
  split or when all N targets merge back into one common row.
- `*_is_subtotal` flags mark parent/subtotal pairs. Subtotal ESTO pairs are kept as standalone
  common rows and are *not* used to structurally merge other flows.
- Map at the **finest level both systems support**, and let parents be sums. Mapping a parent
  *and* its children to overlapping targets double counts (§5).

## 3. Rollups: the two kinds

The word "rollup" covers two different mechanisms. Confusing them causes most rollup bugs.

### 3a. Source rollups (`leap_rollup_rules`, `ninth_rollup_rules`)

Applied to **raw source data before conversion**. Each rule says: input (flow, product) rows
are summed into a synthetic rolled row named `rolled_*`. Use these when the source data is too
fine (or differently shaped) for the mapping you want, e.g. building a `Coal transformation`
parent row out of LEAP's leaf rows so a parent-level mapping row has something to match.

The synthetic rolled row **contains** its inputs' energy. If the inputs are *also* mapped
directly, that energy enters conversion twice. Rule: **a source pair should reach conversion
through exactly one path** — either raw or inside a rolled row, never both (the converter's
`allowed_rolled_pairs` guard limits rollups to mapped pairs, but it cannot catch a rolled row
and its inputs both being mapped to overlapping targets).

### 3b. ESTO target rollups (`esto_rollup_rules`)

These define **virtual ESTO flows** — labels that do not exist in the ESTO balance but that
mapping sheets may use as `esto_flow` targets. Each rule row is one component:

```
input_esto_flow            rolled_esto_flow
09.08.01 Coke ovens        09.08.01 Coke ovens (including own use)
10.01.05 Coke ovens        09.08.01 Coke ovens (including own use)
```

reads as: *the virtual flow "09.08.01 Coke ovens (including own use)" consists of the real
flows 09.08.01 and 10.01.05*.

What the pipeline does with a group now depends on whether the group is registered as a real
hierarchy node.

**Registered hierarchy rollups** have both `parent_flow_label` and `child_flow_labels`
populated. These are the normal path for virtual ESTO flows. A mapping row targeting the
rolled name stays as one full-value relationship row. Stage 3 also registers the rolled label
as a real node in the ESTO and Common ESTO flow trees, so parent/child validation can compare
the rolled parent against its declared children without pretending the source aggregate was
split.

**Fallback rollups** are rows that have a rolled ESTO flow but no hierarchy placement. These
can still use the older component expansion path: a mapping row targeting the rolled name is
expanded into one relationship per component, with `allocation_share = 1/N` so the source value
is split rather than multiplied (§4). This path is only a fallback for groups that cannot yet be
registered as tree nodes.

**Every group must list ALL of its real components.** The own-use groups once listed only the
`10.01.x` flow (the `09.x` input rows had been dropped in a sheet restructure): expansion then
sent LEAP values *only* to own-use, the merge never formed, no `(including own use)` row
appeared, and the main transformation flows silently vanished from `leap_vs_esto`. If a group
is meant to be "X plus its own use", it needs both the X row and the 10.01.x row.

Nested rollups are allowed (a component may itself be a rolled name; resolution recurses,
depth-capped), but keep nesting shallow — it makes double-count review hard.

### The columns

| Column | Meaning |
|---|---|
| `input_*` | One real component pair. Blank product = all products of that flow. |
| `rolled_*` | The virtual/rolled name. All rows sharing this name form one group. |
| `include` | `True` to enable the rule. |
| `Note` | Free text: say *why* the group exists. Future-you will need it. |
| `Subtotal` | Marker for mixed/subtotal groups (informational). |
| `parent_flow_label` / `child_flow_labels` | Declares the rolled flow's hierarchy position. When both are populated, the rolled label is registered as a real tree node and mapping rows targeting it are not expanded/split. |
| `rollup_context`, `rollup_group_id`, `rollup_reason`, `priority` | See mappings_system.md §rollup_context. Usually blank for simple groups. |

## 4. Fallback fan-out and allocation shares

Registered hierarchy rollups do **not** use fan-out. A mapping row targeting a registered rolled
label stays as one full-value row.

Fan-out only applies to fallback rollups that do not have `parent_flow_label` /
`child_flow_labels`. When one mapping row expands to N components, the converter would naively
deliver the full source value N times. Expanded rows therefore carry `allocation_share = 1/N`,
and the converters multiply by it. Because Stage 2 merges all N components into **one** common
row, the N shares sum back to exactly 1× at the destination.

This re-assembly is the load-bearing assumption:

> **A fallback expanded target is safe if and only if all of its components end up in the same
> common row, and nothing else maps into that row's components.**

If a component lands in a *different* common row than its siblings, its share of the source
value leaks into that row — no share arithmetic can fix delivery to the wrong row.

Implementation note: expanded rows keep `allocation_method = "direct"`. Stage 2 draws the
merge edges between a source row's targets **only when no split-allowing allocation method is
present** (`allocation_allows_split`) — changing the method to something "smarter" quietly
dismantles the merge itself.

## 5. Parent vs leaf targets: the double-counting trap

The hierarchy, using coal as the worked example (gas processing `09.06` is identical in shape):

```
ESTO:  09.08 Coal transformation          10.01 Own use & losses
       ├── 09.08.01 Coke ovens            ├── 10.01.05 Coke ovens (own use)
       └── 09.08.02 Blast furnaces        └── 10.01.07 Blast furnaces (own use)

LEAP:  Coal transformation  = Coke ovens + Blast furnaces   (no own-use split)
```

Correct setup:

- **Leaf mappings target leaf rolled groups**: LEAP `Coke ovens` →
  `09.08.01 Coke ovens (including own use)` (= 09.08.01 + 10.01.05). Both components live in
  the same merged common row → shares re-assemble → LEAP counted once, ESTO side includes own
  use. ✅
- **Parent mappings target the plain parent**: LEAP `Coal transformation` →
  `09.08 Coal transformation`. ✅

Wrong setup (what we had): LEAP `Coal transformation` →
`09.08 Coal transformation (including own use)` (= 09.08 + 10.01.05 + 10.01.07). Those three
components live in **three different** common rows — `09.08` in its own subtotal row,
`10.01.05` inside the coke-ovens leaf row, `10.01.07` inside the blast-furnaces leaf row. The
parent's value (which is just the sum of the leaves — not new energy) leaked into rows already
fed by the leaf mappings. Result: LEAP coke ovens appeared at **3×** in the comparison data.

The parent's own use is not lost by pointing it at the plain flow: it is fully counted inside
the leaf `(including own use)` rows, and summing those leaf rows reproduces
"09.08 including own use" exactly. The remaining asymmetry — the parent *row* compares
LEAP-parent vs plain-09.08 — is a known validator gap tracked in
`docs/prompts/explore_parent_level_own_use_comparison_rows.md`.

Contrast with groups that ARE safe at parent level: `16.01-16.02 Buildings`,
`09.01-09.02 Power sector`, `16.03-16.04 Agriculture and fishing`. Their components merge into
one dedicated common row and **no finer source mapping competes** for those flows. These are now
registered hierarchy rollups, so mapping rows targeting the rolled labels stay whole rather than
being fan-out split.

## 6. Checklist for adding or editing a rollup group

1. List **all** real components as `input_*` rows — for "(including own use)" groups that
   means the 09.x flow *and* its 10.01.x counterpart(s).
2. Check every component appears in `ESTO unique flows and products` (typo → the component is
   silently not real; unregistered rolled targets then show up in `qa_unknown_esto_target_flows.csv`).
3. Populate `parent_flow_label` and `child_flow_labels` whenever the rolled label has a real
   hierarchy position. This is the preferred path. It registers the rolled label as a tree node
   and prevents source values from being split across components.
4. Ask the overlap question: does any *other* mapping row (especially a parent- or child-level
   one) target any of these components or another group containing them? If yes, resolve the
   overlap first.
5. Point the mapping-sheet rows at the rolled name; leave parent-level mapping rows on plain
   parent flows.
6. Save the workbook (actually save — check the file mtime), rerun the pipeline, then verify:
   - `results/mapping_relationships/common_esto_overrides.csv` — the group has all components
     and the right `preferred_common_flow_label`;
   - `results/common_esto/common_esto_rows.csv` — one common row with the rolled label whose
     `component_esto_flow` values are exactly the components (no extras = no blob-merge);
   - `results/common_esto/common_esto_comparison_data.csv` — for one economy/year/product, the
     source-system value equals the raw source value **once** (not 2×/3×), and the ESTO value
     equals the sum of the components from the ESTO balance.
   - `results/tree_structure/esto_tree.csv` and `results/tree_structure/common_esto_tree.csv`
     include the rolled label when `parent_flow_label` / `child_flow_labels` are populated.

## 7. Known open edges (2026-07-09)

- **NINTH rolled source rows** (`09_08_coal_transformation_incl_own_use` etc.) can reproduce
  the parent-leak pattern on the NINTH side; NINTH-target expansion and rule unification are
  parked in `docs/prompts/unify_rollup_rules_prompt.md`. Until then, check the coke-ovens
  NINTH value (raw `09_08_01` + `10_01_05`, exactly 1×) after each rerun.
- **Registered parent/child rollup nodes** are now understood by Stage 3 validation, but the
  deeper own-use transformation chains still contain workbook-level overlap questions. Do not
  silently resolve conflicting child claims in code; fix the workbook hierarchy fields once the
  intended structure is reviewed.
- Validation exceptions for genuinely-unreconcilable families belong in
  `config/mapping_issue_exception_sets.xlsx`, not in this workbook.
