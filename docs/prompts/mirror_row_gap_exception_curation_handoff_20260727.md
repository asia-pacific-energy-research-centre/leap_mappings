# Handoff: curating source_mismatch_allowed exceptions — paused 2026-07-27

**Status: paused, not abandoned.** The mechanism this work depends on is done, tested, and safely
committed to master. What's paused is populating it with fresh, currently-valid exception rows —
blocked by unrelated, in-progress concurrent work on this same repo (see "Why this is paused"
below). Read this in full before resuming; skipping to the "how to resume" steps risks re-deriving
context that's already here, or resuming before the actual blocker has cleared.

## Why this work matters

The anchor validator (`codebase/mapping_tools/source_parent_anchor_validation.py`) checks whether
NINTH's own reported totals for a (sector, fuel) combination are internally consistent. Some
failures are genuine bugs in this repo's mapping/pipeline code — worth fixing. Others are NINTH's
own source data disagreeing with itself (the same real value reported at two different depths of
its own hierarchy) — not fixable in this repo at all, since there's no reliable way to tell from
the data alone which of the two conflicting numbers is "right."

**Four separate sessions tried to teach the validator to tell these two cases apart
automatically, and every attempt failed** — see
`docs/prompts/anchor_validator_fixes_findings_20260723.md`'s "mirror-row gap" section for the full
trace. Automatic detection either missed the real target cases or produced false positives on
already-correct rows. The conclusion, reached the hard way across those four sessions: there may be
no safe *automatic* signal for this at all.

Given that, the design (see the `mirror-row-gap-flag-propagation-design` memory) is a **curated,
human-reviewed exception list** instead: a spreadsheet sheet where a person (or a script whose
output a person reviews before it reaches the shared file) records "I checked this specific
mismatch directly against NINTH's raw data — it's genuinely NINTH's own data being inconsistent,
not a bug." This is a fundamentally different, safer shape than the four failed attempts: **a false
positive here gets caught by a human before it reaches the shared workbook**, instead of being
silently embedded in validator logic with no one checking its output.

## What's done and safely in master (commits `7db1822`, `cf740de`, `6bf8f69`)

1. **A real, unrelated bug fix** (`7db1822`): `target_dataset_share` allocation was silently
   falling back to a flat equal-share split because its basis lookup excluded ESTO's `is_subtotal`
   rows — recovered the real basis from the raw ESTO source, scoped narrowly. Resolved the original
   6-row `14.03 Manufacturing` coal-products residual that kicked off this whole investigation.
2. **The exception mechanism** (`cf740de`):
   - `config/mapping_issue_exception_sets.xlsx` gained a `source_mismatch_allowed` sheet:
     `enabled | source_system | validation_axis | parent_code | other_axis_value | economy |
     parent_value | notes`, same `*`-prefix-matching convention as this repo's 13 other exception
     families.
   - `codebase/mapping_issue_exceptions.py`'s `matching_exception_row`/`split_allowed_rows` gained
     an opt-in `numeric_tolerance_columns` parameter (default empty — zero behavior change for the
     13 existing sheets). Used here to require `parent_value` to match within tolerance, not just
     the code/label — **this is the safeguard that makes stale curation self-correcting**: if the
     underlying data changes (a NINTH data fix, or an unrelated new bug landing on the same
     code/label key), the exception stops matching automatically instead of silently continuing to
     hide something new.
   - `validate_source_parent_anchors` (`source_parent_anchor_validation.py`) follows an
     "augment, don't hide" pattern: a matched row's `status`/`reason` are left exactly as computed;
     `known_data_quality_exception` (bool) and `data_quality_exception_notes` are added alongside.
     Nothing currently reading `status` breaks.
   - 10 regression tests covering both the matching logic and the augmentation function.
3. **A first curation pass** (`6bf8f69`): 455 product-axis rows (`08_gas`, `16_others`), each
   individually verified against `data/merged_file_energy_ALL_20251106.csv` directly — not just
   trusting the validator's own reason string. **This pass is now stale** (see below) but the
   commit itself is harmless to leave in place; stale exceptions simply stop matching, they don't
   cause harm.

## Why this is paused

A second curation pass (adding flow-axis coverage: `09_06_gas_processing_plants`,
`09_total_transformation_sector`, `14_industry_sector/14_03_manufacturing`,
`10_losses_and_own_use/10_01_own_use`, `15_transport_sector` — 736 more rows) was done on
2026-07-24 but never committed before the working environment it was done in was torn down. Nothing
about that pass was wrong — re-verifying it from scratch against fresher data (see next) is what
actually surfaced the real blocker.

