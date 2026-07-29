# Separate-axis mapping contract exploration

**Status:** paused at two required human decisions

**Exploration branch:** `codex/separate-axis-mapping-exploration`

**Baseline commit:** `f5e0bd7`

**Canonical workbook tested:** `config/outlook_mappings_master.xlsx`

**Workbook SHA-256:** `B1826A4E7F9DB60E491E0FF04B42DE489CFA395EEA68D551675CF9DF2736079A`

**Last measured:** 2026-07-29

## Executive finding

A separate-axis representation can reproduce the current accepted pair
relationship set and Common ESTO component membership, but only after applying
a large reviewed compatibility override layer.

- The accepted workbook normalises to 7,649 unique active complete
  relationships.
- Independent axes plus strict non-zero valid-pair filtering reproduce 5,008
  relationships directly.
- They miss 2,641 accepted relationships and create 1,132 additional Cartesian
  relationships.
- A generated review-only layer of 2,641 includes and 1,132 excludes restores
  the exact accepted relationship set.
- With that restored set, all 9,826 measured Common ESTO component memberships
  are unchanged.
- Without overrides, only 2,942 of 10,132 compared component memberships are
  unchanged; 2,880 change membership, 4,004 are missing, and 306 are extra.

The representation is therefore technically viable as a compiler behind a
compatibility boundary. It is not ready to replace the maintained pair sheets.
Two prompt-defined stop conditions are present:

1. Forty-six source products have target-product sets that vary by source flow
   and are not explained by strict valid-pair filtering alone.
2. The locally available ESTO vintages show pair status churn but do not provide
   enough history to choose an accepted dormancy duration.

The recommendation is to proceed only with a shadow compiler after these two
policies are reviewed. Do not migrate sibling repositories or edit the
canonical workbook yet.

## Safety and baseline

The exploration did not edit:

- `config/outlook_mappings_master.xlsx`;
- `C:\Users\Work\github\leap_mappings\config\outlook_mappings_master todo.xlsx`;
- any production code in `leap_initialisation` or `leap_dashboard`.

The main checkout's todo workbook has SHA-256
`0C10BD068DD9CFC8094D1CACA50941E2D9B7EE03E3F6E2E79B28962B4F72CB2C`.
It was used only as read-only evidence for the proposed 27 detailed
power-process rollups. Those rollups are not treated as accepted configuration
in this worktree.

Generated evidence is under
`results/separate_axis_mapping_exploration/`. Every generated mapping or
override row remains unreviewed and must not be written to the workbook
automatically.

## Proposed contract

### Flow mappings

One reviewed row maps a source flow or branch to a target flow. Minimum fields:

```text
mapping_name
comparison_scope
source_system
source_flow
target_system
target_flow
relationship_semantics
notes
```

### Product mappings

One reviewed row maps a source product or fuel to a target product. Minimum
fields:

```text
mapping_name
comparison_scope
source_system
source_product
target_system
target_product
relationship_semantics
notes
```

The unresolved evidence shows that a globally context-free product mapping is
not sufficient for every current relationship. The decision is whether to:

- retain narrow pair overrides for flow-qualified product meaning; or
- add an explicit optional `source_flow_context` field to the product-axis
  contract.

Silently deriving flow-qualified product meaning from pair rows would defeat
the purpose of the separation.

### Valid-pair registries

Each generated target registry records:

```text
dataset
flow
product
flow_is_parent
product_is_parent
pair_is_subtotal
first_observed_year
last_observed_year
economy_support_count
year_support_count
nonzero_observation_count
source_vintage
source_fingerprint
pair_status
scenario_scope
registry_review_status
```

`data_valid` means at least one finite value has absolute magnitude greater
than `1e-9` in the selected source and scenario scope. A structurally present
pair with no such value is `zero_only`, not data-valid.

Generated snapshots are review inputs. An accepted registry needs its own
version and review state; a newly generated snapshot must never replace it
silently.

### Pair overrides

The prototype produces the following narrow reason codes:

- `reserved_zero_only_target_pair`;
- `reserved_target_pair_absent_from_registry`;
- `cartesian_pair_not_reviewed`.

Every override carries `include` or `exclude`, a human note, and
`review_status=unreviewed`.

The current proof requires 3,773 such rows:

| Action | Reason | Rows |
|---|---|---:|
| include | reserved zero-only target pair | 1,367 |
| include | target pair absent from registry | 1,274 |
| exclude | Cartesian pair not reviewed | 1,132 |

