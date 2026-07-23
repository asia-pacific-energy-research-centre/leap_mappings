# `results/` — navigation guide

Everything in this folder is **generated output**. Nothing here should be hand-edited — if a
file looks wrong, fix the input (`config/outlook_mappings_master.xlsx`, `data/*.csv`) or the
producing script, then re-run the pipeline. The whole folder is gitignored and safe to delete;
`python codebase/run_mapping_pipeline.py` rebuilds it from scratch (see the "How this gets
built" section below).

This README and the one in each subfolder exist because the pipeline currently produces far
more files than a first-time reader needs to see at once. See
`docs/results_folder_cleanup_candidates.md` for a list of files that look stale/orphaned and
are flagged for future cleanup — nothing has been deleted yet.

## Start here

If you just want the answer — the fully mapped, comparable LEAP / 9th Outlook / ESTO dataset —
these four files are it:

| File | What it is |
|---|---|
| `common_esto/common_esto_comparison_data.csv` | The final long-format comparison table: every source row mapped onto the common ESTO structure. This is what dashboards should read. |
| `common_esto/common_esto_comparison_wide.csv` | Same data, pivoted to one column per year — easier to eyeball or drop into Excel. |
| `common_esto/common_esto_rows.csv` | The common ESTO row structure itself (which exact ESTO components got grouped together, and why). |
| `mapping_relationships/energy_balance_relationships.csv` | The row-level relationships (source → target) that everything downstream is built from — trace a mapping decision back here. |

If a total looks wrong, the QA files under `common_esto/` (prefixed `qa_`) and
`tree_structure/` are where to look next — see those folders' READMEs.

## Folder map

| Folder | Built by (pipeline stage) | Contains |
|---|---|---|
| `common_esto/` | Stage 2 (build) + Stage 3 (apply) | The final comparison data, the common-row structure, and most of the QA/diagnostic output. Start here for almost everything. |
| `mapping_relationships/` | Stage 1 + `data_convert` | Intermediate relationship tables and per-source (LEAP/9th/ESTO) conversion outputs. Mostly lineage/QA, not usually the first stop. |
| `tree_structure/` | Stage 3 | Hierarchy trees for each dataset and recursive-sum validation. Check here when a subtotal doesn't reconcile. |
| `maintenance/` | Stage 0 | QA on the mapping workbook itself (duplicates, unmapped pairs, subtotal-flag issues). Check before editing `outlook_mappings_master.xlsx`. |
| `logs/` | every pipeline run | `mapping_pipeline.log` — the tee'd console output of the last run. Check first when a run fails. |
| `mapping_graph_index/` | standalone dashboard tools, **not** the main pipeline | Graph-index tables for the LEAP comparison dashboard template. Only relevant if you're working on dashboard wiring. Not currently populated in this checkout — see that folder's README. |
| `for_colleagues/` | standalone export script | Simplified, trimmed copies of the comparison data for sharing outside the repo. |
| `missing_mapped_esto_rows/` (top level) | none — stale duplicate | See `docs/results_folder_cleanup_candidates.md`. The live version of this output is under `maintenance/missing_mapped_esto_rows/`; this top-level copy is an older, superseded run. |

## How this gets built

`codebase/run_mapping_pipeline.py` runs the stages in order:

```
0  Maintenance      -> results/maintenance/
1  Relationships    -> results/mapping_relationships/energy_balance_relationships.*
2  Common structure -> results/common_esto/common_esto_rows.*
   leap_parse       -> results/mapping_relationships/raw_leap_results.csv
   data_convert     -> results/mapping_relationships/*_converted_to_esto.csv, esto_results_exact_rows.csv
3  Apply structure  -> results/common_esto/common_esto_comparison_data.csv, results/tree_structure/*
```

A handful of other scripts under `codebase/mapping_tools/` are **standalone** maintenance/QA
tools a researcher runs manually (not part of the automatic pipeline run) — each subfolder
README says which of its files come from the pipeline vs. a standalone script.

See the repo root `README.md` for the full pipeline description and `docs/mappings_system.md`
for the design rationale.
