# Cross-repository hierarchy/subtotal audit and modularisation plan

**Audit date:** 2026-07-29

**Repositories:** `leap_mappings`, `leap_initialisation`, `leap_dashboard`

**Scope:** hierarchy, structural subtotal classification, contextual subtotal
flags, mismatch policy, exception/override policy, recursive validation, and
diagnostic tree rendering. No mapping workbook or subtotal label was changed.

## Executive decision

`leap_mappings` is the single authority for structural parent/subtotal truth.
The authority is the combination of:

- `codebase/mapping_tools/hierarchy_subtotal_contract.py`;
- the source adapters in
  `codebase/mapping_tools/hierarchy_subtotal_adapters.py`;
- the build entry point in `codebase/hierarchy_subtotal_contract_workflow.py`;
- the review-only workbook reconciliation in
  `codebase/mapping_tools/hierarchy_subtotal_review.py`; and
- the versioned artifact
  `aperc_hierarchy_subtotal_contract` /
  `hierarchy_subtotal_contract_v1`.

Its defining rule is stable and testable:

```text
node_is_structural_parent = node has at least one ordinary hierarchy child
pair_is_subtotal = axis_1_is_structural_parent OR axis_2_is_structural_parent
```

Source-reported flags such as ESTO `is_subtotal` and Ninth
`subtotal_layout` / `subtotal_results` answer a different question. They may
remain local when selecting source values for a period, scenario, or workflow,
but must not redefine structural parenthood.

The most consequential duplication is not the two small consumer loaders. It
is the set of active or reachable initialisation paths that re-infer LEAP,
Ninth, or ESTO parent/subtotal state from mapping rows, name patterns, code
prefixes, or period flags. Those paths can change which values are filtered,
so they must be migrated one ingress at a time with before/after fixtures.

The recommended first implementation step is to publish a small, dependency-
light consumer reference plus shared conformance fixtures and an immutable
artifact-selection rule. That gives all three repositories one tested
`load_contract(...)` and `attach_pair_status(...)` behavior before any
high-risk value filtering changes.

## Evidence baseline and runtime caveats

- The audit read committed code at mappings `dd87577`, initialisation
  `0ef0fbb`, and dashboard `c81ce47`.
- The active mappings checkout had unrelated uncommitted workbook-review work,
  so this audit used an isolated worktree.
- The active dashboard checkout had unrelated edits to
  `common_esto_dashboard_mapping_diagnostics.py` and its test. The committed
  contract adapter and fallback path were audited; the uncommitted rendering
  overlay was not incorporated into this plan.
- A current contract bundle existed only in the active mappings result tree,
  not in the clean audit worktree. Its build ID was
  `9c566a5474aa409f5fd2564778f5981c427ce91fe6362c40776d0eecbca29b5f`.
  This proves the producer can build the artifact, but also proves a clean
  checkout cannot rely on the untracked `results/.../current` directory as a
  distribution mechanism.
- Current documentation is inconsistent: `results/tree_structure/README.md`
  still calls `all_dataset_trees.csv` the canonical hierarchy source, while
  the maintained contract documentation correctly makes the versioned
  contract canonical. The tree CSV remains an active producer input and
  compatibility artifact, not the cross-repository authority.

## Contract and artifact inventory

The current contract manifest validates the contract name, schema version,
build ID, producer commit, input hashes, member hashes, member row counts, and
compatibility declarations. The observed build contained:

| Member | Observed rows | Key schema responsibility |
|---|---:|---|
| `datasets.csv` | 5 | `dataset_id`, source/adapter version, dataset kind, provenance |
| `axis_nodes.csv` | 2,794 | dataset/axis/node identity, declared parent, depth, child count, structural parent/leaf status, source flags as evidence |
| `declared_relationship_edges.csv` | 2,478 | typed ordinary, additive, alias, expanding, non-expanding, detached, graph, or unresolved relationships |
| `canonical_source_pairs.csv` | 11,359 | two-axis pair identity, per-axis resolution/parent status, `pair_is_subtotal`, synthetic status, separate `declared_output_subtotal` |
| `value_conformance_diagnostics.csv` | 301,653 | economy/scenario/period/fixed-opposite-axis additivity evidence, status/reason, source attribution, tolerance and exception context |