This is too large to accept as an opaque exception table. Before adoption, the
rows should be reduced by separating structural/reserved validity from
observed non-zero validity and by resolving the 46 flow-qualified product
groups.

### Explicit relationship semantics

The compiler must classify one-to-many relationships as exactly one of:

- `recombine_to_common_row`;
- `allocate_across_common_rows`;
- `deliberate_aggregate_view`;
- `unresolved`.

Unresolved many-to-many membership is rejected. The fixture implementation
delivers each source value once, retains component lineage, checks allocation
shares sum to one, and rejects unresolved many-to-many cases.

## Measured valid-pair evidence

### ESTO vintages

| Source | Pairs | Data-valid | Zero-only |
|---|---:|---:|---:|
| 2024 with subtotals | 8,487 | 3,408 | 5,079 |
| 2025 with subtotals | 8,487 | 3,439 | 5,048 |
| ESTO Extended | 9,696 | 4,254 | 5,442 |

The two base ESTO vintages have the same structural pair keys. There are no
added or disappeared keys, but 123 status changes:

- 46 move from `data_valid` to `zero_only`;
- 77 move from `zero_only` to `data_valid`.

This demonstrates that non-zero validity is volatile. A one-vintage zero-only
result must not delete a mapping.

Proposed policy, requiring approval:

1. New pair keys are `candidate_added` until reviewed.
2. A previously accepted key that disappears or becomes zero-only is
   `pending_confirmation` for the first affected vintage.
3. After two consecutive affected vintages it becomes `dormant`, while the
   mapping remains retained.
4. Deletion requires an explicit semantic review; it is never an automatic
   consequence of data absence.

The local history supports the pending state but cannot empirically justify
the proposed two-vintage threshold.

### Ninth scenario scope

| Scope | Pairs | Data-valid | Zero-only |
|---|---:|---:|---:|
| all scenarios | 12,770 | 2,935 | 9,835 |
| reference | 12,769 | 2,804 | 9,965 |
| target | 12,770 | 2,922 | 9,848 |

Reference versus target changes 169 keys/status records:

- one target-only structural key, which is zero-only;
- 13 pairs move from data-valid in reference to zero-only in target;
- 131 move from zero-only in reference to data-valid in target;
- 24 retain data-valid status but change subtotal/parent metadata.

Scenario choice therefore materially changes the registry. The accepted Ninth
registry should be explicit about whether it is:

- scenario-union validity for mapping availability; or
- separate reference and target validity for scenario-specific QA.

The recommendation is a scenario-union accepted availability registry plus
separate scenario-status columns. This prevents a target-only technology from
being treated as globally invalid while preserving scenario diagnostics.

## Relationship reproduction

### Relationship rows

| Status | Rows |
|---|---:|
| exact relationship match | 5,008 |
| accepted relationship not compiled | 2,641 |
| extra factorised relationship | 1,132 |

### Source-pair target sets

| Status | Source pairs |
|---|---:|
| lossless without override | 3,474 |
| missing accepted targets | 2,313 |
| extra factorised targets | 929 |
| both missing and extra targets | 124 |

Strict non-zero target validity is the main reason accepted rows are missing:
1,367 accepted rows point to zero-only target pairs and 1,274 point to pairs
absent from the selected strict registry.

### Flow-qualified product semantics

All 46 detected product-context groups remain unresolved by strict registry
filtering:

- 36 `leap_to_esto` products in `BOTH`;
- 5 `leap_to_ninth` products;
- 5 `ninth_to_esto` products.

The LEAP-to-ESTO group includes common fuels such as electricity, heat,
natural gas, diesel, LPG, coal products, biomass products, solar
nonspecified, and hydrogen. The Ninth-to-ESTO cases are aggregated Ninth fuel
categories, including thermal coal, coal products, other hydrocarbons, jet
fuel, and other petroleum products.

These are not safe to dismiss as naming noise. The detailed table is
`results/separate_axis_mapping_exploration/diagnostics/product_context_dependence.csv`.

## Common ESTO structure

Axis-only compilation changes the graph substantially:

| Membership result | Components |
|---|---:|
| unchanged | 2,942 |
| changed component membership | 2,880 |
| missing from compiled graph | 4,004 |
| extra in compiled graph | 306 |

After applying the generated compatibility overrides, all 9,826 component
memberships are unchanged.

This proves that the current Stage 1 relationship schema is a viable
compatibility boundary. It does not prove that the 3,773 generated overrides
are semantically acceptable.

## Power-process test

The read-only review workbook contains 27 detailed main-activity/autoproducer
rollup groups, each with two ESTO component flows. It contains 120 direct LEAP
mapping rows to those rolled flows.

