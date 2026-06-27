#%%
"""Generate review-only mapping candidates from independently inferred axes.

The candidate logic treats sector/branch -> ESTO flow and fuel -> ESTO product
as separate evidence. It combines those axes only for source pairs that occur
with non-zero data. Candidates are diagnostics and must never update the
canonical mapping workbook automatically.
"""

#%%
from pathlib import Path

import pandas as pd


CANDIDATE_OUTPUT_COLUMNS = [
    "candidate_context",
    "candidate_status",
    "candidate_rank",
    "mapping_sheet",
    "comparison_scope",
    "use_case",
    "source_system",
    "common_row_id",
    "leap_sector_name_full_path",
    "raw_leap_fuel_name",
    "9th_sector",
    "9th_fuel",
    "esto_flow",
    "esto_product",
    "source_pair_nonzero",
    "source_nonzero_row_count",
    "source_nonzero_economy_count",
    "source_abs_sum",
    "flow_axis_match_method",
    "flow_axis_support_count",
    "flow_axis_mapping_count",
    "flow_axis_confidence",
    "flow_axis_alternatives",
    "product_axis_match_method",
    "product_axis_support_count",
    "product_axis_mapping_count",
    "product_axis_confidence",
    "product_axis_alternatives",
    "missing_axis_evidence",
    "combined_axis_confidence",
    "candidate_confidence",
    "source_pair_existing_target_count",
    "candidate_would_add_another_target",
    "candidate_rationale",
    "review_warning",
    "computer_generated_review_only",
    "derived_from_existing_axis_mappings",
    "paste_ready",
    "paste_instruction",
]


def normalise_text(value: object) -> str:
    """Return a stable string key."""
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def normalise_path(value: object) -> str:
    """Normalise LEAP path separators and repeated whitespace."""
    return normalise_text(value).replace("\\", "/")


def collapsed_path(value: object) -> str:
    """Collapse consecutive duplicate LEAP path segments."""
    parts = [normalise_text(part) for part in normalise_path(value).split("/") if normalise_text(part)]
    collapsed: list[str] = []
    for part in parts:
        if not collapsed or collapsed[-1].lower() != part.lower():
            collapsed.append(part)
    return "/".join(collapsed)


def leaf_path(value: object) -> str:
    """Return the final LEAP path segment."""
    parts = [part for part in collapsed_path(value).split("/") if part]
    return parts[-1] if parts else ""


def summarise_nonzero_leap_pairs(
    raw_leap_df: pd.DataFrame,
    value_tolerance: float,
) -> pd.DataFrame:
    """Summarise observed non-zero LEAP branch/fuel pairs."""
    columns = [
        "source_flow",
        "source_product",
        "source_nonzero_row_count",
        "source_nonzero_economy_count",
        "source_abs_sum",
    ]
    if raw_leap_df.empty:
        return pd.DataFrame(columns=columns)
    working_df = raw_leap_df.copy()
    working_df["value"] = pd.to_numeric(working_df["value"], errors="coerce").fillna(0)
    working_df = working_df[working_df["value"].abs() > value_tolerance].copy()
    if working_df.empty:
        return pd.DataFrame(columns=columns)
    working_df["source_flow"] = working_df["leap_flow"].map(normalise_path)
    working_df["source_product"] = working_df["leap_product"].map(normalise_text)
    working_df["_abs_value"] = working_df["value"].abs()
    if "economy" not in working_df.columns:
        working_df["economy"] = ""
    return working_df.groupby(["source_flow", "source_product"], as_index=False).agg(
        source_nonzero_row_count=("value", "size"),
        source_nonzero_economy_count=("economy", "nunique"),
        source_abs_sum=("_abs_value", "sum"),
    )[columns]