The producer's `load_contract()` additionally checks declared key uniqueness.
The two consumer copies currently validate hashes and row counts but do not
enforce a required member set, required columns, declared keys, or boolean
normalisation. Those omissions belong in the shared consumer boundary.

## Implementation and call-site inventory

### `leap_mappings`

| File / public entry | Callers and artifacts | Definition used | Status and disposition |
|---|---|---|---|
| `mapping_tools/hierarchy_subtotal_contract.py`: `normalize_adapter_tables`, `classify_pairs`, `build_contract_frames`, `write_contract`, `load_contract` | Called by the contract workflow and focused tests. Writes/loads the five manifest-declared CSV members above. | Ordinary edges alone define structural parenthood; numerical conformance is separate. | **Canonical authority — retain.** Strengthen the shared consumer validation to match producer strictness. |
| `mapping_tools/hierarchy_subtotal_adapters.py`: ESTO, Ninth, LEAP, ESTO Extended, and Common ESTO adapters | Called by the contract workflow; `build_common_esto_pair_classification` is also called by Stage 3 wide-output construction. Inputs include ESTO/Ninth tables, branch inventory, mapping workbook, `esto_extended_tree.csv`, and `common_esto_rows.csv`. | Dataset-specific parsing produces normalized nodes, typed edges, observed pairs, and evidence. | **Canonical source adapters — retain beside producer.** LEAP remains explicitly partial until MAPQ-032 resolves the full template/model policy. |
| `hierarchy_subtotal_contract_workflow.py`: `build_hierarchy_subtotal_contract` | Manual notebook-safe entry. Builds, strictly reloads, and writes review CSVs under `results/hierarchy_subtotal_contract/`. | Registry-driven producer plus exact build manifest. | **Canonical build entry — retain.** Replace the review-workbook default with a deliberate configured selection in a later implementation. |
| `mapping_tools/hierarchy_subtotal_review.py`: `build_review_frames`, `write_review_csvs` | Contract workflow and tests. Reads the three mapping sheets and the three subtotal exception sheets; writes summary, pair, cell, conflict, unresolved, and exception-audit CSVs. | Contract pair status, never majority/current workbook state. | **Canonical review consumer — retain.** It remains review-only. |
| `mapping_tools/build_dataset_tree_structure.py`: tree builders, typed Common ESTO edges, recursive validators, `run_tree_structure_workflow` | Called by Stage 0, Stage 3, contract adapters, structural compilation, validation orchestration, tests, and a scrapbook. Writes `*_tree.csv`, `all_dataset_trees.csv`, typed edges, and source/Common ESTO validation files. Tree schema is `dataset, axis, code, label, level, parent_code, is_subtotal`; validation schemas add exact source context and value differences. | Mixes sound hierarchy parsing with contextual numerical validation. | **Active source adapter/validator — retain, then split.** Its parsing functions belong behind adapters; its value validators remain separate diagnostics. Stop presenting `all_dataset_trees.csv` as the published authority once all consumers use the contract. |
| `mapping_tools/apply_common_esto_structure.py` wide-output builder | Stage 3. Calls `build_common_esto_pair_classification` and writes `is_subtotal` from `declared_output_subtotal`. | Uses the canonical Common ESTO adapter, including typed synthetic output boundaries. | **Active producer consumer — retain.** This is a legitimate output-filter use of the separate declared-output field. |
| `archive/outlook_mapping_maintenance_workflow.py`: `run` | Despite its archive path, it is active Stage 0 via `run_mapping_pipeline.py`, smoke tests, docs, and focused tests. Reads mapping/source/exception workbooks; writes maintenance QA, subtotal preview, tree artifacts, and display-name QA. Workbook subtotal writes are intentionally unreachable. | Rebuilds ESTO/Ninth status from non-zero raw flags and LEAP status from available export/mapping paths, then applies exact-row overrides. | **Active compatibility/duplicate — migrate and deprecate structural derivation.** Retain non-subtotal mapping QA. Replace subtotal preview inputs with the contract review frames. Rename/move only in a separate compatibility task. |
| `leap_mapping_refresh_workflow.py`: `run_workflow` and report builders | Focused tests only; its configured `config/leap_mappings.xlsx` no longer exists. Docs and AGENTS mark it legacy. | Mapping-row paths, source flags, and old workbook conventions. | **Legacy — retain only until tests/evidence are ported, then remove.** It must not regain authority. |
| `mapping_tools/infer_subtotal_labels.py`: `main` | Standalone manual tool; reads generated trees, rollup-sheet `Subtotal`, current workbook values, and `subtotal_label_exceptions`; writes three draft CSVs and rollup consistency. | Tree lookup plus manual semantic totals, rollup values, and first/current workbook evidence. | **Superseded inference — deprecate.** Preserve useful rollup-consistency checks by moving them to contract review; do not use its drafts for new writes. |
| `mapping_tools/build_subtotal_mismatch_review.py`: `build_review_rows`, `run` | No active caller; its module-level toggle currently writes a review CSV on execution/import when true. | Majority of current workbook flags, ties forced to subtotal, then OR across axes and systems. | **Duplicate and semantically invalid as authority — deprecate immediately.** Contract review replaces it. |
| `mapping_tools/apply_subtotal_updates.py`: `build_plan`, `apply_plan`, `verify_plan` | Standalone writer for approved drafts from `infer_subtotal_labels.py`; no tests or active pipeline caller found. | Applies superseded draft values, including historical `MIXED` handling. | **Legacy writer — freeze, then remove after review migration.** Do not feed it new approvals. |
| `mapping_tools/apply_subtotal_mismatch_review.py`: `run` | Standalone guarded writer for the majority-based mismatch review. Rebuilds both `subtotal_mismatch_allowed` and `subtotal_label_overrides`. | Treats review approval as a label change and rejection as an allowed mismatch. | **Overlapping legacy writer — freeze.** Its two policy effects must be split before removal; keep Git history as the recovery path. |
| `mapping_issue_exceptions.py` and `mapping_tools/mapping_issue_exceptions.py` | Stage 0, Stage 1, Stage 3, source-parent validation, Common ESTO application, and tests. Reads enabled rows from `mapping_issue_exception_sets.xlsx`; emits matching/split status but does not write. The nested module is a narrow re-export/extra code-mask layer. | Reviewed QA suppression/annotation, not hierarchy. | **Canonical exception matching utility — retain.** Add typed policy declarations so sheets cannot be interchanged merely because columns overlap. |

