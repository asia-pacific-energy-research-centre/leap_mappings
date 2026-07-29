# Separate-axis production promotion and full-system run

**Run date:** 2026-07-30 (Tokyo)

**Outcome:** The separate-axis contract was promoted to local `master`, the
full non-shadow ESTO/ESTO Extended/LEAP/Ninth mapping pipeline completed, and
all 21 available dashboard economies rendered against the same Common ESTO
run. The operational run completed, but it is not a claim that every deep
validation passed. The failures, skipped checks, and semantic debt below remain
open.

## Integration and production contract

Mapping integration and production commits:

- `26c700c` — merge registry framework into diagnostics work;
- `8c737d5` — merge separate-axis mapping feature;
- `3e621ab` — promote the separate-axis mapping contract;
- `682b2a5` — recognize current LEAP balance export names;
- `f3b4590` — refresh structural and registry provenance.

Dashboard commits used by the run and final audit:

- `f158e9b` — record mapping run in dashboard metadata;
- `0df8dd7` — render mapping diagnostics for every economy;
- `8ae8d42` — fix the all-economy diagnostics import path;
- `8999fe8` — carry the matching Stage 3 status into dashboard metadata.

The production ownership boundary is:

- human-edited `config/outlook_mappings_single_axis.xlsx`;
- generated, do-not-edit
  `config/outlook_mappings_key_pairs_generated.xlsx`; and
- generated, do-not-edit compatibility
  `config/outlook_mappings_master.xlsx`.

The generated master retains the 14-sheet downstream contract. Its three pair
sheet bodies are generated. The 11 non-pair sheets remain a temporary
human-maintained exception copied through generation; MAPQ-036 owns their
migration.

The pre-promotion master SHA-256 was
`b1826a4e7f9db60e491e0ff04b42de489cfa395eea68d551675cf9df2736079a`.
The promoted master SHA-256 is
`b17698f2d46803e48a9503247d57315df1aefeab1d855c2538b774c8c2902e65`.
The original is backed up at
`outputs/separate_axis_mapping_refresh/workbooks/prior_canonical_master_b1826a4e7f9d.xlsx`.
Rollback is a Git restore of the master workbook followed by deliberate
regeneration.

The editable workbook contains 585 axis relationships and four narrow
accepted-extra-pair sheets. Generation reproduces all 7,649 previously
maintained relationships and adds 3,501 relationships labelled
`provisionally_accepted`, for 11,150 total:

| Generated pair sheet | Relationships |
|---|---:|
| LEAP to ESTO | 4,811 |
| LEAP to Ninth | 3,568 |
| Ninth to ESTO | 2,771 |

All maintained workbook Boolean values reopened as literal Booleans with
ordinary cell formatting; no checkbox controls or checkbox formatting were
introduced.

## Mapping run identity and inputs

- Common ESTO run ID:
  `common_esto_20260729T175438145911Z`
- Run timestamp:
  `2026-07-29T17:54:38.145911+00:00`
- Operational manifest status: `completed`
- Full pipeline log:
  `results/logs/full_mapping_pipeline_20260730_stdout.log`
- Stderr log:
  `results/logs/full_mapping_pipeline_20260730_stderr.log` (empty)
- Stage 3 elapsed time: 3,891.887 seconds
  - value application: 1,565.261 seconds;
  - Common validation: 981.866 seconds;
  - parent-anchor validation: 1,132.809 seconds.

The manifest enables `ESTO`, `ESTO_EXTENDED`, `LEAP`, `NINTH`, and generated
`COMMON_ESTO`. `SYNTH_BALANCE` and `synth_balance_comparison` remained disabled
and no synthetic rows or scopes appear in the published fact.

All four registered Stage 3 inputs were present, non-empty, readable, and
consumed. Stage 3 read 18,846,357 source rows. LEAP conversion used the five
available balance exports: `01_AUS`, `02_BD` (Brunei Darussalam), `05_PRC`,
`12_NZ`, and `20_USA`, comprising 1,176,275 LEAP rows. All registered source
units are PJ.

The run rebuilt the four registered comparison scopes with exactly these
memberships:

| Scope | Source systems |
|---|---|
| `esto_leap` | ESTO, LEAP |
| `esto_extended_leap` | ESTO_EXTENDED, LEAP |
| `esto_leap_ninth` | ESTO, LEAP, NINTH |
| `esto_extended_leap_ninth` | ESTO_EXTENDED, LEAP, NINTH |

The Stage 3 manifest records the dataset, value-adapter, mapping-sheet,
rollup-sheet, diagnostic-adapter, comparison-scope, scenario, and period policy
registries with current paths, row counts, and SHA-256 hashes.

## Counts and explained deltas

