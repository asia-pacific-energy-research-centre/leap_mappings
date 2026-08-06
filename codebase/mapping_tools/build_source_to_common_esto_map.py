#%%
"""Build the any-dataset -> common ESTO axis map (Phase C step 1, overnight
work program W6, 2026-08-06/07).

``leap_mappings/results/common_esto/esto_to_common_esto_map.csv`` maps ESTO
components only. For LEAP and the 9th there is no equivalent today: a
consumer must read the pre-converted fact table, or compose the
``*_source_to_esto_component_lineage.csv.gz`` files (built from *observed*
data) with the ESTO map. This script builds the missing piece structurally
instead, from ``energy_balance_relationships.csv`` (18,020 rows built from
the mapping workbooks, not from what any one economy happened to report)
composed with ``esto_to_common_esto_map.csv``, so the map is a static
artifact good for every economy rather than a per-run computation.

Built **per comparison scope, participating sources only**: a scope's
participating sources are read off its name (``esto_leap`` / ``esto_leap_ninth``
etc. always include LEAP; ``*_ninth`` scopes also include NINTH). ESTO is not
included here - it already has its own dedicated, ESTO-only map.

**Zero fan-out is the mapping system's central design rule, not a property
of the current data that might change** (see
``docs/prompts/measure_aware_dashboard_and_mapping_inversion_plan.md``,
"Do not split a source aggregate unless there is an explicit allocation
method"). One structural source pair must resolve to exactly one common row
within a scope. This script asserts that while generating and fails loudly
if it does not hold - a fan-out here is a mapping-system bug to fix upstream,
never a case for this script (or any consumer) to paper over with allocation.

Structural links with no common row in a scope (the W1 finding, 2026-08-06/07:
3,347 unmapped LEAP structural links in esto_leap_ninth, 388 of which carry
real nonzero LEAP values - see
``leap_dashboard/outputs/overnight_20260806/w1_finding_unmapped_leap_links.md``)
are excluded from the map and listed explicitly in the coverage CSV this
script also writes, rather than silently dropped.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]

RELATIONSHIPS_PATH = REPO_ROOT / "results" / "mapping_relationships" / "energy_balance_relationships.csv"
ESTO_TO_COMMON_MAP_PATH = REPO_ROOT / "results" / "common_esto" / "esto_to_common_esto_map.csv"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "results" / "common_esto" / "source_to_common_esto_map.csv"
DEFAULT_COVERAGE_OUTPUT_PATH = REPO_ROOT / "results" / "common_esto" / "source_to_common_esto_map_coverage.csv"

#: Human-readable labels first (D3: "a reader must never have to join another
#: file to understand a row"); common_row_id last - it is a join key for code,
#: not something a non-coder reader needs to look at row by row.
MAP_COLUMNS = [
    "comparison_scope",
    "source_system",
    "source_flow",
    "source_product",
    "common_flow_label",
    "common_product_label",
    "common_row_id",
]

#: D3 sort order: "source system, then source flow, then source product" -
#: comparison_scope groups first since scopes are separate contexts a reader
#: would otherwise have to filter apart by eye.
MAP_SORT_COLUMNS = ["comparison_scope", "source_system", "source_flow", "source_product"]


class FanOutError(ValueError):
    """Raised when a structural source pair resolves to more than one common row."""


def _participating_source_systems(comparison_scope: str) -> set[str]:
    """Read a scope's participating sources off its own name.

    Every comparison scope in ``esto_to_common_esto_map.csv`` is an
    ``esto_...`` scope (ESTO is always the target vocabulary), so only the
    non-ESTO participants need naming: ``leap`` is in every scope name seen
    today; ``ninth`` names the 3-way scopes. Raises rather than silently
    including nothing if a future scope name doesn't say either, since that
    would build an empty (not merely narrow) slice of the map without
    complaint.
    """
    lowered = comparison_scope.casefold()
    sources = set()
    if "leap" in lowered:
        sources.add("LEAP")
    if "ninth" in lowered:
        sources.add("NINTH")
    if not sources:
        raise ValueError(
            f"Comparison scope {comparison_scope!r} names no known participating "
            "source system (expected 'leap' and/or 'ninth' in the name)."
        )
    return sources


def build_source_to_common_esto_map(
    relationships_path: Path = RELATIONSHIPS_PATH,
    esto_to_common_map_path: Path = ESTO_TO_COMMON_MAP_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the any-dataset -> common ESTO map and its coverage report.

    Returns ``(source_to_common_esto_map, coverage)``. Raises
    :class:`FanOutError` if any structural source pair resolves to more than
    one common row within a scope.
    """
    relationships = pd.read_csv(relationships_path).drop_duplicates(subset=["relationship_id"])
    relationships = relationships[relationships["source_system"] != "ESTO"]

    esto_to_common = pd.read_csv(esto_to_common_map_path)
    scopes = sorted(esto_to_common["comparison_scope"].astype(str).unique())

    map_rows: list[pd.DataFrame] = []
    coverage_rows: list[pd.DataFrame] = []

    for scope in scopes:
        participating = _participating_source_systems(scope)
        scope_relationships = relationships[relationships["source_system"].isin(participating)].copy()
        scope_map = esto_to_common[esto_to_common["comparison_scope"] == scope][
            ["component_esto_flow", "component_esto_product", "common_row_id", "common_flow_label", "common_product_label"]
        ].drop_duplicates()

        merged = scope_relationships.merge(
            scope_map,
            left_on=["target_flow", "target_product"],
            right_on=["component_esto_flow", "component_esto_product"],
            how="left",
        )

        mapped = merged[merged["common_row_id"].notna()].copy()
        mapped["comparison_scope"] = scope
        map_rows.append(mapped[MAP_COLUMNS].drop_duplicates())

        unmapped = merged[merged["common_row_id"].isna()][
            ["relationship_id", "source_system", "source_flow", "source_product", "target_flow", "target_product"]
        ].drop_duplicates(subset=["relationship_id"]).copy()
        unmapped["comparison_scope"] = scope
        unmapped["reason"] = "no common row in esto_to_common_esto_map for this scope"
        coverage_rows.append(unmapped)

        # Zero fan-out assertion: one structural source pair -> one common row,
        # within this scope. This is the mapping system's central design rule
        # (see module docstring), not a property of today's data - fail loudly
        # if it is ever violated rather than silently allocating.
        fan_out = (
            mapped.groupby(["source_system", "source_flow", "source_product"])["common_row_id"]
            .nunique()
        )
        offenders = fan_out[fan_out > 1]
        if not offenders.empty:
            raise FanOutError(
                f"Fan-out at the common level in scope {scope!r}: "
                f"{len(offenders)} source pair(s) resolve to more than one common row. "
                f"First offenders: {offenders.head(5).to_dict()}"
            )

    source_to_common_map = pd.concat(map_rows, ignore_index=True) if map_rows else pd.DataFrame(columns=MAP_COLUMNS)
    coverage = pd.concat(coverage_rows, ignore_index=True) if coverage_rows else pd.DataFrame()
    source_to_common_map = (
        source_to_common_map.sort_values(MAP_SORT_COLUMNS).reset_index(drop=True)[MAP_COLUMNS]
    )
    return source_to_common_map, coverage


def build_and_write_source_to_common_esto_map(
    output_path: Path = DEFAULT_OUTPUT_PATH,
    coverage_output_path: Path = DEFAULT_COVERAGE_OUTPUT_PATH,
) -> pd.DataFrame:
    """Build the map and coverage report, write both, and return the map."""
    source_to_common_map, coverage = build_source_to_common_esto_map()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_to_common_map.to_csv(output_path, index=False)
    coverage_output_path = Path(coverage_output_path)
    coverage.to_csv(coverage_output_path, index=False)
    print(
        f"source_to_common_esto_map: {len(source_to_common_map):,} rows -> {output_path}\n"
        f"coverage (excluded, listed not dropped): {len(coverage):,} rows -> {coverage_output_path}\n"
        "Zero fan-out assertion: PASSED for every comparison scope."
    )
    return source_to_common_map


if __name__ == "__main__":
    build_and_write_source_to_common_esto_map()