### `leap_initialisation`

| File / public entry | Callers and artifacts | Definition used | Status and disposition |
|---|---|---|---|
| `mappings/hierarchy_subtotal_contract_loader.py`: `load_hierarchy_subtotal_contract`, `attach_structural_pair_status` | Only its focused test and consumer document call it. No runtime workflow imports it. | Strict selected artifact plus pair attachment that preserves period flags. | **Correct test-only consumer — wire at ingress.** It is not yet an active integration. |
| `outlook_mapping_maintenance_workflow.py` and `functions/outlook_mapping_maintenance_utils.py` | Tests, workflow inventory, and a scrapbook call; no main supply workflow call found. Writes mapping refresh/conflict reports and can overwrite mapping sheets after confirmation. | Re-infers LEAP parents from active paths and target status from raw source flags. | **Repository-owned duplicate — retire from initialisation.** Mapping maintenance belongs in `leap_mappings`; preserve only any LEAP-export extraction helper that has no mappings equivalent. |
| `mapping_tools/update_mapping_cardinality.py`: `update_mapping_cardinality` | Manual toggle and mapping-rollup tests. Reads the mappings workbook and raw sources; rewrites mapping/rollup sheets and emits rollup/cardinality/subtotal QA. | ESTO raw flag; Ninth hierarchy plus period flags; LEAP effective mapping paths. | **Mapping-authority duplicate — retire or move to mappings.** Do not wire the contract into this writer inside initialisation. |
| `mapping_tools/mapping_rollups.py` | Used by initialisation's copied Stage 1, cardinality updater, tests, and active `functions/supply_demand_mapping.py`. Produces effective mapping tables, rollup/cardinality QA, and subtotal-alignment QA. | Reads and interprets rollup rules locally; subtotal QA accepts locally built lookups. | **Mixed status — split.** Retire mapping-workbook mutation/QA copies; retain only the runtime rollup/pair resolution behavior until it can consume a mappings-published effective mapping artifact. |
| `utilities/energy_balance_template_extractor.py`: `TemplateBalanceExtractor`, `run_template_balance_extraction` | Active via baseline-seed diagnostics, LEAP balance conversion, old workflows, and tests. Emits extracted/mapped balance rows and diagnostics. | Reads authored mapping flags and mismatch allowlist, but also re-infers LEAP/total status from paths and names. | **Legitimate LEAP-template consumer with duplicate inference.** Retain extraction and template transforms; attach contract status at mapping ingress and remove heuristic parenthood after equivalence tests. |
| `utilities/leap_results_dashboard_balance.py` | Broad active use by supply reconciliation, preflight, results saving, tables, LEAP I/O, old workflows, and tests. Emits converted balance tables, lineage, coverage, dashboard, and total-check artifacts. | Uses mapping flags, raw source flags, name/code heuristics, and local filtering. | **High-risk active consumer.** Retain conversion/rendering and contextual filters; replace structural annotation incrementally. Never bulk-switch its value filtering without golden-output checks. |
| `mapping_tools/prepare_new_esto_data.py`: `label_esto_subtotals`, `prepare_new_esto_data` | Tests and manual path wrapper; no active workflow caller found. Emits a prepared ESTO CSV plus summary. | Copies prior-vintage pair flags, falls back to product-code parent inference, then defaults false. | **Legitimate source-vintage preparation with duplicated structural inference.** Retain row completion/LNG split locally; move or delegate subtotal classification to the mappings ESTO adapter/contract build. |

