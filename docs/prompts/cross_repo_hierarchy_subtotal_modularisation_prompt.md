# Cross-repository hierarchy/subtotal system audit and modularisation prompt

## Objective

Review the hierarchy, subtotal-recognition, mapping-validation, exception, and
tree-building systems across:

- `C:\Users\Work\github\leap_mappings`
- `C:\Users\Work\github\leap_initialisation`
- `C:\Users\Work\github\leap_dashboard`

Identify which implementations are canonical, which are legitimate
dataset-specific consumers, and which independently reconstruct the same
structural truth. Track every relevant path and produce a practical
modularisation and migration plan.

This is a separate architecture/audit task. Do not continue the mapping-master
workbook review or change subtotal labels in this task.

## Working rules

1. Read all applicable `AGENTS.md` files before acting.
2. Use a new worktree for this task. The active `leap_mappings` checkout has
   unrelated in-progress changes that must not be modified, staged, or
   committed.
3. Start with a read-only audit. Do not begin a broad refactor merely because
   duplication is found.
4. Treat the findings below as starting hypotheses. Verify each one directly
   against current code, tests, documentation, and call sites.
5. Distinguish carefully between:
   - structural hierarchy truth;
   - source-reported or period-specific subtotal flags used to filter values;
   - cross-dataset mapping mismatch checks;
   - exception/override policy;
   - presentation-only tree construction.
6. Do not replace legitimate source-period filters such as Ninth
   `subtotal_layout`/`subtotal_results` or raw ESTO `is_subtotal` merely because
   a canonical structural contract exists. Those flags may describe a
   different, contextual question.
7. Prefer a dependency-light shared consumer interface over cross-repository
   imports from an arbitrary local checkout.
8. Record identified work in the relevant `docs/*.md` work queues. Use stable
   task IDs and cross-link them from the main audit document.
9. Commit only the audit/tracking changes made by this task. If a small,
   clearly safe implementation is proposed, document it first and leave it for
   a separately scoped implementation task unless it is necessary to validate
   the proposed boundary.

## Starting hypotheses to verify

### `leap_mappings`

The likely canonical producer is:

- `codebase/mapping_tools/hierarchy_subtotal_adapters.py`
- `codebase/mapping_tools/hierarchy_subtotal_contract.py`
- `codebase/mapping_tools/hierarchy_subtotal_review.py`
- `codebase/mapping_tools/hierarchy_subtotal_contract_workflow.py`

It appears to own the versioned hierarchy/subtotal contract, source-specific
adapters, structural node classification, canonical source pairs, declared
edges, and value-conformance diagnostics.

Potential parallel or older implementations include:

- `codebase/leap_mapping_refresh_workflow.py`
- `codebase/mapping_tools/infer_subtotal_labels.py`
- `codebase/archive/outlook_mapping_maintenance_workflow.py`
- `codebase/mapping_tools/build_subtotal_mismatch_review.py`
- `codebase/mapping_tools/apply_subtotal_updates.py`
- `codebase/mapping_tools/apply_subtotal_mismatch_review.py`
- `codebase/mapping_tools/build_dataset_tree_structure.py`
- `codebase/mapping_issue_exceptions.py`

Verify whether these paths are active, legacy, specialized, or duplicative.
Trace their callers and outputs rather than classifying them from filenames.

Review the semantics of these exception sheets in
`config/mapping_issue_exception_sets.xlsx`:

- `subtotal_mismatch_allowed`
- `subtotal_label_exceptions`
- `subtotal_label_overrides`

Determine whether they represent distinct policies or overlapping historical
mechanisms. In particular, do not assume that an allowed cross-dataset mismatch
proves either dataset's subtotal label is correct.

### `leap_initialisation`

There appears to be a strict consumer loader at:

- `codebase/mappings/hierarchy_subtotal_contract_loader.py`

Verify whether it is wired into active runtime paths or currently used only by
tests/documentation.

Investigate local structural re-derivation in at least:

- `codebase/outlook_mapping_maintenance_workflow.py`
- `codebase/functions/outlook_mapping_maintenance_utils.py`
- `codebase/mapping_tools/update_mapping_cardinality.py`
- `codebase/utilities/energy_balance_template_extractor.py`
- `codebase/utilities/leap_results_dashboard_balance.py`
- `codebase/mapping_tools/mapping_rollups.py`
- `codebase/mapping_tools/prepare_new_esto_data.py`

For each path, decide whether it:

- needs canonical structural status from the contract;
- legitimately filters source values using period/scenario-specific subtotal
  flags;
- performs LEAP-export/template-specific transformation;
- or duplicates hierarchy inference that should be retired.

### `leap_dashboard`

Likely relevant files include:

- `codebase/hierarchy_subtotal_contract_loader.py`
- `codebase/mapping_diagnostics_contract.py`
- `codebase/common_esto_dashboard_mapping_diagnostics.py`

Verify whether the Mapping diagnostics page consumes the canonical contract,
when it falls back to legacy CSV/tree artifacts, and whether any presentation
logic accidentally becomes structural authority.

