# Mapping pipeline agent guide

**Verified:** 2026-07-29

Use this runbook only after reading `AGENTS.md`,
[`../mappings_system.md`](../mappings_system.md), and
[`../work_queue.md`](../work_queue.md).

## Exact operational table

| Workflow | Entry point | Supporting modules | Inputs | Outputs | Workbook mutation |
|---|---|---|---|---|---|
| Separate-axis generation | `separate_axis_mapping_refresh_workflow.py` | compiler, pair registries, workbook-source workflow, Python/openpyxl workbook builder | editable axes/extras/exceptions/rollups, data evidence, templates | generated pair evidence, canonical compatibility master, generation manifest | refresh normalizes editable duplicate rows and copies editable rollup sheets into the generated master |
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
4. Run the production separate-axis refresh and confirm its generation-manifest
   hash matches the canonical compatibility workbook.
5. Confirm current ESTO/9th filenames and sibling LEAP export discovery.
6. Record commit, source vintages, workbook state, and requested scopes.
7. If axes, accepted extra pairs, data vintages, templates, or rollup rules
   changed, refresh the separate-axis compiler before Stage 1.
8. Decide whether a full run or a cached fast path is justified.

## Optional maintenance workflows

Do not prepend a generic Stage 0 to every run. Use the narrow workflow that
matches the change:

| Change | Workflow | Default toggle |
|---|---|---|
| reviewed ESTO/ESTO Extended categories or structural-completion rows | `codebase/missing_mapped_esto_rows_workflow.py` | `RUN_MISSING_MAPPED_ESTO_ROWS_REVIEW = False` |
| hierarchy, subtotal flags, structural source inventory, or subtotal exceptions | `codebase/hierarchy_subtotal_contract_workflow.py` | `BUILD_CONTRACT = False` |

Both workflows are review-only. Neither writes the canonical mapping workbook
or ESTO source CSVs. The archived
`codebase/archive/outlook_mapping_maintenance_workflow.py` is not an operating
entry point.

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
    run_stage_1,
    run_stage_2,
    run_leap_parse,
    run_data_convert,
    run_stage_3,
)

#%%
RUN_STAGE_1 = True
RUN_STAGE_2 = True
RUN_LEAP_PARSE = True
RUN_DATA_CONVERT = True
RUN_STAGE_3 = True
LEAP_ECONOMIES = None
SKIP_DEEP_VALIDATION = False

#%%
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
| editable axis or accepted extra pair | separate-axis generation, focused hierarchy review when structural flags changed, 1, 2, affected conversions, 3 |
| pair-authority source/template vintage | separate-axis generation, then downstream stages affected by the compatibility diff |
| workbook mapping/rollup | Stage 1, 2, conversions as affected, 3; run focused hierarchy review when structural flags or hierarchy changed |
| scope/override/name affecting structure | Stage 1 if relationship-dependent; Stage 2 and 3 |
| source vintage | conversion and Stage 3; Stage 1/2 if coverage/structure changes; run ESTO-row review only when category coverage changed |
| LEAP balance export only | LEAP parse and LEAP conversion; rerun Stage 3 when the converted LEAP values are to be republished |
| values only; every cached dependency proven current | fast path |
| Stage 3 validation logic | Stage 3 full validation |

## Outputs to inspect in order

1. `results/logs/mapping_pipeline.log`;
2. `results/logs/mapping_pipeline_resource_usage.json` for average/peak RSS;
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
