# Handoff prompt: scope an "ESTO extended" dataset (and a general extension path)

You are taking over work in `C:\Users\Work\github\leap_mappings`. The goal is
to design (and only then, if the design is sound, implement) a new dataset
called **ESTO extended**: it reuses the existing ESTO mappings but adds more
detail, so that LEAP categories currently unmapped to ESTO can be mapped
against it. Do not start writing mapping rows before the design questions
below are answered — this is a design/scoping task first.

**Treat ESTO extended as the first instance of a general capability, not a
one-off.** The explicit goal is that adding a *future* dataset (a 2nd, 3rd,
Nth one beyond ESTO extended) should be a matter of following an established
pattern — new tree/mapping/rollup-rule inputs plus config, not new branching
logic sprinkled through the pipeline. Wherever the design below would
naturally lead to something ESTO-extended-specific (a new `if dataset ==
"esto_extended"` check, a new hardcoded `source_system` string in the middle
of shared logic, a bespoke comparison scope wired by hand in one place), stop
and ask instead: what would make this a data-driven, config-declared
extension point that the Nth dataset can also use without editing the same
code again? Concretely, look at how `ROLLUP_SHEET_CONFIGS` in
`non_expanding_rollups.py` and `COMPARISON_SCOPE_SYSTEMS` in
`source_parent_anchor_validation.py` already generalize ESTO/LEAP/NINTH as
parallel, declaratively-configured datasets rather than three separately
special-cased code paths — the design should extend that same pattern, not
add a fourth special case next to it. Call out explicitly, in the design
note, exactly what a future dataset addition would need to touch under your
proposed design (which files, which config, ideally zero core-logic changes)
so this is verifiable rather than assumed.

Use `C:\Users\Work\miniconda3\python.exe` for Python. Read the repository
`AGENTS.md`, `docs/mappings_system.md`, and `docs/rollup_rules_system.md`
before proposing anything. Do not delete or revert user-owned files.

## Immediate coordination

Start with:

```powershell
git status --short
git log -12 --oneline
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*run_mapping_pipeline.py*' } |
  Select-Object ProcessId,CommandLine
```

There may be an active Stage 3 run, or uncommitted user edits to
`config/outlook_mappings_master.xlsx` and its variants. Do not start another
pipeline run while one is active, and do not touch workbook files that are
mid-edit by the user — inspect, don't alter, unless asked.

## Why this matters — read before designing anything

A recent session spent most of a day tracing and fixing a family of bugs in
`codebase/mapping_tools/source_parent_anchor_validation.py` that were all the
same underlying shape: **the same physical value represented at more than one
level of detail at once**, without the pipeline being told which
representation is authoritative for a given comparison. Examples already
found and fixed this cycle:

- ESTO's raw `data/00APEC_2025_low_with_subtotals.csv` carries an explicit
  subtotal row at every hierarchy level (`is_subtotal`), so an intermediate
  code can duplicate the value of its own single real child
  (`16.01 Commercial and public services` == `16.01.99 ... unallocated`).
- NINTH's raw hierarchy reports the same total as a literal row at multiple
  depths at once when a branch has one nonzero contributor
  (`12_solar`, `07_petroleum_products`, `15_solid_biomass`, `16_others`).
- LEAP's `esto_leap_ninth` comparison scope legitimately collapses several
  distinct LEAP products onto one shared Common ESTO row (e.g.
  `07.12-07.17 Petroleum products`) when NINTH can't distinguish them, but
  the anchor validator wasn't grouping siblings before comparing.

**ESTO extended is structurally the same risk, deliberately**: it is a
second, more-detailed representation of data that already exists at a
coarser level in ESTO. If a LEAP branch's value ends up representable through
both the existing coarse ESTO mapping and the new extended-ESTO mapping for
the same economy/scenario/year, that is a double-count waiting to happen —
exactly the class of bug this repo just spent a day chasing down, except
self-inflicted at design time instead of discovered later. The design must
close this off structurally, not rely on catching it in review.

See `docs/prompts/holistic_mapping_system_stocktake_findings_20260722.md` for
the full write-up of that investigation, and the current state of
`codebase/mapping_tools/source_parent_anchor_validation.py` /
`codebase/mapping_tools/non_expanding_rollups.py` for the mechanisms
(`exclude_parents`, `has_data_pairs`, `literal_pairs`) already in place to
detect and prevent this kind of overlap — familiarize yourself with these
before designing new mapping structure, since ESTO extended will need to
compose with them, not bypass them.

## What "unmapped LEAP categories" actually are — get concrete first

Stage 3 already reports this diagnostic on every run:

```
Nonzero LEAP branches without direct ESTO mappings: 223
```

Before designing anything, get the actual list, not just the count. Find
where this is computed in `codebase/run_mapping_pipeline.py` (search for
`without direct ESTO mappings` and `Nonzero LEAP branches`) and produce a
concrete, named list of the LEAP branches this refers to, with example
economies/years where they carry real nonzero data. Group them by rough
subject area. This list is the actual scope of "ESTO extended" — don't design
in the abstract.

