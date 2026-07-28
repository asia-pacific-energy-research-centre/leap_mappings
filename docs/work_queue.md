# LEAP mappings work queue and handover plan

**Snapshot date:** 2026-07-28

**Planning horizon:** four weeks, through 2026-08-24

**Owner repository:** `leap_mappings`

**Related repositories:** `leap_dashboard`, `leap_initialisation`

This is the controlling queue for current work and handover preparation. It
reconciles repository state, worktrees, recent commits, the older
`improvement_todo.md`, active prompt files, and the documentation audit in
`documentation_audit_20260728.md`.

Do not mark an item complete only because a prompt or findings file says it is
complete. Completion requires the change to be committed on the intended
branch, verified, and either present on `master` or explicitly recorded as a
clean, ready-to-integrate worktree.

## Status definitions

| Status | Meaning |
|---|---|
| `complete_on_master` | Implemented, verified, committed, and reachable from local `master`. |
| `complete_unpushed` | Complete on local `master`, but not yet present on `origin/master`. |
| `complete_in_worktree` | Clean, committed work exists on another branch and still needs integration or an explicit decision not to integrate. |
| `partial_uncommitted` | Material work exists only as uncommitted changes or an unfinished draft. |
| `partial` | Some committed implementation exists, but the acceptance criteria are not complete. |
| `partial_reconciliation` | Committed branch work overlaps later changes and must be reconciled commit by commit rather than merged wholesale. |
| `paused` | Work is intentionally preserved but should not resume until its stated gate is met. |
| `not_started` | No implementation evidence was found. |
| `human_decision` | Progress depends on a semantic or policy choice that should not be guessed. |
| `superseded_cleanup` | The work is complete or superseded; only archival or branch/worktree cleanup remains. |

## Repository state at the snapshot

- Local `master` is four commits ahead of `origin/master`:
  `947742d`, `2e39cca`, `34858fe`, and the handover queue commit at `HEAD`.
- The main checkout is dirty. It contains a draft qualitative LNG fallback,
  demand-scope configuration changes, documentation edits, five deleted
  non-canonical workbook variants, Office/temp files, and untracked local tool
  directories. These changes are not one coherent completed unit and must not
  be staged together.
- No Python process was running when this snapshot was taken.
- Five non-master worktrees are clean. Four contain commits that Git still
  considers unmerged; one contains a patch-equivalent change already present
  on `master`.
- `leap_dashboard` local `master` is 55 commits ahead of its remote.
- `leap_initialisation` local `master` is 142 commits ahead of its remote.
  Those large remote gaps are cross-repository handover risks even though this
  queue does not authorize pushing either repository.

## Worktree and branch reconciliation

| Branch/worktree | Evidence on 2026-07-28 | Classification | Required action |
|---|---|---|---|
| `master` | Four local commits ahead of `origin/master`; dirty checkout | `complete_unpushed` plus `partial_uncommitted` | Separate the completed local commits from the dirty draft work. Review and push only through the user's normal repository process. |
| `codex/output-contract-phase-2` | Clean; three commits; 320 broader tests passed with documented unrelated/environment failures | `complete_in_worktree` | Review and integrate the output-contract commits before changing the normal output publication path. Preserve the exact ESTO Extended delta as non-default until its quiet-window measurements are complete. |
| `claude/zen-pike-39adbf` | Clean; one commit; candidate-focused tests passed | `complete_in_worktree` | Integrate the empty-partial-coverage guard or document why it is no longer needed. It prevents a legitimate no-candidate state from crashing Stage 3. |
| `codex/esto-rollup-source-identity-guard` | Clean; one commit with tests and inspectable QA output | `complete_in_worktree` | Integrate the regression guard after checking overlap with later output-contract validation. The underlying doubling defect is fixed on `master`, but this guard is not. |
| `claude/mapping-diagnostics-dashboard-a55009` | Clean; six commits; four commits behind current `master` | `partial_reconciliation` | Do not merge wholesale. It repeats workbook/config changes already landed differently, contains the source-identity guard, and adds useful deferred-work docs. Reconcile commit by commit. Its claim that the guard was merged to `master` is currently inaccurate. |
| `codex/investigate-anchor-validator-memory` | Clean; one commit; `git cherry` reports a patch-equivalent change already on `master` | `superseded_cleanup` | Confirm `03c9405` is the intended integrated equivalent, then remove the stale worktree/branch through the normal safe cleanup process. |
| `worktree-agent-abcb30bdd765f323c` | Unmerged local branch at the repository's initial commit; no active worktree | `superseded_cleanup` | Confirm it carries no work, then delete the stale branch. |

## Prioritized queue

Dates below are target windows for handover planning, not promises that semantic
decisions can be made without review.

