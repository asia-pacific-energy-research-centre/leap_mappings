# Master Prompt: Recover Then Rerun All LEAP Processes

Coordinate the following work across these repositories:

- `C:\Users\Work\github\leap_mappings`
- `C:\Users\Work\github\leap_initialisation`
- `C:\Users\Work\github\leap_dashboard`

Use the four detailed prompts in this directory as the process-specific instructions.

## Required order

1. Confirm the Codex bundled runtime has rehydrated and `@oai/artifact-tool` imports successfully.
2. Run the `leap_initialisation` update process and generate PRC, AUS, and USA previews.
3. Run the full `leap_mappings` pipeline. It is expected to be the most memory-intensive process. Do not run the long baseline-seed process concurrently with it.
4. Reconfirm the mapping outputs are available to `leap_initialisation`.
5. Run the 11-economy baseline seeds in `leap_initialisation`, at most three economies in parallel per batch. This is expected to take many hours.
6. After the baseline seeds finish, run the full `leap_dashboard` process for AUS, PRC, and USA.

If the user wants the mapping pipeline before the update process for dependency reasons, explain the conflict and follow the safer dependency order: validate/update source previews first, then run the full mapping pipeline, then baseline seeds, then dashboard. Never run memory-intensive mapping and baseline-seed batches together.

## Incident safety context

On July 30, unsafe `git worktree remove` commands traversed Windows directory junctions. One junction pointed from a mapping worktree into the shared Codex runtime and emptied its `node_modules`, removing `@oai/artifact-tool`. Another cleanup path affected LEAP initialization export-template data. No tracked repository source is known to be missing, and the current 29_07 templates were restored, but ignored data and generated artifacts are not protected by Git.

Therefore:

- Do not run worktree cleanup, recursive deletion, or broad output cleanup.
- Detect and refuse any cleanup involving reparse points/junctions.
- Preserve and hash restored templates and current balance exports.
- Do not restore Recycle Bin files automatically.
- Do not overwrite existing outputs; use unique run labels.

## Process monitoring policy

- Poll every 30 minutes for the first two hours of each process.
- Poll hourly after two hours.
- Keep full logs on disk; report only incremental tails and concise status.
- At each poll report process identity, elapsed time, current stage, memory/resource concerns, newest output, and failure state.
- Leave healthy active processes running.

## Error policy

- Fix only simple, local, unambiguous issues.
- Do not invent mappings, change template IDs, modify semantic rules, or overwrite user changes to make a run pass.
- If an issue is substantive or uncertain, record it with repository, stage, economy, command/configuration, traceback, likely cause, and suggested next action.
- Continue to the next independent process/economy when safe.
- Stop launching new dependent work if a shared runtime, mapping, template, or repository-state blocker affects downstream results.

## Required handoff artifacts

For each process, preserve:

- exact command/workflow entry point;
- repository commit and working-tree status;
- input/template/export hashes where relevant;
- run label and output paths;
- start/end times and polling summary;
- per-economy status;
- blocking and non-blocking findings;
- downstream readiness decision.

## Final report

Provide a concise cross-repository table showing:

- runtime status;
- update/previews status;
- mapping status;
- baseline status for all 11 economies;
- dashboard status for AUS, PRC, and USA;
- unresolved issues and whether they block further work;
- exact output locations.

Do not claim overall success if any required economy or dependent process failed or was skipped.
