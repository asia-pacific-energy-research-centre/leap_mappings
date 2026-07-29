# Repo data slim-down plan (config / data / results)

Source: `config data results leap mappigns.zip` (repo root), 485 entries, ~4.9 GB uncompressed.

> **Execution update (2026-07-29):** the active pipeline now starts at Stage 1.
> References below have been updated accordingly; focused hierarchy/subtotal
> and missing-ESTO-row reviews are optional workflows outside the pipeline.

Goal: extract only what `codebase/run_mapping_pipeline.py` (Stages 1, 2, `leap_parse`,
`data_convert`, 3) and its applicable optional review workflows actually read as *inputs*. Everything
else in `results/` is a regenerated **output** of running the pipeline, so almost none of it
needs to be extracted at all.

Traced by reading `codebase/run_mapping_pipeline.py` and the modules it imports
(`build_energy_balance_relationships.py`, `build_common_esto_structure.py`,
`apply_common_esto_structure.py`, `convert_leap_results_to_esto.py`,
`apply_ninth_to_esto_conversion.py`, `build_dataset_tree_structure.py`,
`codebase/archive/outlook_mapping_maintenance_workflow.py`, `mapping_issue_exceptions.py`,
`source_branch_preflight.py`), plus grepping the rest of `codebase/` for every other file named
in the zip to confirm it's actually referenced somewhere.

**Note (2026-07-23):** this plan describes a *secondary checkout*'s zip snapshot, not this repo
directly — this repo already exists in full, it wasn't extracted from that zip. Treat the figures
below as reference for "what's actually load-bearing vs. safe to exclude from a fresh checkout,"
not as a literal to-do list for this repo's current working tree.

## Bottom line

| Folder | Zip size | Needed for main workflow | Needed size |
|---|---|---|---|
| `config/` | ~20.6 MB | 6 files + 1 empty dir | ~1.45 MB |
| `data/` | ~399.7 MB | 3 files | ~340.9 MB |
| `results/` | ~4,494.9 MB | folder skeleton only, **zero files** | 0 MB |
| **Total** | **~4.9 GB** | | **~342 MB (~93% reduction)** |

`results/` is entirely pipeline output. Every script that writes into it creates its output
directories with `mkdir(parents=True, exist_ok=True)` before writing, so none of the ~350
result files in the zip need to be extracted for the pipeline to run — a clean run from Stage 1
through Stage 3 regenerates the active pipeline outputs. Extract empty `results/` subfolders only if you want the
working tree to look pre-populated; it isn't required.

---

## config/ — extract these files

| File | Why it's required |
|---|---|
| `config/outlook_mappings_master.xlsx` | The core editable mapping workbook. Read by Stage 1, Stage 3, the optional review workflows, and most `mapping_tools/*` scripts. |
| `config/master_config.xlsx` | `FALLBACK_WORKBOOK_PATH` in `build_energy_balance_relationships.py` (Stage 1). |
| `config/mapping_issue_exception_sets.xlsx` | `EXCEPTION_WORKBOOK_PATH` in `codebase/mapping_issue_exceptions.py`, used by mapping QA and several `mapping_tools/*` scripts. |
| `config/source_branch_fallback_rules.csv` | `SOURCE_BRANCH_FALLBACK_RULES_PATH`, read during LEAP→ESTO conversion (`data_convert` stage). |
| `config/all_demand_aggregated_components.json` | `ALL_DEMAND_COMPONENTS_PATH`, same conversion step. |
| `config/common_esto_label_overrides.csv` | `COMMON_ESTO_LABEL_OVERRIDES_PATH`, read in Stage 2 (`build_common_esto_structure.py`). |

## config/ — extract as an empty folder only (no files)

| Folder | Why |
|---|---|
| `config/archive/` | Only used as a **write** target (`ARCHIVE_DIR`) by explicit apply scripts (`apply_display_name_updates.py`, `apply_duplicate_mapping_removal.py`, `apply_subtotal_mismatch_review.py`, `apply_subtotal_mismatch_source_flip.py`, `apply_subtotal_updates.py`) when they back up the workbook before editing it. None of the ~80 archived `.xlsx` snapshots in the zip (`outlook_mappings_master.before_*`, `.maintenance_run_*`, etc.) are read by anything — they're historical backups only. Safe to leave out entirely; an approved apply run will start a fresh archive history. |

## config/ — not needed at all (unreferenced anywhere in `codebase/`)

Confirmed via grep across every `.py` file — none of these paths appear as a load target:

