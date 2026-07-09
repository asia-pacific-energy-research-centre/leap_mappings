# Prompt 1: shared rollup and hierarchy resolver

Work in `C:\Users\Work\github\leap_mappings`.

Read `AGENTS.md` and `docs/mappings_system.md` before editing. Inspect the
current worktree and preserve unrelated changes. In particular, do not stage
or modify `config/outlook_mappings_master.xlsx` or its Excel lock file.

## Goal

Create one structural resolver used consistently by LEAP, Ninth and ESTO. It
must use explicit workbook rollup rules for semantic aggregation and generated
tree `parent_code` relationships for actual hierarchy. It must never infer
ancestry from string prefixes.

## Required work

1. Review `codebase/mapping_tools/source_rollups.py`, the three tree builders,
   Stage 1 rollup handling and Claude's uncommitted anchor-validation patch.
2. Design a small function-based API that can:
   - resolve direct parent/child ancestry from a supplied tree;
   - resolve explicit source rollups from the workbook rule tables;
   - return the rule or tree evidence used for every resolution;
   - distinguish unresolved, ambiguous and cyclic relationships;
   - operate on category pairs, not on flow names alone.
3. Replace `_nearest_mapped_prefix`, `_roll_up_to_mapped` and all other
   prefix-based hierarchy inference. Do not retain a prefix fallback.
4. Preserve Claude's safe performance improvements: caches, indexed lookups,
   economy normalization, scope-loop hoisting and validation slicing.
5. Permit a source value to appear in nested ancestor aggregates. Do not flag
   `Passenger road -> Road -> Transport -> Total final consumption` merely for
   being reused along an ancestor chain.
6. Report exact duplicate rules, cycles, unresolved relationships and genuine
   conflicting assignments. Do not silently guess.

## Tests

Add focused synthetic tests for:

- Passenger road and Freight road explicitly rolling to Road.
- Ninth and ESTO hierarchy traversal through `parent_code`.
- A category whose text looks like a prefix but has no tree/rule relationship.
- Pair-sensitive rules where the same flow behaves differently by product.
- Blank rule product meaning “preserve/match all products”.
- Cycles, missing parents and exact duplicate rules.
- Legitimate nested aggregate reuse not being classified as a conflict.

Run the focused mapping and anchor-validation tests. Do not run the full data
pipeline in this prompt.

## Success criteria

- No production hierarchy decision depends on string prefixes.
- Every resolved relationship has explicit tree or rule evidence.
- Existing safe validator performance work remains present.
- Tests pass and unrelated worktree changes remain untouched.
- Commit only this prompt's files with a `codex:` commit and report the commit.

