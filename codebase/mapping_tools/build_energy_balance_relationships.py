#%%
"""
Build long energy-balance relationship rows.

This workflow reads the maintained mapping workbooks, preserves every source
row, duplicates each underlying relationship by use case, and writes conversion
QA outputs without modifying source workbooks.
"""

#%%
import hashlib
import re
from pathlib import Path
from typing import Any

import pandas as pd

from codebase.mapping_issue_exceptions import EXCEPTION_WORKBOOK_PATH, split_allowed_rows
from codebase.utilities.outlook_mappings_filters import filter_used_in_leap_initialisation

#%%
USE_CASES = [
    "leap_to_esto_balance_conversion",
    "ninth_to_esto_balance_conversion",
    "leap_to_ninth_comparison",
    "ninth_to_leap_initialisation",
    "mapping_review",
]

SHEET_CONFIGS = [
    {
        "sheet_name": "leap_combined_esto",
        "source_system": "LEAP",
        "target_system": "ESTO",
        "source_flow_candidates": ["leap_sector_name_full_path"],
        "source_product_candidates": ["raw_leap_fuel_name"],
        "target_flow_candidates": ["esto_flow"],
        "target_product_candidates": ["esto_product"],
        "use_cases": ["leap_to_esto_balance_conversion", "mapping_review"],
    },
    {
        "sheet_name": "ninth_pairs_to_esto_pairs",
        "source_system": "NINTH",
        "target_system": "ESTO",
        "source_flow_candidates": ["9th_sector", "ninth_sector"],
        "source_product_candidates": ["9th_fuel", "ninth_fuel"],
        "target_flow_candidates": ["esto_flow"],
        "target_product_candidates": ["esto_product"],
        "use_cases": ["ninth_to_esto_balance_conversion", "mapping_review"],
    },
    {
        "sheet_name": "leap_combined_ninth",
        "source_system": "LEAP",
        "target_system": "NINTH",
        "source_flow_candidates": ["leap_sector_name_full_path"],
        "source_product_candidates": ["raw_leap_fuel_name"],
        "target_flow_candidates": ["ninth_sector"],
        "target_product_candidates": ["ninth_fuel"],
        "use_cases": ["leap_to_ninth_comparison", "mapping_review"],
    },
]

RELATIONSHIP_COLUMNS = [
    "relationship_id",
    "relationship_key",
    "use_case",
    "include_in_use_case",
    "source_system",
    "source_flow",
    "source_product",
    "source_sector_path",
    "source_fuel",
    "source_sector_code",
    "source_product_code",
    "target_system",
    "target_flow",
    "target_product",
    "target_sector_code",
    "target_product_code",
    "esto_pair_is_subtotal",
    "cardinality",
    "relationship_type",
    "relationship_level",
    "allocation_method",
    "allocation_source",
    "allocation_share",
    "relationship_status",
    "relationship_source",
    "exclude_reason",
    "notes",
    "review_required",
    "review_flags",
    "remove_row",
    "is_rollup_derived",
    "source_mapping_file",
    "source_sheet",
    "source_row_number",
]

ESTO_OVERRIDES_COLUMNS = [
    "comparison_scope",
    "override_group_id",
    "component_esto_flow",
    "component_esto_product",
    "preferred_common_flow_label",
    "preferred_common_product_label",
    "override_reason",
    "notes",
]

COLUMN_CANDIDATES = {
    "source_sector_path": [
        "leap_sector_name_full_path",
        "leap_flow",
        "leap_sector",
        "leap_sector_path",
        "leap_branch",
        "leap_branch_path",
    ],
    "source_fuel": [
        "raw_leap_fuel_name",
        "leap_product",
        "leap_fuel",
        "leap_product_name",
        "leap_fuel_name",
    ],
    "target_flow": [
        "esto_flow",
        "esto_sector",
        "esto_sector_name",
        "esto_flow_name",
        "flow",
    ],
    "target_product": [
        "esto_product",
        "esto_fuel",
        "esto_product_name",
        "esto_fuel_name",
        "product",
    ],
    "source_sector_code": [
        "leap_flow_code",
        "leap_sector_code",
        "source_sector_code",
    ],
    "source_product_code": [
        "leap_product_code",
        "leap_fuel_code",
        "source_product_code",
        "source_fuel_code",
    ],
    "target_sector_code": [
        "esto_flow_code",
        "esto_sector_code",
        "target_sector_code",
    ],
    "target_product_code": [
        "esto_product_code",
        "esto_fuel_code",
        "target_product_code",
        "target_fuel_code",
    ],
    "remove_row": [
        "remove_row",
        "remove",
        "inactive",
        "drop_row",
    ],
    "esto_pair_is_subtotal": [
        "esto_pair_is_subtotal",
        "ninth_pair_is_subtotal",
    ],
    "cardinality": [
        "cardinality",
        "relationship_cardinality",
        "pair_mapping_cardinality",
    ],
    "notes": [
        "notes",
        "note",
        "comments",
        "comment",
        "remove_row_reason",
    ],
}

QA_FILENAMES = {
    "leap_sources_without_esto_target": "leap_sources_without_esto_target.csv",
    "esto_targets_without_leap_source": "esto_targets_without_leap_source.csv",
    "missing_dataset_pairs_by_use_case": "missing_dataset_pairs_by_use_case.csv",
    "not_considered_esto_rows": "not_considered_esto_rows.csv",
    "leap_to_esto_duplicate_source_pairs": "leap_to_esto_duplicate_source_pairs.csv",
    "leap_to_esto_duplicate_source_pairs_allowed_matched": "leap_to_esto_duplicate_source_pairs_allowed_matched.csv",
    "leap_to_esto_duplicate_target_pairs": "leap_to_esto_duplicate_target_pairs.csv",
    "leap_to_esto_duplicate_target_pairs_allowed_matched": "leap_to_esto_duplicate_target_pairs_allowed_matched.csv",
    "one_to_many_mappings_without_allocation_or_combined_target": "one_to_many_mappings_without_allocation_or_combined_target.csv",
    "leap_to_esto_parent_child_risks": "leap_to_esto_parent_child_risks.csv",
    "leap_to_esto_coverage_summary": "leap_to_esto_coverage_summary.csv",
    "leap_to_esto_excluded_source_audit": "leap_to_esto_excluded_source_audit.csv",
}

QA_SHEET_NAMES = {
    "missing_dataset_pairs_by_use_case": "missing_pairs_by_use_case",
    "leap_to_esto_duplicate_source_pairs_allowed_matched": "duplicate_source_allowed",
    "leap_to_esto_duplicate_target_pairs_allowed_matched": "duplicate_target_allowed",
}

DUPLICATE_SOURCE_EXCEPTION_SHEET = "leap_dup_source_allowed"
DUPLICATE_TARGET_EXCEPTION_SHEET = "leap_dup_target_allowed"

CATALOGUE_COLUMNS = [
    "relationship_id",
    "source_system",
    "source_flow",
    "source_product",
    "target_system",
    "target_flow",
    "target_product",
    "relationship_type",
    "relationship_level",
    "cardinality",
    "allocation_method",
    "included_use_cases",
    "excluded_use_cases",
    "all_use_cases",
    "used_for_leap_to_esto_balance_conversion",
    "used_for_ninth_to_esto_balance_conversion",
    "used_for_leap_to_ninth_comparison",
    "used_for_ninth_to_leap_initialisation",
    "any_excluded",
    "review_required",
    "review_flags",
    "notes",
]

COMPACT_CATALOGUE_COLUMNS = [
    "ninth_sector",
    "ninth_fuel",
    "esto_flow",
    "esto_product",
    "leap_flow",
    "leap_product",
]

COVERAGE_EXCLUSION_COLUMNS = [
    "use_case",
    "comparison_scope",
    "source_system",
    "target_system",
    "target_flow",
    "target_product",
    "exclusion_reason",
    "notes",
]

ESTO_COMBINED_ROW_COLUMNS = [
    "combined_row_id",
    "combined_row_name",
    "use_case",
    "target_system",
    "target_flow",
    "target_product",
    "component_system",
    "component_flow",
    "component_product",
    "component_sign",
    "notes",
]

#%%
def _find_repo_root(start_path: Path) -> Path:
    """Find the leap_mappings repo root from a nested workflow path."""
    for candidate in [start_path, *start_path.parents]:
        if (candidate / "AGENTS.md").exists() and (candidate / "config" / "outlook_mappings_master.xlsx").exists():
            return candidate
    raise FileNotFoundError(f"Could not find repo root above: {start_path}")


def clean_column_name(value: Any) -> str:
    """Normalise a source column name for robust matching."""
    text = "" if value is None else str(value)
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def first_existing_column(columns: list[str], candidates: list[str]) -> str | None:
    """Return the first source column matching one of the configured candidates."""
    column_set = set(columns)
    for candidate in candidates:
        if candidate in column_set:
            return candidate
    return None


def parse_remove_row(value: Any) -> bool:
    """Interpret common true-ish remove-row values."""
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    text = str(value).strip().lower()
    return text in {"true", "t", "yes", "y", "1", "remove", "removed", "drop", "inactive"}


