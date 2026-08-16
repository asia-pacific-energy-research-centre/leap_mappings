#%%
"""Convert native source values onto the common ESTO axis (D4, overnight work
program W6, 2026-08-06/07).

One merge plus an aggregation - the whole point of building
``source_to_common_esto_map.csv`` (see
``build_source_to_common_esto_map.py``) is that a consumer never needs more
than this. **Deliberately minimal on purpose**: this module imports only
``pandas`` and reads a plain CSV. It must never import orchestration,
relevance/coverage QA, diagnostics, or output-writing modules from elsewhere
in ``mapping_tools`` - those stay where they are (see the design plan,
Phase C step 2: "Leave orchestration, relevance/coverage QA, diagnostics,
total checks and output writing where they are"). A caller that only wants
to convert values should never have to pull in the rest of the pipeline to
do it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP_PATH = REPO_ROOT / "results" / "common_esto" / "source_to_common_esto_map.csv"

VALUE_KEY_COLUMNS = ["economy", "scenario", "year"]
COMMON_AXIS_COLUMNS = ["common_row_id", "common_flow_label", "common_product_label"]


def load_source_to_common_esto_map(map_path: str | Path = DEFAULT_MAP_PATH) -> pd.DataFrame:
    """Read the published any-dataset -> common ESTO map."""
    return pd.read_csv(map_path)


def apply_source_to_common_esto_map(
    values: pd.DataFrame,
    source_to_common_map: pd.DataFrame,
    comparison_scope: str,
    source_system: str,
    value_column: str = "value",
    value_key_columns: list[str] = VALUE_KEY_COLUMNS,
) -> pd.DataFrame:
    """Convert one source's native values onto the common ESTO axis.

    ``values`` carries native rows with ``source_flow``, ``source_product``,
    *value_key_columns* (default ``economy``, ``scenario``, ``year``), and
    *value_column*. Returns one row per
    ``(comparison_scope, source_system, *value_key_columns, common_row_id,
    common_flow_label, common_product_label)``, summed - this is the
    aggregation half: several native source pairs can share one common row
    (many-to-one, never one-to-many at the common level - see
    ``build_source_to_common_esto_map``'s zero-fan-out guarantee), so their
    values must be added, not just merged.

    Native rows whose ``(source_flow, source_product)`` is not in the map for
    this scope (excluded structurally, or the source pair does not appear in
    this scope at all) are silently absent from the result rather than
    raising - the map's own coverage CSV
    (``source_to_common_esto_map_coverage.parquet``) is where that gap is listed
    explicitly; a converter re-raising it on every call would be noise, not
    a new finding.
    """
    scope_column = "scope" if "scope" in source_to_common_map.columns else "comparison_scope"
    system_column = "system" if "system" in source_to_common_map.columns else "source_system"
    scoped_map = source_to_common_map[
        (source_to_common_map[scope_column] == comparison_scope)
        & (source_to_common_map[system_column] == source_system)
    ][["source_flow", "source_product", *COMMON_AXIS_COLUMNS]].drop_duplicates()

    merged = values.merge(scoped_map, on=["source_flow", "source_product"], how="inner")
    converted = (
        merged.groupby([*value_key_columns, *COMMON_AXIS_COLUMNS], as_index=False)[value_column]
        .sum()
    )
    converted.insert(0, "source_system", source_system)
    converted.insert(0, "comparison_scope", comparison_scope)
    return converted


if __name__ == "__main__":
    # Worked example: convert a handful of synthetic LEAP rows. Flow/product
    # labels are real LEAP vocabulary (see source_to_common_esto_map.csv) so
    # this actually exercises the merge, not just the plumbing.
    example_values = pd.DataFrame(
        [
            {"source_flow": "Agriculture and fishing", "source_product": "Natural gas", "economy": "20_USA", "scenario": "Target", "year": 2022, "value": 100.0},
            {"source_flow": "Agriculture and fishing", "source_product": "Biogas", "economy": "20_USA", "scenario": "Target", "year": 2022, "value": 10.0},
        ]
    )
    example_map = load_source_to_common_esto_map()
    example_result = apply_source_to_common_esto_map(
        example_values, example_map, comparison_scope="esto_leap_ninth", source_system="LEAP"
    )
    print(example_result.to_string(index=False))
