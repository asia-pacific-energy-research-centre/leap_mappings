# Common ESTO lineage and validation prompt pack

Run these prompts in order. They are split into five reviewable chunks because
the structural mapping contract must be stable before large value datasets or
numeric validation are introduced.

1. `01_shared_rollup_and_hierarchy_resolver.md`
2. `02_compile_structural_mapping_artifacts.md`
3. `03_partitioned_value_application_and_lineage.md`
4. `04_anchor_validation_from_lineage.md`
5. `05_full_integration_benchmark_and_documentation.md`
6. `06_reconcile_anchor_validation_against_conversion_outputs.md`

Each prompt must end at a stable, tested commit. Do not start the next prompt
when the current prompt's success criteria are not satisfied.

Prompt 6 **replaces the anchor-validation methodology from Prompt 4**: instead of
re-deriving each source system's hierarchy from its tree (which manufactures
false failures — see `PROMPT5_STATUS_AND_ISSUES.md`), it reconciles raw source
parent totals against the existing converted-to-ESTO outputs. Prompt 5 (full
integration / certification) should be run only after Prompt 6 lands, because
Prompt 4's tree-walk gate is not semantically credible.

## Existing state to preserve

- Commit `f266131` added source-data rollups to LEAP-to-ESTO conversion.
- `codebase/mapping_tools/source_parent_anchor_validation.py` contains
  uncommitted Claude performance and validation-slice work. The user has
  approved retaining that work, but prefix-based hierarchy inference must be
  removed because it is not a safe source of hierarchy truth.
- `config/outlook_mappings_master.xlsx` has unrelated uncommitted changes.
  Do not edit, stage, or commit it unless the user separately requests that.
- The deleted Excel lock file is unrelated and must not be staged.

## Architectural boundary

```text
compile mappings -> stable structural artifacts
apply mappings   -> partitioned value processing and final CSV
validate         -> structural, slice, or full numeric checks
```

Internal Parquet files are allowed for performance. Final human-facing outputs
must include CSV files.