### `leap_dashboard`

| File / public entry | Callers and artifacts | Definition used | Status and disposition |
|---|---|---|---|
| `hierarchy_subtotal_contract_loader.py`: `load_hierarchy_subtotal_contract`, `diagnostic_status_labels` | Called by the diagnostics adapter and focused tests. | Same strict loading core as initialisation; dashboard-only status labels keep structure/additivity separate. | **Active consumer copy — converge shared core, retain dashboard label adapter.** |
| `mapping_diagnostics_contract.py`: `load_mapping_diagnostics_contract` | Called by the Mapping diagnostics page and tests. Adapts Common ESTO nodes, diagnostics, and typed edges into dashboard tree/validation/rollup frames. | Canonical contract if a manifest exists; returns `None` if none exists. | **Active compatibility adapter — retain temporarily.** Artifact absence must become configured/observable rather than filesystem-driven. |
| `common_esto_dashboard_mapping_diagnostics.py`: `write_mapping_diagnostics_page`, tree/rollup render helpers | Active workflow call. Reads many mappings result CSVs. It replaces only Common ESTO tree, validation, and rollup catalogue with contract views when selected; source trees and other QA remain legacy CSV inputs. | Presentation transforms supplied structure; it does not define parenthood. | **Legitimate presentation consumer.** Retain rendering. Make fallback state machine explicit and time-bounded; do not centralise it into mappings. |

## Duplication map

