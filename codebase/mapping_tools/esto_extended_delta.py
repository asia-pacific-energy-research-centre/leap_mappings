#%%
"""Exact row-overlay helpers for representing ESTO Extended from ESTO base rows."""

from __future__ import annotations

from typing import Any

import pandas as pd


BASE_SOURCE_SYSTEM = "ESTO"
EXTENDED_SOURCE_SYSTEM = "ESTO_EXTENDED"
DELTA_OPERATION_COLUMN = "delta_operation"
DELETE_OPERATION = "delete"
UPSERT_OPERATION = "upsert"
REQUIRED_EXACT_ROW_COLUMNS = [
    "source_system",
    "economy",
    "scenario",
    "year",
    "esto_flow",
    "esto_product",
    "value",
]


def _require_exact_row_schema(frame: pd.DataFrame, table_name: str) -> None:
    """Require the finalized long-format schema consumed by Stage 3."""
    missing = [
        column for column in REQUIRED_EXACT_ROW_COLUMNS
        if column not in frame.columns
    ]
    if missing:
        raise ValueError(f"{table_name} is missing required exact-row columns: {missing}")


def _row_identity_columns(columns: list[str]) -> list[str]:
    """Use every non-value field except source identity as the row identity."""
    return [
        column for column in columns
        if column not in {"source_system", "value"}
    ]


def _key_value(value: object) -> tuple[str, object]:
    """Make nulls and scalar types stable inside dictionary keys."""
    if pd.isna(value):
        return ("null", "")
    return (type(value).__name__, value)


def _row_key(row: dict[str, object], identity_columns: list[str]) -> tuple[tuple[str, object], ...]:
    return tuple(_key_value(row[column]) for column in identity_columns)


def _rows_by_key(
    frame: pd.DataFrame,
    identity_columns: list[str],
    table_name: str,
) -> dict[tuple[tuple[str, object], ...], dict[str, object]]:
    """Index rows and reject ambiguous identities before creating a delta."""
    indexed: dict[tuple[tuple[str, object], ...], dict[str, object]] = {}
    for row in frame.to_dict("records"):
        key = _row_key(row, identity_columns)
        if key in indexed:
            example = {
                column: row[column]
                for column in identity_columns
            }
            raise ValueError(f"{table_name} contains a duplicate row identity: {example}")
        indexed[key] = row
    return indexed


def _values_equal(left: object, right: object) -> bool:
    if pd.isna(left) and pd.isna(right):
        return True
    return bool(left == right)


def _validate_source_identity(
    frame: pd.DataFrame,
    expected_source_system: str,
    table_name: str,
) -> None:
    invalid = (
        frame["source_system"].isna()
        | frame["source_system"].astype(str).ne(expected_source_system)
    )
    if invalid.any():
        observed = sorted(set(frame["source_system"].dropna().astype(str)))
        raise ValueError(
            f"{table_name} must contain only source_system={expected_source_system!r}; "
            f"observed {observed}"
        )


def build_esto_extended_exact_row_delta(
    esto_base_rows: pd.DataFrame,
    esto_extended_rows: pd.DataFrame,
) -> pd.DataFrame:
    """Build an exact add/change/delete overlay from finalized exact-row artifacts.

    Base rows are first relabelled from ``ESTO`` to ``ESTO_EXTENDED``. Unchanged
    relabelled rows are inherited and omitted from the delta. New or value-
    changed rows are ``upsert`` records; base rows absent from Extended are
    ``delete`` records. This handles former ESTO leaves that become subtotals
    after Extended introduces children.
    """
    _require_exact_row_schema(esto_base_rows, "ESTO base rows")
    _require_exact_row_schema(esto_extended_rows, "ESTO Extended rows")
    if list(esto_base_rows.columns) != list(esto_extended_rows.columns):
        raise ValueError(
            "ESTO base and Extended exact-row schemas must have identical ordered columns."
        )
    _validate_source_identity(esto_base_rows, BASE_SOURCE_SYSTEM, "ESTO base rows")
    _validate_source_identity(
        esto_extended_rows,
        EXTENDED_SOURCE_SYSTEM,
        "ESTO Extended rows",
    )

    columns = esto_extended_rows.columns.tolist()
    identity_columns = _row_identity_columns(columns)
    inherited = esto_base_rows.copy()
    inherited["source_system"] = EXTENDED_SOURCE_SYSTEM
    base_by_key = _rows_by_key(inherited, identity_columns, "ESTO base rows")
    extended_by_key = _rows_by_key(
        esto_extended_rows,
        identity_columns,
        "ESTO Extended rows",
    )

    delta_rows: list[dict[str, Any]] = []
    for key in sorted(set(base_by_key) | set(extended_by_key), key=repr):
        base_row = base_by_key.get(key)
        extended_row = extended_by_key.get(key)
        if extended_row is None:
            delta_rows.append({
                DELTA_OPERATION_COLUMN: DELETE_OPERATION,
                **base_row,
            })
        elif base_row is None or not _values_equal(base_row["value"], extended_row["value"]):
            delta_rows.append({
                DELTA_OPERATION_COLUMN: UPSERT_OPERATION,
                **extended_row,
            })
    return pd.DataFrame(delta_rows, columns=[DELTA_OPERATION_COLUMN, *columns])


def reconstruct_esto_extended_exact_rows(
    esto_base_rows: pd.DataFrame,
    delta_rows: pd.DataFrame,
) -> pd.DataFrame:
    """Apply an exact-row delta to ESTO base rows and return ESTO Extended rows."""
    _require_exact_row_schema(esto_base_rows, "ESTO base rows")
    _validate_source_identity(esto_base_rows, BASE_SOURCE_SYSTEM, "ESTO base rows")
    expected_delta_columns = [DELTA_OPERATION_COLUMN, *esto_base_rows.columns.tolist()]
    if list(delta_rows.columns) != expected_delta_columns:
        raise ValueError(
            "ESTO Extended delta schema must be delta_operation followed by the "
            "ordered base exact-row columns."
        )
    _validate_source_identity(
        delta_rows,
        EXTENDED_SOURCE_SYSTEM,
        "ESTO Extended delta",
    )

    columns = esto_base_rows.columns.tolist()
    identity_columns = _row_identity_columns(columns)
    reconstructed = esto_base_rows.copy()
    reconstructed["source_system"] = EXTENDED_SOURCE_SYSTEM
    rows_by_key = _rows_by_key(reconstructed, identity_columns, "ESTO base rows")
    delta_by_key = _rows_by_key(
        delta_rows.drop(columns=DELTA_OPERATION_COLUMN),
        identity_columns,
        "ESTO Extended delta",
    )
    operations_by_key = {
        _row_key(row, identity_columns): str(row[DELTA_OPERATION_COLUMN])
        for row in delta_rows.to_dict("records")
    }

    for key, row in delta_by_key.items():
        operation = operations_by_key[key]
        if operation == DELETE_OPERATION:
            if key not in rows_by_key:
                raise ValueError("ESTO Extended delta cannot delete a row absent from the base.")
            del rows_by_key[key]
        elif operation == UPSERT_OPERATION:
            row["source_system"] = EXTENDED_SOURCE_SYSTEM
            rows_by_key[key] = row
        else:
            raise ValueError(f"Unsupported ESTO Extended delta operation: {operation!r}")

    ordered_rows = [rows_by_key[key] for key in sorted(rows_by_key, key=repr)]
    return pd.DataFrame(ordered_rows, columns=columns)


#%%
