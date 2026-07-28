# Prompt: Complete the hierarchy and subtotal contract

Work primarily in `C:\Users\Work\github\leap_mappings`, with coordinated
consumer changes in:

- `C:\Users\Work\github\leap_dashboard`
- `C:\Users\Work\github\leap_initialisation`

Read each repository's `AGENTS.md` and relevant local instructions before
acting. Run `git status --short` in all three repositories and preserve
unrelated work. Check for active mapping, dashboard, or initialisation
processes before replacing shared outputs.

This is the implementation prompt for MAPQ-030. Read these design sources
before changing code:

- `docs/subtotal_columns_rebuild_plan.md`
- `docs/mappings_system.md`, especially **Hierarchical tree validation**
- `docs/rollup_rules_system.md`
- `docs/esto_extended_category_creation_considerations.md`
- `docs/prompts/data_reliability_flag_and_diagnostic_consolidation_design_20260723.md`
- `config/mapping_issue_exception_sets.xlsx`
- the current mapping workbook named by MAPQ-030
- the current Common ESTO output-contract documentation and implementation
- the dashboard Mapping diagnostics implementation and guide

Search for the current symbols and their consumers rather than relying on line
numbers:

- `build_dataset_tree_structure`
- `build_ninth_tree`
- `_build_ninth_subtotal_results_sets`
- `infer_subtotal_labels`
- `build_subtotal_mismatch_review`
- `apply_subtotal_updates`
- `validate_*_recursive_sums`
- `_build_source_inconsistency_lookup`
- `source_parent_anchor_validation`
- `common_esto_output_contract`
- `_rollup_graph_data`
- `label_esto_subtotals`
- `_compute_leap_subtotals`

## Objective

Build one canonical, versioned hierarchy/subtotal contract owned by
`leap_mappings`. It must:

1. represent the hierarchy of each mapped dataset on each axis;
2. classify every mapping-side pair consistently;
3. diagnose whether parent values add to their children without confusing
   numerical inconsistency with structural classification;
4. work through dataset adapters so additional datasets can be added without
   rewriting the core engine;
5. drive mapping QA and the reviewed subtotal columns in the maintained
   mapping workbook;
6. supply the structural evidence used by `leap_dashboard` and
   `leap_initialisation` instead of allowing either repository to independently
   reconstruct subtotal truth;
7. retain the dashboard as an independent, human-readable checking surface,
   not as the source of truth.

Mappings are the primary use case. Do not weaken mapping identity, review,
cardinality, rollup, or workbook-preservation requirements to make a generic
abstraction easier.

## Non-negotiable semantics

### 1. Structural parenthood defines subtotal status

A node is a structural subtotal when it has one or more declared children in
the authoritative hierarchy for that dataset and axis.

Declared structure must come from the fullest available schema, code list, or
model tree. A child does not need to be non-zero—or even observed for a
particular economy, scenario, or year—to establish that its declared parent is
a structural parent.

For a mapping-side pair:

```text
pair_is_subtotal = any(axis_node_is_structural_parent)
```

For the current two-axis energy datasets this is:

```text
pair_is_subtotal =
    sector_or_flow_is_structural_parent
    OR fuel_or_product_is_structural_parent
```

Therefore:

- a parent sector paired with a leaf fuel is a subtotal pair;
- a leaf sector paired with a parent fuel is a subtotal pair;
- a parent sector paired with a parent fuel is a subtotal pair;
- only a leaf sector paired with a leaf fuel is a non-subtotal pair.

The same source pair must receive the same source-side subtotal classification
wherever it appears, regardless of mapping direction or sheet.

### 2. Additivity is a separate, contextual diagnostic

Do not define a parent by whether its values happen to equal the sum of its
children. Structure determines parenthood. Values test conformance with the
declared structure.

A structurally valid parent remains `is_subtotal=True` when:

- its value does not equal the sum of its children;
- some children are absent or zero;
- the source publishes a parent and children using different modelling
  conventions;
- additivity changes by economy, scenario, year, or historical/projection
  period;
- the values cannot be tested.

Record those conditions as value-conformance evidence with explicit statuses.
Never convert the parent to a leaf to make a recursive-sum test pass.

The Ninth Outlook transformation hierarchy is a required regression case.
Parents in families such as `09_06_gas_processing_plants` and
`09_08_coal_transformation` may not numerically reconcile with their declared
children. They must still be classified as structural subtotals. The mismatch
must remain visible as source-data inconsistency or non-additivity evidence.
Do not guess whether the parent or children are more accurate, and do not
silently substitute one for the other.

