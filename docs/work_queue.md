# LEAP mappings work queue and handover plan

**Snapshot date:** 2026-07-28
**Last full verification:** 2026-07-28 (git state, worktrees, workbooks, code, and links re-checked directly)
**Planning horizon:** four weeks, through 2026-08-24
**Owner repository:** `leap_mappings`
**Related repositories:** `leap_dashboard`, `leap_initialisation`

## MAPQ-039 — Restore Energy Balance-only Production products

**Status: complete and verified end to end 2026-08-03.**

The generated LEAP pair registry previously derived its global Energy Balance
product catalogue only from fuels below `Demand\All demand aggregated`. This
excluded observed, non-zero `Production` pairs for Additives and oxygenates,
Hydro, Natural gas liquids, Nuclear, Solar photovoltaics, and Wind. The USA
dashboard consequently omitted the latter five from post-base-year production.

Registry version 5 adds these report-only products to the fixed balance
catalogue. The focused regression test passes, and the refreshed compiler and
canonical workbook contain all six `Production` relationships on both the ESTO
and Ninth axes. The canonical workbook was promoted through an explicitly
user-authorized `openpyxl` fallback after the bundled `@oai/artifact-tool`
runtime proved unavailable. Stages 1–3 then completed with 100% mapped-value
preservation in all ten scope/source combinations. The rerendered USA Supply
chart contains the expected 2023 Reference values for Hydro, Wind, Nuclear,
Natural gas liquids, and Solar photovoltaics; 54 focused dashboard tests and
publication readiness passed.

## MAPQ-040 — Commit verified ESTO Transfers history fix

**Status: complete; committed 2026-08-03 separately from the concurrent
APEC anchor-validation and pair-registry work, as instructed below.**

The ESTO exact-row extractor dropped the subtotal parent `08 Transfers`, even
though some economies store their published transfer observations on that
parent while the `08.01-08.99` children are zero or incomplete. The pending
change retains that parent flow, adds a focused regression test, and documents
the source-data exception in `mappings_system.md` and
`special_rules_and_design_decisions.md`.

Real-data verification completed on 2026-08-03: the canonical Common ESTO
comparison was rebuilt, USA ESTO transfer rows now cover 1990-2023, the
dashboard chart shows ESTO through 2022 and LEAP from 2023, 42 dashboard tests
and 3 focused mapping tests passed, publication readiness passed for all 21
economies, and page-noise analysis reported zero flagged pages. Commit only
the transfer-retention hunks and their test/documentation changes; do not
include the concurrent APEC anchor-validation or pair-registry work.

This is the controlling queue for current work and handover preparation. It
reconciles repository state, worktrees, recent commits, the older
`improvement_todo.md`, active prompt files, and the documentation audit in
[`documentation_audit_20260728.md`](documentation_audit_20260728.md).
Cross-repository ownership, data contracts, and refresh order live in
[`cross_repository_handover_index.md`](cross_repository_handover_index.md).

## Same-day current-state addendum

Verified after commit `94c8e90` and before the documentation-disposition
commit. This addendum supersedes contradictory repository-state, prompt-state,
and completed-documentation claims later in this dated queue; the detailed
task rationale remains preserved below.

| Area | Current evidence and status |
|---|---|
| Local/remote | Local `master` is 24 commits ahead of `origin/master`, not four. It is not behind. MAPQ-002 remains an unpushed-history risk. |
| Dirty checkout | The user-owned modified mapping helper, canonical workbook, cleanup-candidate document, review workbook, Office recovery files, `.codex*`, and `node_modules/` remain outside this documentation pass. Do not infer a clean baseline from this checkout. |
| MAPQ-003 | **Complete on local master:** output-contract implementation/certification landed in `1f48790` and `4f41ecc`. A fresh post-change end-to-end baseline is still required by MAPQ-005. |
| MAPQ-004 | **Still not integrated:** `git cherry` reports `+` for `add312d` and `8b169de`. The later `eb3a293` ESTO Extended rollup identity fix is related but does not make those two branch commits patch-equivalent. |
| MAPQ-006 | The layered handover set and exhaustive disposition register now exist. Remaining work is maintenance and the clean-checkout rehearsal, not creation of the original five-document set. |
| MAPQ-007 | Core ESTO Extended mapping/delta work advanced through `947742d`, `afec8f6`, `db67012`, `1a85c2b`, `a16ac13`, `8adfaa5`, `af067c9`, and `c578829`. Uncommitted delta-integration code exists in a separate worktree, so this item is not complete. |
| MAPQ-013 | Compression and verified quarantine work landed (`34858fe`, `a16ac13`), but the user-owned `results_folder_cleanup_candidates.md` edit and the blocked missing-row comparison remain open. |
| MAPQ-014/015 | The maintained handover guides and data-contract reference landed in `861dba5`; the older `cross_repository_handover_index.md` is now a dated evidence snapshot. MAPQ-022 is still needed to prove the guides from a clean checkout. |
| Prompt inventory | Completed and superseded prompt packs were preservation-archived in the exhaustive documentation pass. `docs/prompts/AGENTS.md` is the current active inventory. |
| MAPQ-026 | `codebase/run_mapping_pipeline_delayed.ps1` was removed by `ac33daa`. The remaining variant-workbook decision concerns review evidence/column recovery and the active MAPQ-010 prompt, not a live delayed runner. |

See
[`documentation_disposition_20260728.md`](documentation_disposition_20260728.md)
for the file-by-file documentation evidence. When updating an individual MAPQ
item, fold this addendum into that item's body rather than adding another
parallel status layer.

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

## Verified repository state — 2026-07-28

All statements below were re-derived from git and the working tree on
2026-07-28; none are carried forward from older notes.

- Local `master` is **seven commits ahead of `origin/master`** (`5c960c9`):
  `947742d`, `2e39cca`, `34858fe`, `76e280f`, then this audit's three —
  `5bb66f0` (verified audit + cross-repository index), `6dc0ee5` (unit A
  demand-scope restructure), `78c3f8d` (unit D, four workbook deletions).
- The main checkout started dirty with 17 paths across **five independent
  units** (A–E, see MAPQ-001). After the 2026-07-28 sign-off it holds **three
  tracked changes**: the draft LNG fallback (unit B), the results-cleanup doc
  (unit C), and this queue; plus five untracked environment paths (unit E).
- **No Python process was running** at snapshot time. No pipeline run is in
  flight, so git and results state can be treated as static.
- **Excel workbook lock:** `config/~$outlook_mappings_master.xlsx` was present
  at the start of this audit (165 bytes, 2026-07-28 10:21) and has since been
  released. That lock file is the mechanism behind the `_rebuilt` fallback
  CSVs — current code writes a `_rebuilt` variant when the canonical output is
  locked, which is why `_rebuilt` files are **not** evidence of a stale manual
  copy. Confirm the workbook is closed before any run intended as a baseline.
- **Five non-master worktrees exist and all five are clean** (`git status
  --porcelain` empty in each). A sixth branch has no worktree.
- `leap_dashboard` local `master` is **55 commits ahead** of its remote, with one
  modified file. `leap_initialisation` local `master` is **142 commits ahead** of
  its remote, clean, with **nine worktrees** (three of which sit at the initial
  commit). Those remote gaps and stray worktrees are cross-repository handover
  risks; this queue does not authorize pushing or pruning either repository.

### Worktree and branch reconciliation

