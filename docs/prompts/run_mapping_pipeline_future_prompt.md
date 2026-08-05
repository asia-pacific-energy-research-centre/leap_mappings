# Prompt: Run the four-source mapping pipeline and all-economy dashboards

## Task type

Long-running, cross-repository production run and verification. This is a
reusable run procedure, not permission to redesign mappings or edit reviewed
workbook semantics.

## Goal

Run the complete mapping pipeline for ESTO, ESTO Extended, Ninth Outlook
(`NINTH`), and LEAP. After the mapping run completes and its required artifacts
are structurally valid, render the Common ESTO dashboard for every economy with
data available in the selected mapping output. Include every economy's
diagnostics pages and render the mapping-pipeline health report.

QA findings such as hierarchy mismatches, anchor failures, unmapped rows, or
coverage gaps are **completed with findings**, not automatic workflow blockers.
Continue to the dashboard when the required artifacts exist and are readable.
Stop only for a missing or unreadable required artifact, a failed generation or
promotion gate, invalid workbook structure or IDs, or another documented hard
safety gate.

## Repositories and entry points

Mappings repository and primary entry point:

```text
C:\Users\Work\github\leap_mappings
codebase/run_mapping_pipeline.py
```

Dashboard repository and all-economy entry point:

```text
C:\Users\Work\github\leap_dashboard
scripts/render_common_esto_dashboard_all_economies.py
```

Use the maintained notebook-safe functions and current runbook if these entry
points have changed. Do not introduce a new command-line wrapper merely for
this run.

## Prerequisites

Before starting:

1. Read every applicable `AGENTS.md`, including repository-specific files.
2. Read `docs/handover/agent_operations_guide.md` and the relevant current
   sections of `docs/mappings_system.md`.
3. Run `git status --short` in both repositories. Preserve and report all
   unrelated changes.
4. Confirm the user's separate-axis work is committed at the intended stable
   checkpoint. Record both repositories' branch names and commit hashes.
5. Confirm no mapping or dashboard process is already running.
6. Confirm editable workbooks are closed and no Excel owner-lock file will
   redirect or block generation.
7. Verify the configured source paths and schemas for ESTO, ESTO Extended,
   NINTH, and LEAP before starting the expensive run.
8. Verify adequate free memory and disk space for outputs and logs.

The editable mapping authority is
`config/outlook_mappings_single_axis.xlsx`. Follow the current documented
separate-axis generation and promotion contract. Do not edit generated pair
sheets directly, invent mappings, approve exception candidates, or make
review-driven workbook changes during this run.

## Running and monitoring

Run the mapping workflow in its documented Stage 1, Stage 2, LEAP parsing,
four-source conversion, and Stage 3 order, with deep validation enabled. Do not
use the Common ESTO fast path for this baseline.

Launch each genuinely long-running mapping or dashboard command with a clearly
named process and a dedicated log file in the repository's normal log/output
area.

**Poll only once every 20 minutes while a long-running process is active.**

- Make the first scheduled poll 20 minutes after launch.
- Poll every 20 minutes thereafter.
- Do not add early 5- or 10-minute polls.
- Do not treat quiet or unchanged output as failure by itself.
- At a poll, inspect only process liveness, a simple progress signal such as
  CPU time, and the last 20–40 log lines.
- If the monitoring mechanism reports completion or failure without an extra
  poll, handle that terminal state immediately.
- Do not restart or terminate a healthy process merely because it is quiet.
- If progress and CPU time are both unchanged across two scheduled polls,
  investigate whether it is stalled before taking disruptive action.

When mappings complete, determine the dashboard economy list from the
successfully generated data and current dashboard configuration. Do not rely
on a hard-coded list. Render all economies with usable data, their diagnostics
pages, and the pipeline-health report.

## Stop and change-control rules

- Do not silently skip a required source, stage, economy, diagnostics page, or
  QA output.
