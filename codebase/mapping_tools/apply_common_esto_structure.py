#%%
"""
Apply the generated common ESTO structure to ESTO-shaped source data.

Input data should already be converted to ESTO-style rows with source_system,
economy, scenario, year, ESTO flow/product, and value columns.
"""

#%%
from pathlib import Path
import sys

import pandas as pd

SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from codebase.mapping_issue_exceptions import row_is_allowed

#%%
OUTPUT_COLUMNS = [
    "comparison_scope",
    "source_system",
    "economy",
    "scenario",
    "year",
    "common_flow_code",
    "common_flow_name",
    "common_flow_label",
    "common_product_code",
    "common_product_name",
    "common_product_label",
    "value",
]
COMPARISON_INTERNAL_COLUMNS = [
    "common_row_id",
    "common_component_count",
    "common_flow_component_count",
    "common_product_component_count",
]
WIDE_OUTPUT_ID_COLUMNS = ["economy", "scenario", "product", "flow"]
SOURCE_VALUE_COLUMNS = ["source_system", "economy", "scenario", "year", "esto_flow", "esto_product", "value"]
SOURCE_VALUE_SCOPE_COLUMNS = ["comparison_scope"] + SOURCE_VALUE_COLUMNS
TOTAL_GROUP_COLUMNS = ["comparison_scope", "source_system", "economy", "scenario", "year"]
SUBTOTAL_KEYWORDS = ["total", "subtotal"]
BROAD_COMMON_ROW_COMPONENT_LIMIT = 50
ACTIVE_COMPONENT_ABS_TOLERANCE = 0.0
NINTH_PROJECTION_START_YEAR = 2023
COMPARISON_SCOPE_SYSTEMS = {
    "leap_vs_esto": {"LEAP", "ESTO"},
    "leap_vs_ninth": {"LEAP", "NINTH"},
    "leap_vs_esto_vs_ninth": {"LEAP", "NINTH", "ESTO"},
    "esto_only": {"ESTO"},
}

#%%
def _find_repo_root(start_path: Path) -> Path:
    """Find the leap_mappings repo root from a nested workflow path."""
    for candidate in [start_path, *start_path.parents]:
        if (candidate / "AGENTS.md").exists() and (candidate / "config" / "outlook_mappings_master.xlsx").exists():
            return candidate
    raise FileNotFoundError(f"Could not find repo root above: {start_path}")


def read_table_if_exists(path: Path) -> pd.DataFrame:
    """Read CSV/XLSX input if it exists, otherwise return an empty table."""
    if not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def normalise_label(value: object) -> str:
    """Collapse whitespace in labels used as join keys."""
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def should_ignore_missing_common_map_flow(esto_flow: object) -> bool:
    """Return True for missing-map diagnostic flows that are intentionally ignored."""
    return row_is_allowed(
        pd.Series({"esto_flow": normalise_label(esto_flow)}),
        sheet_name="missing_common_map_ignored",
    )


def filter_missing_common_map_diagnostics(missing_map_df: pd.DataFrame) -> pd.DataFrame:
    """Remove intentionally ignored ESTO flows from the missing common-map diagnostic."""
    if missing_map_df.empty or "esto_flow" not in missing_map_df.columns:
        return missing_map_df.copy()
    ignored_mask = missing_map_df["esto_flow"].map(should_ignore_missing_common_map_flow)
    return missing_map_df[~ignored_mask].copy()


def normalise_source_columns(source_df: pd.DataFrame, default_source_system: str, default_economy: str) -> pd.DataFrame:
    """Normalise a source table to source_system/economy/scenario/year/esto/value columns."""
    if source_df.empty:
        return pd.DataFrame(columns=SOURCE_VALUE_COLUMNS)
    working_df = source_df.copy()
    rename_map = {}
    if "target_flow" in working_df.columns and "esto_flow" not in working_df.columns:
        rename_map["target_flow"] = "esto_flow"
    if "target_product" in working_df.columns and "esto_product" not in working_df.columns:
        rename_map["target_product"] = "esto_product"
    if "component_esto_flow" in working_df.columns and "esto_flow" not in working_df.columns:
        rename_map["component_esto_flow"] = "esto_flow"
    if "component_esto_product" in working_df.columns and "esto_product" not in working_df.columns:
        rename_map["component_esto_product"] = "esto_product"
    if "value_pj" in working_df.columns and "value" not in working_df.columns:
        rename_map["value_pj"] = "value"
    working_df = working_df.rename(columns=rename_map)

    if "source_system" not in working_df.columns:
        working_df["source_system"] = default_source_system
    if "economy" not in working_df.columns:
        working_df["economy"] = default_economy
    for column in ["scenario", "year"]:
        if column not in working_df.columns:
            working_df[column] = ""

    missing_columns = [column for column in ["esto_flow", "esto_product", "value"] if column not in working_df.columns]
    if missing_columns:
        raise ValueError(f"Source data for {default_source_system} is missing required columns: {missing_columns}")

    working_df["esto_flow"] = working_df["esto_flow"].map(normalise_label)
    working_df["esto_product"] = working_df["esto_product"].map(normalise_label)
    working_df["value"] = pd.to_numeric(working_df["value"], errors="coerce").fillna(0)
    if "comparison_scope" in working_df.columns:
        return working_df[SOURCE_VALUE_SCOPE_COLUMNS].copy()
    return working_df[SOURCE_VALUE_COLUMNS].copy()


