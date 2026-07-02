## Mapping pipeline smoke test

The repository now includes an opt-in real-data smoke test that runs the
notebook-style mapping pipeline sequence against the checked-in inputs:

```shell
RUN_MAPPING_PIPELINE_SMOKE=1 pytest -q tests/test_mapping_pipeline_smoke.py
```

What it exercises:

1. Stage 0 maintenance: subtotal flags, cardinality, and maintenance QA files.
2. Stage 1 relationships: `energy_balance_relationships.csv` and `.xlsx`.
3. Stage 2 common ESTO structure: `common_esto_rows.csv` and the map output.
4. LEAP parse and data conversion: raw LEAP export, LEAP-to-ESTO, 9th-to-ESTO,
   and ESTO exact rows.
5. Stage 3 application: `common_esto_comparison_data.csv` plus tree validation
   outputs and the Stage 3 status manifest.

The test is skipped by default so the regular unit suite stays fast. It writes
to `results/` and reads the real tracked inputs, so it is best treated as an
integration smoke test rather than a pure unit test.