| ID | Priority | Target | Status | Work item | Evidence and completion test |
|---|---|---|---|---|---|
| MAPQ-001 | P0 | 2026-07-28 to 2026-07-30 | `partial_uncommitted` | Stabilize the main checkout | Classify every current modified, deleted, and untracked path as keep/commit, move to a dedicated worktree, restore, quarantine, or ignore. Do not combine the draft LNG table, demand-scope edits, workbook cleanup, and documentation edits in one commit. Complete when `git status --short` is either clean or every remaining path has a named owner and queue ID. |
| MAPQ-002 | P0 | 2026-07-28 to 2026-07-31 | `complete_unpushed` | Reconcile local `master` with `origin/master` | The four local commits contain the canonical workbook merge, demand/power branch-tab reading, compressed recurring outputs, and this handover queue/audit. Complete when the intended remote contains them or the handover explicitly records why it does not. |
| MAPQ-003 | P0 | 2026-07-29 to 2026-08-01 | `complete_in_worktree` | Integrate the Common ESTO output contract | Review `codex/output-contract-phase-2`, run its focused tests after integration, and confirm dashboard-required identities, keys, years, values, booleans, manifest hashes, and rollback behavior. The exact ESTO Extended delta remains experimental unless separately approved. |
| MAPQ-004 | P0 | 2026-07-29 to 2026-08-01 | `complete_in_worktree` | Integrate two small Stage 3 safety fixes | Reconcile the empty-candidate guard from `claude/zen-pike-39adbf` and the exact-row source-identity guard from `codex/esto-rollup-source-identity-guard`. Complete when both are on `master` with focused tests, or when a written comparison proves a later guard supersedes one of them. |
| MAPQ-005 | P0 | 2026-07-30 to 2026-08-03 | `partial` | Produce one clean current pipeline baseline | Run the intended mapping maintenance and Stages 1-3 only after MAPQ-001 through MAPQ-004 settle code and workbook state. Record run ID, inputs, commit, workbook hash/state, durations, validation counts, and blocking versus review-only findings. A successful exit code alone is not completion. |
| MAPQ-006 | P0 | Start 2026-07-28; weekly | `partial` | Establish documentation control | Use this queue as the controlling backlog; complete the actions in `documentation_audit_20260728.md`; date every status review; and archive completed prompts in the same commit that updates the prompt inventory. Complete when active docs contain only current instructions or clearly dated historical context. |
| MAPQ-007 | P1 | 2026-07-31 to 2026-08-05 | `partial` | Reconcile ESTO Extended work | The design and much of the implementation are on `master`; output-contract and delta work are in a clean worktree; deferred structure/recheck docs are on another worktree. Produce one current status note separating production behavior, experimental behavior, missing Common ESTO structure coverage, and dashboard consumption. |
| MAPQ-008 | P1 | Re-measure 2026-08-17 | `paused` | Recheck deferred ESTO Extended coverage findings | Recover the measurements/docs from `claude/mapping-diagnostics-dashboard-a55009`, but re-measure on the then-current pipeline before implementing its proposed structure changes. If the premise has changed, close or rewrite the task rather than implementing stale counts. |
| MAPQ-009 | P1 | 2026-08-03 to 2026-08-09 | `partial` | Re-triage semantic mapping findings | Use the clean MAPQ-005 baseline. Group actionable partial coverage, non-zero unmapped LEAP branches, presence conflicts, and non-ESTO hierarchy edges by semantic cause. Record human rules before workbook edits. Completion is a reviewed, bounded decision list, not zero raw diagnostic rows. |
| MAPQ-010 | P1 | 2026-08-03 to 2026-08-10 | `not_started` | Review `NON_EXPANDING` versus `DETACHED` rollups | Execute `docs/prompts/review_non_expanding_vs_detached_rollups_prompt.md`. Classify each affected rollup, document human decisions, update only the narrowest configuration required, and rerun affected validation. |
| MAPQ-011 | P1 | After MAPQ-005 | `paused` | Resume mirror-row-gap exception curation | The exception mechanism and 455 curated NINTH inconsistencies are on `master`. Resume from `mirror_row_gap_exception_curation_handoff_20260727.md` only in a clean window with current outputs and no concurrent pipeline mutation. |
| MAPQ-012 | P1 | 2026-08-05 to 2026-08-12 | `partial` | Finish reliability attribution and diagnostic consolidation design | Reconcile the 2026-07-23 design with the later curated-exception implementation, grouped validation outputs, compressed artifacts, output contracts, and dashboard health report. Decide which remaining flags belong in mapping outputs and which belong in dashboard presentation before writing more code. |
| MAPQ-013 | P1 | 2026-08-01 to 2026-08-12 | `partial` | Complete reversible results cleanup and storage policy | The output compression work is on local `master`; exact contract work is in a clean worktree; several old artifacts are verified quarantine candidates. Resolve the blocked `results/missing_mapped_esto_rows/` comparison before moving it. Keep an archive log and never hard-delete a broad results path. |
| MAPQ-014 | P1 | 2026-08-05 to 2026-08-14 | `partial` | Write the technical handover set | Create a short start-here guide, pipeline runbook, mapping-workbook editing guide, validation/diagnostic interpretation guide, cross-repository data contract, and known-risks/decisions list. Prefer links to canonical detail rather than copying the 1,000+ line system document into several places. |
| MAPQ-015 | P1 | 2026-08-10 to 2026-08-17 | `partial` | Define the cross-repository ownership boundary | `leap_mappings` owns mapping semantics and Common ESTO contracts; `leap_initialisation` owns LEAP area initialization/import-ID integrity; `leap_dashboard` owns presentation. Record exact produced/consumed files, schemas, refresh order, and failure ownership. Reconcile the large local-vs-remote commit gaps in the two sibling repos as a separate authorized action. |
| MAPQ-016 | P2 | 2026-08-06 to 2026-08-14 | `partial` | Finish canonical-workbook migration | Re-audit the remaining `master_config.xlsx` and legacy fallback call sites against current code, migrate production paths to `config/outlook_mappings_master.xlsx`, and isolate deliberate compatibility behavior. |
| MAPQ-017 | P2 | 2026-08-08 to 2026-08-16 | `not_started` | Build a compact researcher review workbook | Produce a review-only workbook with source/target definitions, cardinality, non-zero examples, exception context, suggested action, owning sheet/row, and decision-log link. It must not write approvals into the canonical workbook. |
| MAPQ-018 | P2 | 2026-08-08 to 2026-08-16 | `not_started` | Make orchestration notebook-safe | Refactor the existing stage orchestration into Jupyter-friendly toggles and functions without duplicating processing logic. Preserve a simple runnable bottom block and explicit repository-root path resolution. |
| MAPQ-019 | P2 | 2026-08-10 to 2026-08-18 | `partial` | Finish LEAP-side no-data checks as coverage permits | Real LEAP result data exist for `20_USA`, `12_NZ`, and `02_BD`. Implement and verify real `leap_side_has_data` behavior for available economies, while clearly reporting that 21-economy completion remains blocked on full output coverage. |
| MAPQ-020 | P2 | Human review by 2026-08-18 | `human_decision` | Resolve ESTO definition-authority review items | Review the four `review_queue` rows, 109 `product_leaks`, unknown/unclassified definitions, and low-confidence `Others` categories. Preserve citations and rejected interpretations. |
| MAPQ-021 | P2 | 2026-08-12 to 2026-08-19 | `human_decision` | Decide additive frontier ownership | Resolve `CROSS-002`: one additive frontier versus several named frontiers, and which dashboard views require each. Mapping outputs should publish validated metadata; dashboards should not infer hierarchy from display labels. |
| MAPQ-022 | P0 | 2026-08-18 to 2026-08-24 | `not_started` | Run a handover dry run and freeze the queue | Have a colleague or clean agent session follow the runbook from a fresh checkout, record every missing assumption, fix the documentation, produce a final clean baseline, and label every remaining item with owner, risk, next action, and last verified date. |