def read_source_tables(source_paths: dict[str, Path], default_economy: str) -> pd.DataFrame:
    """Read and concatenate available ESTO-shaped source tables."""
    frames: list[pd.DataFrame] = []
    for source_system, path in source_paths.items():
        source_df = read_table_if_exists(path)
        if source_df.empty:
            print(f"Skipped missing or empty {source_system} source data: {path}")
            continue
        frames.append(normalise_source_columns(source_df, default_source_system=source_system, default_economy=default_economy))
        print(f"{source_system} ESTO-shaped rows read: {len(source_df):,}")
    if not frames:
        return pd.DataFrame(columns=SOURCE_VALUE_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def split_code_name(label: object) -> tuple[str, str]:
    """Split an ESTO label into leading code and display name."""
    text = "" if pd.isna(label) else str(label).strip()
    if not text:
        return "", ""
    parts = text.split(" ", 1)
    if len(parts) == 1:
        return text, text
    return parts[0].strip(), parts[1].strip()


def code_sort_key(code: str) -> tuple[object, ...]:
    """Sort dotted numeric-ish ESTO codes in a stable human order."""
    parts: list[object] = []
    for part in str(code).replace("-", ".").split("."):
        if not part:
            continue
        parts.append(int(part) if part.isdigit() else part)
    return tuple(parts)


def compress_codes(codes: list[str]) -> str:
    """Compress adjacent dotted codes like 01.02, 01.03, 01.04 into 01.02-01.04."""
    cleaned_codes = sorted({str(code).strip() for code in codes if str(code).strip()}, key=code_sort_key)
    if not cleaned_codes:
        return ""

    ranges: list[str] = []
    start = cleaned_codes[0]
    previous = cleaned_codes[0]

    def adjacent(left: str, right: str) -> bool:
        left_prefix, _, left_tail = left.rpartition(".")
        right_prefix, _, right_tail = right.rpartition(".")
        if not left_prefix or left_prefix != right_prefix:
            return False
        if not left_tail.isdigit() or not right_tail.isdigit():
            return False
        return int(right_tail) == int(left_tail) + 1

    for code in cleaned_codes[1:]:
        if adjacent(previous, code):
            previous = code
            continue
        ranges.append(start if start == previous else f"{start}-{previous}")
        start = code
        previous = code
    ranges.append(start if start == previous else f"{start}-{previous}")
    return ",".join(ranges)


def make_label(code: str, name: str) -> str:
    """Combine code and name while tolerating missing names."""
    if code and name:
        return f"{code} {name}"
    return code or name


def nonzero_source_rows(source_df: pd.DataFrame, active_component_abs_tolerance: float) -> pd.DataFrame:
    """Drop zero-value rows before data-aware component pruning and mapping."""
    if source_df.empty:
        return source_df.copy()
    value_abs = pd.to_numeric(source_df["value"], errors="coerce").fillna(0).abs()
    return source_df[value_abs > active_component_abs_tolerance].copy()


def build_component_relevance(
    source_df: pd.DataFrame,
    active_component_abs_tolerance: float,
    ninth_projection_start_year: int,
    esto_base_year: int | None = None,
) -> tuple[pd.DataFrame, int | None]:
    """Return ESTO pairs with non-zero evidence in the periods used for mapping QA.

    ESTO contributes only its latest available base year unless a year is
    supplied explicitly. NINTH contributes projection years only. Mapped LEAP
    rows contribute every exported balance year because LEAP exports are
    already selected model results rather than a full historical time series.
    """
    columns = [
        "component_esto_flow",
        "component_esto_product",
        "esto_base_year_nonzero",
        "ninth_projection_nonzero",
        "mapped_leap_balance_nonzero",
        "unmapped_leap_balance_nonzero",
        "relevance_reasons",
    ]
    if source_df.empty:
        return pd.DataFrame(columns=columns), esto_base_year

    working_df = source_df.copy()
    working_df["year"] = pd.to_numeric(working_df["year"], errors="coerce")
    working_df["value"] = pd.to_numeric(working_df["value"], errors="coerce").fillna(0)
    working_df["source_system"] = working_df["source_system"].astype(str).str.upper().str.strip()
    nonzero_mask = working_df["value"].abs() > active_component_abs_tolerance

    esto_years = working_df.loc[
        (working_df["source_system"] == "ESTO") & working_df["year"].notna(),
        "year",
    ]
    resolved_esto_base_year = esto_base_year
    if resolved_esto_base_year is None and not esto_years.empty:
        resolved_esto_base_year = int(esto_years.max())

    evidence_masks = {
        "esto_base_year_nonzero": (
            (working_df["source_system"] == "ESTO")
            & (working_df["year"] == resolved_esto_base_year)
            & nonzero_mask
        ),
        "ninth_projection_nonzero": (
            (working_df["source_system"] == "NINTH")
            & (working_df["year"] >= ninth_projection_start_year)
            & nonzero_mask
        ),
        "mapped_leap_balance_nonzero": (
            (working_df["source_system"] == "LEAP")
            & nonzero_mask
        ),
    }

    evidence_frames: list[pd.DataFrame] = []
    pair_columns = ["esto_flow", "esto_product"]
    for evidence_column, mask in evidence_masks.items():
        evidence_df = working_df.loc[mask, pair_columns].drop_duplicates().copy()
        if evidence_df.empty:
            continue
        evidence_df[evidence_column] = True
        evidence_frames.append(evidence_df)

    if not evidence_frames:
        return pd.DataFrame(columns=columns), resolved_esto_base_year

    relevance_df = evidence_frames[0]
    for evidence_df in evidence_frames[1:]:
        relevance_df = relevance_df.merge(evidence_df, on=pair_columns, how="outer")
    relevance_df = relevance_df.rename(
        columns={
            "esto_flow": "component_esto_flow",
            "esto_product": "component_esto_product",
        }
    )
    for evidence_column in [
        "esto_base_year_nonzero",
        "ninth_projection_nonzero",
        "mapped_leap_balance_nonzero",
    ]:
        if evidence_column not in relevance_df.columns:
            relevance_df[evidence_column] = False
        relevance_df[evidence_column] = relevance_df[evidence_column].fillna(False).astype(bool)
    relevance_df["unmapped_leap_balance_nonzero"] = False
    reason_columns = [
        "esto_base_year_nonzero",
        "ninth_projection_nonzero",
        "mapped_leap_balance_nonzero",
        "unmapped_leap_balance_nonzero",
    ]
    relevance_df["relevance_reasons"] = relevance_df.apply(
        lambda row: "|".join(column for column in reason_columns if bool(row[column])),
        axis=1,
    )
    return relevance_df[columns], resolved_esto_base_year


def build_unmapped_leap_branch_evidence(
    raw_leap_df: pd.DataFrame,
    leap_esto_df: pd.DataFrame,
    leap_ninth_df: pd.DataFrame,
    ninth_esto_df: pd.DataFrame,
    active_component_abs_tolerance: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Audit non-zero LEAP branches without direct ESTO mappings.

    An indirect ESTO pair is accepted as relevance evidence only when the
    branch can be followed through LEAP-to-NINTH and NINTH-to-ESTO mappings.
    Branches without that chain remain branch-level review findings.
    """
    audit_columns = [
        "leap_flow",
        "leap_product",
        "indirect_esto_flow",
        "indirect_esto_product",
        "qa_status",
        "qa_severity",
    ]
    relevance_columns = [
        "component_esto_flow",
        "component_esto_product",
        "unmapped_leap_balance_nonzero",
    ]
    if raw_leap_df.empty:
        return pd.DataFrame(columns=audit_columns), pd.DataFrame(columns=relevance_columns)

    def clean_text(series: pd.Series) -> pd.Series:
        return series.fillna("").astype(str).str.strip().str.replace("\\\\", "/", regex=False)

    raw_df = raw_leap_df.copy()
    raw_df["value"] = pd.to_numeric(raw_df["value"], errors="coerce").fillna(0)
    raw_df = raw_df[raw_df["value"].abs() > active_component_abs_tolerance].copy()
    if raw_df.empty:
        return pd.DataFrame(columns=audit_columns), pd.DataFrame(columns=relevance_columns)
    raw_df["leap_flow"] = clean_text(raw_df["leap_flow"])
    raw_df["leap_product"] = clean_text(raw_df["leap_product"])
    observed_df = raw_df[["leap_flow", "leap_product"]].drop_duplicates()

    direct_df = leap_esto_df.copy()
    direct_df["leap_sector_name_full_path"] = clean_text(direct_df["leap_sector_name_full_path"])
    direct_df["raw_leap_fuel_name"] = clean_text(direct_df["raw_leap_fuel_name"])
    direct_pairs = direct_df[["leap_sector_name_full_path", "raw_leap_fuel_name"]].drop_duplicates()
    unmapped_df = observed_df.merge(
        direct_pairs.assign(_direct_mapping=True),
        left_on=["leap_flow", "leap_product"],
        right_on=["leap_sector_name_full_path", "raw_leap_fuel_name"],
        how="left",
    )
    unmapped_df = unmapped_df[unmapped_df["_direct_mapping"].isna()][["leap_flow", "leap_product"]]
    if unmapped_df.empty:
        return pd.DataFrame(columns=audit_columns), pd.DataFrame(columns=relevance_columns)

    leap_ninth = leap_ninth_df.copy()
    for column in ["leap_sector_name_full_path", "raw_leap_fuel_name", "ninth_sector", "ninth_fuel"]:
        leap_ninth[column] = clean_text(leap_ninth[column])
    ninth_esto = ninth_esto_df.copy()
    for column in ["9th_sector", "9th_fuel", "esto_flow", "esto_product"]:
        ninth_esto[column] = clean_text(ninth_esto[column])

    audit_df = unmapped_df.merge(
        leap_ninth[["leap_sector_name_full_path", "raw_leap_fuel_name", "ninth_sector", "ninth_fuel"]],
        left_on=["leap_flow", "leap_product"],
        right_on=["leap_sector_name_full_path", "raw_leap_fuel_name"],
        how="left",
    ).merge(
        ninth_esto[["9th_sector", "9th_fuel", "esto_flow", "esto_product"]],
        left_on=["ninth_sector", "ninth_fuel"],
        right_on=["9th_sector", "9th_fuel"],
        how="left",
    )
    audit_df["indirect_esto_flow"] = clean_text(audit_df["esto_flow"])
    audit_df["indirect_esto_product"] = clean_text(audit_df["esto_product"])
    has_indirect_pair = audit_df["indirect_esto_flow"].ne("") & audit_df["indirect_esto_product"].ne("")
    audit_df["qa_status"] = "nonzero_unmapped_leap_branch_without_esto_pair"
    audit_df.loc[has_indirect_pair, "qa_status"] = "nonzero_unmapped_leap_branch_with_indirect_esto_pair"
    audit_df["qa_severity"] = "review"
    audit_df = audit_df[audit_columns].drop_duplicates().sort_values(["qa_status", "leap_flow", "leap_product"])

    relevance_df = audit_df.loc[
        audit_df["indirect_esto_flow"].ne("") & audit_df["indirect_esto_product"].ne(""),
        ["indirect_esto_flow", "indirect_esto_product"],
    ].drop_duplicates().rename(
        columns={
            "indirect_esto_flow": "component_esto_flow",
            "indirect_esto_product": "component_esto_product",
        }
    )
    relevance_df["unmapped_leap_balance_nonzero"] = True
    return audit_df, relevance_df[relevance_columns]


def merge_component_relevance(
    relevance_df: pd.DataFrame,
    unmapped_leap_relevance_df: pd.DataFrame,
) -> pd.DataFrame:
    """Merge direct source evidence with indirectly inferred LEAP evidence."""
    if unmapped_leap_relevance_df.empty:
        return relevance_df.copy()
    pair_columns = ["component_esto_flow", "component_esto_product"]
    combined_df = relevance_df.merge(unmapped_leap_relevance_df, on=pair_columns, how="outer", suffixes=("", "_indirect"))
    for column in [
        "esto_base_year_nonzero",
        "ninth_projection_nonzero",
        "mapped_leap_balance_nonzero",
        "unmapped_leap_balance_nonzero",
    ]:
        direct_values = combined_df[column] if column in combined_df.columns else False
        indirect_column = f"{column}_indirect"
        indirect_values = combined_df[indirect_column] if indirect_column in combined_df.columns else False
        combined_df[column] = pd.Series(direct_values, index=combined_df.index).fillna(False).astype(bool) | pd.Series(
            indirect_values, index=combined_df.index
        ).fillna(False).astype(bool)
    reason_columns = [
        "esto_base_year_nonzero",
        "ninth_projection_nonzero",
        "mapped_leap_balance_nonzero",
        "unmapped_leap_balance_nonzero",
    ]
    combined_df["relevance_reasons"] = combined_df.apply(
        lambda row: "|".join(column for column in reason_columns if bool(row[column])),
        axis=1,
    )
    return combined_df[pair_columns + reason_columns + ["relevance_reasons"]].drop_duplicates()


def filter_partial_coverage_by_relevance(
    structural_partial_df: pd.DataFrame,
    relevance_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep only data-relevant missing pairs and audit inactive candidates."""
    if structural_partial_df.empty:
        return structural_partial_df.copy(), pd.DataFrame()
    relevance_lookup = {
        (str(row["component_esto_flow"]).strip(), str(row["component_esto_product"]).strip()): str(row["relevance_reasons"])
        for _, row in relevance_df.iterrows()
    }
    actionable_rows: list[dict[str, object]] = []
    inactive_rows: list[dict[str, object]] = []
    for _, row in structural_partial_df.iterrows():
        structural_pairs: list[tuple[str, str]] = []
        for text_pair in str(row.get("missing_component_pairs", "")).split("|"):
            if " :: " not in text_pair:
                continue
            flow, product = text_pair.split(" :: ", 1)
            structural_pairs.append((flow.strip(), product.strip()))
        relevant_pairs = [pair for pair in structural_pairs if pair in relevance_lookup]
        inactive_pairs = [pair for pair in structural_pairs if pair not in relevance_lookup]
        if relevant_pairs:
            output_row = row.to_dict()
            output_row["structural_missing_component_pairs"] = row.get("missing_component_pairs", "")
            output_row["missing_component_pairs"] = "|".join(f"{flow} :: {product}" for flow, product in relevant_pairs)
            output_row["relevant_missing_component_count"] = len(relevant_pairs)
            output_row["relevance_evidence"] = "|".join(
                f"{flow} :: {product} [{relevance_lookup[(flow, product)]}]" for flow, product in relevant_pairs
            )
            actionable_rows.append(output_row)
        for flow, product in inactive_pairs:
            inactive_row = row.to_dict()
            inactive_row["inactive_component_esto_flow"] = flow
            inactive_row["inactive_component_esto_product"] = product
            inactive_row["inactive_reason"] = "no_nonzero_esto_base_ninth_projection_or_leap_balance_evidence"
            inactive_row["qa_status"] = "partial_coverage_component_without_relevance"
            inactive_row["qa_severity"] = "info"
            inactive_rows.append(inactive_row)
    return pd.DataFrame(actionable_rows), pd.DataFrame(inactive_rows)


def relabel_common_rows_for_active_components(
    relevance_df: pd.DataFrame,
    common_rows_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Prune components without current-run relevance evidence."""
    if relevance_df.empty or common_rows_df.empty:
        return common_rows_df.copy(), pd.DataFrame()

    active_pairs_df = relevance_df[["component_esto_flow", "component_esto_product"]].drop_duplicates()
    working_df = common_rows_df.merge(
        active_pairs_df.assign(_active_component=True),
        on=["component_esto_flow", "component_esto_product"],
        how="left",
    )
    active_mask = working_df["_active_component"].fillna(False).astype(bool)
    pruned_df = working_df[~active_mask].drop(columns=["_active_component"]).copy()
    adjusted_df = working_df[active_mask].drop(columns=["_active_component"]).copy()
    if pruned_df.empty or adjusted_df.empty:
        return adjusted_df, pruned_df

    for boolean_column in ["is_exact_row", "requires_rollup"]:
        if boolean_column in adjusted_df.columns:
            adjusted_df[boolean_column] = adjusted_df[boolean_column].astype(object)

    pruned_df["prune_status"] = "component_not_needed_for_current_comparison_data"
    pruned_df["prune_reason"] = "no_nonzero_esto_base_ninth_projection_or_leap_balance_evidence"

    return adjusted_df, pruned_df


def save_component_pruning_diagnostics(pruned_components_df: pd.DataFrame, output_dir: Path) -> None:
    """Write diagnostics for components pruned as not applicable for this run."""
    diagnostics_dir = output_dir / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    pruned_components_df.to_csv(diagnostics_dir / "common_esto_components_pruned_not_applicable.csv", index=False)


def save_relevance_diagnostics(
    relevance_df: pd.DataFrame,
    pruned_components_df: pd.DataFrame,
    leap_branch_audit_df: pd.DataFrame,
    actionable_partial_df: pd.DataFrame,
    inactive_partial_df: pd.DataFrame,
    output_dir: Path,
) -> None:
    """Write data-relevance evidence and the resulting QA classifications."""
    diagnostics_dir = output_dir / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    relevance_df.to_csv(diagnostics_dir / "common_esto_component_relevance.csv", index=False)
    pruned_components_df.to_csv(output_dir / "qa_common_esto_existing_components_without_relevance.csv", index=False)
    leap_branch_audit_df.to_csv(output_dir / "qa_nonzero_unmapped_leap_branches.csv", index=False)
    actionable_partial_df.to_csv(output_dir / "qa_common_esto_unresolved_partial_coverage.csv", index=False)
    inactive_partial_df.to_csv(output_dir / "qa_common_esto_partial_coverage_components_without_relevance.csv", index=False)


def apply_common_structure(source_df: pd.DataFrame, common_rows_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Join ESTO-shaped source rows to common rows and aggregate values."""
    if source_df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS), pd.DataFrame(), pd.DataFrame(columns=SOURCE_VALUE_SCOPE_COLUMNS)
    map_columns = [
        "comparison_scope",
        "component_esto_flow",
        "component_esto_product",
        "common_row_id",
        "common_flow_code",
        "common_flow_name",
        "common_flow_label",
        "common_product_code",
        "common_product_name",
        "common_product_label",
        "component_sign",
    ]
    map_df = common_rows_df[map_columns].drop_duplicates().copy()
    component_counts_df = (
        common_rows_df.groupby(["comparison_scope", "common_row_id"], dropna=False)
        .agg(
            common_component_count=("component_esto_product", "size"),
            common_flow_component_count=("component_esto_flow", "nunique"),
            common_product_component_count=("component_esto_product", "nunique"),
        )
        .reset_index()
    )
    map_df = map_df.merge(component_counts_df, on=["comparison_scope", "common_row_id"], how="left")
    if "comparison_scope" not in source_df.columns:
        scopes_df = map_df[["comparison_scope"]].drop_duplicates()
        expanded_frames: list[pd.DataFrame] = []
        for _, scope_row in scopes_df.iterrows():
            comparison_scope = str(scope_row["comparison_scope"])
            allowed_systems = COMPARISON_SCOPE_SYSTEMS.get(comparison_scope)
            if allowed_systems is None:
                scoped_source_df = source_df.copy()
            else:
                scoped_source_df = source_df[source_df["source_system"].isin(allowed_systems)].copy()
            if scoped_source_df.empty:
                continue
            scoped_source_df["comparison_scope"] = comparison_scope
            expanded_frames.append(scoped_source_df)
        source_df = pd.concat(expanded_frames, ignore_index=True) if expanded_frames else pd.DataFrame(columns=SOURCE_VALUE_SCOPE_COLUMNS)
    else:
        source_df = source_df.copy()
        valid_scope_mask = source_df.apply(
            lambda row: row["source_system"] in COMPARISON_SCOPE_SYSTEMS.get(str(row["comparison_scope"]), {row["source_system"]}),
            axis=1,
        )
        source_df = source_df[valid_scope_mask].copy()
    merged_df = source_df.merge(
        map_df,
        left_on=["comparison_scope", "esto_flow", "esto_product"],
        right_on=["comparison_scope", "component_esto_flow", "component_esto_product"],
        how="left",
    )
    missing_map_df = merged_df[merged_df["common_row_id"].isna()].copy()
    mapped_df = merged_df.dropna(subset=["common_row_id"]).copy()
    mapped_df["component_sign"] = pd.to_numeric(mapped_df["component_sign"], errors="coerce").fillna(1)
    mapped_df["value"] = mapped_df["value"] * mapped_df["component_sign"]
    mapped_source_df = mapped_df[SOURCE_VALUE_SCOPE_COLUMNS].copy()
    group_columns = OUTPUT_COLUMNS[:-1] + COMPARISON_INTERNAL_COLUMNS
    comparison_df = (
        mapped_df.groupby(group_columns, dropna=False, as_index=False)["value"]
        .sum()
        .sort_values(OUTPUT_COLUMNS[:-1])
        .reset_index(drop=True)
    )
    return comparison_df, missing_map_df, mapped_source_df


def is_subtotal_label(value: object) -> bool:
    """Return True for labels that should be filtered from final outputs."""
    text = "" if pd.isna(value) else str(value).strip().lower()
    return any(keyword in text for keyword in SUBTOTAL_KEYWORDS)


def split_subtotal_rows(comparison_df: pd.DataFrame, exclude_subtotal_rows: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split final comparison rows into kept rows and subtotal/total audit rows."""
    if comparison_df.empty or not exclude_subtotal_rows:
        return comparison_df.copy(), pd.DataFrame(columns=list(comparison_df.columns) + ["subtotal_filter_reason"])

    flow_mask = comparison_df["common_flow_label"].map(is_subtotal_label)
    product_mask = comparison_df["common_product_label"].map(is_subtotal_label)
    subtotal_mask = flow_mask | product_mask
    subtotal_df = comparison_df[subtotal_mask].copy()
    kept_df = comparison_df[~subtotal_mask].copy()
    if not subtotal_df.empty:
        subtotal_df["subtotal_filter_reason"] = ""
        subtotal_df.loc[flow_mask[subtotal_mask].values, "subtotal_filter_reason"] = "common_flow_label_contains_total_or_subtotal"
        both_mask = flow_mask & product_mask
        subtotal_df.loc[both_mask[subtotal_mask].values, "subtotal_filter_reason"] = "common_flow_and_product_labels_contain_total_or_subtotal"
        product_only_mask = product_mask & ~flow_mask
        subtotal_df.loc[product_only_mask[subtotal_mask].values, "subtotal_filter_reason"] = "common_product_label_contains_total_or_subtotal"
    return kept_df, subtotal_df


def build_broad_common_row_diagnostics(
    common_rows_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
    broad_component_limit: int,
) -> dict[str, pd.DataFrame]:
    """Build diagnostics for broad common rows that need mapping review."""
    component_counts_df = (
        common_rows_df.groupby(
            [
                "common_row_id",
                "common_flow_label",
                "common_product_label",
                "aggregation_reason",
                "aggregate_group_source",
                "aggregate_group_source_id",
            ],
            dropna=False,
        )
        .agg(
            exact_component_count=("component_esto_product", "size"),
            exact_flow_count=("component_esto_flow", "nunique"),
            exact_product_count=("component_esto_product", "nunique"),
        )
        .reset_index()
    )
    broad_summary_df = component_counts_df[
        component_counts_df["exact_component_count"] > broad_component_limit
    ].copy()
    if broad_summary_df.empty:
        return {
            "broad_common_row_summary": broad_summary_df,
            "broad_common_row_components": pd.DataFrame(),
            "broad_common_row_affected_output": pd.DataFrame(),
        }

    broad_summary_df["qa_status"] = "mapping_revision_required"
    broad_summary_df["qa_status"] = "review_broad_common_row_allowed_if_totals_preserve"
    broad_summary_df["qa_severity"] = "info"
    broad_summary_df["qa_reason"] = (
        "common row has too many exact ESTO components; likely caused by crossing aggregate mappings"
    )
    broad_ids = set(broad_summary_df["common_row_id"])
    broad_components_df = common_rows_df[common_rows_df["common_row_id"].isin(broad_ids)].copy()
    affected_output_df = comparison_df[comparison_df["common_row_id"].isin(broad_ids)].copy()
    return {
        "broad_common_row_summary": broad_summary_df,
        "broad_common_row_components": broad_components_df,
        "broad_common_row_affected_output": affected_output_df,
    }


def save_broad_common_row_diagnostics(
    diagnostics: dict[str, pd.DataFrame],
    output_dir: Path,
) -> None:
    """Write broad common row diagnostics as CSVs and one workbook."""
    diagnostics_dir = output_dir / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    for name, df in diagnostics.items():
        df.to_csv(diagnostics_dir / f"{name}.csv", index=False)
    with pd.ExcelWriter(diagnostics_dir / "broad_common_row_diagnostics.xlsx", engine="openpyxl") as writer:
        for name, df in diagnostics.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)


def raise_if_broad_common_rows(
    diagnostics: dict[str, pd.DataFrame],
    output_dir: Path,
) -> None:
    """Raise a mapping-review error when broad common rows are present."""
    summary_df = diagnostics["broad_common_row_summary"]
    if summary_df.empty:
        return
    save_broad_common_row_diagnostics(diagnostics, output_dir)
    max_components = int(summary_df["exact_component_count"].max())
    raise ValueError(
        "Broad common ESTO rows require mapping review before final output can be written. "
        f"Broad rows: {len(summary_df):,}; max exact components in one row: {max_components:,}. "
        f"Diagnostics written to: {output_dir / 'diagnostics'}"
    )


def broad_common_row_error_message(
    diagnostics: dict[str, pd.DataFrame],
    output_dir: Path,
) -> str:
    """Write broad common row diagnostics and return a warning message if any exist."""
    summary_df = diagnostics["broad_common_row_summary"]
    if summary_df.empty:
        return ""
    save_broad_common_row_diagnostics(diagnostics, output_dir)
    max_components = int(summary_df["exact_component_count"].max())
    return (
        "Broad common ESTO rows are present. "
        f"Broad rows: {len(summary_df):,}; max exact components in one row: {max_components:,}. "
        f"Diagnostics written to: {output_dir / 'diagnostics'}"
    )


def build_intersecting_axis_group_diagnostics(
    adjusted_common_rows_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
    axis: str,
) -> pd.DataFrame:
    """Find overlapping product or flow groups in final output rows."""
    if comparison_df.empty:
        return pd.DataFrame()
    if axis == "product":
        label_column = "common_product_label"
        component_column = "component_esto_product"
    elif axis == "flow":
        label_column = "common_flow_label"
        component_column = "component_esto_flow"
    else:
        raise ValueError(f"Unsupported axis for intersection check: {axis}")

    active_common_ids = set(comparison_df["common_row_id"].dropna().astype(str))
    active_components_df = adjusted_common_rows_df[
        adjusted_common_rows_df["common_row_id"].astype(str).isin(active_common_ids)
    ].copy()
    if active_components_df.empty:
        return pd.DataFrame()

    group_rows: list[dict[str, object]] = []
    for label, group_df in active_components_df.groupby(label_column, dropna=False):
        components = sorted(set(group_df[component_column].dropna().astype(str)))
        if not components:
            continue
        group_rows.append(
            {
                "axis": axis,
                "group_label": str(label),
                "component_set": set(components),
                "component_count": len(components),
                "common_row_ids": "|".join(sorted(set(group_df["common_row_id"].dropna().astype(str)))),
            }
        )

    diagnostics_rows: list[dict[str, object]] = []
    for left_index, left in enumerate(group_rows):
        for right in group_rows[left_index + 1 :]:
            intersection = left["component_set"] & right["component_set"]
            if not intersection:
                continue
            if left["component_set"] == right["component_set"]:
                continue
            diagnostics_rows.append(
                {
                    "axis": axis,
                    "left_group_label": left["group_label"],
                    "right_group_label": right["group_label"],
                    "left_component_count": left["component_count"],
                    "right_component_count": right["component_count"],
                    "intersection_component_count": len(intersection),
                    "intersection_components": "|".join(sorted(intersection)),
                    "left_only_components": "|".join(sorted(left["component_set"] - right["component_set"])),
                    "right_only_components": "|".join(sorted(right["component_set"] - left["component_set"])),
                    "left_common_row_ids": left["common_row_ids"],
                    "right_common_row_ids": right["common_row_ids"],
                    "qa_status": "review_allowed_parent_detail_overlap",
                    "qa_severity": "info",
                    "qa_reason": f"intersecting_common_{axis}_groups_allowed_if_subtotals_validate",
                }
            )
    return pd.DataFrame(diagnostics_rows)


def save_intersecting_axis_group_diagnostics(
    product_diagnostics_df: pd.DataFrame,
    flow_diagnostics_df: pd.DataFrame,
    output_dir: Path,
) -> None:
    """Write intersecting flow/product group diagnostics."""
    diagnostics_dir = output_dir / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    product_diagnostics_df.to_csv(diagnostics_dir / "intersecting_common_product_groups.csv", index=False)
    flow_diagnostics_df.to_csv(diagnostics_dir / "intersecting_common_flow_groups.csv", index=False)
    with pd.ExcelWriter(diagnostics_dir / "intersecting_common_axis_groups.xlsx", engine="openpyxl") as writer:
        product_diagnostics_df.to_excel(writer, sheet_name="product_group_overlaps", index=False)
        flow_diagnostics_df.to_excel(writer, sheet_name="flow_group_overlaps", index=False)


def intersecting_axis_group_error_message(
    adjusted_common_rows_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
    output_dir: Path,
) -> str:
    """Write intersecting-axis diagnostics and return a warning message if any exist."""
    product_diagnostics_df = build_intersecting_axis_group_diagnostics(
        adjusted_common_rows_df,
        comparison_df,
        axis="product",
    )
    flow_diagnostics_df = build_intersecting_axis_group_diagnostics(
        adjusted_common_rows_df,
        comparison_df,
        axis="flow",
    )
    if product_diagnostics_df.empty and flow_diagnostics_df.empty:
        return ""
    save_intersecting_axis_group_diagnostics(product_diagnostics_df, flow_diagnostics_df, output_dir)
    return (
        "Intersecting common ESTO axis groups are present. "
        f"Product group overlaps: {len(product_diagnostics_df):,}; "
        f"flow group overlaps: {len(flow_diagnostics_df):,}. "
        f"Diagnostics written to: {output_dir / 'diagnostics'}"
    )


def build_total_check(source_df: pd.DataFrame, comparison_df: pd.DataFrame) -> pd.DataFrame:
    """Check before/after total preservation by source/economy/scenario/year."""
    if source_df.empty:
        return pd.DataFrame(columns=TOTAL_GROUP_COLUMNS + ["source_total", "common_total", "difference"])
    source_df = source_df.copy()
    if "comparison_scope" not in source_df.columns:
        if comparison_df.empty or "comparison_scope" not in comparison_df.columns:
            source_df["comparison_scope"] = ""
        else:
            scopes_df = comparison_df[["comparison_scope"]].drop_duplicates()
            expanded_frames: list[pd.DataFrame] = []
            for _, scope_row in scopes_df.iterrows():
                comparison_scope = str(scope_row["comparison_scope"])
                allowed_systems = COMPARISON_SCOPE_SYSTEMS.get(comparison_scope)
                if allowed_systems is None:
                    scoped_source_df = source_df.copy()
                else:
                    scoped_source_df = source_df[source_df["source_system"].isin(allowed_systems)].copy()
                if scoped_source_df.empty:
                    continue
                scoped_source_df["comparison_scope"] = comparison_scope
                expanded_frames.append(scoped_source_df)
            source_df = pd.concat(expanded_frames, ignore_index=True) if expanded_frames else pd.DataFrame(columns=SOURCE_VALUE_SCOPE_COLUMNS)
    else:
        valid_scope_mask = source_df.apply(
            lambda row: row["source_system"] in COMPARISON_SCOPE_SYSTEMS.get(str(row["comparison_scope"]), {row["source_system"]}),
            axis=1,
        )
        source_df = source_df[valid_scope_mask].copy()
    before_df = source_df.groupby(TOTAL_GROUP_COLUMNS, dropna=False, as_index=False)["value"].sum().rename(columns={"value": "source_total"})
    if comparison_df.empty:
        after_df = pd.DataFrame(columns=TOTAL_GROUP_COLUMNS + ["common_total"])
    else:
        after_df = comparison_df.groupby(TOTAL_GROUP_COLUMNS, dropna=False, as_index=False)["value"].sum().rename(columns={"value": "common_total"})
    check_df = before_df.merge(after_df, on=TOTAL_GROUP_COLUMNS, how="outer")
    check_df["source_total"] = pd.to_numeric(check_df["source_total"], errors="coerce").fillna(0)
    check_df["common_total"] = pd.to_numeric(check_df["common_total"], errors="coerce").fillna(0)
    check_df["difference"] = check_df["common_total"] - check_df["source_total"]
    return check_df.sort_values(TOTAL_GROUP_COLUMNS).reset_index(drop=True)


def build_wide_year_output(comparison_df: pd.DataFrame) -> pd.DataFrame:
    """Create economy/scenario/product/flow rows with year columns.

    The wide file intentionally has no source_system column, so source_system is
    folded into scenario to avoid summing LEAP, 9th, and ESTO rows together.
    """
    if comparison_df.empty:
        return pd.DataFrame(columns=WIDE_OUTPUT_ID_COLUMNS)

    working_df = comparison_df.copy()
    working_df["product"] = working_df["common_product_label"]
    working_df["flow"] = working_df["common_flow_label"]
    working_df["scenario"] = (
        working_df["source_system"].fillna("").astype(str).str.strip()
        + " "
        + working_df["scenario"].fillna("").astype(str).str.strip()
    ).str.strip()
    working_df["year"] = working_df["year"].astype(str)
    wide_df = (
        working_df.pivot_table(
            index=WIDE_OUTPUT_ID_COLUMNS,
            columns="year",
            values="value",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
    )
    wide_df.columns = [str(column) for column in wide_df.columns]
    year_columns = sorted(
        [column for column in wide_df.columns if column not in WIDE_OUTPUT_ID_COLUMNS],
        key=lambda value: int(value) if value.isdigit() else value,
    )
    return wide_df[WIDE_OUTPUT_ID_COLUMNS + year_columns]


def drop_internal_common_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove internal QA columns from final comparison output."""
    return df.drop(columns=[column for column in COMPARISON_INTERNAL_COLUMNS if column in df.columns])


def write_csv_with_locked_fallback(df: pd.DataFrame, output_path: Path) -> Path:
    """Write a CSV, falling back to a rebuilt filename if the target is locked."""
    try:
        df.to_csv(output_path, index=False)
        return output_path
    except PermissionError:
        fallback_path = output_path.with_name(f"{output_path.stem}_rebuilt{output_path.suffix}")
        print(f"Could not overwrite locked CSV: {output_path}")
        print(f"Writing rebuilt CSV instead: {fallback_path}")
        df.to_csv(fallback_path, index=False)
        return fallback_path


def error_tagged_path(output_path: Path, error_occurred: bool) -> Path:
    """Add an error tag to output filenames when QA errors occurred."""
    if not error_occurred:
        return output_path
    return output_path.with_name(f"{output_path.stem}_needs_mapping_review{output_path.suffix}")


def save_outputs(
    comparison_df: pd.DataFrame,
    wide_year_df: pd.DataFrame,
    total_check_df: pd.DataFrame,
    missing_map_df: pd.DataFrame,
    subtotal_filtered_df: pd.DataFrame,
    output_dir: Path,
    error_occurred: bool,
) -> None:
    """Write common comparison data and QA outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written_paths = []
    written_paths.append(write_csv_with_locked_fallback(
        drop_internal_common_columns(comparison_df),
        error_tagged_path(output_dir / "common_esto_comparison_data.csv", error_occurred),
    ))
    written_paths.append(write_csv_with_locked_fallback(
        wide_year_df,
        error_tagged_path(output_dir / "common_esto_comparison_wide.csv", error_occurred),
    ))
    written_paths.append(write_csv_with_locked_fallback(
        total_check_df,
        error_tagged_path(output_dir / "common_esto_total_check.csv", error_occurred),
    ))
    written_paths.append(write_csv_with_locked_fallback(
        total_check_df,
        error_tagged_path(output_dir / "qa_common_esto_total_check.csv", error_occurred),
    ))
    written_paths.append(write_csv_with_locked_fallback(
        missing_map_df,
        error_tagged_path(output_dir / "common_esto_source_rows_missing_common_map.csv", error_occurred),
    ))
    written_paths.append(write_csv_with_locked_fallback(
        subtotal_filtered_df,
        error_tagged_path(output_dir / "common_esto_subtotal_rows_filtered.csv", error_occurred),
    ))
    status_df = pd.DataFrame(
        [
            {
                "status": "needs_mapping_review" if error_occurred else "ok",
                "current_output_file": path.name,
            }
            for path in written_paths
        ]
    )
    write_csv_with_locked_fallback(status_df, output_dir / "common_esto_output_status.csv")


def run_apply_common_esto_structure(
    source_paths: dict[str, Path],
    common_rows_path: Path,
    output_dir: Path,
    default_economy: str,
    exclude_subtotal_rows: bool,
    broad_common_row_component_limit: int,
    active_component_abs_tolerance: float,
    raw_leap_results_path: Path | None = None,
    outlook_mappings_path: Path | None = None,
    structural_partial_coverage_path: Path | None = None,
    ninth_projection_start_year: int = NINTH_PROJECTION_START_YEAR,
    esto_base_year: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Apply the common ESTO structure to available ESTO-shaped source data."""
    source_df = read_source_tables(source_paths, default_economy=default_economy)
    common_rows_df = pd.read_csv(common_rows_path, dtype=str).fillna("")
    for column in ["component_esto_flow", "component_esto_product"]:
        if column in common_rows_df.columns:
            common_rows_df[column] = common_rows_df[column].map(normalise_label)
    relevance_df, resolved_esto_base_year = build_component_relevance(
        source_df=source_df,
        active_component_abs_tolerance=active_component_abs_tolerance,
        ninth_projection_start_year=ninth_projection_start_year,
        esto_base_year=esto_base_year,
    )
    leap_branch_audit_df = pd.DataFrame()
    if (
        raw_leap_results_path is not None
        and raw_leap_results_path.exists()
        and outlook_mappings_path is not None
        and outlook_mappings_path.exists()
    ):
        raw_leap_df = pd.read_csv(raw_leap_results_path, low_memory=False)
        leap_esto_df = pd.read_excel(outlook_mappings_path, sheet_name="leap_combined_esto")
        leap_ninth_df = pd.read_excel(outlook_mappings_path, sheet_name="leap_combined_ninth")
        ninth_esto_df = pd.read_excel(outlook_mappings_path, sheet_name="ninth_pairs_to_esto_pairs")
        leap_branch_audit_df, unmapped_leap_relevance_df = build_unmapped_leap_branch_evidence(
            raw_leap_df=raw_leap_df,
            leap_esto_df=leap_esto_df,
            leap_ninth_df=leap_ninth_df,
            ninth_esto_df=ninth_esto_df,
            active_component_abs_tolerance=active_component_abs_tolerance,
        )
        relevance_df = merge_component_relevance(relevance_df, unmapped_leap_relevance_df)

    active_source_df = nonzero_source_rows(source_df, active_component_abs_tolerance)
    if not relevance_df.empty:
        relevant_pairs_df = relevance_df[["component_esto_flow", "component_esto_product"]].rename(
            columns={
                "component_esto_flow": "esto_flow",
                "component_esto_product": "esto_product",
            }
        )
        active_source_df = active_source_df.merge(
            relevant_pairs_df.drop_duplicates(),
            on=["esto_flow", "esto_product"],
            how="inner",
        )
    adjusted_common_rows_df, pruned_components_df = relabel_common_rows_for_active_components(
        relevance_df=relevance_df,
        common_rows_df=common_rows_df,
    )
    save_component_pruning_diagnostics(pruned_components_df, output_dir)

    structural_partial_df = pd.DataFrame()
    if structural_partial_coverage_path is not None and structural_partial_coverage_path.exists():
        structural_partial_df = pd.read_csv(structural_partial_coverage_path, low_memory=False)
    actionable_partial_df, inactive_partial_df = filter_partial_coverage_by_relevance(
        structural_partial_df=structural_partial_df,
        relevance_df=relevance_df,
    )
    save_relevance_diagnostics(
        relevance_df=relevance_df,
        pruned_components_df=pruned_components_df,
        leap_branch_audit_df=leap_branch_audit_df,
        actionable_partial_df=actionable_partial_df,
        inactive_partial_df=inactive_partial_df,
        output_dir=output_dir,
    )
    unfiltered_comparison_df, missing_map_df, mapped_source_df = apply_common_structure(active_source_df, adjusted_common_rows_df)
    missing_map_df = filter_missing_common_map_diagnostics(missing_map_df)
    subtotal_kept_df, subtotal_filtered_df = split_subtotal_rows(unfiltered_comparison_df, exclude_subtotal_rows=exclude_subtotal_rows)
    broad_diagnostics = build_broad_common_row_diagnostics(
        common_rows_df=adjusted_common_rows_df,
        comparison_df=subtotal_kept_df,
        broad_component_limit=broad_common_row_component_limit,
    )
    broad_warning_message = broad_common_row_error_message(broad_diagnostics, output_dir)
    intersecting_axis_warning_message = intersecting_axis_group_error_message(
        adjusted_common_rows_df=adjusted_common_rows_df,
        comparison_df=subtotal_kept_df,
        output_dir=output_dir,
    )
    error_occurred = False
    if broad_warning_message:
        print(f"WARNING: {broad_warning_message}")
    if intersecting_axis_warning_message:
        print(f"WARNING: {intersecting_axis_warning_message}")
    comparison_df = subtotal_kept_df.copy()
    wide_year_df = build_wide_year_output(comparison_df)
    total_check_df = build_total_check(mapped_source_df, unfiltered_comparison_df)
    save_outputs(
        comparison_df,
        wide_year_df,
        total_check_df,
        missing_map_df,
        subtotal_filtered_df,
        output_dir,
        error_occurred=error_occurred,
    )

    max_abs_difference = total_check_df["difference"].abs().max() if "difference" in total_check_df.columns and not total_check_df.empty else 0
    print(f"ESTO-shaped source rows read: {len(source_df):,}")
    print(f"ESTO base year used for component relevance: {resolved_esto_base_year}")
    print(f"NINTH projection start year used for component relevance: {ninth_projection_start_year}")
    print(f"Data-relevant ESTO component pairs: {len(relevance_df):,}")
    print(f"Actionable partial-coverage rows: {len(actionable_partial_df):,}")
    print(f"Inactive partial-coverage component findings: {len(inactive_partial_df):,}")
    print(f"Nonzero LEAP branches without direct ESTO mappings: {len(leap_branch_audit_df):,}")
    print(f"Nonzero ESTO-shaped source rows used: {len(active_source_df):,}")
    print(f"Common ESTO components pruned as not applicable: {len(pruned_components_df):,}")
    print(f"Common comparison rows before subtotal filtering: {len(unfiltered_comparison_df):,}")
    print(f"Subtotal/total rows filtered from final outputs: {len(subtotal_filtered_df):,}")
    print(f"Common comparison rows written: {len(comparison_df):,}")
    print(f"Wide year rows written: {len(wide_year_df):,}")
    print(f"Source rows missing common map: {len(missing_map_df):,}")
    print(f"before/after total differences max abs: {max_abs_difference}")
    print(f"Error tag applied to output filenames: {error_occurred}")
    print(f"Wrote common ESTO comparison output to: {output_dir}")
    return comparison_df, total_check_df, missing_map_df

#%%
# User-tuned constants / flags.
SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = _find_repo_root(SCRIPT_PATH.parent)

RELATIONSHIP_DIR = REPO_ROOT / "results" / "mapping_relationships"
COMMON_STRUCTURE_DIR = REPO_ROOT / "results" / "common_esto"
COMMON_ROWS_PATH = COMMON_STRUCTURE_DIR / "common_esto_rows.csv"
STRUCTURAL_PARTIAL_COVERAGE_PATH = COMMON_STRUCTURE_DIR / "qa_common_esto_structural_partial_coverage.csv"
RAW_LEAP_RESULTS_PATH = RELATIONSHIP_DIR / "raw_leap_results.csv"
OUTLOOK_MAPPINGS_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
OUTPUT_DIR = REPO_ROOT / "results" / "common_esto"

SOURCE_PATHS = {
    "LEAP": RELATIONSHIP_DIR / "leap_results_converted_to_esto.csv",
    "NINTH": RELATIONSHIP_DIR / "ninth_results_converted_to_esto.csv",
    "ESTO": RELATIONSHIP_DIR / "esto_results_exact_rows.csv",
}
DEFAULT_ECONOMY = "20_USA"
EXCLUDE_SUBTOTAL_ROWS = True
BROAD_COMMON_ROW_COMPONENT_LIMIT = 50
ACTIVE_COMPONENT_ABS_TOLERANCE = 0.0

RUN_APPLY_COMMON_ESTO_STRUCTURE = False

#%%
if __name__ == "__main__":
    try:
        if RUN_APPLY_COMMON_ESTO_STRUCTURE:
            run_apply_common_esto_structure(
                source_paths=SOURCE_PATHS,
                common_rows_path=COMMON_ROWS_PATH,
                output_dir=OUTPUT_DIR,
                default_economy=DEFAULT_ECONOMY,
                exclude_subtotal_rows=EXCLUDE_SUBTOTAL_ROWS,
                broad_common_row_component_limit=BROAD_COMMON_ROW_COMPONENT_LIMIT,
                active_component_abs_tolerance=ACTIVE_COMPONENT_ABS_TOLERANCE,
                raw_leap_results_path=RAW_LEAP_RESULTS_PATH,
                outlook_mappings_path=OUTLOOK_MAPPINGS_PATH,
                structural_partial_coverage_path=STRUCTURAL_PARTIAL_COVERAGE_PATH,
                ninth_projection_start_year=NINTH_PROJECTION_START_YEAR,
            )
        else:
            print("Set RUN_APPLY_COMMON_ESTO_STRUCTURE = True after setting SOURCE_PATHS.")
    except Exception as exc:
        print("Apply common ESTO structure workflow failed.")
        print(f"Error: {exc}")
        raise

#%%