### 3. Source subtotal flags are evidence, not structural authority

Keep source fields such as:

- ESTO `is_subtotal`;
- Ninth `subtotal_layout`;
- Ninth `subtotal_results`;
- period-specific variants of those fields;
- existing workbook subtotal columns;
- rollup-sheet `Subtotal` values;

as separate evidence columns. Investigate disagreement with the hierarchy, but
do not let a missing, false, period-specific, or internally inconsistent source
flag erase a declared parent-child relationship.

For Ninth:

- derive sector hierarchy from `sectors` through `sub4sectors`;
- derive fuel hierarchy from `fuels` and `subfuels`;
- treat `"x"` as absent;
- preserve the distinction between historical/layout and
  projection/results subtotal signals;
- do not derive sector parenthood from `subtotal_results`;
- do not let a fuel subtotal signal contaminate sector classification, or vice
  versa.

### 4. Relationship types must remain distinct

Do not treat every aggregate-looking relationship as an ordinary hierarchy
edge. Represent at least:

- ordinary structural parent-child edges;
- additive synthetic rollups;
- exact aliases or renamed leaves;
- expanding rollups;
- non-expanding comparison-boundary replacements;
- detached diagnostic boundaries;
- graph-generated comparison categories;
- unresolved or incomplete hierarchy evidence.

Only ordinary hierarchy edges define structural parenthood automatically.
Synthetic or comparison relationships require their declared semantic type.
Do not splice comparison-boundary replacements into the raw source hierarchy.

### 5. Exceptions annotate; they do not rewrite truth

The exception workbook may explain an accepted mismatch, source
non-additivity, unavailable relationship, or intentionally different mapping
frontier. It must not silently change:

- whether a source node has children;
- the canonical pair subtotal boolean;
- a failed numerical reconciliation into a pass.

Retained exceptions need a specific reason, scope, provenance, reviewer, and
status. Generic notes such as “retain current value” are insufficient.

## Required architecture

### A. Dataset registry and adapters

Create a small, explicit dataset-adapter interface. The core contract builder
must not grow hard-coded dataset branches for every new source.

Each adapter must provide or construct:

- stable `dataset_id` and source version;
- axis definitions and mapping-facing axis roles;
- normalized node identifiers and labels;
- immediate parent-child edges;
- root and depth information;
- source subtotal signals as evidence;
- mapping-side pair keys;
- optional value observations for conformance checks;
- provenance for every input.

Support the current ESTO, Ninth, LEAP, ESTO Extended, and Common ESTO
structures as appropriate. Clearly distinguish raw source datasets from
derived comparison structures.

The core engine should operate on normalized node, edge, pair, and observation
tables. Dataset-specific parsing belongs in adapters. Shared classification,
validation, serialization, and QA logic belongs in `leap_mappings`.

Do not copy these functions into sibling repositories. Prefer a versioned
output contract consumed by the other repositories. If a small shared package
is genuinely required, justify its ownership and deployment before creating
it.

### B. Canonical contract tables

At minimum, publish the following logical members. Exact filenames may change
after inspecting the existing Common ESTO contract, but their grain and
responsibilities must remain separate.

#### Dataset and build manifest

Include:

- contract name and schema version;
- build ID and generation time;
- producer commit;
- input paths, hashes, vintages, and schemas;
- adapter version for each dataset;
- member paths, hashes, row counts, and key columns;
- validation result and failure reason;
- compatibility information for dashboard and initialisation consumers.

An invalid selected contract must fail closed. Do not silently fall back to a
different or older structural build.

#### Axis nodes

One row per dataset, axis, and node, including:

- `dataset_id`
- `axis_id`
- `node_id`
- `node_label`
- `parent_node_id`
- `depth`
- `is_leaf`
- `is_structural_parent`
- `child_count`
- hierarchy completeness/status
- source subtotal signals
- classification rule
- evidence and provenance

Reject duplicate node keys, cycles, self-parent edges, missing parents, and
contradictory parent assignments unless explicitly represented as unresolved
diagnostics.

#### Hierarchy and declared relationship edges

Keep ordinary hierarchy edges separate from rollup, alias, replacement, and
detached edges. Include relationship type, direction, additive behaviour,
source rule identifier, review status, and provenance.

#### Canonical source pairs

One row per dataset pair at the grain used by mappings, including:

- normalized node key for every axis;
- per-axis structural-parent booleans;
- `pair_is_subtotal`;
- the exact rule `any(axis_node_is_structural_parent)`;
- whether every node resolved;
- source-signal disagreements;
- synthetic/rollup status;
- confidence or review state;
- evidence and provenance.