_SUBTOTAL_TRUE_VALUES: frozenset[str] = frozenset({"true", "yes", "1"})
_SUBTOTAL_FALSE_VALUES: frozenset[str] = frozenset({"false", "no", "0", ""})


def parse_esto_pair_is_subtotal(value: Any) -> bool:
    """Strictly parse the esto_pair_is_subtotal flag from a workbook cell.

    Accepted true values:   boolean True, integer/float 1, strings "1" / "true" / "yes"
    Accepted false values:  boolean False, integer/float 0, strings "0" / "false" / "no",
                            blank strings, None, pandas NA, and any NaN.

    Any other non-empty value raises ValueError so that unexpected workbook
    content is caught rather than silently coerced.

    This function intentionally does NOT call bool() on the raw value directly
    because bool(np.nan) is True, which would incorrectly mark blank Excel cells
    as subtotals.
    """
    # NaN / NA / None -> False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
        raise ValueError(
            f"Unexpected numeric value for esto_pair_is_subtotal: {value!r}. "
            "Expected 0, 1, True, False, or blank."
        )

    text = str(value).strip().lower()
    if text in _SUBTOTAL_TRUE_VALUES:
        return True
    if text in _SUBTOTAL_FALSE_VALUES:
        return False
    raise ValueError(
        f"Unexpected string value for esto_pair_is_subtotal: {value!r}. "
        f"Expected one of {sorted(_SUBTOTAL_TRUE_VALUES | _SUBTOTAL_FALSE_VALUES)!r}."
    )


def normalise_match_text(value: Any) -> str:
    """Normalise text used in relationship IDs and QA keys."""
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip()).lower()


def normalise_path_segments(path: Any) -> list[str]:
    """Split a LEAP path on either slash style and drop empty segments."""
    if pd.isna(path):
        return []
    normalised_path = str(path).replace("\\", "/")
    return [segment.strip() for segment in normalised_path.split("/") if segment.strip()]


def is_parent_child_path(parent_path: Any, child_path: Any) -> bool:
    """Return True if parent_path is a strict parent of child_path."""
    parent_segments = normalise_path_segments(parent_path)
    child_segments = normalise_path_segments(child_path)
    return bool(parent_segments) and child_segments[: len(parent_segments)] == parent_segments and len(child_segments) > len(parent_segments)


def is_total_or_subtotal_flow(flow: Any) -> bool:
    """Return True for total final rows or explicit total/subtotal labels."""
    text = "" if pd.isna(flow) else str(flow).strip().lower()
    return text.startswith(("12 ", "13 ")) or "total" in text or "subtotal" in text


def has_expected_cardinality(cardinality_text: Any) -> bool:
    """Return True when cardinality metadata says duplication can be expected."""
    text = "" if pd.isna(cardinality_text) else str(cardinality_text).strip().lower()
    return "many" in text or "multiple" in text or "ok" in text


def join_unique(values: pd.Series | list[Any]) -> str:
    """Join unique non-empty values with pipe separators."""
    raw_values = values.tolist() if isinstance(values, pd.Series) else values
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        if pd.isna(value):
            continue
        text = str(value).strip()
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return "|".join(cleaned)


def make_relationship_id(
    source_system: str,
    source_flow: Any,
    source_product: Any,
    target_system: str,
    target_flow: Any,
    target_product: Any,
) -> str:
    """Create a stable ID for the underlying source-to-target relationship."""
    key_parts = [
        source_system,
        normalise_match_text(source_flow),
        normalise_match_text(source_product),
        target_system,
        normalise_match_text(target_flow),
        normalise_match_text(target_product),
    ]
    digest = hashlib.sha1("||".join(key_parts).encode("utf-8")).hexdigest()[:16]
    return f"rel_{digest}"


def normalise_mapping_columns(df: pd.DataFrame, sheet_config: dict[str, Any]) -> pd.DataFrame:
    """Rename workbook columns into the relationship builder's standard names."""
    original_columns = list(df.columns)
    cleaned_columns = [clean_column_name(column) for column in original_columns]
    working_df = df.copy()
    working_df.columns = cleaned_columns

    candidate_map = dict(COLUMN_CANDIDATES)
    candidate_map["source_sector_path"] = sheet_config["source_flow_candidates"] + candidate_map["source_sector_path"]
    candidate_map["source_fuel"] = sheet_config["source_product_candidates"] + candidate_map["source_fuel"]
    candidate_map["target_flow"] = sheet_config["target_flow_candidates"] + candidate_map["target_flow"]
    candidate_map["target_product"] = sheet_config["target_product_candidates"] + candidate_map["target_product"]

    rename_map: dict[str, str] = {}
    for target_column, candidates in candidate_map.items():
        source_column = first_existing_column(cleaned_columns, candidates)
        if source_column is not None:
            rename_map[source_column] = target_column

    normalised_df = working_df.rename(columns=rename_map)
    required_columns = ["source_sector_path", "source_fuel", "target_flow", "target_product"]
    missing_required = [column for column in required_columns if column not in normalised_df.columns]
    if missing_required:
        raise ValueError(
            "Could not identify required mapping columns: "
            + ", ".join(missing_required)
            + f". Source columns were: {original_columns}"
        )

    optional_defaults = {
        "source_sector_code": "",
        "source_product_code": "",
        "target_sector_code": "",
        "target_product_code": "",
        "esto_pair_is_subtotal": False,
        "remove_row": pd.NA,
        "cardinality": "",
        "notes": "",
    }
    for column, default_value in optional_defaults.items():
        if column not in normalised_df.columns:
            normalised_df[column] = default_value

    return normalised_df


def infer_relationship_type(target_flow: Any, target_system: str) -> str:
    """Infer a coarse relationship type from the target ESTO flow."""
    flow = "" if pd.isna(target_flow) else str(target_flow).strip()
    if target_system == "NINTH" and flow.startswith(("12_", "13_")):
        return "total_final_rollup"
    if flow.startswith(("12 ", "13 ")):
        return "total_final_rollup"
    if flow.startswith(("10.01", "10.02")):
        return "own_use_or_losses"
    return "direct_or_existing_mapping"


def infer_relationship_level(target_flow: Any, source_sector_path: Any, target_system: str) -> str:
    """Infer relationship level using ESTO totals and LEAP path depth."""
    flow = "" if pd.isna(target_flow) else str(target_flow).strip()
    if target_system == "NINTH" and flow.startswith(("12_", "13_")):
        return "total"
    if flow.startswith(("12 ", "13 ")):
        return "total"
    if len(normalise_path_segments(source_sector_path)) > 1:
        return "child"
    return "parent"


def relationship_status_for_remove_flag(remove_flag: bool) -> str:
    """Return status for a generated use-case row."""
    if remove_flag:
        return "excluded_by_remove_row_for_use_case"
    return "included_in_use_case"


def build_relationship_rows(
    source_df: pd.DataFrame,
    source_mapping_path: Path,
    sheet_config: dict[str, Any],
) -> pd.DataFrame:
    """Create one row per relationship per use case from one mapping sheet."""
    source_sheet = sheet_config["sheet_name"]
    source_system = sheet_config["source_system"]
    target_system = sheet_config["target_system"]
    use_cases = sheet_config["use_cases"]
    normalised_df = normalise_mapping_columns(source_df, sheet_config).copy()
    normalised_df["source_row_number"] = normalised_df.index + 2

    for column in [
        "source_sector_path",
        "source_fuel",
        "source_sector_code",
        "source_product_code",
        "target_flow",
        "target_product",
        "target_sector_code",
        "target_product_code",
        "cardinality",
        "notes",
    ]:
        normalised_df[column] = normalised_df[column].fillna("").astype(str).str.strip()

    relationship_rows: list[dict[str, Any]] = []
    for _, row in normalised_df.iterrows():
        remove_flag = parse_remove_row(row["remove_row"])
        relationship_id = make_relationship_id(
            source_system,
            row["source_sector_path"],
            row["source_fuel"],
            target_system,
            row["target_flow"],
            row["target_product"],
        )
        include_in_use_case = not remove_flag
        exclude_reason = "remove_row_true_in_source_mapping" if remove_flag else ""
        relationship_status = relationship_status_for_remove_flag(remove_flag)

        for use_case in use_cases:
            relationship_rows.append(
                {
                    "relationship_id": relationship_id,
                    "relationship_key": f"{relationship_id}::{use_case}",
                    "use_case": use_case,
                    "include_in_use_case": include_in_use_case,
                    "source_system": source_system,
                    "source_flow": row["source_sector_path"],
                    "source_product": row["source_fuel"],
                    "source_sector_path": row["source_sector_path"],
                    "source_fuel": row["source_fuel"],
                    "source_sector_code": row["source_sector_code"],
                    "source_product_code": row["source_product_code"],
                    "target_system": target_system,
                    "target_flow": row["target_flow"],
                    "target_product": row["target_product"],
                    "target_sector_code": row["target_sector_code"],
                    "target_product_code": row["target_product_code"],
                    "esto_pair_is_subtotal": parse_esto_pair_is_subtotal(row.get("esto_pair_is_subtotal", False)),
                    "cardinality": row["cardinality"],
                    "relationship_type": infer_relationship_type(row["target_flow"], target_system),
                    "relationship_level": infer_relationship_level(row["target_flow"], row["source_sector_path"], target_system),
                    "allocation_method": "direct",
                    "allocation_source": "",
                    "allocation_share": "",
                    "relationship_status": relationship_status,
                    "relationship_source": source_sheet,
                    "exclude_reason": exclude_reason,
                    "notes": row["notes"],
                    "review_required": False,
                    "review_flags": "",
                    "remove_row": row["remove_row"],
                    "is_rollup_derived": False,
                    "source_mapping_file": str(source_mapping_path),
                    "source_sheet": source_sheet,
                    "source_row_number": row["source_row_number"],
                }
            )

    return pd.DataFrame(relationship_rows, columns=RELATIONSHIP_COLUMNS)