- Five groups have all direct mappings supported by two non-zero-valid
  component pairs.
- Across all groups, 46 of 120 direct mappings have both component pairs
  non-zero-valid in at least one of base ESTO or ESTO Extended.
- Twenty-two groups need review under the strict rule.

This does not mean the remaining power mappings are wrong. It means non-zero
data validity alone is too narrow to serve as structural model validity for
reserved and future technologies. The compiler can represent each reviewed
power mapping as:

1. one source flow mapping to two component flows;
2. one independent product mapping;
3. a reviewed structural/reserved validity decision for each component pair;
4. `recombine_to_common_row`;
5. one source delivery with two component-lineage rows.

Solar aliases, coal versus coal-hydrogen-blended power, and the
`Other and solid biomass` hierarchy alignment must remain separate reviewed
rules. The experiment did not alter any rollup.

## LEAP valid-pair authority

No single locally available workbook is a sufficient global authority.

Measured evidence:

- 21 economy templates were readable;
- their union contains 1,058 branch paths;
- 407 paths are explicit transformation fuel-leaf paths;
- seven latest observed balance exports are available across four economies
  (`01_AUS`, `02_BD`, `12_NZ`, and `20_USA`);
- those exports contain 8,229 observed flow-product keys, of which 723 have a
  non-zero observation and 7,506 are zero-only.

The recommended reproducible authority is layered:

1. **Structural branch authority:** the union of the 21 versioned economy
   templates, with support counts and fingerprints.
2. **Observed pair evidence:** latest reviewed balance exports by economy and
   scenario, explicitly labelled partial evidence.
3. **Reviewed reserved-pair configuration:** deliberate future technologies,
   aliases, and branches not expected to be non-zero in current exports.
4. **Refresh manifest:** template/export file list, fingerprints, date,
   economy/scenario coverage, and generated-versus-accepted review status.

Missing from one template or one economy is never global invalidity. Demand
templates provide branch structure but do not manufacture a global
branch-fuel Cartesian registry. `new leap rows.xlsx` remains planning evidence,
not authority.

## Cross-repository impact

The detailed matrix is
`results/separate_axis_mapping_exploration/migration_matrix.csv`.

| Repository | Consumer boundary | Proposed input | Risk |
|---|---|---|---|
| `leap_mappings` | Stage 0 / workbook maintenance | axes, registries, reviewed overrides | high |
| `leap_mappings` | Stage 1 relationship builder | compiled compatibility pair view | high |
| `leap_mappings` | Stages 2–3 | unchanged relationship/Common ESTO schemas initially | low to high; value delivery is high |
| `leap_mappings` | candidate, hierarchy, and subtotal QA | accepted registries plus compiled view | medium-high |
| `leap_initialisation` | canonical mapping loaders | versioned compiled pair view | medium |
| `leap_initialisation` | supply/demand/transformation readers | central loader, not direct sheet reads | high |
| `leap_initialisation` | duplicated maintenance utilities | retire only after compiler acceptance | high |
| `leap_dashboard` | main data path | unchanged Common ESTO data/metadata | low |
| `leap_dashboard` | mapping diagnostics | compiler manifest and compatibility diagnostics | low-medium |

The preferred ownership boundary from the prompt is supported:

- `leap_mappings` owns axes, registries, compilation, QA, rollups, and Common
  ESTO membership;
- `leap_initialisation` consumes compiled mappings or Common ESTO outputs and
  owns LEAP template/export evidence;
- `leap_dashboard` consumes Common ESTO data/metadata and should not infer
  mapping semantics.

`leap_initialisation` already warns that pair/context mappings must not be
collapsed into a global fuel-only dictionary. That warning remains correct.

## Value-delivery risk

The current value application path was inspected separately from the mapping
set proof. One source relationship may merge to several component rows before
the final aggregation. Accounting diagnostics de-duplicate source row IDs, but
that does not itself guarantee that the final value was delivered only once.

The prototype fixture establishes the required future contract:

- source value delivery happens once per mapping view;
- recombined components share one `common_row_id`;
- allocation shares sum to one;
- deliberate aggregate views are explicit;
- lineage retains every component without repeating the source value;
- unresolved many-to-many relationships fail.

This must be verified or corrected in the real Stage 3 application before a
separate-axis compiler becomes authoritative. Aggregate-total equality alone
is not an acceptance test.

## Performance finding

The correctness-first registry scan is not production-fast:

- three object-typed Ninth scans were abandoned and replaced with a one-pass
  all/reference/target bundle;