Do not write `MIXED` into mapping workbook boolean columns. Mixed or
contradictory evidence belongs in diagnostic fields.

#### Value-conformance diagnostics

Store numerical conformance separately at the full available context:

- dataset and source version;
- economy;
- scenario;
- year or period;
- validation axis;
- parent node;
- fixed opposite-axis node;
- parent value;
- immediate-child or approved-frontier sum;
- signed and absolute differences;
- positive and negative subtotals where cancellation matters;
- expected, observed, missing, and mapped child counts;
- tolerance;
- status;
- reason;
- inherited source-inconsistency attribution;
- exception/review metadata.

Use clear statuses such as:

- `passed`;
- `failed`;
- `children_incomplete`;
- `unavailable`;
- `not_applicable`;
- `unanchorable`;
- `mapping_ambiguous`;
- `intentionally_non_additive`;
- `unresolved`.

Do not report an untested or unavailable case as passed. Do not hide failures
when an upstream inconsistency explains them; retain the failure and add the
attribution.

### C. Relationship to the Common ESTO output contract

Inspect the existing `common_esto_output_contract_v1` before choosing the
packaging. Prefer either:

1. a separate versioned structural contract referenced by the Common ESTO
   output manifest; or
2. a clearly versioned future contract member if its grain and lifecycle fit.

Do not insert component-grain hierarchy data into a one-row-per-comparison-row
metadata table merely for convenience. Document the decision and migration
path.

## Required implementation phases

### Phase 0 — Establish a safe baseline

- Inspect all three worktrees and active processes.
- Identify the exact mapping workbook base. Do not assume the canonical
  workbook or the todo workbook is current.
- Record hashes of the mapping workbook, exception workbook, source datasets,
  full LEAP structure, and relevant generated artifacts.
- Re-run or verify the lossless workbook round-trip proof before any workbook
  write.
- Run the current tree, subtotal, mapping, contract, and dashboard tests to
  establish a baseline.
- Record known failures separately from regressions introduced by this work.

### Phase 1 — Diagnose the present system before replacing it

Inventory every current subtotal or hierarchy derivation across all three
repositories. For each implementation, record:

- inputs and grain;
- structural rule used;
- dependence on observed/non-zero rows;
- dependence on source subtotal flags;
- treatment of both axes;
- treatment of rollups and aliases;
- outputs and consumers;
- known inconsistencies with the required semantics;
- whether it should be replaced, retained as value evidence, or adapted.

Explicitly reproduce the Ninth `09.06` and `09.08` cases and show:

- the declared parent-child structure;
- the resulting structural subtotal classification;
- the numerical conformance result;
- why these are not contradictory.

Create a concise diagnosis in `docs/` before major refactoring.

### Phase 2 — Implement normalized adapters and structural classification

- Add the dataset registry and normalized adapter outputs.
- Correct Ninth structural classification so parenthood comes from hierarchy
  columns, not `subtotal_results`.
- Build LEAP hierarchy from the fullest available model/tree inventory, not
  solely from mappings or non-zero observations.
- Preserve ESTO code hierarchy and maintained code/name authority.
- Represent ESTO Extended and Common ESTO synthetic relationships without
  corrupting raw source trees.
- Compute `is_structural_parent` from immediate hierarchy edges.
- Compute canonical pair status using the any-axis-parent rule.

Keep functions small, explicit, notebook-safe, and testable. Follow the
repository's `#%%` and workflow-file conventions. Do not add a CLI-only
workflow.

### Phase 3 — Implement the contract and provenance

- Serialize deterministic contract members and manifest.
- Validate schemas, keys, member hashes, parent references, and cross-member
  membership.
- Add a strict loader in `leap_mappings`.
- Make identical inputs produce byte-stable or content-stable normalized
  members and a reproducible build identity.
- Retain a narrow human-readable summary and put trace-heavy detail under
  diagnostics or `extra_detail`.

### Phase 4 — Separate and improve value-conformance validation

- Reuse the existing source recursive-sum and inherited-inconsistency work
  where sound.
- Remove any logic that changes structural subtotal status because values fail
  to add.
- Preserve exact context when attributing source inconsistency.
- Test both hierarchy axes independently.
- Use additive frontiers that never include a parent and its descendants
  together.
- Distinguish incomplete children, mapping ambiguity, source non-additivity,
  unavailable values, and genuine downstream transformation errors.
- Keep positive/negative cancellation diagnostics for transformation data.

