# AGENTS.md

These are project-level instructions for Codex (and similar agents).

## Repository routing

- This repo is the active home for LEAP mapping maintenance.
- Use this repo for `config/outlook_mappings_master.xlsx`, canonical mapping helpers, mapping checks, mapping conversion tools, and `codebase/outlook_mapping_maintenance_workflow.py`.
- `config/leap_mappings.xlsx`, `config/master_config.xlsx`, and `codebase/leap_mapping_refresh_workflow.py` are legacy references unless a task explicitly asks for old-workbook maintenance.
- `C:\Users\Work\github\leap_utilities` is the old workspace where this mapping code was built. Do not use `leap_utilities` for active mapping work anymore unless the user explicitly asks for legacy cleanup or comparison.
- For LEAP area initialisation and supply reconciliation work, use `C:\Users\Work\github\leap_initialisation` instead.

## Cross-repo access

In Claude Code sessions all three repos are configured as additional working directories and are directly accessible:

- `C:\Users\Work\github\leap_initialisation`
- `C:\Users\Work\github\leap_mappings` (this repo)
- `C:\Users\Work\github\leap_dashboard`

Agents can read, search, and edit files in any of them. The codebase for the mapping pipeline lives in `codebase/` within this repo.

## Rebuild scope and canonical status

This repository is being rebuilt. All new mapping code goes here, not in `leap_utilities`.

This repo is the canonical mapping source for the APERC project. Other repos should reference it, not duplicate its logic:

- `leap_initialisation` uses these mappings when reconciling LEAP outputs against supply baselines.
- `leap_dashboard` uses the downstream common ESTO comparison data to generate its charts.

Active documentation being developed:

- `docs/mappings_system.md` — the canonical reference for the mappings system design, pipeline stages, rollup rules, graph partitioning, and naming conventions.
- `docs/special_rules_and_design_decisions.md` — human-selected rules, provisional assumptions, and unresolved semantic decisions found during end-to-end runs.

## When editing draw.io diagrams

- See `AGENTS_DRAWIO.md` for draw.io-specific requirements.

## Small guide for humans

- Put instructions here that you want Codex to follow every time it edits this repo.
- Keep rules short and specific; avoid large, complex policies.
- Do not use this repo for LEAP dashboard implementation or dashboard template edits. Use `C:\Users\Work\github\leap_dashboard` for LEAP dashboard work unless the user explicitly asks for shared `leap_utilities` code changes.
- For file-specific rules, include path globs like `docs/leap-system*.drawio`.
- Workflow-file pattern for small projects: create/maintain one `*_workflow.py` entry script per task area and make it notebook-safe.
- In workflow scripts, always define `REPO_ROOT = Path(__file__).resolve().parents[1]` (or correct repo level), add it to `sys.path` only if missing, and resolve all relative paths via a `_resolve()` helper against `REPO_ROOT`.
- Why: notebooks run with arbitrary CWD, so this prevents `FileNotFoundError` and import failures.
- Normalize user-provided path strings by replacing `\\` with `/` before `Path(...)` when needed.
- When updating transfer category mappings, re-run `codebase/scrapbook/transfers_mapping_exploration.py`
  and paste the printed `TRANSFER_PROCESS_CONFIG` into `codebase/transfers_workflow.py`.
- When referring to files in replies, prefer paths relative to the active repo root
  (for example, `outputs/example.csv`) instead of absolute `/mnt/c/...` or
  `C:\...` paths. Use absolute paths only for files outside the repo or when needed
  to disambiguate.

## Converting documentation to Word

`scripts/convert_docs.py` converts Markdown files in `docs/` to `.docx` using Pandoc.
It fixes encoding mojibake, renders Mermaid diagrams to PNG, and suppresses auto-captions.

```powershell
# Convert all .md files individually
python scripts/convert_docs.py

# Combine the main docs into one Word document
python scripts/convert_docs.py --combine

# Convert only a subdirectory
python scripts/convert_docs.py --docs-dir docs/transformation_supply_docs
```

Output goes to `docs/docx/`. Mermaid PNGs go to `docs/docx/mermaid/`.

Requirements (one-time install):

- `winget install JohnMacFarlane.Pandoc`
- `npm install -g @mermaid-js/mermaid-cli`

## Output clarity

- Keep output folders small and easy to inspect.
- Prefer a few clearly named primary outputs.
- Do not create extra files unless they serve a clear human-facing purpose.
- Keep primary outputs narrow: include important columns only.
- Put debug-heavy or trace-heavy artifacts in `extra_detail` or `diagnostics`, not beside the main outputs.
- Make sure there is a clear file for inspecting errors when needed.

## LEAP mapping maintenance

- Removed rows in `leap_combined_esto` and `leap_combined_ninth` are often deliberate guardrails, not obsolete data.
- Many removed rows are rows that would create many-to-many mappings if active, usually because LEAP, ESTO, and 9th Outlook have different levels of detail.
- When checking mapping gaps, treat `counterpart_presence_state == removed_only` as unavailable rather than as a missing row to restore.
- Before reactivating or adding rows, check whether the change would create a many-to-many relationship and prefer the narrowest mapping needed for the workflow.

## Computer-generated mapping candidates

