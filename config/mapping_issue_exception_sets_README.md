# `mapping_issue_exception_sets.xlsx`

This workbook is a reviewed QA decision layer. It does not create mappings,
repair source data, or make failed numerical checks pass. It tells a named
diagnostic how to record a finding that a reviewer has judged intentional,
acceptable, or outside the modelled scope.

## Active sheets

| Sheet | Purpose |
| --- | --- |
| `subtotal_mismatch_allowed` | Reviewed cases where a source and mapped pair differ in subtotal status. |
| `missing_common_map_ignored` | ESTO flows intentionally excluded from missing Common ESTO map diagnostics. Supports `*` prefix patterns. |
| `subtotal_label_exceptions` | Older subtotal-label inference decisions. |
| `display_names_exceptions` | Exact LEAP display-name cases excluded from display-name QA. |
| `leap_dup_source_allowed` | Reviewed duplicate LEAP source-pair findings. |
| `leap_dup_target_allowed` | Reviewed duplicate LEAP target-pair findings. |
| `subtotal_label_overrides` | Explicit subtotal truth used by subtotal contract/review workflows. |
| `unmodelled_source_ignored` | Sectors and fuels intentionally outside the modelled source scope. |
| `source_mismatch_allowed` | Active confirmations of raw ESTO/NINTH/LEAP source hierarchy contradictions attached to anchor diagnostics. |

## History and legacy sheets

`source_mismatch_archive` is not an allowlist. It preserves older review
records for provenance, including records that were superseded, migrated, or
were not specific enough for safe operational matching. The validator never
uses it to annotate current results. Do not add new active exceptions there.

The remaining legacy-only sheets are retained for archived maintenance
workflows and should not receive new active-pipeline findings:

- `many_to_many_allowed`
- `crosswalk_allowed`
- `leap_source_presence_allowed`
- `unmapped_esto_nonzero_allowed`
- `unmapped_ninth_nonzero_allowed`

## `source_mismatch_allowed` rules

Required operational fields are:

```text
enabled, review_status, exception_id, issue_class, source_system,
validation_axis, parent_code, other_axis_value, economy, scenario, year,
parent_value, notes
```

Use `review_status = confirmed`, a unique `exception_id`, and a nonblank
`issue_class`. The source identity fields remain exact:
`source_system`, `validation_axis`, `parent_code`, and `other_axis_value`.
For an economy-specific exception, `parent_value` must also match apart from
negligible floating-point serialization noise. When `economy = all`, the
stored value is review evidence from the APEC finding rather than a match key:
the exception applies to the same structural signature in every economy even
though no individual economy is expected to equal the APEC aggregate.
If an economy-specific row and an `economy = all` row both match, the
economy-specific review takes precedence. Duplicate matches at the same
specificity remain ambiguous and fail closed.

To avoid repeating a confirmed issue, the literal `all` may be used in
`economy`, `scenario`, and/or `year`. For example:

```text
economy = 05PRC    scenario = all    year = all
```

This means the same source issue applies to every scenario and checked year
for economy `05PRC`. It does not permit `all` in `parent_code`,
`other_axis_value`, or `parent_value`, and prefix wildcards are not supported
in this sheet. Keep `parent_value` populated as provenance even when
`economy = all`.

Confirmed exceptions annotate evidence only. A failed anchor remains failed
in the numerical results; the diagnostic adds the confirmation metadata and
notes beside it.
