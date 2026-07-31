# Work Queue Prompt: Prepare Portable LEAP Repositories and Junction-Safe Cleanup

## Task type

Cross-repository safety, portability, dependency, and distribution preparation. This is not permission to run the long mapping, baseline-seed, update, or dashboard pipelines unless a separate run prompt explicitly requests them.

## End goal

Prepare `leap_mappings`, `leap_initialisation`, and `leap_dashboard` so that a person who does not use Codex can clone or receive the repositories and run the supported Python workflows without inheriting machine-specific Windows junctions, Codex-only paths, hidden shared dependencies, or unsafe cleanup behavior.

The final handoff must clearly distinguish:

1. Python workflows that are portable after documented environment setup.
2. Spreadsheet-dependent workflows that require `@oai/artifact-tool` or an approved non-Codex replacement.
3. Optional Codex conveniences that must never be required for a clean external checkout.

The repositories must be safe to distribute without copying `C:\Users\Work\.cache`, `.codex`, `.claude`, local worktrees, generated outputs, or private session state.

## Historical context and incident

On 2026-07-30, unsafe cleanup of Codex/Claude worktrees followed Windows directory junctions. A `leap_mappings` worktree contained a `node_modules` junction targeting:

```text
C:\Users\Work\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules
```

Removing the worktree emptied the shared runtime and deleted `@oai/artifact-tool`. A `leap_initialisation` worktree also contained junctions to repository data/export directories; cleanup partially followed those links and emptied LEAP export-template content during a baseline-seed run.

The current runtime and restored inputs have been recovered. The recovery tests passed, but junctions still exist and must be treated as a live safety risk.

Previously observed junction categories, which must be remeasured rather than assumed:

- `leap_mappings`: six junctions, primarily `node_modules` links to the shared Codex runtime.
- `leap_initialisation`: five junctions, including runtime links and links from `.claude\worktrees` to `leap_dashboard` and `leap_mappings`.
- `leap_dashboard`: no junctions were observed in the last scan.

## Current verified recovery state

- The bundled Codex Node runtime imports `@oai/artifact-tool` successfully when tested from the bundled Node directory.
- A temporary artifact-tool smoke workbook was created, formula-calculated, inspected, rendered, and exported successfully.
- Eleven LEAP templates are discovered for `01_AUS`, `02_BD`, `05_PRC`, `10_MAS`, `11_MEX`, `12_NZ`, `13_PNG`, `15_PHL`, `19_THA`, `20_USA`, and `21_VN`.
- All eleven templates have the expected LEAP ID/key columns, year columns, non-missing IDs, non-missing logical keys, and no duplicate logical keys in the tested rows.
- Current AUS, PRC, and USA balance exports pass the Level 2+ detail check.
- `leap_mappings` focused pipeline tests passed: 11 passed, 1 skipped.
- `leap_initialisation` focused tests passed except for one stale expected-area assertion: the test expects `USA clean slate 28_07`, while the current restored workbook area is `USA clean slate 29_07`. Do not silently overwrite the new workbook; decide whether the test expectation should be updated and record the decision.
- Recovery backups exist at `C:\Users\Work\codex_recovery_backup_20260731`, including Codex/Claude state, Git bundles, all 12 restored templates, and all 36 balance-export files.

## Non-negotiable safety rules

1. Do not run `git worktree remove`, `git worktree prune`, `Remove-Item -Recurse`, `rmdir /s`, `shutil.rmtree`, or equivalent recursive cleanup on these repositories until a junction-safe cleanup implementation has been reviewed and tested.
2. Never follow or recursively delete through a Windows reparse point. Detect junctions before traversal and refuse by default.
3. Do not delete the current shared Codex runtime, restored templates, balance exports, repository source, or recovery backup.
4. Do not modify the current junctions casually. First inventory their exact targets and confirm no process depends on them. When removing a junction, remove the link itself only; never remove its target contents.
5. Preserve unrelated uncommitted changes. Run `git status --short --branch` before edits in every repository and report any overlap before changing files.
6. Do not copy `.codex`, `.claude`, runtime caches, private session state, or generated output trees into a distribution package.
7. Do not install or vendor `@oai/artifact-tool` from an unknown source. Establish whether a supported non-Codex installation route exists. If not, document the spreadsheet-dependent workflows as Codex/runtime-dependent instead of creating a resolution hack.

## Work plan

### 1. Inventory the three repositories

For each repository:

- record the repository root, current branch, commit, dirty status, and worktree list;
- enumerate all files and directories with `ReparsePoint` attributes without following them;
- record each junction/symlink target and classify it as runtime, sibling repository, generated-output, or unknown;
- identify any hard-coded `C:\Users\Work`, `.codex`, `.claude`, `node_modules`, worktree, or machine-specific paths in live code/config/docs;
- identify ignored files that are required for local execution but absent from a clean clone.

