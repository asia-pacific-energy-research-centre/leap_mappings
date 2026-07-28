# Cross-repository agent operations guide

**Evidence snapshot:** 2026-07-28

**Audience:** coding agents and maintainers running or changing workflows
**Detail level:** Level 3

Read every applicable `AGENTS.md`, the controlling work queue, and the
repository-owned guide before acting. This guide does not authorize workbook
changes, LEAP imports, publishing, or long pipeline runs; those actions still
need to be within the user’s request.

## 1. Pre-flight safety

For each repository:

```powershell
git status --short --branch
git worktree list
git branch --no-merged
git log -8 --oneline
```

Then:

1. classify every existing dirty path;
2. identify other active worktrees/processes touching the same files;
3. close Excel before reading or writing canonical workbooks;
4. treat `~$*.xlsx`, hex-named Office recovery files, and “todo/copy” workbook
   variants as user state—not cleanup targets;
5. record the current commit, mapping workbook state, input vintage, and run
   label before a run;
6. use narrow staging (`git add <exact files>`), never `git add .`;
7. do not run mapping Stage 3 and the dashboard fast path concurrently.

Current dirty paths that pre-date this handover include mapping code/workbook/
notes/noise and dashboard diagnostics code/tests. Preserve them.

## 2. Environment and notebook setup

The user’s preferred execution surface is Jupyter with `#%%` cells and
editable constants. Use the Windows interpreter:

```text
C:\Users\Work\miniconda3\python.exe
```

Do not use a repository `.venv` from PowerShell; the documented `.venv` is
WSL-created. Do not rely on PowerShell’s `python` or `py` aliases.

Notebook setup pattern:

```python
#%%
from pathlib import Path
import os
import sys

REPO_ROOT = Path(r"C:\Users\Work\github\leap_mappings")
os.chdir(REPO_ROOT)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

#%%
```

Use the matching repository root for initialisation or dashboard work. Keep the
final `#%%` so the whole file can be run in one pass.

Windows-only dependencies:

- LEAP COM/API and `win32com`;
- the installed LEAP application and target area;
- LEAP exports/templates and Excel-compatible workbook handling.

Mapping and dashboard CSV processing can run without COM. Initialisation’s
ordinary workbook-generation path also does not require live COM unless the
specific LEAP fill/scrape toggle is enabled.

## 3. Workflow inventory

| Workflow | Owner | Entry point | Inputs | Outputs | Mutates canonical data? | Validation | Downstream |
|---|---|---|---|---|---|---|---|
| mapping maintenance | mappings | `codebase/archive/outlook_mapping_maintenance_workflow.py` | workbook, sources, template/export, exceptions | preview and QA/tree files | default no; reviewed helpers can | maintenance summary and QA | Stage 1/reviewer |
| mapping pipeline | mappings | `codebase/run_mapping_pipeline.py` | workbook, ESTO/9th/LEAP | relationships, Common ESTO, values, lineage/status | generated outputs only | Stage 0–3 QA | dashboard |
| Common ESTO fast path | mappings | `codebase/regen_common_esto_comparison_fast_path_workflow.py` | cached converted values and rows | final long/wide/status | overwrites generated outputs | no deep validation | dashboard |
| supply reconciliation | initialisation | `codebase/supply_reconciliation_workflow.py` | sources, canonical mappings, templates, optional LEAP results | run-labelled seeds/updates and diagnostics | generated outputs; optional live LEAP fill | preflight, invariants, readiness, conservation | LEAP/human |
| seed patch | initialisation | `codebase/functions/patch_baseline_seeds.py` through orchestrator mode | existing seed and module output | patched seed and validation | generated seed | shared emit-boundary checks | LEAP/human |
| dashboard render | dashboard | `codebase/common_esto_dashboard_workflow.py` | Common ESTO long/wide and config | economy HTML/JS/manifests | generated outputs; optional docs publish | tests/readiness/page noise | browser |
| dashboard all economies | dashboard | `scripts/render_common_esto_dashboard_all_economies.py` | same | 21 economy folders | generated outputs | publication scripts | browser |

## 4. Mapping operations

### 4.1 Canonical run order

In a mappings-root notebook:

