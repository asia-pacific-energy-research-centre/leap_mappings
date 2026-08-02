# Reusable Prompt: Run the LEAP Workflows End to End

Coordinate the LEAP workflows across:

- `C:\Users\Work\github\leap_mappings`
- `C:\Users\Work\github\leap_initialisation`
- `C:\Users\Work\github\leap_dashboard`

Read the process-specific prompts in this directory and use them for the
individual workflow commands and validation details.

## Objective

Run the requested LEAP workflows end to end using a new unique run label:

1. Run the full mappings pipeline.
2. Run the initialisation update/previews for the requested economies,
   normally PRC, AUS, and USA.
3. Run baseline seeds for the requested non-provisional economies, in batches
   of no more than three economies at a time.
4. Run the dashboard for the requested economies, normally AUS, PRC, and USA.

If a process-specific prompt defines a different dependency order, follow that
order. Never run the memory-intensive mappings pipeline at the same time as
baseline-seed batches unless the user explicitly authorizes it.

Do not require smoke tests or other test runs before starting the workflow.
Run tests only when they are needed to diagnose a failure, verify a simple
local fix, or when the user explicitly requests them.

## Before starting

- Confirm the repositories and requested economies.
- Check for already-running equivalent processes and do not launch duplicates.
- Record the working-tree status and preserve unrelated user changes.
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

- Poll every 30 minutes for the first two hours of each process.
- Poll hourly after two hours.
- At each effective poll, report only incremental log tails and concise status:
  process identity, elapsed time, current stage, memory/resource concerns,
  newest output, and failure state.
- Leave healthy processes running and never launch a duplicate.

## Completion report

Provide a concise status table covering:

- mappings pipeline;
- update/previews by economy;
- baseline seed by economy;
- dashboard by economy;
- warnings and substantive blockers;
- exact output and log locations;
- whether any safe independent work remains.

Do not claim overall success if a required economy or dependent workflow was
skipped, failed, or produced invalid outputs.
