# Cross-repository handover index

> **Dated audit snapshot.** The maintained start page is
> [`handover/README.md`](handover/README.md), and the maintained producer/
> consumer contract is
> [`handover/cross_repository_data_contracts.md`](handover/cross_repository_data_contracts.md).
> This file remains as the evidence snapshot that initiated that documentation
> set.

**Snapshot date:** 2026-07-28
**Last verified:** 2026-07-28 — schemas read from current output files; path
constants read from `leap_dashboard/codebase/common_esto_dashboard_workflow.py`;
git state read directly from each repository.
**Owner of this document:** `leap_mappings`

This index defines who owns what across the three active repositories, which
files cross repository boundaries, what those files contain, the order in which
they must be refreshed, and who owns each failure mode. It is the companion to
[`work_queue.md`](work_queue.md) (queue item MAPQ-015) and is the reference the
Week 4 handover rehearsal validates against.

Anything not listed here does **not** cross a repository boundary and should be
treated as internal to its repository.

## 1. Repository ownership

| Repository | Owns | Must not own |
|---|---|---|
| `leap_mappings` (this repo) | Mapping semantics: the canonical workbook, rollup rules, graph partitioning, comparison scopes, component membership, and the Common ESTO published dataset and its contract. | Dashboard presentation; LEAP area initialisation and import-ID integrity. |
| `leap_dashboard` | Presentation of the Common ESTO comparison: chart routing, page layout, series config, rendering, publication readiness. | Mapping logic. Its own `AGENTS.md` forbids reproducing mapping logic or inferring hierarchy from display labels. |
| `leap_initialisation` | LEAP area initialisation, baseline seeds, supply/transformation/transfers reconciliation, LEAP import/export integrity, and the LEAP balance exports themselves. | Mapping semantics. Its `AGENTS.md` routes mapping-only maintenance here. |

Frozen / retired, not part of the handover: `leap_utilities` (original
workspace), `leap_dashboard_legacy` (visual comparison only).

**Canonical rule:** `leap_mappings` is the single source of mapping truth. The
other two repositories reference it and must not duplicate its logic. When a
mapping concept is ambiguous, `docs/mappings_system.md` in this repository wins.

## 2. Files that cross repository boundaries

### 2.1 Produced by `leap_mappings`, consumed by `leap_dashboard`

The dashboard resolves this repository through `LEAP_MAPPINGS_ROOT`
(default `../leap_mappings`) in
`leap_dashboard/codebase/common_esto_dashboard_workflow.py`. Every path below is
a hard dependency of the dashboard workflow.

| Produced file | Dashboard constant | Purpose |
|---|---|---|
| `results/common_esto/common_esto_comparison_data.csv` | `DEFAULT_INPUT_PATH` | Long-format comparison values. The dashboard's primary input. |
| `results/common_esto/common_esto_rows.csv` | `COMMON_ESTO_ROWS_PATH` | Common-row structure and component membership. |
| `results/mapping_relationships/esto_results_exact_rows.csv.gz` | exact-rows path | ESTO exact rows, gzip-compressed. |
| `results/mapping_relationships/esto_extended_results_exact_rows.csv.gz` | extended exact-rows path | ESTO Extended exact rows, gzip-compressed. |
| `config/all_demand_aggregated_components.json` | components path | Declared membership of `All demand aggregated`. Config, not output — the dashboard reads this repository's config directly. |
| `codebase/mapping_tools/source_branch_preflight.get_demand_sectors_without_detail` | imported via `sys.path` | The dashboard **imports live Python from this repository**. Signature changes are breaking changes. |

Two coupling points deserve explicit attention at handover:

- The dashboard inserts `LEAP_MAPPINGS_ROOT` into `sys.path` and imports
  `codebase.mapping_tools` directly. This is a code-level dependency, not just
  a data one — renaming or moving a mapping module breaks the dashboard.
- The dashboard can **write into this repository**: its fast-path refresh
  recomputes outputs into `leap_mappings/results/common_esto/`. A dashboard run
  can therefore invalidate a mapping baseline. Do not run a dashboard refresh
  during MAPQ-005 baseline production.

`leap_dashboard/codebase/common_esto_dashboard_mapping_diagnostics.py`
additionally reads QA artifacts from this repository by design (its module
docstring says so). Those artifacts are diagnostic, not contractual — treat
their schemas as unstable until MAPQ-012 decides what belongs in mapping output
versus dashboard presentation.

### 2.2 Produced by `leap_initialisation`, consumed by `leap_mappings`

| File | Consumer status |
|---|---|
| `leap_initialisation/data/leap balances exports/{00_APEC,01_AUS,02_BD,12_NZ,20_USA}/` | **Not yet a wired contract.** `leap_mappings` currently carries only a partial local copy (`data/archive/leap balances exports/` with `02_BD` and `20_USA`, plus `data/usa_leap_balance_long.csv`). MAPQ-019 must decide whether this repository reads the sibling tree directly or receives a published extract. Until then this is an undeclared dependency. |