```python
#%%
from codebase.run_mapping_pipeline import (
    run_stage_0,
    run_stage_1,
    run_stage_2,
    run_leap_parse,
    run_data_convert,
    run_stage_3,
)

#%%
RUN_STAGE_0 = True
RUN_STAGE_1 = True
RUN_STAGE_2 = True
RUN_LEAP_PARSE = True
RUN_DATA_CONVERT = True
RUN_STAGE_3 = True
LEAP_ECONOMIES = None  # Or an explicit reviewed list such as ["20_USA"].
SKIP_DEEP_VALIDATION = False

#%%
if RUN_STAGE_0:
    run_stage_0()
if RUN_STAGE_1:
    run_stage_1()
if RUN_STAGE_2:
    run_stage_2()
if RUN_LEAP_PARSE:
    run_leap_parse(economies=LEAP_ECONOMIES)
if RUN_DATA_CONVERT:
    run_data_convert()
if RUN_STAGE_3:
    run_stage_3(skip_deep_validation=SKIP_DEEP_VALIDATION)

#%%
```

Do not use `skip_deep_validation=True` for release evidence. It is a test-mode
boundary.

### 4.2 Stage inputs and outputs

| Stage | Key modules | Inputs | Expected success artifacts |
|---|---|---|---|
| 0 | archived maintenance workflow, tree builder, display-name update | canonical workbook, source CSVs, exceptions, model structure | `results/maintenance/maintenance_summary.csv`, tree CSVs |
| 1 | relationship builder, rollup modules | workbook base/rollup sheets | `energy_balance_relationships.csv`, catalogue, QA |
| 2 | Common structure builder, structural resolver | relationships, exclusions, overrides | `common_esto_rows.csv`, map and structural QA |
| LEAP parse | balance export resolver/parser | sibling balance-export tree | `raw_leap_results.csv` |
| convert | LEAP/9th converters and ESTO exact-row selectors | raw sources and mappings | converted source files and compressed lineage |
| 3 | Common structure application and validators | converted values and common rows | comparison long/wide, status, manifest, lineage, validation |

### 4.3 Runtime and monitoring

Observed full Stage 3 on 2026-07-28:

- application: 1,085.7 s;
- recursive validation: 1,113.9 s;
- source-anchor validation: 1,219.2 s;
- total: 3,635.8 s (about 61 minutes).

These are observations, not timeouts. Name any background process after the
actual workflow and keep its command line visible in run notes. Do not kill a
long Stage 3 merely because it is quiet. Inspect `results/logs/mapping_pipeline.log`
and process CPU/command line without modifying outputs.

### 4.4 Workbook and output behavior

- Stage 0 is preview-first. `--apply-maintenance` in the current orchestrator is
  deprecated/no-op; do not claim it mutates the workbook.
- Workbook-changing helper scripts create backups under `config/archive/`.
- Stage 3 can write `*_needs_mapping_review` on application errors.
- Locked CSVs can cause `_rebuilt` outputs.
- `common_esto_output_status.csv/current_output_file` selects the current file.
- The fast path overwrites the long/wide/status outputs and deliberately skips
  maintenance, structure, candidate, tree, and anchor checks.

### 4.5 Mapping release checks

At minimum:

1. confirm Stage 0 summary and actionable QA;
2. confirm relationship/structure files exist and have expected non-empty
   schemas;
3. inspect `common_esto_output_status.csv`;
4. inspect `stage3_run_manifest.json`;
5. review every failed/skipped validation and its reason;
6. inspect source rows missing common maps and material non-zero gaps;
7. confirm no candidate was added automatically;
8. trace at least one changed category through relationship, component, value,
   and lineage files;
9. rerun focused tests for modified modules.

Do not call the pipeline clean because a diagnostic is empty without proving
the file exists, the check ran, and the run IDs match.

## 5. Initialisation operations

Use the repository-owned
`leap_initialisation/docs/handover/supply_reconciliation_agent_guide.md` for the
exact mode/toggle table. The non-negotiable launch rules are summarized here.

### 5.1 Before a long run

1. Read `leap_initialisation/docs/work_queue.md`.
2. Confirm no run is active for the same economy.
3. Inspect JSON locks under the active run’s
   `supporting_files/runtime/economy_locks/`.
