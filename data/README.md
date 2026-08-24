# `data/` — navigation guide

Only `data/README.md` (this file) and any `**/README.md`/`**/.gitkeep` are git-tracked (see
`.gitignore`: `data/*` then explicit exceptions). Everything else here is restored from a shared
archive/zip, not from git.

## Portable Data Bundle

**Bundle creation and installation are coordinated with the sibling
`leap_initialisation` repository.** Clone both repositories beside each other
before running either bundle script: `.../leap_mappings` and
`.../leap_initialisation`. Running `scripts/create_data_bundle.py` in either
repository deliberately rebuilds both bundles, so mapping inputs and
initialisation inputs are refreshed at the same time. The script stops with a
clear error if the sibling checkout is missing.

Each repository receives its own dated, commit-labelled ZIP under
`data_bundles/`. This repository's ZIP contains the source files listed below;
tracked mapping configuration and generated `results/` files are deliberately
excluded.

After cloning both repositories, place the matching ZIP in each repository's
`data_bundles/` folder and run `scripts/extract_data_bundle.py` from either
checkout. It deliberately installs both bundles. The extractor validates each
manifest and ZIP contents, refuses unsafe paths, and does not overwrite
different local files unless `ALLOW_OVERWRITE` is deliberately changed to
`True`. The ZIPs are ignored by Git and are intended to be shared separately
through restricted storage such as Google Drive.

### Publication checklist

When publishing a code update that changes bundled inputs or their bundle
contract (normally alongside the Git push), rebuild and validate this ZIP,
upload it to the restricted Google Drive data-bundles folder, then move the
superseded ZIP for this repository into that folder's `archive/` subfolder.
Keep the newest verified ZIP in the top-level folder; do not delete historical
bundles.

**Note:** an earlier version of this file described a much larger set of files and workflow
scripts (`codebase/industry_workflow.py`, `full model export.xlsx`, per-sector LEAP import
templates, etc.) that no longer match the current pipeline — none of those files or scripts exist
in this repo any more (verified 2026-07-23). That old content is available via `git log --
data/README.md` if useful for archaeology, but don't treat it as current; this replaces it.

## Required to run the pipeline

| File | Used by |
|---|---|
| `00APEC_2025_low_with_subtotals.csv` | Primary ESTO source table — Stage 0, `data_convert`, Stage 3. |
| `00APEC_2024_low_with_subtotals.csv` | Secondary ESTO year, checked by Stage 0 maintenance for missing-mapped-row detection. |
| `merged_file_energy_ALL_20251106.csv` | 9th Outlook source table — Stage 0, `data_convert`, Stage 3. The single largest required input (currently several hundred MB). |
| `esto_extended.csv` | ESTO Extended source used by conversion, hierarchy, and Stage 3. |
| `temp/new leap rows.xlsx` | Maintained LEAP branch inventory used by hierarchy and mapping refresh checks. |

The default `codebase/run_mapping_pipeline.py` run uses the committed mapping
configuration, parses the bounded `20_USA` smoke economy, and skips the very
large recursive/anchor audit. Pass `--leap-economies all` for an intentional
multi-economy refresh after checking memory. Maintainers run
`--stages generate,...` only after editing mapping inputs, and opt into the
potentially 100+ GB audit with `--deep-validation` when the available disk and
run time have been checked.

## Not needed for this repo's pipeline

- `archive/leap balances exports/` — raw LEAP exports are owned by the sibling
  `leap_initialisation` repo; this local copy is legacy/reference only (see the root
  `README.md`'s "Current Inputs" section and `codebase/utilities/leap_balance_export_resolver.py`).
- `merged_file_energy_00_APEC_20251106.csv`, `usa_leap_balance_long.csv` — not referenced by any
  current script (the latter is only a legacy fallback in `build_dataset_tree_structure.py`).

## Full detail

See `docs/repo_data_slimdown_plan.md` for the complete file-by-file breakdown and reasoning.
