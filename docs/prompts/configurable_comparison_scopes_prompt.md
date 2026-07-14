# Prompt: Make comparison scopes selectable, and make each selected scope actually use its own granularity

Work in `C:\Users\Work\github\leap_mappings`.

## Background / why this matters

`build_common_esto_structure.py` builds four "comparison scopes" on every
pipeline run: `leap_vs_esto`, `leap_vs_ninth`, `leap_vs_esto_vs_ninth`,
`esto_only` (see `COMPARISON_SCOPES` at
`codebase/mapping_tools/build_common_esto_structure.py:37`). Each scope is
supposed to represent a different pair/triple of systems being compared, and
each scope's common rows carry a `comparison_scope` column so downstream
consumers can filter to the comparison they care about.

We verified against the current run's actual output
(`results/common_esto/common_esto_rows.csv`) that **all four scopes currently
produce byte-for-byte the same 2,180 `common_row_id`s** — the
`comparison_scope` column is just a label on an identical structure, not a
genuinely different partitioning. This defeats the purpose: a user who wants
"just the LEAP<>ESTO comparison, at whatever detail LEAP+ESTO alone can
support" gets the same coarse aggregation that was only necessary because
NINTH's data is much coarser than LEAP/ESTO.

### Root cause

`build_common_esto_for_scope()`
(`codebase/mapping_tools/build_common_esto_structure.py:1456`) takes a
`scope_config` dict with three keys — `systems`, `use_cases`,
`aggregate_source_systems` — but only `use_cases` and
`aggregate_source_systems` are actually read, and **every scope in
`COMPARISON_SCOPES` is configured with the same values**:

```python
_ALL_USE_CASES = ["leap_to_esto_balance_conversion", "ninth_to_esto_balance_conversion"]
_ALL_AGGREGATE_SOURCE_SYSTEMS = ["LEAP", "NINTH"]
```

`scope_config["systems"]` (the one field that *does* differ per scope, e.g.
`["LEAP", "ESTO"]` for `leap_vs_esto` vs `["LEAP", "NINTH"]` for
`leap_vs_ninth`) is never read anywhere — confirmed by grep, zero hits outside
the dict literal itself.

Concretely, this means:

- `included_esto_relationships()` (line 303) filters relationships by
  `use_case.isin(use_cases)` — since `use_cases` is always both values, every
  scope includes both `leap_to_esto_balance_conversion` and
  `ninth_to_esto_balance_conversion` rows, even the two-system scopes.
- `build_source_aggregate_edges()` (line 395) filters by
  `source_system.isin(aggregate_source_systems)` — since this is always
  `["LEAP", "NINTH"]`, NINTH source rows draw union-find edges between ESTO
  components in *every* scope, including `leap_vs_esto`, forcing merges that
  a genuine two-way LEAP+ESTO comparison shouldn't have.

`energy_balance_relationships.csv` currently has these `use_case` values
(counts from the current run, for reference):
`mapping_review` (6,993), `ninth_to_esto_balance_conversion` (2,758),
`leap_to_ninth_comparison` (2,206), `leap_to_esto_balance_conversion`
(2,029).

## What to build

Two related but separable pieces of work. Do both, in this order.

### 1. Make which scopes get built configurable

Today `run_common_esto_structure_workflow()`
(`codebase/mapping_tools/build_common_esto_structure.py:1599`) unconditionally
loops over every entry in `COMPARISON_SCOPES`
(`for comparison_scope, scope_config in COMPARISON_SCOPES.items():` at line
1637) and builds all four. Change this so the set of scopes actually built is
a parameter, not a hard-coded loop over the whole dict — e.g. an
`enabled_scopes: list[str] | None = None` argument that defaults to "all", but
can be passed down from `run_stage_2()` in
`codebase/run_mapping_pipeline.py:175` (which currently calls
`run_common_esto_structure_workflow` with no scope selection at all).

**The two scopes we actually want enabled going forward are:**

- `esto_leap_ninth` — three-way, current `leap_vs_esto_vs_ninth` behaviour
  (keep `use_cases=_ALL_USE_CASES`,
  `aggregate_source_systems=["LEAP", "NINTH"]`).
- `esto_leap` — two-way, LEAP+ESTO only, and per part 2 below this must
  **not** be influenced by NINTH at all (no NINTH edges, no NINTH-only
  required components).