### 2.3 Shared reference, no code coupling

| File | Owner | Used by |
|---|---|---|
| `leap_dashboard/config/common_esto_dashboard/series_config.json` | `leap_dashboard` | Authoritative economy code/name list for all three repositories. Uses compact keys (`02BD`); workflow inputs use underscore-normalized codes (`02_BD`). |
| `leap_mappings/docs/mappings_system.md` | `leap_mappings` | Required reading before either sibling changes assumptions about scopes, hierarchy, component membership, rollups, or generated labels. |
| `C:\Users\Work\.codex\AGENTS_LEAP_EXPORT.md`, `AGENTS_BALANCE_TABLES.md` | outside all repos | Structural definitions referenced by `leap_mappings/AGENTS.md`. **These live outside version control and would not survive a clean-checkout handover** — see §6. |

## 3. Schemas of the published files

Column lists below were read from the current files on 2026-07-28. They are
descriptive of today's output; MAPQ-003 (`common_esto_output_contract.py`, in
the `codex/output-contract-phase-2` worktree) is what makes them enforced.

### `common_esto_comparison_data.csv` — long comparison values

```text
comparison_scope, source_system, economy, scenario, year,
common_flow_code, common_flow_name, common_flow_label,
common_product_code, common_product_name, common_product_label,
common_row_id, common_row_basis,
is_exact_row, requires_rollup, is_non_expanding_rollup,
non_expanding_rollup_id, rollup_mode,
source_aggregate_labels, source_aggregate_group_ids,
value
```

Key: (`comparison_scope`, `source_system`, `economy`, `scenario`, `year`,
`common_row_id`). `source_system` distinguishes the compared sources and must
never be collapsed — preserving it is exactly what the ESTO rollup
source-identity work protects.

### `common_esto_rows.csv` — common-row structure and components

```text
comparison_scope, common_structure_version, common_row_id,
common_flow_code, common_flow_name, common_flow_label,
common_product_code, common_product_name, common_product_label,
component_esto_flow, component_esto_product,
component_flow_code, component_flow_name,
component_product_code, component_product_name,
component_sign, is_exact_row, requires_rollup,
is_non_expanding_rollup, non_expanding_rollup_id, rollup_mod…
```

One row per (common row × component). `common_structure_version` is the
compatibility handle the dashboard should check before assuming a layout.
`component_sign` carries the sign convention: positive = output from a flow,
negative = input to a flow.

### `esto_results_exact_rows.csv.gz` and `esto_extended_results_exact_rows.csv.gz`

```text
economy, esto_flow, esto_product, year, value,
source_system, scenario, non_expanding_rollup_id
```

Identical schema for both. Gzip-compressed since `34858fe` — consumers must
read them as gzip, not plain CSV. `source_system` plus `non_expanding_rollup_id`
together identify which rollup produced a row; duplicating a row across source
systems is the defect class the MAPQ-004 guard exists to catch.

### `common_esto_comparison_wide.csv` — wide pivot

```text
comparison_scope, economy, scenario, product, flow, is_subtotal,
1980 … 2070   (year columns as strings)
```

### `common_esto_output_status.csv` — run and validation status

```text
run_id, run_timestamp_utc, record_type, artifact_name,
validation_name, validation_axis, source_system, status,
checks_performed, eligible_parent_count, mismatch_count, reason,
current_output_file, output_path, output_mtime_ns,
input_path, input_mtime_ns, input_mtime_utc, input_size_bytes,
raw_check_row_count, raw_mismatch_row_count, validation_summary_path,
comparison_scope, eligible, passed, failed, skipped
```

This is the file to read first when judging whether a run is usable. It records
which artifact is current, whether the canonical file or a `_rebuilt` fallback
was written, and per-validation pass/fail counts. **`current_output_file` is
the authoritative answer to "which CSV should I read"** — do not infer it from
filenames.

## 4. Refresh order

Refresh strictly in this order. Each step's inputs are the previous step's
outputs.

1. **Close the mapping workbook in Excel.** An open workbook leaves
   `config/~$outlook_mappings_master.xlsx` and forces `_rebuilt` fallback
   writes, producing a run whose canonical outputs are stale.
2. **`leap_initialisation`** — refresh LEAP balance exports if the LEAP model
   changed. Only needed when LEAP-side data must move; otherwise skip.
3. **Optional `leap_mappings` review** — run
   `codebase/hierarchy_subtotal_contract_workflow.py` when structural meaning
   changes, or `codebase/missing_mapped_esto_rows_workflow.py` when reviewed
   ESTO category coverage changes.
