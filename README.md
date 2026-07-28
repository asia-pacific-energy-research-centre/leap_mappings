# leap_mappings

This repo is the active home for LEAP / ESTO / 9th Outlook mapping maintenance. It keeps the human mapping task simple while letting scripts generate the more complex relationship tables, common-denominator ESTO structures, and QA outputs needed for fair comparisons.

New to the connected mappings, LEAP-initialisation, and dashboard system? Start
with [`docs/handover/README.md`](docs/handover/README.md). Analysts can continue
to the
[`end-to-end system guide`](docs/handover/end_to_end_system_guide.md); agents
should use the
[`operations guide`](docs/handover/agent_operations_guide.md).

Researchers should maintain simple editable mapping sheets such as:

- `leap_combined_esto`: LEAP rows mapped to exact ESTO flow/product components.
- `ninth_pairs_to_esto_pairs`: 9th Outlook rows mapped to exact ESTO flow/product components.
- `leap_combined_ninth`: LEAP rows mapped to 9th Outlook sector/fuel rows.

The core idea is that people edit simple rows:

```text
source row -> target row/component
include/exclude
notes
```

Scripts then generate the structured outputs used by comparison tools and dashboards.

## Layered Workflow

1. Refresh and audit the simple mapping workbook:
   - `codebase/archive/outlook_mapping_maintenance_workflow.py`
   - input: `config/outlook_mappings_master.xlsx`

2. Generate canonical relationship rows:
   - `codebase/mapping_tools/build_energy_balance_relationships.py`
   - output: `results/mapping_relationships/energy_balance_relationships.csv`
   - output: `results/mapping_relationships/energy_balance_relationships.xlsx`

3. Build automatic common ESTO rows:
   - `codebase/mapping_tools/build_common_esto_structure.py`
   - output: `results/common_esto/common_esto_rows.csv`
   - output: `results/common_esto/esto_to_common_esto_map.csv`

4. Apply the common structure to ESTO-shaped data:
   - `codebase/mapping_tools/apply_common_esto_structure.py`
   - output: `results/common_esto/common_esto_comparison_data.csv`
   - optional wide output: `results/common_esto/common_esto_comparison_wide.csv`

The dashboard should use common ESTO comparison data, not raw LEAP rows, raw 9th rows, or `relationship_id -> graph_id` links. `dashboard_chart` should not be treated as a required mapping use case.

## Common ESTO Structure

The common ESTO structure is generated as a graph/partition problem. Exact ESTO flow/product pairs are nodes. If a LEAP or 9th source row maps to multiple ESTO components, those components get connected and must stay together for comparison scopes that include that source.

This protects the main rule:

```text
Do not split a source aggregate unless there is an explicit allocation method.
```

If all sources can support exact ESTO detail, the row stays exact. If one source is coarser, other sources are rolled up to the common denominator.

Common row labels are mechanical:

```text
compressed component codes + nearest useful parent name
```

For example:

```text
07.12-07.17,07.99 Petroleum products
```

Label overrides can improve display names, but they should not change component membership.

## QA Philosophy

The generated QA outputs are as important as the final comparison table. They should show:

- missing or duplicate exact ESTO components;
- source aggregates split across common rows;
- rollup explanations;
- unresolved partial coverage;
- total preservation checks;
- broad or intersecting aggregate groups for review.

The system should usually resolve detail mismatches by rolling up. Final comparison outputs use a mapped-universe policy: rows outside the common structure are written to diagnostics, while mapped rows must preserve totals. Broad rows and parent/detail overlaps are review signals rather than blockers when mapped-universe totals and subtotal/tree validation pass.

## Current Inputs

- `config/outlook_mappings_master.xlsx`
- `data/00APEC_2025_low_with_subtotals.csv`
- `data/merged_file_energy_ALL_20251106.csv`
- `data/leap balances exports/`

Raw LEAP balance exports are owned by the sibling `leap_initialisation` repo at
`../leap_initialisation/data/leap balances exports/`. Mapping outputs are written
to this repository's `results/`; the local path above is legacy/reference only
and is not selected by the pipeline. Set `LEAP_BALANCE_EXPORTS_ROOT` only for a
non-standard checkout layout.

`config/master_config.xlsx` is a legacy reference workbook.
`config/leap_mappings.xlsx` is a retired legacy filename and is not present in
the current checkout. New mapping pipeline work should use
`config/outlook_mappings_master.xlsx` unless a script is explicitly documented
as legacy.

Run notebook-style from the repo root, following `AGENTS.md`.

## Finding Your Way Around `results/`

The pipeline writes a lot into `results/`. Start with `results/README.md` — it points to the
handful of primary outputs and links to a short guide for each subfolder. See
`docs/results_folder_cleanup_candidates.md` for known clutter/orphaned files flagged for future
cleanup (not yet actioned), and `docs/repo_data_slimdown_plan.md` for which `config/`/`data/`
files are actually required to run the pipeline.

## Finding Your Way Around `codebase/`

`codebase/` mixes the live pipeline with standalone maintenance tools, a legacy refresh
workflow, dashboard-prototype code that (per `AGENTS.md`) belongs in the sibling
`leap_dashboard` repo instead, and at least one currently-broken script. See
`docs/workflow_inventory.md` for which is which before assuming a file is part of the active
pipeline just because it's under `codebase/`.

## Finding Your Way Around the Rest of the Repo

`config/README.md` and `data/README.md` explain what's required to run the pipeline vs. legacy,
right there in each folder. `docs/README.md` indexes every file under `docs/` so you don't have
to open all of them to find the one you need.

## Suggested Improvements To The Guide

- Add a small diagram of the pipeline: editable sheets -> relationships -> common ESTO rows -> comparison data -> dashboard.
- Define `comparison_scope` explicitly in the implementation plan, including which systems each scope includes.
- Separate hard QA failures from warning diagnostics, for example: missing components and split source aggregates should fail; label overrides and broad-but-unused aggregates can warn.
- Add one concrete worked example, such as 9th `01_x_thermal_coal` forcing `01.02-01.04,01.99 Coal` as the product partition.
- Add a short glossary for `relationship`, `component`, `common row`, `source aggregate`, and `axis partition`.
