# Explore a separate-axis mapping contract across the three LEAP repositories

> **Status 2026-07-29:** Resumed as an isolated prototype after further user
> direction. The prototype may generate review workbooks and compatibility
> views, but it must not edit the canonical workbook or change production
> consumers.
>
> **Current checkpoint:** The prototype is split into an editable
> `config/outlook_mappings_single_axis_prototype.xlsx`, a generated do-not-edit
> `config/outlook_mappings_key_pairs_generated_prototype.xlsx`, and a generated
> do-not-edit `config/outlook_mappings_master_generated_prototype.xlsx`. The
> last workbook preserves the canonical sheet interface and passes the current
> loader and Stage 1 without a consumer-code change. Semantic acceptance and
> direct compilation from the editable workbook remain open.

## Objective

Test whether the maintained pair mappings can be factorised into:

1. flow/sector mappings;
2. fuel/product mappings;
3. a strict, versioned registry of valid flow-product pairs for each dataset;
4. a small set of explicit pair-level overrides.

The experiment must determine whether this model can reproduce the current
mapping relationships and Common ESTO output losslessly while making mapping
maintenance substantially simpler.

This is an isolated exploration. Do not edit either
`config/outlook_mappings_master.xlsx` or
`config/outlook_mappings_master todo.xlsx`. Do not change production code in
`leap_initialisation` or `leap_dashboard`. Read those repositories to assess
impact and identify consumers, but keep prototype implementation in this
`leap_mappings` worktree.

## Repositories

Read the applicable instructions in all three repositories before beginning:

- `C:\Users\Work\github\leap_mappings`
- `C:\Users\Work\github\leap_initialisation`
- `C:\Users\Work\github\leap_dashboard`

`leap_mappings` remains the canonical owner of mapping logic. The dashboard
must consume compiled Common ESTO outputs and must not reproduce mapping or
valid-pair logic.

## Required starting references

Read at least:

- `docs/mappings_system.md`
- `docs/power_mapping_cardinality_simplification_diagnosis.md`
- `docs/guide_outlook_mappings_master.md`
- `docs/handover/cross_repository_data_contracts.md`
- the three mapping sheets and the three rollup-rule sheets in the canonical
  mapping workbook;
- the configured Ninth and ESTO source files used by the current pipeline;
- the relevant mapping and Common ESTO consumers in all three repositories.

Treat documentation as a guide, not proof. Verify claims against current code,
configuration and outputs.

## Core model to test

Prototype four logical inputs.

### 1. Flow mappings

Map only the sector/flow axis:

```text
source_system
source_flow
target_system
target_flow
comparison_scope
relationship_semantics
notes
```

The model must support one-to-one, many-to-one and one-to-many flow
relationships.

### 2. Product mappings

Map only the fuel/product axis:

```text
source_system
source_product
target_system
target_product
comparison_scope
notes
```

Determine which product mappings are genuinely global and which require
dataset, scope or flow-specific qualification.

### 3. Valid flow-product pairs

