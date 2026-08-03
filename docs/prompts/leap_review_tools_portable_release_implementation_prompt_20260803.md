# Implementation Prompt: Developer-Linked and Portable LEAP Review Tools

## Task type

Cross-repository implementation. Build a maintainable Windows distribution path
for the LEAP dashboard generator and the balance-review workbook generator.
This is a productisation task, not authority to alter mappings or to run the
full all-economy pipelines.

## User outcome

Two supported ways to run the same tools:

1. **Developer mode** on the maintainer's machine runs directly against the
   current working copies of `leap_initialisation`, `leap_mappings`, and
   `leap_dashboard`. It uses code and mappings as they stand at run time, so
   local fixes take effect without rebuilding a package.
2. **Portable release mode** is a versioned Windows folder/ZIP for colleagues
   who do not need Python, Conda, Git, Codex, or the three repositories. It is
   built from an exact, tested set of repository commits and contains only the
   complete modules, configuration, and assets needed for the supported tools.

The first supported portable functions are:

- dashboard generation from its documented LEAP-export input;
- creation of the balance-review workbook, including the form represented by
  `leap_initialisation/outputs/leap_exports/supply_reconciliation/supporting_files/baseline_seed_balance_diagnostics/results_update_preview_20260803_usa_tgt/comparison_workbooks/balance_review_20_USA_tgt_2022.xlsx`.

Do not claim the balance-review workbook can be generated from a raw LEAP
export alone unless the required upstream reconciliation/comparison inputs are
actually bundled and validated. Make the two possible input modes explicit:
existing comparison/diagnostic artifacts, or a full supported reconciliation
run.

## Repository ownership and locations

- `C:\Users\Work\github\leap_initialisation` owns reconciliation and
  balance-review construction. Relevant starting symbols include
  `run_balance_update_workflow`, `build_balance_review_workbooks`, and
  `build_balance_structure_review_workbook`.
- `C:\Users\Work\github\leap_mappings` owns canonical mapping workbooks and
  mapping helpers. Do not edit generated pair-sheet bodies directly.
- `C:\Users\Work\github\leap_dashboard` owns dashboard-generation code and
  dashboard-specific configuration.

