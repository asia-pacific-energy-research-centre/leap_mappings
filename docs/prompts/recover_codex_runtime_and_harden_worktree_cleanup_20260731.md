# Recovery Prompt: Restore Codex Spreadsheet Runtime and Harden Worktree Cleanup

## Objective

Recover the shared Codex spreadsheet runtime after an unsafe worktree cleanup, verify that the restored LEAP inputs are usable, and design/implement junction-safe worktree cleanup. Work autonomously through all safe local recovery and validation steps. Stop and hand back to the user only if Codex Desktop must be repaired, reinstalled, or otherwise changed outside the repositories.

Do not rerun the mapping-pipeline monitor until the runtime dependency check passes.

## Historical incident context

On 2026-07-30, Codex worktrees were reviewed and several clean worktrees were removed. The cleanup used `git worktree remove` on these paths:

- `C:\Users\Work\github\worktrees\leap_mappings_multi_dataset_registry`
- `C:\Users\Work\github\worktrees\leap_mappings_output_contract`
- `C:\Users\Work\github\worktrees\leap_mappings_separate_axis_exploration`
- Several clean `leap_initialisation` Claude worktrees, including `results-update-dry-run-preview`, `upbeat-elion-408d71`, and `zealous-mcnulty-f8ddad`.

The repositories themselves were not deleted. However, at approximately 21:09:57 JST, removing the `leap_mappings_separate_axis_exploration` worktree traversed this directory junction:

```text
worktrees\leap_mappings_separate_axis_exploration\node_modules
  -> C:\Users\Work\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules
```

That emptied the shared runtime `node_modules`, including `@oai/artifact-tool`. Spreadsheet-dependent mapping processes then failed because the bundled JavaScript spreadsheet dependency was unavailable.

A similar unsafe cleanup affected `leap_initialisation`: one Claude worktree contained junctions to the main repository's export-template and USA-export directories. Removing that worktree partially followed those links and emptied the export-template directory during a baseline-seed run. This contributed to the later five-economy failures.

The root cause is that ignored junction/reparse-point targets are invisible to ordinary `git status`, while worktree removal can recursively delete through them. Treat this as a data-loss incident, not ordinary stale-worktree cleanup.

## Known current state

- No tracked source files are known to be missing from `leap_mappings`, `leap_initialisation`, or `leap_dashboard`.
- `C:\Users\Work\github\leap_initialisation\data\leap_export_templates` currently contains twelve restored `29_07` workbooks:
  - `APEC clean slate 29_07.xlsx`
  - `AUS clean slate 29_07.xlsx`
  - `BD clean slate 29_07.xlsx`
  - `MAS clean slate 29_07.xlsx`
  - `MEX clean slate 29_07.xlsx`
  - `NZ clean slate 29_07.xlsx`
  - `PHL clean slate 29_07.xlsx`
  - `PNG clean slate 29_07.xlsx`
  - `PRC clean slate 29_07.xlsx`
  - `THA clean slate 29_07.xlsx`
  - `USA clean slate 29_07.xlsx`
  - `VN clean slate 29_07.xlsx`
- Current USA and PRC balance exports are present.
- Older templates and `REF 3007 PRC.xlsx` remain in the Recycle Bin. Do not restore or overwrite current files with them unless structural validation proves the current files are invalid and the user explicitly approves replacement.
- The shared Node runtime currently resolves to:

```text
C:\Users\Work\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe
C:\Users\Work\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules
```

- The runtime `node_modules` directory was observed empty after the incident. `@oai/artifact-tool` was not found in the expected bundled location, and no complete local replacement was found during the initial search.
- The mapping-pipeline monitor must remain stopped at `failed_dependency_runtime` until the dependency import succeeds.
- `data/*` is ignored by Git in `leap_initialisation`; Git status/history cannot protect or explain deletion of those template files.

## Safety rules

1. Do not delete, move, overwrite, or rename the restored templates or current balance exports.
2. Do not restore Recycle Bin files automatically.
3. Do not run `git worktree remove`, `git worktree prune`, recursive directory deletion, `Remove-Item -Recurse`, `rmdir /s`, or equivalent cleanup until junction/reparse-point handling has been designed and tested.
4. Do not install a random npm package, use a global Node installation, set `NODE_PATH`, copy package internals, or create a resolution hack for `@oai/artifact-tool`. The spreadsheet workflow requires the bundled Codex runtime dependency.
5. Preserve evidence: record paths, timestamps, file sizes, hashes, and command outputs before making changes.
6. Never modify unrelated existing worktree changes. Work only in clearly scoped new diagnostic files or the requested cleanup utility/documentation.
7. If a step requires restarting, repairing, or reinstalling Codex Desktop, stop and report the exact blocker and the precise user action needed. Do not attempt to simulate that repair from a repository shell.