| Structural question | Canonical answer | Other implementations answering the same question | Similar-looking behavior that must remain separate |
|---|---|---|---|
| Does a node have ordinary children? | Contract ordinary edges + `axis_nodes.is_structural_parent` | Stage 0 path inference; old refresh path inference; initialisation maintenance/cardinality; extractor/results name heuristics; new-ESTO product-prefix fallback | Dashboard tree layout and LEAP template path splitting |
| Is a source pair structurally a subtotal? | `canonical_source_pairs.pair_is_subtotal` | Workbook-majority review; inference drafts; authored mapping flags treated as truth; initialisation local lookups | `declared_output_subtotal`, which also covers typed synthetic output boundaries |
| Do child values add to a parent in this context? | `value_conformance_diagnostics` | Recursive validators and source-parent anchors | Structural parenthood; a failed sum does not make a parent a leaf |
| Should a source value row be filtered for this period/scenario? | Local workflow policy using source-reported flags plus the relevant contract field | Several initialisation filters currently mix local and structural status | Structural annotation alone; it does not choose a period's value frontier |
| Is a cross-dataset mismatch acceptable? | Typed `subtotal_mismatch_allowed` QA policy after both sides are correctly classified | Old combined mismatch writers | A label override or evidence exception |
| How is a tree shown to a modeller? | Dashboard adaptation of supplied nodes/typed edges | Legacy `*_tree.csv` fallback | Structural production; presentation must never invent parents |

## Exception taxonomy

The three sheets are historically overlapping but semantically distinct:

| Sheet | Enabled rows on 2026-07-29 | Correct policy meaning | Migration |
|---|---:|---|---|
| `subtotal_mismatch_allowed` | 434 | A reviewed cross-dataset relationship may legitimately connect unlike structural statuses. It proves neither side's label. | Retain as typed QA allowance; revalidate after canonical labels are approved. |
| `subtotal_label_exceptions` | 118 | Suppresses proposals from the superseded inference draft. | Freeze; migrate any still-valid evidence into canonical review decisions, then remove the sheet and reader. |
| `subtotal_label_overrides` | 2,408 | Exact mapping-cell override applied after Stage 0's old computation. | Treat as a temporary migration ledger. Classify rows as confirmed, redundant, stale, or unresolved; do not keep it as permanent structural authority. |

The shared exception API should require an explicit policy type, dataset/pair or
mapping-cell grain, reason, reviewer, and evidence/build identity. A generic
matching function may implement the mechanics, but a caller must not use a
label override where a mismatch allowance is expected.

## Proposed module and distribution boundary

### Producer package in `leap_mappings`

Keep dataset parsing and contract production in mappings:

```python
def build_contract(
    adapter_registry: list[DatasetAdapter],
    output_dir: Path,
    input_paths: list[Path],
) -> ContractManifest: ...

def classify_pairs(
    nodes: pd.DataFrame,
    pairs: pd.DataFrame,
    edges: pd.DataFrame,
) -> pd.DataFrame: ...
```

The producer owns schemas, relationship types, adapter/source versions,
deterministic serialization, review evidence, and exception migration.

### Shared dependency-light consumer

The common core should expose only artifact validation and attachment:

```python
def load_contract(
    contract_dir: Path,
    *,
    expected_build_id: str,
    expected_schema_version: str = "hierarchy_subtotal_contract_v1",
    expected_input_hashes: dict[str, str] | None = None,
) -> LoadedHierarchySubtotalContract: ...

def attach_pair_status(
    data: pd.DataFrame,
    contract: LoadedHierarchySubtotalContract,
    *,
    dataset_id: str,
    axis_1_column: str,
    axis_2_column: str,
    require_resolved: bool = True,
) -> pd.DataFrame: ...
```

Required validation:

- exact contract and schema names;
- explicit expected build ID in production workflows;
- required member set and required columns;
- member hashes, row counts, and key uniqueness;
- normalised booleans and allowed enum values;
- no duplicate pair join keys;
- explicit failure for unresolved requested pairs when `require_resolved=True`;
- exposure of build ID/schema version on every downstream run manifest.

### Distribution recommendation

Use generated/reference-tested consumer copies first, not runtime imports from
a sibling checkout:

1. Keep one canonical consumer source template and conformance fixture pack in
   `leap_mappings`.