4. **`leap_mappings` Stages 1–3** — `codebase/run_mapping_pipeline.py`:
   `run_stage_1` → `run_stage_2` → `run_leap_parse` →
   `run_leap_to_esto` → `run_ninth_to_esto` → `run_esto_exact_rows` →
   `run_esto_extended_exact_rows` → `run_data_convert` → `run_stage_3`.
   Log: `results/logs/mapping_pipeline.log`.
5. **Verify** `results/common_esto/common_esto_output_status.csv` before
   publishing anything downstream.
6. **`leap_dashboard`** — `codebase/common_esto_dashboard_workflow.py`, then the
   focused tests, the `20_USA` fixture render, and the publication-readiness and
   page-noise scripts.

Never run steps 4 and 6 concurrently: the dashboard fast path writes into
`leap_mappings/results/common_esto/`.

Use `C:\Users\Work\miniconda3\python.exe` throughout. The repository `.venv` is
WSL-created and unusable from Windows shells; PowerShell's `python`/`py`
aliases swallow output and report unreliable exit codes.

## 5. Failure ownership

| Symptom | Owner | First check |
|---|---|---|
| Dashboard input file missing or unreadable | `leap_mappings` | `common_esto_output_status.csv` → `current_output_file`; then whether the workbook was locked during the run. |
| Dashboard reads a `_rebuilt` file / values look stale | `leap_mappings` | Excel lock on the master workbook during the run. Re-run with the workbook closed. |
| Comparison row duplicated across source systems | `leap_mappings` | `source_system` / `non_expanding_rollup_id` in the exact-rows files. This is the MAPQ-004 guard's failure class. |
| A LEAP branch or fuel is unmapped or wrongly mapped | `leap_mappings` | `config/outlook_mappings_master.xlsx`, then `config/mapping_issue_exception_sets.xlsx` and QA/decision history. A formerly rejected row is not restored merely because it is absent. |
| Chart routing, page layout, or label presentation is wrong | `leap_dashboard` | `config/common_esto_dashboard/`. Do not fix by changing mapping labels. |
| A category exists in mapping output but the dashboard cannot place it | joint — escalate via MAPQ-021 | Component membership is the source of truth for generated categories; the dashboard must not infer hierarchy from display labels. |
| LEAP import IDs, baseline seeds, or supply reconciliation are wrong | `leap_initialisation` | Its own `docs/work_queue.md`. |
| Mapping import from the dashboard fails (`ImportError`) | `leap_mappings` | A mapping module was renamed or moved; the dashboard imports `codebase.mapping_tools` directly. |
| Economy code mismatch (`02BD` vs `02_BD`) | `leap_dashboard` owns the list | `series_config.json`. `02_BD` is Brunei Darussalam, not Bangladesh. |

## 6. Handover risks recorded by this index

1. **Both sibling repositories are single-point-of-failure local checkouts.**
   `leap_dashboard` is 55 commits ahead of its remote; `leap_initialisation` is
   142 ahead. 197 commits of work exist only on this machine.
   **Delegated 2026-07-28** to the handover audits running inside those
   repositories — see MAPQ-025, which records the evidence but does not track
   the work. This risk is retired when those audits report back, not by any
   action in `leap_mappings`. Until then, treat every schema in §3 as depending
   on two consumers whose only copy is local. This audit does not push them.
2. **`leap_mappings` local `master` is 7 commits ahead of `origin/master`**,
   including the canonical workbook merge and this audit. Tracked as MAPQ-002.
3. **Two structural reference documents live outside version control**
   (`C:\Users\Work\.codex\AGENTS_LEAP_EXPORT.md` and `AGENTS_BALANCE_TABLES.md`).
   A clean-checkout handover would not include them. Either vendor them into
   `docs/` or record them as an external prerequisite before MAPQ-022.
4. **The LEAP balance export dependency is undeclared** (§2.2). MAPQ-019.
5. **The dashboard can overwrite mapping outputs** through its fast-path
   refresh. Until MAPQ-003 lands a contract with manifest hashes, there is no
   automatic protection against a dashboard run invalidating a baseline.
6. **Nine worktrees in `leap_initialisation`**, three at the initial commit,
   plus two detached `.codex` worktrees. Stray worktrees make it unclear which
   checkout is authoritative. MAPQ-025.

## 7. Verification for the Week 4 rehearsal

The rehearsal (MAPQ-022) validates this index by doing, in order:

1. Clone `leap_mappings` fresh; restore inputs from documentation alone.
2. Run the refresh order in §4, steps 1 and 3–5.
3. Confirm every file in §2.1 exists with the schema in §3.
4. Point `leap_dashboard` at the fresh checkout via `LEAP_MAPPINGS_ROOT` and
   render the `20_USA` fixture.
5. Record every step that required knowledge not present in this index or the
   MAPQ-014 document set. Each one is a defect to fix before handover.
