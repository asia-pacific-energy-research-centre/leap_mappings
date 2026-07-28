# Power mapping cardinality simplification diagnosis

## Status and scope

This is a read-only diagnosis of the power mappings in
`config/outlook_mappings_master todo.xlsx`. It does not approve or enact any
workbook changes.

The purpose is to identify:

1. where ordinary one-to-many or many-to-one relationships can replace
   synthetic power rollups;
2. which application and QA layers must be repaired first; and
3. which rollups remain deliberate because they prevent a genuine
   many-to-many ambiguity or provide an explicitly requested comparison view.

The key semantic distinction is:

- **Recombining fan-out:** one source pair maps to several target components,
  but those components belong to one common comparison row. The source value
  must appear once after the components are recombined. This is a structural
  relationship, not an allocation.
- **Allocating fan-out:** one source pair is divided between separate target
  rows that remain separate in the comparison output. The allocation shares
  must sum to one.

These cases must not be handled by the same default.

## Inventory

The current power-related rules contain 36 rollup groups:

- 27 ESTO producer-type combinations. Each combines the main-activity and
  autoproducer versions of one Extended power process.
- 9 coordinated `Other and solid biomass` groups: electricity, CHP and heat,
  each represented on the LEAP, Ninth and ESTO axes.

The producer-type groups are the main simplification opportunity. For example:

```text
09.01.03.03 Others HP
09.02.03.03 Others HP
    -> 09.01.03.03,09.02.03.03 Others HP
```

Replacing all 27 producer rollup targets with their two component flows would
introduce ordinary flow-axis fan-out for:

- 120 power source pairs in `leap_combined_esto`;
- 95 power source pairs in `ninth_pairs_to_esto_pairs`.

This is expected. The ESTO Extended axis distinguishes producer type where the
LEAP and Ninth source branches generally do not.

Many-to-one relationships are not the blocker. The tested LEAP, Ninth and
partitioned application paths all summed two source rows of 4 and 6 to one
target value of 10.

## Current layer behaviour

| Layer | Many-to-one | Recombining one-to-many | Consequence |
|---|---:|---:|---|
| Common-row graph (`build_source_aggregate_edges`) | Supported | Supported for ordinary leaf targets | A source pair can connect several ESTO components into one common row. |
| Graph with subtotal or rollup-derived targets | Supported | Edges deliberately suppressed | Parent/alternate-view rows must not merge unrelated descendants. |
| LEAP direct conversion | Supported | **Unsafe by default** | Blank `allocation_share` becomes 1 on every target, so a value of 10 becomes 20 across two targets. |
| Ninth direct conversion | Supported | Conserved by automatic split | A value of 10 stays 10, but it is represented as allocated component shares rather than a source-once common-row membership. |
| Compiled partition application | Supported | **Unsafe** | The joined lineage repeats the value for every membership; 10 becomes 20. Its accounting then de-duplicates the source row and misleadingly reports 10 mapped. |
| Stage 1 one-to-many QA | N/A | **Rejects unless allocated or combined** | A valid structural fan-out is currently reported as a high-severity issue. |
| Structural compiler | Supported | Preserves every relationship row | It carries relationship/component identity but not an explicit recombine-versus-allocate contract. |

The hierarchy model can therefore represent ordinary one-to-many mappings.
The limitation is the inconsistent value-application contract around that
model.

## Proposed contract

Every included one-to-many source pair should have one of three explicit
semantics:

1. `recombine_to_common_row`
   - all target components must resolve to one `common_row_id`;
   - the source value is attached once to that common row;
   - no `allocation_share` is required;
   - component relationships remain in lineage.
2. `allocate_across_common_rows`
   - targets may resolve to different `common_row_id` values;
   - allocation shares are required and must sum to one per source pair and
     partition;
   - target-data shares or a reviewed fixed rule may supply the allocation.
3. `deliberate_aggregate_view`
   - an explicit non-expanding rollup creates an alternate comparison view;
   - raw and rolled views must remain separate so both cannot be summed as if
     independent energy.

An unclassified one-to-many relationship should fail before values are
applied. It should never silently default to full value on every target or to
an equal split.

## Rollup classification

### Strong candidates for removal after the application fix

The 27 `PRODUCER_TYPE_COMBINATION` ESTO rollups appear to hide an ordinary
source-to-two-component relationship:

```text
LEAP or Ninth power process
    -> ESTO main-activity component
    -> ESTO autoproducer component
    -> one Common ESTO comparison row
```

For leaf Extended flows, direct mappings to both components are structurally
cleaner than a synthetic comma-joined flow. These rules should be removable
only after the conversion, compiled application and QA layers implement
`recombine_to_common_row` consistently.

### Cases requiring separate review

#### Solar aliases

Expanding the producer combinations exposes eight many-to-many relationship
rows around:

- `Solar CSP` with source fuels `Solar` and `Solar nonspecified`;
- `Solar rooftop` / `Solar_rooftop` with the same source-fuel alias pattern.