We do not currently need `leap_vs_ninth` or `esto_only` — but don't delete the
capability to define more scopes later; just don't enable them by default.
Rename the two we keep to `esto_leap_ninth` and `esto_leap` (see the renaming
checklist below — the scope name string is threaded through several other
files that must stay in sync).

### 2. Make each enabled scope use its own genuine granularity

For the `esto_leap` scope specifically, wire the config so it does **not**
include NINTH at all:

- `use_cases = ["leap_to_esto_balance_conversion"]` (drop
  `ninth_to_esto_balance_conversion`)
- `aggregate_source_systems = ["LEAP"]` (drop `"NINTH"`)

For `esto_leap_ninth`, keep the current values (both use cases, both LEAP and
NINTH as aggregate source systems).

**Open design question to resolve while implementing (use your judgement,
document the decision):** `build_required_components()` (line 332) derives
which ESTO (flow, product) pairs need a common row at all, from whatever
`included_df` comes out of `included_esto_relationships()`. If `esto_leap`'s
`use_cases` excludes `ninth_to_esto_balance_conversion`, then ESTO components
that are *only* ever targeted via a NINTH mapping (no LEAP mapping reaches
them) will no longer be "required" in the `esto_leap` scope. Decide whether
that's correct (a LEAP+ESTO-only comparison shouldn't need a row for an ESTO
component LEAP never reaches) or whether such components should still get a
standalone common row for completeness. Check what
`qa_common_esto_components_missing_from_structure` looks like for `esto_leap`
after the change to sanity-check this.

After the fix, verify: rebuild `common_esto_rows.csv` and confirm
`esto_leap`'s `common_row_id` set is **no longer identical** to
`esto_leap_ninth`'s, and that (as expected) it has more/finer rows because it
isn't forced into NINTH's coarser aggregate groups. Report the before/after
row counts per scope.

## Renaming checklist — keep these in sync

The scope name strings (`leap_vs_esto`, `leap_vs_ninth`,
`leap_vs_esto_vs_ninth`, `esto_only`) are referenced outside
`build_common_esto_structure.py` in these places — confirmed via grep, update
all of them to match whatever final scope names you land on
(`esto_leap_ninth` / `esto_leap`, plus whichever of the other two remain
definable-but-disabled):

- `codebase/mapping_tools/apply_common_esto_structure.py:125-128` —
  `COMPARISON_SCOPE_SYSTEMS` dict, used to filter `source_df` to the allowed
  systems per scope during Stage 3 apply/validation (several call sites at
  lines ~845, ~859, ~1124, ~1137, ~1177).
- `codebase/mapping_tools/source_parent_anchor_validation.py:20-23` — same
  dict, duplicated.
- `codebase/mapping_tools/build_dataset_tree_structure.py:1135` and `:1279` —
  `ninth_scopes = {"leap_vs_esto_vs_ninth", "leap_vs_ninth"}`.
- `codebase/mapping_tools/build_energy_balance_relationships.py:1160` —
  hard-coded `"comparison_scope": "leap_vs_esto"`.
- `codebase/mapping_tools/inverted_conservation_validation.py:42,48` —
  hard-coded scope name literals.
- `codebase/mapping_tools/reconcile_anchor_validation.py:71-73` — maps
  `source_system -> comparison_scope` name.

Grep for the four scope name strings across the whole repo (not just
`codebase/mapping_tools`) before you finish, to catch anything this list
missed, including tests under `tests/`.

## Testing

- Re-run Stage 2 (`python codebase/run_mapping_pipeline.py --stages 2`) and
  inspect `results/common_esto/common_esto_rows.csv`: confirm
  `comparison_scope` now has your two enabled scope names, and their
  `common_row_id` sets differ (report the counts).
- Re-run Stage 3 and confirm `common_esto_comparison_data.csv` still has
  sensible `source_system` values per scope (no NINTH rows leaking into
  `esto_leap`).
- Check the existing test suite for scope-name-literal assumptions:
  `tests/test_build_common_esto_structure.py`,
  `tests/test_apply_common_esto_structure.py`, and any others that reference
  `leap_vs_esto` / `leap_vs_ninth` / `esto_only` — update them to match the
  new names/behaviour rather than deleting coverage.
- Do not modify `config/outlook_mappings_master.xlsx`.