| Branch / worktree | Verified evidence 2026-07-28 | Classification | Required action |
|---|---|---|---|
| `master` (main checkout) | 4 commits ahead of `origin/master`; dirty checkout; workbook lock file present | `complete_unpushed` + `partial_uncommitted` | Separate completed commits from draft work (MAPQ-001, MAPQ-002). |
| `codex/output-contract-phase-2` (`4f53662`) | Historical implementation worktree; its contract commits have been superseded by the integrated `master` implementation | `superseded_cleanup` | Retain only until normal branch/worktree cleanup confirms no unique changes remain. |
| `claude/zen-pike-39adbf` (`add312d`) | Clean; 1 commit ahead, 3 behind | `complete_in_worktree` | Integrate the empty-partial-coverage guard (MAPQ-004). |
| `codex/esto-rollup-source-identity-guard` (`8b169de`) | Clean; 1 commit ahead, 5 behind; `git cherry master` reports **`+`** (not on master); touches `non_expanding_rollups.py` (+161), `run_mapping_pipeline.py` (+20), `tests/test_non_expanding_rollups.py` (+151) | `complete_in_worktree` | Integrate the regression guard (MAPQ-004). The `_source_identity` symbols on `master` are in `apply_partitioned_common_esto.py` and are a **different** cache-identity concept — they do not supersede this guard. |
| `claude/mapping-diagnostics-dashboard-a55009` (`7de6cd1`) | Clean; 6 commits ahead, 5 behind; contains its own copy of the guard (`23cd8b0`) and a workbook merge already landed differently as `947742d` | `partial_reconciliation` | Do not merge wholesale (MAPQ-008). **Its commit message "record the source-identity guard as merged to master" is factually wrong** — verified above. Salvage only the deferred-work docs. |
| `codex/investigate-anchor-validator-memory` (`65df95e`) | Clean; 1 commit ahead, 18 behind; `git cherry master` reports **`-`** (patch-equivalent already on master as `03c9405`) | `superseded_cleanup` | Confirm and remove the stale worktree/branch through the normal safe cleanup process (MAPQ-023). |
| `worktree-agent-abcb30bdd765f323c` (`09ed7fe`) | Local branch at the repository's initial commit; 234 behind; no active worktree | `superseded_cleanup` | Confirm it carries no work, then delete the stale branch (MAPQ-023). |

### Uncommitted work classification (MAPQ-001 detail)

Verified by reading each diff. These must not be committed as one change.

| Unit | Paths | Assessment |
|---|---|---|
| **A — demand-scope restructure** ✅ **committed `6dc0ee5`** | `config/source_coverage_scopes.json`, `config/all_demand_aggregated_components.json`, `docs/rollup_rules_system.md`, `docs/source_coverage_audit.md` | Coherent and self-consistent: `Freight road` + `Passenger road` collapse into `Road`; `International transport` is added as a separate component. Human sign-off given 2026-07-28. Verified before commit: both JSON files parse, the six declared components match the documentation, 66 tests pass, and LEAP branch names in `config/leap_results_expected_sheets.json` are deliberately unchanged. **Requires a pipeline rerun to reach outputs — MAPQ-005.** |
| **B — draft qualitative LNG fallback** | `codebase/mapping_tools/build_missing_mapped_esto_rows.py` | Adds `LNG_TRADE_DIRECTION` (21 economies) and `_qualitative_lng_shares()`. Its own comment says "Needs a human pass to confirm/correct before relying on it for a real run." **Still uncommitted. Draft; do not commit as production behaviour.** |
| **C — results cleanup verification pass** | `docs/results_folder_cleanup_candidates.md` | Documentation-only. Records the 2026-07-27 verification, corrects the `_rebuilt` classification (it is an automatic lock fallback, not a manual copy), and removes `missing_mapped_esto_rows/` from the quarantine batch. **Still uncommitted.** Committable on its own once reviewed; fold into MAPQ-013. |
| **D — non-canonical workbook deletions** ✅ **four of five committed `78c3f8d`** | 5 deleted `config/outlook_mappings_master*.xlsx` variants | Human sign-off given 2026-07-28. Four deleted after verifying no code references them: `... new.xlsx`, `... new_with_other_branches_review.xlsx`, `... v2.xlsx`, `..._esto_extended_test.xlsx`. **`outlook_mappings_master_combined_esto.xlsx` was restored, not deleted** — it has live dependencies. See MAPQ-026. |
| **E — environment noise** | `config/9098DA00`, `config/FDC59700`, `config/~$outlook_mappings_master.xlsx`, `.codex/`, `.codex-remote-attachments/`, `node_modules/` | Not project content. The two hex files are Office crash-recovery blobs; `~$...` is the live Excel lock. They appear as untracked because `.gitignore:205` `!config/*` un-ignores everything directly under `config/`. Fix with a narrow re-ignore (MAPQ-024). |

## Prioritized queue

Index. Full detail for each ID follows. `Wk` is the target handover week
(W1 = 2026-07-28→08-03, W2 = 08-04→08-10, W3 = 08-11→08-17, W4 = 08-18→08-24).

| ID | Pri | Status | Owner repo | Depends on | Wk | Last verified |
|---|---|---|---|---|---|---|
| MAPQ-001 | P0 | `partial_uncommitted` | `leap_mappings` | — | W1 | 2026-07-28 |
| MAPQ-002 | P0 | `complete_unpushed` | `leap_mappings` | MAPQ-001 | W1 | 2026-07-28 |
| MAPQ-003 | P0 | `complete_unpushed` | `leap_mappings` | MAPQ-001 | W1 | 2026-07-28 |
| MAPQ-004 | P0 | `complete_in_worktree` | `leap_mappings` | MAPQ-001 | W1 | 2026-07-28 |
| MAPQ-005 | P0 | `partial` | `leap_mappings` | MAPQ-001…004, MAPQ-024 | W1–W2 | 2026-07-28 |
| MAPQ-006 | P0 | `partial` | `leap_mappings` | — | W1–W4 | 2026-07-28 |
| MAPQ-007 | P1 | `partial` | `leap_mappings` | MAPQ-003, MAPQ-005 | W2 | 2026-07-28 |
| MAPQ-008 | P1 | `partial_reconciliation` | `leap_mappings` | MAPQ-004 | W3 | 2026-07-28 |
| MAPQ-009 | P1 | `partial` | `leap_mappings` | MAPQ-005 | W2 | 2026-07-28 |
| MAPQ-010 | P1 | `not_started` | `leap_mappings` | MAPQ-005 | W2 | 2026-07-28 |
| MAPQ-011 | P1 | `paused` | `leap_mappings` | MAPQ-005 | W2–W3 | 2026-07-28 |
| MAPQ-012 | P1 | `partial` | `leap_mappings` | MAPQ-003, MAPQ-009 | W2–W3 | 2026-07-28 |
| MAPQ-013 | P1 | `partial` | `leap_mappings` | MAPQ-003, MAPQ-005 | W2–W3 | 2026-07-28 |
| MAPQ-014 | P1 | `partial` | `leap_mappings` | MAPQ-005, MAPQ-015 | W3 | 2026-07-28 |
| MAPQ-015 | P1 | `partial` | `leap_mappings` | MAPQ-003 | W3 | 2026-07-28 |
| MAPQ-016 | P2 | `partial` | `leap_mappings` | MAPQ-001 | W3 | 2026-07-28 |
| MAPQ-017 | P2 | `not_started` | `leap_mappings` | MAPQ-009 | W3 | 2026-07-28 |
| MAPQ-018 | P2 | `not_started` | `leap_mappings` | MAPQ-005 | W3 | 2026-07-28 |
| MAPQ-019 | P2 | `not_started` | `leap_mappings` + `leap_initialisation` | MAPQ-015 | W3 | 2026-07-28 |
| MAPQ-020 | P2 | `human_decision` | `leap_mappings` | MAPQ-009 | W3 | 2026-07-28 |
| MAPQ-021 | P2 | `human_decision` | `leap_mappings` + `leap_dashboard` | MAPQ-015 | W3 | 2026-07-28 |
| MAPQ-022 | P0 | `not_started` | `leap_mappings` | all above | W4 | 2026-07-28 |
| MAPQ-023 | P1 | `superseded_cleanup` | `leap_mappings` | MAPQ-004, MAPQ-008 | W1–W2 | 2026-07-28 |
| MAPQ-024 | P2 | `not_started` | `leap_mappings` | — | W1 | 2026-07-28 |
| MAPQ-025 | — | **delegated** to the sibling repos' own handover audits | `leap_dashboard` + `leap_initialisation` | — | n/a | 2026-07-28 |
| MAPQ-026 | P2 | `human_decision` | `leap_mappings` | MAPQ-010, MAPQ-027 | W2 | 2026-07-28 |
| MAPQ-027 | P2 | `human_decision` | `leap_mappings` | MAPQ-005 | W2 | 2026-07-28 |
| MAPQ-028 | P2 | `deferred_active_processes` | `leap_mappings` + `leap_initialisation` + `leap_dashboard` | MAPQ-015, MAPQ-016, MAPQ-027 | W3 | 2026-07-28 |
| MAPQ-029 | P2 | `review_in_progress` | `leap_mappings` + `leap_initialisation` | MAPQ-005, MAPQ-007 | W3 | 2026-07-28 |
| MAPQ-030 | P1 | `contract_and_review_ready` | `leap_mappings` | MAPQ-029, MAPQ-031 | human approval | 2026-07-28 |
| MAPQ-031 | P1 | `review_in_progress` | `leap_mappings` + `leap_initialisation` | MAPQ-007 | W1-W3 | 2026-07-28 |
| MAPQ-032 | P1 | `ready_for_implementation` | `leap_mappings` | MAPQ-001 | W2 | 2026-07-28 |
| MAPQ-033 | P2 | `blocked_pending_dataset_selection` | `leap_mappings` | multi-dataset M1-M6 | W3 | 2026-07-29 |
| MAPQ-034 | P2 | `production_validation_complete_review_debt_open` | `leap_mappings` | MAPQ-005, MAPQ-029, MAPQ-031 | promoted and run end to end; semantic and QA debt remains | 2026-07-30 |
| MAPQ-035 | P2 | `deferred_until_current_row_work_finishes` | `leap_mappings` + `leap_initialisation` | MAPQ-031, MAPQ-034 | after current detailed-row work | 2026-07-29 |
| MAPQ-036 | P2 | `queued_after_separate_axis_promotion` | `leap_mappings` | MAPQ-034 | after production validation | 2026-07-30 |
| MAPQ-037 | P1 | `review_in_progress` | `leap_mappings` + `leap_dashboard` | MAPQ-034 | current APEC anchor-validation work | 2026-08-03 |

