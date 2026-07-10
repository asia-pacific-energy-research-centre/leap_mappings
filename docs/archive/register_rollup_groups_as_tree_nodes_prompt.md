# Status: register `esto_rollup_rules` groups as real tree nodes

Repo: `C:\Users\Work\github\leap_mappings`.

This prompt was originally an implementation prompt. The core implementation is now complete and
committed. Keep this file as the handoff/status record for follow-up agents.

## Completed commits

- `802858a codex: register ESTO rollup tree nodes`
  - Adds workbook-backed rollup hierarchy loading from `esto_rollup_rules`.
  - Registers rolled ESTO flow labels as real flow-axis tree nodes in both ESTO and Common ESTO
    trees.
  - Splices declared children under rolled labels such as:
    - `16.01-16.02 Buildings`
    - `16.03-16.04 Agriculture and fishing`
    - `09.01-09.02 Power sector`
  - Keeps registered rolled ESTO targets unexpanded in Stage 1 relationships, so source values are
    not duplicated across component rows.
  - Treats registered rolled ESTO labels as known ESTO targets for unknown-target QA.
  - Adds focused unit tests for tree splicing, registered target pass-through, unknown-target QA,
    and structural ambiguity detection.

- `3ff2684 codex: persist Stage 3 tree artifacts`
  - The optimized Stage 3 path already built the updated trees in memory for validation, but did
    not write `esto_tree.csv`, `common_esto_tree.csv`, or `all_dataset_trees.csv`.
  - This commit writes the same tree frames used by Stage 3 validation to disk so tree artifacts
    match the validation run.

Note: commits `090478e`, `352e6e2`, and `c2586f0` landed from another concurrent session while this
work was underway. Do not assume a linear single-agent history; always inspect `git status` and
recent commits before editing.

## Verification already run

Full tests:

```powershell
C:\Users\Work\miniconda3\python.exe -m pytest -q tests
```

Result after the Stage 3 artifact patch:

```text
163 passed, 1 skipped
```

Pipeline verification:

```powershell
C:\Users\Work\miniconda3\python.exe codebase/run_mapping_pipeline.py --stages 1,2,data_convert,3
C:\Users\Work\miniconda3\python.exe codebase/run_mapping_pipeline.py --stages 3
```

The first run hit the wrapper timeout after Stage 3 had written outputs. Stage 3 was rerun cleanly
and completed successfully in about 53 minutes.

Structural artifacts were refreshed explicitly:

```powershell
@'
from codebase.mapping_tools.compile_structural_mapping_artifacts import compile_structural_mapping_artifacts
artifacts = compile_structural_mapping_artifacts()
for name, frame in artifacts.items():
    print(name, len(frame))
'@ | C:\Users\Work\miniconda3\python.exe -
```

## Verified outcomes

Tree artifacts now include the registered nodes in both ESTO and Common ESTO trees:

- `results/tree_structure/esto_tree.csv`
- `results/tree_structure/common_esto_tree.csv`
- `results/tree_structure/all_dataset_trees.csv`

Verified rows include:

- `16.01-16.02 Buildings` under `16 Other sector`
- `16.03-16.04 Agriculture and fishing` under `16 Other sector`
- `16.03 Agriculture` and `16.04 Fishing` under `16.03-16.04 Agriculture and fishing`
- `09.01-09.02 Power sector` under `09 Total transformation sector`

NINTH AUS 2023 Motor gasoline now appears once under the rolled Agriculture/Fishing label in
`results/common_esto/common_esto_comparison_data.csv`:

```text
source_system = NINTH
economy = 01_AUS
scenario = reference
year = 2023
common_flow_label = 16.03-16.04 Agriculture and fishing
common_product_label = 07.01 Motor gasoline
value = 6.941255
```

It does not appear under `16.03 Agriculture` or `16.04 Fishing`.

Important correction to the original prompt: the old prompt cited `3.470627` for this example.
With the current `data/merged_file_energy_ALL_20251106.csv`, the raw NINTH value is `6.941255`.
The old value is stale, not a failed verification.

Structural artifact checks:

- `results/common_esto/structural_artifacts/source_pair_to_common_row.csv` no longer contains the
  stale bare `"Agriculture and fishing"` source row.
- `qa_ambiguous_structural.csv` and `qa_conflicting_structural.csv` do not newly flag the three
  in-scope groups.
- LEAP `Other sector/Agriculture` and `Other sector/Fishing` still land on precise `16.03` and
  `16.04` common labels in the structural artifact. That is acceptable: LEAP has precise rows and
  does not need explicit rolled-label relationship rows for the tree validator to resolve the
  rolled parent.

## Current known caveats

- `results/tree_structure/common_esto_validation.csv` has checks for the synthetic
  `16.03-16.04 Agriculture and fishing` parent. It may not have checks for `16 Other sector` in a
  given source/year/product context if the parent row itself is absent from the comparison data.
  That absence is expected from the validator's current lookup behavior.

- The deeper transformation chains under `09.06`, `09.08`, `09.07`, and `09.12` were explicitly out
  of scope for semantic review. The generic mechanism can register them, but existing overlapping
  child claims in the workbook remain a sheet-authoring question, not a code fix to invent here.

- The optimized Stage 3 path now writes tree CSVs, but if future fast-path workflows bypass
  `run_mapping_pipeline.py --stages 3`, they must also ensure tree artifacts are refreshed or
  clearly documented as stale.

## Remaining uncommitted work at the time of this update

These files were still dirty/untracked after the completed commits and were not committed as part
of this task:

- `codebase/mapping_tools/apply_ninth_to_esto_conversion.py`
- `codebase/mapping_tools/convert_leap_results_to_esto.py`
- `docs/mappings_system.md`
- `docs/prompts/regen_common_esto_comparison_fast_path_prompt.md`
- `docs/guide_outlook_mappings_master.md`
- `docs/prompts/explore_parent_level_own_use_comparison_rows.md`
- `docs/prompts/register_rollup_groups_as_tree_nodes_prompt.md` (this status update)

The two conversion-script changes apply `allocation_share` when present. They predated the tree-node
commit and are now only relevant as fallback behavior for unregistered rollup targets. All active
current `esto_rollup_rules` rows with rolled flow labels have hierarchy fields populated, so the
registered target path does not use the allocation split.

## What is next

1. Decide whether to keep, revise, or revert the pre-existing `allocation_share` converter changes.
   They are not needed for the currently registered tree-node rollups, but they may still be useful
   as fallback behavior if future `esto_rollup_rules` rows intentionally lack
   `parent_flow_label` / `child_flow_labels`.

2. Update `docs/guide_outlook_mappings_master.md` and `docs/mappings_system.md` so they no longer
   describe registered ESTO target rollups as always fan-out/split. The current rule is:
   registered hierarchy rollups remain single full-value rolled target rows; only unregistered
   fallback rollups may expand/split.

3. Optionally add a short Stage 3 implementation note near `run_stage_3()` explaining why the
   optimized path writes tree CSVs directly instead of calling `run_tree_structure_workflow()`.

4. Do not rerun the full pipeline unless another code/workbook change affects relationships,
   conversion, common structure, or validation. The latest Stage 3 verification has already
   completed cleanly.

