# Mappings System

This document explains how the APERC Outlook mappings system works, why it is structured the way it is, and what each part does. It is intended for people who need to maintain, extend, or reason about comparison outputs across energy-balance datasets.

## Contents

### Overview

- [What the mappings system is for](#what-the-mappings-system-is-for)
- [The core mapping workbooks](#the-core-mapping-workbooks)

### Core concepts

- [Key design principle: do not split source aggregates](#key-design-principle-do-not-split-source-aggregates)
- [Keep base mappings simple](#keep-base-mappings-simple)
- [Cardinality](#cardinality)
- [Rollups](#rollups)
- [Naming conventions for generated aggregate categories](#naming-conventions-for-generated-aggregate-categories)
- [Explicit rollups and graph partitioning](#explicit-rollups-and-graph-partitioning)

### The workbook

- [The mapping sheets in detail](#the-mapping-sheets-in-detail)
- [Subtotal handling](#subtotal-handling)
- [Column-level quick reference](#column-level-quick-reference)

### The pipeline

- [Mapping maintenance workflow](#mapping-maintenance-workflow)
- [From mapping rows to comparison outputs](#from-mapping-rows-to-comparison-outputs)

### Operations and reference

- [LEAP structure export and mapping maintenance](#leap-structure-export-and-mapping-maintenance)
- [Hierarchical tree validation](#hierarchical-tree-validation)
- [Adding new scenarios](#adding-new-scenarios)
- [Special-case examples](#special-case-examples)
- [QA outputs and what to look for](#qa-outputs-and-what-to-look-for)
- [Common mistakes to avoid](#common-mistakes-to-avoid)

---

## What the mappings system is for

The mapping system is used to maintain, check, and compile mappings between APERC Outlook datasets, including LEAP, ESTO, and 9th Outlook.

The main source systems use different structures:

- **LEAP** - the energy model, which uses a branch tree with sector paths and fuel names.
- **ESTO** - the historical energy balance, structured as flow/product pairs, such as `09.07 Oil refineries` / `06.04 Additives and oxygenates`.
- **9th Outlook** - the projection dataset, structured as sector/fuel hierarchy pairs, such as `09_07_oil_refineries` / `06_x_other_hydrocarbons`.

None of these datasets uses exactly the same categories at the same level of detail. The mapping system creates a controlled bridge between them so comparison values - balance totals, transformation outputs, trade flows, final consumption, and diagnostics - can be compared fairly without misattributing values across different boundary definitions.

The system supports mappings and comparisons such as:

- `LEAP -> ESTO`
- `9th -> ESTO`
- `LEAP -> 9th`
- `9th -> LEAP`

The output of the mapping system feeds:

- Balance reconciliation diagnostics used during LEAP initialisation.
- The dashboard comparison tools in `leap_dashboard`.
- Mapping QA outputs used when reviewing coverage gaps, subtotal issues, rollups, and cardinality problems.

This document is the canonical mapping reference for the APERC project. `leap_initialisation` uses these mappings when reconciling LEAP outputs against supply baselines; `leap_dashboard` uses the downstream common ESTO comparison data to generate its charts. Other repos should reference this document rather than reproducing mapping logic internally.

### Mental model

Base mappings say what rows correspond.

Rollup rules provide extra aggregated categories that known categories that have differnet levels of detail can be compared at.

Graph partitioning finds the smallest safe common comparison rows when source aggregates overlap across datasets.

The maintenance workflow checks the workbook.

The compilation pipeline produces the final comparison-ready dataset.

---

## The core mapping workbooks

### `config/outlook_mappings_master.xlsx`

This is the central workbook for the newer mapping system. Researchers should treat it as the main human-maintained workbook for APERC Outlook mapping maintenance.

It contains:

| Sheet | Purpose |
| --- | --- |
| `Guide` | Human guide and workbook notes |
| `leap_combined_esto` | LEAP branch+fuel -> ESTO flow+product pair |
| `ninth_pairs_to_esto_pairs` | 9th Outlook sector+fuel -> ESTO flow+product pair |
| `leap_combined_ninth` | LEAP branch+fuel -> 9th Outlook sector+fuel pair |
| `leap_rollup_rules` | LEAP rows rolled to known comparison categories |
| `esto_rollup_rules` | ESTO rows rolled to known comparison categories |
| `ninth_rollup_rules` | 9th Outlook rows rolled to known comparison categories |
| `rollup_label_overrides` | Reserved for display-name overrides for generated or rolled categories |

### `config/mapping_issue_exception_sets.xlsx`

This workbook is the manual source of truth for reviewed QA exceptions. Workflows read it, but they must not update it automatically.

| Sheet | Purpose |
| --- | --- |
| `many_to_many_allowed` | Reviewed many-to-many mapping diagnostics that are acceptable |
| `crosswalk_allowed` | Reviewed crosswalk target conflicts that are acceptable |
| `subtotal_mismatch_allowed` | Reviewed subtotal mismatch diagnostics that are acceptable |
| `missing_common_map_ignored` | ESTO flows intentionally excluded from missing common-map diagnostics |

Each sheet uses only:

- `enabled`
- the relevant QA output match columns
- `notes`

Rows with `enabled` set to true are used for matching. Blank match cells are ignored, so a row can match narrowly or broadly. In `missing_common_map_ignored`, match values ending in `*` are treated as prefixes, for example `18.*`.

Each base mapping sheet records source-to-target relationships. The aim is for each row to stay simple: one source row maps to one target row where this is possible. Extra comparison logic belongs in rollup or adjustment sheets.

The direction of the mapping is important. For example LEAP>ESTO mappings mean that LEAP categories cant be mapped to multiple ESTO categories, otherwise an allocation rule would be required. However mapping multiple leap categories to only one ESTO category leaves just a simple sum to be done. This is a key design principle of the system: do not split source aggregates unless there is an explicit allocation method (which for now seems unlikely to be developed). If a single LEAP branch corresponds to multiple ESTO rows, the system should use the roll up funcitonality to aggregtes the esto categories to a common comparison category rather than pretending to know how to split the LEAP branch across the ESTO rows. 

### Source data files

Three source data files feed the mapping and comparison pipeline:

- **`data/00APEC_2025_low_with_subtotals.csv`** — ESTO historical energy balance for all 21 APEC member economies. Covers 1990 to the latest available year, which is always two years behind the release year. Rows are structured as flow/product pairs. Subtotals are flagged with a single `is_subtotal` boolean column. This is the canonical ESTO reference for balance comparisons.

- **`data/merged_file_energy_ALL_20251106.csv`** — 9th Outlook projection data for all 21 APEC member economies and both scenarios (reference and target). Covers 1980–2070. Sector and fuel codes use underscores (e.g. `09_06_gas_processing_plants`). Subtotals are tracked with two columns: `subtotal_layout` marks aggregate rows in historical years (pre-2022), and `subtotal_results` marks aggregate rows generated by the 9th Outlook model in projection years. This is the primary source for mapping workflows, balance comparisons, and dashboard generation.

- **`data/merged_file_energy_00_APEC_20251106.csv`** — A subset of the above containing only the APEC aggregate economy (`00_APEC`) in the reference scenario. Useful for aggregate-level checks without the full dataset volume.

The date suffix in the 9th Outlook filenames (e.g. `20251106`) records when the file was produced. When a new 9th Outlook vintage is released both files should be updated together and the suffix updated to match.

## LEAP structure export and mapping maintenance

The mapping system identifies LEAP categories by normalized branch/category and
fuel labels, not by LEAP's numeric import IDs. It nevertheless depends on a
current full-model Analysis export to determine the real LEAP hierarchy,
parent/child status, branch existence, and available transformation and
Resources leaves.

The maintenance workflow checks, in order:

1. `leap_mappings/data/full model export.xlsx`, when present; then
2. `leap_initialisation/data/full model export.xlsx` as the shared canonical
   fallback.

Operational ownership of the canonical export and its ID rules belongs to
`leap_initialisation`. See `CROSS-001` in
[`leap_initialisation/docs/special_rules_and_design_decisions.md`](../../leap_initialisation/docs/special_rules_and_design_decisions.md#cross-001-full-model-export-and-leap-import-id-integrity)
and the detailed lifecycle in
[`leap_initialisation/data/README.md`](../../leap_initialisation/data/README.md#maintaining-full-model-exportxlsx).

Refresh the export after a LEAP structural change, including adding, deleting,
renaming, moving, or recreating a branch; changing a process or transformation
fuel leaf; moving a Resources fuel between `Primary` and `Secondary`; or
changing variables or scenarios. Numerical result changes alone do not require
a hierarchy refresh.

After a refresh, mapping maintenance must review:

- mapped LEAP paths no longer present in the export;
- new LEAP leaves with no active mapping;
- paths whose parent/leaf (`leap_is_subtotal`) status changed;
- rollups and cardinality affected by a changed hierarchy boundary; and
- old mapping rows retained only as deliberate removed-row guardrails.

LEAP import-workbook duplicates and `-1` IDs are not mapping relationships and
must not be added to `outlook_mappings_master.xlsx` as fixes. A mapping row
answers which semantic categories correspond; ID enrichment and duplicate
logical-key resolution belong to `leap_initialisation`. Conversely, a branch
that is genuinely new in LEAP may require both a refreshed structure export
and a new or revised mapping row.

---

## Key design principle: do not split source aggregates

The central rule in this system is:

> **Do not split a source aggregate unless there is an explicit allocation method.**

This exists because all three datasets use different levels of detail. A single LEAP branch can correspond to multiple ESTO rows. A single 9th Outlook sector can correspond to multiple ESTO flows. If the system splits the coarser aggregate across the finer categories without a justified allocation rule, it introduces false precision and distorts comparison totals.

The system resolves this in two ways:

- Explicit rollup rules handle known comparison boundaries.
- Graph partitioning generates the most detailed safe common comparison categories where source aggregates overlap across LEAP, ESTO, and 9th Outlook.

In both cases, the finer data are rolled up to a comparison level that the coarser source can support. The system should not pretend to know a split that the source data do not provide.

---

## Keep base mappings simple

Base mapping sheets answer:

> **What row maps to what row?**

Rollup and adjustment sheets answer:

> **At what level should these rows be compared?**

Do not put subtotal logic, own-use/loss boundary adjustments, many-to-many fixes, interim placeholder handling, or special comparison logic directly into the base mapping rows unless there is no better option. Those rules are easier to audit and reuse when they live in the rollup rule sheets with an explicit context and note.

---

## Cardinality

Cardinality describes the relationship type between source and target rows.

| Cardinality | Meaning |
| --- | --- |
| `one_to_one` | One source row maps to exactly one target row |
| `many_to_one` | Multiple source rows map to the same target |
| `one_to_many` | One source row maps to multiple targets |
| `many_to_many` | Multiple sources map to multiple targets in a way that needs review |

The processing order matters:

1. Read the base mapping rows.
2. Apply the relevant LEAP, ESTO, and/or 9th rollup rules.
3. Create effective rolled source and target pairs.
4. Calculate cardinality on those effective pairs.
5. Flag any many-to-many relationships that remain after rollup.

The current maintenance workflow writes cardinality to QA CSVs in `results/maintenance/`; it does not write cardinality columns back into the workbook. Conceptually, `pair_mapping_cardinality_raw` means cardinality before rollup and `pair_mapping_cardinality_after_rollup` means cardinality after applying relevant rollup rules. If a future workflow writes a single visible `pair_mapping_cardinality` column, it should represent the effective after-rollup cardinality.

**Many-to-many before rollup is a signal. Many-to-many after rollup usually needs review.** A raw many-to-many relationship often means the base mapping has crossed a comparison boundary and needs a known rollup or graph-generated common category. Some many-to-many rows are deliberate placeholder overlaps, such as completed LEAP power branches coexisting with interim fallback branches while the 9th Outlook has unallocated fuel categories. Reviewed exceptions are maintained in `config/mapping_issue_exception_sets.xlsx`, written to `results/maintenance/many_to_many_allowed_matched.csv` when matched, and removed from `results/maintenance/many_to_many_conflicts.csv` so the conflict file stays actionable.

Subtotal columns are updated by the mapping maintenance workflow, not maintained manually. Cardinality is currently reviewed through generated QA outputs.

---

## Rollups

Rollups are used when detailed categories in one dataset cannot be matched one-to-one with detailed categories in another. Instead of forcing an exact match, a rollup creates an effective comparison view that both sides can reliably support.

**A rollup does not delete the original row.** The original detailed rows are preserved for traceability, QA, and detailed diagnostic outputs. When result data are rolled up, all rows assigned to the same rolled category are summed.

Detailed outputs and rolled comparison outputs are separate views. Do not show both original detailed rows and the rolled row in the same additive total unless that is explicitly intended.

### Rollup rule sheets

The rollup rules live in `config/outlook_mappings_master.xlsx`:

| Sheet | What it rolls |
| --- | --- |
| `leap_rollup_rules` | LEAP sector+fuel to a rolled LEAP sector+fuel |
| `esto_rollup_rules` | ESTO flow+product to a rolled ESTO flow+product |
| `ninth_rollup_rules` | 9th Outlook sector+fuel to a rolled 9th sector+fuel |
| `rollup_label_overrides` | Reserved for human-readable label overrides for rolled or generated categories |

Each rule should be explainable from its columns:

| Column | Meaning |
| --- | --- |
| `rollup_context` | When the rule applies |
| `input_*` | Source row matched by the rule |
| `rolled_*` | Effective comparison label after rollup |
| `include` | Whether the rule is active |
| `Note` | Human explanation of why this rollup exists |

**Blank cells in rollup rules:**

- A blank input fuel/product means the rule applies to all fuels or products for that input sector or flow.
- A blank rolled fuel/product means keep the original fuel or product label.

Current implementation note: Stage 2 reads common-row label overrides from
`results/mapping_relationships/common_esto_label_overrides.csv` if that file
exists. The workbook `rollup_label_overrides` sheet is reserved but is not
currently wired into Stage 2.

### Rollup reason/type

The current workbook records the reason/type in `Note`. If a future schema adds a dedicated
`rollup_type`, it should distinguish ordinary category aggregation from other comparison logic.
Recommended values are:

| Value | Meaning |
| --- | --- |
| `category_rollup` | Ordinary category aggregation, such as several LEAP gas-processing branches rolling to Gas processing plants |
| `subtotal_rollup` | Final consumption or transport subtotal-style comparison views |
| `comparison_boundary_adjustment` | Cases where ESTO own-use/loss rows are included in transformation comparison boundaries because LEAP or another source does not report them separately |
| `interim_placeholder_handling` | Interim branches that should not double count with completed detailed branches |
| `label_override` | Display-name improvement only, not membership change |

### `rollup_context`

Each rule has a `rollup_context` column that controls when it applies. Use `all` only if the rollup is genuinely safe in every comparison view. Use a specific context where the same source row might roll differently depending on the comparison.

Recommended context names include:

- `all`
- `leap_to_esto`
- `ninth_to_esto`
- `leap_to_ninth`
- `ninth_to_leap`
- `road_comparison`
- `other_sector_comparison`
- `transport_comparison`
- `tfc_comparison`
- `tfec_comparison`
- `power_comparison`
- `transformation_comparison`
- `leap_vs_esto_comparison_boundary`
- `ninth_vs_esto_comparison_boundary`

Uncontrolled context names make rules hard to apply reliably. Context is what prevents a row such as `Freight road` from being rolled to Road, Transport, Total final consumption, and Total final energy consumption in the same output.

### Avoiding double counting

Detailed and rolled outputs are separate views. If a detailed row has been included in a rolled category, do not also add it separately in the same additive total unless that is explicitly intended.

Interim branches are especially risky. They should be handled as placeholders or fallback rows, not additive detail alongside completed detailed branches.


## Rollup naming conventions

Source-side rollups and cross-dataset common comparison categories have different naming rules.

**Source-side rollups** (in `leap_rollup_rules`, `esto_rollup_rules`, `ninth_rollup_rules`) are explicit human-defined rules for known categories. Naming depends on the source system:

- **ESTO rollups**: follow ESTO code format. Use the compressed code-range convention (e.g. `16.01-16.02 Buildings`) and prefer a real parent category code where one exists.
- **9th Outlook rollups**: follow the 9th code format (e.g. `09_06_gas_processing_plants`).
- **LEAP rollups**: LEAP branches have no numeric codes. Use standard ESTO energy balance terminology where possible — for example `Gas processing plants` rather than an invented label — so that LEAP rollup names stay consistent with their ESTO counterparts.

Human-readable names are acceptable for source-side rollups because these are known categories with stable meanings. Use `rollup_label_overrides` to set a preferred display name without changing the underlying group membership.

**Cross-dataset common comparison categories** generated by graph partitioning are always ESTO-shaped and named mechanically using compressed ESTO component codes. These are covered in [Naming conventions for generated aggregate categories](#naming-conventions-for-generated-aggregate-categories). The `rollup_` vs `common_` ID prefix is what distinguishes source-side rollups from graph-generated common categories in the pipeline, but are not what the human sees when operating this system.

---

## Naming conventions for generated aggregate categories

Generated aggregate categories should be transparent, stable, and mechanically traceable. A user should be able to look at a generated category name and understand which original categories were combined.

Generated category names should describe their component codes first, and their common meaning second.

For example:

```text
07.12-07.17,07.99 Petroleum products
```

means:

```text
This category contains ESTO product codes 07.12 through 07.17, plus 07.99.
```

Do not create vague labels such as `Other petroleum products` unless there is a label override. The mechanical code-based label should remain available for traceability.

### Generated code

When several categories are joined, the generated code should be created from the component codes.

Rules:

1. Sort component codes in their natural code order.
2. Compress consecutive ranges with a hyphen.
3. Separate non-consecutive components with commas.
4. Preserve the relevant code prefix where possible.
5. If the group exactly matches a real parent category, use the real parent category instead of a generated code.

Examples:

```text
07.12 + 07.13 + 07.14 + 07.15 + 07.16 + 07.17
-> 07.12-07.17
```

```text
07.12 + 07.13 + 07.14 + 07.15 + 07.16 + 07.17 + 07.99
-> 07.12-07.17,07.99
```

```text
09.01.01 Electricity plants + 09.02.01 Electricity plants
-> 09.01.01,09.02.01
```

If a broader real parent category exists and is the intended comparison row, prefer the parent:

```text
08.01 Recycled products + 08.02 Interproduct transfers + 08.03 Products transferred + 08.04 Gas separation + 08.99 Transfers nonspecified
-> 08 Transfers
```

rather than:

```text
-> 08.01-08.04,08.99 Transfers
```

because `08 Transfers` is a real ESTO parent row.

### Generated name

The generated name should use the nearest useful common parent or shared description.

Examples:

```text
07.12-07.17,07.99 Petroleum products
09.01.01,09.02.01 Electricity plants
09.01.02,09.02.02 CHP plants
09.01.03,09.02.03 Heat plants
```

If the code cannot confidently infer a common name, it should still generate a stable code-based label and flag the name for review.

### Generated label

The display label should combine the generated code and generated name:

```text
generated_label = generated_code + " " + generated_name
```

Examples:

```text
07.12-07.17,07.99 Petroleum products
09.01.01,09.02.01 Electricity plants
09.01.02,09.02.02 CHP plants
```

### Generated ID

Each generated category also gets a machine-safe identifier (`common_row_id`). This is the stable key that ties the pipeline together across stages.

The display label (`common_flow_label`, `common_product_label`) can be overridden for readability, reformatted, or adjusted without breaking anything — but only if the ID stays the same. Stage 3 joins source data rows to their common category using the ID, not the label. The component membership table is also keyed on the ID. This means label overrides are safe to apply at any point without needing to re-run upstream stages.

The ID is deterministic and derived from the generated label, so it can be reconstructed from the label alone and does not need a separate lookup table to be meaningful.

The ID is carried through to the final comparison output as an internal column alongside the human-readable label columns. It is not the primary display field, but it stays available for traceability and joining.

Rules:

1. Lowercase the label.
2. Replace spaces, punctuation, slashes, commas, and hyphens with underscores.
3. Collapse repeated underscores.
4. Remove leading or trailing underscores.
5. Prefix with `rollup_` or `common_` depending on the output type.

Examples:

```text
07.12-07.17,07.99 Petroleum products
-> common_07_12_07_17_07_99_petroleum_products
```

```text
09.01.01,09.02.01 Electricity plants
-> common_09_01_01_09_02_01_electricity_plants
```

```text
08 Transfers
-> rollup_08_transfers
```

### Component membership remains the source of truth

The generated label is only a label. The actual category definition is the list of component rows.

For each generated category, the system should preserve a component table such as:

```text
generated_category_id
component_flow_or_sector
component_product_or_fuel
component_name
source_system
comparison_scope
```

This makes the generated category auditable.

### Label overrides

Human-readable label overrides are allowed, but they should not change membership.

For example, a generated label might be:

```text
16.01 Commercial and public services + 16.02 Residential 
-> 16.01-16.02 Others
```

A label override could display this as:

```text
16.01-16.02 Buildings
```

but the original generated label and component list should still be preserved.

Label overrides should affect display only:

```text
preferred_rollup_label
```

They should not alter:

```text
rollup_group_id
generated_category_id
component membership
```

### Why this naming convention matters

This naming system is used so generated comparison categories are:

- stable across runs;
- easy to audit;
- mechanically traceable back to original ESTO or source-system categories;
- close to the original energy-balance style;
- clear enough for dashboard users and mapping maintainers.

The aim is to avoid hidden manual categories. If the system creates a new aggregate category, the category name should show what was combined.

---

## Explicit rollups and graph partitioning

Rollups and graph partitioning solve related but different problems.

**Rollups = explicit known rules.** Explicit rollup rules define known comparison boundaries. These are used where the correct comparison level is already known, such as transfers, gas processing, coal transformation, power-sector categories, final consumption totals, and own-use/loss boundary adjustments. They are aggregates, so that categories on a more detailed level can be aggregated and compared to another dataset, when that aggregation doesnt exist in the source data.

**Graph partitioning = automatic common-category generation from source aggregate constraints.** Graph partitioning derives common categories from the mapping relationships themselves. It is used when source aggregates overlap across mapped datasets and the system needs to find the most detailed safe comparison structure automatically.

Do not assume every category mismatch needs a hand-written rollup. Use explicit rollups for known comparison boundaries. Let graph partitioning generate common categories where overlapping source aggregates define the necessary comparison structure.

Graph partitioning is only applied in the `leap_vs_esto_vs_ninth` comparison scope. The `leap_vs_esto` scope uses only explicit rollup rules, since there is no third dataset whose aggregate constraints require automatic common-category generation.

### What graph partitioning means here

A graph is a network of nodes and edges. In this system, each exact ESTO flow/product pair is a node. If one source aggregate maps to several ESTO pairs, those pairs are connected by edges. Connected groups of nodes become common comparison rows.

Example:

```text
A = 07.12 White spirit SBP
B = 07.13 Lubricants
C = 07.14 Bitumen
D = 07.15 Paraffin waxes
```

If LEAP has one aggregate row that maps to `A + B`, add edge `A--B`.

If 9th Outlook has one aggregate row that maps to `B + C`, add edge `B--C`.

The connected component is `A--B--C`, so the safe common comparison row is `A + B + C`. `D` remains separate.

Graph partitioning finds the most detailed set of common comparison rows that does not split any source aggregate. This allows LEAP vs ESTO to remain more detailed where possible, while LEAP vs ESTO vs 9th may roll up more categories only where the third dataset requires it.

The final common comparison dataset should remain close to ESTO style, with mechanically transparent generated categories where needed.

---

## The mapping sheets in detail

The three base mapping sheets (`leap_combined_esto`, `ninth_pairs_to_esto_pairs`, and `leap_combined_ninth`) are the core human-maintained input. They should be kept as simple as possible, with one source row mapping to one target row where possible.
They are directional, as in leap_combined_esto means "LEAP combined to ESTO". This means that the LEAP side of the mapping should not be more detailed than the ESTO side, otherwise an allocation rule (which for now we assume is not possible) or a rollup would be required. If, like for the buildings sector or the split of autoproducers/main-activity producers in ESTO, a single LEAP branch corresponds to multiple ESTO rows and a mapping cannot be made to the parent of those ESTO rows, the system should use the roll up functionality to aggregate the ESTO categories to a common comparison category rather than pretending to know how to split the LEAP branch across the ESTO rows.
These sheets are also not totally inclusive. For example, `ninth_pairs_to_esto_pairs` can have known gaps where 9th Outlook sectors have no ESTO counterpart. However it is expected that since all datasets were designed to add up to the same totals, the upper most level of every ESTO flow/product pair should have at least one mapping to a source system row, even if that mapping is to a subtotal or aggregate row rather than a detailed row.

## Subtotal handling

Subtotals are aggregate rows where the value is the sum of child rows rather than an independent measured value. Any row that is not at the leaf end of a branch hierarchy is treated as a subtotal. The system assumes consistent aggregation — child rows should sum to their parent subtotal.

Each source dataset flags subtotals differently:

- **ESTO** (`data/00APEC_2025_low_with_subtotals.csv`): a single `is_subtotal` column.
- **9th Outlook** (`data/merged_file_energy_ALL_20251106.csv`): two columns — `subtotal_layout` for historical years (pre-2022) and `subtotal_results` for projection years. The maintenance workflow takes the logical OR of both to determine whether a 9th row is a subtotal.
- **LEAP**: subtotal status is derived from the branch structure — any branch that has children is a subtotal. The maintenance workflow reads `full model export.xlsx` first, normalizes LEAP `Branch Path` values to the mapping-sheet path style, and uses that hierarchy where the mapped path exists in the export. If the export does not contain a mapped path, the workflow falls back to the mapping-sheet path hierarchy for that path so incomplete exports do not erase known demand-side parent/child relationships.

The mapping sheets (`leap_combined_esto`, `leap_combined_ninth`, `ninth_pairs_to_esto_pairs`) each include computed columns recording subtotal status:

- `leap_is_subtotal`
- `esto_pair_is_subtotal`
- `ninth_pair_is_subtotal`

These are computed by the mapping maintenance workflow and should not be edited manually. They are recorded for auditing and QA purposes.

Because all three datasets operate at different levels of detail, subtotal↔non-subtotal mappings will naturally occur throughout the sheets. In most cases these are fine — the mapped branch in the coarser dataset effectively represents the same scope as the non-subtotal rows in the finer dataset.

- **Subtotal↔subtotal**: generally fine — both sides represent the same level of aggregation.
- **Non-subtotal↔non-subtotal**: fine — direct row-level comparison.
- **Subtotal↔non-subtotal**: will occur frequently and is generally acceptable given the different levels of detail across datasets.

A mismatch is detected when a leaf-level source (not a subtotal) maps to an aggregate target (is_subtotal = True) **and** a more specific (non-subtotal) target also exists at the same flow. Reviewed acceptable cases live in `config/mapping_issue_exception_sets.xlsx` on the `subtotal_mismatch_allowed` sheet. The maintenance workflow reads that sheet but does not update it automatically. Current mismatches that are not present in the manual allowlist are written to `results/maintenance/subtotal_mismatches.csv` for review.

---

## Mapping maintenance workflow

`codebase/outlook_mapping_maintenance_workflow.py` reads `config/outlook_mappings_master.xlsx` and maintains or checks workbook fields without creating the final dashboard dataset.

Run this after editing mapping rows or rollup rules.

Each run first writes a timestamped workbook copy to `config/archive/`, using filenames like `outlook_mappings_master.maintenance_run_YYYYMMDD_HHMMSS.xlsx`.

What it does:

- Loads ESTO and 9th source tables and resolves code/name lookups.
- Recalculates subtotal flags in the workbook from the current mapping rows.
- Writes cardinality QA CSVs from the active mapping rows.
- Checks subtotal flags.
- Builds tree-structure CSVs and validates ESTO recursive sums.
- Finds duplicate and conflicting mappings.
- Checks active row presence across the three base mapping sheets.
- Detects crosswalk target conflicts, such as the same source implying inconsistent ESTO or 9th targets.
- Produces researcher-facing QA outputs.

The maintenance workflow is upstream QA and workbook maintenance. It does not write to LEAP, and it does not create the final dashboard comparison dataset.

---

## From mapping rows to comparison outputs

The mapping rows in `outlook_mappings_master.xlsx` are the human-maintained input. Everything downstream is generated by scripts. The maintenance workflow (Stage 0) is described in the [Mapping maintenance workflow](#mapping-maintenance-workflow) section above; run it whenever workbook rows or rollup rules change, before running the downstream stages.

### Stage 0 - Mapping maintenance

`codebase/outlook_mapping_maintenance_workflow.py`

Maintains the workbook, recalculates subtotal columns, writes cardinality QA outputs, checks subtotal alignment, and produces tree-structure outputs.

### Stage 1 - Relationship rows

`codebase/mapping_tools/build_energy_balance_relationships.py`

Compiles source-target mapping rows into long relationship tables for each use case.

| Use case | Purpose |
| --- | --- |
| `leap_to_esto_balance_conversion` | Convert LEAP balance exports into ESTO-shaped rows |
| `ninth_to_esto_balance_conversion` | Convert 9th projections into ESTO-shaped rows |
| `leap_to_ninth_comparison` | Compare LEAP directly against 9th Outlook |
| `ninth_to_leap_initialisation` | Use 9th projections to initialise LEAP values |
| `mapping_review` | QA and coverage auditing |

Output: `results/mapping_relationships/energy_balance_relationships.csv`

This intermediate table exists because downstream scripts need a plain CSV interface that does not depend on Excel. It also has rollup rules already applied and expresses multiple named use cases as filtered views of a single compiled output, so each downstream stage can read one stable file rather than reconstructing the same logic from the workbook directly.

### Stage 2 - Rollup and common comparison structure

`codebase/mapping_tools/build_common_esto_structure.py`

Applies explicit rollup rules where defined and uses graph partitioning where required to generate common comparison rows.

The common ESTO structure is built separately for each comparison scope:

| Scope | What it covers |
| --- | --- |
| `leap_vs_esto` | LEAP and ESTO only |
| `leap_vs_ninth` | LEAP and 9th Outlook, bridged via ESTO |
| `leap_vs_esto_vs_ninth` | LEAP, ESTO, and 9th Outlook |
| `esto_only` | ESTO reference only |

Common row labels are generated mechanically from compressed component codes and a useful parent name where possible:

```text
07.12-07.17,07.99 Petroleum products
```

Output: `results/common_esto/common_esto_rows.csv`

### Stage 3 - Apply common structure to data

`codebase/mapping_tools/apply_common_esto_structure.py`

Maps LEAP/ESTO/9th data into comparison rows and aggregates values. It takes ESTO-shaped source data, maps rows with a known `common_row_id`, aggregates values within each common row, and writes a separate diagnostic for source rows that are outside the mapped universe.

Output: `results/common_esto/common_esto_comparison_data.csv`

Stage 3 uses a mapped-universe policy: final comparison outputs and total
preservation checks are based on rows that map to the common structure. Unmapped
ESTO rows are retained in
`results/common_esto/common_esto_source_rows_missing_common_map.csv` for review,
but they do not by themselves make the final comparison output invalid. Flows
listed in the `missing_common_map_ignored` sheet of
`config/mapping_issue_exception_sets.xlsx` are excluded from this diagnostic. If
mapped-universe preservation fails, the latest outputs are written with a
`_needs_mapping_review` suffix. Check
`results/common_esto/common_esto_output_status.csv` to see which files belong to
the latest run.

This stage is separate from Stage 2 because Stage 2 defines which comparison rows to use and can be run independently to check the structure without needing data. Stage 3 can then be re-run with new source data without rebuilding the structure.
### Stage 4 - Dashboard / comparison tools

The dashboard and comparison tools consume the final common comparison dataset. They should not consume raw LEAP rows, raw 9th rows, or direct `relationship_id -> graph_id` links.

---

## Hierarchical tree validation

Each source dataset has a hierarchical structure where parent row values should equal the sum of their child rows. Validating this catches missing mappings, misattributed rows, and aggregation errors. Recording the tree structure also provides the definitive basis for determining which rows are subtotals — any node that is not a leaf is a subtotal.

### How hierarchy is detected

Hierarchy is encoded differently in each dataset:

| Dataset | Encoding | Example |
| --- | --- | --- |
| ESTO | Dot-separated numeric codes | `09` → `09.06` → `09.06.01` |
| 9th Outlook | Underscore-separated codes plus `sub1sector`–`sub4sector` columns | `09_transformation` → `09_06_gas_processing_plants` |
| LEAP | Slash-separated branch paths | `Transformation` → `Transformation/Electricity plants` |
| Common comparison | ESTO dot notation where the category is ESTO-shaped; generated categories (e.g. `09.01.01,09.02.01 Electricity plants`) are treated as leaf-level | — |

A node is a leaf if it has no children in the dataset. Any non-leaf node is a subtotal.

### Dataset tree structure output

For each dataset the tree structure is recorded as a CSV with one row per node:

| Column | Meaning |
| --- | --- |
| `dataset` | Source dataset (`esto`, `ninth`, `leap`, `common`) |
| `axis` | Flow/sector axis or product/fuel axis |
| `code` | Code, label, or path of this node |
| `label` | Human-readable label |
| `parent_code` | Immediate parent code, or blank for root nodes |
| `level` | Depth in the hierarchy |
| `is_leaf` | Whether this node has no children |
| `is_subtotal` | Whether this node has children |

This file is produced as a prerequisite step and can be used independently of the mapping sheets — for example, to determine what level of detail a mapping row operates at, or to drive other validation tasks.

### Validation process

The current implementation validates ESTO product and flow subtotals. For each non-leaf ESTO product node, the validation sums all immediate product children and compares against the parent product value by economy, flow, and year. For each non-leaf ESTO flow node, it sums all immediate flow children and compares against the parent flow value by economy, product, and year.

Common ESTO validation is also run when `results/common_esto/common_esto_comparison_data.csv` exists. It uses parent/child rows that appear in both `common_esto_tree.csv` and the source ESTO tree, grouped by comparison scope, source system, economy, scenario, other axis, and year. Graph-generated aggregate labels, such as `09.01.01,09.02.01 Electricity plants`, and projection-only detail labels, such as datacentres, are treated as leaf-level because they do not have a source ESTO recursive hierarchy.

These validations do not yet prove mapped ESTO subtotal coverage. `esto_validation.csv` checks the raw ESTO hierarchy without regard to which child pairs are mapped. `qa_common_esto_total_check.csv` proves that values already admitted to the mapped universe are preserved through Common ESTO aggregation, but it does not compare every raw ESTO subtotal against the sum of its mapped leaf descendants. In addition, Stage 3 filters total/subtotal-labelled Common ESTO rows from the final comparison output, so an empty `common_esto_validation.csv` can mean either no mismatches or no eligible parent rows. A future mapped-subtotal coverage output must report both checks performed and mismatches.

- 9th Outlook value validation and LEAP value validation are not yet implemented in this tree workflow.

For example, an ESTO product check compares a parent product against the sum of its direct child products:

```text
Level 0: 07 Petroleum products
  Level 1: 07.01 Motor gasoline
  Level 1: 07.02 Aviation gasoline
```

The validation checks:

```text
07 Petroleum products = sum(07.xx child products) by economy, flow, and year
```

The tree files still record flow, 9th, LEAP, and Common ESTO hierarchy, but value validation is currently limited to ESTO and Common ESTO rows with direct dot-notation parent/child relationships.

### Current implementation status

The maintenance workflow builds hierarchical tree structures for all four datasets (ESTO, 9th, LEAP, Common ESTO) and runs recursive sum validation against the ESTO balance data. Tree CSVs are written to `results/tree_structure/` each time the maintenance workflow runs.

| Output | Content |
| --- | --- |
| `esto_tree.csv` | ESTO flow (up to depth 3) and product (up to depth 2) node hierarchy |
| `ninth_tree.csv` | 9th sector (up to depth 5) and fuel (depth 2) node hierarchy |
| `leap_tree.csv` | LEAP sector (slash-paths, depth 1–3) and fuel (flat) from mapping sheets |
| `common_esto_tree.csv` | Same dot-notation logic as ESTO, filtered to common structure rows |
| `esto_validation.csv` | Recursive sum check results: parent vs sum-of-children for ESTO products and flows |
| `common_esto_validation.csv` | Recursive sum mismatches for eligible Common ESTO parent rows; an empty file does not currently report how many checks were performed |
| `common_esto_non_esto_parent_child_edges.csv` | Common ESTO parent-child edges that are not present in the source ESTO tree; review these as dashboard/additive-total risks, not subtotal validation failures |

Tree CSV columns: `dataset`, `axis`, `code`, `label`, `level`, `parent_code`, `is_leaf`, `is_subtotal`. `is_subtotal` is derived from tree structure (node has children), not the data's mapping-context flag.

---

## Adding new scenarios

The mapping sheets are category-level, not scenario-level. Adding a new LEAP scenario does not require any changes to `outlook_mappings_master.xlsx`.

However, the current 9th-to-ESTO conversion path in `codebase/run_mapping_pipeline.py` calls `prepare_ninth_long_format()` with its default `scenario_filter="reference"`. A new LEAP scenario such as EED has no automatic 9th Outlook counterpart, so it can only participate in LEAP vs ESTO comparisons unless the conversion and dashboard scenario pairing are explicitly extended. LEAP vs 9th and three-way comparisons will not be available for it by default.

To include a new LEAP scenario in comparisons:

- No mapping sheet changes are needed.
- If the scenario should be paired with an existing 9th scenario (e.g. EED paired with `reference`), add it to the scenario map in `leap_dashboard`.
- If it has no 9th counterpart, it will appear in LEAP vs ESTO outputs only. The dashboard should handle this gracefully without errors.

---

## Special-case examples

### Transfers

On the ESTO side, `08 Transfers` is a real parent category in the hierarchy and requires no rollup rule — the detailed subflows (`08.01 Recycled products`, `08.02 Interproduct transfers`, `08.03 Products transferred`, `08.04 Gas separation`, `08.99 Transfers nonspecified`) aggregate to it naturally via the ESTO code hierarchy.

The rollup requirement is on the LEAP side. LEAP has no natural `Transfers` parent. Instead, transfers are modelled as transformation-style processes grouped by fuel function — upstream liquids movements, refinery and blending activity, and an unallocated remainder. This design was chosen to create meaningful economy-specific differentiation within LEAP rather than following ESTO's administrative categorisation, which organises transfers by type of transaction rather than by fuel group. As a result, LEAP transfer categories do not correspond to any individual ESTO `08.xx` subflow and cannot be mapped to them directly.

The three standard LEAP transfer process names roll up to `Transfers` for comparison against `08 Transfers` in ESTO:

```text
Upstream liquids transfers      →   Transfers
Refinery & blending transfers   →   Transfers
Transfers unallocated           →   Transfers
```

This is a normal `category_rollup` applied in the `leap_to_esto` context.

### Gas processing

Several LEAP gas-processing branches roll to a single comparison category for comparison against `09.06 Gas processing plants` in ESTO:

```text
Gas works plants              →   Gas processing plants
Gas to liquids plants         →   Gas processing plants
LNG regasification            →   Gas processing plants
NG Liquefaction               →   Gas processing plants
Natural gas blending plants   →   Gas processing plants
```

This is a normal `category_rollup`.

### Coal transformation

Several LEAP coal transformation branches roll to a single comparison category for comparison against `09.08 Coal transformation` in ESTO:

```text
BKB and PB plants        →   Coal transformation
Blast furnaces           →   Coal transformation
Coke ovens               →   Coal transformation
Liquefaction coal to oil →   Coal transformation
Patent fuel plants       →   Coal transformation
```

This is a normal `category_rollup`.

### Power sector

Since LEAP and ninth do not align with ESTO at detailed public/autoproducer/technology levels, use shared comparison categories such as these for mappig the esto categories to more simple categories that exclude the auto/main-activity producer split:
09.01.01 Electricity plants		09.01.01,09.02.01 Electricity plants
09.02.01 Electricity plants		09.01.01,09.02.01 Electricity plants
09.01.02 CHP plants		09.01.02,09.02.02 CHP plants
09.02.02 CHP plants		09.01.02,09.02.02 CHP plants
09.01.03 Heat plants		09.01.03,09.02.03 Heat plants
09.02.03 Heat plants		09.01.03,09.02.03 Heat plants

- `Electricity plants`
- `CHP plants`
- `Heat plants`

Interim power branches should be handled as placeholders or fallback rows, not additive detail alongside completed branches. Note that purpose clearly in the rollup rule `Note` column.

### Final consumption

Final consumption rollups must be applied through context-specific comparison views. A branch such as `Freight road` appears in road, transport, and total final consumption comparisons simultaneously — applying all rollups at once without context would sum it multiple times.

Each rollup context defines one comparison view:

**`road_comparison`**

```text
Freight road    →   Road
Passenger road  →   Road
```

**`other_sector_comparison`**

```text
Other sector/Agriculture   →   Agriculture and fishing
Other sector/Fishing       →   Agriculture and fishing
```

**`transport_comparison`**

```text
Freight road                              →   Transport
Passenger road                            →   Transport
Transport non road/Freight non road       →   Transport
Transport non road/Nonspecified transport →   Transport
Transport non road/Pipeline transport     →   Transport
Transport non road/Passenger non road     →   Transport
```

**`tfc_comparison`**

```text
All demand aggregated   →   Total final consumption
Buildings               →   Total final consumption
Freight road            →   Total final consumption
Industry                →   Total final consumption
Other sector            →   Total final consumption
Passenger road          →   Total final consumption
Transport non road      →   Total final consumption
```

**`tfec_comparison`**

```text
All demand aggregated   →   Total final energy consumption
Buildings               →   Total final energy consumption
Freight road            →   Total final energy consumption
Industry                →   Total final energy consumption
Other sector            →   Total final energy consumption
Passenger road          →   Total final energy consumption
Transport non road      →   Total final energy consumption
```

### Own use and losses

ESTO `10.x` own-use/loss rows are folded into their related transformation comparison categories as explicit comparison-boundary adjustments. LEAP and 9th Outlook do not report these own-use/loss quantities separately from the transformation process — they are absorbed into the process boundary. Including the ESTO own-use rows in the comparison category makes the boundary consistent across all three datasets.

The comparison categories use an `(including own use)` suffix to make this explicit. This preserves the original category name (e.g. `09.06 Gas processing plants`) for use with datasets that do report own-use separately, and makes it unambiguous to any reader what is included in the boundary.

**ESTO rollups:**

| ESTO own-use/loss row | Comparison category |
| --- | --- |
| `10.01.02 Gas works plants` | `09.06 Gas processing plants (including own use)` |
| `10.01.02 Gas works plants` | `09.06.01 Gas works plants (including own use)` |
| `10.01.03 Liquefaction/regasification plants` | `09.06 Gas processing plants (including own use)` |
| `10.01.03 Liquefaction/regasification plants` | `09.06.02 Liquefaction/regasification plants (including own use)` |
| `10.01.05 Coke ovens` | `09.08 Coal transformation (including own use)` |
| `10.01.05 Coke ovens` | `09.08.01 Coke ovens (including own use)` |
| `10.01.07 Blast furnaces` | `09.08 Coal transformation (including own use)` |
| `10.01.07 Blast furnaces` | `09.08.02 Blast furnaces (including own use)` |
| `10.01.11 Oil refineries` | `09.07 Oil refineries (including own use)` |
| `10.01.17 Non-specified own uses` | `09.12 Non-specified transformation (including own use)` |

**9th Outlook rollups:**

| 9th own-use/loss sector | Rolled comparison category |
| --- | --- |
| `10_01_02_gas_works_plants` | `09_06_gas_processing_plants_incl_own_use` |
| `10_01_02_gas_works_plants` | `09_06_01_gas_works_plants_incl_own_use` |
| `10_01_03_liquefaction_regasification_plants` | `09_06_gas_processing_plants_incl_own_use` |
| `10_01_03_liquefaction_regasification_plants` | `09_06_02_liquefaction_regasification_plants_incl_own_use` |
| `10_01_05_coke_ovens` | `09_08_coal_transformation_incl_own_use` |
| `10_01_05_coke_ovens` | `09_08_01_coke_ovens_incl_own_use` |
| `10_01_07_blast_furnaces` | `09_08_coal_transformation_incl_own_use` |
| `10_01_07_blast_furnaces` | `09_08_02_blast_furnaces_incl_own_use` |
| `10_01_11_oil_refineries` | `09_07_oil_refineries_incl_own_use` |
| `10_01_17_nonspecified_own_uses` | `09_12_nonspecified_transformation_incl_own_use` |

These rules should be documented in the rollup rule `Note` column with:

```text
comparison_boundary_adjustment: own_use_absorbed_into_transformation_boundary
```

Do not describe these as ordinary mappings. They are explicit boundary adjustments that make the ESTO comparison boundary consistent with how LEAP and 9th Outlook define their transformation process scope.

---

## QA outputs and what to look for

QA outputs are produced at each pipeline stage. The most important outputs to review are described below, grouped by which stage produces them.

### Stage 1 — Relationship rows (`build_energy_balance_relationships.py`)

These files are written to `results/mapping_relationships/`:

| File | What it means |
| --- | --- |
| `one_to_many_mappings_without_allocation_or_combined_target.csv` | Source rows that map to more than one target with no allocation rule or combined-target declared. These are the equivalent of many-to-many signals before rollup — they usually mean the mapping crosses a source aggregate boundary and needs a rollup or common category. Review before assuming the mapping is correct. |
| `leap_to_esto_duplicate_source_pairs.csv` | Multiple mapping rows with the same LEAP source pair, which may cause double-counting. |
| `leap_to_esto_duplicate_target_pairs.csv` | Multiple mapping rows with the same ESTO target pair, which may indicate conflicting coverage. |
| `leap_to_esto_parent_child_risks.csv` | Cases where a parent ESTO row and one of its child rows both appear as active mapping targets. If both rows are included in the same additive output this will double-count the child. |
| `esto_targets_without_leap_source.csv` | ESTO target rows that have no active LEAP source mapping. Check whether the gap is expected or a missing mapping. |
| `leap_sources_without_esto_target.csv` | LEAP source rows that have no active ESTO target mapping. |
| `missing_dataset_pairs_by_use_case.csv` | For each use case, rows present in one dataset but absent or excluded in another. Useful for finding coverage gaps by use case. |
| `leap_to_esto_excluded_source_audit.csv` | All excluded LEAP source rows with their exclusion reasons. Use this to check whether removed rows are intentional guardrails or gaps. |
| `leap_to_esto_coverage_summary.csv` | Summary of mapping coverage per use case: how many source and target pairs are included, excluded, or missing. |
| `coverage_exclusions.csv` | Explicit coverage exclusions declared in the workflow, with reason. |
| `not_considered_esto_rows.csv` | ESTO rows that were present in the source data but not considered in any relationship row. Usually empty if coverage is complete. |
| `esto_combined_rows.csv` | Combined-target rows declared in the mapping (where multiple ESTO rows are treated as a single comparison target). Usually empty until combined-target logic is populated. |

**Key signals from Stage 1:**

- A non-empty `one_to_many_mappings_without_allocation_or_combined_target.csv` is a warning, not an automatic error. Review each group to check whether a rollup or common category is needed.
- `leap_to_esto_parent_child_risks.csv` entries are high-priority. A single active parent row and an active child row for the same ESTO target will double-count if both are summed together.
- `leap_sources_without_esto_target.csv` being non-empty is expected for some LEAP branches that have no ESTO counterpart. Check the exclusion audit for rows that should have a mapping but do not.

### Stage 2 — Common ESTO structure (`build_common_esto_structure.py`)

Stage 2 reads the expanded, rollup-augmented relationship rows from Stage 1 and graph-partitions ESTO (flow, product) pairs into common comparison rows. Key QA outputs written to `results/common_esto/`:

| File | Contents |
| --- | --- |
| `qa_common_esto_rollup_explanations.csv` | Which source aggregates drove each graph edge |
| `qa_common_esto_source_aggregates_split.csv` | Source aggregates that were split rather than rolled — high-severity if non-empty |
| `qa_common_esto_structural_partial_coverage.csv` | Full Stage 2 structural candidates where a comparison system covers only part of a Common ESTO row |
| `qa_common_esto_unresolved_partial_coverage.csv` | Stage 3 actionable subset with one missing ESTO pair per row, explicit evidence columns, and the mapping sheet/system that needs review |
| `qa_common_esto_partial_coverage_components_without_relevance.csv` | Structurally missing components without qualifying current-data evidence |
| `qa_common_esto_existing_components_without_relevance.csv` | Existing components not required by current comparison data; informational only |
| `qa_nonzero_unmapped_leap_branches.csv` | Non-zero LEAP branches without direct ESTO mappings and any auditable indirect ESTO pair |
| `qa_common_esto_partial_coverage_mapping_candidates.csv` | Only complete, high-confidence, non-zero, copy-ready candidates for actionable partial coverage |
| `qa_nonzero_unmapped_leap_branch_mapping_candidates.csv` | Only complete, high-confidence, non-zero, copy-ready candidates for unmapped LEAP branch/fuel pairs |
| `highly_recommended_mapping_candidates.csv` | Combined copy-ready rows from both candidate files; its path is printed prominently by Stage 3 |
| `qa_common_esto_flow_axis_partitions.csv` | How ESTO flow codes were grouped into common flow axes |
| `qa_common_esto_product_axis_partitions.csv` | How ESTO product codes were grouped into common product axes |

Many-to-many relationships that survive into the common structure are a high-severity problem — check `qa_common_esto_source_aggregates_split.csv` if the structure looks unexpectedly broad.

Stage 2 outputs are structure outputs, not final result data. Review `common_esto_rows.csv` and `esto_to_common_esto_map.csv` for the generated comparison categories that Stage 3 will apply to LEAP, ESTO, and 9th data. The QA files above explain why rows were rolled together and whether any source aggregate was split or only partially covered. A clean Stage 2 does not mean source values match; it means the common comparison structure is internally consistent enough for Stage 3.

### Maintenance workflow (`outlook_mapping_maintenance_workflow.py`)

`codebase/outlook_mapping_maintenance_workflow.py` produces QA outputs to `results/maintenance/`:

| File | Contents |
| --- | --- |
| `maintenance_summary.csv` | Compact row-count and status summary for the main Stage 0 maintenance and tree validation outputs |
| `cardinality_leap_esto.csv` | (LEAP source, ESTO target) pair cardinality |
| `cardinality_leap_ninth.csv` | (LEAP source, 9th target) pair cardinality |
| `cardinality_ninth_esto.csv` | (9th source, ESTO target) pair cardinality |
| `many_to_many_allowed_matched.csv` | Current many-to-many rows matched by the manual `many_to_many_allowed` exception sheet |
| `many_to_many_conflicts.csv` | Active many-to-many mapping pairs that are not allowlisted and still need review |
| `leap_source_presence_conflicts.csv` | Active LEAP source pairs present in only one of `leap_combined_esto` or `leap_combined_ninth` |
| `crosswalk_target_conflicts_allowed_matched.csv` | Current crosswalk rows matched by the manual `crosswalk_allowed` exception sheet |
| `crosswalk_target_conflicts.csv` | Active LEAP-to-9th mappings where the 9th-to-ESTO crosswalk implies ESTO targets that are not active for the same LEAP source; `conflict_classification` separates missing crosswalk rows, expected combined/aggregate targets, partial combined-target reviews, and target mismatches |
| `unmapped_esto_pairs.csv` | ESTO (flow, product) pairs in the data file with no active mapping row |
| `unmapped_ninth_pairs.csv` | 9th (sector, fuel) pairs in the data file with no active mapping row |
| `subtotal_mismatches_allowed_matched.csv` | Current subtotal mismatch rows matched by the manual `subtotal_mismatch_allowed` exception sheet |
| `subtotal_mismatches.csv` | Current leaf source → aggregate target subtotal mismatch rows not present in the manual exception workbook |

### Notes on interpreting outputs

Broad common rows generated by graph partitioning are not automatically wrong. They may be the correct result when a source aggregate overlaps several detailed ESTO rows. Parent/detail common labels may also coexist in the output. Treat these as review diagnostics rather than blockers when mapped-universe totals and subtotal/tree validation pass.

Many-to-many before rollup (flagged in Stage 1) is a signal. Many-to-many that survives into the common ESTO structure (Stage 2) is a problem.

---

## Column-level quick reference

### Columns shared across base mapping sheets

The table below covers the stable conceptual columns. The authoritative full column list is in the Guide sheet of `config/outlook_mappings_master.xlsx`.

| Column | Updated by | Meaning |
| --- | --- | --- |
| `leap_is_subtotal` | Mapping maintenance workflow | LEAP branch is a subtotal row |
| `esto_pair_is_subtotal` / `ninth_pair_is_subtotal` | Mapping maintenance workflow | Target pair is a subtotal row |
| `remove_row` | Human | Whether the row is excluded, when present |
| `remove_row_reason` | Human | Reason for exclusion, when present |
| `Note` | Human | Free text explanation |

Subtotal columns should not be manually edited. They are overwritten by the mapping maintenance workflow. Cardinality is currently written to `results/maintenance/cardinality_*.csv` rather than workbook columns.

## Review-only computer-generated mapping candidates

Mapping candidates use a repeatable axis-first inference method:

1. Learn branch/sector-to-flow evidence from reviewed mappings already in the canonical workbook.
2. Learn fuel-to-product evidence separately.
3. Restrict candidate source pairs to combinations that occur with non-zero relevant source data.
4. Combine the two independently inferred axes into a proposed mapping row.
5. Rank candidates using support counts, axis consistency, and source-data presence.
6. Put only complete, high-confidence, non-zero candidates that do not add another target into the copy-ready outputs.
7. Leave every incomplete or ambiguous finding in its original QA file; never update the workbook automatically.

For partial coverage, `source_system` identifies the mapping sheet that lacks coverage. A `LEAP` finding belongs in `leap_combined_esto`; a `NINTH` finding belongs in `ninth_pairs_to_esto_pairs`. Evidence such as `esto_base_year_nonzero` explains why the missing ESTO component matters, but does not mean the ESTO data or workbook should be edited.

Relevance does not prove that a direct mapping should exist. Aggregate-looking target flows or products, especially `Total` rows, are flagged for subtotal/hierarchy review first because adding direct parent mappings alongside detail can double count.

The actionable partial-coverage output contains one missing pair per row. Its evidence columns include the selected ESTO base year, non-zero row/economy counts and magnitudes, the 9th projection year range and magnitudes, mapped LEAP balance evidence, and indirectly inferred evidence from non-zero unmapped LEAP branches.

Candidate rows deliberately include the canonical copy columns:

- `leap_combined_esto`: `leap_sector_name_full_path`, `raw_leap_fuel_name`, `esto_flow`, `esto_product`.
- `ninth_pairs_to_esto_pairs`: `9th_sector`, `9th_fuel`, `esto_flow`, `esto_product`.

Rows in `highly_recommended_mapping_candidates.csv` have `paste_ready = True` and a sheet-specific `paste_instruction`. They may be copied into the named mapping sheet because the source pair is non-zero and both axes reproduce patterns already present in reviewed mappings. The required pipeline rerun remains part of applying the row. Medium-confidence, zero-only, incomplete, or source-pair-already-mapped suggestions are excluded from all candidate files rather than mixed with recommended rows.

Independent-axis inference is often strong because branch/sector labels generally determine the balance flow while fuel labels determine the product. It is not universally valid. A source pair may be context-specific, aggregate, subtotal, or legitimately one-to-many. Low support, conflicting axis targets, an existing target for the proposed source pair, compound categories, and hierarchy-level differences are mandatory review warnings.

For non-zero LEAP branches without direct ESTO mappings, the workflow first uses an auditable LEAP-to-9th-to-ESTO chain when available. Otherwise it tries exact branch-path evidence, a collapsed repeated-path form, then the branch leaf name; fuel evidence remains separate. If both axes cannot be inferred, the output retains an unresolved row instead of inventing a target.

Before copying a candidate into the workbook:

1. Confirm the proposed source pair exists and is non-zero in the relevant source data.
2. Check definitions, inclusions, exclusions, and common mistakes in `config/esto_external_definition_authority_working_set.xlsx`.
3. Check whether the source pair already maps to another target.
4. Check source and target subtotal levels.
5. Check whether the new row creates one-to-many or many-to-many coverage before and after rollup.
6. Add a note or decision-log reference for any non-obvious choice.
7. Rerun maintenance and Stages 1-3; review totals, partial coverage, and cardinality again.

### Rollup rule columns

| Column | Meaning |
| --- | --- |
| `rollup_context` | When the rule applies, such as `leap_to_esto`, `transport_comparison`, or `all` |
| `input_*` | Source row matched by the rule |
| `rolled_*` | Effective comparison row after rollup |
| `include` | Whether the rule is active |
| `Note` | Human explanation of why this rollup exists |

---

## Common mistakes to avoid

**Restoring removed rows without checking cardinality.** A row is often removed because activating it would create a many-to-many mapping. Restoring it without understanding why it was removed will create unresolved cardinality problems downstream.

**Adding a many-to-many workaround in the base sheet instead of a rollup rule.** The base sheets should stay simple. If an exact match is not possible at the current level of detail, add a rollup rule for known comparison boundaries or let the common-category generator roll up to the safest common level.

**Using `all` as a rollup context too casually.** `all` should only be used when the rule is safe in every comparison view. Otherwise, use a specific context so the same row is not rolled into multiple totals at once.

**Treating own-use/loss boundary adjustments as ordinary mappings.** If an ESTO `10.x` row is folded into a transformation category, document it as a `comparison_boundary_adjustment` with a clear reason. These rows use the `(including own use)` suffix in their comparison category name to make the boundary explicit.

**Combining detailed rows and rolled rows in the same total.** Rollups preserve original rows for traceability, but rolled comparison outputs are separate additive views. The hierarchical totals validation can help detect this — if a parent and child row both appear in the same additive output, the parent-child check will flag the double count.

**Comparing dashboard totals against raw ESTO or 9th data.** The comparison outputs use common comparison rows, which may aggregate several ESTO pairs or apply rollup rules. Comparing them directly against individual raw rows may show apparent differences that are actually correct rollup results.

**Editing subtotal columns manually.** These are computed by the mapping maintenance workflow. Manual edits will be overwritten on the next maintenance run. Cardinality should be reviewed in the generated `results/maintenance/cardinality_*.csv` files.

**Treating `ninth_pairs_to_esto_pairs` as complete.** This sheet can have known gaps. Use mapping coverage outputs to identify which 9th or ESTO rows are currently unmapped, removed-only, or intentionally excluded.
