# Preservation-first Markdown consolidation plan

**Status:** reviewed proposal; no source document has been moved or deleted

**Scope:** active Markdown in `leap_mappings`, `leap_initialisation`, and
`leap_dashboard`

**Evidence date:** 2026-07-28

**Archive after:** the approved consolidation work is complete and verified

## Goal

Reduce the number of live documents a maintainer must choose between without
discarding technical rules, decisions, dated evidence, commands, or historical
reasoning.

The target is not the smallest possible file count. The target is one
authoritative live document per purpose, with dated source material preserved
under `docs/archive/` when it is no longer an operating instruction.

## Preservation rules

Every consolidation must:

1. identify the destination document and its authority before editing;
2. inventory every source heading and its unique claims;
3. copy all still-useful material into a named destination section;
4. retain dates, commit IDs, measured counts, commands, limitations, and human
   decisions when they remain meaningful;
5. include a provenance appendix mapping each source file and heading to its
   destination or archival disposition;
6. move superseded originals to a dated `docs/archive/` bundle rather than
   deleting them;
7. update every live relative link in the same commit;
8. render changed Markdown and Mermaid, scan active links, and compare the
   combined document against the source-heading inventory; and
9. use a small, repository-specific commit so the consolidation can be
   reversed cleanly.

Git history is useful recovery evidence, but it is not a substitute for
preserving a readable archived source when that source contains human
decisions or investigation results.

## High-confidence merges

### 1. Mapping hierarchy/subtotal contract

Create one live `leap_mappings/docs/hierarchy_subtotal_contract.md`.

| Source | Unique role to preserve |
|---|---|
| `hierarchy_subtotal_contract_reference.md` | packaging, members, invariants, worked non-additivity example, consumer contract |
| `hierarchy_subtotal_contract_diagnosis.md` | decision, input baseline, prior derivations, Ninth regression, migration boundary |
| `hierarchy_subtotal_contract_verification_20260728.md` | dated inputs, commands/results, limitations, unresolved decisions |

Recommended combined order:

1. authority and current status;
2. contract reference;
3. production and consumer invariants;
4. diagnosis and migration rationale;
5. worked example;
6. dated verification evidence;
7. known limitations and open human decisions;
8. source-provenance appendix.

Keep `subtotal_columns_rebuild_plan.md` separate while MAPQ-030 remains active.
It governs human review and workbook application, whereas the combined
contract document defines and verifies the structural artifact.

Expected result: three live documents become one; all three originals move
together to `docs/archive/hierarchy_subtotal_contract_20260728/`.

### 2. Initialisation All-demand-aggregated guides

Create one live
`leap_initialisation/docs/all_demand_aggregated_branch_guide.md`.

| Source | Unique role to preserve |
|---|---|
| `colleague_intro_all_demand_aggregated.md` | nontechnical purpose, project context, colleague-facing LEAP task |
| `leap_all_demand_aggregated_branch_guide.md` | exact branch structure, naming rules, fuel-count check |

Recommended combined order:

1. plain-English purpose;
2. structure to create;
3. exact LEAP steps;
4. naming rules;
5. fuel-count and completion checks;
6. source-provenance appendix.

Use audience callouts inside the combined guide instead of retaining two nearly
parallel entry points. Preserve both originals in
`docs/archive/all_demand_aggregated_guides_20260728/`.

Expected result: two live documents become one.

### 3. Dashboard operating guides

Retire `leap_dashboard/docs/common_esto_dashboard_guide.md` as a parallel
operating guide after its unique material has been distributed:

| Destination | Material to receive |
|---|---|
| `docs/handover/dashboard_pipeline_guide.md` | conceptual inputs, configuration ownership, publication meaning, ESTO Extended behavior |
| `docs/handover/dashboard_pipeline_agent_guide.md` | exact run commands, environment variables, fixture refresh, smoke tests, operational checks |

The reader and agent guides must remain separate. The consolidation removes
only the older third operating guide. Archive it with a provenance note after
all commands and settings are accounted for.

