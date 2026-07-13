# Prompt: Investigate Buildings / Buildings-Services NINTH Counterpart Gaps

Work in `C:\Users\Work\github\leap_mappings`.

## Task Type

Investigation only. Do not edit `config/outlook_mappings_master.xlsx` during this prompt.

The goal is to classify the `Buildings` and `Buildings/Services` NINTH counterpart gaps as either:

- expected one-sided granularity differences; or
- fixable missing mapping/crosswalk coverage, with specific proposed rows for later human review.

## Read First

Before doing analysis, read:

- `AGENTS.md`
- `docs/prompts/AGENTS.md`
- `docs/mappings_system.md`
- `docs/rollup_rules_system.md`, if present

Then run:

```powershell
git status --short
```

Preserve unrelated dirty worktree changes. Do not stage, revert, or format unrelated files.

## Background

`results/common_esto/inverted_conservation_variant_verification/inverted_conservation_no_counterpart.csv`
contains a concentration of `target_without_source` findings in the `NINTH_TO_LEAP`
direction for LEAP `target_flow` values:

- `Buildings`
- `Buildings/Services`

These findings mean the structural crosswalk has LEAP-side source pairs for those
flows, but no NINTH-side source row lands on the same common row. The current open
question is whether this is expected dataset granularity or a missing mapping.

Important: this is not a Liquefaction, Regasification, CHP, Electricity, or Heat
plants task. Do not touch those areas.

## Inputs To Inspect

Use these files as evidence:

- `results/common_esto/inverted_conservation_variant_verification/inverted_conservation_no_counterpart.csv`
- `results/common_esto/structural_artifacts/source_pair_to_common_row.csv`
- `results/tree_structure/all_dataset_trees.csv`
- `results/tree_structure/leap_tree.csv`
- `results/tree_structure/ninth_tree.csv`
- `results/common_esto/common_esto_rows.csv`
- `results/mapping_relationships/energy_balance_relationships.csv`
- `results/mapping_relationships/ninth_source_to_esto_component_lineage.csv`, if present
- `results/common_esto/esto_component_to_common_row_lineage.csv`, if present

Read these workbook sheets without modifying them:

- `config/outlook_mappings_master.xlsx` / `leap_combined_ninth`
- `config/outlook_mappings_master.xlsx` / `ninth_pairs_to_esto_pairs`
- `config/outlook_mappings_master.xlsx` / `leap_rollup_rules`
- `config/outlook_mappings_master.xlsx` / `ninth_rollup_rules`
- any sheet that lists NINTH unique sectors/fuels, if present

Use source NINTH data for actual row/value evidence:

- `data/merged_file_energy_ALL_20251106.csv`

## Investigation Steps

1. Confirm the current gap set.
   - Filter `inverted_conservation_no_counterpart.csv` to:
     - `counterpart_state == "target_without_source"`
     - `target_flow` in `["Buildings", "Buildings/Services"]`
   - Summarise by `target_flow`, fuel/product, `comparison_scope`, scenario, and year.
   - Record whether the issue appears in both `reference` and `target`, or only one scenario.

2. Explain `Buildings` vs `Buildings/Services`.
   - Use the LEAP tree and `leap_rollup_rules`.
   - Determine whether these are parent/child rows, subtotal/detail rows, rollup duplicates, or distinct modeled categories.
   - Decide whether the no-counterpart rows are double-counting the same semantic gap at two hierarchy levels.

3. Trace each gap to Common ESTO structure.
   - Use `source_pair_to_common_row.csv` to find the common rows for the affected LEAP pairs.
   - For each common row, check whether any NINTH source pair maps to the same common row.
   - If lineage files exist, use them as supporting evidence, not as the only source of truth.

4. Check whether NINTH has candidate source data.
   - Identify likely NINTH buildings sectors such as residential/commercial/buildings/service sector rows from the source data and workbook vocabulary.
   - For each affected fuel, check whether NINTH has non-zero data under a plausible buildings sector.
   - Separate:
     - NINTH has no comparable source row or no non-zero data;
     - NINTH has data but no mapping path to the Common ESTO row;
     - NINTH maps to a different common row because of a legitimate boundary difference.

5. Classify each fuel gap.
   - Use one row per `target_flow` plus fuel/product, unless the same classification clearly applies to a group.
   - Classification values:
     - `expected_granularity_gap`
     - `likely_missing_leap_ninth_mapping`
     - `likely_missing_ninth_esto_mapping`
     - `rollup_or_hierarchy_duplicate`
     - `needs_human_decision`
   - Include concise evidence for each classification.

6. Propose fixes only where justified.
   - Do not apply workbook edits in this prompt.
   - For fixable gaps, provide copy-ready proposed rows with sheet name and columns:
     - `leap_combined_ninth`: `leap_sector_name_full_path`, `raw_leap_fuel_name`, `ninth_sector`, `ninth_fuel`
     - `ninth_pairs_to_esto_pairs`: `ninth_sector`, `ninth_fuel`, `esto_flow`, `esto_product`
   - Include warnings if a proposed row may create subtotal, parent/child, one-to-many, or many-to-many issues.

## Outputs

Create a findings document:

```text
docs/prompts/buildings_ninth_counterpart_gap_FINDINGS.md
```

Keep it human-readable and compact. Include:

- summary verdict;
- counts by flow/fuel/classification;
- explanation of `Buildings` vs `Buildings/Services`;
- evidence table for classifications;
- proposed mapping rows, if any;
- follow-up validation commands to run if mappings are later applied.

If a supporting CSV would make the evidence easier to inspect, write one narrow file under:

```text
results/common_esto/diagnostics/buildings_ninth_counterpart_gap/
```

Do not create multiple debug-heavy files unless they are necessary.

## Validation

For investigation-only work, validation means:

- the findings can be reproduced from the listed input files;
- every proposed mapping row has source-data evidence;
- expected granularity gaps explicitly say why no mapping should be added;
- `config/outlook_mappings_master.xlsx` remains unmodified by this task.

If you write helper code, run focused tests or a small reproducibility snippet and report the command used.

Do not run the full mapping pipeline unless the investigation genuinely needs refreshed outputs. If refreshed outputs are needed, stop and recommend using `docs/prompts/run_mapping_pipeline_future_prompt.md`.

## Stop Conditions

Stop and report rather than editing mappings if:

- source files needed for the investigation are missing;
- the workbook schema differs from the expected sheets/columns;
- the evidence points to mapping fixes that require human semantic decisions;
- results depend on stale generated outputs that need a full pipeline refresh.

## Completion

When the investigation is complete, tested where applicable, and committed:

- archive this prompt and its findings file to `docs/archive/`;
- update `docs/prompts/AGENTS.md`;
- commit only files belonging to this investigation.