---

### MAPQ-001 — Stabilize the main checkout

- **Priority / status / week:** P0 · `partial_uncommitted` · W1
- **Owner repo:** `leap_mappings` · **Depends on:** —
- **Evidence (2026-07-28):** `git status --porcelain` originally showed 6 modified, 5 deleted, 6 untracked paths, classified into units A–E above. Diffs read individually. **Units A and D were signed off and committed on 2026-07-28** (`6dc0ee5`, `78c3f8d`), less the one workbook held back as MAPQ-026.
- **Remaining:** unit B (draft LNG table), unit C (cleanup doc), unit E (environment noise).
- **Next action:** Commit unit C on its own under MAPQ-013; move unit B to a dedicated branch or leave it explicitly parked with a note; apply MAPQ-024 for unit E.
- **Completion criteria:** `git status --short` is either clean or every remaining path has a named owner and a queue ID recorded here.

### MAPQ-002 — Reconcile local `master` with `origin/master`

- **Priority / status / week:** P0 · `complete_unpushed` · W1
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-001
- **Evidence (2026-07-28):** Four commits ahead — `947742d` (canonical workbook merge of ESTO Extended rows), `2e39cca` (demand/power branch-tab reading), `34858fe` (compressed recurring outputs; 14 files incl. `result_storage.py` and tests), `76e280f` (handover queue). `origin/master` at `5c960c9`.
- **Next action:** Review the four commits, then push through the user's normal repository process. Pushing is **not** authorized by this audit.
- **Completion criteria:** The intended remote contains the four commits, or the handover explicitly records why it does not and where the only copy lives.

### MAPQ-003 — Integrate the Common ESTO output contract

- **Priority / status / week:** P0 · `complete_unpushed` · W1
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-001
- **Evidence (2026-07-28):** `master` now contains `1f48790` (contract implementation) and `4f41ecc` (certified publication). The latter records 56 focused tests passed and 320 broader tests passed with 1 skipped and 4 unrelated pre-existing/environment failures. Current `results/common_esto/` artifacts predate those commits and contain no contract manifest/fact/metadata generation.
- **Next action:** After MAPQ-001 and the Stage 3 safety work are settled, run a QA-successful Stage 3 publication, verify the manifest hashes, and perform one dashboard render with explicit contract selection.
- **Completion criteria:** Contract code and tests on `master`; dashboard-required identities, keys, years, values, booleans, manifest hashes, and rollback behaviour confirmed against the consumers listed in the cross-repository index. The exact ESTO Extended delta stays non-default unless separately approved.

### MAPQ-004 — Integrate two small Stage 3 safety fixes

- **Priority / status / week:** P0 · `complete_in_worktree` · W1
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-001
- **Evidence (2026-07-28):** `claude/zen-pike-39adbf` (`add312d`, empty partial-coverage candidate guard) and `codex/esto-rollup-source-identity-guard` (`8b169de`) are both clean and both report `+` under `git cherry master` — neither is on `master`. The guard adds 334 lines across `non_expanding_rollups.py`, `run_mapping_pipeline.py`, a README line, and a 151-line test module.
- **Next action:** Integrate both, then delete the two source branches once merged.
- **Completion criteria:** Both fixes on `master` with their focused tests passing, or a written comparison proving a later guard supersedes one of them. Do not accept the `master` `_source_identity` helpers in `apply_partitioned_common_esto.py` as that proof — verified to be a different concept.

### MAPQ-005 — Produce one clean current pipeline baseline

- **Priority / status / week:** P0 · `partial` · W1–W2
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-001, MAPQ-002, MAPQ-003, MAPQ-004, MAPQ-024
- **Evidence (2026-07-28):** `codebase/run_mapping_pipeline.py` exposes `run_stage_0/1/2`, `run_leap_parse`, `run_leap_to_esto`, `run_ninth_to_esto`, `run_esto_exact_rows`, `run_esto_extended_exact_rows`, `run_data_convert`, `run_stage_3`. Current `results/common_esto/` mixes 2026-07-27 and 2026-07-28 artifacts with a 2026-07-13 `_rebuilt` file — it is not a single coherent run. An Excel lock on the master workbook is currently present.
- **Next action:** Close the workbook in Excel, settle MAPQ-001…004, then run maintenance plus Stages 1–3 in one pass.
- **Completion criteria:** A recorded run ID with inputs, commit SHA, workbook hash/state, per-stage durations, validation counts, and a split between blocking and review-only findings. A zero exit code alone is not completion.

### MAPQ-006 — Establish documentation control

- **Priority / status / week:** P0 · `partial` · W1–W4 (weekly)
- **Owner repo:** `leap_mappings` · **Depends on:** —
- **Evidence (2026-07-28, preservation audit update):** `docs/README.md` links this queue and the audit, labels `improvement_todo.md` as historical, and now links a real `diagnostic_file_review_signals.md` status page. That page preserves the path proposed by the historical cleanup handoff without claiming the planned file-by-file consolidation study is finished. A full tracked-Markdown relative-link scan now reports zero broken links.
- **Next action:** Continue the sequence in `documentation_audit_20260728.md` §"Documentation cleanup sequence"; distinguish live instructions from explicitly dated/archived evidence, and re-date this queue at each weekly review.
- **Completion criteria:** Active docs contain only current instructions or clearly dated historical context; `docs/prompts/` holds only active prompts; zero broken relative links.

### MAPQ-007 — Reconcile ESTO Extended work

- **Priority / status / week:** P1 · `partial` · W2
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-003, MAPQ-005
- **Evidence (2026-07-28):** Design and much of the implementation are on `master` (`947742d`, `8750f9f`, `c810cfa`, `79b79c7`). `results/mapping_relationships/esto_extended_results_exact_rows.csv.gz` exists (23 MB, 2026-07-27). Output-contract/delta work is in `codex/output-contract-phase-2`; deferred structure docs are on `claude/mapping-diagnostics-dashboard-a55009`.
- **Next action:** Write one current status note.
- **Completion criteria:** A single document separating production behaviour, experimental behaviour, missing Common ESTO structure coverage, and dashboard consumption — replacing `esto_extended_dataset_design.md` as the current reference.

### MAPQ-008 — Salvage and retire the diagnostics-dashboard branch

- **Priority / status / week:** P1 · `partial_reconciliation` · W3
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-004
- **Evidence (2026-07-28):** `claude/mapping-diagnostics-dashboard-a55009` at `7de6cd1`, 6 ahead / 5 behind, clean. `cf97f88` duplicates the workbook merge landed as `947742d`; `23cd8b0` duplicates the guard in MAPQ-004; `7de6cd1`'s claim that the guard is merged to master is **verified false**. Unique value: `2095365` and `a5c9ea0` (deferred Extended coverage docs, flagged for a 2026-08-17 recheck).
- **Next action:** Cherry-pick only the two docs commits; do not merge the branch.
- **Completion criteria:** The deferred-work docs exist on `master` with corrected status text, and the branch is deleted or explicitly retained with a written reason.

