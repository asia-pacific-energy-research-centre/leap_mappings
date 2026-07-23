# Design note: "ESTO extended" — scoping and recommendation

**Written 2026-07-23.** Gates implementation per `esto_extended_dataset_prompt.md`. Do not start
writing mapping rows or new dataset infrastructure before this note is reviewed.

## Headline finding — read this before anything else

**Most of the 264 currently-unmapped-nonzero LEAP branches almost certainly don't need a new
"ESTO extended" dataset at all.** Checked ESTO's own raw flow list
(`data/00APEC_2025_low_with_subtotals.csv`) directly against the concrete branch list (below) and
found ESTO **already has matching granular flows** for several of the largest, most promising
candidates:

| Unmapped LEAP branch | Matching existing ESTO flow(s) |
|---|---|
| `CHP plants/Coal CHP`, `CHP plants/Gas CHP` | `09.01.02 CHP plants`, `09.02.02 CHP plants` — ESTO doesn't split CHP by fuel-type at the *flow* level, but the LEAP split (Coal CHP vs Gas CHP) maps naturally onto the *product* axis instead (`Sub bituminous coal` vs `Natural gas`, exactly the two fuels each LEAP branch reports) against the SAME existing ESTO flow. This is an ordinary two-axis mapping gap, not new detail. |
| `LNG regasification` | `09.06.02.02 Regasification` (also `09.06.02 Liquefaction/regasification plants`, `10.01.03 Liquefaction/regasification plants`) |
| `NG Liquefaction` | `09.06.02.01 Liquefaction` (also `09.08.05 Liquefaction (coal to oil)`, `10.01.10 Liquefaction plants (Coal to Oil)` for related but distinct coal-to-liquids flows — verify which is the right match before mapping) |
| `Other loss and own use` | `10 Losses & own use` / `10.01 Own Use` / `10.01.17 Non-specified own uses` — ESTO already has an explicit "non-specified own uses" catch-all at this exact conceptual level |

