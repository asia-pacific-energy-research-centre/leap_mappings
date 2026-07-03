# Prompt 5 — status, findings, and issues for review

_Session date: 2026-07-03. Autonomous run while you were out._

## TL;DR

**I did not certify a "full integration" pass, because the blocker you asked me
to assume-fixable is real and is a _validation-layer_ problem, not corrupted
output.** I proved this with a real slice, fixed the one unambiguous integration
bug (the validator's default tree input did not exist), restored deleted
artifacts, and captured benchmarks. The deeper fix (the anchor validator's
methodology) is a Prompt-4 redesign and needs a decision from you before I run
or commit it — details below.

The **actual human-facing output is sound**: applied comparison values cover
**89.2%** of LEAP input by exact membership joins. The scary numbers from the
earlier stop ("3,708 missing-child failures", "contaminated boundaries") come
from the validator, not the data.

## What I changed (committed)

- **`build_dataset_tree_structure.py`**: the workflow already built a combined
  `all_trees` frame in memory but never wrote it. The lineage validator's
  default input is `results/tree_structure/all_dataset_trees.csv`, which
  **did not exist and nothing produced it** — so the validator could not run
  from its documented entry point. Added `combine_dataset_trees(...)` (pure,
  tested) and persist `all_dataset_trees.csv`.
- **`tests/test_combine_dataset_trees.py`**: 3 focused tests. Full suite now
  **120 passed, 1 skipped**.

## What I restored (generated outputs, not committed — `*.csv` is gitignored)

- `results/tree_structure/all_dataset_trees.csv` (911 rows, all datasets/axes).
- `results/common_esto/structural_artifacts/*` — regenerated deterministically
  in 2.4 s (identical QA counts: 27 ambiguous, 14 unresolved). See issue #2.

## Evidence: the "semantic safety" blocker is a validator artifact

Ran the real chain on the LEAP data (note: `raw_leap_results.csv` is **entirely
economy `20_USA`**, 1.79 M rows — so the "USA slice" _is_ the full LEAP set).
Validated 3 representative partitions with the committed `validate_partition_lineage`:

| status | reason | count |
|---|---|---|
| failed | `missing_mapped_child` | 5,500 |
| failed | `common_boundary_contamination` | 88 |
| passed | `within_tolerance` | 1,892 |

The `missing_mapped_child` failures are **not** unmapped data. Representative row:

> parent `Blast furnaces`, expected child `Blast furnaces/Blast furnaces`,
> "missing" child `Blast furnaces/Blast furnaces`, iterated across **every**
> product in the data (Additives, Ammonia, Anthracite, …).

Two mechanical causes, both methodology — matching the previously-diagnosed
mapping-granularity mismatch:

1. **Tree vocabulary ≠ lineage/mapping vocabulary.** The LEAP tree uses
   branch-path node codes (`Blast furnaces/Blast furnaces`) that never appear as
   `original_source_flow` in the lineage, so the "child" is never found. This is
   the same `Road` vs `Passenger road/…` problem noted before; prefix/tree
   roll-up does not bridge it.
2. **Parent × every-other-axis Cartesian explosion.** The check pairs each parent
   flow with every product present anywhere in the partition, regardless of
   whether that product applies — manufacturing thousands of false negatives
   (5,500 from just 3 partitions).

`common_boundary_contamination` largely fires on common rows that **legitimately
aggregate multiple ESTO components** — **99.9% of common rows map >1 source pair**
(up to 112). Common rows are membership sets by design, so a naive
"any non-child contributor = contamination" rule flags normal rollup targets.

**Conclusion:** the validator re-derives frontiers via tree walk, which is
exactly the approach that was already judged unsafe. It should instead reconcile
raw source parent totals against the pre-existing conversion outputs
(`leap_results_converted_to_esto.csv`, `ninth_results_converted_to_esto.csv`,
`esto_results_exact_rows.csv`). That is a redesign of Prompt 4, not a Prompt 5
task — see issue #1.

## Genuine (non-artifact) items — small and enumerable

- **27 ambiguous rollup assignments** (`qa_ambiguous_structural.csv`): source
  nodes that could roll into two aggregate parents, e.g. `Gas works plants` →
  {`Gas processing plants`, `Total transformation - no transfers`};
  `Freight road`/`Passenger road` → {`Road`, `Transport`, `Total final …`}.
  These need a **human rollup decision**; they are real ambiguities in the rules.
- **14 `component_missing_common_row`** (`qa_unresolved_structural.csv`): all
  concern `06.04 Additives/oxygenates` / `06_x_other_hydrocarbons` lacking a
  common row. A small, specific structural gap.

## Benchmarks (LEAP / 20_USA, this machine, miniconda py3.13)

| stage | time | notes |
|---|---|---|
| structural compile | **2.4 s** | 10 artifact frames, no value data loaded |
| prepare partition cache | ~part of apply | 77 partitions |
| partitioned apply | **167.9 s** | 77 partitions; comparison CSV 109 MB, lineage 203 MB |
| value coverage | **89.2 %** | max-view mapped ÷ true partition input |
| lineage validation | **~26 s / partition** | ⇒ ~33 min for LEAP alone; Ninth (21 economies) far larger, and artifact-dominated |

Memory stayed partition-bounded throughout (peak process ~660 MB).

## Issues to check (ranked)

1. **[Decision needed] Anchor validator methodology.** Prompt 4's
   `validate_lineage_anchors.py` reproduces the granularity artifact and is slow.
   Recommend reworking it to reconcile against the existing conversion outputs
   (your earlier documented steer) rather than tree-walking, OR at minimum
   reclassifying tree-vocab/other-axis cases as `unanchorable` instead of
   `failed`. I did **not** do this blindly — it changes what "validation passes"
   means and should be your call. Until then, Prompt 4's success criterion
   ("slice results are semantically credible") is **not** met, so Prompt 5's
   "certify full output" cannot honestly be declared complete.
2. **[Data-integrity — unexplained] Generated outputs deleted mid-session.**
   `results/common_esto/structural_artifacts/`, `.../diagnostics/`, and the
   495 MB `results/common_esto/common_esto_comparison_data.csv` (present at
   session start, Jul 2–3) **disappeared during the session**. They are
   gitignored, so git did not flag it. **My runs are scratch-scoped and do not
   touch those paths** — I could not attribute the deletion to my code (possible
   external cleaner / concurrent process?). I regenerated `structural_artifacts/`
   (2.4 s, deterministic). **I did not regenerate the 495 MB comparison CSV** —
   it needs the full Stage-3 apply; regenerate when ready.
3. **[Wiring] Partitioned application is LEAP-only.** The Prompt-3 apply run
   block only prepares/consumes `raw_leap_results.csv` (LEAP). Ninth and ESTO
   sources are not wired into the partitioned apply, yet Prompt 4/5 require all
   three. Needs Ninth/ESTO source cache + apply before a real "full" run.
4. **[Perf] Mapping-view fan-out.** `_preferred_mapping_view` emits a distinct
   view per rolled target (~750–940 view labels per partition). Accounting stays
   a summary, but the validator loops over all of them — a large contributor to
   the ~26 s/partition cost.

## What is safe to rely on right now

- Structural compilation: fast, deterministic, tested.
- Partitioned application + 89.2% coverage comparison CSV: sound and
  memory-bounded.
- The new `all_dataset_trees.csv` builder + tests.

Nothing that asserts "full output certified / Prompt 5 complete" was committed.