def classify_duplicate_row(row: pd.Series, duplicate_kind: str) -> pd.Series:
    """Classify duplicate QA rows without treating all duplicates as defects."""
    expected_duplicate = (
        has_expected_cardinality(row.get("cardinality", ""))
        or "total_final_rollup" in str(row.get("relationship_types", ""))
        or "total" in str(row.get("relationship_levels", ""))
        or any(is_total_or_subtotal_flow(flow) for flow in str(row.get("target_flows", "")).split("|"))
    )
    if expected_duplicate:
        return pd.Series(
            {
                "qa_status": "review_expected",
                "qa_severity": "info",
                "qa_reason": f"{duplicate_kind} duplication is expected by cardinality or total/subtotal metadata.",
                "expected_duplicate": True,
            }
        )
    return pd.Series(
        {
            "qa_status": "review",
            "qa_severity": "warning",
            "qa_reason": f"{duplicate_kind} duplication needs human review; no metadata currently marks it expected.",
            "expected_duplicate": False,
        }
    )


def classify_parent_child_row(row: pd.Series) -> pd.Series:
    """Classify parent/child overlap as warning unless metadata marks it expected."""
    expected_duplicate = has_expected_cardinality(row.get("cardinality", "")) or bool(row.get("subtotal_overlap", False))
    if expected_duplicate:
        return pd.Series(
            {
                "qa_status": "review_expected",
                "qa_severity": "info",
                "qa_reason": "Parent/child overlap is expected by cardinality or subtotal metadata.",
                "expected_duplicate": True,
            }
        )
    return pd.Series(
        {
            "qa_status": "review",
            "qa_severity": "warning",
            "qa_reason": "Parent/child overlap can double-count if both rows are consumed together.",
            "expected_duplicate": False,
        }
    )


def build_duplicate_source_pairs(relationship_df: pd.DataFrame, use_case: str) -> pd.DataFrame:
    """Find included LEAP source pairs that map to multiple ESTO targets."""
    included_df = relationship_df[
        (relationship_df["use_case"] == use_case) & relationship_df["include_in_use_case"]
    ].copy()
    if included_df.empty:
        return pd.DataFrame()

    included_df["target_pair"] = included_df["target_flow"].astype(str) + " :: " + included_df["target_product"].astype(str)
    grouped_df = (
        included_df.groupby(["source_flow", "source_product"], dropna=False)
        .agg(
            included_row_count=("relationship_id", "size"),
            target_pair_count=("target_pair", "nunique"),
            target_pairs=("target_pair", join_unique),
            target_flows=("target_flow", join_unique),
            source_rows=("source_row_number", join_unique),
            cardinality=("cardinality", join_unique),
            relationship_types=("relationship_type", join_unique),
            relationship_levels=("relationship_level", join_unique),
        )
        .reset_index()
    )
    duplicate_df = grouped_df[grouped_df["target_pair_count"] > 1].copy()
    if duplicate_df.empty:
        return duplicate_df
    classification_df = duplicate_df.apply(lambda row: classify_duplicate_row(row, "source-to-target"), axis=1)
    return pd.concat([duplicate_df, classification_df], axis=1).sort_values(
        ["qa_severity", "source_flow", "source_product"]
    )


def build_duplicate_target_pairs(relationship_df: pd.DataFrame, use_case: str) -> pd.DataFrame:
    """Find included ESTO target pairs that receive multiple LEAP sources."""
    included_df = relationship_df[
        (relationship_df["use_case"] == use_case) & relationship_df["include_in_use_case"]
    ].copy()
    if included_df.empty:
        return pd.DataFrame()

    included_df["source_pair"] = included_df["source_flow"].astype(str) + " :: " + included_df["source_product"].astype(str)
    grouped_df = (
        included_df.groupby(["target_flow", "target_product"], dropna=False)
        .agg(
            included_row_count=("relationship_id", "size"),
            source_pair_count=("source_pair", "nunique"),
            source_pairs=("source_pair", join_unique),
            source_rows=("source_row_number", join_unique),
            cardinality=("cardinality", join_unique),
            relationship_types=("relationship_type", join_unique),
            relationship_levels=("relationship_level", join_unique),
        )
        .reset_index()
    )
    duplicate_df = grouped_df[grouped_df["source_pair_count"] > 1].copy()
    if duplicate_df.empty:
        return duplicate_df
    duplicate_df["target_flows"] = duplicate_df["target_flow"]
    classification_df = duplicate_df.apply(lambda row: classify_duplicate_row(row, "target-to-source"), axis=1)
    return pd.concat([duplicate_df, classification_df], axis=1).sort_values(
        ["qa_severity", "target_flow", "target_product"]
    )