4. Never remove a lock until its recorded PID is confirmed dead.
5. Set an explicit dated `RUN_OUTPUT_LABEL` for a retained repeated scope;
   identical `"auto"` scopes resolve to the same label and can collide.
6. Verify `ECONOMIES`, `SCENARIOS`, `RUN_MODE`,
   `CAPACITY_UNMET_PASS_MODE`, preflight toggles, horizon, and live LEAP
   interaction toggles.
7. Verify each real economy resolves its own template.

### 5.2 Jupyter execution

The workflow is designed as a notebook-style script with editable constants.
Review and edit the constants in the file, then use the notebook’s Run All or:

```python
#%%
import runpy
from pathlib import Path

REPO_ROOT = Path(r"C:\Users\Work\github\leap_initialisation")
WORKFLOW_PATH = REPO_ROOT / "codebase" / "supply_reconciliation_workflow.py"

# Review the file's constants before this call.
RESULTS = runpy.run_path(str(WORKFLOW_PATH), run_name="__main__")

#%%
```

Do not edit `ECONOMIES` in a shared working tree while another process is
between launch and late preflight import. The module can be read again under a
second module identity.

After launch, verify the exact process command line, not merely a process name:

```powershell
Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" |
  Select-Object ProcessId, Name, CommandLine
```

Do not poll more often than every 10 minutes. Let the workflow finish.

### 5.3 Run modes and safe rerun boundaries

| Mode/pass | Use | Reads recalculated LEAP results? | Safe reuse boundary |
|---|---|---:|---|
| `baseline_seed` | first full model seed | normally no | source/config/template/run scope unchanged |
| `results_update` | reconcile after LEAP recalculation | yes | balance export and config unchanged |
| `patch_baseline_seeds` | replace one verified module slice | depends on module | existing seed and module source unchanged |
| compressed projection preflight | cheap source/workbook-generation exercise | no live LEAP interaction | diagnostic only |
| compressed results-update preflight | cheap results-update path exercise | compressed inputs | diagnostic only |

Per-economy process-based parallelism exists, but use sequential runs unless
the current documented configuration and merge boundary are understood.
Overlapping economy scopes are prohibited. Live LEAP API imports are never
safe in parallel.

### 5.4 Import gate

Do not import until:

- export-readiness `blocking_failures == 0`;
- non-zero rows have valid IDs;
- duplicate four-part keys are resolved;
- template/fuel catalog coverage is acceptable;
- share groups and expression syntax pass;
- relevant conservation and source-preservation evidence is reviewed;
- run label, source vintage, commit, and template are recorded.

The latest real USA seed on 2026-07-28 has 3,244 blocking readiness findings;
it is evidence that file generation succeeded, not an import-ready example.

### 5.5 Manual LEAP loop

After import:

1. recalculate the correct LEAP area;
2. export Results → Energy Balance in PJ, normally at Level 2 or higher;
3. place the export in the resolver’s canonical economy directory;
4. rerun results-update;
5. compare gap trajectories and readiness/conservation evidence.

A full LEAP balance export can take 3–4 hours. Never confuse that with the
Python workflow time.

## 6. Dashboard operations

### 6.1 Safe render

Set environment variables in the Jupyter kernel before loading the workflow,
because the module executes its bottom run block on import:

```python
#%%
import os
import runpy
from pathlib import Path

REPO_ROOT = Path(r"C:\Users\Work\github\leap_dashboard")

os.environ["COMMON_ESTO_RUN_DASHBOARD_WORKFLOW"] = "1"
os.environ["COMMON_ESTO_UPDATE_DATA"] = "0"
os.environ["COMMON_ESTO_PUBLISH_TO_DOCS"] = "0"
os.environ["COMMON_ESTO_ECONOMIES"] = "20_USA"
os.environ["LEAP_MAPPINGS_ROOT"] = r"C:\Users\Work\github\leap_mappings"

WORKFLOW_PATH = REPO_ROOT / "codebase" / "common_esto_dashboard_workflow.py"
RESULTS = runpy.run_path(str(WORKFLOW_PATH), run_name="__main__")

#%%
```