Maintain one generated registry per dataset. At minimum include:

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
```

The registry describes dataset availability. It is not itself a mapping.

### 4. Pair overrides

Keep pair-level configuration only where independent axes plus valid-pair
filtering are insufficient. Candidate reasons include:

- deliberate many-to-many hierarchy alignment;
- allocation across separate common rows;
- sign or relationship-type handling;
- alias/fallback source selection;
- scope-specific inclusion;
- reserved categories not currently present in data;
- reviewed exclusion;
- a product mapping whose meaning genuinely depends on the flow.

Every override must have a narrow reason code and human note.

## Valid-pair rules to investigate

### Ninth Outlook

Start from this proposed rule:

> A Ninth flow-fuel pair is data-valid when it has at least one finite,
> non-zero year value for at least one economy in the configured Ninth source
> dataset.

Test the rule rather than assuming it is sufficient.

The output must:

- state which scenarios are included and show whether scenario selection
  changes the registry;
- scan all numeric year columns;
- use a documented zero tolerance;
- retain subtotal flags derived from `subtotal_layout OR subtotal_results`;
- distinguish a structurally present but always-zero pair from a non-zero
  valid pair;
- distinguish aggregate and leaf pairs;
- record source vintage and fingerprint so results are reproducible.

Do not silently promote an always-zero Ninth pair to data-valid. If the model
needs a reserved pair, represent that as explicit reviewed configuration.

### ESTO

ESTO pair availability may change with each data update. Build and test a
strict refresh workflow:

1. generate a versioned valid-pair snapshot from the configured ESTO source;
2. compare it with the last reviewed snapshot;
3. report added, removed and status-changed pairs;
4. never silently delete mappings because a pair disappears in one vintage;
5. require review before a new snapshot becomes the accepted registry.

For every newly added ESTO pair, produce narrow review outputs that:

- check whether the flow and product axes already map independently;
- compile candidate LEAP pairs only where the source flow-product combination
  is itself valid;
- flag missing LEAP coverage without automatically writing mapping rows;
- report whether a corresponding Ninth pair exists;
- explicitly acknowledge a missing Ninth counterpart rather than treating
  absence as an unexplained gap;
- identify subtotal, parent/child and cardinality consequences.

Investigate how many vintages are locally available and whether a
one-vintage disappearance should be treated as removed, dormant or pending
confirmation. Recommend a clear policy supported by measured examples.

### LEAP

Identify the authoritative source for valid LEAP branch-fuel pairs across the
three repositories. Consider:

- actual model/export structure;
- `new leap rows.xlsx` and related maintenance inputs;
- initialisation templates;
- observed LEAP result exports;
- deliberately reserved branches.

Do not assume that a pair missing from one economy is globally invalid.
Propose a reproducible registry and refresh authority that does not depend on
one modeller's workbook being complete.

## Relationship compilation

Prototype the compiler:

1. start from a valid source flow-product pair;
2. join its flow mapping targets;
3. join its product mapping targets;
4. form candidate target pairs;
5. retain only pairs allowed by the target dataset's accepted valid-pair
   registry or by an explicit reviewed reserved-pair override;
6. apply pair overrides;
7. classify resulting cardinality and relationship semantics.

Do not treat a Cartesian product as automatically valid.

Every one-to-many result must be classified as one of:

- `recombine_to_common_row`: all target components resolve to one
  `common_row_id`, and the source value is delivered once;
- `allocate_across_common_rows`: targets remain separate and reviewed
  allocation shares sum to one;
- `deliberate_aggregate_view`: a reviewed alternate comparison boundary;
- `unresolved`: fail the prototype validation.

Many-to-many results must be rejected unless a deliberate aggregate or narrow
pair override resolves them.

## Power-process test case

Use the current power-process mappings as the first demanding example.

Test whether the 27 ESTO main-activity/autoproducer combination rollups can be
represented as:

- one source flow mapped to both ESTO component flows;
- one independently mapped product;
- two valid ESTO flow-product pairs;
- one Common ESTO row receiving the source value exactly once.

Keep these exceptions separate:

- solar branch/fuel aliases;
- Ninth coal power versus coal-hydrogen-blended power;
- the coordinated `Other and solid biomass` hierarchy alignment.

Do not modify the real power rollups during this experiment.

## Cross-repository impact assessment

Search all three repositories for:

- direct reads of the three maintained pair-mapping sheets;
- duplicated fuel/product or sector/flow mappings;
- assumptions that one mapping row equals one value delivery;
- mapping cardinality checks;
- valid-pair or observed-pair generation;
- code that infers hierarchy or semantics from labels;
- dashboard code that would be affected by generated pair relationships.

Produce a migration matrix containing:

```text
repository
consumer
current input
proposed compiled input
required change
compatibility risk
owner
```

The preferred boundary is:

- `leap_mappings` owns separate-axis configuration, pair registries, pair
  compilation, mapping QA and Common ESTO membership;
- `leap_initialisation` consumes stable compiled mappings or Common ESTO
  outputs;
- `leap_dashboard` consumes stable Common ESTO data and metadata only.

## Prototype constraints

- Use functions and notebook-safe `#%%` workflow files.
- Keep paths relative to `REPO_ROOT`.
- Keep generated snapshots and diagnostics outside `config/`.
- Do not update the canonical workbook automatically.
- Do not infer validity from display labels.
- Preserve stable identifiers separately from presentation labels.
- Keep outputs narrow, with debug detail under `extra_detail` or
  `diagnostics`.
- Treat every generated mapping candidate as review-only.

## Lossless proof

Using the current accepted workbook and configured source vintages, compare the
prototype-compiled relationships with the current pair mappings.

Report:

- exact relationship matches;
- relationships reproducible through independent axes;
- relationships requiring pair overrides;
- relationships lost because a target pair is not data-valid;
- extra relationships created by the factorised model;
- cardinality changes;
- subtotal/hierarchy changes;
- Common ESTO connected-component changes;
- value-delivery differences on small deterministic fixtures.

The proof must explicitly test:

- 1:1;
- many-to-one;
- recombining one-to-many;
- allocated one-to-many;
- rejected unresolved many-to-many;
- target-pair additions and removals between registry vintages;
- source pairs valid in only one economy or year;
- zero-only pairs;
- subtotal pairs;
- alias/fallback cases.

Do not claim success merely because aggregate totals match. Component
membership, source-once delivery and lineage must also match.

## Deliverables

Create:

1. `docs/separate_axis_mapping_exploration_findings.md`
   - current-state evidence;
   - proposed schema;
   - measured reproduction rates;
   - unresolved semantics;
   - cross-repository migration matrix;
   - recommendation on whether to proceed.
2. A small notebook-safe prototype workflow and focused tests in
   `leap_mappings`.
3. Narrow valid-pair snapshots and delta reports for the configured Ninth and
   ESTO sources.
4. A LEAP valid-pair authority recommendation, with evidence.
5. A staged implementation plan that preserves compatibility with the current
   pair sheets until the new compiler is proven.

Commit stable exploration checkpoints on the worktree branch. Do not push.

## Stop conditions

Stop and ask for a decision if:

- the same source product genuinely maps differently depending on flow and no
  existing rule explains it;
- a reviewed ESTO pair-refresh policy requires choosing how long disappeared
  pairs remain dormant;
- the authoritative LEAP valid-pair source cannot be identified;
- lossless reproduction requires changing mapping semantics rather than only
  representation;
- implementation would require editing production code in a sibling
  repository.

Otherwise continue through the isolated prototype and findings report without
touching production workbooks.
