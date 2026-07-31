# Prompt: Rerun `leap_initialisation` Baseline Seeds for 11 Economies

Work in `C:\Users\Work\github\leap_initialisation`.

## Objective

Rerun baseline-seed generation and validation for the 11 economies represented by the current LEAP export templates in `data\leap_export_templates`. This is the longest process and must run only after the latest `leap_mappings` pipeline and the update/preview process have completed successfully enough for downstream use.

Run at most three economies in parallel at a time. Do not start all 11 simultaneously.

## Preconditions

- Confirm `@oai/artifact-tool` imports from the official bundled Codex Node runtime.
- Confirm the full mapping pipeline completed and record the exact mapping outputs/commit.
- Confirm the update process and PRC/AUS/USA previews completed or have documented non-blocking findings.
- Enumerate the 11 economy templates actually present and resolvable. Do not assume the list from old documentation; derive it from the current folder and resolver.
- Validate template structure, IDs, region metadata, and branch coverage before launching economies.
- Preserve hashes of the current templates and current USA/PRC balance exports.
- Check active processes and lock state. Use a new unique run label and do not overwrite previous partial runs.
- Inspect repository status and preserve unrelated changes.
- Do not use `git worktree remove`, recursive deletion, or cleanup commands. Do not follow or delete through junctions/reparse points.

## Execution order

1. Run one small smoke-test economy first, preferably an economy with a confirmed current template and known balance export.
2. If the smoke test passes the runtime/template gates, process the remaining economies in batches of no more than three concurrent economies.
3. Wait for a batch to finish and record results before starting the next batch.
4. Keep failed economies isolated from successful economies; do not rerun successful economies unnecessarily.
5. Preserve all seed workbooks, validation findings, diagnostics, logs, and run manifests.

## Error handling

- Fix only simple, local, unambiguous problems such as a missing output directory or an explicitly wrong run parameter.
- Do not patch mappings, template IDs, or balance logic while the long run is active unless the issue is already documented and the fix is clearly mechanical.
- If an economy fails, record its stage, exception, inputs, output label, and likely cause, then continue with the other economies.
- If a shared dependency, template root, mapping output, or runtime problem affects all economies, stop launching new batches and report the shared blocker.
- Expect some economy-specific validation findings; distinguish warnings from blocking failures.

## Monitoring

- Poll every 30 minutes for the first two hours.
- Poll hourly after two hours.
- Monitor each process separately: PID/process name, economy, batch, stage, elapsed time, output timestamp, memory, and failure state.
- Do not repeatedly print large logs. Read incremental tails and preserve full logs on disk.
- If a process is alive and making progress, leave it running.

## Completion criteria

Report a table for all 11 economies containing:

- started/completed/failed status;
- batch and elapsed time;
- seed output path;
- validation output path;
- blocking versus non-blocking findings;
- whether the output is safe for the next dashboard/update step.

Do not claim full success if any economy failed or was skipped. Do not start the dashboard process from this prompt.
