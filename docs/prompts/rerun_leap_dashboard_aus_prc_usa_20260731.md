# Prompt: Rerun `leap_dashboard` for AUS, PRC, and USA

Work in `C:\Users\Work\github\leap_dashboard`.

## Objective

Run the full current dashboard process for AUS, PRC, and USA after the refreshed mappings, update/previews, and 11-economy baseline-seed work have completed.

## Preconditions

- Confirm the mapping pipeline completed and record its exact outputs/commit.
- Confirm the `leap_initialisation` update process and baseline-seed results are available.
- Confirm the three economies have usable, validated source outputs. Do not silently build a dashboard from a failed or partial baseline seed.
- Confirm the Codex runtime if the dashboard workflow uses spreadsheet-dependent JavaScript.
- Inspect `git status --short --branch` and preserve unrelated changes.
- Do not run worktree cleanup or recursive deletion. Detect junctions/reparse points before any output cleanup.

## Execution

1. Identify the canonical full dashboard workflow and current run toggles.
2. Use a new unique output/run label.
3. Run the process for AUS, PRC, and USA.
4. Validate generated charts, tables, comparison outputs, and economy labels.
5. Inspect for empty/missing outputs, stale-source use, broken links, formula errors, or cross-economy contamination.
6. Preserve logs, previews, manifests, and exact input provenance.

## Error handling and monitoring

- Fix only simple, local, unambiguous issues.
- Record substantive data or rendering problems and continue with other economies where independent.
- Poll every 30 minutes for the first two hours, then hourly.
- Read incremental log tails only; do not dump large artifacts into chat.

## Completion criteria

Report status and output paths for AUS, PRC, and USA, including validation findings and exact mapping, baseline-seed, and code inputs used.
