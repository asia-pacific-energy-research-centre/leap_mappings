# Dataset and comparison-scope registries

These files are the reviewed M1 configuration surface for dataset identity and
comparison membership:

- `dataset_registry.csv` declares the five current datasets plus the
  disabled-by-default synthetic onboarding dataset.
- `comparison_scopes.csv` declares every existing comparison scope and which
  four the pipeline builds by default.
- `mapping_sheet_registry.csv` declares how the three maintained workbook
  sheets compile into the current normalized relationship surface.
- `rollup_sheet_registry.csv` declares how dataset-specific rollup columns
  compile into the normalized rollup-rule surface.
- `value_adapter_registry.csv` declares native adapter execution order and the
  normalized artifacts admitted to Stage 3.

Pipe (`|`) separates ordered values inside list fields. `default_order`
preserves the current pipeline build order independently from the order of all
available scope definitions. Dataset identifiers use
upper snake case because they match current `source_system` values. Comparison
scope identifiers use lower snake case because they match existing output
contracts.

The loader in
`codebase/mapping_tools/dataset_registry.py` rejects duplicate identifiers,
invalid booleans, unknown dataset references, empty membership/use-case lists,
and default scopes that have been disabled. A registry edit should be followed
by:

```powershell
& 'C:\Users\Work\miniconda3\python.exe' -m pytest tests/test_dataset_registry.py -q
```

Registry stewardship is deliberately lightweight. A permanent named owner is
not required: the owner or user operating the system is responsible for the
entries they change, and Git history plus review metadata supplies provenance.
The `owner` column may identify a useful person or role but is not an approval
gate.

M1 intentionally does not move mapping-sheet interpretation, dataset parsing,
or rollup rules into these files. Those are separate migration milestones in
`docs/multi_dataset_mapping_framework.md`.

M2 moves mapping-sheet identity, dataset direction, ordered source/target
column candidates, and use-case membership into `mapping_sheet_registry.csv`.
The workbook remains the human editing surface and is never rewritten by the
registry loader.
