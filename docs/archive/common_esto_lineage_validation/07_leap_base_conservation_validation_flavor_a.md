# Prompt: build LEAP-base conservation validation (Flavor A only)

Work in `C:\Users\Work\github\leap_mappings`. Read `AGENTS.md` and
`docs/mappings_system.md` first. You may read `C:\Users\Work\github\leap_initialisation`
for context but do not modify it.

This is a **plan-first task**: inspect the real code and artifacts, produce a
short plan, get it reviewed, then implement. A smaller honest diagnostic is
preferred over a complete-looking one built on assumptions.

## What already exists (do not rebuild, reuse)

The mappings system converts every source dataset (LEAP, Ninth, ESTO) into ONE
target vocabulary: the **ESTO-based common language** (ESTO exact rows +
automatic `connected_component_rollup` rows). There is no conversion into LEAP
or Ninth vocabulary anywhere.

`codebase/mapping_tools/reconcile_anchor_validation.py` already contains:

- `reconcile_partition` / `run_anchor_reconciliation` — per-system conservation:
  raw source parent total (left) vs that system's converted-to-ESTO total
  (right), classified from structural artifacts (exact / rollup / shared).
- `ParentBoundary` (now carries de-duplicated mapping `edges` =
  `(source_flow, source_product, esto_flow, esto_product, relationship_id)`).
- `build_anchor_contributions` + `run_anchor_contribution_breakdown` — the
  **Option A** contributor breakdown: it walks a boundary's edges and, per
  failed anchor, nets **bijective** 1:1 edges per row (`resolved_pair`,
  `value_quality=exact_direct`) while listing **entangled** fan-out /
  many-to-one members one-sided and flagging them `value_quality=unknown`,
  `mapping_status=unsafe_unallocated_fanout` (or `unsafe_many_to_one`) with NO
  fabricated per-edge split. Each check's `breakdown_remainder` reproduces the
  reconcile difference; `fully_attributed` says whether it did so per row.
  `check_id` is a deterministic content hash.

This machinery is the validator you will reuse. It is direction-agnostic in
spirit: it only needs a boundary's edges plus a raw side and a target side.

## The interlingua model you must exploit

Every dataset's `(flow, product)` source pairs attach to **common rows** (the
ESTO-based interlingua). This is recorded in
`results/common_esto/structural_artifacts/source_pair_to_common_row.csv`
(columns include: `comparison_scope`, `source_system`, `original_source_flow`,
`original_source_product`, `relationship_id`, `component_esto_flow`,
`component_esto_product`, `common_row_id`, `component_sign`, `is_exact_row`,
`requires_rollup`). Companion artifacts:
`common_row_to_source_pairs.csv` and `esto_component_to_common_row.csv`.

`comparison_scope` values present: `esto_only`, `leap_vs_esto`,
`leap_vs_esto_vs_ninth`, `leap_vs_ninth`. In every scope the common row is
ESTO-based. Two datasets' pairs are linked iff they share a `common_row_id`.

## Goal (Flavor A ONLY)

Build conservation validation in the **inverted / LEAP-base direction**, plus
Ninth-into-ESTO, reusing the Option A breakdown. For a chosen
`(source_system X, target_vocabulary Y)`:

1. Take X's raw values (for ESTO, **base year only** — see constraints).
2. Project them onto Y's pairs through the shared common rows (invert/compose
   the existing structural edges — do NOT author new mappings).
3. Verify X's parent totals are **conserved** into Y vocabulary, and when they
   are not, decompose the gap into the **child rows responsible**.

Required directions:
- `ESTO → LEAP` (the headline: does ESTO base-year mass survive into LEAP
  branch vocabulary, and which ESTO rows don't?)
- `NINTH → LEAP`
- `NINTH → ESTO` (may already be covered by the existing ESTO-base run; confirm
  and reframe rather than duplicate).

This is **pure mapping-conservation**: the Y-vocabulary values are DERIVED from
X by re-expressing X's mass on Y's pairs. Conservation holds by construction
unless (a) an X row has no Y counterpart on its common row (mass cannot be
placed → this is the finding), or (b) an X row fans out to several Y pairs
(Option A does not split it → mass held as unresolved). Both must be attributed
to the exact child rows.

**Explicitly OUT OF SCOPE (do not build):**
- Any comparison against LEAP's *actual modeled* branch values (that is
  "Flavor B" — validating the model, not the mapping). Flavor A never reads a
  LEAP results file as a third column.
