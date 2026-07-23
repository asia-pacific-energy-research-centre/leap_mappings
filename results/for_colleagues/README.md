# `results/for_colleagues/`

Not part of the main pipeline run. Built by `codebase/for_colleagues_export_workflow.py` as a
manual step, to produce simplified, trimmed copies of the comparison data safe to share outside
the repo (e.g. by email or a shared drive).

| File | Purpose |
|---|---|
| `common_esto_comparison_wide.csv` | Copy of the final wide Common ESTO comparison output. |
| `source_pair_to_common_row.csv` | Simplified source-to-common membership file, trimmed to the useful review columns (`comparison_scope`, `source_system`, `source_flow`, `source_product`, `common_flow`, `common_product`, `common_row_is_subtotal`, `source_row_is_subtotal`). |

Re-run `codebase/for_colleagues_export_workflow.py` after a pipeline run to refresh these.
