# Prompt: Rerun `leap_initialisation` Update Process and Previews

Work in `C:\Users\Work\github\leap_initialisation`.

## Objective

Run the current update workflow first, before the long 11-economy baseline-seed process. Generate and inspect previews for PRC, AUS, and USA. Use the latest validated mappings from `C:\Users\Work\github\leap_mappings`.

## Preconditions

- Confirm the Codex bundled Node runtime and `@oai/artifact-tool` import are working. Stop and report a runtime blocker if not.
- Confirm that the refreshed `leap_mappings` pipeline has completed and identify its exact output/commit.
- Confirm the twelve restored workbooks in `data\leap_export_templates` are present and readable. Do not overwrite them or restore older Recycle Bin files automatically.
- Hash or otherwise record the restored templates and current USA/PRC balance exports before running.
- Inspect `git status --short --branch`; preserve unrelated user changes.
- Do not run worktree cleanup or recursive deletion. Check for junctions/reparse points before touching generated directories.

## Execution

1. Identify the canonical update workflow and its notebook-safe run block.
2. Configure a new unique output label.
3. Run the update process using current mappings and current templates.
4. Generate previews specifically for:
   - PRC
   - AUS
   - USA
5. Inspect previews for missing sheets, broken formulas, empty outputs, clipped/invalid content, and obvious template/ID mismatches.
6. Preserve logs, diagnostics, previews, configuration, and the exact input hashes.

## Error handling

- Fix only simple, local, unambiguous setup problems.
- If a preview or economy has a substantive data, ID, mapping, or balance failure, record it and continue with the other economies.
- Do not silently substitute old templates or overwrite current outputs.
- Do not alter mapping semantics in this prompt.

## Monitoring

- Poll every 30 minutes for the first two hours.
- Poll hourly after two hours.
- Read only incremental log tails; do not dump large workbooks or logs.
- Report process identity, elapsed time, current stage, newest output, and resource concerns at each poll.

## Completion criteria

Report whether the update succeeded and provide:

- the output label and paths;
- preview paths for PRC, AUS, and USA;
- validation findings by economy;
- any blockers that could affect the baseline-seed rerun;
- the exact mappings, templates, and code revision used.

Do not start the 11-economy baseline-seed process from this prompt.
