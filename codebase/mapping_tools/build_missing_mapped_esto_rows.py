#%%
"""Build reviewed, paste-ready ESTO zero rows without editing source data.

Required rows come from three auditable sources: always-required structural
pairs, non-zero Ninth rows mapped to reviewed new ESTO categories, and the
``16.01.99`` completion child.  Output columns always match the source ESTO
CSV exactly so a researcher can review and paste the rows manually.
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
        "source_flow_prefix": "09.06",
        "source_ninth_sector_prefix": "09_06",
        "target_flows": [
            "09.06.02.01 Liquefaction",
            "09.06.02.02 Regasification",
        ],
        "reason": "Fuel has non-zero data within 09.06 in ESTO or Ninth data",
    },
    "structural_completion": {
        "parent_flow": "16.01 Commercial and public services",
        "completion_child_flow": "16.01.99 Commercial and public services unallocated",
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
    required = ["9th_sector", "9th_fuel", "esto_flow", "esto_product"]
    missing = [column for column in required if column not in mappings.columns]
    if missing:
        raise ValueError(f"ninth_pairs_to_esto_pairs is missing columns: {missing}")

    remove_mask = mappings.get("remove_row", pd.Series(False, index=mappings.index)).map(_truthy)
    duplicate_mask = mappings.get("duplicate_to_remove", pd.Series(False, index=mappings.index)).map(_truthy)
    mappings = mappings[~(remove_mask | duplicate_mask)].copy()
    mappings["flow_code"] = mappings["esto_flow"].map(extract_simple_esto_code)
    mappings["product_code"] = mappings["esto_product"].map(extract_simple_esto_code)
    mappings = mappings[mappings["flow_code"].ne("") & mappings["product_code"].ne("")].copy()
    mappings["9th_sector"] = mappings["9th_sector"].map(_normalise_text)
    mappings["9th_fuel"] = mappings["9th_fuel"].map(_normalise_text)
    return mappings


def _read_ninth_nonzero_evidence(ninth_csv_path: Path) -> pd.DataFrame:
    """Return economy-specific deepest Ninth pairs with any non-zero year."""
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

    ninth["9th_sector"] = ""
    for column in NINTH_SECTOR_COLUMNS:
        values = ninth[column].map(_normalise_text)
        usable = values.ne("") & values.ne("x")
        ninth.loc[usable, "9th_sector"] = values[usable]

    ninth["9th_fuel"] = ninth["fuels"].map(_normalise_text)
    subfuel = ninth["subfuels"].map(_normalise_text)
    usable_subfuel = subfuel.ne("") & subfuel.ne("x")
    ninth.loc[usable_subfuel, "9th_fuel"] = subfuel[usable_subfuel]
    ninth["economy_key"] = ninth["economy"].map(_normalise_economy)

    return ninth[["economy_key", "9th_sector", "9th_fuel"]].drop_duplicates().reset_index(drop=True)


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


def _nonzero_esto_0906_products(esto: pd.DataFrame) -> pd.DataFrame:
    """Return ESTO products with any non-zero value under flow 09.06."""
    year_columns = [column for column in esto.columns if str(column).isdigit()]
    working = esto[["flows", "products", *year_columns]].copy()
    working["flow_code"] = working["flows"].map(extract_simple_esto_code)
    working = working[working["flow_code"].str.startswith("09.06", na=False)].copy()
    if working.empty:
        return pd.DataFrame(columns=["product_code", "products"])
    values = working[year_columns].apply(pd.to_numeric, errors="coerce").fillna(0.0).abs()
    working = working[values.gt(0).any(axis=1)].copy()
    working["product_code"] = working["products"].map(extract_simple_esto_code)
    working = working[working["product_code"].ne("")]
    return working.groupby("product_code", as_index=False).agg(
        products=("products", _preferred_label),
    )


def _required_candidates(
    esto: pd.DataFrame,
    mappings: pd.DataFrame,
    ninth_nonzero: pd.DataFrame,
) -> pd.DataFrame:
    """Build economy-level candidates from the three reviewed rule sources."""
    economies = sorted(esto["economy"].dropna().map(_normalise_text).loc[lambda values: values.ne("")].unique())
    economy_by_key = {_normalise_economy(economy): economy for economy in economies}
    flow_labels, product_labels = _source_label_lookups(esto)
    product_codes = {
        code for code in esto["products"].map(extract_simple_esto_code) if code
    } | set(mappings["product_code"])
    parent_product_codes = _parent_codes(product_codes)
    candidates: list[dict[str, object]] = []

    # 1. Always-required LNG rows, including every product with non-zero 09.06 data.
    required_lng_pairs = list(ESTO_BALANCE_CHANGE_PLAN["always_required_pairs"])
    lng_products = _nonzero_esto_0906_products(esto)
    nonzero_pair_keys = set(map(tuple, ninth_nonzero[["9th_sector", "9th_fuel"]].itertuples(index=False, name=None)))
    ninth_0906 = mappings[
        mappings["9th_sector"].str.startswith(ESTO_BALANCE_CHANGE_PLAN["lng_split"]["source_ninth_sector_prefix"])
        & mappings.apply(lambda row: (row["9th_sector"], row["9th_fuel"]) in nonzero_pair_keys, axis=1)
    ]
    mapped_lng_products = ninth_0906[["product_code", "esto_product"]].drop_duplicates()
    all_lng_products = pd.concat(
        [
            lng_products.rename(columns={"products": "esto_product"}),
            mapped_lng_products,
        ],
        ignore_index=True,
    ).groupby("product_code", as_index=False).agg(
        esto_product=("esto_product", _preferred_label),
    )
    for _, row in all_lng_products.iterrows():
        for flow in ESTO_BALANCE_CHANGE_PLAN["lng_split"]["target_flows"]:
            required_lng_pairs.append({
                "flow": flow,
                "product": row["esto_product"],
                "is_subtotal": row["product_code"] in parent_product_codes,
                "reason": ESTO_BALANCE_CHANGE_PLAN["lng_split"]["reason"],
            })

    seen_lng_pairs: set[tuple[str, str]] = set()
    for pair in required_lng_pairs:
        key = (extract_simple_esto_code(pair["flow"]), extract_simple_esto_code(pair["product"]))
        if not all(key) or key in seen_lng_pairs:
            continue
        seen_lng_pairs.add(key)
        flow = flow_labels.get(key[0], pair["flow"])
        product = product_labels.get(key[1], pair["product"])
        for economy in economies:
            candidates.append(_make_candidate(
                economy=economy,
                flow=flow,
                product=product,
                is_subtotal=bool(pair["is_subtotal"]),
                requirement_source="always_required",
                reason=str(pair["reason"]),
            ))

    # 2. Non-zero Ninth rows mapped to reviewed new ESTO flows or products.
    reviewed_flows = set(ESTO_BALANCE_CHANGE_PLAN["new_esto_categories"]["flows"])
    reviewed_products = set(ESTO_BALANCE_CHANGE_PLAN["new_esto_categories"]["products"])
    reviewed_mappings = mappings[
        mappings["esto_flow"].map(_normalise_text).isin(reviewed_flows)
        | mappings["esto_product"].map(_normalise_text).isin(reviewed_products)
    ].copy()
    evidenced = reviewed_mappings.merge(
        ninth_nonzero,
        on=["9th_sector", "9th_fuel"],
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
            source_ninth_sector=row["9th_sector"],
            source_ninth_fuel=row["9th_fuel"],
        ))

    # 3. One completion child for every economy/product present under 16.01.
    structural = ESTO_BALANCE_CHANGE_PLAN["structural_completion"]
    parent_code = extract_simple_esto_code(structural["parent_flow"])
    parent_rows = esto.copy()
    parent_rows["flow_code"] = parent_rows["flows"].map(extract_simple_esto_code)
    parent_rows = parent_rows[parent_rows["flow_code"].eq(parent_code)]
    for _, row in parent_rows[["economy", "products"]].drop_duplicates().iterrows():
        candidates.append(_make_candidate(
            economy=row["economy"],
            flow=structural["completion_child_flow"],
            product=row["products"],
            is_subtotal=bool(structural["is_subtotal"]),
            requirement_source="structural_completion",
            reason=structural["reason"],
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


def build_missing_mapped_esto_rows(
    esto_csv_path: Path,
    mapping_workbook_path: Path,
    ninth_csv_path: Path,
    active_ninth_mappings: pd.DataFrame | None = None,
    ninth_nonzero_evidence: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return source-shaped paste rows and a row-level explanation audit."""
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
    ninth_nonzero = (
        _read_ninth_nonzero_evidence(ninth_csv_path)
        if ninth_nonzero_evidence is None
        else ninth_nonzero_evidence.copy()
    )
    candidates = _deduplicate_candidates(_required_candidates(esto, mappings, ninth_nonzero))

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
    audit = audit.sort_values(["requirement_source", "economy", "flows", "products"]).reset_index(drop=True)
    return paste_ready, audit


