# Hierarchy/subtotal contract v1 reference

## Packaging

Contract name: `aperc_hierarchy_subtotal_contract`

Schema version: `hierarchy_subtotal_contract_v1`

Default build directory:
`results/hierarchy_subtotal_contract/current/`

The manifest is the commit marker. Consumers must select one directory
explicitly, validate its contract name/schema/build identity, verify every
member hash and row count, and fail without falling back to another build.

## Members

| Member | Grain | Purpose |
| --- | --- | --- |
| `datasets.csv` | dataset | Source version, adapter version, raw/derived kind, provenance |
| `axis_nodes.csv` | dataset + axis + node | Declared parent, depth, child count, leaf/parent status, hierarchy completeness, source flags as evidence |
| `declared_relationship_edges.csv` | dataset + axis + parent + child + relationship type | Ordinary hierarchy separated from additive rollups, aliases, replacements, detached boundaries, and graph categories |
| `canonical_source_pairs.csv` | dataset + two normalized mapping-axis nodes | Per-axis structural booleans and canonical pair boolean |
| `value_conformance_diagnostics.csv` | dataset + context + validation axis + parent + fixed opposite-axis node | Parent value versus immediate-child sum without changing structure |

The manifest records input paths/hashes/sizes, adapter versions, producer
commit, member hashes/row counts/key columns, compatibility declarations,
validation status, generation time, and content-derived build ID.

## Invariants

- Ordinary hierarchy edges alone automatically define structural parenthood.
- Duplicate nodes, duplicate edges, self-parent edges, missing ordinary-edge
  endpoints, contradictory ordinary parents, and cycles are rejected.
- `pair_is_subtotal` is exactly
  `any(axis_node_is_structural_parent)`.
- Complete active mapping pairs contain a boolean only when both nodes resolve.
  Unresolved evidence remains in the review queue.
- `MIXED` is never a canonical boolean.
- An additivity failure remains a failure even when attributable to source
  non-additivity.
- `passed` is not used for missing or untested contexts.

## Worked non-additivity example

For a fixed economy, scenario, year, and fuel:

```text
Structural subtotal: YES
Children add to parent in this context: NO
```

`09_06_gas_processing_plants` has declared immediate sector children, so the
first line is stable. If its published parent value differs from the signed
sum of those children, the diagnostic records `failed`,
`difference_exceeds_tolerance`, the signed/absolute difference, positive and
negative child sums, and child counts. The parent remains a structural
subtotal.

## Consumer contract

`leap_dashboard` and `leap_initialisation` consume the serialized artifact;
neither imports an arbitrary `leap_mappings` checkout or recomputes pair
parenthood. Period-specific source flags may remain in initialisation value
filters, but their output must be named and kept separate from structural
status. The dashboard checking surface must present structural and numerical
status as two distinct fields.