Write a compact inventory report outside generated output folders. Do not dump large file listings into the report.

### 2. Separate portable source from local scaffolding

Classify every discovered junction and local dependency:

- repository source or configuration that belongs in Git;
- generated output/cache that should remain ignored;
- Codex/Claude worktree scaffolding that must not be distributed;
- runtime dependency required by a workflow;
- accidental cross-repository link.

For the two `.claude\worktrees\leap_dashboard` and `.claude\worktrees\leap_mappings` links in `leap_initialisation`, verify they are scaffolding and not canonical source. Record that conclusion before removal.

### 3. Design and implement junction-safe cleanup

Create a small, reviewable utility or documented procedure with dry-run as the default. It must:

- accept one explicit worktree path;
- resolve and validate the path remains inside the intended worktree root;
- enumerate reparse points without following them;
- print every reparse point and target;
- refuse cleanup if any reparse point exists unless an explicit safe-detach mode is requested;
- detach/remove only the link object, never its target;
- distinguish registered Git worktrees, stale directories, and ordinary directories;
- inspect tracked, untracked, and ignored files separately;
- log the exact deletion plan;
- require a narrow confirmation for actual deletion;
- leave associated branches intact unless branch deletion is separately requested.

Test it in temporary directories with synthetic junctions and a shared-target fixture. Include a regression test proving that deleting a worktree containing a `node_modules` junction does not alter the target directory.

Do not test against the live Codex runtime or live LEAP data.

### 4. Make the repositories portable

For each repository:

- remove or replace machine-specific live references where appropriate;
- ensure no required source/config path depends on `C:\Users\Work`;
- document Python environment setup and expected input locations;
- document optional Node/spreadsheet requirements separately;
- ensure a clean clone does not need `.codex`, `.claude`, or a local junction;
- add or update `.gitignore`/`.worktreeinclude` only where the intended behavior is clear;
- do not add ignored data or private runtime contents to Git merely to make a local run pass.

For `@oai/artifact-tool`, determine whether external users have a supported installation route. If it is Codex-managed only, state that clearly and identify which scripts require it. Do not substitute another spreadsheet library without explicit approval.

### 5. Create a clean-clone validation

Use a temporary clean checkout or equivalent isolated copy with no junctions and no access to the user’s Codex runtime. Verify:

- Python imports and configuration resolution;
- mapping tests that do not require Codex-only spreadsheet tooling;
- template resolver behavior when input files are supplied explicitly;
- baseline-seed validation/import logic against supplied templates;
- dashboard Python/data-processing logic where applicable;
- expected, clearly documented failures for Codex-only spreadsheet features.

The clean-clone test must not touch the production repositories, restored data, or recovery backup.

### 6. Validate the current operational path

Before declaring the distribution work complete, rerun compact local smoke tests:

- bundled artifact-tool import and temporary workbook smoke test;
- all 11 template discovery and header/ID/key checks;
- current balance-export Level 2+ checks;
- focused mapping resolver/pipeline tests;
- focused initialisation resolver/baseline validation tests, with the `29_07` USA assertion decision recorded;
- reparse-point inventory for all three repositories.

Do not start the long full mapping, update, baseline-seed, or dashboard pipelines as part of this portability task.

## Expected outputs

Produce:

1. A junction/reparse-point inventory for all three repositories.
2. A portable-dependency matrix showing which workflows are Python-only, Node-dependent, Codex-runtime-dependent, or blocked for non-Codex users.
3. A dry-run junction-safe cleanup utility/procedure and tests.
4. A clean-clone validation report.
5. Documentation updates for setup, dependency boundaries, and safe worktree handling.
6. A short unresolved-issues list, including the USA `28_07` versus `29_07` test expectation.

## Stop conditions

Stop and report before making a change if:

- a junction target is outside the expected runtime/repository scope;
- a proposed removal could affect a shared target;
- a required external dependency has no confirmed installation route;
- current uncommitted work overlaps the proposed edit;
- a clean-clone test would require copying private Codex/Claude state;
- a test failure indicates a data or ID mismatch rather than a simple stale expectation.

## Completion criteria

The task is complete only when:

- no accidental repository-to-repository junctions remain in the distributable repository state;
- no distribution-critical workflow depends on a machine-specific Codex path without explicit documentation;
- cleanup refuses unsafe reparse-point traversal by default;
- a clean-clone validation has been run and its limitations are documented;
- the current restored templates and balance exports remain unchanged;
- all changes are reviewed, tested, and committed without including unrelated user changes.