**This changes the shape of the whole task.** The original premise ("LEAP categories currently
unmapped to ESTO, needing more detail than ESTO has") only holds for whatever's left AFTER a much
cheaper first pass: checking every one of the 264 branches against ESTO's *existing* tree for a
plausible flow/product match, the same way the anchor-validator work this same day found and
added exactly one missing `ninth_pairs_to_esto_pairs` row after a systematic gap-detector pass
(see `docs/prompts/anchor_validator_fixes_findings_20260723.md`, item on the missing-mapping-gap
detector). Recommend running that same style of detector — adapted for LEAP→ESTO instead of
NINTH→ESTO — before concluding a new dataset is needed for anything.

## Get concrete: the actual list, grouped

From `results/common_esto/qa_nonzero_unmapped_leap_branches.csv` (264 rows, regenerated
2026-07-23 14:51, all currently `qa_status == "nonzero_unmapped_leap_branch_without_esto_pair"`,
zero rows have an `indirect_esto_flow` already inferred — i.e. the existing indirect-inference
logic in `apply_common_esto_structure.py` found nothing for any of them). Grouped by `leap_flow`:

| Group | Row count | Character |
|---|---|---|
| `Total Transformation` | 52 | **LEAP's own aggregate/rollup flow** — a summary total across many products, not a specific sector. Confirmed via direct check: this exact string appears **nowhere** in the `leap_rollup_rules` workbook sheet (neither as an input nor a rolled-target label) — it is a genuinely unregistered aggregate, not a rollup-handling gap with an existing-but-broken registration. Mapping this directly alongside its own real components would double-count exactly the way this session's other fixes (connected-components grouping, `1c17af8`) were built to prevent. The real fix is registering it in `leap_rollup_rules` (as a NON_EXPANDING/DETACHED contributor, per whatever its actual real-total relationship is to its components), not adding it as a leaf mapping. |
| `Total Final Energy Demand` | 45 | Same shape and same confirmation as above — not registered anywhere in `leap_rollup_rules` under this exact string either. Same recommendation. |
| `All demand aggregated` (+ 44 `All demand aggregated/<product>` variants, 1 each) | 44+44 | **More nuanced than the other two** — confirmed this string IS already registered in `leap_rollup_rules`, as a `NON_EXPANDING` input contributing to both `Total final consumption` and `Total final energy consumption`. Despite that registration, it still shows up in the unmapped-nonzero diagnostic — meaning rollup-contributor registration alone doesn't satisfy whatever check produces this diagnostic; there's a real, narrower gap here worth its own trace (does the unmapped-branch audit in `apply_common_esto_structure.py` simply not consult `leap_rollup_rules` at all, or does it check for a *direct ESTO mapping* regardless of rollup-contributor status, which would be correct behavior and mean this row is expected to show up here even though the rollup side is fine — read that audit function's logic before assuming this is a bug). |
| `Unmet Requirements` | 17 | A LEAP modeling construct (demand the model couldn't satisfy from supply) — very likely has **no ESTO equivalent at all**, since ESTO is a historical/statistical balance, not a capacity-constrained model. Needs a human decision on whether this should ever be mapped, not a mapping design — flagging as out of scope for ESTO extended entirely. |
| `Transfers unallocated` (+ `/Transfers unallocated` duplicate) | 12+12 | Needs its own trace — "unallocated" naming suggests a placeholder/residual bucket, similar shape to `08_gas_unallocated` seen elsewhere this session (usually near-zero or catch-all, worth checking evidence before assuming it's real detail). |
| `Other loss and own use` | 11 | **Likely just a missing mapping against existing ESTO detail** — see table above. |
| `Refinery and blending transfers` (+ duplicate) | 7+6 | Products (`Bitumen`, `Fuel oil`, `Gas and diesel oil`, `Motor gasoline`, `Naphtha`, `Other products`, `Refinery feedstocks`) look like genuine refinery-output detail — check against ESTO's `10.01.11 Oil refineries` (confirmed to exist from this session's earlier `10.01 Own Use` tracing) before assuming new detail is needed. |
| `CHP plants/Coal CHP`, `CHP plants/Gas CHP` | 3+3 | **Missing mapping against existing ESTO detail** — see table above. |
| `LNG regasification` | 3 | **Missing mapping against existing ESTO detail** — see table above. |
| `Upstream liquids transfers` (+ duplicate) | 2+2 | Products (`LPG`, `Natural gas liquids`) — check against ESTO's processing/extraction flows before assuming new detail. |
| `NG Liquefaction` (+ `/Liquefaction` duplicate) | 1+1 | **Missing mapping against existing ESTO detail** — see table above. |

**Practical read:** of the ~158 rows that are the three aggregate/rollup buckets (`Total
Transformation`, `Total Final Energy Demand`, `All demand aggregated`), essentially none should
become new mapping detail — they need rollup-exclusion handling, the same class of fix already
applied to `esto_rollup_rules`/`leap_rollup_rules` elsewhere. Of the remaining ~106, several
concrete groups (CHP-by-fuel, liquefaction/regasification, own-use/losses, refinery transfers) look
like they already have an ESTO home and just need a mapping row, not new infrastructure. `Unmet
Requirements` (17) is out of scope by construction. That leaves a genuinely small residual —
plausibly just `Transfers unallocated` and `Upstream liquids transfers` (a few dozen rows) — as
actual candidates for needing something ESTO doesn't already represent, and even those need
verification, not an assumption.

## Design questions

### 1. New `source_system`/dataset, or extension of existing ESTO mapping sheets?

**Recommendation: neither, for the large majority of this list.** Given the headline finding, most
unmapped branches need an ordinary new row in the existing `leap_combined_esto` mapping sheet
against ESTO's *already-existing* tree — no new tree builder, no new rollup-rule sheet, no new
comparison-scope wiring. This is a much smaller, safer change than standing up a parallel dataset.

For whatever small residual survives the missing-mapping-detector pass recommended above (real
LEAP detail with *zero* plausible existing ESTO home): recommend treating it as **new rows in the
existing ESTO product/flow tree** (extending `build_esto_tree`'s source data, i.e. new codes under
an existing ESTO parent) rather than a wholesale new `source_system`. A genuinely new dataset
(new tree builder, new rollup-rule sheet, new `COMPARISON_SCOPE_SYSTEMS` entries) is a much larger
commitment that this residual — likely a few dozen rows across maybe 2-3 real subject areas — does
not obviously justify. Revisit this recommendation only if the missing-mapping-detector pass turns
up a residual large and structurally distinct enough to actually need parallel-dataset machinery
(a new tree, not just new leaves on the existing one).

### 2. How is double-counting against existing ESTO components prevented, structurally?

For the "just add a mapping row" cases (CHP-by-fuel, liquefaction/regasification, own-use): the
existing anchor-validator and Common-ESTO recursive-sum machinery (`exclude_parents`,
`has_data_pairs`, `literal_pairs`, the connected-components shared-frontier grouping added
2026-07-23) already exists precisely to catch a leaf being double-counted against its own parent
or a sibling's shared frontier — **use it as verification, don't design something new.** Concretely:
after adding each candidate mapping row, rerun
`pytest tests/test_source_parent_anchor_validation.py` and the real-data anchor-validator repro
(see `docs/prompts/anchor_validator_fixes_findings_20260723.md`'s "Reusable tooling" section for
the recipe) and confirm the affected parent's failure count doesn't get WORSE — if it does, that's
the double-count this question is asking about, caught by machinery that already exists.

For the aggregate/rollup buckets (`Total Transformation`, `Total Final Energy Demand`, `All
demand aggregated`): these should never get a direct mapping row at all — they need to be
recognized as rollups and excluded from ordinary additive-parent validation the same way
`esto_rollup_rules`/`leap_rollup_rules` labels already are (`anchor_exclude_parents` in
`run_mapping_pipeline.py`). Check whether `load_rollup_mode_labels` already covers these three
LEAP-side labels; if not, that's the actual gap (a `leap_rollup_rules` workbook-content addition),
not a mapping-detail gap.

### 3. Does this need its own `comparison_scope`?

**No, for the "just add a mapping row" cases** — they participate in whichever existing scopes
(`esto_leap`, `esto_leap_ninth`) the target ESTO flow already participates in, with zero new
wiring. For NINTH-inclusive scopes: if NINTH can't resolve to whatever level of ESTO detail a
mapping row targets, that's the same "NINTH can't distinguish this" shape `esto_leap_ninth`
already handles for the Oil Refining `07.12-07.17` case and the connected-components grouping fix
generalized on 2026-07-23 — no new scope-handling logic needed, the existing shared-frontier
grouping already covers "multiple LEAP-side detail collapsing onto one NINTH-resolvable Common
ESTO row."

If the small residual from question 1 turns out to need genuinely new ESTO tree codes with no
NINTH equivalent at all: those rows would need to be *excluded* from NINTH-inclusive scopes
(structurally impossible for NINTH to reconcile against detail it fundamentally can't report),
participating only in `esto_leap`. This is a config-level scope-membership decision per new code,
not new scope-resolution logic — `COMPARISON_SCOPE_SYSTEMS` already models "which systems
participate in which scope" declaratively; a new ESTO leaf simply wouldn't get a NINTH-side
`common_row_id` registered for it in `common_esto_rows.csv`, which the existing "registered but
dataless"/raw-fallback machinery (`3fdf592`, `97e20f5`, this session) already handles gracefully.

### 4. Source of the "extra detail"?

For the "just add a mapping row" majority: no new detail needed at all — it's LEAP's own existing
data, mapped onto ESTO's own existing (currently unused for this purpose) tree codes. Purely a
mapping-compiler change (new rows in `leap_combined_esto`), no new human-authored source data.

For the small residual (if any survives verification): would need a human judgment call on where
in ESTO's tree the new leaf belongs (a new child under an existing ESTO parent, using LEAP's own
breakdown as the source of the finer split) — this is real, but likely small in scope given the
headline finding above.

### 5. What breaks if this is wrong?

Same validators already in place catch this without new tooling: `Mapped-row aggregation
preservation` (the Stage 3 print showing source_total vs. common_total by scope/system — a
mapping row that double-counts would show up as `common_total` exceeding `source_total` for the
affected scope), the recursive Common ESTO validator, and `source_parent_anchor_validation.py`'s
anchor checks (which would flag the affected ESTO parent failing if a new leaf isn't correctly
counted once, not twice, or zero times). Confirm new rows are visible to all three by running the
existing test suite plus a real pipeline run before/after, not by assuming visibility.

### 6. What would dataset N+1 need to touch?

Given the recommendation above (extend existing ESTO tree/mapping rather than build a new
dataset), this question is largely moot for the current instance — there is no new dataset being
built, just new mapping rows and possibly new ESTO tree leaves. **If a genuinely new dataset is
proposed in the future** (the prompt's hypothetical "6 months from now" case), the checklist under
the current architecture would be:

- New tree builder function in `build_dataset_tree_structure.py` (parallel to
  `build_esto_tree`/`build_ninth_tree`/`build_leap_tree`), producing rows in the same
  `TREE_COLS` shape.
- New entry in `ROLLUP_SHEET_CONFIGS` (`non_expanding_rollups.py`) if the new dataset has its own
  rollup-rule sheet — zero new code, one new dict entry.
- New entry/entries in `COMPARISON_SCOPE_SYSTEMS` (`source_parent_anchor_validation.py`) for
  whichever scopes the new dataset participates in — zero new code, dict entries only.
- A new mapping sheet (parallel to `leap_combined_esto`, `ninth_pairs_to_esto_pairs`) in the
  workbook, and a new `load_raw_source_anchor_inputs`-equivalent loader.
- **Confirmed NOT needing new code under this design:** the shared-frontier connected-components
  grouping, the raw-fallback mechanism, `_build_source_internal_bad_pairs`, and the Common ESTO
  recursive validator all operate generically on `source_system` as a string key and
  `axis_col`/`other_col` conventions already — none of them special-case ESTO/LEAP/NINTH by name
  in a way that would need editing for a 4th dataset (confirmed via `test_frontier_leaf_...
  is_dataset_agnostic`-style regression tests already added this session, e.g. `97af252`).
  This is a genuine strength of the current architecture worth preserving, not a gap to close.

## Pilot scope (if the "just add a mapping row" path is approved)

Two branches with no existing overlapping ESTO coverage risk (confirmed by the existing-flow check
above finding a clean, singular ESTO match with no ambiguity):

1. **`NG Liquefaction` → ESTO `09.06.02.01 Liquefaction`** (1 real row, `Natural gas` product) —
   smallest possible pilot, single product, single clean target.
2. **`LNG regasification` → ESTO `09.06.02.02 Regasification`** (3 rows: `Electricity`, `LNG`,
   `Natural gas`) — slightly larger, same subject area, natural second step.

Do NOT pilot with `CHP plants/Coal CHP`/`Gas CHP` first despite being on the "likely clean" list —
it requires a two-axis (flow AND product) simultaneous match rather than a straightforward
flow-level target, so it's a better second-wave case once the simpler liquefaction/regasification
pilot has validated the overall approach.

## Verification plan for the pilot

1. Before: capture `results/common_esto/common_esto_comparison_data.csv`'s current row count and
   the `Mapped-row aggregation preservation` table's `esto_leap` row (source_total/common_total)
   from a real pipeline run's log.
2. Add the 1-2 proposed mapping rows to `leap_combined_esto`.
3. Rerun `codebase/run_mapping_pipeline.py --stages 1,2,3` (or the narrower stage set covering
   Stage 2/3 regeneration).
4. Confirm: `esto_leap` scope's `source_total`/`common_total` in the aggregation-preservation table
   still match exactly (100% coverage, no new drift) — a real double-count would show up here
   first, as a diff between the two.
5. Run `pytest -q tests/test_source_parent_anchor_validation.py
   tests/test_structural_resolver.py tests/test_build_dataset_tree_structure.py
   tests/test_non_expanding_rollups.py tests/test_build_energy_balance_relationships.py` — 111
   passing is the current baseline (as of `c6772a9`); confirm no regressions.
6. Rerun the anchor-validator real-data repro (recipe in
   `docs/prompts/anchor_validator_fixes_findings_20260723.md`) and confirm the flows touched by
   the pilot (`09 Total transformation sector` and its `09.06` children) don't show a NEW failure
   that wasn't there before — the existing 760-failed baseline is the reference point.
7. **Pass signal**: aggregation-preservation stays at 100% coverage for `esto_leap`, no new test
   failures, and the anchor-validator failure count for the touched flows doesn't increase.
   **Fail signal**: any of the above regresses — if so, the mapping row introduced exactly the
   double-count this whole design was meant to avoid, and should be reverted, not patched further.

## Recommended next step (not done here)

1. Run a LEAP→ESTO missing-mapping-gap detector (adapt the NINTH→ESTO one built 2026-07-23) across
   all 264 rows, not just the ~10 sampled by hand above, to get a definitive residual count before
   assuming the pilot scope above is representative of everything that needs doing.
2. Get explicit sign-off on treating the three aggregate/rollup buckets (`Total Transformation`,
   `Total Final Energy Demand`, `All demand aggregated`, ~158 of the 264 rows) as a
   rollup-exclusion fix rather than a mapping-detail fix — this is a different kind of change
   (workbook rollup-rule content) than anything else in this note.
3. Only after both of the above: implement the two-branch pilot per the scope and verification
   plan above, one branch at a time.