2. Copy that small module and fixtures into the two consumer repositories with
   an explicit sync script or release step.
3. Record a source-template hash in each copy and run the identical fixture
   suite in all three repositories.
4. Publish contract bundles as immutable, build-ID-named archives or release
   assets. Consumers select a configured local bundle; they do not discover
   `../leap_mappings/results/.../current`.

This is safer immediately than creating a wheel because no shared package
registry/deployment path was found. A standalone package becomes preferable
only after the team chooses an internal release channel and can pin it in all
runtime environments. Dashboard-only presentation labels and initialisation-
only ingress helpers remain outside the shared core.

## Deliberately retained local behavior

- Ninth `subtotal_layout` and `subtotal_results` filtering by base/projection
  period.
- ESTO source `is_subtotal` filtering when selecting raw published values.
- LEAP export/template parsing, IDs, paths, units, scenarios, and variables.
- Initialisation's new-vintage row completion and LNG allocation logic.
- Supply-reconciliation conversion, conservation, sign, and total checks.
- Dashboard HTML, graph layout, interactivity, materiality ranking, and
  presentation-only issue flags.
- Contextual additivity and source-parent anchor checks. They remain contract
  evidence or downstream diagnostics, not structural classifiers.

## Phased migration plan

### Phase 1 — consumer contract and immutable selection

**Owners:** `leap_mappings` MAPQ-033, `leap_initialisation` INIT-HS-001,
`leap_dashboard` DASHQ-026.

- Add the shared loader/attachment fixture pack and close validation gaps.
- Decide and implement artifact publication/sync; pin build ID and schema in
  consumer run configuration.
- Put build ID/schema/input hash in initialisation and dashboard run manifests.

**Acceptance:** the same positive and corrupt fixture matrix passes in all
three repositories; a clean checkout can obtain one named bundle without a
sibling runtime import; stale, missing, wrong-schema, duplicate-key, and
missing-column bundles fail before value processing.

**Rollback:** keep current loaders and dashboard legacy artifacts behind an
explicit compatibility mode. Do not silently choose compatibility mode.

### Phase 2 — exception and review consolidation

**Owner:** `leap_mappings` MAPQ-034.

- Make contract review the only new subtotal proposal path.
- Audit all three subtotal sheets against one contract build.
- Freeze `infer_subtotal_labels`, majority mismatch review, and both associated
  writers; preserve historical outputs in archive/Git.
- Route Stage 0 subtotal preview through contract review frames while retaining
  unrelated mapping QA.

**Acceptance:** one pair has one proposed structural status; all exception rows
have a typed policy and evidence; no new workflow reads
`subtotal_label_exceptions`; Stage 0 produces the same non-subtotal QA.

**Removal condition:** old drafts/writers have no callers, no active prompt,
and their unique tests have been ported.

### Phase 3 — initialisation ingress migration

**Owners:** `leap_initialisation` INIT-HS-001 and INIT-HS-002.

Migrate one boundary at a time:

1. attach canonical status in `TemplateBalanceExtractor` mapping ingress;
2. attach it in `leap_results_dashboard_balance` crosswalk ingress;
3. replace runtime rollup reconstruction with mappings-published effective
   mapping rows;
4. move new-ESTO structural classification to the producer while retaining
   row completion locally;
5. retire copied mapping maintenance/cardinality/Stage 1 tools.

**Acceptance per boundary:** representative ESTO, Ninth, and LEAP fixtures
prove the same selected value rows, totals, signs, export identities, and
diagnostics before/after, except for a separately reviewed correction.
Period flags remain unchanged columns. Unknown pairs fail or enter a named
review queue; they never default silently.

**Rollback:** selectable old/new attachment adapter at the ingress, with dual-
run comparison output. Remove the old path only after two current-vintage
economies and at least one hierarchy edge case agree.

### Phase 4 — dashboard fallback retirement

**Owners:** `leap_dashboard` DASHQ-026 and DASHQ-027.