def summarise_nonzero_ninth_projection_pairs(
    ninth_csv_path: Path,
    projection_start_year: int,
    value_tolerance: float,
) -> pd.DataFrame:
    """Read the 9th wide table and summarise active projection source pairs."""
    columns = [
        "source_flow",
        "source_product",
        "source_nonzero_row_count",
        "source_nonzero_economy_count",
        "source_abs_sum",
    ]
    if not ninth_csv_path.exists():
        return pd.DataFrame(columns=columns)
    header = pd.read_csv(ninth_csv_path, nrows=0).columns.tolist()
    projection_columns = [
        column for column in header
        if str(column).isdigit() and int(column) >= projection_start_year
    ]
    required_columns = ["scenarios", "economy", "sectors", "sub1sectors", "fuels", "subfuels"]
    raw_df = pd.read_csv(ninth_csv_path, usecols=required_columns + projection_columns, dtype=object)
    raw_df = raw_df[
        raw_df["scenarios"].astype(str).str.lower().eq("reference")
        & raw_df["sub1sectors"].astype(str).str.strip().eq("x")
    ].copy()
    if raw_df.empty:
        return pd.DataFrame(columns=columns)
    values_df = raw_df[projection_columns].apply(pd.to_numeric, errors="coerce").fillna(0).abs()
    raw_df["source_abs_sum"] = values_df.sum(axis=1)
    raw_df["source_nonzero_row_count"] = values_df.gt(value_tolerance).sum(axis=1)
    raw_df = raw_df[raw_df["source_abs_sum"] > value_tolerance].copy()
    raw_df["source_flow"] = raw_df["sectors"].map(normalise_text)
    raw_df["source_product"] = raw_df["subfuels"].map(normalise_text)
    aggregate_fuel_mask = raw_df["source_product"].eq("x")
    raw_df.loc[aggregate_fuel_mask, "source_product"] = raw_df.loc[aggregate_fuel_mask, "fuels"].map(normalise_text)
    return raw_df.groupby(["source_flow", "source_product"], as_index=False).agg(
        source_nonzero_row_count=("source_nonzero_row_count", "sum"),
        source_nonzero_economy_count=("economy", "nunique"),
        source_abs_sum=("source_abs_sum", "sum"),
    )[columns]


def build_axis_profile(
    mapping_df: pd.DataFrame,
    source_column: str,
    target_column: str,
    source_normaliser,
) -> pd.DataFrame:
    """Count how consistently one source-axis label maps to a target label."""
    working_df = mapping_df[[source_column, target_column]].copy()
    working_df["source_axis"] = working_df[source_column].map(source_normaliser)
    working_df["target_axis"] = working_df[target_column].map(normalise_text)
    working_df = working_df[(working_df["source_axis"] != "") & (working_df["target_axis"] != "")]
    support_df = working_df.groupby(["source_axis", "target_axis"], as_index=False).size().rename(
        columns={"size": "axis_support_count"}
    )
    totals_df = working_df.groupby("source_axis", as_index=False).size().rename(
        columns={"size": "axis_mapping_count"}
    )
    profile_df = support_df.merge(totals_df, on="source_axis", how="left")
    profile_df["axis_confidence"] = profile_df["axis_support_count"] / profile_df["axis_mapping_count"]
    return profile_df


def candidate_confidence_label(flow_confidence: float, product_confidence: float, minimum_support: int) -> str:
    """Classify independent-axis evidence without implying automatic approval."""
    combined = min(flow_confidence, product_confidence)
    if combined == 1 and minimum_support >= 2:
        return "high"
    if combined >= 0.75:
        return "medium"
    return "low"


def format_profile_alternatives(profile_df: pd.DataFrame, source_label: str = "source_axis") -> str:
    """Format compact source or target alternatives for human review."""
    if profile_df.empty:
        return ""
    parts: list[str] = []
    for _, row in profile_df.head(5).iterrows():
        label = normalise_text(row.get(source_label, row.get("target_axis", "")))
        support = row.get("axis_support_count", row.get("flow_axis_support_count", row.get("product_axis_support_count", 0)))
        total = row.get("axis_mapping_count", row.get("flow_axis_mapping_count", row.get("product_axis_mapping_count", 0)))
        confidence = row.get("axis_confidence", row.get("flow_axis_confidence", row.get("product_axis_confidence", 0)))
        parts.append(
            f"{label} [support={int(support)}/{int(total)}; confidence={float(confidence):.3f}]"
        )
    return "|".join(parts)