Use a small release-specific folder in `leap_initialisation` unless inspection
shows another existing product/release location is a better fit. Keep the
release builder and its tests in source control; generated packages must remain
ignored. Follow each repository's `AGENTS.md` and inspect `git status --short
--branch` in all three repositories before editing.

## Design constraints

- Package **complete files/modules**, never selected functions or line ranges
  from a large Python file. If a required file is too broad, first extract a
  deliberately small module in its owning repository and test it there.
- Build a declared dependency closure: every imported in-repo module,
  template, configuration file, static asset, and runtime dependency required
  by a supported command must be either included or rejected by validation.
- Do not copy `.codex`, `.claude`, `node_modules` junctions, private caches,
  user data, historical output trees, or raw input data into a release.
- Do not rely on `@oai/artifact-tool` or any Codex-managed runtime in portable
  mode. If a current workflow needs it, make that command unavailable in the
  portable release and give a clear reason; do not silently substitute a
  different spreadsheet engine.
- Do not embed actively maintained mapping workbooks in the executable.
  Distribute approved mapping/configuration files under an external `config/`
  directory and validate them at startup. Record their SHA-256 values in every
  run manifest.
- Prefer a PyInstaller **one-folder** (`--onedir`) Windows build (or an
  installer wrapping it), not a single-file executable. The package may use
  a simple standard-library GUI or clear guided command flow; do not add a
  heavyweight UI framework without need.
- Keep developer mode deliberately separate from portable mode. A colleague's
  release must never import from the maintainer's live checkout.
- Do not silently run `git pull`. A developer-facing update command may pull
  only after showing the proposed repositories/branches and refusing dirty
  worktrees, or it may be omitted in favour of normal Git updates.
- Outputs must always include a machine-readable and human-readable run
  manifest: release version, mode, timestamp, input paths and hashes, mapping
  hashes, source repository commits, and dirty status for developer mode.

## Required deliverables

### 1. Release contract and manifest

Create a reviewed manifest format (YAML, TOML, or JSON) that declares:

- semantic release version;
- exact commit SHA for each participating repository;
- complete allowlisted source paths per repository;
- external configuration/template assets;
- supported commands and their input/output contract;
- expected Python/runtime packages.

The builder must validate the manifest: referenced commits and files exist,
paths do not escape a repository root, and no unsafe/private/generated path is
allowlisted. It must fail clearly on a missing dependency rather than packaging
a partial program.

### 2. Developer launcher

Implement a notebook-safe, documented developer launcher that resolves the
three repositories from one explicit local settings file. It must not depend on
the current working directory and should expose the two initial functions. It
should check that all required repositories/configuration exist before a run.

The launcher must report the current commit and dirty state for each repository
in the output manifest. Developer-mode changes should apply on the next run;
there is no build step in this mode.

### 3. Portable-release builder

Implement a notebook-safe release workflow that creates a clean staging
directory from the manifest. It must retrieve files from the declared commits,
not whichever uncommitted code happens to exist in a working tree. Prefer Git
archive/show mechanisms or temporary clean worktrees; never mutate or reset
the maintainer's checkouts.

The workflow must:

- copy approved whole modules/assets only;
- construct a portable package layout with `config`, `templates`, `input`,
  `output`, `logs`, `README`, and `licenses` as appropriate;
- build the Windows executable/folder reproducibly;
- write the frozen release manifest into the package;
- emit a concise release report with file list and hashes;
- keep all generated staging/build/package locations ignored and easy to
  delete manually without traversing links.

### 4. Runtime input validation and support bundle

Before processing an input, validate its schema, economy/scenario/year values,
and required companion artifacts. Explain missing/invalid inputs in plain
language. Write normal logs to `logs/` and make a support bundle containing
the run manifest, logs, effective settings, and validation report. Do not add
raw input data to a support bundle by default.

### 5. Golden test and clean-machine rehearsal

Build a regression test around the USA 2022 balance-review case named above.
Use existing known-good inputs, write only to a temporary test location, and
compare the generated workbook's structural contract and selected core values
against a defined golden expectation. Do not overwrite the named historical
workbook.

Run an isolated portable-mode smoke test that has no imports from the live
repositories after packaging. Verify its output path, run manifest, mapping
hash capture, and error behaviour for one deliberately invalid input. Document
any manual Windows prerequisites such as Excel, code signing, or SmartScreen
approval.

## Documentation required

Document:

- how the maintainer runs developer mode and updates repositories safely;
- how a colleague runs the portable release;
- how mappings/settings can be updated without rebuilding the executable;
- when a code bug requires a new tested release;
- release/versioning procedure and rollback procedure;
- what input data is required for each supported command;
- known limitations and unavailable Codex-only functionality.

## Verification and completion criteria

Before completion:

1. Run focused tests for the added release/launcher code.
2. Run the golden USA balance-review test without changing source inputs or the
   historical reference workbook.
3. Build one portable folder and prove its entry point does not import live
   repository code.
4. Verify a mapping/configuration edit in a copied release config folder is
   detected and recorded in the next output manifest (use a harmless fixture;
   do not change the canonical mapping workbook).
5. Inspect the generated package to confirm it has no `.git`, `.codex`,
   `.claude`, junction/reparse-point, private cache, or large historical output
   content.
6. Commit only the implementation and documentation authored for this task,
   using small coherent commits. Do not stage or commit unrelated existing
   changes.

## Stop conditions

Stop and report rather than guessing if:

- the dashboard or workbook workflow's input contract cannot be isolated from
  an undocumented upstream artifact;
- an imported dependency has unclear licence/distribution rights;
- a required component exists only inside a Codex runtime;
- a source module is changing concurrently in a way that would make a release
  manifest misleading;
- a clean package cannot reproduce the defined golden test.

## Final handoff

Provide the source locations, release manifest format, exact commands/notebook
toggle blocks for developer and release builds, verification results, package
location, and a short list of remaining constraints. Do not distribute a
release to colleagues or run a network update without explicit user approval.