- cached snapshots make subsequent runs practical;
- current Stage 1 rollup expansion remains Python-loop heavy and took roughly
  18 CPU-minutes for accepted plus axis-only contracts in this environment;
- the initial production graph/renderer path was also too slow for interactive
  proof, so the final graph proof uses a vectorized edge enumeration verified
  against the production edge semantics on focused fixtures, followed by the
  production override, union-find, and non-expanding-frontier functions.

Production implementation should cache normalized evidence and vectorize
rollup expansion and source-edge enumeration before enabling routine refresh.

## User direction after the exploration

Recorded on 2026-07-29:

1. **Park the proposal.** Treat separate-axis mappings as a suggestion for
   future development, not as an active implementation task.
2. **Axes are relations, not functions.** Sector/flow and fuel/product mappings
   may each be one-to-many or many-to-one between datasets. The design must not
   assume one global target per sector or fuel.
3. **Temporal pair evidence should bridge the datasets.** Use non-zero ESTO
   evidence in the final available ESTO year to describe combinations active
   at the historical boundary. Use non-zero Ninth evidence in years after that
   boundary to describe combinations possible in projections.
4. **The projection quantifier remains open.** Before implementation, decide
   whether a Ninth pair qualifies when it is non-zero in any post-ESTO year or
   must be non-zero in every relevant post-ESTO year. The former admits
   technologies introduced later; the latter describes continuous activity.
   The registry should probably retain both facts rather than discard one.
5. **Avoid conflicting cross-level mappings.** In general, do not map a source
   parent to a target child when a source child or sibling relationship already
   maps into children of that target parent in a way that crosses the active
   hierarchy frontier. This needs a precise graph rule and counterexample tests
   before it can be enforced.
6. **The size of a legitimate exception layer is unknown.** The current 3,773
   generated compatibility overrides must not be treated as the desired future
   design.
7. **Desired benefits:** easier auditing, fewer maintained rows, and clearer
   semantics.

The first practical future use should therefore be an audit and suggestion
view over the reviewed pair mappings. Replacement of the pair sheets is a
separate, later possibility that would need to prove a genuinely smaller and
better-understood contract.

One distinction remains important: allowing one-to-many and many-to-one axis
relations does not by itself resolve conditional meaning. A fuel can map to
products A and B globally, or it can map to A only under one flow and B only
under another. The 46 detected product-context groups should be used to decide
whether target-pair validity is sufficient to express that condition or
whether explicit flow context is still needed.

### Accepted pair universe clarification

The proposed registry is not the Cartesian product of every sector with every
fuel. It is a dataset-specific set of exact accepted key pairs:

- exact flow/product pairs structurally present in ESTO, plus any reviewed
  reserved ESTO pairs;
- exact most-specific sector/fuel pairs structurally present in Ninth, plus any
  reviewed reserved projection pairs; and
- exact LEAP branch/fuel pairs evidenced by models/templates/exports or retained
  as reviewed accepted pairs.

Each accepted pair then carries evidence fields such as:

- `historical_boundary_active`;
- `projection_future_active`;
- first and last active years;
- supporting scenarios and economies; and
- generated, reviewed-reserved, or rejected authority.

This keeps zero-only or future pairs available without pretending they are
currently active. It also gives the compiler a direct membership test that can
reject unsupported products of many-to-many axes. For ESTO and Ninth, the
structural pair universe can largely be generated from exact source rows. LEAP
remains harder because a template can prove branch structure without proving
every branch/fuel combination; reviewed source pairs may be needed as bootstrap
authority.

### Feasibility against the original problems

This revised model addresses, but does not automatically eliminate, the
prototype's failures:

- The 1,367 accepted relationships targeting structurally present zero-only
  pairs should no longer be rejected merely for lacking non-zero evidence.
- An accepted-pair membership test should remove many or all of the 1,132
  unsupported Cartesian relationships, provided the pair universe is complete.
- The 1,274 accepted relationships absent from the strict source-generated
  registry still need classification as missing source authority, reviewed
  reserved pairs, or questionable current mappings.
- Exact pair membership may resolve some conditional meanings, but cannot
  resolve a case where products A and B are both accepted under several flows
  and only the source-flow context selects between them.
- Pair membership does not enforce the non-crossing hierarchy-frontier rule.
  That remains a separate compiler validation.
- Pair membership does not define one-to-many value delivery. Recombination,
  allocation, and contextual selection remain explicit relationship semantics.