### Phase 5 — Make mappings consume the canonical pair classification

Generate a review workbook before changing mapping cells. It must include:

- one row per canonical pair;
- one row per affected workbook cell;
- mapping sheet and exact mapping identity;
- current and proposed values;
- both axis classifications and hierarchy evidence;
- source-signal disagreements;
- rollup/exception context;
- coherent parent and immediate-sibling groups;
- cross-sheet conflicts;
- confidence and required human decision.

For the maintained sheets:

- `leap_combined_esto`
- `ninth_pairs_to_esto_pairs`
- `leap_combined_ninth`

require:

- `leap_is_subtotal`, `ninth_pair_is_subtotal`, and
  `esto_pair_is_subtotal` contain the approved canonical booleans;
- identical LEAP pair flags across both LEAP sheets;
- identical Ninth pair flags across both Ninth sheets;
- identical ESTO/ESTO Extended pair flags across both ESTO-target sheets;
- no blank or non-boolean flag on complete active mapping rows;
- every `True` traceable to at least one parent axis or an approved additive
  synthetic classification;
- every leaf/leaf `False` traceable to resolved leaf nodes on both axes.

Do not automatically write the canonical mapping workbook. Apply reviewed
changes only after explicit approval, using exact row identities and a
formatting-preserving workbook path. Physically remove rejected mappings;
do not retain incorrect relationships as inactive guardrails.

All Boolean mapping columns must remain actual Boolean values displayed as
Excel in-cell checkboxes. When a reviewed write adds rows or changes Boolean
cells, copy the complete checkbox representation from a correctly formatted
cell on the same sheet before setting the value. Copying only `True`/`False`,
ordinary styles, or data validation is not sufficient. After saving, reopen
and visually inspect every edited Boolean column. Any literal displayed
`True`/`False`, or a mixture of literal Booleans and checkboxes in the same
populated column, is a failed workbook write. If the editing library cannot
preserve the checkbox representation, stop and use a proven lossless Excel
editing route.

### Phase 6 — Audit and redesign subtotal exceptions

Audit:

- `subtotal_mismatch_allowed`;
- `subtotal_label_exceptions`;
- `subtotal_label_overrides`;
- any code-level or CSV exception lists;
- non-expanding and detached rollup exclusions.

Classify each row as confirmed, redundant, stale, mis-scoped, or unresolved.
Separate:

- structural classification override requests, which should be extremely rare
  and require a declared semantic relationship;
- accepted cross-system subtotal mismatches;
- known source numerical non-additivity;
- unavailable validation;
- mapping-frontier or rollup exceptions.

Remove exceptions that only preserve a historically incorrect workbook value
after their replacements have been reviewed.

### Phase 7 — Integrate `leap_initialisation`

Replace local re-derivation of structural subtotal truth with the strict
contract loader. Inventory consumers before changing them; some local uses of
`subtotal_layout`, `subtotal_results`, or ESTO reference flags are
period-specific value filters and may remain valid as contextual data logic.

Keep those value filters explicitly distinct from structural classification.
Add compatibility tests proving that migration changes only cases where the
old local inference disagreed with the approved contract.

Do not make `leap_initialisation` import an arbitrary checkout of
`leap_mappings` at runtime. Use the agreed versioned artifact or an explicitly
managed shared package.

### Phase 8 — Build the dashboard checking surface

Use the Mapping diagnostics page and its **All sector rollup structure**
element as the main human checking surface.

The dashboard must load the same structural contract as the mapping review and
show:

- contract version, build ID, input hashes, and freshness;
- selected dataset and axis;
- ordinary hierarchy separately from rollup/comparison relationships;
- parent, immediate children, and siblings;
- per-axis parent status and resulting pair subtotal status;
- source subtotal signals as evidence;
- numerical conformance status by economy, scenario, and period;
- missing children, mapping ambiguity, and inherited source inconsistency;
- exception status and reason;
- current versus proposed workbook flag during review;
- Extended-only, duplicate, orphan, unresolved, and failed states clearly.

The interface must make this distinction obvious:

```text
Structural subtotal: YES
Children add to parent in this context: NO
```

Add a focused route or selection mechanism so each proposed parent/sibling
group in the review workbook can be opened directly. A reviewer must not need
to search manually for every case.

The dashboard is a visual and diagnostic acceptance check. It does not compute
or override canonical classifications. Refuse to show a green/clean state when
the contract is stale, missing, invalid, or built from different inputs than
the review workbook.

### Phase 9 — Validate end to end