- Do not report zero eligible checks as a pass.
- Do not modify mapping semantics, exception workbooks, or dashboard code just
  to make a run pass.
- If a code or configuration defect prevents the run, diagnose and report the
  smallest proposed fix. Do not edit or commit it without separate authority.
- Do not commit or push generated outputs, code, documentation, or workbook
  changes unless the user separately asks.

## Post-run mapping checks

After the mapping workflow completes, check:

1. Every required stage completed for ESTO, ESTO Extended, NINTH, and LEAP.
   Distinguish successful completion with QA findings from a workflow blocker.
2. The selected output contract, manifests, run ID, and timestamps all refer to
   the new coherent run rather than a preserved or stale earlier run.
3. Mapped-value preservation and source-once/cardinality gates are structurally
   valid in every generated comparison scope. Report numerical findings without
   treating them as hidden passes.
4. `source_parent_anchor_validation.csv` contains `exception_review_status`,
   `exception_id`, `exception_issue_class`, and
   `source_non_additivity_observed`.
5. `source_parent_anchor_validation_summary.csv` contains `failed`,
   `confirmed_issue_failed`, `unconfirmed_failed`, and
   `source_non_additivity_observed`.
6. For every summary row:

   ```text
   failed = confirmed_issue_failed + unconfirmed_failed
   ```

7. Confirmed source issues remain numerical failures. They must not become
   `passed` or `skipped`, and their original numerical reason must remain.
8. Only exact, enabled, user-confirmed exception contexts are confirmed. Check
   specifically that removed or pending PRC cases have not resurfaced as
   confirmed issues.
9. Automatic source non-additivity is evidence only. It must not automatically
   confirm an exception or prove mapping correctness or causation.
10. Hierarchy, anchor, rollup, mapping-coverage, structural, lineage, and
    exception-candidate outputs exist and are readable. Report their material
    findings and review status.
11. Zero eligible checks or execution errors are explicitly `skipped`,
    `unavailable`, or `error` with a reason—not passed.
12. Logs contain no unreported exception, missing required artifact,
    unexpected row-count collapse, duplicate promotion, or memory failure.

## Post-run dashboard checks

For every selected economy:

1. Confirm the main dashboard HTML and supporting Plotly assets exist.
2. Confirm the mapping diagnostics page and mapping-tree explorer exist where
   required by the current dashboard contract.
3. Confirm `chart_manifest.csv` and `page_assignment_summary.csv` exist and are
   readable.
4. Confirm diagnostics cards, failure rankings, confirmed issues, unconfirmed
   failures, and exception candidates are scoped to that economy. No other
   economy's rows should leak into the page.
5. Confirm wording does not say a confirmed source issue proves the mapping
   correct or caused the anchor mismatch.
6. Confirm the pipeline-health report consumes the new review split, retains
   every numerical failure, and does not sum overlapping comparison scopes into
   one misleading headline total.
7. Run the maintained publication-readiness and page-noise checks. Record every
   warning or failure with its affected economy and page.

## Completion report

Provide a concise report containing:

- exact commands or functions, working directories, branches, and commits;
- mapping and dashboard run IDs and timestamps;
- confirmation that all four source systems were processed;
- every economy rendered and any omission with its reason;
- total, confirmed, and unconfirmed anchor failures by comparison scope,
  source system, and validation axis;
- every failed, skipped, unavailable, or errored validation, separated from
  non-blocking QA findings;
- mapped-value preservation, structural/cardinality, coverage, hierarchy,
  rollup, and lineage findings;
- publication-readiness and page-noise results;
- errors, interventions, reruns, or suspected stalls;
- primary artifact, dashboard, diagnostics, health-report, log, and error paths;
  and
- confirmation that no files were committed or pushed unless separately
  authorized.

For every generated `.csv` or `.xlsx` cited, provide both a clickable Markdown
link using its full Windows path and the plain `C:\...` path.