The design is technically realistic as an audit and suggestion system. It is
not yet proven to reduce maintained rows enough to replace the pair sheets.
That question can be answered with one bounded follow-up experiment:

1. Generate exact accepted-pair universes for ESTO and Ninth and bootstrap the
   LEAP universe from the best available exact-pair evidence.
2. Add boundary-year and post-boundary activity fields without filtering pairs
   out of the universe.
3. Recompile the many-to-many axes using exact accepted-pair membership.
4. Apply a diagnostic version of the non-crossing hierarchy-frontier rule.
5. Recount missing relationships, extra relationships, conditional-context
   exceptions, and the genuinely human-maintained rows required.

Proceeding beyond an audit/suggestion role would only be justified if this
experiment produces a substantially smaller, semantically classified exception
set while preserving exact current relationships and source-once delivery.

## Possible staged implementation plan if resumed

### Stage A — decide the two blocked policies

1. Choose narrow pair overrides versus an explicit `source_flow_context` on
   product mappings for the 46 groups.
2. Approve or replace the proposed two-consecutive-vintage dormancy threshold.
3. Decide whether structural/reserved validity is a separate accepted status
   from observed non-zero validity.

### Stage B — shadow registries and compiler in `leap_mappings`

1. Add versioned generated and accepted registry locations outside `config/`.
2. Add reviewed structural/reserved-pair configuration.
3. Generate axes from the current workbook only as a bootstrap.
4. Emit compatibility pair views with the exact existing sheet columns.
5. Run exact relationship, cardinality, hierarchy, subtotal, graph membership,
   and source-once gates.

The current pair sheets remain authoritative throughout Stage B.

### Stage C — reduce and review overrides

1. Partition generated includes into structural reserved, dormant, missing
   authority, and genuine flow-qualified semantics.
2. Review generated excludes as either correct invalid Cartesian products or
   evidence that an axis mapping is too broad.
3. Resolve the 27 power groups with explicit structural/reserved validity.
4. Keep solar, coal/hydrogen, and other/solid-biomass exceptions independent.

### Stage D — switch the mappings-owned boundary

1. Make Stage 1 consume the compiler's accepted compatibility view.
2. Keep its output schema stable.
3. Shadow-run current and compiled paths for at least two source refreshes.
4. Require zero unexplained relationship, Common ESTO membership, and
   source-once differences.

### Stage E — migrate consumers without sibling production edits in this task

1. Add one compiled-pair loader in `leap_initialisation`.
2. Migrate active direct readers in small groups; leave legacy copies until
   their callers are proven retired.
3. Keep `leap_dashboard` on Common ESTO outputs; update only diagnostics
   provenance.
4. Remove compatibility pair-sheet dependence only after all consumers and
   rollback procedures are proven.

## Verification

Focused tests cover:

- 1:1 and many-to-one compilation behavior;
- recombining and allocated one-to-many source-once delivery;
- rejected unresolved many-to-many;
- registry additions, removals, and status changes;
- one-economy/year validity;
- zero-only and subtotal pairs;
- Ninth scenario scope;
- aliases/fallbacks;
- single-pass Ninth bundle equivalence;
- vectorized graph membership equivalence with production edge semantics.

Command:

```text
C:\Users\Work\miniconda3\python.exe -m pytest tests\test_separate_axis_mapping_exploration.py -q
```

Result: `10 passed`.

An additional relevant run of the existing Common ESTO and Stage 1 tests
reported 53 passes and one pre-existing failure:
`test_esto_leap_scope_excludes_ninth_relationships_and_aggregate_edges`
asserts that only `esto_leap_ninth` and `esto_leap` are enabled, while the
committed production constant already enables four scopes, including both ESTO
Extended scopes. This exploration did not change either file and did not
rewrite the stale assertion.

The canonical workbook hash was unchanged, and no sibling production files
were edited.

## Questions to resolve if resumed

Before any future shadow implementation, a reviewer must decide:

1. Should flow-qualified product meaning be represented by narrow reviewed
   pair overrides, or by an explicit optional flow-context key on product
   mappings?
2. Should an accepted pair become dormant after two consecutive absent or
   zero-only vintages, or use another threshold?
3. Does post-ESTO projection validity mean non-zero in any later Ninth year,
   every later Ninth year, or two separately reported evidence states?
4. What exact hierarchy-frontier rule rejects a conflicting parent-to-child
   mapping without rejecting legitimate coarse mappings between datasets?

MAPQ-033 is parked as a future-development suggestion. Until it is deliberately
resumed, treat every generated axis, registry, candidate, and override as
review-only evidence.
