# Prompt: Explore an interactive anchor-tree diagnostic

Work in `C:\Users\Work\github\leap_mappings` and, for dashboard code and
rendered outputs, `C:\Users\Work\github\leap_dashboard`. Read both relevant
`AGENTS.md` files before changing code. Start with `git status --short` in each
repository and preserve all pre-existing changes, especially mapping workbooks
and generated outputs owned by another agent.

## Purpose

Explore, prototype, and assess an interactive diagnostic that lets a reviewer
inspect source hierarchy values, their mapped Common ESTO representation, and
the anchor comparison without confusing a mapping route with a hierarchy edge.
This is a design-and-evidence task first. Do not change the canonical mapping
workbook or silently change validator semantics.

The current static `mapping_diagnostics.html` is useful but has an important
presentation limitation: its right-hand panel can show the same Common ESTO row
once as reached from a source parent and again as reached from a source child.
Those are two **mapping routes**, not two values that should be added.

## Required semantic model

Keep these three things separate in the design and in every label:

1. **Original source tree**: the actual LEAP, NINTH, or ESTO parent/child
   hierarchy, with raw source values.
2. **Mapping routes**: arrows from one source node to one or more Common ESTO
   comparison rows. A source parent may fan out directly to several target rows.
3. **Mapped Common ESTO tree**: the real parent/child hierarchy among the
   Common ESTO rows reached by the mapping. Only draw a parent/child edge on the
   right when it exists in the Common ESTO hierarchy. Do not fabricate a target
   tree merely because a source parent has children.

For example, `Other loss and own use` may map directly to Common ESTO Coal
mines and Oil/gas extraction. If those target rows are siblings rather than a
parent and child, the right panel must say that there is **no mapped target
parent/child roll-up for this source parent**. It should show the direct fan-out
and the unique mapped comparison rows, but not pretend Coal mines and Oil/gas
extraction are children of an ESTO row called Other loss and own use.

## Display requirements to investigate

For a selected failed or flagged anchor context, prototype a scrollable map or
tree explorer which can show:

- raw source parent and children, including a raw children sum and residual;
- the actual mapped Common ESTO rows, with their real hierarchy where available;
- a direct mapping fan-out view where no target-tree parent/child relation
  exists;
- mapping arrows or route details that can be toggled independently from target
  hierarchy edges;
- the precise set of Common ESTO row IDs included in the anchor total, each
  counted once;
- an explicit validator comparison: source value in its raw convention, source
  value after any validator-only sign normalisation, unique mapped comparison
  total, and difference;
- source-data warnings, exception/flag status, incomplete-frontier status, and
  the reason an anchor is not actionable;
- an explanation of why a route might repeat a target row without changing the
  numeric total.

### Number display

Do not independently round every value to three significant figures. Select a
single human-friendly scale for the whole inspected context (for example
`values in thousands, ×1,000`) and show enough stable decimal precision that
displayed children visibly reconcile to their displayed total. Avoid exposing
floating-point noise. State that calculations use the unrounded values.

## Suggested investigation sequence

1. Trace the current anchor validator's definition of its unique comparison
   total and identify the existing outputs which carry Common ESTO row IDs,
   raw child values, mapping routes, and target hierarchy relationships.
2. Use at least three concrete cases:
   - LEAP `Other loss and own use` / Natural gas (direct fan-out, no invented
     target parent);
   - a real source-tree inconsistency in NINTH;
   - a case where the mapped Common ESTO rows genuinely do form a target
     hierarchy.
3. Produce a compact text/table design before building a browser prototype.
   State precisely what each node, arrow, number, and total means.
4. Build the smallest self-contained HTML prototype or extension needed to test
   the idea. Avoid a new application framework or external network dependency.
   A scrollable SVG/HTML map with click-to-expand detail is sufficient.
5. Render it using real generated pipeline outputs, visually inspect it, and
   compare every shown total with the validator artifact.
6. Decide whether this can safely replace or augment the current paired cards.
   Record limitations such as very large graphs, many-to-many routes, absent
   target hierarchy, and mobile layout.

## Guardrails

- Mapping candidates and route discoveries are review-only. Never write them
  into `config/outlook_mappings_master.xlsx`.
- Do not treat mapping fan-out as duplicate data. The anchor total must count
  each included `common_row_id` exactly once.
- Do not suppress a true source-tree contradiction merely because a mapped total
  happens to reconcile.
- Do not alter exception workbook entries during this exploration.
- If a target hierarchy relationship or dashboard meaning is ambiguous, stop
  and request a human decision rather than inventing one.

## Deliverables and success criteria

Provide:

- a short findings/design document explaining the chosen visual grammar;
- a prototype HTML output rendered from real data, or a clear evidence-backed
  explanation of why a prototype is not yet feasible;
- the cases used and their raw-vs-mapped numeric reconciliation evidence;
- a recommendation on whether to integrate it into `mapping_diagnostics.html`;
- focused tests and visual QA evidence for any code change;
- a small, dedicated `codex:` commit for only files owned by this task.

The design succeeds only if a reviewer can answer, without inference: “Which
source parent is being checked?”, “Which target rows are counted?”, “Are these
target rows siblings or a genuine target roll-up?”, and “Why is this total not
the sum of every displayed mapping route?”