def _candidate_base(issue: pd.Series, mapping_sheet: str) -> dict[str, object]:
    """Copy issue identity into a candidate row."""
    return {
        "candidate_context": "partial_coverage",
        "mapping_sheet": mapping_sheet,
        "comparison_scope": issue.get("comparison_scope", ""),
        "use_case": issue.get("use_case", ""),
        "source_system": issue.get("source_system", ""),
        "common_row_id": issue.get("common_row_id", ""),
        "esto_flow": issue.get("missing_component_esto_flow", ""),
        "esto_product": issue.get("missing_component_esto_product", ""),
        "computer_generated_review_only": True,
    }


def generate_partial_coverage_candidates_for_system(
    issues_df: pd.DataFrame,
    active_source_pairs_df: pd.DataFrame,
    mapping_df: pd.DataFrame,
    source_flow_column: str,
    source_product_column: str,
    mapping_sheet: str,
    max_candidates_per_issue: int,
) -> pd.DataFrame:
    """Suggest observed source pairs whose two axes independently match a target."""
    if issues_df.empty:
        return pd.DataFrame(columns=CANDIDATE_OUTPUT_COLUMNS)
    source_flow_normaliser = normalise_path if mapping_sheet == "leap_combined_esto" else normalise_text
    flow_profile = build_axis_profile(mapping_df, source_flow_column, "esto_flow", source_flow_normaliser)
    product_profile = build_axis_profile(mapping_df, source_product_column, "esto_product", normalise_text)
    existing_targets = mapping_df.copy()
    existing_targets["source_flow"] = existing_targets[source_flow_column].map(source_flow_normaliser)
    existing_targets["source_product"] = existing_targets[source_product_column].map(normalise_text)
    existing_targets["target_flow"] = existing_targets["esto_flow"].map(normalise_text)
    existing_targets["target_product"] = existing_targets["esto_product"].map(normalise_text)
    existing_exact_mappings = set(
        existing_targets[["source_flow", "source_product", "target_flow", "target_product"]].itertuples(
            index=False,
            name=None,
        )
    )
    target_counts = existing_targets.groupby(["source_flow", "source_product"], as_index=False).agg(
        source_pair_existing_target_count=("esto_flow", "size")
    )

    rows: list[dict[str, object]] = []
    for _, issue in issues_df.iterrows():
        target_flow = normalise_text(issue["missing_component_esto_flow"])
        target_product = normalise_text(issue["missing_component_esto_product"])
        flow_matches = flow_profile[flow_profile["target_axis"] == target_flow].rename(
            columns={
                "source_axis": "source_flow",
                "axis_support_count": "flow_axis_support_count",
                "axis_mapping_count": "flow_axis_mapping_count",
                "axis_confidence": "flow_axis_confidence",
            }
        )
        product_matches = product_profile[product_profile["target_axis"] == target_product].rename(
            columns={
                "source_axis": "source_product",
                "axis_support_count": "product_axis_support_count",
                "axis_mapping_count": "product_axis_mapping_count",
                "axis_confidence": "product_axis_confidence",
            }
        )
        candidates_df = active_source_pairs_df.merge(
            flow_matches[["source_flow", "flow_axis_support_count", "flow_axis_mapping_count", "flow_axis_confidence"]],
            on="source_flow",
            how="inner",
        ).merge(
            product_matches[["source_product", "product_axis_support_count", "product_axis_mapping_count", "product_axis_confidence"]],
            on="source_product",
            how="inner",
        ).merge(target_counts, on=["source_flow", "source_product"], how="left")
        candidates_df["source_pair_existing_target_count"] = candidates_df["source_pair_existing_target_count"].fillna(0).astype(int)
        if not candidates_df.empty:
            already_mapped_mask = candidates_df.apply(
                lambda candidate: (
                    candidate["source_flow"],
                    candidate["source_product"],
                    target_flow,
                    target_product,
                ) in existing_exact_mappings,
                axis=1,
            )
            candidates_df = candidates_df[~already_mapped_mask].copy()
        candidates_df["combined_axis_confidence"] = candidates_df[["flow_axis_confidence", "product_axis_confidence"]].min(axis=1)
        candidates_df = candidates_df.sort_values(
            ["combined_axis_confidence", "source_abs_sum", "flow_axis_support_count", "product_axis_support_count"],
            ascending=[False, False, False, False],
        ).head(max_candidates_per_issue)

        base = _candidate_base(issue, mapping_sheet)
        if candidates_df.empty:
            missing_evidence: list[str] = []
            if flow_matches.empty:
                missing_evidence.append("no_source_axis_maps_to_target_flow")
            if product_matches.empty:
                missing_evidence.append("no_source_axis_maps_to_target_product")
            if not flow_matches.empty and not product_matches.empty:
                missing_evidence.append("no_nonzero_source_pair_combines_the_two_axes")
            output = dict(base)
            output.update(
                {
                    "candidate_status": "no_observed_source_pair_matches_both_axes",
                    "candidate_rank": 0,
                    "source_pair_nonzero": False,
                    "candidate_confidence": "none",
                    "flow_axis_alternatives": format_profile_alternatives(flow_matches, "source_flow"),
                    "product_axis_alternatives": format_profile_alternatives(product_matches, "source_product"),
                    "missing_axis_evidence": "|".join(missing_evidence),
                    "candidate_rationale": "No non-zero source pair had both independently inferred axes.",
                    "review_warning": "Manual source-category review required.",
                }
            )
            rows.append(output)
            continue

        for rank, (_, candidate) in enumerate(candidates_df.iterrows(), start=1):
            output = dict(base)
            source_flow = str(candidate["source_flow"])
            source_product = str(candidate["source_product"])
            if mapping_sheet == "leap_combined_esto":
                output["leap_sector_name_full_path"] = source_flow
                output["raw_leap_fuel_name"] = source_product
            else:
                output["9th_sector"] = source_flow
                output["9th_fuel"] = source_product
            minimum_support = int(min(candidate["flow_axis_support_count"], candidate["product_axis_support_count"]))
            confidence = candidate_confidence_label(
                float(candidate["flow_axis_confidence"]),
                float(candidate["product_axis_confidence"]),
                minimum_support,
            )
            existing_target_count = int(candidate["source_pair_existing_target_count"])
            output.update(
                {
                    "candidate_status": "proposed",
                    "candidate_rank": rank,
                    "source_pair_nonzero": True,
                    "source_nonzero_row_count": candidate["source_nonzero_row_count"],
                    "source_nonzero_economy_count": candidate["source_nonzero_economy_count"],
                    "source_abs_sum": candidate["source_abs_sum"],
                    "flow_axis_match_method": "exact_source_axis_profile",
                    "flow_axis_support_count": candidate["flow_axis_support_count"],
                    "flow_axis_mapping_count": candidate["flow_axis_mapping_count"],
                    "flow_axis_confidence": candidate["flow_axis_confidence"],
                    "flow_axis_alternatives": source_flow,
                    "product_axis_match_method": "exact_source_axis_profile",
                    "product_axis_support_count": candidate["product_axis_support_count"],
                    "product_axis_mapping_count": candidate["product_axis_mapping_count"],
                    "product_axis_confidence": candidate["product_axis_confidence"],
                    "product_axis_alternatives": source_product,
                    "missing_axis_evidence": "",
                    "combined_axis_confidence": candidate["combined_axis_confidence"],
                    "candidate_confidence": confidence,
                    "source_pair_existing_target_count": existing_target_count,
                    "candidate_would_add_another_target": existing_target_count > 0,
                    "candidate_rationale": "Observed non-zero source pair; source flow and product independently map to the missing ESTO axes.",
                    "review_warning": (
                        "Source pair already has a target; adding this row may create one-to-many coverage."
                        if existing_target_count > 0
                        else "Review semantic scope and hierarchy before copying."
                    ),
                }
            )
            rows.append(output)
    return pd.DataFrame(rows).reindex(columns=CANDIDATE_OUTPUT_COLUMNS)


