# Outcome: developer-linked and portable LEAP review tools

Completed 2026-08-03. Implementation and documentation live in
`leap_initialisation`; this repository contributes one module and one
configuration file to a release and needed no code changes.

## Where the work landed

| Repository | What |
|---|---|
| `leap_initialisation` | `codebase/portable_release/` (launcher, builder, runtime, validation, provenance, portable entry point), `config/portable_release_manifest.toml`, `config/leap_review_tools_settings.example.toml`, `docs/leap_review_tools.md`, three test modules |
| `leap_dashboard` | `codebase/common_esto_dashboard_portable.py` — the narrow, packageable render entry point; `set_code_colors_path()` in the renderer so a package can locate its colour map |
| `leap_mappings` | nothing. `codebase/mapping_tools/source_branch_preflight.py` and `config/all_demand_aggregated_components.json` are consumed by a release at a pinned commit |

Read `leap_initialisation/docs/leap_review_tools.md` first. It covers both
modes, the release and rollback procedure, and the limitations below.

## What a release supports

- **dashboard** — renders the Common ESTO dashboard for one economy from
  existing comparison data.
- **balance-review** — builds the five-sheet balance-review workbook from
  *existing diagnostic artifacts* plus the LEAP balance export they were
  computed against.

A balance-review workbook cannot be produced from a raw LEAP export alone. The
full reconciliation run that produces the diagnostics is developer-mode only: it
needs the canonical mapping workbook, the ESTO base table, and the 288 MB
9th-edition projection table, through a 38-module closure that reaches the LEAP
COM API.

## Notes for this repository

- A release pins `leap_mappings` to an exact 40-character commit and reads the
  two files above with `git cat-file`. Master moving does not affect an existing
  release; a *new* release picks up whatever is pinned at the time.
- `config/all_demand_aggregated_components.json` is distributed as an external
  configuration file, not embedded. Replacing it in a colleague's `config/`
  folder changes the next run and is recorded by SHA-256 in that run's manifest,
  with no rebuild.
- The balance-review builder and this repository's workbook builders are both
  off `@oai/artifact-tool` and Node.js now. Both supported commands were run
  end-to-end from a frozen executable with no Codex runtime present. The only
  capability not carried over is sheet-image preview rendering.
