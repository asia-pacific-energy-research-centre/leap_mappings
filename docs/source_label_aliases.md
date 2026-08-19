# Source label aliases

`config/leap_export_label_aliases.csv` is the single reviewed source-label
standardisation layer for LEAP balance exports.  It resolves spelling,
capitalisation, and known export-label variants before source-to-target mapping
relationships are applied.

This table is not a mapping table.  Mapping workbooks contain only real source
and target relationships; they must not carry duplicate rows merely to support
two spellings of the same LEAP label.

Each enabled row records:

- `alias_scope`: the parser or extractor that uses the rule;
- `label_axis`: `flow` or `fuel`;
- `raw_label`: the exact source spelling;
- `canonical_label`: the source label used in mapping relationships; and
- `rationale`: why the alias is needed.

Before adding an alias, check whether the raw label occurs in current exports,
whether the labels are semantically identical, and whether the intended
canonical label exists on both mapping axes.  Do not use this table to change
flow/product meaning, allocation, hierarchy, or display labels.