This is not a reason to keep every producer rollup. It is an alias/fallback
selection issue. The selected LEAP branch/fuel spelling must be resolved before
cardinality is evaluated, so only one active source representation contributes
within a partition.

The existing branch fallback rules already prevent simultaneous standard and
interim power branches (`Electricity Generation` versus `Electricity interim`,
and the equivalent CHP and heat pairs). The solar spelling aliases need the
same source-selection principle or an equivalent normalisation rule.

#### Ninth coal power versus coal-hydrogen-blended power

Two Ninth source pairs currently target both the `Coal power` and
`Coal hydrogen blended` producer-combined flows:

- `09_01_01_coal_power :: 17_electricity`;
- `09_01_01_coal_power :: 01_x_thermal_coal`.

Producer expansion would turn each into four ESTO target flows: main-activity
and autoproducer for both process types. This is genuine semantic fan-out, not
just removal of the producer-type wrapper. It needs a decision about whether:

- the Ninth source is a deliberate aggregate of both process types and all
  four components should recombine into one common row;
- one of the two ESTO process types is incorrect; or
- the source value must be allocated between separate comparison rows.

Do not simplify these rows automatically with the other 27 groups.

#### `Other and solid biomass`

The nine coordinated rollup rules currently reconcile different process
hierarchies:

- LEAP has two branches (`Others` and `Solid biomass`);
- Ninth has two branches for CHP and heat, but three for electricity
  (`biomass`, `other renewable`, and `other fuel`);
- ESTO Extended has `Others` and `Solid biomass`, each split again by producer
  type.

The present mappings apply these aggregate views to 31 LEAP-to-ESTO rows,
29 LEAP-to-Ninth rows and 29 Ninth-to-ESTO rows.

Most input-fuel rows may be separable without an aggregate because the
fuel/product axis identifies the intended child. The likely irreducible cases
are products present under more than one process branch, especially the
electricity output row. There the sector axis can still be two-to-three across
LEAP and Ninth after product matching, which is a real many-to-many boundary.

Therefore these rollups should be narrowed, not removed wholesale:

- use direct child mappings wherever the product axis produces an unambiguous
  one-to-one, one-to-many or many-to-one relationship;
- retain a deliberate aggregate only for the exact source-product pairs that
  remain many-to-many;
- document the retained aggregate as a hierarchy-alignment choice, not as an
  application workaround.

## Implementation plan

### Phase 1 — make cardinality semantics explicit

1. Add a compiled relationship field that distinguishes recombination,
   allocation and deliberate aggregate views.
2. Validate recombination after common-row compilation:
   every target component for a source pair must resolve to exactly one
   `common_row_id`.
3. Validate allocation separately:
   targets may span common rows, but shares must be explicit and sum to one.
4. Make an unclassified one-to-many relationship a hard pre-application error.

### Phase 2 — repair all value consumers

1. In `apply_partitioned_common_esto.py`, aggregate source membership to
   `(source row, comparison scope, mapping view, common_row_id)` before applying
   the value. Preserve component relationships in a separate lineage table.
2. Use the same source-once rule in the LEAP conversion path.
3. Stop automatically equal-splitting Ninth recombining fan-out. Retain
   target-data-share allocation only for relationships explicitly classified
   as allocation.
4. Calculate accounting from the actual final delivered values as well as
   unique source coverage, so duplication cannot be hidden by de-duplicating
   `_source_row_id`.
5. Reuse one shared helper/contract across the mapping pipeline and dashboard
   comparison application rather than allowing each consumer to infer
   cardinality independently.

### Phase 3 — update QA and tests

Add tests for:

- 1:1;
- many-to-one;
- recombining one-to-many into one common row;
- allocated one-to-many across two common rows;
- many-to-many rejected unless represented by a deliberate aggregate view;
- subtotal/rollup-derived edge suppression;
- raw versus rolled view isolation;
- alias/fallback source selection;
- accounting totals matching final delivered totals.

Replace the current Stage 1 rule “one-to-many must have allocation or a
combined target” with the explicit contract above.

### Phase 4 — simplify the workbook in controlled batches

1. Start with one non-solar producer group and prove a lossless round trip
   through Stages 1–3 and both application paths.
2. Expand to the remaining unambiguous producer groups.
3. Handle solar only after alias/fallback selection is proven.
4. Hold the Ninth coal/hydrogen-blended rows for a semantic decision.
5. Decompose the `Other and solid biomass` mappings by source-product pair and
   retain rollups only for the pairs that remain genuinely many-to-many.
6. Remove superseded synthetic mapping rows and rollup rules rather than
   retaining inactive guardrail rows.

## Proof required before workbook changes

For every removed rollup group, compare the current and proposed mappings on
the same source fixtures and require:

- identical input totals;
- identical final Common ESTO totals at the intended comparison-row level;
- no source pair delivered more than once within a mapping view;
- no unclassified one-to-many or many-to-many relationships;
- no change to unrelated common-row connected components;
- lineage still identifies every target ESTO component;
- dashboard output uses the same compiled contract and produces the same
  comparison totals.

Only after those checks pass should the corresponding workbook rollup and
synthetic mapping rows be removed.
