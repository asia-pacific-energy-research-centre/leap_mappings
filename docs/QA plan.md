## Mapping pipeline smoke test

This is the focused automated smoke-test reference, not the complete release
or handover QA plan. For full-run order, status-manifest interpretation,
contract checks, and human stop conditions, use
[`handover/mapping_pipeline_agent_guide.md`](handover/mapping_pipeline_agent_guide.md).

The repository now includes an opt-in real-data smoke test that runs the
notebook-style mapping pipeline sequence against the checked-in inputs:

```shell
RUN_MAPPING_PIPELINE_SMOKE=1 pytest -q tests/test_mapping_pipeline_smoke.py
```

What it exercises:

1. Stage 1 relationships: `energy_balance_relationships.csv` and `.xlsx`.
2. Stage 2 common ESTO structure: `common_esto_rows.csv` and the map output.
3. LEAP parse and data conversion: raw LEAP export, LEAP-to-ESTO, 9th-to-ESTO,
   and ESTO exact rows.
4. Stage 3 application: `common_esto_comparison_data.csv` plus tree validation
   outputs and the Stage 3 status manifest.

Focused hierarchy/subtotal-contract and missing-ESTO-row reviews are tested
separately because they are optional input-review workflows, not a generic
pipeline stage.

The test is skipped by default so the regular unit suite stays fast. It writes
to `results/` and reads the real tracked inputs, so it is best treated as an
integration smoke test rather than a pure unit test.