### MAPQ-009 — Re-triage semantic mapping findings

- **Priority / status / week:** P1 · `partial` · W2
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-005
- **Evidence (2026-07-28):** Diagnostic outputs exist but predate a coherent run (see MAPQ-005). `config/mapping_issue_exception_sets.xlsx` holds the curated allowlists that scope this work.
- **Next action:** From the MAPQ-005 baseline only, group actionable partial coverage, non-zero unmapped LEAP branches, presence conflicts, and non-ESTO hierarchy edges by semantic cause.
- **Completion criteria:** A reviewed, bounded decision list with human rules recorded **before** any workbook edit. Zero raw diagnostic rows is not the target.

### MAPQ-010 — Review `NON_EXPANDING` versus `DETACHED` rollups

- **Priority / status / week:** P1 · `not_started` · W2
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-005
- **Evidence (2026-07-28):** `docs/prompts/review_non_expanding_vs_detached_rollups_prompt.md` is present and active; no implementation commits reference it.
- **Next action:** Execute that prompt against the MAPQ-005 baseline.
- **Completion criteria:** Each affected rollup classified, human decisions documented in `special_rules_and_design_decisions.md`, only the narrowest configuration changed, and affected validation rerun.

### MAPQ-011 — Resume mirror-row-gap exception curation

- **Priority / status / week:** P1 · `paused` · W2–W3
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-005
- **Evidence (2026-07-28, verified numerically):** The exception mechanism is on `master` (`cf740de`), and `config/mapping_issue_exception_sets.xlsx` sheet `source_mismatch_allowed` holds **456 rows = 455 curated NINTH self-inconsistencies + header**, matching commit `6bf8f69`. Consumers: `source_parent_anchor_validation.py` (`DATA_QUALITY_EXCEPTION_SHEET`) and `verify_ninth_mirror_row_candidates.py`. Note the sheet lives in `mapping_issue_exception_sets.xlsx`, **not** in `outlook_mappings_master.xlsx` (which has 14 sheets, none of them exception sheets).
- **Next action:** Resume from `docs/prompts/mirror_row_gap_exception_curation_handoff_20260727.md` only in a clean window with current outputs and no concurrent pipeline mutation.
- **Completion criteria:** As defined in that handoff document, against MAPQ-005 outputs.

### MAPQ-012 — Finish reliability attribution and diagnostic consolidation design

- **Priority / status / week:** P1 · `partial` · W2–W3
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-003, MAPQ-009
- **Evidence (2026-07-28):** `docs/prompts/data_reliability_flag_and_diagnostic_consolidation_design_20260723.md` predates curated exceptions, grouped validation, compressed artifacts (`34858fe`), output contracts, and the dashboard health report.
- **Next action:** Reconcile the 2026-07-23 design against what has actually landed before writing more code.
- **Completion criteria:** A written decision on which flags belong in mapping outputs versus dashboard presentation, and the superseded design archived.

### MAPQ-013 — Complete reversible results cleanup and storage policy

- **Priority / status / week:** P1 · `partial` · W2–W3
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-003, MAPQ-005
- **Evidence (2026-07-28):** Compression work is on local `master` (`34858fe`, adds `result_storage.py` and `docs/results_output_storage.md`). The uncommitted unit C verification pass confirms three tree-artifact groups are safe to quarantine and removes `missing_mapped_esto_rows/` from that batch. `results/common_esto/` still holds a 952 MB `common_esto_comparison_data.csv` and stale 2026-07-13 artifacts.
- **Next action:** Commit unit C, then execute only the confirmed quarantine batch.
- **Completion criteria:** Quarantine moves recorded in `docs/archive_log.md` in the same commit; no hard deletion of any broad `results/` path; the `_rebuilt` fallback documented as lock-driven rather than stale.

### MAPQ-014 — Write the technical handover set

- **Priority / status / week:** P1 · `partial` · W3
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-005, MAPQ-015
- **Evidence (2026-07-28):** The progressive-disclosure set now exists under `docs/handover/`: Level 1 start page, Level 2 connected-system and mapping guides, producer/consumer contract, and Level 3 cross-repository/mapping runbooks. It links rather than copies `mappings_system.md`, `guide_outlook_mappings_master.md`, the initialisation check/rule guides, and dashboard-owned configuration. The remaining completion gate is the clean-checkout rehearsal, not more first-draft files.
- **Next action:** Execute MAPQ-022 from the new runbooks, record every undocumented dependency, and correct any gap before freezing the set.
- **Completion criteria:** All five exist, link to canonical detail rather than copying it, and survive the MAPQ-022 rehearsal without the rehearser needing to ask a question that the set should have answered.

### MAPQ-015 — Define the cross-repository ownership boundary

- **Priority / status / week:** P1 · `partial` · W3
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-003
- **Evidence (2026-07-28):** [`handover/cross_repository_data_contracts.md`](handover/cross_repository_data_contracts.md) supersedes the dated index as the maintained contract and is linked from all three repository README/doc indexes. It was checked against current producer headers, the integrated v1 contract schemas/hashes, dashboard strict opt-in loaders and provenance handling, initialisation templates, and real run outputs.
- **Next action:** Validate the first published v1 generation during the three-repository clean-checkout rehearsal and record the selected contract run ID in the dashboard evidence.
- **Completion criteria:** The index is confirmed by all three repositories and referenced from each repository's `AGENTS.md`.

### MAPQ-016 — Finish canonical-workbook migration

- **Priority / status / week:** P2 · `partial` · W3
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-001
- **Evidence (2026-07-28):** `AGENTS.md` designates `config/outlook_mappings_master.xlsx` canonical and `config/leap_mappings.xlsx` / `config/master_config.xlsx` legacy. Five non-canonical `outlook_mappings_master*` variants are currently deleted-but-uncommitted (unit D).
- **Next action:** Re-audit remaining legacy call sites against current code before committing unit D.
- **Completion criteria:** Production paths read only the canonical workbook; deliberate compatibility fallbacks isolated and commented.

### MAPQ-017 — Build a compact researcher review workbook

- **Priority / status / week:** P2 · `not_started` · W3
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-009
- **Evidence (2026-07-28):** No such workbook exists in `config/` or `results/`.
- **Next action:** Specify columns before building.
- **Completion criteria:** A review-only workbook with source/target definitions, cardinality, non-zero examples, exception context, suggested action, owning sheet/row, and decision-log link. It must not write approvals into the canonical workbook.

### MAPQ-018 — Make orchestration notebook-safe

- **Priority / status / week:** P2 · `not_started` · W3
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-005
- **Evidence (2026-07-28):** `run_mapping_pipeline.py` already exposes per-stage functions and resolves `REPO_ROOT`, but has no `#%%` cell structure, unlike the pattern `AGENTS.md` prescribes.
- **Next action:** Refactor into notebook cells and toggles without duplicating processing logic.
- **Completion criteria:** Runs unchanged as a script and cell-by-cell in a notebook from an arbitrary CWD.

### MAPQ-019 — Finish LEAP-side no-data checks as coverage permits

- **Priority / status / week:** P2 · `not_started` (corrected from `partial`) · W3
- **Owner repo:** `leap_mappings`, data owned by `leap_initialisation` · **Depends on:** MAPQ-015
- **Evidence (2026-07-28, corrected):** `codebase/mapping_tools/build_no_data_mapping_rows.py:75,89` sets `df["leap_side_has_data"] = pd.NA` with the comment "not yet checkable" — **there is no implementation to be partial about**. LEAP balance exports actually available: `leap_initialisation/data/leap balances exports/` holds `00_APEC`, `01_AUS`, `02_BD`, `12_NZ`, `20_USA`; `leap_mappings/data/archive/leap balances exports/` holds only `02_BD` and `20_USA` plus `data/usa_leap_balance_long.csv`. The earlier "20_USA, 12_NZ, 02_BD" claim was both incomplete and repo-ambiguous.
- **Next action:** Decide whether `leap_mappings` reads the sibling export tree directly (a new cross-repo input contract — see MAPQ-015) or receives a published extract.
- **Completion criteria:** Real `leap_side_has_data` values for the available economies, with 21-economy completion explicitly reported as blocked on export coverage.