def write_missing_mapped_esto_rows(
    esto_csv_paths: list[Path],
    mapping_workbook_path: Path,
    ninth_csv_path: Path,
    output_dir: Path,
) -> pd.DataFrame:
    """Write one clean paste file and one explanation audit per ESTO vintage."""
    output_dir.mkdir(parents=True, exist_ok=True)
    mappings = _active_ninth_mappings(mapping_workbook_path)
    ninth_nonzero = _read_ninth_nonzero_evidence(ninth_csv_path)
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
        )
        output_path = output_dir / f"{esto_csv_path.stem}_missing_mapped_rows.csv"
        audit_path = output_dir / f"{esto_csv_path.stem}_missing_mapped_rows_audit.csv"
        paste_ready.to_csv(output_path, index=False)
        audit.to_csv(audit_path, index=False)
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
            "output_file": str(output_path),
            "audit_file": str(audit_path),
        })
        print(
            f"  {esto_csv_path.name}: {len(paste_ready):,} paste-ready rows "
            f"(always={int(counts.get('always_required', 0)):,}, "
            f"Ninth={int(counts.get('ninth_driven', 0)):,}, "
            f"completion={int(counts.get('structural_completion', 0)):,})"
        )

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_dir / "missing_mapped_esto_rows_summary.csv", index=False)
    return summary


#%%
