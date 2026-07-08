# Prompt: Run the mapping pipeline and report QA issues

Work in `C:\Users\Work\github\leap_mappings`.

## Goal

Run the relevant mapping workflow to produce the latest mapping outputs and QA
results in the repository's normal output locations.

Use the primary entrypoint:

```powershell
C:\Users\Work\miniconda3\python.exe codebase\run_mapping_pipeline.py
```

If the repo docs or code clearly identify a newer primary entrypoint, use that
instead and state why. If multiple scripts are required, run them in the order
defined by the repo docs.

Do not use any LEAP economies setting copied from another prompt. Use the
pipeline's normal/default scope unless this prompt is explicitly edited to say
otherwise.

## Required context before running

Before starting the workflow:

1. Read `AGENTS.md`.
2. Read `docs/mappings_system.md` enough to confirm the current pipeline stages,
   workbook rules, and QA output locations.
3. Check `git status --short`.
4. Note any pre-existing modified or untracked files, especially Excel temporary
   files or existing outputs. Do not revert or clean them unless the user asks.

## Workbook safety rule

Do not automatically write, archive, save, or update:

```text
config/outlook_mappings_master.xlsx
```

If a script attempts to make automatic workbook adjustments, disable or bypass
that behavior for this run and record exactly what was changed. Stage 0
maintenance should be preview/check/report only unless the user has explicitly
asked for workbook writes in this prompt.

Generated CSV and QA outputs in `results/` should still be written normally.

## Running and monitoring

Launch each long-running run step or workflow stage as a background process with
its own log file under the repo's normal log/results area.

Use this polling schedule independently for each run step or workflow stage:

1. Poll after 5 minutes.
2. Poll after another 5 minutes.
3. Poll after 10 minutes.
4. Poll after another 10 minutes.
5. Poll after 20 minutes.
6. Poll after another 20 minutes.
7. Poll every 20 minutes thereafter until the current run step is finished.

Restart that polling count for each new run step or workflow stage.

At each scheduled poll, inspect only:

- whether the process is still alive;
- CPU time or another simple progress signal, if available;
- the last 20-40 lines of the log.

Do not poll more frequently than the schedule. If CPU time or log progress stops
changing across two scheduled polls, report that the run may be stalled and
investigate before simply waiting longer.

## Error handling

If an error occurs and the fix does not require a major decision from the user:

1. Diagnose it.
2. Make the smallest safe fix.
3. Record the error and the fix.
4. Rerun the affected step.
5. Continue the workflow.

If the error requires a major design decision, stop and report the decision
needed instead of guessing.

Do not silently skip failed stages or failed QA generation. If a stage is
intentionally skipped, state the reason and cite the repo docs or code path that
justifies it.

## Warning and issue handling

Record warnings as they happen. For each warning or QA issue, capture:

- source stage or script;
- exact warning text or output file name;
- whether it affects generated comparison data, QA-only outputs, or both;
- the relevant output files to inspect;
- whether the issue is actionable now, review-only, already allowlisted, or
  needs a user decision.

When investigating diagnostics, distinguish actual observed non-zero data rows
from theoretical or zero-only combinations. Prefer narrow, human-facing outputs.
Put bulky trace/debug files in `diagnostics` or `extra_detail` if new files are
needed.

## Mapping gap interpretation

For missing mapping diagnostics:

- Treat rows as actionable only when they are backed by observed source data,
  and highlight non-zero rows separately from zero-only rows.
- Do not treat `counterpart_presence_state == removed_only` as a row to restore;
  removed rows are often deliberate guardrails.
- Before recommending a new mapping row, check whether an equivalent parent,
  repeated-child, or singular-child variant already maps the same source product
  or target product. If so, classify it as an exception or review note instead
  of a direct mapping gap.
- Do not generate or apply mapping candidates directly into the workbook. Any
  candidate rows must remain review-only CSV outputs.

## Reporting requirements

At the end, provide a concise but complete report suitable for review tomorrow.

Include:

- what was run, including exact commands and working directory;
- what completed successfully;
- warnings encountered;
- errors encountered;
- fixes applied;
- steps rerun after fixes;
- important QA outputs produced;
- highest-priority issues for human review;
- any remaining issues or decisions needed from the user;
- whether `config/outlook_mappings_master.xlsx` was unchanged, and how this was
  verified if workbook safety was relevant.

For generated `.csv` or `.xlsx` outputs, provide both:

- a clickable Markdown link using the full Windows path as the link target; and
- the plain `C:\...` Windows path.

## Git handling

If code or documentation changes are made, commit only the files changed for
this task with a scoped `codex:` commit. Do not stage unrelated workbook,
temporary, output, or user-created files.
