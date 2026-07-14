#%%
"""Build reviewed, paste-ready ESTO rows without editing source data.

Required rows come from three auditable sources: always-required structural
pairs, non-zero Ninth rows mapped to reviewed new ESTO categories, and the
``16.01.99`` completion child. LNG and completion rows receive calculated
values; other mapping-driven placeholders remain zero. Output columns always
match the source ESTO CSV exactly for manual review and insertion.
"""

#%%
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


#%%
REQUIRED_ESTO_COLUMNS = ("economy", "flows", "products")
SIMPLE_ESTO_CODE_PATTERN = re.compile(r"\d+(?:\.\d+)*")
NINTH_SECTOR_COLUMNS = ["sectors", "sub1sectors", "sub2sectors", "sub3sectors", "sub4sectors"]
NINTH_FUEL_COLUMNS = ["fuels", "subfuels"]

ESTO_BALANCE_CHANGE_PLAN = {
    "new_esto_categories": {
        "flows": [
            "09.13 Hydrogen transformation",
            "09.13.01 Electrolysers",
            "09.13.02 SMR wo CCS",
            "09.13.03 SMR w CCS",
            "09.06.02.01 Liquefaction",
            "09.06.02.02 Regasification",
            "16.01.01 Datacentres",
            "16.01.99 Commercial and public services unallocated",
        ],
        "products": [
            "16.10 Ammonia",
            "16.11 E-fuel",
            "16.12 Hydrogen",
        ],
    },
    "always_required_pairs": [
        {
            "flow": "09.06.02.01 Liquefaction",
            "product": "08.01 Natural gas",
            "is_subtotal": False,
            "reason": "Confirmed LNG split row",
        },
        {
            "flow": "09.06.02.01 Liquefaction",
            "product": "08.02 LNG",
            "is_subtotal": False,
            "reason": "Confirmed LNG split row",
        },
        {
            "flow": "09.06.02.02 Regasification",
            "product": "08.01 Natural gas",
            "is_subtotal": False,
            "reason": "Confirmed LNG split row",
        },
        {
            "flow": "09.06.02.02 Regasification",
            "product": "08.02 LNG",
            "is_subtotal": False,
            "reason": "Confirmed LNG split row",
        },
    ],
    "lng_split": {
        "ninth_sector": "09_06_02_liquefaction_regasification_plants",
        "target_flows": [
            "09.06.02.01 Liquefaction",
            "09.06.02.02 Regasification",
        ],
        "reason": "Matched Ninth sector/fuel has non-zero data in at least one year",
    },
    "structural_completion": {
        "parent_flow": "16.01 Commercial and public services",
        "completion_child_flow": "16.01.99 Commercial and public services unallocated",
        "ninth_sector": "16_01_01_commercial_and_public_services",
        "is_subtotal": False,
        "reason": (
            "Ensure 16.01 has complete child coverage. 16.01.01 Datacentres only "
            "covers part of electricity, so 16.01.99 holds the remaining "
            "commercial/public services demand."
        ),
    },
}

REQUIREMENT_PRIORITY = {
    "structural_completion": 0,
    "always_required": 1,
    "ninth_driven": 2,
}


#%%
def _truthy(value: object) -> bool:
    """Return True only for explicit true-like values."""
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _normalise_text(value: object) -> str:
    """Strip and collapse whitespace for comparisons."""
    if pd.isna(value):
        return ""
    return " ".join(str(value).split())


def _normalise_economy(value: object) -> str:
    """Match compact ESTO and underscored Ninth economy codes."""
    return _normalise_text(value).replace("_", "")


def extract_simple_esto_code(label: object) -> str:
    """Return one dot-notation ESTO code, excluding generated lists/ranges."""
    text = _normalise_text(label)
    if not text:
        return ""
    code = text.split(" ", 1)[0]
    return code if SIMPLE_ESTO_CODE_PATTERN.fullmatch(code) else ""


def _preferred_label(values: pd.Series) -> str:
    """Choose the most frequent nonblank label, with a stable tie break."""
    clean = values.dropna().map(_normalise_text)
    clean = clean[clean.ne("")]
    if clean.empty:
        return ""
    counts = clean.value_counts()
    return sorted(counts[counts.eq(counts.max())].index)[0]


def _parent_codes(codes: set[str]) -> set[str]:
    """Return dot-notation codes that have at least one descendant."""
    return {
        code
        for code in codes
        if any(other.startswith(code + ".") for other in codes if other != code)
    }


def _active_ninth_mappings(mapping_workbook_path: Path) -> pd.DataFrame:
    """Load active Ninth-to-ESTO rows with only simple target pairs."""
    mappings = pd.read_excel(
        mapping_workbook_path,
        sheet_name="ninth_pairs_to_esto_pairs",
        dtype=object,
    ).fillna("")
    required = ["ninth_sector", "ninth_fuel", "esto_flow", "esto_product"]
    missing = [column for column in required if column not in mappings.columns]
    if missing:
        raise ValueError(f"ninth_pairs_to_esto_pairs is missing columns: {missing}")

    remove_mask = mappings.get("remove_row", pd.Series(False, index=mappings.index)).map(_truthy)
    duplicate_mask = mappings.get("duplicate_to_remove", pd.Series(False, index=mappings.index)).map(_truthy)
    mappings = mappings[~(remove_mask | duplicate_mask)].copy()
    mappings["flow_code"] = mappings["esto_flow"].map(extract_simple_esto_code)
    mappings["product_code"] = mappings["esto_product"].map(extract_simple_esto_code)
    mappings = mappings[mappings["flow_code"].ne("") & mappings["product_code"].ne("")].copy()
    mappings["ninth_sector"] = mappings["ninth_sector"].map(_normalise_text)
    mappings["ninth_fuel"] = mappings["ninth_fuel"].map(_normalise_text)
    return mappings