## Four-week handover sequence

### Week 1: 2026-07-28 to 2026-08-03

- Stabilize git state and reconcile the five worktrees.
- Integrate the completed output/safety work.
- Establish a clean, reproducible pipeline baseline.
- Start prompt archival and correct the documentation index.

### Week 2: 2026-08-04 to 2026-08-10

- Triage semantic mapping issues from the new baseline.
- Reconcile reliability/diagnostic design with what has already landed.
- Draft the runbook, workbook guide, and cross-repository contract.
- Make explicit human decisions on rollup modes where evidence is ready.

### Week 3: 2026-08-11 to 2026-08-17

- Complete the main handover documents.
- Recheck the deferred ESTO Extended findings on 2026-08-17.
- Resolve or explicitly defer canonical migration, review-workbook, and
  notebook workflow work.
- Confirm which work in the sibling repositories is local-only versus remotely
  recoverable.

### Week 4: 2026-08-18 to 2026-08-24

- Perform a clean-checkout handover rehearsal.
- Fix documentation gaps found by the rehearsal.
- Freeze a final dated queue and known-risks list.
- Ensure every unmerged branch/worktree and unpushed commit has an explicit
  disposition and named owner.

## Queue maintenance rules

1. Update `Last verified` evidence whenever a status changes.
2. Include the commit, worktree, run ID, or human decision that supports the
   status.
3. Never silently roll an old prompt's row counts forward to a new baseline.
4. Move completed prompts to `docs/archive/`; keep active prompts narrow and
   independently runnable.
5. Keep cross-repository tasks in this queue only when the dependency affects
   mapping ownership or handover. Implementation-specific dashboard and
   initialization work belongs in those repositories' own queues.
6. At the end of each week, record what moved to `complete_on_master`, what is
   blocked, and what must be descoped before handover.