Add focused unit, contract, integration, and representative real-data tests.
At minimum test:

1. parent sector + leaf fuel → subtotal;
2. leaf sector + parent fuel → subtotal;
3. parent sector + parent fuel → subtotal;
4. leaf sector + leaf fuel → not subtotal;
5. structurally parent Ninth `09.06` with failed child sum → subtotal plus
   failed/non-additive diagnostic;
6. structurally parent Ninth `09.08` with failed child sum → subtotal plus
   failed/non-additive diagnostic;
7. historical and projection source flags disagree but hierarchy is stable;
8. a missing child produces incomplete/unavailable, not pass and not leaf;
9. a non-expanding or detached boundary does not become an ordinary hierarchy
   edge;
10. an additive synthetic rollup receives its declared subtotal treatment;
11. the same pair appearing in two mapping sheets receives the same flag;
12. an adapter for a small synthetic fourth/fifth dataset works without
    editing the core classifier;
13. a stale or mismatched contract is rejected by both consumers;
14. the dashboard renders structural status and additivity status separately;
15. source failures propagate as attribution without being hidden.

Then run:

- mapping maintenance and relevant Stage 0 QA;
- Stages 1–3 on a bounded representative slice;
- the full pipeline when safe and proportionate;
- dashboard contract and render tests;
- initialisation contract and filtering tests;
- workbook formatting and exact-cell verification after any approved write.

Compare before and after:

- mapping cardinality;
- raw and rollup-aware graph structure;
- additive frontiers;
- source-total preservation;
- parent/child diagnostics;
- exception counts and reasons;
- dashboard warnings;
- output-contract provenance.

## Required deliverables

Keep outputs narrow and clearly named.

1. A diagnosis document in `docs/` describing the old implementations,
   disagreements, and migration decisions.
2. The canonical adapter-based hierarchy/subtotal engine in `leap_mappings`.
3. A versioned structural contract and strict loader.
4. A contract schema/reference document with a worked Ninth non-additivity
   example.
5. A cell-level subtotal review workbook and concise summary.
6. A reviewed exception audit.
7. Dashboard loader, diagnostic UI, and tests.
8. Initialisation loader/migration and tests.
9. A final end-to-end verification report with exact commands, inputs, hashes,
   results, known limitations, and unresolved human decisions.
10. Updates to `docs/mappings_system.md`, `docs/work_queue.md`, prompt
    inventory, and affected repository guides.

Commit small, coherent checkpoints in the repository that owns each change.
Do not combine unrelated dirty work. Report every commit and any intentionally
uncommitted generated workbook.

## Acceptance criteria

The work is complete only when:

- structural subtotal truth is produced once by `leap_mappings`;
- adding a dataset requires an adapter/configuration, not core classifier
  branches;
- pair subtotal status follows the any-axis-parent rule everywhere;
- numerical non-additivity never changes a structural parent into a leaf;
- Ninth `09.06` and `09.08` are covered by real-data regression evidence;
- all current mapping pairs resolve or appear in a bounded review queue;
- identical pairs have zero cross-sheet flag conflicts;
- exceptions no longer act as undocumented structural truth;
- dashboard and initialisation consume the same validated contract build;
- the dashboard visibly separates structure from numerical conformance;
- stale or incompatible contracts fail closed;
- mappings, rollups, graph partitions, and additive frontiers have no
  unexplained regression;
- approved workbook edits preserve layout, formatting, formulas, validations,
  filters, and exact mapping identity;
- every populated maintained Boolean cell in edited mapping rows displays as
  an in-cell checkbox after save and reopen, with no literal `True`/`False`
  remaining in checkbox columns;
- all targeted tests and agreed end-to-end checks pass, with pre-existing
  failures documented separately.

## Stop and escalation conditions

Continue through diagnosis, code, tests, contract outputs, and consumer
integration without pausing for ordinary implementation choices.

Stop before:

- writing proposed subtotal values into the canonical mapping workbook without
  explicit human approval;
- changing a reviewed rollup mode or hierarchy relationship whose semantics
  cannot be established from repository evidence;
- deleting or broadly rewriting exception rows without a review artifact;
- replacing shared outputs while another process is using them;
- choosing between conflicting source hierarchies when the choice would change
  mapping meaning;
- expanding the task into correction of Ninth or ESTO source values.

When stopping, provide the exact disputed nodes/pairs, both interpretations,
downstream impact, evidence already checked, and the smallest decision needed
from the user. Do not use a failed additivity check by itself as evidence that
the hierarchy is wrong.