def _read_ninth_nonzero_evidence_and_pairs(
    ninth_csv_path: Path,
) -> tuple[pd.DataFrame, set[tuple[str, str]]]:
    """Read Ninth once and return economy evidence plus global hierarchy pairs."""
    header = pd.read_csv(ninth_csv_path, nrows=0).columns.tolist()
    year_columns = [column for column in header if str(column).isdigit()]
    required = ["economy", *NINTH_SECTOR_COLUMNS, *NINTH_FUEL_COLUMNS]
    missing = [column for column in required if column not in header]
    if missing:
        raise ValueError(f"Ninth file {ninth_csv_path} is missing columns: {missing}")

    ninth = pd.read_csv(
        ninth_csv_path,
        usecols=required + year_columns,
        dtype=object,
        low_memory=False,
    )
    values = ninth[year_columns].apply(pd.to_numeric, errors="coerce").fillna(0.0).abs()
    ninth = ninth[values.gt(0).any(axis=1)].copy()

    ninth["ninth_sector"] = ""
    for column in NINTH_SECTOR_COLUMNS:
        values = ninth[column].map(_normalise_text)
        usable = values.ne("") & values.ne("x")
        ninth.loc[usable, "ninth_sector"] = values[usable]

    ninth["ninth_fuel"] = ninth["fuels"].map(_normalise_text)
    subfuel = ninth["subfuels"].map(_normalise_text)
    usable_subfuel = subfuel.ne("") & subfuel.ne("x")
    ninth.loc[usable_subfuel, "ninth_fuel"] = subfuel[usable_subfuel]
    ninth["economy_key"] = ninth["economy"].map(_normalise_economy)

    economy_evidence = (
        ninth[["economy_key", "ninth_sector", "ninth_fuel"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    pairs: set[tuple[str, str]] = set()
    for sector_column in NINTH_SECTOR_COLUMNS:
        sectors = ninth[sector_column].map(_normalise_text)
        usable = sectors.ne("") & sectors.ne("x")
        pairs.update(
            map(
                tuple,
                pd.DataFrame({
                    "ninth_sector": sectors[usable],
                    "ninth_fuel": ninth.loc[usable, "ninth_fuel"],
                }).drop_duplicates().itertuples(index=False, name=None),
            )
        )
    return economy_evidence, pairs


def _read_ninth_nonzero_evidence(ninth_csv_path: Path) -> pd.DataFrame:
    """Return economy-specific deepest Ninth pairs with any non-zero year."""
    evidence, _pairs = _read_ninth_nonzero_evidence_and_pairs(ninth_csv_path)
    return evidence


def _read_ninth_nonzero_sector_fuel_pairs(ninth_csv_path: Path) -> set[tuple[str, str]]:
    """Return non-zero Ninth sector/fuel pairs across any economy, scenario, or year.

    A sector is matched at every explicit hierarchy level. This lets a reviewed
    aggregate sector such as ``09_06_02_liquefaction_regasification_plants``
    qualify when its non-zero observations are carried by descendant rows.
    """
    _evidence, pairs = _read_ninth_nonzero_evidence_and_pairs(ninth_csv_path)
    return pairs


def _product_to_ninth_fuel_profile(mappings: pd.DataFrame) -> pd.DataFrame:
    """Rank reviewed Ninth fuel candidates for each ESTO product code."""
    profile = (
        mappings[mappings["ninth_fuel"].ne("")]
        .groupby(["product_code", "ninth_fuel"], as_index=False)
        .size()
        .rename(columns={"size": "mapping_support_count"})
    )
    if profile.empty:
        profile["is_best_candidate"] = pd.Series(dtype=bool)
        return profile
    profile["maximum_support"] = profile.groupby("product_code")["mapping_support_count"].transform("max")
    profile["is_best_candidate"] = profile["mapping_support_count"].eq(profile["maximum_support"])
    return profile


def build_reviewed_flow_product_filter_audit(
    esto: pd.DataFrame,
    mappings: pd.DataFrame,
    nonzero_ninth_pairs: set[tuple[str, str]],
) -> pd.DataFrame:
    """Explain which proposed new flow/product pairs pass exact Ninth evidence."""
    flow_labels, product_labels = _source_label_lookups(esto)
    profile = _product_to_ninth_fuel_profile(mappings)
    product_codes = {
        code for code in esto["products"].map(extract_simple_esto_code) if code
    } | set(mappings["product_code"])
    parent_product_codes = _parent_codes(product_codes)

    proposed: list[tuple[str, str, str]] = []
    lng_config = ESTO_BALANCE_CHANGE_PLAN["lng_split"]
    mapped_products = mappings[["product_code", "esto_product"]].drop_duplicates()
    for flow in lng_config["target_flows"]:
        for _, row in mapped_products.iterrows():
            proposed.append((flow, row["product_code"], _normalise_text(row["esto_product"])))
        for pair in ESTO_BALANCE_CHANGE_PLAN["always_required_pairs"]:
            if pair["flow"] == flow:
                proposed.append((flow, extract_simple_esto_code(pair["product"]), pair["product"]))

    completion = ESTO_BALANCE_CHANGE_PLAN["structural_completion"]
    parent_code = extract_simple_esto_code(completion["parent_flow"])
    parent_rows = esto[esto["flows"].map(extract_simple_esto_code).eq(parent_code)]
    for product in parent_rows["products"].dropna().map(_normalise_text).unique():
        proposed.append((completion["completion_child_flow"], extract_simple_esto_code(product), product))

    sector_by_flow = {
        **{flow: lng_config["ninth_sector"] for flow in lng_config["target_flows"]},
        completion["completion_child_flow"]: completion["ninth_sector"],
    }
    rows: list[dict[str, object]] = []
    for flow, product_code, proposed_product in sorted(set(proposed)):
        sector = sector_by_flow[flow]
        candidates = profile[profile["product_code"].eq(product_code)].sort_values(
            ["is_best_candidate", "mapping_support_count", "ninth_fuel"],
            ascending=[False, False, True],
        )
        all_fuels = candidates["ninth_fuel"].astype(str).tolist()
        best_fuels = candidates.loc[candidates["is_best_candidate"], "ninth_fuel"].astype(str).tolist()
        nonzero_best = [fuel for fuel in best_fuels if (sector, fuel) in nonzero_ninth_pairs]
        if not best_fuels:
            status = "unmapped_product"
        elif not nonzero_best:
            status = "zero_only"
        elif len(best_fuels) > 1:
            status = "retained_ambiguous_mapping"
        else:
            status = "retained"
        canonical_product = product_labels.get(product_code, proposed_product)
        rows.append({
            "flows": flow_labels.get(extract_simple_esto_code(flow), flow),
            "products": canonical_product,
            "flow_code": extract_simple_esto_code(flow),
            "product_code": product_code,
            "ninth_sector": sector,
            "all_ninth_fuel_candidates": "; ".join(all_fuels),
            "best_ninth_fuel_candidates": "; ".join(best_fuels),
            "nonzero_best_ninth_fuels": "; ".join(nonzero_best),
            "mapping_candidate_count": len(all_fuels),
            "best_candidate_count": len(best_fuels),
            "is_subtotal": product_code in parent_product_codes,
            "filter_status": status,
            "include_row": bool(nonzero_best),
        })
    return pd.DataFrame(rows).sort_values(["flows", "products"]).reset_index(drop=True)


def _source_label_lookups(esto: pd.DataFrame) -> tuple[dict[str, str], dict[str, str]]:
    """Return stable source labels by simple flow and product code."""
    working = esto[["flows", "products"]].copy()
    working["flow_code"] = working["flows"].map(extract_simple_esto_code)
    working["product_code"] = working["products"].map(extract_simple_esto_code)
    flow_labels = (
        working[working["flow_code"].ne("")]
        .groupby("flow_code")["flows"]
        .agg(_preferred_label)
        .to_dict()
    )
    product_labels = (
        working[working["product_code"].ne("")]
        .groupby("product_code")["products"]
        .agg(_preferred_label)
        .to_dict()
    )
    return flow_labels, product_labels


def _make_candidate(
    economy: str,
    flow: str,
    product: str,
    is_subtotal: bool,
    requirement_source: str,
    reason: str,
    source_ninth_sector: str = "",
    source_ninth_fuel: str = "",
) -> dict[str, object]:
    """Create one normalized candidate row."""
    return {
        "economy": _normalise_text(economy),
        "flows": _normalise_text(flow),
        "products": _normalise_text(product),
        "flow_code": extract_simple_esto_code(flow),
        "product_code": extract_simple_esto_code(product),
        "is_subtotal": bool(is_subtotal),
        "requirement_source": requirement_source,
        "reason": reason,
        "source_ninth_sector": source_ninth_sector,
        "source_ninth_fuel": source_ninth_fuel,
    }


def _required_candidates(
    esto: pd.DataFrame,
    mappings: pd.DataFrame,
    ninth_nonzero: pd.DataFrame,
    filter_audit: pd.DataFrame,
) -> pd.DataFrame:
    """Build economy-level candidates from the three reviewed rule sources."""
    economies = sorted(esto["economy"].dropna().map(_normalise_text).loc[lambda values: values.ne("")].unique())
    economy_by_key = {_normalise_economy(economy): economy for economy in economies}
    flow_labels, product_labels = _source_label_lookups(esto)
    candidates: list[dict[str, object]] = []

    # 1. LNG split rows must pass the exact reviewed Ninth sector/fuel filter.
    lng_config = ESTO_BALANCE_CHANGE_PLAN["lng_split"]
    eligible_lng = filter_audit[
        filter_audit["include_row"]
        & filter_audit["flows"].isin(lng_config["target_flows"])
    ]
    for _, row in eligible_lng.iterrows():
        for economy in economies:
            candidates.append(_make_candidate(
                economy=economy,
                flow=row["flows"],
                product=row["products"],
                is_subtotal=bool(row["is_subtotal"]),
                requirement_source="always_required",
                reason=lng_config["reason"],
                source_ninth_sector=row["ninth_sector"],
                source_ninth_fuel=row["nonzero_best_ninth_fuels"],
            ))

    # 2. Non-zero Ninth rows mapped to reviewed new ESTO flows or products.
    reviewed_flows = set(ESTO_BALANCE_CHANGE_PLAN["new_esto_categories"]["flows"])
    reviewed_products = set(ESTO_BALANCE_CHANGE_PLAN["new_esto_categories"]["products"])
    reviewed_mappings = mappings[
        mappings["esto_flow"].map(_normalise_text).isin(reviewed_flows)
        | mappings["esto_product"].map(_normalise_text).isin(reviewed_products)
    ].copy()
    reviewed_mappings = reviewed_mappings[
        ~reviewed_mappings["esto_flow"].map(_normalise_text).isin(lng_config["target_flows"])
        & ~reviewed_mappings["esto_flow"].map(_normalise_text).eq(
            ESTO_BALANCE_CHANGE_PLAN["structural_completion"]["completion_child_flow"]
        )
    ]
    evidenced = reviewed_mappings.merge(
        ninth_nonzero,
        on=["ninth_sector", "ninth_fuel"],
        how="inner",
    )
    for _, row in evidenced.iterrows():
        economy = economy_by_key.get(row["economy_key"])
        if economy is None:
            continue
        flow = flow_labels.get(row["flow_code"], _normalise_text(row["esto_flow"]))
        product = product_labels.get(row["product_code"], _normalise_text(row["esto_product"]))
        candidates.append(_make_candidate(
            economy=economy,
            flow=flow,
            product=product,
            is_subtotal=_truthy(row.get("esto_pair_is_subtotal", False)),
            requirement_source="ninth_driven",
            reason="Reviewed mapped ESTO category has non-zero Ninth data",
            source_ninth_sector=row["ninth_sector"],
            source_ninth_fuel=row["ninth_fuel"],
        ))

    # 3. Completion rows use the same exact Ninth sector/fuel eligibility rule.
    structural = ESTO_BALANCE_CHANGE_PLAN["structural_completion"]
    parent_code = extract_simple_esto_code(structural["parent_flow"])
    parent_rows = esto.copy()
    parent_rows["flow_code"] = parent_rows["flows"].map(extract_simple_esto_code)
    parent_rows = parent_rows[parent_rows["flow_code"].eq(parent_code)]
    eligible_completion = filter_audit[
        filter_audit["include_row"]
        & filter_audit["flows"].eq(structural["completion_child_flow"])
    ]
    eligible_products = {
        str(row["product_code"]): row
        for _, row in eligible_completion.iterrows()
    }
    for _, row in parent_rows[["economy", "products"]].drop_duplicates().iterrows():
        product_code = extract_simple_esto_code(row["products"])
        eligibility = eligible_products.get(product_code)
        if eligibility is None:
            continue
        candidates.append(_make_candidate(
            economy=row["economy"],
            flow=structural["completion_child_flow"],
            product=row["products"],
            is_subtotal=bool(structural["is_subtotal"]),
            requirement_source="structural_completion",
            reason=structural["reason"],
            source_ninth_sector=eligibility["ninth_sector"],
            source_ninth_fuel=eligibility["nonzero_best_ninth_fuels"],
        ))

    return pd.DataFrame(candidates)


def _deduplicate_candidates(candidates: pd.DataFrame) -> pd.DataFrame:
    """Collapse overlapping requirements to one paste row with an audit trail."""
    if candidates.empty:
        return candidates
    key_columns = ["economy", "flow_code", "product_code"]
    candidates = candidates.copy()
    candidates["_priority"] = candidates["requirement_source"].map(REQUIREMENT_PRIORITY)
    candidates = candidates.sort_values([*key_columns, "_priority"])
    rows: list[dict[str, object]] = []
    for _, group in candidates.groupby(key_columns, sort=False):
        primary = group.iloc[0].to_dict()
        primary["is_subtotal"] = bool(group["is_subtotal"].any())
        primary["requirement_sources"] = "; ".join(sorted(set(group["requirement_source"])))
        primary["reason"] = "; ".join(dict.fromkeys(group["reason"].astype(str)))
        primary["source_ninth_sector"] = "; ".join(sorted(set(group["source_ninth_sector"]) - {""}))
        primary["source_ninth_fuel"] = "; ".join(sorted(set(group["source_ninth_fuel"]) - {""}))
        rows.append(primary)
    return pd.DataFrame(rows).drop(columns=["_priority"])


def _overlay_year_values(base_rows: pd.DataFrame, calculated_rows: pd.DataFrame) -> pd.DataFrame:
    """Replace year values in matching source-shaped rows without adding keys."""
    if base_rows.empty or calculated_rows.empty:
        return base_rows
    output = base_rows.copy()
    year_columns = [column for column in output.columns if str(column).isdigit()]
    calculated = calculated_rows.copy()
    calculated["_key"] = calculated.apply(
        lambda row: (
            _normalise_economy(row["economy"]),
            extract_simple_esto_code(row["flows"]),
            extract_simple_esto_code(row["products"]),
        ),
        axis=1,
    )
    values_by_key = calculated.drop_duplicates("_key").set_index("_key")[year_columns].to_dict("index")
    for index, row in output.iterrows():
        key = (
            _normalise_economy(row["economy"]),
            extract_simple_esto_code(row["flows"]),
            extract_simple_esto_code(row["products"]),
        )
        if key in values_by_key:
            for column in year_columns:
                output.at[index, column] = values_by_key[key][column]
    return output


def build_commercial_public_services_unallocated_rows(
    esto_csv_path: Path,
    eligible_product_codes: set[str] | None = None,
    tolerance: float = 1e-9,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Calculate ``16.01.99 = 16.01 - 16.01.01`` without editing ESTO.

    Missing rows are returned in ``insert_rows``. Existing ``16.01.99`` rows
    whose calculated values differ are returned separately in ``update_rows``.
    The audit records reconciliation, negative remainders, duplicate inputs,
    and the deliberate insert/update/no-change action for every eligible key.
    """
    esto = pd.read_csv(esto_csv_path, dtype=object, low_memory=False)
    source_columns = list(esto.columns)
    year_columns = [column for column in source_columns if str(column).isdigit()]
    config = ESTO_BALANCE_CHANGE_PLAN["structural_completion"]
    parent_code = extract_simple_esto_code(config["parent_flow"])
    datacentre_code = extract_simple_esto_code("16.01.01 Datacentres")
    completion_code = extract_simple_esto_code(config["completion_child_flow"])

    working = esto.copy()
    working["_economy_key"] = working["economy"].map(_normalise_economy)
    working["_flow_code"] = working["flows"].map(extract_simple_esto_code)
    working["_product_code"] = working["products"].map(extract_simple_esto_code)
    for column in year_columns:
        working[column] = pd.to_numeric(working[column], errors="coerce").fillna(0.0)

    parent = working[working["_flow_code"].eq(parent_code)].copy()
    if eligible_product_codes is not None:
        parent = parent[parent["_product_code"].isin(eligible_product_codes)].copy()
    datacentres = working[working["_flow_code"].eq(datacentre_code)].copy()
    existing_completion = working[working["_flow_code"].eq(completion_code)].copy()
    key_columns = ["_economy_key", "_product_code"]

    datacentre_groups = {key: group for key, group in datacentres.groupby(key_columns, dropna=False)}
    completion_groups = {key: group for key, group in existing_completion.groupby(key_columns, dropna=False)}
    insert_rows: list[dict[str, object]] = []
    update_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []

    for key, parent_group in parent.groupby(key_columns, dropna=False):
        parent_row = parent_group.iloc[0]
        datacentre_group = datacentre_groups.get(key)
        completion_group = completion_groups.get(key)
        datacentre_values = (
            datacentre_group[year_columns].sum()
            if datacentre_group is not None
            else pd.Series(0.0, index=year_columns)
        )
        remainder = parent_row[year_columns].astype(float) - datacentre_values.astype(float)
        negative_columns = [column for column in year_columns if float(remainder[column]) < -tolerance]
        reconciled = datacentre_values.astype(float) + remainder
        maximum_error = float((reconciled - parent_row[year_columns].astype(float)).abs().max())

        output_row = {column: parent_row.get(column, pd.NA) for column in source_columns}
        output_row["flows"] = config["completion_child_flow"]
        if "is_subtotal" in source_columns:
            output_row["is_subtotal"] = "FALSE"
        for column in year_columns:
            output_row[column] = float(remainder[column])

        if completion_group is None:
            action = "insert"
            insert_rows.append(output_row)
        else:
            existing_values = completion_group[year_columns].sum().astype(float)
            requires_update = bool((existing_values - remainder).abs().gt(tolerance).any())
            action = "update" if requires_update else "no_change"
            if requires_update:
                update_rows.append(output_row)

        audit_rows.append({
            "economy": parent_row["economy"],
            "products": parent_row["products"],
            "product_code": key[1],
            "datacentres_present": datacentre_group is not None,
            "parent_duplicate_count": len(parent_group),
            "datacentre_duplicate_count": 0 if datacentre_group is None else len(datacentre_group),
            "existing_completion_count": 0 if completion_group is None else len(completion_group),
            "output_action": action,
            "negative_remainder": bool(negative_columns),
            "negative_years": "; ".join(map(str, negative_columns)),
            "minimum_remainder": float(remainder.min()),
            "maximum_reconciliation_error": maximum_error,
            "reconciles_within_tolerance": maximum_error <= tolerance,
            "resolved_cleanly": (
                len(parent_group) == 1
                and (datacentre_group is None or len(datacentre_group) == 1)
                and (completion_group is None or len(completion_group) == 1)
            ),
        })

    insert_df = pd.DataFrame(insert_rows, columns=source_columns)
    update_df = pd.DataFrame(update_rows, columns=source_columns)
    audit_df = pd.DataFrame(audit_rows)
    return insert_df, update_df, audit_df


def build_missing_mapped_esto_rows(
    esto_csv_path: Path,
    mapping_workbook_path: Path,
    ninth_csv_path: Path,
    active_ninth_mappings: pd.DataFrame | None = None,
    ninth_nonzero_evidence: pd.DataFrame | None = None,
    nonzero_ninth_sector_fuel_pairs: set[tuple[str, str]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return source-shaped paste rows and a row-level explanation audit.

    Reviewed Ninth-derived rows pass an exact sector/fuel non-zero filter. LNG
    split and ``16.01.99`` year values are then overlaid from their dedicated
    calculations; other generated rows remain zero-valued placeholders.
    """
    esto = pd.read_csv(esto_csv_path, dtype=object, low_memory=False)
    source_columns = list(esto.columns)
    missing_columns = [column for column in REQUIRED_ESTO_COLUMNS if column not in esto.columns]
    if missing_columns:
        raise ValueError(f"ESTO file {esto_csv_path} is missing columns: {missing_columns}")

    mappings = (
        _active_ninth_mappings(mapping_workbook_path)
        if active_ninth_mappings is None
        else active_ninth_mappings.copy()
    )
    if ninth_nonzero_evidence is None and nonzero_ninth_sector_fuel_pairs is None:
        ninth_nonzero, global_nonzero_pairs = _read_ninth_nonzero_evidence_and_pairs(
            ninth_csv_path
        )
    else:
        ninth_nonzero = (
            _read_ninth_nonzero_evidence(ninth_csv_path)
            if ninth_nonzero_evidence is None
            else ninth_nonzero_evidence.copy()
        )
        global_nonzero_pairs = (
            _read_ninth_nonzero_sector_fuel_pairs(ninth_csv_path)
            if nonzero_ninth_sector_fuel_pairs is None
            else set(nonzero_ninth_sector_fuel_pairs)
        )
    filter_audit = build_reviewed_flow_product_filter_audit(
        esto=esto,
        mappings=mappings,
        nonzero_ninth_pairs=global_nonzero_pairs,
    )
    candidates = _deduplicate_candidates(
        _required_candidates(esto, mappings, ninth_nonzero, filter_audit)
    )

    existing = esto[["economy", "flows", "products"]].copy()
    existing["economy"] = existing["economy"].map(_normalise_economy)
    existing["flow_code"] = existing["flows"].map(extract_simple_esto_code)
    existing["product_code"] = existing["products"].map(extract_simple_esto_code)
    existing_keys = set(map(tuple, existing[["economy", "flow_code", "product_code"]].itertuples(index=False, name=None)))
    candidates["economy_key"] = candidates["economy"].map(_normalise_economy)
    candidates["_exists"] = candidates.apply(
        lambda row: (row["economy_key"], row["flow_code"], row["product_code"]) in existing_keys,
        axis=1,
    )
    missing = candidates[~candidates["_exists"]].copy()

    paste_ready = pd.DataFrame(index=missing.index, columns=source_columns)
    paste_ready["economy"] = missing["economy"].values
    paste_ready["flows"] = missing["flows"].values
    paste_ready["products"] = missing["products"].values
    if "is_subtotal" in source_columns:
        paste_ready["is_subtotal"] = missing["is_subtotal"].map(lambda value: "TRUE" if value else "FALSE").values
    for column in source_columns:
        if str(column).isdigit():
            paste_ready[column] = 0.0

    eligible_lng = filter_audit[
        filter_audit["include_row"]
        & filter_audit["flows"].isin(ESTO_BALANCE_CHANGE_PLAN["lng_split"]["target_flows"])
    ]
    eligible_lng_keys = set(map(tuple, eligible_lng[["flow_code", "product_code"]].itertuples(index=False, name=None)))
    split_rows, _split_audit = build_lng_split_esto_rows(esto_csv_path)
    if not split_rows.empty:
        split_rows = split_rows[
            split_rows.apply(
                lambda row: (
                    extract_simple_esto_code(row["flows"]),
                    extract_simple_esto_code(row["products"]),
                ) in eligible_lng_keys,
                axis=1,
            )
        ]
        paste_ready = _overlay_year_values(paste_ready, split_rows)

    completion_flow = ESTO_BALANCE_CHANGE_PLAN["structural_completion"]["completion_child_flow"]
    eligible_completion_codes = set(
        filter_audit.loc[
            filter_audit["include_row"] & filter_audit["flows"].eq(completion_flow),
            "product_code",
        ].astype(str)
    )
    completion_insert, _completion_update, _completion_audit = (
        build_commercial_public_services_unallocated_rows(
            esto_csv_path=esto_csv_path,
            eligible_product_codes=eligible_completion_codes,
        )
    )
    paste_ready = _overlay_year_values(paste_ready, completion_insert)
    paste_ready = paste_ready.sort_values(["economy", "flows", "products"]).reset_index(drop=True)

    audit_columns = [
        "economy",
        "flows",
        "products",
        "is_subtotal",
        "requirement_source",
        "requirement_sources",
        "reason",
        "source_ninth_sector",
        "source_ninth_fuel",
    ]
    audit = missing[audit_columns].copy()
    audit["source_file"] = esto_csv_path.name
    audit["value_source"] = "zero_placeholder"
    audit.loc[audit["flows"].isin(ESTO_BALANCE_CHANGE_PLAN["lng_split"]["target_flows"]), "value_source"] = (
        "09.06.02 calculated split where source data exists; zero otherwise"
    )
    audit.loc[audit["flows"].eq(completion_flow), "value_source"] = "16.01 parent minus 16.01.01 Datacentres"
    audit = audit.sort_values(["requirement_source", "economy", "flows", "products"]).reset_index(drop=True)
    return paste_ready, audit


LNG_SPLIT_CONFIG = {
    "source_flow_prefix": "09.06.02",
    "liquefaction_flow": "09.06.02.01 Liquefaction",
    "regasification_flow": "09.06.02.02 Regasification",
    "ng_product_prefix": "08.01",
    "lng_product_prefix": "08.02",
}


def _classify_lng_direction_by_year(
    esto: pd.DataFrame,
    economy: str,
    year_cols: list[str],
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return boolean year Series for liquefaction, regasification, and ambiguous.

    Liquefaction: natural gas input (< 0) and LNG output (> 0).
    Regasification: LNG input (< 0) and natural gas output (> 0).
    Ambiguous: all other years with any non-zero NG or LNG activity.

    For ambiguous years the caller pro-rates values by the absolute NG magnitude
    so that even mixed-direction economies (e.g. USA doing both) produce a
    reasonable proportional split rather than losing data.
    """
    cfg = LNG_SPLIT_CONFIG
    source_mask = (
        esto["economy"].map(_normalise_economy).eq(_normalise_economy(economy))
        & esto["flows"].map(extract_simple_esto_code).eq(
            extract_simple_esto_code(cfg["source_flow_prefix"])
        )
    )
    source_rows = esto[source_mask]

    def _product_series(prefix: str) -> pd.Series:
        rows = source_rows[
            source_rows["products"].map(extract_simple_esto_code).str.startswith(prefix, na=False)
            & ~source_rows["products"].map(extract_simple_esto_code).apply(
                lambda c: any(
                    c != prefix and other.startswith(c + ".")
                    for other in source_rows["products"].map(extract_simple_esto_code)
                )
            )
        ]
        if rows.empty:
            return pd.Series(0.0, index=year_cols, dtype=float)
        numeric = rows[year_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
        return numeric.sum()

    ng = _product_series(cfg["ng_product_prefix"])
    lng = _product_series(cfg["lng_product_prefix"])

    liq_mask = (ng < 0) & (lng > 0)
    regas_mask = (ng > 0) & (lng < 0)
    activity_mask = ng.ne(0) | lng.ne(0)
    ambiguous_mask = activity_mask & ~liq_mask & ~regas_mask

    return liq_mask, regas_mask, ambiguous_mask


def _lng_ambiguous_shares(
    esto: pd.DataFrame,
    economy: str,
    year_cols: list[str],
    ambiguous_mask: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    """Return (liq_share, regas_share) Series for ambiguous years only.

    Share is based on the absolute NG contribution from each direction inferred
    from the LNG flow sign: positive LNG implies some liquefaction is occurring,
    negative LNG implies some regasification is occurring.  When neither LNG
    signal is available both shares default to 0.5.
    """
    cfg = LNG_SPLIT_CONFIG
    source_mask = (
        esto["economy"].map(_normalise_economy).eq(_normalise_economy(economy))
        & esto["flows"].map(extract_simple_esto_code).eq(
            extract_simple_esto_code(cfg["source_flow_prefix"])
        )
    )
    lng_rows = esto[
        source_mask
        & esto["products"].map(extract_simple_esto_code).str.startswith(
            cfg["lng_product_prefix"], na=False
        )
    ]
    if lng_rows.empty:
        liq = pd.Series(0.5, index=year_cols, dtype=float)
        return liq, 1.0 - liq

    lng_numeric = lng_rows[year_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).sum()
    lng_positive = lng_numeric.clip(lower=0.0)   # portion attributable to liquefaction
    lng_negative = (-lng_numeric).clip(lower=0.0) # portion attributable to regasification
    total = lng_positive + lng_negative
    zero_total = total.eq(0)
    liq_share = pd.Series(0.0, index=year_cols, dtype=float)
    regas_share = pd.Series(0.0, index=year_cols, dtype=float)
    liq_share[ambiguous_mask & ~zero_total] = (lng_positive / total)[ambiguous_mask & ~zero_total]
    regas_share[ambiguous_mask & ~zero_total] = (lng_negative / total)[ambiguous_mask & ~zero_total]
    liq_share[ambiguous_mask & zero_total] = 0.5
    regas_share[ambiguous_mask & zero_total] = 0.5
    return liq_share, regas_share


def build_lng_split_esto_rows(esto_csv_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split 09.06.02 rows into 09.06.02.01 Liquefaction and 09.06.02.02 Regasification.

    For each economy the direction in each year is determined by the sign of
    the natural gas (08.01) and LNG (08.02) rows:

      Liquefaction  — NG input (< 0) and LNG output (> 0): natural gas → LNG
      Regasification — LNG input (< 0) and NG output (> 0): LNG → natural gas
      Ambiguous      — both directions present in the same year (e.g. USA);
                       values are pro-rated by the absolute LNG magnitude
                       attributed to each direction

    All other products (petroleum products, electricity, gas subtotals) follow
    the same year-direction mask, so their signs are preserved correctly in
    each sub-flow.  Economies with no 09.06.02 data produce no rows.

    Returns (split_rows, audit) DataFrames formatted like the source ESTO CSV.
    """
    cfg = LNG_SPLIT_CONFIG
    esto = pd.read_csv(esto_csv_path, dtype=object, low_memory=False)
    year_cols = [c for c in esto.columns if str(c).isdigit()]
    source_code = extract_simple_esto_code(cfg["source_flow_prefix"])

    source_rows = esto[esto["flows"].map(extract_simple_esto_code).eq(source_code)].copy()
    if source_rows.empty:
        return pd.DataFrame(columns=esto.columns), pd.DataFrame()

    # Prefer the label that already appears in the data for sub-flow names, falling
    # back to the config strings if the child flows don't exist yet.
    flow_labels, _ = _source_label_lookups(esto)
    liq_flow_label = flow_labels.get(
        extract_simple_esto_code(cfg["liquefaction_flow"]), cfg["liquefaction_flow"]
    )
    regas_flow_label = flow_labels.get(
        extract_simple_esto_code(cfg["regasification_flow"]), cfg["regasification_flow"]
    )

    economies = sorted(source_rows["economy"].map(_normalise_text).dropna().unique())
    product_codes = {code for code in esto["products"].map(extract_simple_esto_code) if code}
    parent_product_codes = _parent_codes(product_codes)
    split_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []

    for economy in economies:
        eco_source = source_rows[source_rows["economy"].map(_normalise_text).eq(economy)]
        liq_mask, regas_mask, ambiguous_mask = _classify_lng_direction_by_year(
            esto, economy, year_cols
        )
        if not (liq_mask.any() or regas_mask.any() or ambiguous_mask.any()):
            continue

        liq_share, regas_share = _lng_ambiguous_shares(
            esto, economy, year_cols, ambiguous_mask
        )

        for _, row in eco_source.iterrows():
            numeric = pd.to_numeric(row[year_cols], errors="coerce").fillna(0.0)

            liq_values = numeric.copy()
            liq_values[regas_mask] = 0.0
            liq_values[ambiguous_mask] = numeric[ambiguous_mask] * liq_share[ambiguous_mask]

            regas_values = numeric.copy()
            regas_values[liq_mask] = 0.0
            regas_values[ambiguous_mask] = numeric[ambiguous_mask] * regas_share[ambiguous_mask]

            is_sub = extract_simple_esto_code(row.get("products", "")) in parent_product_codes

            for flow_label, values, direction in (
                (liq_flow_label, liq_values, "liquefaction"),
                (regas_flow_label, regas_values, "regasification"),
            ):
                out: dict[str, object] = {}
                for col in esto.columns:
                    if str(col).isdigit():
                        out[col] = values[col]
                    elif col == "flows":
                        out[col] = flow_label
                    elif col == "is_subtotal":
                        out[col] = "TRUE" if is_sub else "FALSE"
                    else:
                        out[col] = row[col]
                split_rows.append(out)
                audit_rows.append({
                    "economy": economy,
                    "flows": flow_label,
                    "products": _normalise_text(row.get("products", "")),
                    "direction": direction,
                    "liq_years": int(liq_mask.sum()),
                    "regas_years": int(regas_mask.sum()),
                    "ambiguous_years": int(ambiguous_mask.sum()),
                    "nonzero_years_assigned": int(values.ne(0).sum()),
                    "source_file": esto_csv_path.name,
                })

    split_df = pd.DataFrame(split_rows, columns=list(esto.columns)) if split_rows else pd.DataFrame(columns=esto.columns)
    split_df = split_df.sort_values(["economy", "flows", "products"]).reset_index(drop=True)
    audit_df = pd.DataFrame(audit_rows)
    return split_df, audit_df


def write_missing_mapped_esto_rows(
    esto_csv_paths: list[Path],
    mapping_workbook_path: Path,
    ninth_csv_path: Path,
    output_dir: Path,
) -> pd.DataFrame:
    """Write one clean paste file and one explanation audit per ESTO vintage."""
    output_dir.mkdir(parents=True, exist_ok=True)
    mappings = _active_ninth_mappings(mapping_workbook_path)
    ninth_nonzero, global_nonzero_pairs = _read_ninth_nonzero_evidence_and_pairs(
        ninth_csv_path
    )
    summary_rows: list[dict[str, object]] = []
    for esto_csv_path in esto_csv_paths:
        if not esto_csv_path.exists():
            summary_rows.append({
                "source_file": esto_csv_path.name,
                "status": "missing_source_file",
                "missing_pair_count": 0,
                "paste_ready_row_count": 0,
                "always_required_row_count": 0,
                "ninth_driven_row_count": 0,
                "structural_completion_row_count": 0,
                "filter_retained_pair_count": 0,
                "filter_removed_pair_count": 0,
                "filter_ambiguous_pair_count": 0,
                "output_file": "",
                "audit_file": "",
            })
            continue

        paste_ready, audit = build_missing_mapped_esto_rows(
            esto_csv_path=esto_csv_path,
            mapping_workbook_path=mapping_workbook_path,
            ninth_csv_path=ninth_csv_path,
            active_ninth_mappings=mappings,
            ninth_nonzero_evidence=ninth_nonzero,
            nonzero_ninth_sector_fuel_pairs=global_nonzero_pairs,
        )
        output_path = output_dir / f"{esto_csv_path.stem}_missing_mapped_rows.csv"
        audit_path = output_dir / f"{esto_csv_path.stem}_missing_mapped_rows_audit.csv"
        paste_ready.to_csv(output_path, index=False)
        audit.to_csv(audit_path, index=False)

        esto = pd.read_csv(esto_csv_path, dtype=object, low_memory=False)
        filter_audit = build_reviewed_flow_product_filter_audit(
            esto=esto,
            mappings=mappings,
            nonzero_ninth_pairs=global_nonzero_pairs,
        )
        filter_audit_path = output_dir / f"{esto_csv_path.stem}_ninth_nonzero_filter_audit.csv"
        filter_audit.to_csv(filter_audit_path, index=False)

        eligible_lng = filter_audit[
            filter_audit["include_row"]
            & filter_audit["flows"].isin(ESTO_BALANCE_CHANGE_PLAN["lng_split"]["target_flows"])
        ]
        eligible_lng_keys = set(map(tuple, eligible_lng[["flow_code", "product_code"]].itertuples(index=False, name=None)))
        split_rows, split_audit = build_lng_split_esto_rows(esto_csv_path)
        if not split_rows.empty:
            split_rows = split_rows[
                split_rows.apply(
                    lambda row: (
                        extract_simple_esto_code(row["flows"]),
                        extract_simple_esto_code(row["products"]),
                    ) in eligible_lng_keys,
                    axis=1,
                )
            ].reset_index(drop=True)
            split_audit = split_audit[
                split_audit.apply(
                    lambda row: (
                        extract_simple_esto_code(row["flows"]),
                        extract_simple_esto_code(row["products"]),
                    ) in eligible_lng_keys,
                    axis=1,
                )
            ].reset_index(drop=True)
        split_path = output_dir / f"{esto_csv_path.stem}_lng_split_rows.csv"
        split_audit_path = output_dir / f"{esto_csv_path.stem}_lng_split_rows_audit.csv"
        split_rows.to_csv(split_path, index=False)
        split_audit.to_csv(split_audit_path, index=False)

        completion_flow = ESTO_BALANCE_CHANGE_PLAN["structural_completion"]["completion_child_flow"]
        eligible_completion_codes = set(
            filter_audit.loc[
                filter_audit["include_row"] & filter_audit["flows"].eq(completion_flow),
                "product_code",
            ].astype(str)
        )
        completion_insert, completion_update, completion_validation = (
            build_commercial_public_services_unallocated_rows(
                esto_csv_path=esto_csv_path,
                eligible_product_codes=eligible_completion_codes,
            )
        )
        completion_update_path = output_dir / f"{esto_csv_path.stem}_commercial_services_unallocated_updates.csv"
        completion_validation_path = output_dir / f"{esto_csv_path.stem}_commercial_services_unallocated_validation.csv"
        completion_update.to_csv(completion_update_path, index=False)
        completion_validation.to_csv(completion_validation_path, index=False)

        counts = audit["requirement_source"].value_counts()
        summary_rows.append({
            "source_file": esto_csv_path.name,
            "status": "rows_required" if not paste_ready.empty else "complete",
            "missing_pair_count": audit[["flow_code", "product_code"]].drop_duplicates().shape[0]
            if {"flow_code", "product_code"}.issubset(audit.columns) else audit[["flows", "products"]].drop_duplicates().shape[0],
            "paste_ready_row_count": len(paste_ready),
            "always_required_row_count": int(counts.get("always_required", 0)),
            "ninth_driven_row_count": int(counts.get("ninth_driven", 0)),
            "structural_completion_row_count": int(counts.get("structural_completion", 0)),
            "filter_retained_pair_count": int(filter_audit["include_row"].sum()),
            "filter_removed_pair_count": int((~filter_audit["include_row"]).sum()),
            "filter_ambiguous_pair_count": int(filter_audit["best_candidate_count"].gt(1).sum()),
            "lng_split_row_count": len(split_rows),
            "commercial_services_update_row_count": len(completion_update),
            "commercial_services_negative_remainder_count": int(
                completion_validation.get("negative_remainder", pd.Series(dtype=bool)).sum()
            ),
            "commercial_services_unresolved_count": int(
                (~completion_validation.get("resolved_cleanly", pd.Series(dtype=bool))).sum()
            ),
            "output_file": str(output_path),
            "audit_file": str(audit_path),
            "filter_audit_file": str(filter_audit_path),
            "lng_split_file": str(split_path),
            "lng_split_audit_file": str(split_audit_path),
            "commercial_services_update_file": str(completion_update_path),
            "commercial_services_validation_file": str(completion_validation_path),
        })
        print(
            f"  {esto_csv_path.name}: {len(paste_ready):,} paste-ready rows "
            f"(always={int(counts.get('always_required', 0)):,}, "
            f"Ninth={int(counts.get('ninth_driven', 0)):,}, "
            f"completion={int(counts.get('structural_completion', 0)):,}), "
            f"{len(split_rows):,} LNG split rows; "
            f"filter retained={int(filter_audit['include_row'].sum()):,}, "
            f"removed={int((~filter_audit['include_row']).sum()):,}"
        )

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_dir / "missing_mapped_esto_rows_summary.csv", index=False)
    return summary


#%%