Do this after the current diagnostics renderer/test changes are committed, so
the operating instructions can be verified against one stable code state.

Expected result: three parallel operating guides become the existing two-level
reader/agent pair.

## Archive or partition; do not concatenate

### Dashboard current-state plan

`common_esto_dashboard_plan.md` mixes three document types:

- implemented-state description;
- active backlog;
- historical build record.

Do not concatenate the whole file into another guide. Instead:

1. move any unique current-state facts into the pipeline guide;
2. move every still-live task into `docs/work_queue.md`;
3. preserve the historical build record as a dated archive document; and
4. archive the original plan only after a row-by-row task comparison.

Wait until DASHQ-007 produces the next reproducible baseline, because several
current-state and page-count statements are deliberately dated.

### Audit and handover snapshots

The following are preservation candidates for dated archive bundles, not
content to paste into current runbooks:

- mappings documentation audit and disposition;
- mappings `cross_repository_handover_index.md`;
- initialisation documentation audit and disposition;
- initialisation `cross_repo_handover_index.md`, after its unique contract
  details are confirmed in the maintained central contract;
- dashboard documentation audit;
- dated page-status and visual-review evidence after replacement evidence is
  published.

Keep the files intact inside archive bundles. Update the live index to describe
their date and evidentiary purpose.

### Historical plans with live references

Do not archive `leap_mappings/docs/improvement_todo.md` yet. Live code still
cites its item 8. First replace that citation with the controlling queue item
or canonical rule, then confirm every remaining live task is represented in
`docs/work_queue.md`.

Do not merge cleanup/storage documents merely because they share filenames or
terms:

- `repo_data_slimdown_plan.md` describes required/extractable repository data;
- `results_folder_cleanup_candidates.md` contains candidate-specific safety
  evidence;
- `results_output_storage.md` defines the maintained output and retention
  contract;
- `esto_extended_delta_storage_design.md` defines one specialized dataset
  design.

Their scopes are related but not interchangeable.

## Documents that should remain separate

Similarity alone is not a reason to merge these:

| Documents | Reason to keep separate |
|---|---|
| reader guide and paired agent guide | different audience and safety depth |
| `process_map_human.md` and `process_map_agent.md` | deliberate modeller/technical views |
| `mappings_system.md` and mapping pipeline guide | canonical semantic reference versus runnable overview |
| mapping editor guide and rollup-rules reference | workbook editing task versus rollup implementation semantics |
| special-rules decision log and work queue | stable decisions versus changing priorities |
| check registry and rule inventory | gate ownership versus detailed rule definitions |
| dated run/investigation findings and general runbooks | evidence must not silently become permanent operating policy |
| cross-repository data contract and local workflow guides | producer/consumer boundary versus repository operation |

## Recommended execution sequence

1. Merge the mapping hierarchy/subtotal contract trilogy.
2. Merge the two initialisation All-demand-aggregated guides.
3. After the dashboard diagnostics change is committed, absorb the older
   dashboard operating guide into the reader/agent pair.
4. After the next clean mappings/dashboard generation, partition and archive
   the dashboard current-state plan.
5. Archive dated audit/handover snapshots in repository-specific batches.
6. Recount active documents and repeat the overlap scan before considering any
   further merge.

The first three changes would remove four documents from the live reading
surface while retaining every original under archive. The later partition and
snapshot work can reduce the live surface further, but should be gated by the
current pipeline and dashboard baselines rather than performed from stale
counts.

## Completion gate for each merge

A merge is complete only when:

- every source heading has a destination or explicit archived-only rationale;
- no live relative link points to the old location;
- the combined document renders correctly;
- Mermaid blocks render successfully;
- the repository's active-document link scan passes;
- the documentation index and start page identify the new authority;
- the archived originals and provenance appendix make reversal possible; and
- the commit contains no unrelated code, workbook, queue, or generated-output
  change.