The economy environment variable is comma-separated when multiple economies
are needed. Ordinary rendering should keep `COMMON_ESTO_UPDATE_DATA=0`.

### 6.2 Destructive/generated behavior

`CLEAR_EXISTING_OUTPUTS=True` recursively removes only the selected economy’s
generated `dashboards`, `chart_bundles`, and `supporting_files` folders before
recreating them. Confirm the output root/economy before running.

`COMMON_ESTO_UPDATE_DATA=1` writes fast-path outputs into the sibling mappings
repository. It is not a full mapping refresh and must not overlap Stage 3.

`COMMON_ESTO_PUBLISH_TO_DOCS=1` copies serving files and removes stale
published HTML/JS for the selected economy. Use only when publishing is
explicitly in scope and publication gates pass.

### 6.3 Validation

From the documented Windows interpreter:

```powershell
C:\Users\Work\miniconda3\python.exe -m pytest tests\test_common_esto_dashboard.py
C:\Users\Work\miniconda3\python.exe scripts\check_common_esto_dashboard_publish_ready.py
C:\Users\Work\miniconda3\python.exe scripts\analyze_common_esto_dashboard_page_noise.py
```

Use additional focused tests for changed loaders, diagnostics, or routing.
Confirm:

- dashboard index and page HTML;
- local JS bundles;
- non-empty `chart_manifest.csv`;
- page-assignment and sign summaries;
- diagnostics page/tree explorer;
- no unexpected empty charts or missing bundles;
- upstream run/provenance is current.

Observed 2026-07-28: a two-economy render wrote 650 charts; the 21-economy
batch’s output timestamps span roughly one hour. Treat these only as planning
evidence.

## 7. Failure triage

| Symptom | Likely layer | First evidence | Owner | Unsafe shortcut |
|---|---|---|---|---|
| `current_output_file` is `_rebuilt` | locked mapping CSV | output status and open handles | mappings | rename it manually over canonical |
| Stage 3 says completed but validators fail | review diagnostics | manifest validation arrays and summary CSVs | mappings | report “pipeline passed” |
| long dashboard load misses required columns | producer/contract mismatch | CSV header and loader required columns | mappings + dashboard | patch columns in generated file |
| values duplicated across scopes | scope collapse | compound key and `source_system` | mappings/consumer | drop scope/source columns |
| seed exists with blocking findings | emit/readiness boundary | readiness summary/findings | initialisation | import anyway |
| repeated run overwrites another | run-label collision | resolved label and run roots | initialisation | keep identical auto label |
| stale economy lock | killed process | lock JSON PID and process table | initialisation | delete all locks |
| wrong region or IDs | economy template mismatch | template and findings | initialisation | copy USA IDs |
| chart missing but row exists | dashboard filter/routing | manifest and page assignment | dashboard | alter mapping label |
| empty diagnostic missing file | check did not run or path changed | producer status/log | owner of check | call it zero findings |

## 8. Human-stop conditions

Stop and request semantic/model review when:

- a candidate would be added to the workbook;
- a mapping change affects complete sibling coverage or many-to-many
  cardinality;
- subtotal meaning is unclear;
- a deliberately absent relationship might be restored;
- an ESTO Extended category/value allocation lacks authoritative evidence;
- a reconciliation cap, import fallback, or surplus strategy changes;
- unresolved IDs or branches would be waived;
- additive frontier ownership is ambiguous;
- publishing would include known blocking/unknown diagnostics.

## 9. Verification evidence to record

For each material run or change, record:

- repository and commit;
- dirty-worktree state;
- workbook path and whether Excel was closed;
- source file paths/vintages;
- economy/scenario/year scope;
- run ID/output label;
- interpreter path and process command line;
- start/end time and timing CSV/manifest;
- exact validation commands;
- counts/statuses of blocking, failed, skipped, and review-only findings;
- representative lineage;
- downstream consumers rerun or explicitly not rerun.

## 10. Handoff checklist

Before committing:

1. review `git diff -- <exact documentation files>`;
2. run link/path/Mermaid checks;
3. ensure no generated data or workbook is staged;
4. stage exact documentation paths;
5. commit separately in each repository using a `codex:` prefix;
6. leave unrelated dirty files untouched and report them.
