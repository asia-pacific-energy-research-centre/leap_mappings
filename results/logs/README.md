# `results/logs/`

| File | Purpose |
|---|---|
| `mapping_pipeline.log` | Tee'd console output of the **last** `run_mapping_pipeline.py` run (overwritten each run, via `_TeeWriter` in `run_mapping_pipeline.py`). Check this first when a pipeline run fails or produces unexpected output — it has every stage's printed diagnostics in one place. |

As of 2026-07-23, every other file that used to sit directly in this folder (timestamped
`mapping_pipeline_<timestamp>.log`, `mapping_pipeline_codex_*`, `stage_runs/`, `*.pid`/`*.pid.txt`,
`*.ps1`, `stdin_pipe_test.*`, etc. — leftovers from ad hoc/manual terminal invocations during
earlier development) has been moved to `_archive_2026-07-23/` (see `docs/archive_log.md`). None
of that is produced by any current code path — only `mapping_pipeline.log` is.
