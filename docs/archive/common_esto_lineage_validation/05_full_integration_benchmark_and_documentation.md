# Prompt 5: full integration, benchmark and documentation

Work in `C:\Users\Work\github\leap_mappings`. Complete Prompts 1-4 first.

## Goal

Run the complete mapping/application/validation chain, prove output integrity
and performance, and document the operational workflow.

## Required work

1. Run structural compilation independently.
2. Run the partitioned value application for the requested full data scope.
3. Run structural validation, the standard slice and full anchor validation.
4. Confirm final CSV compatibility with existing Stage 3/dashboard consumers.
5. Compare final values and coverage against the previous outputs. Explain all
   material differences; do not overwrite unexplained regressions.
6. Record runtime, peak memory where measurable, cache size, partition counts,
   mapped/unmatched values and validation status.
7. Test restart/cache behavior and stale-cache invalidation.
8. Update `docs/mappings_system.md` with:
   - compilation/application/validation boundaries;
   - artifact schemas and directions;
   - membership-versus-allocation warning;
   - partitioning and cache behavior;
   - final CSV locations;
   - structural, slice and full validation instructions;
   - QA interpretation and troubleshooting.

## Performance rules

- Do not load all source values into one pandas DataFrame.
- Do not build a tens-of-millions-row pass-detail table by default.
- Report progress per partition.
- A failed partition must be explicit in the manifest; partial outputs must not
  masquerade as complete final CSVs.

## Final acceptance criteria

- Structural tasks run without loading full value datasets.
- Value application and validation stay within bounded memory.
- Final human-facing CSV outputs are complete and deterministic.
- Common rows can be inspected back to ESTO, Ninth and LEAP membership.
- Every common value has auditable source lineage.
- Anchor validation covers all three datasets and both applicable axes.
- No hierarchy is inferred from string prefixes.
- All tests pass and benchmark results are documented.
- Commit documentation and any final integration fixes in one coherent
  `codex:` commit, excluding unrelated workbook changes.