## Recovery workflow

### 1. Inventory and preserve the recovered inputs

Read-only checks first:

- List all files under `C:\Users\Work\github\leap_initialisation\data\leap_export_templates`.
- Record SHA-256 hashes, sizes, and timestamps for every workbook.
- Locate current USA and PRC balance exports and record the same metadata.
- Confirm that no process is writing to these directories.
- Store the inventory outside the ignored `data` tree if a new diagnostic artifact is needed.

Do not make the inventory a replacement for a backup. If an obvious safe backup location exists, copy the files there without changing the originals and report the destination.

### 2. Diagnose the bundled runtime

Use only the workspace dependency paths supplied by Codex Desktop. Confirm:

- the bundled Node executable exists;
- the bundled `node_modules` path exists;
- `@oai/artifact-tool` is present at that path;
- Node can import it successfully.

The minimum smoke test is equivalent to:

```powershell
& 'C:\Users\Work\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' -e "import('@oai/artifact-tool').then(()=>console.log('artifact-tool OK')).catch(e=>{console.error(e);process.exit(1)})"
```

If the package is absent, search only for an intact official Codex-managed runtime copy or rehydration mechanism. Do not install or copy arbitrary packages. If no official local recovery is available, stop with a concise handoff telling the user that Codex Desktop repair/reinstallation is required.

### 3. Validate the restored templates without overwriting them

After the runtime is restored, run the repository's existing resolver/preflight checks against the current template directory. Confirm:

- all twelve workbooks are discoverable for their intended economies;
- each workbook has the expected LEAP export structure and header rows;
- IDs, key columns, metadata, levels, and expressions are readable;
- USA and PRC balance exports are readable;
- no current workbook is silently replaced by an older Recycle Bin copy.

If filenames differ from older documentation, test the actual resolver rather than renaming files speculatively. The current resolver matches economy tokens in filenames and does not require the old exact filename pattern, but the workbook contents still require structural validation.

### 4. Run a minimal spreadsheet smoke test

Only after `@oai/artifact-tool` imports successfully, run the smallest existing spreadsheet-dependent mapping or workbook inspection test. Confirm that it can import/read/export a temporary test workbook without touching production templates or outputs.

Then rerun the previously failed baseline-seed validation in dry-run or preview mode first. Compare the output and error counts with the known five-economy failure. Do not start the full monitor until the dry run is clean enough to justify it.

### 5. Implement junction-safe cleanup protection

Create a small, reviewable cleanup utility or documented procedure. It must:

- resolve the exact worktree path and verify it is inside the intended repository/worktree root;
- enumerate files and directories without following directory junctions or other reparse points;
- detect every Windows reparse point before deletion, including ignored `node_modules` junctions and links into sibling repositories;
- refuse cleanup and print each junction target unless the caller explicitly handles it;
- never recursively delete through a junction;
- distinguish registered Git worktrees from stale directories and nested full-repository snapshots;
- verify tracked, untracked, ignored, and reparse-point state separately;
- log the exact paths that would be removed;
- default to dry-run;
- require an explicit, narrow confirmation for actual deletion;
- leave associated branches intact unless branch deletion is separately requested.

Add focused tests for:

- a worktree containing a junction to a shared runtime;
- a worktree containing a junction to a sibling repository data directory;
- ignored files hidden from normal `git status`;
- a normal disposable worktree with no reparse points;
- a missing/stale worktree directory;
- a path traversal or junction target outside the intended worktree.

Do not test by deleting the real Codex runtime or real LEAP data. Use temporary test directories and synthetic junctions where Windows permissions allow.

### 6. Document and hand off

Record:

- what was restored and how it was verified;
- whether Codex Desktop rehydration succeeded or remains required;
- template/export hashes and validation results;
- the exact cleanup utility/procedure and its dry-run output;
- any remaining worktree directories that were intentionally left untouched;
- the fact that the incident resulted from junction traversal during worktree cleanup.

Do not mark the monitor recovered until the bundled runtime import, spreadsheet smoke test, and baseline-seed dry run all pass.

## Completion criteria

The task is complete only when:

- current restored templates and balance exports are preserved and validated;
- `@oai/artifact-tool` imports from the official bundled Codex runtime, or the task is explicitly handed back because Codex Desktop repair/reinstallation is required;
- a spreadsheet smoke test passes;
- the baseline-seed dry run no longer fails because of the missing runtime or missing templates;
- junction-safe cleanup protection exists in a tested dry-run form;
- no unsafe worktree cleanup command has been run during this recovery.