## Design questions to answer before implementing

1. **Does this need to be a new `source_system`/dataset at all, or is it an
   extension of the existing ESTO mapping sheets?** The pipeline already
   treats ESTO/LEAP/NINTH as parallel datasets, each with their own tree,
   mapping sheet, and rollup-rule sheet
   (`ROLLUP_SHEET_CONFIGS` in `non_expanding_rollups.py`,
   `COMPARISON_SCOPE_SYSTEMS` in `source_parent_anchor_validation.py`). A
   genuinely new dataset needs a new tree builder, a new rollup-rule sheet, and
   new comparison-scope wiring throughout Stage 2/3 — a real amount of new
   infrastructure. An alternative: treat "ESTO extended" as additional rows in
   the *existing* ESTO mapping/tree, at a finer level of detail than what's
   there today, without inventing a new source system. Compare both options
   explicitly; recommend one with reasons.
2. **How is double-counting against existing ESTO components prevented,
   structurally?** For every unmapped LEAP branch that ESTO extended will
   cover, confirm: does *any* part of that branch's value currently reach an
   existing Common ESTO row through any other path (direct ESTO mapping,
   NON_EXPANDING/DETACHED rollup, or another LEAP mapping)? If yes, ESTO
   extended must either replace that path entirely or explicitly reconcile
   with it — never add alongside it. Propose a concrete mechanism (e.g. an
   `include`/precedence flag, a partition scheme, or scoping ESTO extended
   strictly to LEAP branches with *zero* existing coverage) and justify it.
3. **Does ESTO extended need its own comparison_scope** (like
   `esto_extended_leap`) or does it participate in existing scopes
   (`esto_leap`, `esto_leap_ninth`)? If NINTH can't resolve to the new level
   of detail (likely, since the whole premise is "more detail than ESTO
   currently has"), how should NINTH-inclusive scopes behave for these rows —
   roll extended detail back up to the coarse level for NINTH comparisons, the
   same way `esto_leap_ninth` already does for LEAP's `07.12-07.17 Petroleum
   products` case?
4. **What's the source of the "extra detail"?** Is it derived purely from
   already-existing LEAP data (splitting a currently-aggregate ESTO row using
   LEAP's own finer breakdown), or does it require new source data or manual
   judgment calls? This determines whether ESTO extended is a mechanical
   mapping-compiler change or requires new human-authored mapping rows (or
   both, per branch).
5. **What breaks if this is wrong?** Name the specific validators this repo
   already has that would catch overlap or double-counting if ESTO extended
   introduces it (`Mapped-row aggregation preservation`, the recursive
   Common ESTO validator, `source_parent_anchor_validation.py`'s anchor
   checks) and confirm ESTO extended's rows will actually be visible to all of
   them, not accidentally excluded from validation the way some of today's
   `is_subtotal`/rollup rows were.
6. **If a second new dataset were proposed six months from now, what would
   have to change?** Walk through your proposed design as if a concrete
   future example already existed (pick a plausible one — e.g. a detailed
   national statistics dataset, or a second LEAP variant) and trace exactly
   what adding it would require under your design: which config/sheets get a
   new row vs. which .py files need new code. If the honest answer involves
   editing shared logic in `source_parent_anchor_validation.py`,
   `non_expanding_rollups.py`, `build_dataset_tree_structure.py`, or
   `run_mapping_pipeline.py` beyond adding a new entry to an existing
   config dict/sheet-list, say so plainly and treat that as a design gap to
   resolve now — not something to defer to whoever adds the next dataset.

## Required output

Before writing any mapping rows or code, produce a short design note (new file
under `docs/prompts/`, e.g. `esto_extended_dataset_design.md`) covering:

- The concrete list of currently-unmapped LEAP branches this would cover
  (from the "get concrete first" step above), grouped and prioritized.
- Answers to the six design questions above, with a clear recommendation.
- An explicit "adding dataset N+1" checklist derived from question 6: the
  exact files/config a future dataset addition would touch under the chosen
  design, so this is a concrete artifact reviewable on its own, not just a
  claim inside the prose.
- A small, low-risk pilot scope: 1-2 LEAP branches to implement first, chosen
  specifically because they have no existing overlapping ESTO coverage (the
  cleanest case), so the pilot itself can't introduce a double-count even if
  something else about the design is wrong.
- A test/verification plan for the pilot: which existing checks
  (`pytest tests/test_source_parent_anchor_validation.py`, the conservation
  totals Stage 3 prints, the recursive validator's mismatch counts) must stay
  green, and what a genuine pass/fail signal looks like for "this branch is
  now correctly represented with no double-count."

Only after that design note exists and has been reviewed should implementation
start, one pilot branch at a time — the same "diagnose fully before touching
the workbook" discipline used in
`docs/prompts/holistic_mapping_system_stocktake_prompt.md`.