### MAPQ-020 — Resolve ESTO definition-authority review items

- **Priority / status / week:** P2 · `human_decision` · W3
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-009
- **Evidence (2026-07-28):** `config/esto_external_definition_authority_working_set.xlsx` present (52 KB, last written 2026-06-24). Row counts quoted in older notes (4 `review_queue` rows, 109 `product_leaks`) predate the current baseline and must be re-derived, not carried forward.
- **Next action:** Re-count against the MAPQ-005 baseline first, then review.
- **Completion criteria:** Each review row resolved or explicitly deferred, with citations and rejected interpretations preserved.

### MAPQ-021 — Decide additive frontier ownership

- **Priority / status / week:** P2 · `human_decision` · W3
- **Owner repo:** `leap_mappings` + `leap_dashboard` · **Depends on:** MAPQ-015
- **Evidence (2026-07-28):** Open as `CROSS-002` in `docs/special_rules_and_design_decisions.md`. `leap_dashboard/AGENTS.md` already forbids inferring hierarchy from display labels.
- **Next action:** Choose one additive frontier versus several named frontiers, and record which dashboard views require each.
- **Completion criteria:** Decision recorded in the decision log and reflected in published mapping metadata.

### MAPQ-022 — Run a handover dry run and freeze the queue

- **Priority / status / week:** P0 · `not_started` · W4
- **Owner repo:** `leap_mappings` · **Depends on:** all of the above
- **Evidence (2026-07-28):** No rehearsal has been performed.
- **Next action:** See the Week 4 rehearsal definition below.
- **Completion criteria:** A colleague or clean agent session reproduces a baseline from a fresh clone using only the MAPQ-014 documents; every missing assumption is recorded and fixed; the final queue labels every remaining item with owner, risk, next action, and last-verified date.

### MAPQ-023 — Retire superseded branches and stale worktrees

- **Priority / status / week:** P1 · `superseded_cleanup` · W1–W2
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-004, MAPQ-008
- **Evidence (2026-07-28):** `codex/investigate-anchor-validator-memory` is patch-equivalent to `03c9405` on `master` (`git cherry` reports `-`). `worktree-agent-abcb30bdd765f323c` is a branch at the initial commit, 234 behind, with no worktree. Both worktrees are clean.
- **Next action:** Confirm with the user, then remove — this audit does not delete worktrees or branches.
- **Completion criteria:** Only `master` plus worktrees for genuinely active work remain, matching the established worktree-hygiene policy.

### MAPQ-024 — Close the `config/` gitignore gap

- **Priority / status / week:** P2 · `not_started` · W1
- **Owner repo:** `leap_mappings` · **Depends on:** —
- **Evidence (2026-07-28):** `.gitignore:205` `!config/*` un-ignores every file directly under `config/`, so Office crash-recovery blobs (`config/9098DA00`, `config/FDC59700`) and the Excel owner-lock file (`config/~$outlook_mappings_master.xlsx`) permanently pollute `git status`. `docs/guide_outlook_mappings_master.md` already documents them as safe to ignore.
- **Next action:** Add narrow re-ignore rules after the negation (`config/~$*`, plus a rule for 8-hex-character extensionless blobs), and gitignore `.codex/`, `.codex-remote-attachments/`, and `node_modules/`.
- **Completion criteria:** A clean `git status` in an otherwise-clean checkout with the workbook open in Excel.

### MAPQ-025 — Sibling-repository remote and worktree divergence · **delegated**

- **Priority / status / week:** P1 · `human_decision` · **owned elsewhere**
- **Owner repo:** `leap_dashboard` and `leap_initialisation` — **not this queue**
- **Decision, 2026-07-28:** These findings are **handed to the handover audits running in those repositories themselves.** This queue records the evidence so nothing is lost in transit, but does not track the work or its completion. Do not re-open it here.
- **Evidence to hand over (verified 2026-07-28):**
  - `leap_dashboard` `master` is **55 commits ahead** of `origin/master`, with `codebase/common_esto_dashboard_mapping_diagnostics.py` modified, plus worktrees `claude/nz-leap-9th-discrepancies-b9c5b1` and `codex/output-contract-phase-2`.
  - `leap_initialisation` `master` is **142 commits ahead**, working tree clean, with **nine** worktrees — including three branches still at the initial commit `04b6ec2` (`claude/electricity-interim-use-values-0979e2`, `claude/esto-2026-nz-rows-63f3de`, `claude/feedstock-fuel-share-normalize-0641c7`) and two detached `.codex` worktrees.
  - Combined, **197 commits exist only on this machine.**
- **What this queue still owns:** the *consequence* for mapping handover only — that the cross-repository contract in [`cross_repository_handover_index.md`](cross_repository_handover_index.md) currently depends on two repositories whose only copy is local. That risk is recorded in §6 of that document and is retired when the sibling audits report back, not when this queue acts.

### MAPQ-026 — Decide the fate of `outlook_mappings_master_combined_esto.xlsx`

- **Priority / status / week:** P2 · `human_decision` · W2
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-010
- **Evidence (2026-07-28):** This workbook was part of the unit D deletion set but was **restored rather than deleted**, because it has two live dependencies that the other four variants do not:
  - Historical note: `codebase/run_mapping_pipeline_delayed.ps1` used to pass
    this workbook, but the obsolete runner was removed by `ac33daa`; it is no
    longer a live dependency.
  - `docs/prompts/review_non_expanding_vs_detached_rollups_prompt.md:52` names it as evidence to inspect (sheets `esto_rollup_rules`, `leap_combined_esto`) — that prompt is queued and unstarted as MAPQ-010.
  - Content equivalence has now been **measured** — see [`workbook_variant_row_comparison_20260728.md`](workbook_variant_row_comparison_20260728.md). The canonical workbook is a strict superset on every mapping sheet except `leap_combined_ninth`; the variant's `esto_rollup_rules` sheet is a *subset* of canonical, so it is not needed as MAPQ-010 evidence. Of 231 rows the variant holds and canonical lacks, 228 are inactive (`duplicate_to_remove = True`), 1 is rejected (parent/child CHP double-count), and 2 are blank-fuel fills recommended for adoption.
- **Next action:** (a) decide the two `Gas works plants` blank-fuel fills — see
  MAPQ-027; (b) decide whether the `IS_LEAP_ROLLUP_NAME` values are still
  required and, if so, recover them deliberately; then (c) repoint the
  MAPQ-010 prompt at the canonical workbook and delete or explicitly retain
  the variant. No runner update is required after `ac33daa`.
- **2026-08-02 config audit:** No executable consumer remains across the three
  repositories. The variant is now explicitly marked **review, then delete**
  in `config/README.md`; the outstanding review-value/prompt steps above still
  prevent immediate deletion.
- **Completion criteria:** No script or active prompt references a non-canonical workbook, and either the variant is deleted or its continued existence has a written justification in `docs/special_rules_and_design_decisions.md`.

### MAPQ-027 — Fill two blank `ninth_fuel` values on `leap_combined_ninth`

- **Priority / status / week:** P2 · `human_decision` · W2
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-005 (rerun to validate)
- **Evidence (2026-07-28):** Full working in [`workbook_variant_row_comparison_20260728.md`](workbook_variant_row_comparison_20260728.md) §2. `Gas works plants/Gas works plants` + `Blast furnace gas` and + `Other recovered gases` are active canonical rows with `ninth_sector` set and `ninth_fuel` **blank**. Both axes resolve unambiguously to `02_coal_products` (36/36 and 35/35 other active rows respectively; three sibling fuels in the same block already use that target). Only 3 of 2711 active rows have a blank `ninth_fuel`, so this is an anomaly rather than a convention. No many-to-many risk — the result is many-to-one aggregation.
- **Also in scope:** the third blank-fuel row, `Heat plant interim/Heat plant interim` + `Bitumen` → `09_x_heat_plants`, blank in **both** workbooks; `Bitumen` resolves to `07_x_other_petroleum_products` in 23/23 other active rows.
- **Next action:** Human sign-off, then edit the canonical workbook directly — do **not** import from the variant, which carries 228 unwanted inactive rows.
- **Completion criteria:** Zero active rows with a populated `ninth_sector` and a blank `ninth_fuel`; a pipeline rerun confirms the newly active mappings produce no new validation failures. This is a behaviour change, not a cosmetic edit — the rows are currently inert on the fuel axis.

