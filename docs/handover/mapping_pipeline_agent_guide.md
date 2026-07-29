# Mapping pipeline agent guide

**Verified:** 2026-07-29

Use this runbook only after reading `AGENTS.md`,
[`../mappings_system.md`](../mappings_system.md), and
[`../work_queue.md`](../work_queue.md).

## Exact operational table

| Workflow | Entry point | Supporting modules | Inputs | Outputs | Workbook mutation |
|---|---|---|---|---|---|
| Separate-axis generation | `separate_axis_mapping_master_prototype_workflow.py` | pair registries, split-workbook workflow, artifact builder | editable axes/extras, data evidence, templates, rollups | generated pair evidence and compatibility master | generated workbooks only; ordinary refresh leaves editable workbook unchanged |
| Stage 0 | archived maintenance workflow | tree builder, display-name updater, exception loader | workbook, ESTO/9th, model template/export | `results/maintenance`, `results/tree_structure` | default preview/no |
| Stage 1 | relationship builder | rollups, exception/coverage helpers | mapping/rollup sheets | `results/mapping_relationships` | no |
| Stage 2 | Common structure builder | structural resolver, non-expanding rollups | relationships, overrides/exclusions | `results/common_esto` structure/QA | no |
| LEAP parse | orchestrator `run_leap_parse` | balance-export resolver/parser | sibling balance exports | raw long LEAP CSV | no |
| conversions | orchestrator `run_data_convert` | LEAP/9th conversion and exact selectors | sources and mappings | converted rows/lineage | no |
| Stage 3 | orchestrator `run_stage_3` | application, tree validation, anchor validation | converted values/common rows | comparison/status/lineage/QA | no |
| fast path | fast-path workflow | Stage 3 application helper | cached conversions/common rows | long/wide/status | no canonical workbook; yes generated outputs |

## Before running

1. `git status --short --branch`.
2. Check worktrees and active Python processes.
3. Close the editable and generated mapping workbooks in Excel.
4. Confirm whether the run is the current canonical path or the
   separate-axis shadow path. For the latter, use
   `codebase/separate_axis_mapping_shadow_validation_workflow.py`; do not assume
   the Stage 0 wrapper honors the generated-workbook path override.
5. Confirm current ESTO/9th filenames and sibling LEAP export discovery.
6. Record commit, source vintages, workbook state, and requested scopes.
7. If axes, accepted extra pairs, data vintages, templates, or rollup rules
   changed, refresh the separate-axis compiler before Stage 0.
8. Decide whether a full run or a cached fast path is justified.

## Jupyter run block

```python
#%%
from pathlib import Path
import os
import sys

REPO_ROOT = Path(r"C:\Users\Work\github\leap_mappings")
os.chdir(REPO_ROOT)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
LEAP_ECONOMIES = None
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

Do not use deep-validation skip for a release.

## Expected schemas and keys

| Artifact | Key |
|---|---|
| relationship table | relationship ID + use case/status |
| common rows | comparison scope + common row ID + component pair |
| converted source rows | source system + economy + scenario + year + ESTO pair |
| long comparison | scope + source + economy + scenario + year + common row ID |
| source lineage | source identity + component/common identity |

Full published columns are in
[cross_repository_data_contracts.md](cross_repository_data_contracts.md).

## Rerun decision

| Changed | Minimum safe rerun |
|---|---|
| editable axis or accepted extra pair | separate-axis generation, Stage 0, 1, 2, affected conversions, 3 |
| pair-authority source/template vintage | separate-axis generation, then downstream stages affected by the compatibility diff |
| workbook mapping/rollup | Stage 0, 1, 2, conversions as affected, 3 |
| scope/override/name affecting structure | Stage 1 if relationship-dependent; Stage 2 and 3 |
| source vintage | Stage 0, conversion, Stage 3; Stage 1/2 if coverage/structure changes |
| LEAP balance export only | LEAP parse, LEAP conversion, Stage 3 |
| values only; every cached dependency proven current | fast path |
| Stage 3 validation logic | Stage 3 full validation |

## Outputs to inspect in order

1. `results/logs/mapping_pipeline.log`;
2. `results/maintenance/maintenance_summary.csv`;
3. Stage 1 QA and relationship catalogue;
4. Stage 2 structure summary, partial coverage, intersections, and
   non-expanding frontier QA;
5. `results/common_esto/common_esto_output_status.csv`;
6. `results/common_esto/stage3_run_manifest.json`;
7. for a QA-successful publication,
   `common_esto_output_contract.json` and its declared/hash-verified fact and
   metadata members;
8. recursive and source-anchor summaries;
9. material missing-map/candidate diagnostics;
10. representative lineage.

## Overwrite and lock behavior

- Generated CSVs are overwritten in place on a clean run.
- Locked CSVs can produce `_rebuilt`.
- Application errors can produce `_needs_mapping_review`.
- Status manifest selection outranks filename convention.
- Stage 0 reviewed helper mutations back up the workbook; default Stage 0 does
  not apply proposed subtotal changes.
- Fast path overwrites the final status with a fast-path status and omits deep
  validation rows. Preserve the prior full-run evidence separately if needed.

## Tests and validation

Use the explicit Windows interpreter. Run focused tests for every changed
module; representative suites include:

```powershell
C:\Users\Work\miniconda3\python.exe -m pytest tests\test_common_esto_fast_path.py
C:\Users\Work\miniconda3\python.exe -m pytest tests\test_common_esto_validation_orchestration.py
C:\Users\Work\miniconda3\python.exe -m pytest tests\test_source_parent_anchor_validation.py
```

Do not run the hour-long pipeline solely to populate documentation unless the
user explicitly authorizes it.

## Stop for human review

- candidate acceptance;
- new/replaced canonical row;
- incomplete sibling coverage;
- new many-to-many effect;
- subtotal meaning not proven from hierarchy;
- restored deliberately absent mapping;
- new ESTO Extended category or value allocation;
- failed release validation that would be waived;
- additive frontier ambiguity.

## Current runtime and current-state warning

The 2026-07-28 Stage 3 run took about 61 minutes. Its process completed, but
several recursive/anchor validation groups failed. Never summarize that state
as “Stage 3 passed.”

## Downstream impact

After an accepted mapping/structure/value change:

- initialisation must rerun any consumer whose prepared inputs use the changed
  mapping;
- dashboard must rerender affected economies;
- coordinated schema changes require consumer tests before merge;
- never directly edit generated dashboard or Common ESTO CSV files.
