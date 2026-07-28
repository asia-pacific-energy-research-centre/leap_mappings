# Diagnostic file review signals

**Status:** navigation/status page; the proposed file-by-file consolidation
study has not yet been completed.

This path was proposed by the 2026-07-22 repository-cleanup handoff and is
referenced by that historical document. Retaining the path keeps its navigation
valid without pretending that the proposed diagnostic-consumption audit has
been performed.

For current operational guidance:

- use [`handover/mapping_pipeline_agent_guide.md`](handover/mapping_pipeline_agent_guide.md)
  for the order in which to inspect mapping outputs;
- use [`handover/agent_operations_guide.md`](handover/agent_operations_guide.md)
  for cross-repository failure routing;
- use [`results_folder_cleanup_candidates.md`](results_folder_cleanup_candidates.md)
  for evidence about potentially stale or duplicate generated files;
- use [`work_queue.md`](work_queue.md), especially MAPQ-006, MAPQ-012, MAPQ-013,
  and MAPQ-015, for current ownership and next actions.

An empty diagnostic file is evidence of a clean check only when the same run
proves that the check executed. Missing files, skipped checks, and stale files
are unknown—not passes. Do not delete or consolidate diagnostics solely because
they appear similar by name; first verify producer, grain, key, scope, consumers,
run identity, and whether either file is release evidence.

The future detailed study should record, for every candidate diagnostic:

| Field | Question |
|---|---|
| producer | Which stage/function writes it? |
| grain and key | What does one row mean, and what makes it unique? |
| execution evidence | How is “check ran with zero findings” distinguished from skipped/missing? |
| consumer | Which scripts, dashboards, tests, or reviewers read it? |
| overlap | Is another file semantically equivalent or merely similarly named? |
| retention | Is it release evidence, investigation detail, cache, or disposable regeneration output? |
| decision | Keep, merge, relocate to diagnostics, or retire—with evidence and migration plan |

Until that study is completed, this page is a navigation aid rather than a
cleanup verdict.