### MAPQ-028 — Rewrite the workbook Guide and adopt directional mapping-sheet names

- **Priority / status / week:** P2 · `deferred_active_processes` · W3
- **Owner repos:** `leap_mappings`, `leap_initialisation`, and `leap_dashboard` · **Depends on:** MAPQ-015, MAPQ-016, MAPQ-027
- **Human decisions (2026-07-28):**
  - Rewrite `Guide` as a concise workbook entry point and add a separate `Column reference` sheet.
  - Rename `leap_combined_esto` → `leap_to_esto`, `ninth_pairs_to_esto_pairs` → `ninth_to_esto`, and `leap_combined_ninth` → `leap_to_ninth`.
  - Delete the unused legacy sheets `other branches` and `deleted rows - might regret`.
  - Describe `rollup_label_overrides` as **reserved—not currently applied**.
- **Evidence:** The existing Guide contains stale/nonexistent names (`leap_dusplay_names`, `display_name_overrides`), omits five live/reference sheets, predates `ROLLUP_MODE` (`EXPANDING` / `NON_EXPANDING` / `DETACHED`), and describes rollup-context and cardinality behaviour that no longer matches the workbook. Cross-repo search found the three current core sheet names hard-coded throughout active `leap_mappings` and `leap_initialisation` readers; `leap_dashboard` mainly receives them as QA/display labels rather than reading the workbook directly.
- **Why deferred:** All three repositories currently have running work. Do not rename sheets, delete sheets, or change cross-repo loader contracts until those processes have finished and each checkout has a safe implementation window.
- **Documentation checkpoint (2026-08-02):** The Guide/README documentation
  and Mermaid production flow were refreshed without renaming or deleting
  sheets. `other branches` and `deleted rows - might regret` are now marked
  deletion candidates; `rollup_label_overrides` is documented as
  reserved/loaded but not currently applied. The compatibility migration,
  directional renames, physical deletions, and central alias work remain open.
- **Next action:** First introduce central sheet-name constants plus temporary old-name aliases in the active loaders, then update direct readers and tests. Rename/delete workbook sheets only after both producer and consumer code accepts the new contract; update QA `source_sheet` / `mapping_sheet_to_review` labels and maintained documentation in the same coordinated change.
- **Completion criteria:** The canonical workbook has the agreed 13-sheet order; the new Guide and Column reference accurately document every sheet and control column; no runtime code depends only on an old name; active tests in all three repositories pass; the formatting-preservation proof is repeated after the workbook edits; and compatibility aliases have an explicit retirement point.

### MAPQ-029 — Implement detailed power-process remapping and retire aliases

