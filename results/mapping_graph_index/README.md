# `results/mapping_graph_index/`

**Not produced by the main pipeline run** (`run_mapping_pipeline.py` never writes here). These
are outputs of standalone dashboard-mapping prototype tools — only relevant if you're working
on dashboard graph-ID wiring, not for the core LEAP/ESTO/9th mapping workflow.

| File | Producing script | Purpose |
|---|---|---|
| `dashboard_graph_index.csv`, `dashboard_graph_flow_index.csv`, `dashboard_graph_product_index.csv`, `dashboard_graph_flow_product_index.csv` | `build_dashboard_graph_index.py` | Graph IDs and index tables built from the LEAP comparison dashboard template. |
| `leap_comparison_dashboard_template_v3_with_graph_ids.json` | same | Graph-ID-stamped copy of the dashboard template (original left untouched). |
| `esto_first_mapping_candidates_dashboard.csv` / `.xlsx` | `convert_leap_combined_esto_to_esto_first.py` | ESTO-first mapping candidate table converted from `leap_combined_esto`. |
| `energy_balance_graph_links.csv` | `build_energy_balance_graph_links.py` | Product-aware dashboard graph links, built from `energy_balance_relationships.csv`. |
| `dashboard_chart_relationships.csv`, `dashboard_relationships_not_used_by_template.csv`, `dashboard_template_flows_without_mapping.csv`, `dashboard_duplicate_source_relationships.csv`, `dashboard_duplicate_target_relationships.csv`, `dashboard_parent_child_risks.csv` | `build_energy_balance_graph_links.py` / `convert_leap_combined_esto_to_esto_first.py` | QA for the dashboard mapping conversion (same filenames get overwritten by whichever script last ran). |

See `archive/2026-07-23_repo_cleanup/mapping_code/README_dashboard_mapping_starter.md` for the
fuller design notes on this dashboard-graph-index prototype (archived 2026-07-23 as a diverged,
unreferenced duplicate of the live `codebase/mapping_tools/` scripts — see `docs/archive_log.md`).