- Replace `manifest exists -> contract, otherwise legacy` with configured
  modes: `required_contract` (production) and `legacy_compatibility`
  (temporary explicit diagnostics only).
- Display and record mode, build ID, schema, and fallback reason.
- Keep legacy source-tree and QA rendering only where the contract does not
  yet publish equivalent evidence.

**Acceptance:** tests cover required-contract absence, corrupt contract,
explicit compatibility mode, and contract rendering; production readiness
fails when compatibility mode is active.

**Removal condition:** two successful current all-economy generations have
pinned contract builds, every required diagnostic has a contract member or
documented non-structural source, and no published dashboard used fallback.

### Phase 5 — remove superseded producers and copies

**Owners:** each repository for its own files.

- Remove old mappings inference/writers and initialisation mapping-authority
  copies only after the preceding removal conditions.
- Split tree parsing from recursive/value validation so source adapters can be
  tested without invoking Stage 3.
- Correct documentation that calls legacy tree CSVs canonical.

**Acceptance:** repository-wide import/call searches find no superseded
symbols; focused and full suites pass; clean-checkout rehearsal proves one
contract version/build across all outputs.

## Legacy fallback register

| Fallback | Exercised now? | Required before removal |
|---|---|---|
| Dashboard legacy `common_esto_tree.csv` / `common_esto_validation.csv` / rollup catalogue | Yes whenever no contract manifest exists; visible in page text but not prohibited in production | Configured required-contract mode, immutable bundle availability, readiness gate, two all-economy pinned builds |
| Stage 0 mapping-path LEAP hierarchy when full model export is absent | Yes; both historical full-export paths are absent | MAPQ-032 reviewed cross-economy template policy and provenance |
| `build_dataset_tree_structure.py` legacy USA LEAP balance fallback | Reachable when regenerated raw LEAP results are missing | Explicit required Stage 3 input or reviewed multi-economy fallback |
| Initialisation local subtotal/name/code heuristics | Active in extractor/results paths | Ingress attachment plus golden value-filter comparisons |
| Initialisation copied mapping maintenance/cardinality tools | Manual/test reachable; not main supply runtime | Port unique tests/helpers, remove docs/callers, publish mappings-owned equivalent |

## Tests and proof matrix

| Repository | Required tests |
|---|---|
| `leap_mappings` | adapter schema/edge invariants; deterministic build; manifest/member corruption; required columns and keys; exact pair status; exception taxonomy; Stage 0 review parity |
| `leap_initialisation` | shared loader fixtures; attachment preserves source period flags; unresolved pair failure; extractor/results before-after selected-row and total parity; contextual filter tests |
| `leap_dashboard` | shared loader fixtures; explicit compatibility mode; required-contract failure; typed-edge rendering; structural versus conformance labels; build ID in page/run evidence |
| Cross-repository | one fixture bundle with expected nodes, parents, typed rollups, pair booleans, output-subtotal booleans, and one failed additivity context; all repositories report the same schema/build ID |

## Unresolved human decisions

1. Where immutable contract bundles and the generated consumer source should be
   published: repository release asset, shared data distribution, or a future
   internal package registry.
2. Whether production dashboard runs may ever use explicit legacy
   compatibility mode, or whether that mode is development-only immediately.
3. The cross-economy LEAP structural authority and conflict policy tracked by
   MAPQ-032.
4. Whether the new-ESTO preparation workflow should invoke a mappings producer
   command or consume the last published ESTO axis table when a new code first
   appears.
5. Which reviewed exact-cell overrides contain durable domain evidence versus
   merely preserving historical workbook state.
6. The number and choice of initialisation golden economies required before a
   value-filtering migration can remove its rollback path.

## Linked work queue

- [`leap_mappings` MAPQ-033 and MAPQ-034](work_queue.md)
- [`leap_initialisation` INIT-HS-001 and INIT-HS-002](../../leap_initialisation/docs/work_queue.md)
- [`leap_dashboard` DASHQ-026 and DASHQ-027](../../leap_dashboard/docs/work_queue.md)
