# Multi-dataset migration baselines

This folder stores small, tracked manifests for equivalence checks. The large
generated artifacts remain under `results/` and are not copied into Git.

`multi_dataset_m0_reference_20260729.json` distinguishes:

- fresh Stage 1 and Stage 2 artifacts generated in the isolated registry
  worktree; and
- the most recent available Stage 3 artifacts, retained only as historical
  reference evidence.

The manifest is intentionally not a release certificate. The historical Stage
3 run predates the registry branch and contains known failed validations. A
fresh QA-reviewed Stage 3 run is still required before
`release_gate_complete` can become `true`.

Capture logic lives in
`codebase/mapping_tools/capture_multi_dataset_baseline.py`. It records ordered
CSV schemas, row counts, byte sizes, SHA-256 hashes, Git context, Stage 3
timings, and bounded validation summaries without embedding machine-local
artifact paths.
