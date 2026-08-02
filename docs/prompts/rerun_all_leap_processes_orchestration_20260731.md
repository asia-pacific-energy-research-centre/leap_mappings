# Reusable Prompt: Run the LEAP Workflows End to End

Coordinate the LEAP workflows across:

- `C:\Users\Work\github\leap_mappings`
- `C:\Users\Work\github\leap_initialisation`
- `C:\Users\Work\github\leap_dashboard`

Read the process-specific prompts in this directory and use them for the
individual workflow commands and validation details.

## Objective

Run the requested LEAP workflows end to end using a new unique run label:

1. In `leap_mappings`, run the supported separate-axis mapping refresh. The
   editable authority is `config/outlook_mappings_single_axis.xlsx`; do not
   treat the generated master workbook as the editable source.
2. Verify that the refresh promoted and reopened
   `config/outlook_mappings_master.xlsx`, then run the full mappings pipeline.
3. Run the initialisation update/previews for the requested economies,
   normally PRC, AUS, and USA.
4. Run baseline seeds for the requested non-provisional economies, in batches
   of no more than three economies at a time.
5. Run the dashboard for the requested economies, normally AUS, PRC, and USA.

This dependency order is required because `leap_initialisation` reads the
canonical sibling workbook at
`leap_mappings/config/outlook_mappings_master.xlsx`. A mapping change is not
integrated into a new initialisation run unless the separate-axis refresh has
first regenerated that canonical workbook and the mappings pipeline has
successfully rebuilt its downstream artifacts.

If a process-specific prompt defines additional dependencies, incorporate them
without reversing the required mapping-refresh -> mappings-pipeline ->
initialisation order. Never run the memory-intensive mappings pipeline at the
same time as baseline-seed batches unless the user explicitly authorizes it.

Do not require smoke tests or other test runs before starting the workflow.
Run tests only when they are needed to diagnose a failure, verify a simple
local fix, or when the user explicitly requests them.

## Before starting

- Confirm the repositories and requested economies.
- Check for already-running equivalent processes and do not launch duplicates.
- Record the working-tree status and preserve unrelated user changes.
- Confirm that the current `leap_mappings` worktree contains every intended
  editable mapping change. If required changes are uncommitted, keep using that
  exact worktree: do not switch branches, reset it, clean it, or assume the
  changes exist in a fresh checkout or on another machine.
- Create a new unique run label and output location.
- Confirm required inputs exist when each process reaches them.

Do not perform broad cleanup, worktree cleanup, recursive deletion, or
automatic restoration from the Recycle Bin. Do not overwrite source templates,
mapping workbooks, or unrelated user changes. Workflow output overwrites are
allowed only when the user explicitly authorizes them; otherwise use isolated
outputs.

## Execution and failure handling

- Launch each process with its exact documented entry point and record the
  command, repository, process ID, run label, and output paths.
- After the separate-axis refresh, require a successful generation manifest
  with `status = promoted_and_reopened`. Confirm that the generated canonical
  workbook contains the intended mapping and rollup rules before starting the
  full mappings pipeline.
- For the All-demand Other-sector detached rollup, confirm that the generated
  ESTO boundary contains exactly `16.03 Agriculture`, `16.04 Fishing`,
  `16.05 Non-specified others`, and `17 Non-energy use`, and that the aggregate
  LEAP row maps to
  `16.03-16.05,17 Other sector including non-energy (all demand aggregate)`.
  Keep the detailed `17 Non-energy use` mapping intact.
- Before initialisation, verify the mappings pipeline completed its frontier,
  relationship, and conservation checks and that no detached subtotal shares
  the same comparison frontier with its contributors.
- Keep full stdout and stderr logs on disk.
- Verify the expected outputs before starting a dependent process.
- Continue independent economies or workflows after an economy-specific
  failure when their prerequisites remain valid.
- Do not launch a dependent process when its required upstream artifact is
  missing, failed, or invalid.
- Fix only simple, local, unambiguous issues.
- For substantive or uncertain issues, preserve outputs and record the
  repository, stage, economy, command/configuration, traceback, likely cause,
  and suggested next action.
- Stop before any external repair, runtime reinstall, template replacement, or
  modelling/mapping decision that requires user authority.

## Monitoring

- Poll once after the first 30 minutes of each process.
- Poll hourly after that first 30-minute poll.
- At each effective poll, report only incremental log tails and concise status:
  process identity, elapsed time, current stage, memory/resource concerns,
  newest output, and failure state.
- Leave healthy processes running and never launch a duplicate.

## Completion report

Provide a concise status table covering:

- separate-axis mapping refresh and canonical-workbook promotion;
- mappings pipeline;
- update/previews by economy;
- baseline seed by economy;
- dashboard by economy;
- warnings and substantive blockers;
- exact output and log locations;
- whether any safe independent work remains.

Do not claim overall success if a required economy or dependent workflow was
skipped, failed, or produced invalid outputs.
