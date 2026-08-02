# Prompt: Rerun the Full `leap_mappings` Pipeline

Work in `C:\Users\Work\github\leap_mappings`.

## Objective

Run the complete current mapping pipeline using the latest available source data and mappings. This must finish before the 11-economy baseline-seed rerun in `leap_initialisation`, because the baseline seeds must consume the refreshed mappings.

## Preconditions

- Confirm the Codex bundled runtime is healthy before any spreadsheet-dependent step. In particular, verify that the bundled Node runtime can import `@oai/artifact-tool`.
- Do not proceed with spreadsheet work if that dependency is unavailable; record the blocker and stop this process.
- Inspect `git status --short --branch` and preserve unrelated existing changes. Do not reset, checkout, clean, or overwrite user changes.
- Do not run worktree cleanup. Never run `git worktree remove` or recursive deletion in this task. The July 30 incident showed that ignored junctions can point into shared Codex runtimes or sibling-repository data.
- Use the repository’s canonical mapping workflow and current instructions. Do not write computer-generated mapping candidates directly into maintained mapping workbooks.

## Execution

1. Inspect the canonical workflow entry point and its current toggles.
2. Run the full mapping pipeline from a notebook-safe workflow or the repository’s intended execution method.
3. Use a new, clearly named output/run label so prior outputs are not overwritten.
4. Capture stdout, stderr, timestamps, configuration, Git commit, and output paths.
5. Validate the important mapping outputs, including cardinality, missing mappings, generated pair-sheet consistency, and any required workbook artifacts.

## Error handling

- Fix only simple, local, unambiguous issues such as a missing output directory, stale non-destructive lock, or incorrect explicitly configured path.
- Do not make speculative mapping changes, alter semantic mappings, or repair data-quality findings silently.
- A completed pipeline may report QA findings such as hierarchy mismatches,
  anchor findings, or unmapped rows. Classify these as non-blocking findings
  unless required artifacts are missing/corrupt or a documented hard
  integrity/safety gate fails; downstream workflows may consume structurally
  valid completed outputs while carrying the findings forward.
- For non-simple failures, record the economy/stage, traceback, likely cause, and exact next action, then continue with independent safe checks where possible.
- Do not declare success if the pipeline completed only partially.

## Monitoring

- For the first two hours, poll progress every 30 minutes.
- After two hours, poll every 60 minutes.
- Do not repeatedly dump large logs. Read only new tail output and summarize status.
- At each poll, report process identity, elapsed time, current stage, memory pressure if visible, newest output timestamp, and whether the process is still alive.
- If the process is active and unchanged, leave it running.

## Completion criteria

Report:

- success or partial/failure status;
- exact run label and output locations;
- elapsed time and peak/observed memory concerns;
- validation results;
- unresolved issues that baseline-seed work must know about;
- the exact mapping commit/configuration consumed by downstream runs.

Do not start the baseline-seed process from this prompt. Hand off only after the refreshed mapping outputs are validated, or clearly report why they are blocked.