Compare the dashboard contract loader with the initialisation loader. They
appear nearly identical and may be candidates for a shared, dependency-light
consumer module or generated/reference-tested copies.

## Required audit method

Build a call-site and artifact inventory, not just a keyword list.

For every relevant implementation, record:

- repository and file;
- public functions or executable entry points;
- callers;
- input artifacts and schemas;
- output artifacts and schemas;
- hierarchy/subtotal definition used;
- exception sheets or override mechanisms used;
- current status: canonical authority, source adapter, consumer,
  contextual filter, compatibility fallback, duplicate, or legacy;
- recommended disposition: retain, wrap, migrate, deprecate, or remove;
- evidence supporting that classification.

Search for function calls and imported symbols as well as terms such as:

- `subtotal`
- `is_subtotal`
- `subtotal_layout`
- `subtotal_results`
- `structural`
- `hierarchy`
- `parent`
- `rollup`
- `tree`
- `axis_nodes`
- `canonical_source_pairs`
- `value_conformance`
- `mapping_issue_exception_sets`

Inspect tests and documentation for intended ownership. Where code and
documentation disagree, report both and identify current runtime behaviour from
call sites.

## Architecture questions to answer

1. What is the single authority for structural parent/subtotal truth?
2. Which source adapters belong beside that authority?
3. Which value filters must remain local because they are
   period/scenario/source-specific?
4. Which repos need only a strict loader and pair-status attachment API?
5. How should the shared consumer code be distributed without coupling runtime
   code to a sibling checkout?
6. Can the dashboard and initialisation loaders share one tested package, or is
   generated code plus conformance fixtures safer?
7. What is the clean taxonomy for label overrides, label exceptions, and
   cross-dataset mismatch allowances?
8. Which legacy fallback paths are still exercised, and what must be true
   before they can be removed?
9. Which migrations are high-risk because they affect value filtering rather
   than structural annotation?
10. How can all three repos prove they interpreted the same contract version
    and schema?

## Target modular boundary to evaluate

Evaluate, rather than automatically adopt, this ownership model:

### Producer owned by `leap_mappings`

- contract schema and versioning;
- source-specific hierarchy adapters;
- canonical node/edge/pair status;
- mapping-cell review evidence;
- exception classification;
- contract build and validation.

### Small shared consumer interface

- strict manifest/member/hash/schema validation;
- `load_contract(...)`;
- `attach_pair_status(...)`;
- clear failures for stale or incompatible artifacts;
- common conformance fixtures used by all consumer repos.

### `leap_initialisation` consumers

- attach canonical structural status at mapping ingress;
- retain contextual source-period filtering;
- retain LEAP-template/export transformations;
- stop independently declaring structural truth where the contract covers it.

### `leap_dashboard` consumers

- adapt canonical contract tables for rendering;
- display diagnostics and tree structure;
- never infer structural parenthood;
- make legacy fallback explicit, observable, and time-bounded.

Do not centralize dashboard rendering or domain-specific value preparation just
to reduce line count.

## Required outputs

Create:

1. A main audit document in `leap_mappings/docs/`, suggested name:
   `cross_repo_hierarchy_subtotal_modularisation_plan.md`.
2. A compact inventory table covering all three repositories.
3. A duplication map showing which implementations answer the same question
   and which only look similar.
4. A proposed module/API and artifact boundary, including example function
   signatures and schema responsibilities.
5. A phased migration plan with acceptance criteria, tests, dependencies,
   rollback/fallback considerations, and removal conditions.
6. Work-queue entries in the relevant repositories, using stable linked task
   IDs.
7. A short list of deliberately retained local behaviours and why they must
   remain local.
8. A list of unresolved decisions requiring human input.

Suggested migration order to verify:

1. Establish cross-repo contract fixtures and decide how the consumer library
   is distributed.
2. Consolidate exception taxonomy and the mapping-cell review path in
   `leap_mappings`.
3. Wire the contract into `leap_initialisation` at a clear ingress boundary,
   migrating one local structural derivation at a time while preserving
   contextual filtering.
4. Make dashboard fallback use visible and measurable, then remove it only
   after contract freshness and availability are reliable.
5. Deprecate and eventually remove superseded inference/write tools.

## Verification and completion criteria

The audit is complete only when:

- every listed implementation has been verified and classified;
- active call sites are distinguished from dead or test-only code;
- structural inference is distinguished from value filtering;
- duplicate loader behaviour is compared with tests or a concrete diff;
- each proposed migration has a named owner repository and acceptance test;
- work queues link back to the audit document;
- no unrelated worktree changes are included;
- documentation links resolve;
- the scoped documentation/tracking changes are committed with a
  `codex:`-prefixed commit message.

Finish with a concise report of:

- the current authority;
- the most consequential duplication;
- the recommended first implementation step;
- files created or changed;
- verification performed;
- commit hash;
- any decisions still needed from the user.
