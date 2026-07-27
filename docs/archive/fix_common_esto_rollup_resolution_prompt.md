# Fix Common ESTO rollup-aware flow validation

## Objective

Fix the Common ESTO flow hierarchy validator so that it handles `NON_EXPANDING` and `DETACHED` rollups according to their declared semantics, without recursion errors, double counting, or detached branches leaking into ordinary ancestor checks.

The latest full Stage 3 run completed the aggregation and dashboard work, but all Common ESTO flow validations failed with:

```text
RecursionError: maximum recursion depth exceeded
```

The problem is in rollup-aware recursive resolution, not in the underlying ESTO hierarchy.

## Repository

Work in:

```text
C:\Users\Work\github\leap_mappings
```

Read the repository `AGENTS.md` and the two referenced global instruction files before editing.

Preserve unrelated existing worktree changes. Before editing, inspect `git status --short` and relevant diffs. Do not stage or commit unrelated files.

## Known failure

The current resolver is:

```text
codebase/mapping_tools/build_dataset_tree_structure.py
```

around `_resolve_to_comparison_data()`.

The production graph contains synthetic rollup relationships such as:

```text
09.06.01 Gas works plants
  -> 09.06.01 Gas works plants (including own use)
  -> 09.06.01 Gas works plants
```

The first relationship is the validator's inclusive-sibling fallback; the second is the declared rollup tree relationship. Similar cycles affect:

- `09.06 Gas processing plants`
- `09.06.01 Gas works plants`
- `09.06.02 Liquefaction/regasification plants`
- `09.07 Oil refineries`
- `09.08 Coal transformation`
- `09.08.01 Coke ovens`
- `09.08.02 Blast furnaces`

Do not solve this by merely increasing Python's recursion limit or silently catching `RecursionError`.

## Required semantics

### `NON_EXPANDING`

A `NON_EXPANDING` rollup replaces or supplements the ordinary base flow for a comparison boundary. Its inclusive label may be used to resolve a missing base value, but:

- the inclusive branch must not recurse back into the same base flow;
- the base and inclusive representations must not both be counted in one ordinary additive path;
- valid detailed children must still be retained, including extended children such as Liquefaction and Regasification;
- intermediate missing labels may still resolve to their valid comparison-data descendants.

### `DETACHED`

A `DETACHED` rollup is intentionally outside the ordinary hierarchy. Its contributors must not be folded into ordinary ancestor validation.

For detached branches:

- ordinary ancestor traversal must stop at the detached boundary;
- inclusive-sibling fallback must not pull detached contributors back into the base hierarchy;
- descendants of a detached parent remain excluded even if an individual descendant has a `NON_EXPANDING` rule;
- dedicated rollup validation remains responsible for validating the detached boundary.

The declared rollup mode must be authoritative. Do not infer the mode only from the text `"(including own use)"`.

## Implementation guidance

Inspect and, if needed, update:

- `codebase/mapping_tools/build_dataset_tree_structure.py`
- `codebase/mapping_tools/common_esto_validation_orchestration.py`
- `tests/test_build_dataset_tree_structure.py`
- `tests/test_common_esto_validation_orchestration.py`

Prefer a small, explicit design:

1. Carry rollup mode/boundary metadata into the resolution logic, or provide an equivalent explicit lookup.
2. Treat inclusive fallback as a resolution operation rather than an ordinary graph edge.
3. Track the active resolution path/visited nodes so base → inclusive → base cannot recur.
4. Apply the detached boundary before applying descendant fallback.
5. Keep the existing source-frontier support for `ESTO_EXTENDED` children.

Do not weaken existing rollup validation or remove the hierarchy edges merely to make the error disappear.

## Tests to add or update

Add focused regression coverage for:

1. A `NON_EXPANDING` leaf whose real value exists only under its own inclusive label. It should resolve successfully without recursion and without being silently dropped.
2. A `NON_EXPANDING` parent with extended children, such as:

   ```text
   09.06.02 Liquefaction/regasification plants
     - 09.06.02.01 Liquefaction
     - 09.06.02.02 Regasification
   ```

3. A `DETACHED` parent whose contributors must not be included in its ordinary ancestor's sum.
4. A descendant with `NON_EXPANDING` metadata below a `DETACHED` parent; the detached boundary must still win.
5. A graph/resolution assertion that the real production tree has no recursive resolution cycle.

Preserve and rerun the existing tests around:

- `_resolve_to_comparison_data`
- Common ESTO recursive sums
- `NON_EXPANDING`
- `DETACHED`
- source-frontier and ESTO Extended validation

## Verification

Run focused tests first, then the relevant full mapping test subset. At minimum, verify that:

- no Common ESTO flow validation returns `RecursionError`;
- `ESTO`, `ESTO_EXTENDED`, `LEAP`, and `NINTH` flow validations produce actual checks or an explicit, justified skip;
- product validation behavior is unchanged;
- detached contributors do not appear in ordinary ancestor sums;
- non-expanding detailed children are not lost or double-counted;
- existing tests unrelated to this change are not broken.

If practical, run the Common ESTO validation against the existing artifacts:

```text
results/tree_structure/all_dataset_trees.csv
results/tree_structure/common_esto_source_frontier.csv
results/common_esto/common_esto_comparison_data.csv
```

Do not rerun the entire multi-hour pipeline unless the focused validation and tests pass first.

## Stage 3 status handling

Inspect the Stage 3 manifest behavior as part of the work. The last run wrote `status: completed` even though Common ESTO validation rows contained `status: error`. Do not silently classify validation errors as a successful run.

If changing status behavior, use a clear status such as `completed_with_validation_errors` or otherwise ensure downstream watchers inspect validation summaries before starting dashboard rendering. Keep this change scoped and test it.

## Deliverables

1. Minimal implementation fix.
2. Regression tests.
3. Focused verification results.
4. A short explanation of how `NON_EXPANDING` and `DETACHED` now differ.
5. Commit only the files changed for this task, using an agent-prefixed commit message such as:

```text
codex: fix rollup-aware Common ESTO validation recursion
```