- `config/subtotal_labels/subtotal_labels.csv` (and the `config/subtotal_labels/` folder)
- `config/leap_results_expected_sheets.json`
- `config/mapping_coverage_gaps.csv`
- `config/missing_zero_branch_mapping_candidates.xlsx`
- `config/esto_external_definition_authority_working_set.xlsx` (a copy also sits unused in `config/archive/`)
- `config/inverted_conservation_target_aliases.json` / `config/inverted_conservation_target_variants.json` — used only by `inverted_conservation_validation.py`, which is a standalone QA script, not imported by `run_mapping_pipeline.py`. Skip unless you plan to run that check specifically.
- `config/E0E85740`, `config/E2F1A260`, `config/6AC9DA10` — orphaned binary blobs (zip/xlsx signature, hex filenames, likely Office crash-recovery temp files). Not referenced anywhere. Safe to drop.
- `config/outlook_mappings_master no ownuse.xlsx` — a one-off variant, not a script input.

---

## data/ — extract these files

| File | Why it's required |
|---|---|
| `data/00APEC_2025_low_with_subtotals.csv` | Primary ESTO source table (`ESTO_CSV_PATH`) — `data_convert`, Stage 3, and optional review workflows. |
| `data/00APEC_2024_low_with_subtotals.csv` | Secondary ESTO vintage checked by the optional missing-ESTO-row review. It is not required for a normal Stage 1–3 run. |
| `data/merged_file_energy_ALL_20251106.csv` | 9th Outlook source table (`NINTH_CSV_PATH`) — `data_convert`, Stage 3, and optional review workflows. This is the single largest required input (~288 MB). |

## data/ — not needed

- `data/archive/leap balances exports/...` (all of it, including `02_BD` and `20_USA` subfolders) — per `README.md` and `leap_balance_export_resolver.py`, raw LEAP exports are owned by the sibling `leap_initialisation` repo; this local copy is explicitly "legacy/reference only and is not selected by the pipeline."
- `data/merged_file_energy_00_APEC_20251106.csv` — not referenced anywhere in `codebase/`.
- `data/usa_leap_balance_long.csv` — only a legacy fallback (`LEGACY_LEAP_DATA_PATH`) used by `build_dataset_tree_structure.py` if the regenerated `results/mapping_relationships/raw_leap_results.csv` is missing. Not needed if the pipeline is run end-to-end (Stage `leap_parse` produces that file from the sibling repo's exports).
- `data/README.md` — documentation only, not a script input (harmless to keep if you want the notes, but not required for the pipeline to run).

---

## results/ — extract as empty folder skeleton only (no files needed)

Every file under `results/` in the zip (`common_esto/`, `mapping_relationships/`, `tree_structure/`,
`maintenance/`, `logs/`, `mapping_graph_index/`, `for_colleagues/`, and the duplicate top-level
`missing_mapped_esto_rows/`) is produced by running `codebase/run_mapping_pipeline.py`. None of
it is read as an input by any pipeline stage except within the same run (e.g. Stage `leap_parse`
writes `raw_leap_results.csv`, which `data_convert`/Stage 3 then read back — both steps run in
the same pipeline invocation). If you extract nothing under `results/`, a full pipeline run
(`python codebase/run_mapping_pipeline.py`) recreates all of it, including the ~630 MB and
~1.46 GB single files (`results/mapping_relationships/ninth_source_to_esto_component_lineage.csv`,
`results/tree_structure/source_parent_anchor_validation.csv`) that account for most of the zip's
4.5 GB `results/` weight.

If you want a pre-populated working tree without a full pipeline re-run (e.g. to inspect existing
outputs immediately), the smallest useful subset would be just the primary comparison outputs
rather than logs/diagnostics/backups:

- `results/common_esto/common_esto_comparison_data.csv`
- `results/common_esto/common_esto_rows.csv`
- `results/mapping_relationships/energy_balance_relationships.csv`

...but this is optional convenience, not a workflow requirement — recommend skipping entirely
for the repo slim-down goal.

---

## Auto-created folders — confirmed

Every folder this plan says to leave empty (`config/archive/`, all of `results/` and its
subfolders) is created on demand by the code itself, via `.mkdir(parents=True, exist_ok=True)`
immediately before the relevant write (checked across all 88 `mkdir` call sites in `codebase/`).
You do not need to pre-create any of these directories — a fresh clone with just the required
`config/` files and `data/` files, and no `results/` folder at all, is sufficient; running
`python codebase/run_mapping_pipeline.py` builds the rest. Only `config/` and `data/` themselves
need to genuinely pre-exist with content, since those are read, not written.

## Summary of clutter to leave out of the repo entirely

- `config/archive/` contents — ~80 historical `.xlsx` backup snapshots (keep the empty folder only).
- The 6 orphaned/unreferenced `config/` files listed above, including 3 unidentified hex-named binary blobs.
- `data/archive/leap balances exports/` — owned by the sibling `leap_initialisation` repo, not this one.
- `data/merged_file_energy_00_APEC_20251106.csv`, `data/usa_leap_balance_long.csv` — unused/legacy.
- All of `results/` (~4.5 GB) — fully regenerated by the pipeline; extracting it just to delete it again on the next run is pure waste.