def _split_allowed_duplicate_source_pairs(
    duplicate_source_df: pd.DataFrame,
    exception_workbook_path: Path = EXCEPTION_WORKBOOK_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split duplicate source rows into unresolved and manually allowed rows."""
    return split_allowed_rows(
        duplicate_source_df,
        sheet_name=DUPLICATE_SOURCE_EXCEPTION_SHEET,
        status_column="duplicate_source_review_status",
        reason_column="duplicate_source_review_reason",
        workbook_path=exception_workbook_path,
    )


def _split_allowed_duplicate_target_pairs(
    duplicate_target_df: pd.DataFrame,
    exception_workbook_path: Path = EXCEPTION_WORKBOOK_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split duplicate target rows into unresolved and manually allowed rows."""
    return split_allowed_rows(
        duplicate_target_df,
        sheet_name=DUPLICATE_TARGET_EXCEPTION_SHEET,
        status_column="duplicate_target_review_status",
        reason_column="duplicate_target_review_reason",
        workbook_path=exception_workbook_path,
    )


def build_parent_child_risks(relationship_df: pd.DataFrame, use_case: str) -> pd.DataFrame:
    """Flag included parent/child LEAP paths that point to the same ESTO target."""
    included_df = relationship_df[
        (relationship_df["use_case"] == use_case)
        & relationship_df["include_in_use_case"]
        & (relationship_df["source_flow"].fillna("").astype(str).str.len() > 0)
    ].copy()
    risk_rows: list[dict[str, Any]] = []
    if included_df.empty:
        return pd.DataFrame(risk_rows)

    for (target_flow, target_product), group_df in included_df.groupby(["target_flow", "target_product"], dropna=False):
        records = group_df.to_dict("records")
        for left_index, left in enumerate(records):
            for right in records[left_index + 1 :]:
                if is_parent_child_path(left["source_flow"], right["source_flow"]):
                    parent, child = left, right
                elif is_parent_child_path(right["source_flow"], left["source_flow"]):
                    parent, child = right, left
                else:
                    continue
                risk_rows.append(
                    {
                        "target_flow": target_flow,
                        "target_product": target_product,
                        "parent_source_flow": parent["source_flow"],
                        "child_source_flow": child["source_flow"],
                        "parent_source_product": parent["source_product"],
                        "child_source_product": child["source_product"],
                        "parent_source_row_number": parent["source_row_number"],
                        "child_source_row_number": child["source_row_number"],
                        "cardinality": join_unique([parent.get("cardinality", ""), child.get("cardinality", "")]),
                        "relationship_types": join_unique([parent.get("relationship_type", ""), child.get("relationship_type", "")]),
                        "relationship_levels": join_unique([parent.get("relationship_level", ""), child.get("relationship_level", "")]),
                        "subtotal_overlap": is_total_or_subtotal_flow(target_flow),
                    }
                )

    risk_df = pd.DataFrame(risk_rows)
    if risk_df.empty:
        return risk_df
    risk_df = risk_df.drop_duplicates()
    classification_df = risk_df.apply(classify_parent_child_row, axis=1)
    return pd.concat([risk_df, classification_df], axis=1).sort_values(
        ["qa_severity", "target_flow", "target_product", "parent_source_flow", "child_source_flow"]
    )


def build_conversion_qa_tables(
    relationship_df: pd.DataFrame,
    coverage_exclusions_df: pd.DataFrame,
    esto_combined_rows_df: pd.DataFrame,
    use_case: str,
) -> dict[str, pd.DataFrame]:
    """Build LEAP-to-ESTO conversion QA tables."""
    use_case_df = relationship_df[relationship_df["use_case"] == use_case].copy()
    included_df = use_case_df[use_case_df["include_in_use_case"]].copy()
    not_considered_df = build_not_considered_esto_rows(relationship_df, coverage_exclusions_df, use_case)
    one_to_many_issue_df = build_one_to_many_issues(relationship_df, esto_combined_rows_df, use_case)

    source_missing_target_df = included_df[
        (included_df["target_flow"].fillna("").astype(str).str.strip() == "")
        | (included_df["target_product"].fillna("").astype(str).str.strip() == "")
    ].copy()
    target_missing_source_df = included_df[
        (included_df["source_flow"].fillna("").astype(str).str.strip() == "")
        | (included_df["source_product"].fillna("").astype(str).str.strip() == "")
    ].copy()
    excluded_audit_df = use_case_df[~use_case_df["include_in_use_case"]].copy()

    duplicate_source_df = build_duplicate_source_pairs(relationship_df, use_case)
    duplicate_target_df = build_duplicate_target_pairs(relationship_df, use_case)
    duplicate_source_df, allowed_duplicate_source_df = _split_allowed_duplicate_source_pairs(duplicate_source_df)
    duplicate_target_df, allowed_duplicate_target_df = _split_allowed_duplicate_target_pairs(duplicate_target_df)
    parent_child_df = build_parent_child_risks(relationship_df, use_case)
    missing_dataset_pairs_df = build_missing_dataset_pairs_by_use_case(relationship_df)

    summary_rows = [
        {"metric": "relationship_rows", "value": len(use_case_df)},
        {"metric": "included_relationship_rows", "value": len(included_df)},
        {"metric": "excluded_relationship_rows", "value": len(use_case_df) - len(included_df)},
        {"metric": "remove_row_true_rows", "value": int(use_case_df["remove_row"].apply(parse_remove_row).sum())},
        {"metric": "unique_leap_source_pairs", "value": included_df[["source_flow", "source_product"]].drop_duplicates().shape[0]},
        {"metric": "unique_esto_target_pairs", "value": included_df[["target_flow", "target_product"]].drop_duplicates().shape[0]},
        {"metric": "leap_sources_without_esto_target", "value": len(source_missing_target_df)},
        {"metric": "esto_targets_without_leap_source", "value": len(target_missing_source_df)},
        {"metric": "not_considered_esto_rows", "value": len(not_considered_df)},
        {"metric": "missing_dataset_pairs_by_use_case", "value": len(missing_dataset_pairs_df)},
        {"metric": "duplicate_source_groups", "value": len(duplicate_source_df)},
        {"metric": "duplicate_source_groups_allowed_matched", "value": len(allowed_duplicate_source_df)},
        {"metric": "duplicate_target_groups", "value": len(duplicate_target_df)},
        {"metric": "duplicate_target_groups_allowed_matched", "value": len(allowed_duplicate_target_df)},
        {"metric": "one_to_many_allocation_or_combined_target_issues", "value": len(one_to_many_issue_df)},
        {"metric": "parent_child_risk_rows", "value": len(parent_child_df)},
    ]
    coverage_summary_df = pd.DataFrame(summary_rows)

    return {
        "leap_sources_without_esto_target": source_missing_target_df,
        "esto_targets_without_leap_source": target_missing_source_df,
        "missing_dataset_pairs_by_use_case": missing_dataset_pairs_df,
        "not_considered_esto_rows": not_considered_df,
        "leap_to_esto_duplicate_source_pairs": duplicate_source_df,
        "leap_to_esto_duplicate_source_pairs_allowed_matched": allowed_duplicate_source_df,
        "leap_to_esto_duplicate_target_pairs": duplicate_target_df,
        "leap_to_esto_duplicate_target_pairs_allowed_matched": allowed_duplicate_target_df,
        "one_to_many_mappings_without_allocation_or_combined_target": one_to_many_issue_df,
        "leap_to_esto_parent_child_risks": parent_child_df,
        "leap_to_esto_coverage_summary": coverage_summary_df,
        "leap_to_esto_excluded_source_audit": excluded_audit_df,
    }


def build_dataset_pair_observations(relationship_df: pd.DataFrame, included_only: bool) -> pd.DataFrame:
    """Return one row per observed dataset flow/product pair in relationship rows."""
    if relationship_df.empty:
        return pd.DataFrame(
            columns=[
                "use_case",
                "dataset_system",
                "flow",
                "product",
                "relationship_id",
                "relationship_source",
                "source_sheet",
                "source_row_number",
            ]
        )

    working_df = relationship_df.copy()
    if included_only:
        working_df = working_df[working_df["include_in_use_case"]].copy()

    source_pairs_df = working_df[
        [
            "use_case",
            "source_system",
            "source_flow",
            "source_product",
            "relationship_id",
            "relationship_source",
            "source_sheet",
            "source_row_number",
        ]
    ].rename(
        columns={
            "source_system": "dataset_system",
            "source_flow": "flow",
            "source_product": "product",
        }
    )
    target_pairs_df = working_df[
        [
            "use_case",
            "target_system",
            "target_flow",
            "target_product",
            "relationship_id",
            "relationship_source",
            "source_sheet",
            "source_row_number",
        ]
    ].rename(
        columns={
            "target_system": "dataset_system",
            "target_flow": "flow",
            "target_product": "product",
        }
    )
    pair_df = pd.concat([source_pairs_df, target_pairs_df], ignore_index=True)
    for column in ["dataset_system", "flow", "product"]:
        pair_df[column] = pair_df[column].fillna("").astype(str).str.strip()
    pair_df = pair_df[
        (pair_df["dataset_system"] != "")
        & (pair_df["flow"] != "")
        & (pair_df["product"] != "")
    ].copy()
    return pair_df.drop_duplicates()


def build_missing_dataset_pairs_by_use_case(relationship_df: pd.DataFrame) -> pd.DataFrame:
    """List relationship-table dataset pairs absent from each use case."""
    columns = [
        "use_case",
        "dataset_system",
        "flow",
        "product",
        "relationship_rows_in_use_cases",
        "included_in_use_cases",
        "relationship_sources",
        "source_sheets",
        "source_row_numbers",
        "relationship_count_in_all_relationships",
        "missing_reason",
    ]
    if relationship_df.empty:
        return pd.DataFrame(columns=columns)

    all_pair_observations_df = build_dataset_pair_observations(relationship_df, included_only=False)
    included_pair_observations_df = build_dataset_pair_observations(relationship_df, included_only=True)
    if all_pair_observations_df.empty:
        return pd.DataFrame(columns=columns)

    pair_catalogue_df = (
        all_pair_observations_df.groupby(["dataset_system", "flow", "product"], dropna=False)
        .agg(
            relationship_rows_in_use_cases=("use_case", join_unique),
            relationship_sources=("relationship_source", join_unique),
            source_sheets=("source_sheet", join_unique),
            source_row_numbers=("source_row_number", join_unique),
            relationship_count_in_all_relationships=("relationship_id", "nunique"),
        )
        .reset_index()
    )
    included_use_cases_df = (
        included_pair_observations_df.groupby(["dataset_system", "flow", "product"], dropna=False)
        .agg(included_in_use_cases=("use_case", join_unique))
        .reset_index()
    )
    pair_catalogue_df = pair_catalogue_df.merge(
        included_use_cases_df,
        on=["dataset_system", "flow", "product"],
        how="left",
    )
    pair_catalogue_df["included_in_use_cases"] = pair_catalogue_df["included_in_use_cases"].fillna("")

    included_keys = set(
        included_pair_observations_df[["use_case", "dataset_system", "flow", "product"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    use_cases = sorted(relationship_df["use_case"].fillna("").astype(str).str.strip().unique())

    missing_rows: list[dict[str, Any]] = []
    for use_case in use_cases:
        if not use_case:
            continue
        for row in pair_catalogue_df.to_dict("records"):
            key = (use_case, row["dataset_system"], row["flow"], row["product"])
            if key in included_keys:
                continue
            missing_rows.append(
                {
                    "use_case": use_case,
                    "dataset_system": row["dataset_system"],
                    "flow": row["flow"],
                    "product": row["product"],
                    "relationship_rows_in_use_cases": row["relationship_rows_in_use_cases"],
                    "included_in_use_cases": row["included_in_use_cases"],
                    "relationship_sources": row["relationship_sources"],
                    "source_sheets": row["source_sheets"],
                    "source_row_numbers": row["source_row_numbers"],
                    "relationship_count_in_all_relationships": row["relationship_count_in_all_relationships"],
                    "missing_reason": "pair_exists_elsewhere_in_energy_balance_relationships_but_not_included_for_use_case",
                }
            )

    missing_df = pd.DataFrame(missing_rows, columns=columns)
    if missing_df.empty:
        return missing_df
    return missing_df.sort_values(["use_case", "dataset_system", "flow", "product"]).reset_index(drop=True)


def build_relationship_catalogue(relationship_df: pd.DataFrame) -> pd.DataFrame:
    """Build a deduplicated human-readable relationship catalogue."""
    if relationship_df.empty:
        return pd.DataFrame(columns=CATALOGUE_COLUMNS)

    use_case_columns = {
        "leap_to_esto_balance_conversion": "used_for_leap_to_esto_balance_conversion",
        "ninth_to_esto_balance_conversion": "used_for_ninth_to_esto_balance_conversion",
        "leap_to_ninth_comparison": "used_for_leap_to_ninth_comparison",
        "ninth_to_leap_initialisation": "used_for_ninth_to_leap_initialisation",
    }
    rows: list[dict[str, Any]] = []
    for relationship_id, group_df in relationship_df.groupby("relationship_id", dropna=False):
        first = group_df.iloc[0]
        included_use_cases = group_df.loc[group_df["include_in_use_case"], "use_case"].tolist()
        excluded_use_cases = group_df.loc[~group_df["include_in_use_case"], "use_case"].tolist()
        row = {
            "relationship_id": relationship_id,
            "source_system": first["source_system"],
            "source_flow": first["source_flow"],
            "source_product": first["source_product"],
            "target_system": first["target_system"],
            "target_flow": first["target_flow"],
            "target_product": first["target_product"],
            "relationship_type": join_unique(group_df["relationship_type"]),
            "relationship_level": join_unique(group_df["relationship_level"]),
            "cardinality": join_unique(group_df["cardinality"]),
            "allocation_method": join_unique(group_df["allocation_method"]),
            "included_use_cases": "|".join(included_use_cases),
            "excluded_use_cases": "|".join(excluded_use_cases),
            "all_use_cases": join_unique(group_df["use_case"]),
            "any_excluded": bool((~group_df["include_in_use_case"]).any()),
            "review_required": bool(group_df["review_required"].any()),
            "review_flags": join_unique(group_df["review_flags"]),
            "notes": join_unique(group_df["notes"]),
        }
        for use_case, column in use_case_columns.items():
            row[column] = use_case in included_use_cases
        rows.append(row)
    return pd.DataFrame(rows, columns=CATALOGUE_COLUMNS)


def system_pair_view(
    relationship_df: pd.DataFrame,
    source_system: str,
    target_system: str,
    required_use_case: str | None = None,
) -> pd.DataFrame:
    """Return one row per source/target pair for a system relationship."""
    filtered_df = relationship_df[
        (relationship_df["source_system"] == source_system)
        & (relationship_df["target_system"] == target_system)
    ].copy()
    if required_use_case is not None:
        filtered_df = filtered_df[filtered_df["use_case"] == required_use_case].copy()

    included_df = filtered_df[filtered_df["include_in_use_case"]].copy()
    if included_df.empty:
        included_df = filtered_df.copy()

    return included_df[
        ["source_flow", "source_product", "target_flow", "target_product"]
    ].drop_duplicates()


def build_compact_relationship_catalogue(relationship_df: pd.DataFrame) -> pd.DataFrame:
    """Build a compact six-column LEAP/ESTO/9th relationship catalogue."""
    leap_esto_df = system_pair_view(
        relationship_df,
        source_system="LEAP",
        target_system="ESTO",
        required_use_case="leap_to_esto_balance_conversion",
    ).rename(
        columns={
            "source_flow": "leap_flow",
            "source_product": "leap_product",
            "target_flow": "esto_flow",
            "target_product": "esto_product",
        }
    )
    ninth_esto_df = system_pair_view(
        relationship_df,
        source_system="NINTH",
        target_system="ESTO",
        required_use_case="ninth_to_esto_balance_conversion",
    ).rename(
        columns={
            "source_flow": "ninth_sector",
            "source_product": "ninth_fuel",
            "target_flow": "esto_flow",
            "target_product": "esto_product",
        }
    )
    leap_ninth_df = system_pair_view(
        relationship_df,
        source_system="LEAP",
        target_system="NINTH",
        required_use_case="leap_to_ninth_comparison",
    ).rename(
        columns={
            "source_flow": "leap_flow",
            "source_product": "leap_product",
            "target_flow": "ninth_sector",
            "target_product": "ninth_fuel",
        }
    )

    via_esto_df = leap_esto_df.merge(
        ninth_esto_df,
        on=["esto_flow", "esto_product"],
        how="outer",
    )
    via_ninth_df = leap_ninth_df.merge(
        ninth_esto_df,
        on=["ninth_sector", "ninth_fuel"],
        how="left",
    )
    compact_df = pd.concat([via_esto_df, via_ninth_df], ignore_index=True)
    for column in COMPACT_CATALOGUE_COLUMNS:
        if column not in compact_df.columns:
            compact_df[column] = ""
    compact_df = compact_df[COMPACT_CATALOGUE_COLUMNS]
    compact_df = compact_df.fillna("").drop_duplicates()
    return compact_df.sort_values(COMPACT_CATALOGUE_COLUMNS).reset_index(drop=True)


def read_configured_sheet(
    primary_workbook_path: Path,
    fallback_workbook_path: Path,
    sheet_name: str,
) -> tuple[pd.DataFrame | None, Path | None]:
    """Read a mapping sheet from the primary workbook, falling back to master_config."""
    for workbook_path in [primary_workbook_path, fallback_workbook_path]:
        try:
            workbook = pd.ExcelFile(workbook_path)
            if sheet_name in workbook.sheet_names:
                return pd.read_excel(workbook_path, sheet_name=sheet_name), workbook_path
        except FileNotFoundError:
            continue
    return None, None


def normalise_optional_table(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Return an optional config table with expected columns in order."""
    if df is None or df.empty:
        return pd.DataFrame(columns=columns)
    working_df = df.copy()
    for column in columns:
        if column not in working_df.columns:
            working_df[column] = ""
    return working_df[columns].fillna("")


def build_default_coverage_exclusions() -> pd.DataFrame:
    """Build default use-case-specific coverage exclusions."""
    return pd.DataFrame(
        [
            {
                "use_case": "leap_to_esto_balance_conversion",
                "comparison_scope": "leap_vs_esto",
                "source_system": "LEAP",
                "target_system": "ESTO",
                "target_flow": "06 Stock changes",
                "target_product": "",
                "exclusion_reason": "not_represented_in_leap_conversion",
                "notes": "Use-case-specific exclusion; do not apply globally.",
            }
        ],
        columns=COVERAGE_EXCLUSION_COLUMNS,
    )


def read_optional_config_table(
    primary_workbook_path: Path,
    fallback_workbook_path: Path,
    sheet_name: str,
    columns: list[str],
    default_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Read optional config sheet, falling back to a supplied default table."""
    source_df, _source_path = read_configured_sheet(
        primary_workbook_path=primary_workbook_path,
        fallback_workbook_path=fallback_workbook_path,
        sheet_name=sheet_name,
    )
    if source_df is None:
        if default_df is not None:
            return normalise_optional_table(default_df, columns)
        return pd.DataFrame(columns=columns)
    return normalise_optional_table(source_df, columns)


def exclusion_applies(row: pd.Series, exclusions_df: pd.DataFrame) -> bool:
    """Return True when a use-case-specific coverage exclusion applies."""
    if exclusions_df.empty:
        return False
    matches_df = exclusions_df[
        (exclusions_df["use_case"].astype(str) == str(row.get("use_case", "")))
        & (exclusions_df["source_system"].astype(str) == str(row.get("source_system", "")))
        & (exclusions_df["target_system"].astype(str) == str(row.get("target_system", "")))
        & (exclusions_df["target_flow"].astype(str) == str(row.get("target_flow", "")))
    ].copy()
    if matches_df.empty:
        return False
    product_values = matches_df["target_product"].fillna("").astype(str).str.strip()
    target_product = str(row.get("target_product", "")).strip()
    return bool(((product_values == "") | (product_values == target_product)).any())


def build_not_considered_esto_rows(relationship_df: pd.DataFrame, exclusions_df: pd.DataFrame, use_case: str) -> pd.DataFrame:
    """Build audit rows for expected ESTO rows excluded from this use case."""
    use_case_df = relationship_df[
        (relationship_df["use_case"] == use_case)
        & (relationship_df["target_system"] == "ESTO")
    ].copy()
    if use_case_df.empty or exclusions_df.empty:
        return pd.DataFrame(columns=list(use_case_df.columns) + ["coverage_status", "coverage_reason"])
    mask = use_case_df.apply(lambda row: exclusion_applies(row, exclusions_df), axis=1)
    not_considered_df = use_case_df[mask].copy()
    not_considered_df["coverage_status"] = "not_considered"
    not_considered_df["coverage_reason"] = "flow_excluded_from_use_case"
    return not_considered_df


def build_one_to_many_issues(relationship_df: pd.DataFrame, combined_rows_df: pd.DataFrame, use_case: str) -> pd.DataFrame:
    """Find included one-to-many mappings without allocation or combined target."""
    included_df = relationship_df[
        (relationship_df["use_case"] == use_case)
        & relationship_df["include_in_use_case"]
        & relationship_df["cardinality"].fillna("").astype(str).str.lower().str.contains("one_to_many")
    ].copy()
    if included_df.empty:
        return pd.DataFrame()
    valid_allocation = ~included_df["allocation_method"].fillna("").astype(str).str.lower().isin(["", "direct", "none"])
    valid_combined_target = included_df["target_system"].eq("ESTO_COMBINED")
    if not combined_rows_df.empty:
        combined_targets = set(
            zip(
                combined_rows_df["target_flow"].fillna("").astype(str),
                combined_rows_df["target_product"].fillna("").astype(str),
            )
        )
        valid_combined_target = valid_combined_target | included_df.apply(
            lambda row: (str(row["target_flow"]), str(row["target_product"])) in combined_targets,
            axis=1,
        )
    issue_df = included_df[~valid_allocation & ~valid_combined_target].copy()
    if issue_df.empty:
        return issue_df
    issue_df["qa_status"] = "review"
    issue_df["qa_severity"] = "high"
    issue_df["qa_reason"] = "one_to_many mapping has no allocation method and no valid ESTO_COMBINED target."
    issue_df["expected_duplicate"] = False
    return issue_df


# ---------------------------------------------------------------------------
# Combined ESTO expansion helpers
# ---------------------------------------------------------------------------

_COMBINED_ESTO_RE = re.compile(r"\d,\d")


def _str(val: Any) -> str:
    return "" if (val is None or (isinstance(val, float) and pd.isna(val))) else str(val).strip()


def _is_combined_esto_flow(label: str) -> bool:
    return bool(_COMBINED_ESTO_RE.search(label))


def _build_flow_prefix_to_label(workbook_path: Path) -> dict[str, str]:
    """Build {code_prefix: full_label} from esto_flow entries in leap_display_names."""
    try:
        df = pd.read_excel(workbook_path, sheet_name="leap_display_names", dtype=object)
        df = filter_used_in_leap_initialisation(df).fillna("")
    except Exception:
        return {}
    result: dict[str, str] = {}
    for _, row in df.iterrows():
        if _str(row.get("code_type")) == "esto_flow":
            full_label = _str(row.get("code"))
            if full_label:
                prefix = full_label.split()[0] if " " in full_label else full_label
                result[prefix] = full_label
    return result


def _expand_combined_esto_flow(flow_label: str, prefix_to_label: dict[str, str]) -> list[str]:
    """Expand '09.01.01,09.02.01 Electricity plants' → individual full labels."""
    parts = [p.strip() for p in flow_label.split(",")]
    result = []
    for part in parts:
        if " " in part:
            result.append(part)
        else:
            result.append(prefix_to_label.get(part, part))
    return result


def expand_combined_esto_targets(
    relationship_df: pd.DataFrame,
    prefix_to_label: dict[str, str],
) -> pd.DataFrame:
    """Expand relationship rows with combined ESTO flow targets into individual rows."""
    normal_rows: list[dict[str, Any]] = []
    expanded_rows: list[dict[str, Any]] = []
    for _, row in relationship_df.iterrows():
        target_flow = _str(row.get("target_flow", ""))
        if _str(row.get("target_system")) == "ESTO" and _is_combined_esto_flow(target_flow):
            components = _expand_combined_esto_flow(target_flow, prefix_to_label)
            for component_flow in components:
                new_row = row.to_dict()
                new_row["target_flow"] = component_flow
                new_row["relationship_id"] = make_relationship_id(
                    _str(row["source_system"]),
                    _str(row["source_flow"]),
                    _str(row["source_product"]),
                    _str(row["target_system"]),
                    component_flow,
                    _str(row["target_product"]),
                )
                new_row["relationship_key"] = f"{new_row['relationship_id']}::{_str(row['use_case'])}"
                expanded_rows.append(new_row)
        else:
            normal_rows.append(row.to_dict())

    all_rows = normal_rows + expanded_rows
    if not all_rows:
        return relationship_df
    return pd.DataFrame(all_rows, columns=relationship_df.columns).reset_index(drop=True)


def _build_rolled_flow_to_components(esto_rules: pd.DataFrame) -> dict[str, list[str]]:
    """Map each esto_rollup_rules rolled_esto_flow label to its unique input component flows."""
    if esto_rules.empty or "rolled_esto_flow" not in esto_rules.columns:
        return {}
    result: dict[str, list[str]] = {}
    for _, rule in esto_rules.iterrows():
        rolled = _str(rule.get("rolled_esto_flow"))
        component = _str(rule.get("input_esto_flow"))
        if not rolled or not component or component == rolled:
            continue
        components = result.setdefault(rolled, [])
        if component not in components:
            components.append(component)
    return result


def _resolve_rolled_flow_components(
    rolled_flow: str,
    rolled_flow_to_components: dict[str, list[str]],
    max_depth: int = 5,
) -> list[str]:
    """Resolve a rolled flow to real component flows, following nested rollup definitions."""
    resolved: list[str] = []
    pending = [(component, 1) for component in rolled_flow_to_components.get(rolled_flow, [])]
    while pending:
        component, depth = pending.pop(0)
        if component in rolled_flow_to_components and depth < max_depth:
            pending.extend((nested, depth + 1) for nested in rolled_flow_to_components[component])
        elif component not in resolved:
            resolved.append(component)
    return resolved


def expand_esto_rollup_targets(
    relationship_df: pd.DataFrame,
    rolled_flow_to_components: dict[str, list[str]],
) -> pd.DataFrame:
    """Expand relationship rows whose ESTO target is an esto_rollup_rules rolled flow.

    Mapping sheets may point ``esto_flow`` at a rolled label such as
    ``09.08.01 Coke ovens (including own use)``.  Those labels do not exist in
    the ESTO balance, so each such row is expanded into one relationship per
    component flow (e.g. ``09.08.01 Coke ovens`` and ``10.01.05 Coke ovens``),
    keeping the mapped product.  Because the expanded rows share one source
    pair, the common-structure stage links the components into a single common
    row, and the rolled label is applied to that row via common_esto_overrides.
    """
    if not rolled_flow_to_components:
        return relationship_df
    normal_rows: list[dict[str, Any]] = []
    expanded_rows: list[dict[str, Any]] = []
    for _, row in relationship_df.iterrows():
        target_flow = _str(row.get("target_flow", ""))
        if _str(row.get("target_system")) == "ESTO" and target_flow in rolled_flow_to_components:
            for component_flow in _resolve_rolled_flow_components(target_flow, rolled_flow_to_components):
                new_row = row.to_dict()
                new_row["target_flow"] = component_flow
                new_row["relationship_type"] = infer_relationship_type(component_flow, "ESTO")
                new_row["relationship_level"] = infer_relationship_level(
                    component_flow, row.get("source_sector_path", ""), "ESTO"
                )
                existing_notes = _str(row.get("notes", ""))
                rollup_note = f"expanded_from_esto_rollup: {target_flow}"
                new_row["notes"] = f"{existing_notes}; {rollup_note}" if existing_notes else rollup_note
                new_row["relationship_id"] = make_relationship_id(
                    _str(row["source_system"]),
                    _str(row["source_flow"]),
                    _str(row["source_product"]),
                    _str(row["target_system"]),
                    component_flow,
                    _str(row["target_product"]),
                )
                new_row["relationship_key"] = f"{new_row['relationship_id']}::{_str(row['use_case'])}"
                expanded_rows.append(new_row)
        else:
            normal_rows.append(row.to_dict())

    if not expanded_rows:
        return relationship_df
    return pd.DataFrame(normal_rows + expanded_rows, columns=relationship_df.columns).reset_index(drop=True)


def _load_known_esto_flows(workbook_path: Path) -> set[str]:
    """Load real ESTO flow labels from the 'ESTO unique flows and products' sheet."""
    try:
        df = pd.read_excel(workbook_path, sheet_name="ESTO unique flows and products", dtype=object)
    except Exception:
        return set()
    if "flows" not in df.columns:
        return set()
    return {_str(value) for value in df["flows"] if _str(value)}


def build_unknown_esto_target_qa(relationship_df: pd.DataFrame, known_esto_flows: set[str]) -> pd.DataFrame:
    """List ESTO target flows that match no real ESTO flow (no ESTO data will ever compare)."""
    esto_rows = relationship_df[relationship_df["target_system"].astype(str).str.strip() == "ESTO"]
    target_flows = esto_rows["target_flow"].astype(str).str.strip()
    unknown_rows = esto_rows[target_flows.ne("") & ~target_flows.isin(known_esto_flows)]
    if unknown_rows.empty:
        return pd.DataFrame(columns=["target_flow", "source_sheet", "relationship_row_count", "qa_status"])
    qa_df = (
        unknown_rows.groupby(["target_flow", "source_sheet"], dropna=False)
        .size()
        .reset_index(name="relationship_row_count")
        .sort_values(["target_flow", "source_sheet"])
        .reset_index(drop=True)
    )
    qa_df["qa_status"] = "esto_target_flow_has_no_esto_data"
    return qa_df


# ---------------------------------------------------------------------------
# Rollup rule loaders and appliers
# ---------------------------------------------------------------------------

def load_rollup_rules(workbook_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the three rollup rule sheets from outlook_mappings_master.xlsx."""
    def _load(sheet: str) -> pd.DataFrame:
        try:
            df = pd.read_excel(workbook_path, sheet_name=sheet, dtype=object).fillna("")
            return df[df["include"].astype(str).str.lower().isin(["true", "1", "yes"])].reset_index(drop=True)
        except Exception:
            return pd.DataFrame()
    return _load("leap_rollup_rules"), _load("esto_rollup_rules"), _load("ninth_rollup_rules")


def _apply_leap_rollup_rules(
    relationship_df: pd.DataFrame,
    leap_rules: pd.DataFrame,
) -> pd.DataFrame:
    """Create rolled rows for LEAP source rollup rules alongside base rows."""
    if leap_rules.empty:
        return pd.DataFrame(columns=relationship_df.columns)

    leap_df = relationship_df[
        (relationship_df["source_system"].astype(str) == "LEAP")
        & relationship_df["include_in_use_case"].astype(bool)
    ].copy()

    # A rolled aggregate that already has its own direct (non-rollup) mapping is
    # authoritative for that source flow. Cloning its individual input branches'
    # relationships on top would duplicate/inflate whatever those branches already
    # map to (e.g. "Industry" cloned onto "Total final consumption" bogusly injects
    # the whole-economy total into "14 Industry sector"; see
    # docs/prompts/investigate_demand_sector_parent_child_mismatches_FINDINGS.md #2/#3).
    directly_mapped_flows = set(
        leap_df.loc[~leap_df["is_rollup_derived"].astype(bool), "source_flow"]
        .astype(str)
        .str.strip()
    )

    new_rows: list[dict[str, Any]] = []
    for _, rule in leap_rules.iterrows():
        input_flow = _str(rule.get("input_leap_sector_name_full_path"))
        input_fuel = _str(rule.get("input_raw_leap_fuel_name"))
        rolled_flow = _str(rule.get("rolled_leap_sector_name_full_path"))
        rolled_fuel = _str(rule.get("rolled_raw_leap_fuel_name"))
        if not input_flow or not rolled_flow:
            continue
        if rolled_flow in directly_mapped_flows:
            continue

        mask = leap_df["source_flow"].astype(str).str.strip() == input_flow
        if input_fuel:
            mask &= leap_df["source_product"].astype(str).str.strip() == input_fuel

        for _, row in leap_df[mask].iterrows():
            new_source_product = rolled_fuel if rolled_fuel else _str(row["source_product"])
            new_row = row.to_dict()
            new_row["source_flow"] = rolled_flow
            new_row["source_product"] = new_source_product
            new_row["source_sector_path"] = rolled_flow
            new_row["source_fuel"] = new_source_product
            new_row["is_rollup_derived"] = True
            new_row["relationship_id"] = make_relationship_id(
                _str(row["source_system"]),
                rolled_flow,
                new_source_product,
                _str(row["target_system"]),
                _str(row["target_flow"]),
                _str(row["target_product"]),
            )
            new_row["relationship_key"] = f"{new_row['relationship_id']}::{_str(row['use_case'])}"
            new_rows.append(new_row)

    if not new_rows:
        return pd.DataFrame(columns=relationship_df.columns)
    return pd.DataFrame(new_rows, columns=relationship_df.columns).reset_index(drop=True)


def _apply_ninth_rollup_rules(
    relationship_df: pd.DataFrame,
    ninth_rules: pd.DataFrame,
) -> pd.DataFrame:
    """Create rolled rows for NINTH source rollup rules alongside base rows."""
    if ninth_rules.empty:
        return pd.DataFrame(columns=relationship_df.columns)

    ninth_df = relationship_df[
        (relationship_df["source_system"].astype(str) == "NINTH")
        & relationship_df["include_in_use_case"].astype(bool)
    ].copy()

    new_rows: list[dict[str, Any]] = []
    for _, rule in ninth_rules.iterrows():
        input_sector = _str(rule.get("input_9th_sector"))
        input_fuel = _str(rule.get("input_9th_fuel"))
        rolled_sector = _str(rule.get("rolled_9th_sector"))
        rolled_fuel = _str(rule.get("rolled_9th_fuel"))
        if not input_sector or not rolled_sector:
            continue

        mask = ninth_df["source_flow"].astype(str).str.strip() == input_sector
        if input_fuel:
            mask &= ninth_df["source_product"].astype(str).str.strip() == input_fuel

        for _, row in ninth_df[mask].iterrows():
            new_source_product = rolled_fuel if rolled_fuel else _str(row["source_product"])
            new_row = row.to_dict()
            new_row["source_flow"] = rolled_sector
            new_row["source_product"] = new_source_product
            new_row["source_sector_path"] = rolled_sector
            new_row["source_fuel"] = new_source_product
            new_row["is_rollup_derived"] = True
            new_row["relationship_id"] = make_relationship_id(
                _str(row["source_system"]),
                rolled_sector,
                new_source_product,
                _str(row["target_system"]),
                _str(row["target_flow"]),
                _str(row["target_product"]),
            )
            new_row["relationship_key"] = f"{new_row['relationship_id']}::{_str(row['use_case'])}"
            new_rows.append(new_row)

    if not new_rows:
        return pd.DataFrame(columns=relationship_df.columns)
    return pd.DataFrame(new_rows, columns=relationship_df.columns).reset_index(drop=True)


def build_esto_overrides(esto_rules: pd.DataFrame) -> pd.DataFrame:
    """Generate common_esto_overrides.csv content from esto_rollup_rules."""
    if esto_rules.empty:
        return pd.DataFrame(columns=ESTO_OVERRIDES_COLUMNS)

    group_key_to_id: dict[tuple[str, str], str] = {}
    rows: list[dict[str, Any]] = []
    for _, rule in esto_rules.iterrows():
        rolled_flow = _str(rule.get("rolled_esto_flow"))
        rolled_product = _str(rule.get("rolled_esto_product"))
        input_flow = _str(rule.get("input_esto_flow"))
        input_product = _str(rule.get("input_esto_product"))
        if not rolled_flow or not input_flow:
            continue

        group_key = (rolled_flow, rolled_product)
        if group_key not in group_key_to_id:
            digest = hashlib.sha1(f"{rolled_flow}||{rolled_product}".encode()).hexdigest()[:12]
            group_key_to_id[group_key] = f"esto_override_{digest}"
        override_group_id = group_key_to_id[group_key]

        rows.append({
            "comparison_scope": "",
            "override_group_id": override_group_id,
            "component_esto_flow": input_flow,
            "component_esto_product": input_product,
            "preferred_common_flow_label": rolled_flow,
            "preferred_common_product_label": rolled_product,
            "override_reason": "esto_rollup_rules",
            "notes": _str(rule.get("Note")),
        })

    return pd.DataFrame(rows, columns=ESTO_OVERRIDES_COLUMNS)


def save_relationship_outputs(
    relationship_df: pd.DataFrame,
    relationship_catalogue_df: pd.DataFrame,
    compact_catalogue_df: pd.DataFrame,
    coverage_exclusions_df: pd.DataFrame,
    esto_combined_rows_df: pd.DataFrame,
    esto_overrides_df: pd.DataFrame,
    qa_tables: dict[str, pd.DataFrame],
    output_csv_path: Path,
    output_xlsx_path: Path,
    compact_catalogue_csv_path: Path,
    qa_dir: Path,
) -> None:
    """Save relationship table and QA outputs."""
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    qa_dir.mkdir(parents=True, exist_ok=True)

    relationship_df.to_csv(output_csv_path, index=False)
    try:
        compact_catalogue_df.to_csv(compact_catalogue_csv_path, index=False)
    except PermissionError:
        print(f"Could not overwrite locked compact catalogue CSV: {compact_catalogue_csv_path}")
    coverage_exclusions_df.to_csv(qa_dir / "coverage_exclusions.csv", index=False)
    esto_combined_rows_df.to_csv(qa_dir / "esto_combined_rows.csv", index=False)
    esto_overrides_df.to_csv(qa_dir / "common_esto_overrides.csv", index=False)
    def write_workbook(path: Path) -> None:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            relationship_df.to_excel(writer, sheet_name="energy_balance_relationships", index=False)
            relationship_catalogue_df.to_excel(writer, sheet_name="relationship_catalogue", index=False)
            compact_catalogue_df.to_excel(writer, sheet_name="relationship_catalogue_6_col", index=False)
            coverage_exclusions_df.to_excel(writer, sheet_name="coverage_exclusions", index=False)
            esto_combined_rows_df.to_excel(writer, sheet_name="esto_combined_rows", index=False)
            for qa_name, qa_df in qa_tables.items():
                qa_df.to_excel(writer, sheet_name=QA_SHEET_NAMES.get(qa_name, qa_name[:31]), index=False)

    workbook_output_path = output_xlsx_path
    try:
        write_workbook(workbook_output_path)
        pd.ExcelFile(workbook_output_path).close()
    except Exception as exc:
        workbook_output_path = output_xlsx_path.with_name(f"{output_xlsx_path.stem}_rebuilt{output_xlsx_path.suffix}")
        print(f"Could not create a valid canonical workbook ({exc}). Writing rebuilt workbook to: {workbook_output_path}")
        write_workbook(workbook_output_path)

    for qa_name, qa_df in qa_tables.items():
        qa_df.to_csv(qa_dir / QA_FILENAMES[qa_name], index=False)


def run_relationship_workflow(
    mapping_workbook_path: Path,
    fallback_workbook_path: Path,
    sheet_configs: list[dict[str, Any]],
    output_csv_path: Path,
    output_xlsx_path: Path,
    compact_catalogue_csv_path: Path,
    qa_dir: Path,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Run the full energy-balance relationship workflow."""
    relationship_frames: list[pd.DataFrame] = []
    source_row_counts: dict[str, int] = {}
    for sheet_config in sheet_configs:
        sheet_name = sheet_config["sheet_name"]
        source_df, source_path = read_configured_sheet(
            primary_workbook_path=mapping_workbook_path,
            fallback_workbook_path=fallback_workbook_path,
            sheet_name=sheet_name,
        )
        if source_df is None or source_path is None:
            print(f"Skipped missing sheet: {sheet_name}")
            continue
        source_row_counts[sheet_name] = len(source_df)
        relationship_frames.append(
            build_relationship_rows(
                source_df=source_df,
                source_mapping_path=source_path,
                sheet_config=sheet_config,
            )
        )

    if not relationship_frames:
        raise ValueError("No configured mapping sheets were found.")

    base_df = pd.concat(relationship_frames, ignore_index=True)

    # Expand combined ESTO targets and apply rollup rules
    flow_prefix_to_label = _build_flow_prefix_to_label(mapping_workbook_path)
    base_df = expand_combined_esto_targets(base_df, flow_prefix_to_label)
    leap_rules, esto_rules, ninth_rules = load_rollup_rules(mapping_workbook_path)
    rolled_flow_to_components = _build_rolled_flow_to_components(esto_rules)
    rows_before_rollup_expansion = len(base_df)
    base_df = expand_esto_rollup_targets(base_df, rolled_flow_to_components)
    if len(base_df) != rows_before_rollup_expansion:
        print(f"ESTO rollup target expansion: {rows_before_rollup_expansion:,} -> {len(base_df):,} rows")
    leap_rollup_df = _apply_leap_rollup_rules(base_df, leap_rules)
    ninth_rollup_df = _apply_ninth_rollup_rules(base_df, ninth_rules)
    esto_overrides_df = build_esto_overrides(esto_rules)

    all_frames = [base_df]
    if not leap_rollup_df.empty:
        all_frames.append(leap_rollup_df)
    if not ninth_rollup_df.empty:
        all_frames.append(ninth_rollup_df)
    relationship_df = pd.concat(all_frames, ignore_index=True)

    print(f"Base relationship rows (after expansion): {len(base_df):,}")
    if not leap_rollup_df.empty:
        print(f"LEAP rollup rows added: {len(leap_rollup_df):,}")
    if not ninth_rollup_df.empty:
        print(f"NINTH rollup rows added: {len(ninth_rollup_df):,}")
    print(f"ESTO override entries: {len(esto_overrides_df):,}")

    known_esto_flows = _load_known_esto_flows(mapping_workbook_path)
    if known_esto_flows:
        unknown_esto_qa_df = build_unknown_esto_target_qa(relationship_df, known_esto_flows)
        qa_dir.mkdir(parents=True, exist_ok=True)
        unknown_esto_qa_df.to_csv(qa_dir / "qa_unknown_esto_target_flows.csv", index=False)
        if not unknown_esto_qa_df.empty:
            unknown_count = unknown_esto_qa_df["target_flow"].nunique()
            print(
                f"WARNING: {unknown_count} ESTO target flow labels match no real ESTO flow and no "
                "esto_rollup_rules rollup; their comparisons will have no ESTO data. "
                "See qa_unknown_esto_target_flows.csv"
            )

    relationship_catalogue_df = build_relationship_catalogue(relationship_df)
    compact_catalogue_df = build_compact_relationship_catalogue(relationship_df)
    coverage_exclusions_df = read_optional_config_table(
        primary_workbook_path=mapping_workbook_path,
        fallback_workbook_path=fallback_workbook_path,
        sheet_name="coverage_exclusions",
        columns=COVERAGE_EXCLUSION_COLUMNS,
        default_df=build_default_coverage_exclusions(),
    )
    esto_combined_rows_df = read_optional_config_table(
        primary_workbook_path=mapping_workbook_path,
        fallback_workbook_path=fallback_workbook_path,
        sheet_name="esto_combined_rows",
        columns=ESTO_COMBINED_ROW_COLUMNS,
    )
    qa_tables = build_conversion_qa_tables(
        relationship_df,
        coverage_exclusions_df=coverage_exclusions_df,
        esto_combined_rows_df=esto_combined_rows_df,
        use_case="leap_to_esto_balance_conversion",
    )
    save_relationship_outputs(
        relationship_df=relationship_df,
        relationship_catalogue_df=relationship_catalogue_df,
        compact_catalogue_df=compact_catalogue_df,
        coverage_exclusions_df=coverage_exclusions_df,
        esto_combined_rows_df=esto_combined_rows_df,
        esto_overrides_df=esto_overrides_df,
        qa_tables=qa_tables,
        output_csv_path=output_csv_path,
        output_xlsx_path=output_xlsx_path,
        compact_catalogue_csv_path=compact_catalogue_csv_path,
        qa_dir=qa_dir,
    )

    included_by_use_case = relationship_df.groupby("use_case")["include_in_use_case"].sum()
    total_by_use_case = relationship_df.groupby("use_case")["include_in_use_case"].size()
    excluded_by_use_case = total_by_use_case - included_by_use_case
    conversion_summary = qa_tables["leap_to_esto_coverage_summary"].set_index("metric")["value"].to_dict()

    for sheet_name, row_count in source_row_counts.items():
        print(f"Source rows read from {sheet_name}: {row_count:,}")
    print(f"Relationship rows created: {len(relationship_df):,}")
    print(f"Relationship catalogue rows: {len(relationship_catalogue_df):,}")
    print(f"Compact six-column catalogue rows: {len(compact_catalogue_df):,}")
    for use_case in USE_CASES:
        print(
            f"{use_case}: included={int(included_by_use_case.get(use_case, 0)):,}, "
            f"excluded={int(excluded_by_use_case.get(use_case, 0)):,}"
        )
    print(f"remove_row true count: {int(relationship_df['remove_row'].apply(parse_remove_row).sum()):,}")
    print(f"Unique LEAP source pairs: {int(conversion_summary.get('unique_leap_source_pairs', 0)):,}")
    print(f"Unique ESTO target pairs: {int(conversion_summary.get('unique_esto_target_pairs', 0)):,}")
    print(f"Missing source count: {int(conversion_summary.get('esto_targets_without_leap_source', 0)):,}")
    print(f"Missing target count: {int(conversion_summary.get('leap_sources_without_esto_target', 0)):,}")
    print(f"Missing dataset pairs by use case: {int(conversion_summary.get('missing_dataset_pairs_by_use_case', 0)):,}")
    print(f"Not-considered ESTO rows: {int(conversion_summary.get('not_considered_esto_rows', 0)):,}")
    print(f"Duplicate source groups: {int(conversion_summary.get('duplicate_source_groups', 0)):,}")
    print(f"Duplicate target groups: {int(conversion_summary.get('duplicate_target_groups', 0)):,}")
    print(
        "One-to-many allocation/combined-target issues: "
        f"{int(conversion_summary.get('one_to_many_allocation_or_combined_target_issues', 0)):,}"
    )
    print(f"Parent/child risk count: {int(conversion_summary.get('parent_child_risk_rows', 0)):,}")
    print(f"Wrote relationships CSV: {output_csv_path}")
    print(f"Wrote relationships workbook: {output_xlsx_path}")
    print(f"Wrote QA files to: {qa_dir}")

    return relationship_df, qa_tables

#%%
# User-tuned constants / flags.
SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = _find_repo_root(SCRIPT_PATH.parent)

MAPPING_WORKBOOK_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
FALLBACK_WORKBOOK_PATH = REPO_ROOT / "config" / "master_config.xlsx"
OUTPUT_DIR = REPO_ROOT / "results" / "mapping_relationships"
OUTPUT_CSV_PATH = OUTPUT_DIR / "energy_balance_relationships.csv"
OUTPUT_XLSX_PATH = OUTPUT_DIR / "energy_balance_relationships.xlsx"
COMPACT_CATALOGUE_CSV_PATH = OUTPUT_DIR / "relationship_catalogue_6_col.csv"
QA_DIR = OUTPUT_DIR

RUN_BUILD_ENERGY_BALANCE_RELATIONSHIPS = True

#%%
if __name__ == "__main__":
    try:
        if RUN_BUILD_ENERGY_BALANCE_RELATIONSHIPS:
            run_relationship_workflow(
                mapping_workbook_path=MAPPING_WORKBOOK_PATH,
                fallback_workbook_path=FALLBACK_WORKBOOK_PATH,
                sheet_configs=SHEET_CONFIGS,
                output_csv_path=OUTPUT_CSV_PATH,
                output_xlsx_path=OUTPUT_XLSX_PATH,
                compact_catalogue_csv_path=COMPACT_CATALOGUE_CSV_PATH,
                qa_dir=QA_DIR,
            )
    except Exception as exc:
        print("Energy-balance relationship build failed.")
        print(f"Error: {exc}")
        raise

#%%