- Any allocation of fan-out (Options B/C). Fan-out stays `unknown` /
  `unsafe_unallocated_fanout`, never split by a share.
- Editing either mapping workbook or any existing converted/validation output.

## Option A semantics to preserve exactly

- Bijective edge (one X pair ↔ one Y pair, sharing a common row exclusively) →
  netted per row, `value_quality=exact_direct`, `mapping_status=resolved`.
- Entangled (X pair fans out to >1 Y pair, or Y pair fed by >1 X pair) → listed
  one-sided, `value_quality=unknown`, `mapping_status=unsafe_unallocated_fanout`
  or `unsafe_many_to_one`, `contribution_difference` blank. No fabricated split.
- Every X pair and Y pair appears exactly once; the two column sums must equal
  the parent totals so the difference always reproduces
  (`breakdown_remainder` ≤ 1e-9). `fully_attributed` records per-row vs
  aggregate reproduction.

## Hard constraints / honest guards

- **ESTO is trusted for the base year only.** ESTO values are zero after ~2023.
  Scope `ESTO → LEAP` to the ESTO base year; do not pretend ESTO anchors
  projection years.
- **Y pairs with no X counterpart, and X rows with no Y counterpart, are
  `unanchorable` — never `failed` or `estimated`.** LEAP has branches ESTO/Ninth
  do not carry (e.g. hydrogen, e-fuel, ammonia; see
  `results/common_esto/qa_nonzero_unmapped_leap_branches.csv`). Report them as
  "no counterpart in <vocab>", not as errors.
- Do not change the behaviour or outputs of the existing ESTO-base reconcile /
  contribution breakdown. Prefer generalizing the edge-walk (parameterize which
  end of an edge is the raw side vs the target side) over forking it, but if you
  fork, keep the shared Option A helpers.
- Stable, content-derived IDs only (extend `check_id`; add the direction to the
  hashed key). No cache-local integer row IDs.

## Verified facts to rely on

- Inverting ESTO→LEAP is mild: ~87% of ESTO components map 1:1 to a single LEAP
  pair; ~13% are two-way (max fan-out 2). Ninth→LEAP: ~97% clean, ~3% two-way.
  So Option A resolves the large majority and flags a small entangled minority.
- The two ESTO oil-family failures and the LEAP/Ninth failures decompose to
  remainder ≤ 4e-12 under the existing Option A breakdown — that is your
  reproduction bar.

## Key paths & environment

- Structural: `results/common_esto/structural_artifacts/*.csv`
- Tree: `results/tree_structure/all_dataset_trees.csv`
- Raw: `results/mapping_relationships/raw_leap_results.csv`,
  `data/merged_file_energy_ALL_20251106.csv` (Ninth),
  `data/00APEC_2025_low_with_subtotals.csv` (ESTO)
- Existing converted (ESTO vocab): `results/mapping_relationships/*_converted_to_esto.csv`,
  `esto_results_exact_rows.csv`
- Some `codebase/*.py` files carry a UTF-8 BOM — read as `utf-8-sig`.
- Run Python with `/c/Users/Work/miniconda3/python.exe` (the repo `.venv` is a
  WSL venv unusable from Windows shells). Do not use PowerShell `python`.

## Deliverables

1. A short plan: current-state stage table, the exact inversion/composition
   step, files/functions to add or generalize, output schema, and where fan-out
   and no-counterpart cases fall.
2. Implementation reusing `build_anchor_contributions` Option A semantics.
3. New outputs under `results/common_esto/` (e.g. an
   `esto_into_leap_conservation/` folder) with a per-contributor breakdown and a
   per-check summary carrying `check_difference`, `breakdown_remainder`,
   `fully_attributed`, and the unanchorable/no-counterpart accounting.
4. Tests on a small **20USA base-year** slice covering: one bijective 1:1
   ESTO→LEAP pair (resolves), one two-way ESTO→LEAP fan-out (flagged, not
   split), one ESTO row with no LEAP counterpart (unanchorable), and a check
   whose contributions reproduce the parent difference ≤ 1e-9.
5. A note on backward-compatibility confirming existing ESTO-base outputs are
   byte/numerically unchanged.

## Decisions to surface to the user before finalizing

- Whether `NINTH → ESTO` should be a new run or is already answered by the
  existing ESTO-base reconciliation (avoid duplication).
- Whether to also emit the `ESTO → LEAP` result as an "ESTO expressed in LEAP
  branches" table (useful for seeding), or only the conservation diagnostic.