- **Priority / status / week:** P2 · `review_in_progress` · W3
- **Owner repos:** `leap_mappings` and `leap_initialisation` · **Depends on:** MAPQ-005, MAPQ-007
- **Working notes:** [`special_rules_and_design_decisions.md`](special_rules_and_design_decisions.md#map-012-provisional-working-directions-for-detailed-power-processes), MAP-012. These are provisional review directions, not authority that the proposed mappings or current subtotal flags are correct.
- **Scope:** Build the reviewed Electricity Generation, CHP, and Heat plant process mappings from `data/temp/new leap rows.xlsx` on top of `config/outlook_mappings_master todo.xlsx`; route imported electricity to Ninth/ESTO imports; review main-activity/autoproducer coverage, Other + solid biomass boundaries, and stable ESTO Extended power-category identifiers without assuming the current rollups are correct.
- **Alias cleanup:** Treat `Battery` / `Batteries` / `Distributed storage` and `Solar_rooftop` / `Solar rooftop` as non-additive alternatives. Keep safe fallback/alias handling until `leap_initialisation` can migrate models to one canonical branch name, then remove the retired alternatives explicitly.
- **Do not enact during current review:** The canonical mapping workbook and LEAP model structures remain unchanged until the active processes finish and a clean baseline is available.
- **Next action:** On a dedicated branch/worktree, inventory alias co-occurrence by economy, propose the exact rollup rows and mapping-row replacements, and review the plan before editing `config/outlook_mappings_master.xlsx`.
- **Completion criteria:** Imported electricity maps only to `02_imports` / `02 Imports`; aliases cannot double count; Coal-H2 maps within coal power; power-detail mappings have no unresolved post-rollup many-to-many relationships; existing ESTO Extended identifiers remain stable; and maintenance plus Stages 1–3 pass without source-total or parent/child regressions.

### MAPQ-030 — Rebuild subtotal classifications across all mapping sheets

- **Priority / status / timing:** P1 · `contract_and_review_ready` · human hierarchy review and workbook approval required
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-029, MAPQ-031
- **Problem:** Current `leap_is_subtotal`, `ninth_pair_is_subtotal`, and `esto_pair_is_subtotal` values contain historical assumptions and mistakes. Existing QA behaviour and decision-log descriptions must not be read as approval of those classifications.
- **Scope:** Re-derive subtotal status for every row in `leap_combined_esto`, `ninth_pairs_to_esto_pairs`, and `leap_combined_ninth`, including parent/child and rollup-generated targets. Review coherent sibling groups together rather than applying bulk inference one cell at a time.
- **Safety:** Start from a frozen, backed-up workbook; prove formatting-preserving round-trip behaviour first; produce a review table of proposed changes; apply only reviewed classifications; and compare mapping cardinality and additive frontiers before and after.
- **Completion criteria:** Every subtotal flag has an auditable hierarchy basis; no partial sibling group is classified inconsistently; Stage 0 subtotal QA is reviewed rather than merely empty; and Stages 1–3 pass source-total, hierarchy, and frontier checks.
- **2026-07-28 implementation:** Added the adapter-based
  `hierarchy_subtotal_contract_v1`, strict producer/consumer loaders, a separate
  value-conformance member, real `09.06`/`09.08` evidence, and a cell-level
  review workbook. The review currently contains 9,121 canonical pairs, 3,410
  proposed cell changes, 520 current cross-sheet conflicts, and 1,055
  unresolved pairs. No maintained workbook cells were written.
- **2026-07-28 conformance refinement:** ESTO is now the primary numerical
  conformance source. Across every 1990–2023 economy/product context, both
  `09.06 Gas processing plants` and `09.08 Coal transformation` passed all
  55,692 immediate-child comparisons. The bounded 9th check remains secondary
  inherited-source evidence and does not determine structural status.
- **2026-07-28 Common ESTO integration:** The contract now builds Common ESTO
  directly from `common_esto_rows.csv` and typed hierarchy edges, classifies
  the 2,835 actual output pairs, keeps 218 structural pairs separate from 394
  synthetic output-subtotal treatments, and carries 168,509 current-run Common
  ESTO checks in `value_conformance_diagnostics.csv`. The wide output and
  dashboard consume the same classification/contract path.
- **2026-07-29 mapping-master review copy:** Re-ran the current contract against
  an exact SHA-256-recorded MAPQ-030 review base and generated a review-only
  workbook with `CHANGED` annotations on all three mapping sheets. The reusable
  rerun recorded 3,402 proposed subtotal-cell differences: 597 applied, 2,413
  partial or unresolved, and 392 held because of a prior label exception. No mapping
  relationships or maintained workbook cells were changed. See
  [`subtotal_mapping_master_review_20260729.md`](subtotal_mapping_master_review_20260729.md).
- **Next decision:** Review the bounded unresolved queue, beginning with the
  missing full LEAP/fuel hierarchy authority, then explicitly approve coherent
  sibling groups before any workbook application. See
  [`hierarchy_subtotal_contract.md`](hierarchy_subtotal_contract.md).

### MAPQ-031 — Build complete ESTO Extended mappings from the new LEAP rows

- **Priority / status / week:** P1 · `review_in_progress` · W1-W3
- **Owner repos:** `leap_mappings` and `leap_initialisation` · **Depends on:** MAPQ-007
- **Workbook base:** `config/outlook_mappings_master todo.xlsx`. Treat it as the best current starting point, not as proven correct.
- **Source inventories:** `data/temp/new leap rows.xlsx` and `data/temp/new demand branches remapping plan.xlsx`.
- **Rule:** The maintained mapping sheets contain only mappings believed to be correct. Rejected rows are removed, not retained with `duplicate_to_remove = True`.
- **Scope:** Add the missing LEAP-to-ESTO Extended rows first, using the planning sheets as the starting classification. Then complete the corresponding LEAP-to-Ninth and Ninth-to-ESTO relationships so mapped parent/child groups do not contain arbitrary uncovered siblings. Use explicit human-directed coarse mappings where the hierarchies differ.
- **Detailed considerations:** [`esto_extended_category_creation_considerations.md`](esto_extended_category_creation_considerations.md).
- **Confirmed transport directions:** car → LPV small; sports utility vehicle → LPV medium; light truck → LPV large; HEV → ICE; EREV → PHEV; freight two-wheelers → LCVs; FCEV → BEV where the target vehicle has no FCEV child; PHEV → BEV for buses, motorcycles, and medium/heavy trucks where no PHEV child exists; LNG → ICE. Ninth gasoline and diesel PHEV map to the same size-specific PHEV category where it exists, with the fuel/product axis preserved.
- **Open decisions:** review parent output rows versus detailed process children in power/CHP/heat, the Electricity Generation Other plus solid-biomass boundary, the stable registry location, and which categories can receive defensible ESTO Extended historical values.
- **Next action:** Finish the short list of blunt hierarchy decisions with the user, generate an exact row-level proposed change set against the todo workbook, and review it before any workbook write.
- **Completion criteria:** Every new LEAP leaf pair has a reviewed ESTO Extended target or an explicit reason it is outside scope; all mapped sibling groups are complete under the agreed coarse crosswalk; rejected rows are absent; and structural/value validation passes after the workbook is enacted.

### MAPQ-032 — Replace the retired Stage 0 full-model-export resolver

- **Priority / status / week:** P1 · `ready_for_implementation` · W2
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-001
- **Evidence (2026-07-28):**
  `codebase/archive/outlook_mapping_maintenance_workflow.py` still checks
  `leap_mappings/data/full model export.xlsx` and
  `leap_initialisation/data/full model export.xlsx`. Both retired files are
  absent, so Stage 0 currently falls back to hierarchy inferred from active
  mapping paths. The maintained structure evidence is the 21-workbook
  per-economy template set under
  `leap_initialisation/data/leap_export_templates/`.
- **Next action:** Define the intended cross-economy hierarchy policy, update
  the resolver to consume reviewed per-economy templates with provenance, and
  add focused tests for branches whose parent/leaf status differs by economy.
  Do not silently select USA as the structural authority for all economies.
- **Completion criteria:** Stage 0 reports the exact templates used; missing or
  conflicting economy structures are explicit diagnostics; no live code or
  canonical guide treats either retired workbook filename as current; and
  subtotal/path QA passes on the reviewed template census.

### MAPQ-033 — Onboard the first real additional energy-balance dataset

- **Priority / status / week:** P2 · `blocked_pending_dataset_selection` · W3
- **Owner repo:** `leap_mappings` · **Depends on:** the multi-dataset M1–M6
  migration in `codex/multi-dataset-registry-m1`
- **Evidence (2026-07-29):** The disabled `SYNTH_BALANCE` fixture now proves
  registry-only scope admission, reviewed CSV mappings, declared CSV hierarchy,
  normalized PJ ingestion, coarse-boundary conservation, bounded unmapped-row
  review, and Stage 3-style lineage. A real four-source Stage 3 application
  smoke run also published a passed 3,952,646-row output contract after the
  validator registry refactor. The registry-enabled
  `synthetic_multi_dataset_acceptance_v1` run subsequently passed all twelve
  fixture criteria plus mapped-value conservation, publishing ESTO, LEAP,
  NINTH, and `SYNTH_BALANCE` through one unsplit coarse Common row. The fresh
  source-parent anchor rerun also completed: 217,099 eligible checks, 209,837
  passed, and 7,262 retained semantic failures. Implementation evidence is in
  commits `16b4c5d`, `796cfbe`, and `49eb119`.
- **Input needed from the user:** Select the first real additional dataset,
  provide a representative extract that includes its axis columns, economy,
  scenario, period, unit, and values, and identify someone who understands its
  balance/subtotal semantics well enough to review mappings.
- **Next action after input:** Register the dataset disabled, implement or
  configure its adapters, generate a bounded review table against the
  ESTO/ESTO Extended hub, record every manual semantic decision, and enable
  only a dedicated comparison scope for the first reviewed run.
- **Completion criteria:** The real dataset passes the same acceptance gates as
  `SYNTH_BALANCE`; no core Python edit is needed solely to name it; its
  scenarios and periods align through explicit scope rules; all non-PJ values
  are converted before mapping; and a reviewer accepts its mappings,
  exclusions, hierarchy status, and conservation evidence.

### MAPQ-034 — Decide and shadow-test the separate-axis mapping contract

- **Priority / status / timing:** P2 · `production_validation_complete_review_debt_open` · production contract promoted and run end to end 2026-07-30
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-005, MAPQ-029, MAPQ-031
- **Evidence:** [`separate_axis_mapping_exploration_findings.md`](archive/separate_axis_mapping_contract/separate_axis_mapping_exploration_findings.md) and the review-only evidence under `results/separate_axis_mapping_exploration/`.
- **Measured result (2026-07-29):** The editable six-axis workbook is now the ordinary compiler authority (`axis_contract_bootstrapped_this_run = false`). It contains 585 axis relations and four narrow accepted-extra-pair sheets. The generated master reproduces all 7,649 maintained active relationships and provisionally adds 3,501, for 11,150 pair relationships. Current pair-sheet schemas pass unchanged through Stage 1: all 15,298 complete retained canonical use-case rows remain and 7,002 use-case rows are added. Stage 2 is not equivalent: only 6,032 of 10,044 canonical component memberships remain unchanged; 4,012 are replaced and 4,530 generated memberships appear. There are 184 shared source-subtotal corrections, all false-to-true with unchanged target flags.
- **Recorded direction:** Treat sector and fuel axes as relations that may both be one-to-many or many-to-one. Historical possibility should be anchored to non-zero ESTO evidence in its final year, while future possibility should use non-zero Ninth evidence after that year. Avoid hierarchy-crossing mappings that conflict with mappings of siblings to target children. The intended benefits are easier auditing, fewer maintained rows, and clearer semantics.
- **Safety:** Promotion was explicitly approved after the refined structural Stage 3 gate found zero unsafe generated source fan-outs: 54 groups reach two Common rows and all are declared non-expanding parent/detail alternatives. The earlier bounded value run read 18,657,595 source rows, wrote 1,658,315 certified fact rows plus atomic lineage, and preserved 100% of mapped values in all ten scope/source combinations; maximum absolute difference was `1.1641532182693481e-10`. Production generation now records and reopens the candidate workbook, verifies literal Boolean cells and exact schemas, preserves the original canonical Git hash, and enables direct-subtotal edges only when the generation manifest matches the active workbook.
- **Production checkpoint (2026-07-30):** The contract is split into the human-edited `outlook_mappings_single_axis.xlsx`, generated `outlook_mappings_key_pairs_generated.xlsx`, and generated compatibility `outlook_mappings_master.xlsx`. The editable workbook contains the 585 single-axis rows plus four minimal accepted-extra-pair sheets. The initial one-time bootstrap accepted 425 LEAP, 965 ESTO, 965 ESTO Extended, and 917 Ninth pairs required by the maintained master but excluded by generated temporal authority. Presence of a row means accepted; deletion withdraws it, and no Boolean maintenance column is used. Generated registries merge these rows with `pair_origin = reviewed_extra`. The compiler reproduces all 7,649 maintained relationships with zero missing rows and emits 3,501 provisionally accepted Cartesian relationships, for 11,150 total. Eight within-axis many-to-many components remain explicit semantic review debt. The promoted master preserves all 14 canonical sheet names and the existing pair-sheet column contracts.
- **Production validation (2026-07-30):** The full non-shadow four-source run completed as `common_esto_20260729T175438145911Z`; all ten mapped scope/source combinations conserved mapped value with a maximum absolute difference of `1.1641532182693481e-10`, and source-once QA found zero unsafe multiple-Common-row deliveries. All 21 dashboard economies rendered against that exact run and passed automated publication readiness. Deep validation still reports hierarchy and anchor failures, four product-hierarchy checks were skipped because no eligible checks were available, 30 unresolved partial-coverage rows and 472 non-zero unmapped LEAP branches remain, and Stage 3 atomic lineage still lacks embedded `run_id`, `unit`, and original native-pair columns. These are explicit follow-up debt, not promotion blockers hidden as passes. See [`separate_axis_full_system_run_20260730.md`](archive/separate_axis_full_system_run_20260730/separate_axis_full_system_run_20260730.md).
- **Next action:** Review the 3,501 provisional relationships, eight within-axis many-to-many components, 29 ambiguous structural rows, broad Common partition, hierarchy/anchor failures, partial coverage, and lineage contract gap. MAPQ-036 may now begin because the production validation prerequisite is complete.
- **Completion criteria:** Human-approved context and dormancy policies exist; structural/reserved validity is explicit; the accepted compiler reproduces the pair contract and Common ESTO membership without unexplained overrides; Stage 3 proves source-once delivery and lineage; refresh performance is acceptable; and compatibility views have a tested rollback path.

### MAPQ-035 — Move and rename the detailed LEAP row inventory

- **Priority / status / timing:** P2 · `deferred_until_current_row_work_finishes` · after the active detailed-row work
- **Owner repos:** `leap_mappings` + `leap_initialisation` · **Depends on:** MAPQ-031, MAPQ-034
- **Current source:** `leap_mappings/data/temp/new leap rows.xlsx`, using the required `demand` and `power` sheets.
- **Recorded destination:** Move the workbook to `leap_initialisation/data/leap_export_templates/detailed leap model rows.xlsx`.
- **Reason for deferral:** The current workbook is still being used by active mapping work. Moving it now would create avoidable path churn and could disrupt that work.
- **Next action:** Once the current detailed-row work is complete, move and rename the workbook, then update every code, test, documentation, and manifest reference in both repositories. Keep the `demand` and `power` sheet contract unchanged unless a separate reviewed migration says otherwise.
- **Completion criteria:** The old temporary path has no live references; the renamed workbook is resolved from the export-template source area; the LEAP pair registry refresh manifest identifies it by its new path; relevant mapping, hierarchy, and initialisation tests pass; and the move is recorded in both repositories' handover notes.

### MAPQ-036 — Move remaining maintained non-pair sheets upstream

- **Priority / status / timing:** P2 · `queued_after_separate_axis_promotion` · after the production validation run
- **Owner repo:** `leap_mappings` · **Depends on:** MAPQ-034
- **Scope:** Decide whether rollup rules, rollup label overrides, display names,
  and reference lists should move into the primary human-edited workbook or a
  second narrow maintained workbook.
- **Current boundary:** The three pair-sheet bodies in
  `outlook_mappings_master.xlsx` are generated and must not be edited. The
  generator currently preserves the non-pair sheets from that workbook, so
  those particular sheets remain a documented temporary human-maintained
  exception.
- **Next action:** After the promoted full-system run is stable, design the
  smallest migration that keeps the single-axis workbook approachable and
  gives every maintained non-pair sheet an explicit owner.
- **Completion criteria:** Every maintained sheet has one unambiguous editable
  authority; ordinary generation never copies editable state from a generated
  output; downstream loaders retain their current compatibility interface; and
  rollback/provenance tests cover the new ownership boundary.

### MAPQ-037 — Complete review of the APEC anchor-validation workbook

- **Priority / status / timing:** P1 · `review_in_progress` · current work
- **Owner repos:** `leap_mappings` + `leap_dashboard` · **Depends on:** MAPQ-034
- **Evidence:** `outputs/019fc2a9-cf44-7671-b580-29079f59a49d/apec_anchor_validation_review.xlsx` is the current review artifact for the APEC-first source-parent anchor validation work.
- **Next action:** Complete the human review of the workbook before treating the APEC-first validation, targeted economy attribution, shared dashboard diagnostics page, or reviewed source-exception candidate flow as commit-ready. Record accepted findings, rejected exceptions, and any required mapping/workbook corrections in the appropriate maintained authority.
- **Completion criteria:** Every material APEC anchor finding has a documented disposition; any approved exception is exact and reviewer-confirmed; required code, mapping, or documentation corrections are applied and verified; and the resulting dashboard/pipeline smoke evidence is recorded.

---

## Four-week handover sequence

### Week 1: 2026-07-28 → 2026-08-03

- MAPQ-001 stabilize the checkout; MAPQ-024 close the gitignore gap.
- MAPQ-002 reconcile local `master` with the remote.
- MAPQ-003 and MAPQ-004 integrate the output contract and the two safety guards.
- MAPQ-023 begin retiring superseded branches.
- Start MAPQ-005 once code and workbook state are settled; start MAPQ-006.
- **Week 1 gate:** no unclassified dirty path, and no completed work reachable only from a worktree.

### Week 2: 2026-08-04 → 2026-08-10

- Finish MAPQ-005 and publish the baseline run record.
- MAPQ-009 triage semantic findings from that baseline; MAPQ-010 decide rollup modes.
- MAPQ-007 write the current ESTO Extended status note; MAPQ-011 resume curation in a clean window.
- Begin MAPQ-012 and MAPQ-013.
- **Week 2 gate:** one reproducible baseline exists, and semantic findings are a bounded decision list rather than raw diagnostic rows.

### Week 3: 2026-08-11 → 2026-08-17

- MAPQ-014 complete the handover document set; MAPQ-015 confirm the cross-repository index.
- MAPQ-008 salvage the diagnostics branch; **recheck the deferred ESTO Extended findings on 2026-08-17 by re-measuring, not by reusing parked counts.**
- Resolve or explicitly defer MAPQ-016 through MAPQ-021.
- MAPQ-025 confirm what sibling-repository work is local-only.
- **Week 3 gate:** every open item has an owner, a next action, and a last-verified date.

### Week 4: 2026-08-18 → 2026-08-24 — clean-checkout handover rehearsal

MAPQ-022 is the closing exercise and defines "done" for this programme.

1. Clone the repository fresh into a new directory from the intended remote —
   not a copy of this working tree.
2. Restore inputs strictly by following `docs/repo_data_slimdown_plan.md` and
   `data/README.md`. Every file the rehearser must fetch by hand is a
   documentation defect; record it.
3. Set up the environment using only the documented interpreter
   (`C:\Users\Work\miniconda3\python.exe`) and `environment.yml`.
4. Run maintenance plus Stages 1–3 from the MAPQ-014 runbook alone, with the
   mapping workbook closed in Excel.
5. Verify the published outputs against the contract in
   [`cross_repository_handover_index.md`](cross_repository_handover_index.md),
   then point `leap_dashboard` at the fresh checkout via `LEAP_MAPPINGS_ROOT`
   and confirm it renders the `20_USA` fixture.
6. Fix every documentation gap the rehearsal exposes, then repeat the failing
   step only.
7. Freeze the final dated queue and the known-risks list. Every unmerged
   branch, worktree, and unpushed commit across all three repositories must
   have an explicit disposition and a named owner.

**Programme is complete when** a person who has not worked on this repository
can produce a valid baseline from a clean checkout using only the documented
set, and every item in this queue is either `complete_on_master`, explicitly
descoped, or assigned to a named owner with a recorded risk.

## Queue maintenance rules

1. Update the `Last verified` date whenever a status changes, and re-derive the
   evidence rather than copying it forward.
2. Cite the commit, worktree, run ID, workbook sheet, or human decision that
   supports each status.
3. Never roll an old prompt's row counts forward to a new baseline. Re-measure.
4. Move completed prompts to `docs/archive/`; keep active prompts narrow and
   independently runnable.
5. Keep cross-repository tasks here only when the dependency affects mapping
   ownership or handover. Implementation-specific dashboard and initialisation
   work belongs in those repositories' own queues.
6. At the end of each week, record what moved to `complete_on_master`, what is
   blocked, and what must be descoped before handover.