- Generate mapping suggestions by inferring the two axes independently: LEAP branch or 9th sector to ESTO flow, and LEAP fuel or 9th fuel to ESTO product. Combine the axes only for source pairs observed with non-zero relevant data.
- Treat every generated candidate as review-only. Never write candidates into `outlook_mappings_master.xlsx` automatically.
- Only complete, non-zero, high-confidence candidates with no existing source-pair target belong in `highly_recommended_mapping_candidates.csv` and the two candidate QA files. These rows are copy-ready because both axes are derived consistently from existing mappings; paste them into the named sheet and rerun maintenance and Stages 1-3.
- Keep incomplete, zero-only, ambiguous, or one-axis-only findings in their original QA files. Do not pad the candidate files with unresolved rows.
- Candidate outputs must include the destination mapping sheet, copy-ready source and target columns, support counts, axis confidence, ambiguity/cardinality warnings, and the source-data evidence that made the pair relevant.
- Do not invent an ESTO pair for an unmapped LEAP branch when only one axis can be inferred. Leave it as an unresolved review row.
- Before accepting a candidate, check hierarchy/subtotal scope, `esto_external_definition_authority_working_set.xlsx`, existing targets for the source pair, and raw/after-rollup cardinality. Rerun the mapping pipeline after reviewed rows are added.

## LEAP Export File Structure

- See `C:\\Users\\Work\\.codex\\AGENTS_LEAP_EXPORT.md` for LEAP export structure requirements.

## Balance Table Structures (ESTO vs 9th)

- See `C:\\Users\\Work\\.codex\\AGENTS_BALANCE_TABLES.md` for balance table structure details.

These two balance tables are the core inputs for `codebase/transformation_analysis_workflow.py`.
Keep this structure in mind when adding new transformations or debugging data issues.

### 9th structure (sector/fuel hierarchy)

- Source file: `data/merged_file_energy_ALL_20251106.csv` (loaded as "9th" in the script).
  - Use `data/merged_file_energy_ALL_20251106.csv` and `data/merged_file_energy_00_APEC_20251106` when you need to exactly match 9th edition projections.
- Key columns:
  - `scenarios`, `economy`
  - Sector hierarchy: `sectors`, `sub1sectors`, `sub2sectors`, `sub3sectors`, `sub4sectors`
  - Fuel hierarchy: `fuels`, `subfuels`
  - Subtotal flags: `subtotal_layout`, `subtotal_results`
  - Year columns (as strings before normalization): `1980` ... `2070`
- Coding style:
  - Codes use underscores, e.g., `09_06_gas_processing_plants`, `10_01_03_liquefaction_regasification_plants`.
  - `"x"` means "not used" for a given hierarchy level.
- Usage in transformations:
  - Supports detailed subsector selection (e.g., LNG uses `sub2sectors` and `subfuels`).
  - Filtered to `scenarios == reference` before calculations.
- Subtotals are removed using the subtotal mapping in `config/ESTO_subtotal_mapping.xlsx`.

### ESTO (Matt) structure (flow/product table)

- Source file: `data/00APEC_2024_low.csv` (loaded as "ESTO (Matt) data" in the script).
- Key columns:
  - `economy`
  - `flows` (balance rows like production, transformation, own use, losses)
  - `products` (fuel/product codes)
  - Year columns: `1990` ... `2022`
- Coding style:
  - Economy codes are compact (e.g., `01AUS`), normalized to `01_AUS` to align with 9th.
  - Flow codes match the 09/10 transformation and loss lists (e.g., `09.08.01 Coke ovens`, `10.01.05 Coke ovens`).
- Usage in transformations:
  - Used for most transformation flows when sector detail is not required.
  - No `sub*sectors` columns are present, so selection is done via `flows` and `products`.

### Shared sign conventions (both tables)

- Positive values represent outputs from a transformation flow.
- Negative values represent inputs to a transformation flow (feedstock or auxiliary fuels).
- Loss/own-use flows are treated as auxiliary fuel use (absolute values are used in ratios).

## Baseline Seed Validation (`patch_baseline_seeds.py`)

`validate_seed_files()` checks all `leap_import_baseline_seed_*.xlsx` files against the full
model export template.  Two ignore sets control which rows are silently skipped:

- **`VALIDATION_IGNORE_PREFIXES`** — branch path *prefixes* for sectors known to be absent from
  the template (e.g. `Transformation\Biofuels processing\` — confirmed zero energy in ESTO).
- **`VALIDATION_IGNORE_FUEL_NAMES`** — final path *segments* that are 9th-edition aggregate
  category labels and are not real LEAP branches in any sector.  Current members:
  `Biomass`, `Coal`, `Gas`, `Others`, `Municipal solid waste non and renewable`.
  Note: `Solar` is **not** in this set — unallocated solar codes (`12_solar`,
  `12_solar_unallocated`) are remapped to `Solar nonspecified` by
  `_safe_power_interim_display_label()` before reaching the output filter.

When the aggregated demand workflow or another source emits rows for a fuel that isn't a real
LEAP branch and the validation flags it as "unknown path", first check whether the fuel name
belongs in `VALIDATION_IGNORE_FUEL_NAMES` before treating it as a genuine error.  If the fuel
*should* exist in the model, investigate the aggregated demand workbook or the relevant
workflow instead.

## Python Environment

- This repo's `.venv` is a WSL-created venv (`home = /usr/bin` in `pyvenv.cfg`) and cannot be used from Windows shells (PowerShell, cmd, or the Bash tool when running in a Git-Bash context on Windows).
- Use `/c/Users/Work/miniconda3/python.exe` for all Python scripts run via the Bash tool (Git-Bash on Windows).
- Do **not** attempt to activate `.venv/bin/activate` from the Bash tool — it will fail silently or error.
- Do **not** use PowerShell's `python` or `py` aliases — output is swallowed and exit codes are unreliable.