**Re-running the same verification against today's (2026-07-27) regenerated
`results/tree_structure/source_parent_anchor_validation.csv` found something new: literally
0 of 810 product-axis candidates could be confirmed**, where the 2026-07-24 run had confirmed
about half. Spot-checking one candidate row directly against raw NINTH data showed it was **already
fully self-consistent at every level** — meaning the anchor validator is now failing it for some
other reason entirely, not a NINTH self-inconsistency. Checking the broader population confirmed
this wasn't a fluke: **94% of the 810 candidates (`frontier_row_count == 0`) have zero registered
Common ESTO frontier coverage at all**, not just a numeric mismatch against real coverage. That's a
structurally different failure mode than what this whole exception-curation effort was built to
handle.

This traces to **your own other, concurrently-running Codex session** — confirmed by checking one
of the intervening commits (`632ea35`, "normalize anchor validation source systems") directly:
same author (Finn Maunsell), not a third party. Between 2026-07-24 and 2026-07-27, that session
landed dozens of commits touching exactly the files this work depends on (`build_dataset_tree_
structure.py`, `source_parent_anchor_validation.py`, Common ESTO structure-building) — memory
optimization for the anchor validator (see its own scope doc,
`docs/prompts/investigate_anchor_validator_memory_prompt.md`) plus what look like in-progress
"ESTO Extended" mapping-scope changes (commit messages: "align mapped component diagnostics with
resolver," "combine ESTO and Extended mapping scopes," "make Extended hierarchy rollup-driven").

**This is not a bug for this thread to fix.** Chasing the zero-frontier-coverage issue now would
mean auditing a large, unfamiliar, actively-moving body of work from a different session — risking
either duplicate effort or fighting a target that resolves itself once that session's work settles.
The right move is to wait.

## How to resume

1. **Confirm the other session has settled.** Check recent commit activity on `master` for
   continued "codex: ..." commits touching `source_parent_anchor_validation.py` /
   `build_dataset_tree_structure.py` / `build_common_esto_structure.py`. If commits are still
   landing frequently, it's too early.
2. **Regenerate `results/tree_structure/source_parent_anchor_validation.csv` fresh** (full Stage 3
   pipeline run, or at minimum the anchor-validation step) once things have settled.
3. **Run `codebase/mapping_tools/verify_ninth_mirror_row_candidates.py`** — the exact verification
   logic from this session, now committed to the repo (not lost this time):
   ```bash
   python codebase/mapping_tools/verify_ninth_mirror_row_candidates.py \
       --out-dir results/mirror_row_gap_verification
   ```
   It prints the `frontier_row_count == 0` share among candidates before running anything — **if
   that's still a majority, stop and investigate the coverage gap itself before curating any
   exceptions against it** (a curated exception can't fix a missing frontier registration; it would
   just hide the fact that nothing is being compared at all).
4. **Spot-check a sample of the confirmed rows by hand** against
   `data/merged_file_energy_ALL_20251106.csv` directly before trusting the CSV output — this
   session caught a real bug in the script's first version this way (it was treating NINTH's
   routine `0.0` placeholder rows as contradicting evidence, and "confirmed" all 956 candidates
   instead of the real ~455). Don't skip this step because the script has been used before; rerun
   it against fresh data and re-verify.
5. **Write the confirmed rows into `config/mapping_issue_exception_sets.xlsx`'s
   `source_mismatch_allowed` sheet.** Schema: `enabled, source_system, validation_axis, parent_code,
   other_axis_value, economy, parent_value, notes`. The stale 2026-07-24 rows (455, already in
   master) can be left in place (harmless — they just won't match) or replaced; either is fine,
   note whichever choice is made in the commit message.
6. **Verify end-to-end** before committing:
   ```python
   from codebase.mapping_tools.source_parent_anchor_validation import _augment_with_data_quality_exceptions
   import pandas as pd
   df = pd.read_csv("results/tree_structure/source_parent_anchor_validation.csv", dtype=object)
   augmented = _augment_with_data_quality_exceptions(df)
   assert (augmented["status"] == df["status"]).all()  # augment, don't hide
   print((augmented["known_data_quality_exception"] == True).sum(), "rows flagged")
   ```
7. **Run the full test suite** (`python -m pytest tests/ -q`) — expect the same 2 pre-existing,
   unrelated failures (missing `pyarrow`; an Excel-lock-file test quirk) and nothing new.
8. **Commit and push.**

## What's NOT part of this thread

The `14_industry_sector`/`12_solar` case investigated earlier this session turned out to be the
same mirror-row shape as the other families (confirmed by hand-tracing it against raw NINTH data,
not a distinct pipeline bug as first assumed) — it's included in the flow-axis verification script
above, not a separate open item.

The zero-frontier-coverage issue found on 2026-07-27 (94% of candidates) is a real, currently open
question but belongs to whoever is doing the concurrent Common ESTO structure-building work, not to
this exception-curation thread. If it's still unresolved when this thread resumes, flag it
separately rather than trying to route around it here.