def generate_partial_coverage_mapping_candidates(
    issues_df: pd.DataFrame,
    raw_leap_df: pd.DataFrame,
    active_ninth_pairs_df: pd.DataFrame,
    leap_esto_df: pd.DataFrame,
    ninth_esto_df: pd.DataFrame,
    value_tolerance: float,
    max_candidates_per_issue: int = 5,
) -> pd.DataFrame:
    """Generate copy-friendly candidates for LEAP and NINTH coverage gaps."""
    leap_active_df = summarise_nonzero_leap_pairs(raw_leap_df, value_tolerance)
    frames = [
        generate_partial_coverage_candidates_for_system(
            issues_df=issues_df[issues_df["source_system"].astype(str).str.upper() == "LEAP"],
            active_source_pairs_df=leap_active_df,
            mapping_df=leap_esto_df,
            source_flow_column="leap_sector_name_full_path",
            source_product_column="raw_leap_fuel_name",
            mapping_sheet="leap_combined_esto",
            max_candidates_per_issue=max_candidates_per_issue,
        ),
        generate_partial_coverage_candidates_for_system(
            issues_df=issues_df[issues_df["source_system"].astype(str).str.upper() == "NINTH"],
            active_source_pairs_df=active_ninth_pairs_df,
            mapping_df=ninth_esto_df,
            source_flow_column="9th_sector",
            source_product_column="9th_fuel",
            mapping_sheet="ninth_pairs_to_esto_pairs",
            max_candidates_per_issue=max_candidates_per_issue,
        ),
    ]
    combined_df = pd.concat(frames, ignore_index=True).reindex(columns=CANDIDATE_OUTPUT_COLUMNS)
    if combined_df.empty:
        return combined_df
    proposed_df = combined_df[combined_df["candidate_status"] == "proposed"].copy()
    unresolved_df = combined_df[combined_df["candidate_status"] != "proposed"].copy()
    if proposed_df.empty:
        return combined_df
    key_columns = [
        "mapping_sheet",
        "leap_sector_name_full_path",
        "raw_leap_fuel_name",
        "9th_sector",
        "9th_fuel",
        "esto_flow",
        "esto_product",
    ]
    collapsed_rows: list[dict[str, object]] = []
    for _, group_df in proposed_df.fillna("").groupby(key_columns, dropna=False):
        output = group_df.iloc[0].to_dict()
        for column in ["comparison_scope", "use_case", "common_row_id"]:
            output[column] = "|".join(sorted({normalise_text(value) for value in group_df[column] if normalise_text(value)}))
        output["candidate_rank"] = int(pd.to_numeric(group_df["candidate_rank"], errors="coerce").min())
        collapsed_rows.append(output)
    collapsed_df = pd.DataFrame(collapsed_rows).reindex(columns=CANDIDATE_OUTPUT_COLUMNS)
    return pd.concat([collapsed_df, unresolved_df], ignore_index=True).reindex(columns=CANDIDATE_OUTPUT_COLUMNS)