| Artifact | Previous accepted/shadow | Production run | Delta |
|---|---:|---:|---:|
| Stage 1 accepted relationship rows | 17,076 | 22,300 | +5,224 |
| Pair relationships | 7,649 | 11,150 | +3,501 |
| Common component memberships | 10,044 | 10,562 | +518 |
| Compact relationship catalogue | 6,466 | 10,188 | +3,722 |
| Stage 3 fact rows | 1,658,315 | 1,783,707 | +125,392 |

The production output also contains 2,413 metadata rows and 5,028,332 atomic
lineage rows. The material deltas are expected consequences of the 3,501
provisional Cartesian axis combinations, the resulting Common partition
change, and refreshed LEAP exports for the five available LEAP economies. They
are not treated as evidence of correctness by themselves.

The final pair registries contain 34,762 LEAP pairs, 10,692 ESTO pairs, 18,792
ESTO Extended pairs, and 19,695 Ninth pairs.

## Conservation, source-once, and structural QA

All ten mapped scope/source combinations preserve 100% of mapped value. The
maximum absolute before/after difference is
`1.1641532182693481e-10`; no group is outside tolerance.

`qa_source_once_delivery.csv` contains:

- 16,344 `one_common_row` source pairs;
- 54 `protected_parent_detail_alternative` pairs;
- zero unsafe multiple-Common-row deliveries.

All 124 non-expanding-frontier checks are `ok`. The post-commit structural
compiler produced 58,004 source-to-component rows, 10,562 component
memberships, 58,004 source-to-Common rows, and 58,004 reverse rows. It found
zero unresolved, cyclic, duplicate, or conflicting structural rows and 29
ambiguous rows that remain review debt.

## Anchor results

For every summary row,
`failed = confirmed_issue_failed + unconfirmed_failed`. Confirmed issues remain
numerical failures. The detail includes `exception_review_status`,
`exception_id`, and `source_non_additivity_observed`. PRC has zero confirmed
rows. Automatic non-additivity observations remain evidence and do not create
confirmed exceptions.

| Scope | Source | Axis | Failed | Confirmed | Unconfirmed | Non-additivity observed |
|---|---|---|---:|---:|---:|---:|
| `esto_extended_leap` | LEAP | flow | 302 | 0 | 302 | 0 |
| `esto_extended_leap_ninth` | LEAP | flow | 302 | 0 | 302 | 0 |
| `esto_extended_leap_ninth` | NINTH | flow | 876 | 0 | 876 | 0 |
| `esto_leap` | ESTO | flow | 109 | 0 | 109 | 0 |
| `esto_leap` | LEAP | flow | 302 | 0 | 302 | 0 |
| `esto_leap_ninth` | ESTO | flow | 106 | 0 | 106 | 0 |
| `esto_leap_ninth` | LEAP | flow | 302 | 0 | 302 | 0 |
| `esto_leap_ninth` | NINTH | flow | 916 | 0 | 916 | 0 |
| `esto_extended_leap_ninth` | NINTH | product | 25,964 | 354 | 25,610 | 1,669 |
| `esto_leap` | ESTO | product | 2,507 | 0 | 2,507 | 0 |
| `esto_leap_ninth` | ESTO | product | 2,438 | 0 | 2,438 | 0 |
| `esto_leap_ninth` | NINTH | product | 25,964 | 354 | 25,610 | 1,669 |

The summary-row totals are 60,088 failures: 708 confirmed and 59,380
unconfirmed. These totals include overlapping comparison scopes and therefore
must not be interpreted as unique underlying source events.

## Failed, skipped, and unresolved validation

`common_esto_output_status.csv` records 10 passed rows, 16 failed rows, four
skipped rows, and three informational/diagnostic rows without a pass/fail
status.

The four product-hierarchy validations for ESTO, ESTO Extended, LEAP, and Ninth
were skipped because no eligible parent/child checks were found. They are not
reported as passes.

Flow-hierarchy validation failed as follows:

| Source | Checks | Grouped mismatches | Raw mismatch rows |
|---|---:|---:|---:|
| ESTO | 264 | 136 | 174 |
| ESTO_EXTENDED | 273 | 196 | 235 |
| LEAP | 68 | 18 | 736 |
| NINTH | 528 | 216 | 10,945 |

Open mapping and semantic review debt:

- 3,501 provisionally accepted generated relationships;
- eight within-axis many-to-many components;
- 29 ambiguous structural rows;
- 31 broad Common rows, with a maximum of 126 components;
- 30 unresolved partial-coverage rows;
- 472 non-zero unmapped LEAP branches;
- 31 highly recommended mapping candidates;
- 520,964 source rows in the bounded missing-Common-map review output;
- rollup QA states with incomplete or no contributors remain review findings;
- old general maintenance outputs pre-date this run and must not be presented
  as current Stage 0 results because there is no active mutating Stage 0.

