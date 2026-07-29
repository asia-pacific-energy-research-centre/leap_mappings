# Dataset and comparison-scope registries

These files are the reviewed M1 configuration surface for dataset identity and
comparison membership:

- `dataset_registry.csv` declares the five datasets currently understood by
  the mapping framework.
- `comparison_scopes.csv` declares every existing comparison scope and which
  four the pipeline builds by default.

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

M1 intentionally does not move mapping-sheet interpretation, dataset parsing,
or rollup rules into these files. Those are separate migration milestones in
`docs/multi_dataset_mapping_framework.md`.