def _best_profile_matches(profile_df: pd.DataFrame, source_axis: str, limit: int = 3) -> pd.DataFrame:
    """Return the strongest target-axis matches for one source label."""
    matches = profile_df[profile_df["source_axis"] == source_axis].copy()
    return matches.sort_values(["axis_confidence", "axis_support_count"], ascending=[False, False]).head(limit)


def generate_unmapped_leap_branch_candidates(
    leap_branch_audit_df: pd.DataFrame,
    leap_esto_df: pd.DataFrame,
    max_axis_candidates: int = 3,
) -> pd.DataFrame:
    """Infer ESTO targets for non-zero unmapped LEAP pairs from separate axes."""
    if leap_branch_audit_df.empty:
        return pd.DataFrame(columns=CANDIDATE_OUTPUT_COLUMNS)
    mapping_df = leap_esto_df.copy()
    flow_profiles = {
        "exact_branch_path": build_axis_profile(mapping_df, "leap_sector_name_full_path", "esto_flow", normalise_path),
        "collapsed_branch_path": build_axis_profile(mapping_df, "leap_sector_name_full_path", "esto_flow", collapsed_path),
        "branch_leaf_name": build_axis_profile(mapping_df, "leap_sector_name_full_path", "esto_flow", leaf_path),
    }
    product_profile = build_axis_profile(mapping_df, "raw_leap_fuel_name", "esto_product", normalise_text)
    rows: list[dict[str, object]] = []
    source_pairs_df = leap_branch_audit_df[["leap_flow", "leap_product"]].drop_duplicates()
    for _, source_pair in source_pairs_df.iterrows():
        leap_flow = normalise_path(source_pair["leap_flow"])
        leap_product = normalise_text(source_pair["leap_product"])
        flow_matches = pd.DataFrame()
        flow_method = ""
        for method, profile_df in flow_profiles.items():
            key = leap_flow if method == "exact_branch_path" else collapsed_path(leap_flow) if method == "collapsed_branch_path" else leaf_path(leap_flow)
            flow_matches = _best_profile_matches(profile_df, key, max_axis_candidates)
            if not flow_matches.empty:
                flow_method = method
                break
        product_matches = _best_profile_matches(product_profile, leap_product, max_axis_candidates)
        indirect_df = leap_branch_audit_df[
            (leap_branch_audit_df["leap_flow"].map(normalise_path) == leap_flow)
            & (leap_branch_audit_df["leap_product"].map(normalise_text) == leap_product)
            & leap_branch_audit_df["indirect_esto_flow"].fillna("").astype(str).str.strip().ne("")
            & leap_branch_audit_df["indirect_esto_product"].fillna("").astype(str).str.strip().ne("")
        ]
        candidate_pairs: list[dict[str, object]] = []
        for _, indirect in indirect_df.iterrows():
            candidate_pairs.append(
                {
                    "esto_flow": normalise_text(indirect["indirect_esto_flow"]),
                    "esto_product": normalise_text(indirect["indirect_esto_product"]),
                    "flow_method": "indirect_leap_ninth_esto",
                    "product_method": "indirect_leap_ninth_esto",
                    "flow_support": 1,
                    "flow_total": 1,
                    "flow_confidence": 1.0,
                    "product_support": 1,
                    "product_total": 1,
                    "product_confidence": 1.0,
                    "rationale": "Existing LEAP-to-9th and 9th-to-ESTO rows imply this ESTO pair.",
                }
            )
        for _, flow_match in flow_matches.iterrows():
            for _, product_match in product_matches.iterrows():
                candidate_pairs.append(
                    {
                        "esto_flow": flow_match["target_axis"],
                        "esto_product": product_match["target_axis"],
                        "flow_method": flow_method,
                        "product_method": "exact_fuel_profile",
                        "flow_support": flow_match["axis_support_count"],
                        "flow_total": flow_match["axis_mapping_count"],
                        "flow_confidence": flow_match["axis_confidence"],
                        "product_support": product_match["axis_support_count"],
                        "product_total": product_match["axis_mapping_count"],
                        "product_confidence": product_match["axis_confidence"],
                        "rationale": "LEAP branch and fuel axes independently imply the proposed ESTO flow and product.",
                    }
                )
        seen_pairs: set[tuple[str, str]] = set()
        unique_candidates: list[dict[str, object]] = []
        for candidate in candidate_pairs:
            pair = (str(candidate["esto_flow"]), str(candidate["esto_product"]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            unique_candidates.append(candidate)
        if not unique_candidates:
            flow_alternatives = format_profile_alternatives(flow_matches, "target_axis")
            product_alternatives = format_profile_alternatives(product_matches, "target_axis")
            missing_evidence: list[str] = []
            if flow_matches.empty:
                missing_evidence.append("no_flow_inference_for_branch")
            if product_matches.empty:
                missing_evidence.append("no_product_inference_for_fuel")
            rows.append(
                {
                    "candidate_context": "nonzero_unmapped_leap_branch",
                    "candidate_status": "insufficient_axis_evidence",
                    "candidate_rank": 0,
                    "mapping_sheet": "leap_combined_esto",
                    "source_system": "LEAP",
                    "leap_sector_name_full_path": leap_flow,
                    "raw_leap_fuel_name": leap_product,
                    "source_pair_nonzero": True,
                    "candidate_confidence": "none",
                    "flow_axis_alternatives": flow_alternatives,
                    "product_axis_alternatives": product_alternatives,
                    "missing_axis_evidence": "|".join(missing_evidence),
                    "candidate_rationale": "No existing mapping evidence resolved both axes.",
                    "review_warning": "Manual mapping required; do not infer a target from one axis alone.",
                    "computer_generated_review_only": True,
                }
            )
            continue
        unique_candidates.sort(
            key=lambda candidate: (
                min(float(candidate["flow_confidence"]), float(candidate["product_confidence"])),
                min(int(candidate["flow_support"]), int(candidate["product_support"])),
            ),
            reverse=True,
        )
        for rank, candidate in enumerate(unique_candidates, start=1):
            combined_confidence = min(float(candidate["flow_confidence"]), float(candidate["product_confidence"]))
            minimum_support = min(int(candidate["flow_support"]), int(candidate["product_support"]))
            rows.append(
                {
                    "candidate_context": "nonzero_unmapped_leap_branch",
                    "candidate_status": "proposed",
                    "candidate_rank": rank,
                    "mapping_sheet": "leap_combined_esto",
                    "source_system": "LEAP",
                    "leap_sector_name_full_path": leap_flow,
                    "raw_leap_fuel_name": leap_product,
                    "esto_flow": candidate["esto_flow"],
                    "esto_product": candidate["esto_product"],
                    "source_pair_nonzero": True,
                    "flow_axis_match_method": candidate["flow_method"],
                    "flow_axis_support_count": candidate["flow_support"],
                    "flow_axis_mapping_count": candidate["flow_total"],
                    "flow_axis_confidence": candidate["flow_confidence"],
                    "flow_axis_alternatives": candidate["esto_flow"],
                    "product_axis_match_method": candidate["product_method"],
                    "product_axis_support_count": candidate["product_support"],
                    "product_axis_mapping_count": candidate["product_total"],
                    "product_axis_confidence": candidate["product_confidence"],
                    "product_axis_alternatives": candidate["esto_product"],
                    "missing_axis_evidence": "",
                    "combined_axis_confidence": combined_confidence,
                    "candidate_confidence": candidate_confidence_label(
                        float(candidate["flow_confidence"]),
                        float(candidate["product_confidence"]),
                        minimum_support,
                    ),
                    "source_pair_existing_target_count": 0,
                    "candidate_would_add_another_target": False,
                    "candidate_rationale": candidate["rationale"],
                    "review_warning": "Review branch scope, fuel semantics, hierarchy, and cardinality before copying.",
                    "computer_generated_review_only": True,
                }
            )
    return pd.DataFrame(rows).reindex(columns=CANDIDATE_OUTPUT_COLUMNS)


def select_highly_recommended_candidates(candidate_df: pd.DataFrame) -> pd.DataFrame:
    """Keep complete, non-zero, unambiguous candidates that are ready to paste.

    Lower-confidence and incomplete inferences stay in their original QA files
    and are deliberately excluded from the copy-ready candidate outputs.
    """
    if candidate_df.empty:
        return pd.DataFrame(columns=CANDIDATE_OUTPUT_COLUMNS)
    working_df = candidate_df.copy()
    source_nonzero = working_df["source_pair_nonzero"].fillna(False).astype(bool)
    adds_target = working_df["candidate_would_add_another_target"].fillna(False).astype(bool)
    recommended_df = working_df[
        working_df["candidate_status"].eq("proposed")
        & working_df["candidate_confidence"].eq("high")
        & source_nonzero
        & ~adds_target
        & working_df["esto_flow"].fillna("").astype(str).str.strip().ne("")
        & working_df["esto_product"].fillna("").astype(str).str.strip().ne("")
    ].copy()
    if recommended_df.empty:
        return pd.DataFrame(columns=CANDIDATE_OUTPUT_COLUMNS)
    recommended_df["candidate_status"] = "highly_recommended_copy_ready"
    recommended_df["derived_from_existing_axis_mappings"] = True
    recommended_df["paste_ready"] = True
    recommended_df["paste_instruction"] = recommended_df["mapping_sheet"].map(
        {
            "leap_combined_esto": (
                "Paste leap_sector_name_full_path, raw_leap_fuel_name, esto_flow, and esto_product "
                "into leap_combined_esto; then rerun maintenance and Stages 1-3."
            ),
            "ninth_pairs_to_esto_pairs": (
                "Paste 9th_sector, 9th_fuel, esto_flow, and esto_product into "
                "ninth_pairs_to_esto_pairs; then rerun maintenance and Stages 1-3."
            ),
        }
    ).fillna("Paste the populated source and ESTO target columns into the named mapping sheet, then rerun the pipeline.")
    key_columns = [
        "mapping_sheet",
        "leap_sector_name_full_path",
        "raw_leap_fuel_name",
        "9th_sector",
        "9th_fuel",
        "esto_flow",
        "esto_product",
    ]
    recommended_df = recommended_df.reindex(columns=CANDIDATE_OUTPUT_COLUMNS)
    return recommended_df.fillna("").drop_duplicates(key_columns)

#%%