Lineage is substantial but does not yet satisfy every requested field in one
atomic table. The Stage 3 atomic lineage contains scope, source system,
economy, scenario, year, canonical pair, Common row, aggregate metadata, and
value, but does not embed `run_id`, `unit`, or the original native source pair.
Native LEAP/Ninth lineage remains available in separate conversion lineage
files. This is an unresolved governance/contract gap.

## Dashboard run and publication QA

Dashboard batch identifier:
`all_economies_20260730_attempt2`. Rendering ran from approximately
`2026-07-30 04:49` to `05:16` Tokyo time. Every economy metadata file selects
mapping run `common_esto_20260729T175438145911Z`, timestamp
`2026-07-29T17:54:38.145911+00:00`, and matching Stage 3 status `completed`.

Rendered economies:

`01AUS`, `02BD`, `03CDA`, `04CHL`, `05PRC`, `06HKC`, `07INA`, `08JPN`,
`09ROK`, `10MAS`, `11MEX`, `12NZ`, `13PNG`, `14PE`, `15PHL`, `16RUS`,
`17SGP`, `18CT`, `19THA`, `20USA`, and `21VN`.

Every economy has the main dashboard, economy-scoped mapping diagnostics,
Plotly chart bundle, `chart_manifest.csv`, `page_assignment_summary.csv`,
`mapping_diagnostics_summary.csv`, and `dashboard_metadata.json`. A compact-code
cross-economy HTML scan found no foreign economy codes in another economy's
output. The chart pages use the pinned Plotly 2.35.2 CDN and page-linked chart
bundles.

Automated publication readiness passed all 21 outputs. Page-noise QA examined
125 pages and raised one warning: `02BD` “Other transformation” has 27 charts
and a 25.93% suppressed share. No publication-readiness failure was produced.
The pipeline-health report was regenerated after the final structural refresh
and reads all 16 configured artifacts. It retains numerical failures as
critical while showing the confirmed/unconfirmed split.

## Interventions and failures

- The first all-economy dashboard command failed immediately because its script
  did not add `REPO_ROOT` to `sys.path`. Commit `8ae8d42` fixed the notebook-safe
  import path; the second attempt completed all economies. The first attempt's
  stderr log is retained.
- Broad mapping tests initially exposed two implementation failures: LEAP
  full-path context detection and the shadow workflow's default root. Both were
  fixed before the production run.
- Current LEAP balance filenames did not match the older resolver patterns.
  Commit `682b2a5` added the two observed production filename forms before the
  full run.
- The full mapping run itself completed without stderr output or a
  memory-related failure.

## Primary evidence paths

Mapping:

- `config/outlook_mappings_single_axis.xlsx`
- `config/outlook_mappings_key_pairs_generated.xlsx`
- `config/outlook_mappings_master.xlsx`
- `config/outlook_mappings_generation_manifest.json`
- `results/common_esto/common_esto_output_contract.json`
- `results/common_esto/stage3_run_manifest.json`
- `results/common_esto/common_esto_comparison_fact.csv.gz`
- `results/common_esto/esto_component_to_common_row_lineage.csv.gz`
- `results/common_esto/qa_source_once_delivery.csv`
- `results/common_esto/common_esto_source_rows_missing_common_map.csv`
- `results/tree_structure/source_parent_anchor_validation_summary.csv`
- `results/tree_structure/source_parent_anchor_validation_full.csv.gz`
- `results/tree_structure/common_esto_validation_summary.csv`
- `results/common_esto/structural_artifacts/`

Dashboard:

- `C:\Users\Work\github\leap_dashboard\outputs\common_esto_dashboard\`
- per-economy main page:
  `<economy>\dashboards\index.html`
- per-economy diagnostics:
  `<economy>\dashboards\mapping_diagnostics.html`
- health report:
  `C:\Users\Work\github\leap_dashboard\outputs\prototypes\mapping_pipeline_health\mapping_pipeline_health.html`
- render summary:
  `C:\Users\Work\github\leap_dashboard\outputs\common_esto_dashboard\render_summary.csv`
- page-noise outputs:
  `C:\Users\Work\github\leap_dashboard\outputs\common_esto_dashboard\page_noise_summary.csv`
  and `page_noise_flags.csv`
- successful render log:
  `C:\Users\Work\github\leap_dashboard\outputs\common_esto_dashboard\all_economies_20260730_attempt2_stdout.log`
- first-attempt error log:
  `C:\Users\Work\github\leap_dashboard\outputs\common_esto_dashboard\all_economies_20260730_stderr.log`

All scoped source, workbook, and documentation changes were committed locally.
Generated run outputs remain uncommitted according to repository policy.
Nothing was pushed.
