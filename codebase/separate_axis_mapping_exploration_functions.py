#%%
"""Functions for the isolated separate-axis mapping contract exploration.

This module is intentionally non-production. It builds review-only pair
registries, factorises the maintained pair mappings, recompiles candidate
relationships, and measures whether the current contract can be reproduced.
It never writes the canonical mapping workbook.
"""

#%%
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


# --- Stable constants -------------------------------------------------------

ZERO_TOLERANCE = 1e-9
CSV_CHUNK_SIZE = 20_000
MAX_AXIS_COMPONENT_NODE_COUNT = 12
AXIS_COMPONENT_EXCEPTION_COLUMNS = [
    "exception_type",
    "enabled",
    "mapping_name",
    "comparison_scope",
    "axis_name",
    "source_keys",
    "target_keys",
    "notes",
]

MAPPING_SPECS: dict[str, dict[str, str]] = {
    "leap_to_esto": {
        "sheet_name": "leap_combined_esto",
        "source_system": "LEAP",
        "target_system": "ESTO",
        "source_flow_column": "leap_sector_name_full_path",
        "source_product_column": "raw_leap_fuel_name",
        "target_flow_column": "esto_flow",
        "target_product_column": "esto_product",
        "source_subtotal_column": "leap_is_subtotal",
        "target_subtotal_column": "esto_pair_is_subtotal",
    },
    "leap_to_ninth": {
        "sheet_name": "leap_combined_ninth",
        "source_system": "LEAP",
        "target_system": "NINTH",
        "source_flow_column": "leap_sector_name_full_path",
        "source_product_column": "raw_leap_fuel_name",
        "target_flow_column": "ninth_sector",
        "target_product_column": "ninth_fuel",
        "source_subtotal_column": "leap_is_subtotal",
        "target_subtotal_column": "ninth_pair_is_subtotal",
    },
    "ninth_to_esto": {
        "sheet_name": "ninth_pairs_to_esto_pairs",
        "source_system": "NINTH",
        "target_system": "ESTO",
        "source_flow_column": "ninth_sector",
        "source_product_column": "ninth_fuel",
        "target_flow_column": "esto_flow",
        "target_product_column": "esto_product",
        "source_subtotal_column": "ninth_pair_is_subtotal",
        "target_subtotal_column": "esto_pair_is_subtotal",
    },
}

EDITABLE_AXIS_SHEET_SPECS: dict[str, dict[str, str]] = {
    "leap_sector_to_esto": {
        "axis": "flow",
        "mapping_name": "leap_to_esto",
        "source_system": "LEAP",
        "target_system": "ESTO",
        "source_column": "leap_sector",
        "target_column": "esto_flow",
        "scope_column": "esto_dataset_scope",
    },
    "leap_fuel_to_esto": {
        "axis": "product",
        "mapping_name": "leap_to_esto",
        "source_system": "LEAP",
        "target_system": "ESTO",
        "source_column": "leap_fuel",
        "target_column": "esto_product",
        "scope_column": "esto_dataset_scope",
    },
    "leap_sector_to_ninth": {
        "axis": "flow",
        "mapping_name": "leap_to_ninth",
        "source_system": "LEAP",
        "target_system": "NINTH",
        "source_column": "leap_sector",
        "target_column": "ninth_sector",
    },
    "leap_fuel_to_ninth": {
        "axis": "product",
        "mapping_name": "leap_to_ninth",
        "source_system": "LEAP",
        "target_system": "NINTH",
        "source_column": "leap_fuel",
        "target_column": "ninth_fuel",
    },
    "ninth_sector_to_esto": {
        "axis": "flow",
        "mapping_name": "ninth_to_esto",
        "source_system": "NINTH",
        "target_system": "ESTO",
        "source_column": "ninth_sector",
        "target_column": "esto_flow",
        "scope_column": "esto_dataset_scope",
    },
    "ninth_fuel_to_esto": {
        "axis": "product",
        "mapping_name": "ninth_to_esto",
        "source_system": "NINTH",
        "target_system": "ESTO",
        "source_column": "ninth_fuel",
        "target_column": "esto_product",
        "scope_column": "esto_dataset_scope",
    },
}

RELATIONSHIP_KEY_COLUMNS = [
    "mapping_name",
    "comparison_scope",
    "source_system",
    "source_flow",
    "source_product",
    "target_system",
    "target_flow",
    "target_product",
]

SOURCE_PAIR_COLUMNS = [
    "mapping_name",
    "comparison_scope",
    "source_system",
    "source_flow",
    "source_product",
    "target_system",
]


# --- General helpers --------------------------------------------------------

def _clean(value: Any) -> str:
    """Return a stripped text value, treating common null spellings as blank."""
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.casefold() in {"nan", "none", "<na>"} else text


def _truthy(value: Any) -> bool:
    """Use the repository's ordinary truthy convention."""
    return value is True or _clean(value).casefold() in {"true", "1", "1.0", "yes", "y", "t", "on"}


def _normalise_scope(value: Any, target_system: str) -> str:
    """Return a stable mapping scope."""
    if target_system != "ESTO":
        return "NINTH"
    scope = _clean(value).upper()
    return scope if scope in {"ESTO", "ESTO_EXTENDED", "BOTH"} else "BOTH"


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return a SHA-256 fingerprint for a file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_vintage(path: Path) -> str:
    """Extract a readable vintage from a configured source filename."""
    name = Path(path).stem
    match = re.search(r"(20\d{2}(?:\d{4})?)", name)
    return match.group(1) if match else name


def _year_columns(columns: Iterable[Any]) -> list[str]:
    """Return sorted numeric year columns as strings."""
    years = [str(column) for column in columns if str(column).strip().isdigit()]
    return sorted(years, key=int)


def _code_part(label: Any) -> str:
    """Return the code-like first token from an ESTO label."""
    text = _clean(label)
    return text.split(maxsplit=1)[0] if text else ""


def _dot_parent_labels(labels: set[str]) -> set[str]:
    """Identify parent labels from dot-separated ESTO code prefixes."""
    code_to_label = {_code_part(label): label for label in labels if _code_part(label)}
    parents: set[str] = set()
    codes = set(code_to_label)
    for code, label in code_to_label.items():
        if any(other.startswith(code + ".") for other in codes if other != code):
            parents.add(label)
    return parents


def add_ninth_pair_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Add most-specific Ninth sector/fuel columns without changing source rows."""
    result = frame.copy()
    sector_columns = [
        column
        for column in ["sectors", "sub1sectors", "sub2sectors", "sub3sectors", "sub4sectors"]
        if column in result.columns
    ]
    fuel_columns = [column for column in ["fuels", "subfuels"] if column in result.columns]

    if not sector_columns or not fuel_columns:
        raise ValueError("Ninth source is missing sector or fuel hierarchy columns.")

    sector_values = result[sector_columns].fillna("").astype(str).apply(lambda column: column.str.strip())
    sector_values = sector_values.mask(sector_values.apply(lambda column: column.str.casefold().eq("x")))
    result["flow"] = sector_values.ffill(axis=1).iloc[:, -1].fillna("")

    fuel_values = result[fuel_columns].fillna("").astype(str).apply(lambda column: column.str.strip())
    fuel_values = fuel_values.mask(fuel_values.apply(lambda column: column.str.casefold().eq("x")))
    result["product"] = fuel_values.ffill(axis=1).iloc[:, -1].fillna("")
    return result


def _ninth_parent_nodes(frame: pd.DataFrame) -> tuple[set[str], set[str]]:
    """Return structural parent sector/fuel nodes observed in Ninth hierarchy rows."""
    flow_parents: set[str] = set()
    product_parents: set[str] = set()
    sector_columns = [
        column
        for column in ["sectors", "sub1sectors", "sub2sectors", "sub3sectors", "sub4sectors"]
        if column in frame.columns
    ]
    fuel_columns = [column for column in ["fuels", "subfuels"] if column in frame.columns]

    if sector_columns:
        sector_values = frame[sector_columns].fillna("").astype(str).apply(lambda column: column.str.strip())
        for row in sector_values.itertuples(index=False, name=None):
            nodes = [value for value in row if value and value.casefold() != "x"]
            flow_parents.update(nodes[:-1])
    if len(fuel_columns) == 2:
        fuel_values = frame[fuel_columns].fillna("").astype(str).apply(lambda column: column.str.strip())
        has_subfuel = (
            fuel_values[fuel_columns[1]].ne("")
            & ~fuel_values[fuel_columns[1]].str.casefold().eq("x")
        )
        product_parents.update(fuel_values.loc[has_subfuel, fuel_columns[0]].tolist())
    return flow_parents, product_parents


# --- Valid-pair registries --------------------------------------------------

REVIEWED_EXTRA_PAIR_ORIGIN = "reviewed_extra"


def _reviewed_extra_pair_mask(registry: pd.DataFrame) -> pd.Series:
    """Return rows explicitly accepted by the editable extra-pair contract."""
    origins = registry.get(
        "pair_origin",
        pd.Series("", index=registry.index),
    ).map(_clean)
    return origins.eq(REVIEWED_EXTRA_PAIR_ORIGIN)


def merge_reviewed_extra_pairs(
    registry: pd.DataFrame,
    extra_pairs: pd.DataFrame,
    *,
    dataset: str,
) -> pd.DataFrame:
    """Merge human-accepted exact pairs into one generated registry.

    The editable table is intentionally narrow: it contains only ``flow`` and
    ``product``. Presence means accepted. Existing structural rows retain their
    evidence columns but use ``pair_origin = reviewed_extra`` to make the human
    authority explicit. Pairs absent from the dataset are added as accepted
    structural exceptions without claiming that they were observed.
    """
    required = {"flow", "product"}
    missing = required - set(extra_pairs.columns)
    if missing:
        raise ValueError(
            "Reviewed extra-pair table is missing columns: "
            f"{sorted(missing)}"
        )

    result = registry.copy()
    result["flow"] = result["flow"].map(_clean)
    result["product"] = result["product"].map(_clean)
    extras = extra_pairs[["flow", "product"]].copy()
    extras["flow"] = extras["flow"].map(_clean)
    extras["product"] = extras["product"].map(_clean)
    extras = extras[
        extras["flow"].ne("") & extras["product"].ne("")
    ].drop_duplicates()
    if extras.empty:
        return result

    keyed = result.set_index(["flow", "product"], drop=False)
    extra_index = pd.MultiIndex.from_frame(extras[["flow", "product"]])
    existing = extra_index.intersection(keyed.index)
    if len(existing):
        keyed.loc[existing, "pair_origin"] = REVIEWED_EXTRA_PAIR_ORIGIN
        keyed.loc[existing, "pair_universe_member"] = True
        keyed.loc[existing, "pair_universe_authority"] = (
            "reviewed_extra_key_pair"
        )
        if "temporal_evidence_status" in keyed.columns:
            keyed.loc[existing, "temporal_evidence_status"] = (
                "reviewed_extra_pair"
            )
    result = keyed.reset_index(drop=True)

    result_index = pd.MultiIndex.from_frame(result[["flow", "product"]])
    missing_rows = extras.loc[~extra_index.isin(result_index)].copy()
    if not missing_rows.empty:
        missing_rows["dataset"] = dataset
        missing_rows["pair_is_subtotal"] = False
        missing_rows["pair_exists_in_dataset"] = False
        missing_rows["pair_universe_member"] = True
        missing_rows["pair_status"] = "reviewed_extra"
        missing_rows["historical_boundary_active"] = False
        missing_rows["projection_future_active"] = False
        missing_rows["temporal_evidence_status"] = "reviewed_extra_pair"
        missing_rows["pair_universe_authority"] = (
            "reviewed_extra_key_pair"
        )
        missing_rows["pair_origin"] = REVIEWED_EXTRA_PAIR_ORIGIN
        result = pd.concat([result, missing_rows], ignore_index=True)

    return result.sort_values(
        ["flow", "product"],
        kind="stable",
    ).reset_index(drop=True)


def derive_required_reviewed_extra_pairs(
    current_relationships: pd.DataFrame,
    pair_universes: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """Bootstrap distinct inactive/absent pairs required by the master.

    This function is used only when the editable extra-pair sheets do not yet
    exist. Once those sheets have been created, their rows are loaded directly
    so a user's deletion remains effective.
    """
    required_by_dataset: dict[str, list[pd.DataFrame]] = {
        "LEAP": [],
        "ESTO": [],
        "ESTO_EXTENDED": [],
        "NINTH": [],
    }

    for source_system in ("LEAP", "NINTH"):
        source = current_relationships.loc[
            current_relationships["source_system"].eq(source_system),
            ["source_flow", "source_product"],
        ].rename(
            columns={
                "source_flow": "flow",
                "source_product": "product",
            }
        )
        required_by_dataset[source_system].append(source)

    ninth_targets = current_relationships.loc[
        current_relationships["target_system"].eq("NINTH"),
        ["target_flow", "target_product"],
    ].rename(
        columns={
            "target_flow": "flow",
            "target_product": "product",
        }
    )
    required_by_dataset["NINTH"].append(ninth_targets)

    esto_targets = current_relationships.loc[
        current_relationships["target_system"].eq("ESTO"),
        ["comparison_scope", "target_flow", "target_product"],
    ].copy()
    esto_targets = esto_targets.rename(
        columns={
            "target_flow": "flow",
            "target_product": "product",
        }
    )
    scopes = esto_targets["comparison_scope"].map(_clean).str.upper()
    required_by_dataset["ESTO"].append(
        esto_targets.loc[
            scopes.isin({"ESTO", "BOTH"}),
            ["flow", "product"],
        ]
    )
    required_by_dataset["ESTO_EXTENDED"].append(
        esto_targets.loc[
            scopes.isin({"ESTO_EXTENDED", "BOTH"}),
            ["flow", "product"],
        ]
    )

    active_columns = {
        "LEAP": None,
        "ESTO": "historical_boundary_active",
        "ESTO_EXTENDED": "historical_boundary_active",
        "NINTH": "projection_future_active",
    }
    result: dict[str, pd.DataFrame] = {}
    for dataset, frames in required_by_dataset.items():
        required = pd.concat(frames, ignore_index=True)
        required["flow"] = required["flow"].map(_clean)
        required["product"] = required["product"].map(_clean)
        required = required[
            required["flow"].ne("") & required["product"].ne("")
        ].drop_duplicates()

        registry = pair_universes[dataset].copy()
        active_column = active_columns[dataset]
        if active_column is None:
            eligible = pd.Series(True, index=registry.index)
        else:
            eligible = registry.get(
                active_column,
                pd.Series(False, index=registry.index),
            ).fillna(False).astype(bool)
        eligible = eligible | _reviewed_extra_pair_mask(registry)
        eligible_pairs = registry.loc[
            eligible,
            ["flow", "product"],
        ].drop_duplicates()
        extra = required.merge(
            eligible_pairs.assign(_already_eligible=True),
            on=["flow", "product"],
            how="left",
        )
        already_eligible = (
            extra["_already_eligible"].fillna(False).astype(bool)
        )
        result[dataset] = extra.loc[
            ~already_eligible,
            ["flow", "product"],
        ].sort_values(
            ["flow", "product"],
            kind="stable",
        ).reset_index(drop=True)
    return result


def expand_pair_universe_with_rollups(
    registry: pd.DataFrame,
    rules_df: pd.DataFrame,
    *,
    input_flow_column: str,
    input_product_column: str,
    rolled_flow_column: str,
    rolled_product_column: str,
    dataset_scope: str | None = None,
) -> pd.DataFrame:
    """Add every pair deterministically derivable from active rollup rules.

    Blank input products match every product and blank rolled products preserve
    the matched product. Rules are applied repeatedly so a rolled pair can feed
    a later rollup. ``pair_origin`` is the only public provenance field needed:
    raw pairs remain ``raw``, derived pairs are ``rollup``, and exact overlaps
    are labelled ``raw_and_rollup``.
    """
    required_registry = {"flow", "product"}
    missing_registry = required_registry - set(registry.columns)
    if missing_registry:
        raise ValueError(
            "Pair registry is missing required columns: "
            f"{sorted(missing_registry)}"
        )
    required_rules = {input_flow_column, rolled_flow_column}
    missing_rules = required_rules - set(rules_df.columns)
    if missing_rules:
        raise ValueError(
            "Rollup rules are missing required columns: "
            f"{sorted(missing_rules)}"
        )

    result = registry.copy()
    result["flow"] = result["flow"].map(_clean)
    result["product"] = result["product"].map(_clean)
    result = result[
        result["flow"].ne("") & result["product"].ne("")
    ].drop_duplicates(["flow", "product"], keep="first")
    if "pair_origin" not in result.columns:
        result["pair_origin"] = "raw"
    else:
        result["pair_origin"] = (
            result["pair_origin"].map(_clean).replace("", "raw")
        )

    rules = rules_df.copy()
    if "include" in rules.columns:
        rules = rules[rules["include"].map(_truthy)].copy()
    if dataset_scope and "esto_dataset_scope" in rules.columns:
        scopes = rules["esto_dataset_scope"].map(_clean).str.upper()
        rules = rules[
            scopes.isin({"", "BOTH", dataset_scope.upper()})
        ].copy()
    for column in [
        input_flow_column,
        input_product_column,
        rolled_flow_column,
        rolled_product_column,
    ]:
        if column not in rules.columns:
            rules[column] = ""
        rules[column] = rules[column].map(_clean)
    rules = rules[
        rules[input_flow_column].ne("")
        & rules[rolled_flow_column].ne("")
    ].drop_duplicates(
        [
            input_flow_column,
            input_product_column,
            rolled_flow_column,
            rolled_product_column,
        ]
    )

    boolean_columns = [
        column
        for column in result.columns
        if column
        in {
            "flow_is_parent",
            "product_is_parent",
            "pair_is_subtotal",
            "pair_exists_in_dataset",
            "pair_universe_member",
            "historical_boundary_active",
            "projection_future_active",
            "active_before_or_at_boundary",
        }
    ]
    first_year_column = (
        "first_observed_year"
        if "first_observed_year" in result.columns
        else None
    )
    last_year_column = (
        "last_observed_year"
        if "last_observed_year" in result.columns
        else None
    )

    # A finite rule set reaches closure quickly. The explicit bound protects
    # against accidental cycles while still allowing nested rollups.
    for _ in range(max(len(rules), 1) + 1):
        derived_records: list[dict[str, Any]] = []
        for rule in rules.to_dict("records"):
            matched = result[
                result["flow"].eq(rule[input_flow_column])
            ].copy()
            input_product = rule[input_product_column]
            if input_product:
                matched = matched[
                    matched["product"].eq(input_product)
                ]
            if matched.empty:
                continue

            rolled_product = rule[rolled_product_column]
            subtotal_setting = _clean(rule.get("Subtotal")).casefold()
            grouped = matched.groupby("product", sort=False, dropna=False)
            for product, group in grouped:
                record = group.iloc[0].to_dict()
                record["flow"] = rule[rolled_flow_column]
                record["product"] = rolled_product or _clean(product)
                record["pair_origin"] = "rollup"
                for column in boolean_columns:
                    record[column] = bool(
                        group[column].fillna(False).astype(bool).any()
                    )
                if "pair_exists_in_dataset" in record:
                    record["pair_exists_in_dataset"] = True
                if "pair_universe_member" in record:
                    record["pair_universe_member"] = True
                if "pair_is_subtotal" in record:
                    if subtotal_setting in {"true", "1", "yes"}:
                        record["pair_is_subtotal"] = True
                    elif subtotal_setting in {"false", "0", "no"}:
                        record["pair_is_subtotal"] = False
                if first_year_column:
                    record[first_year_column] = pd.to_numeric(
                        group[first_year_column],
                        errors="coerce",
                    ).min()
                if last_year_column:
                    record[last_year_column] = pd.to_numeric(
                        group[last_year_column],
                        errors="coerce",
                    ).max()
                record["pair_universe_authority"] = (
                    "generated_from_active_rollup_rules"
                )
                if "authority_layer" in record:
                    record["authority_layer"] = "rollup_rule"
                if "source_kind" in record:
                    record["source_kind"] = "rollup_rule"
                derived_records.append(record)

        if not derived_records:
            break
        derived_raw = pd.DataFrame(derived_records)
        combined_records: list[dict[str, Any]] = []
        for _, group in derived_raw.groupby(
            ["flow", "product"],
            sort=False,
            dropna=False,
        ):
            record = group.iloc[0].to_dict()
            for column in boolean_columns:
                record[column] = bool(
                    group[column].fillna(False).astype(bool).any()
                )
            if first_year_column:
                record[first_year_column] = pd.to_numeric(
                    group[first_year_column],
                    errors="coerce",
                ).min()
            if last_year_column:
                record[last_year_column] = pd.to_numeric(
                    group[last_year_column],
                    errors="coerce",
                ).max()
            combined_records.append(record)
        derived = pd.DataFrame(combined_records)
        existing_index = result.set_index(["flow", "product"]).index
        new_mask = ~pd.MultiIndex.from_frame(
            derived[["flow", "product"]]
        ).isin(existing_index)
        new_rows = derived.loc[new_mask].copy()

        overlap = derived.loc[~new_mask].set_index(["flow", "product"])
        if not overlap.empty:
            keyed = result.set_index(["flow", "product"])
            for key in overlap.index.unique():
                current_origin = _clean(keyed.at[key, "pair_origin"])
                if current_origin == "raw":
                    keyed.at[key, "pair_origin"] = "raw_and_rollup"
                for column in boolean_columns:
                    keyed.at[key, column] = bool(
                        _truthy(keyed.at[key, column])
                        or _truthy(overlap.at[key, column])
                    )
            result = keyed.reset_index()

        if new_rows.empty:
            break
        result = pd.concat([result, new_rows], ignore_index=True)

    active_historical = result.get(
        "historical_boundary_active",
        pd.Series(False, index=result.index),
    ).fillna(False).astype(bool)
    active_projection = result.get(
        "projection_future_active",
        pd.Series(False, index=result.index),
    ).fillna(False).astype(bool)
    rollup_only = result["pair_origin"].eq("rollup")
    rollup_involved = result["pair_origin"].isin(
        {"rollup", "raw_and_rollup"}
    )
    if "pair_status" in result.columns:
        result.loc[rollup_only, "pair_status"] = "rollup_derived_pair"
        result.loc[
            rollup_involved & (active_historical | active_projection),
            "pair_status",
        ] = "data_valid"
    if "temporal_evidence_status" in result.columns:
        result.loc[
            rollup_only,
            "temporal_evidence_status",
        ] = "structural_rollup_pair"
        result.loc[
            rollup_involved & active_historical,
            "temporal_evidence_status",
        ] = "historical_boundary_active"
        result.loc[
            rollup_involved & active_projection,
            "temporal_evidence_status",
        ] = "projection_future_active"

    return result.sort_values(
        ["flow", "product"],
        kind="stable",
    ).reset_index(drop=True)

def build_valid_pair_registry(
    source_path: Path,
    dataset: str,
    *,
    scenario_scope: str = "all",
    zero_tolerance: float = ZERO_TOLERANCE,
    chunk_size: int = CSV_CHUNK_SIZE,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build a strict, generated valid-pair registry from a source CSV.

    A pair is ``data_valid`` only when at least one finite value has absolute
    magnitude greater than ``zero_tolerance``. Structurally present rows that
    remain zero across all selected years are retained as ``zero_only``.
    """
    source_path = Path(source_path)
    dataset = dataset.upper()
    if dataset not in {"ESTO", "ESTO_EXTENDED", "NINTH"}:
        raise ValueError(f"Unsupported registry dataset: {dataset}")
    if scenario_scope not in {"all", "reference", "target"}:
        raise ValueError("scenario_scope must be all, reference, or target.")

    header = pd.read_csv(source_path, nrows=0)
    years = _year_columns(header.columns)
    if not years:
        raise ValueError(f"No numeric year columns found in {source_path}")

    if dataset == "NINTH":
        identity_columns = [
            "economy",
            "scenarios",
            "sectors",
            "sub1sectors",
            "sub2sectors",
            "sub3sectors",
            "sub4sectors",
            "fuels",
            "subfuels",
            "subtotal_layout",
            "subtotal_results",
        ]
    else:
        identity_columns = ["economy", "flows", "products", "is_subtotal"]
    use_columns = [column for column in identity_columns + years if column in header.columns]

    stats: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "economies": set(),
            "years": set(),
            "scenarios": set(),
            "nonzero_observation_count": 0,
            "pair_is_subtotal": False,
        }
    )
    flow_parents: set[str] = set()
    product_parents: set[str] = set()
    source_row_count = 0
    selected_row_count = 0

    for chunk in pd.read_csv(
        source_path,
        usecols=use_columns,
        dtype=object,
        low_memory=False,
        chunksize=chunk_size,
    ):
        source_row_count += len(chunk)
        if dataset == "NINTH":
            if scenario_scope != "all":
                scenario_values = chunk["scenarios"].fillna("").astype(str).str.strip().str.casefold()
                chunk = chunk[scenario_values.eq(scenario_scope)].copy()
            if chunk.empty:
                continue
            parent_flows, parent_products = _ninth_parent_nodes(chunk)
            flow_parents.update(parent_flows)
            product_parents.update(parent_products)
            chunk = add_ninth_pair_columns(chunk)
            subtotal_flag = (
                chunk.get("subtotal_layout", pd.Series(False, index=chunk.index)).map(_truthy)
                | chunk.get("subtotal_results", pd.Series(False, index=chunk.index)).map(_truthy)
            )
            scenarios = chunk.get("scenarios", pd.Series("", index=chunk.index)).fillna("").astype(str).str.strip()
        else:
            chunk = chunk.rename(columns={"flows": "flow", "products": "product"})
            subtotal_flag = chunk.get("is_subtotal", pd.Series(False, index=chunk.index)).map(_truthy)
            scenarios = pd.Series("not_applicable", index=chunk.index)

        selected_row_count += len(chunk)
        chunk = chunk.reset_index(drop=True)
        subtotal_flag = subtotal_flag.reset_index(drop=True)
        scenarios = scenarios.reset_index(drop=True)
        chunk["flow"] = chunk["flow"].fillna("").astype(str).str.strip()
        chunk["product"] = chunk["product"].fillna("").astype(str).str.strip()
        valid_identity = chunk["flow"].ne("") & chunk["product"].ne("")
        chunk = chunk.loc[valid_identity].reset_index(drop=True)
        subtotal_flag = subtotal_flag.loc[valid_identity].reset_index(drop=True)
        scenarios = scenarios.loc[valid_identity].reset_index(drop=True)
        if chunk.empty:
            continue

        numeric = chunk[years].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        nonzero = np.isfinite(numeric) & (np.abs(numeric) > zero_tolerance)
        row_has_nonzero = nonzero.any(axis=1)
        economies = chunk.get("economy", pd.Series("", index=chunk.index)).fillna("").astype(str).str.strip()

        pair_groups = chunk.groupby(["flow", "product"], sort=False, dropna=False).indices
        for pair, positions in pair_groups.items():
            positions_array = np.asarray(positions, dtype=int)
            pair_mask = nonzero[positions_array]
            pair_rows_nonzero = row_has_nonzero[positions_array]
            record = stats[(_clean(pair[0]), _clean(pair[1]))]
            record["nonzero_observation_count"] += int(pair_mask.sum())
            record["pair_is_subtotal"] = bool(
                record["pair_is_subtotal"] or subtotal_flag.iloc[positions_array].any()
            )
            record["scenarios"].update(
                value for value in scenarios.iloc[positions_array].map(_clean) if value
            )
            if pair_rows_nonzero.any():
                active_positions = positions_array[pair_rows_nonzero]
                record["economies"].update(
                    value for value in economies.iloc[active_positions].map(_clean) if value
                )
                active_years = np.flatnonzero(pair_mask.any(axis=0))
                record["years"].update(int(years[index]) for index in active_years)

    if dataset != "NINTH":
        labels_flow = {flow for flow, _ in stats}
        labels_product = {product for _, product in stats}
        flow_parents = _dot_parent_labels(labels_flow)
        product_parents = _dot_parent_labels(labels_product)

    fingerprint = file_sha256(source_path)
    records: list[dict[str, Any]] = []
    for (flow, product), record in sorted(stats.items()):
        observed_years = sorted(record["years"])
        nonzero_count = int(record["nonzero_observation_count"])
        records.append(
            {
                "dataset": dataset,
                "flow": flow,
                "product": product,
                "flow_is_parent": flow in flow_parents,
                "product_is_parent": product in product_parents,
                "pair_is_subtotal": bool(record["pair_is_subtotal"]),
                "first_observed_year": observed_years[0] if observed_years else pd.NA,
                "last_observed_year": observed_years[-1] if observed_years else pd.NA,
                "economy_support_count": len(record["economies"]),
                "year_support_count": len(observed_years),
                "nonzero_observation_count": nonzero_count,
                "source_vintage": _source_vintage(source_path),
                "source_fingerprint": fingerprint,
                "pair_status": "data_valid" if nonzero_count > 0 else "zero_only",
                "scenario_scope": scenario_scope if dataset == "NINTH" else "not_applicable",
                "scenarios_observed": "|".join(sorted(record["scenarios"])),
                "registry_review_status": "generated_unreviewed",
            }
        )

    registry = pd.DataFrame(records)
    if not registry.empty:
        registry["first_observed_year"] = registry["first_observed_year"].astype("Int64")
        registry["last_observed_year"] = registry["last_observed_year"].astype("Int64")

    manifest = {
        "dataset": dataset,
        "scenario_scope": scenario_scope if dataset == "NINTH" else "not_applicable",
        "zero_tolerance": zero_tolerance,
        "source_path": str(source_path.resolve()),
        "source_vintage": _source_vintage(source_path),
        "source_fingerprint": fingerprint,
        "source_row_count": source_row_count,
        "selected_row_count": selected_row_count,
        "pair_count": len(registry),
        "data_valid_pair_count": int(registry["pair_status"].eq("data_valid").sum()) if not registry.empty else 0,
        "zero_only_pair_count": int(registry["pair_status"].eq("zero_only").sum()) if not registry.empty else 0,
        "review_status": "generated_unreviewed",
    }
    return registry, manifest


def build_ninth_valid_pair_registry_bundle(
    source_path: Path,
    *,
    zero_tolerance: float = ZERO_TOLERANCE,
    chunk_size: int = CSV_CHUNK_SIZE,
) -> dict[str, tuple[pd.DataFrame, dict[str, Any]]]:
    """Build all/reference/target Ninth registries in one source-file pass.

    This is the refresh-oriented counterpart to ``build_valid_pair_registry``.
    It parses the large Ninth table and converts its year block only once,
    while maintaining independent statistics for each requested scope.
    """
    source_path = Path(source_path)
    header = pd.read_csv(source_path, nrows=0)
    years = _year_columns(header.columns)
    if not years:
        raise ValueError(f"No numeric year columns found in {source_path}")
    identity_columns = [
        "economy",
        "scenarios",
        "sectors",
        "sub1sectors",
        "sub2sectors",
        "sub3sectors",
        "sub4sectors",
        "fuels",
        "subfuels",
        "subtotal_layout",
        "subtotal_results",
    ]
    use_columns = [
        column
        for column in identity_columns + years
        if column in header.columns
    ]
    scopes = ("all", "reference", "target")
    stats_by_scope: dict[
        str,
        dict[tuple[str, str], dict[str, Any]],
    ] = {
        scope: defaultdict(
            lambda: {
                "economies": set(),
                "years": set(),
                "scenarios": set(),
                "nonzero_observation_count": 0,
                "pair_is_subtotal": False,
            }
        )
        for scope in scopes
    }
    flow_parents_by_scope = {scope: set() for scope in scopes}
    product_parents_by_scope = {scope: set() for scope in scopes}
    selected_row_counts = {scope: 0 for scope in scopes}
    source_row_count = 0

    for chunk in pd.read_csv(
        source_path,
        usecols=use_columns,
        dtype=object,
        low_memory=False,
        chunksize=chunk_size,
    ):
        source_row_count += len(chunk)
        chunk = chunk.reset_index(drop=True)
        chunk = add_ninth_pair_columns(chunk)
        chunk["flow"] = chunk["flow"].fillna("").astype(str).str.strip()
        chunk["product"] = chunk["product"].fillna("").astype(str).str.strip()
        scenario_values = (
            chunk["scenarios"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.casefold()
        )
        valid_identity = chunk["flow"].ne("") & chunk["product"].ne("")
        chunk = chunk.loc[valid_identity].reset_index(drop=True)
        scenario_values = scenario_values.loc[valid_identity].reset_index(drop=True)
        if chunk.empty:
            continue

        subtotal_flag = (
            chunk.get("subtotal_layout", pd.Series(False, index=chunk.index)).map(_truthy)
            | chunk.get("subtotal_results", pd.Series(False, index=chunk.index)).map(_truthy)
        )
        numeric = chunk[years].apply(
            pd.to_numeric,
            errors="coerce",
        ).to_numpy(dtype=float)
        nonzero = np.isfinite(numeric) & (np.abs(numeric) > zero_tolerance)
        row_has_nonzero = nonzero.any(axis=1)
        economies = (
            chunk.get("economy", pd.Series("", index=chunk.index))
            .fillna("")
            .astype(str)
            .str.strip()
        )

        scope_masks = {
            "all": np.ones(len(chunk), dtype=bool),
            "reference": scenario_values.eq("reference").to_numpy(),
            "target": scenario_values.eq("target").to_numpy(),
        }
        for scope, scope_mask in scope_masks.items():
            positions_in_scope = np.flatnonzero(scope_mask)
            selected_row_counts[scope] += len(positions_in_scope)
            if len(positions_in_scope) == 0:
                continue
            scope_chunk = chunk.iloc[positions_in_scope]
            parent_flows, parent_products = _ninth_parent_nodes(scope_chunk)
            flow_parents_by_scope[scope].update(parent_flows)
            product_parents_by_scope[scope].update(parent_products)
            pair_groups = scope_chunk.groupby(
                ["flow", "product"],
                sort=False,
                dropna=False,
            ).indices
            for pair, relative_positions in pair_groups.items():
                absolute_positions = positions_in_scope[
                    np.asarray(relative_positions, dtype=int)
                ]
                pair_mask = nonzero[absolute_positions]
                pair_rows_nonzero = row_has_nonzero[absolute_positions]
                record = stats_by_scope[scope][
                    (_clean(pair[0]), _clean(pair[1]))
                ]
                record["nonzero_observation_count"] += int(pair_mask.sum())
                record["pair_is_subtotal"] = bool(
                    record["pair_is_subtotal"]
                    or subtotal_flag.iloc[absolute_positions].any()
                )
                record["scenarios"].update(
                    value
                    for value in scenario_values.iloc[absolute_positions].map(_clean)
                    if value
                )
                if pair_rows_nonzero.any():
                    active_positions = absolute_positions[pair_rows_nonzero]
                    record["economies"].update(
                        value
                        for value in economies.iloc[active_positions].map(_clean)
                        if value
                    )
                    active_years = np.flatnonzero(pair_mask.any(axis=0))
                    record["years"].update(
                        int(years[index]) for index in active_years
                    )

    fingerprint = file_sha256(source_path)
    source_vintage = _source_vintage(source_path)
    bundle: dict[str, tuple[pd.DataFrame, dict[str, Any]]] = {}
    for scope in scopes:
        records: list[dict[str, Any]] = []
        for (flow, product), record in sorted(stats_by_scope[scope].items()):
            observed_years = sorted(record["years"])
            nonzero_count = int(record["nonzero_observation_count"])
            records.append(
                {
                    "dataset": "NINTH",
                    "flow": flow,
                    "product": product,
                    "flow_is_parent": flow in flow_parents_by_scope[scope],
                    "product_is_parent": product in product_parents_by_scope[scope],
                    "pair_is_subtotal": bool(record["pair_is_subtotal"]),
                    "first_observed_year": (
                        observed_years[0] if observed_years else pd.NA
                    ),
                    "last_observed_year": (
                        observed_years[-1] if observed_years else pd.NA
                    ),
                    "economy_support_count": len(record["economies"]),
                    "year_support_count": len(observed_years),
                    "nonzero_observation_count": nonzero_count,
                    "source_vintage": source_vintage,
                    "source_fingerprint": fingerprint,
                    "pair_status": (
                        "data_valid" if nonzero_count > 0 else "zero_only"
                    ),
                    "scenario_scope": scope,
                    "scenarios_observed": "|".join(
                        sorted(record["scenarios"])
                    ),
                    "registry_review_status": "generated_unreviewed",
                }
            )
        registry = pd.DataFrame(records)
        if not registry.empty:
            registry["first_observed_year"] = registry[
                "first_observed_year"
            ].astype("Int64")
            registry["last_observed_year"] = registry[
                "last_observed_year"
            ].astype("Int64")
        manifest = {
            "dataset": "NINTH",
            "scenario_scope": scope,
            "zero_tolerance": zero_tolerance,
            "source_path": str(source_path.resolve()),
            "source_vintage": source_vintage,
            "source_fingerprint": fingerprint,
            "source_row_count": source_row_count,
            "selected_row_count": selected_row_counts[scope],
            "pair_count": len(registry),
            "data_valid_pair_count": int(
                registry["pair_status"].eq("data_valid").sum()
            )
            if not registry.empty
            else 0,
            "zero_only_pair_count": int(
                registry["pair_status"].eq("zero_only").sum()
            )
            if not registry.empty
            else 0,
            "review_status": "generated_unreviewed",
            "refresh_method": "single_pass_scenario_bundle",
        }
        bundle[scope] = (registry, manifest)
    return bundle


def compare_registry_snapshots(
    previous: pd.DataFrame,
    current: pd.DataFrame,
) -> pd.DataFrame:
    """Return added, disappeared, and status-changed pair rows."""
    keys = ["flow", "product"]
    previous_cols = keys + [
        "pair_status",
        "pair_is_subtotal",
        "flow_is_parent",
        "product_is_parent",
        "source_vintage",
        "source_fingerprint",
    ]
    current_cols = list(previous_cols)
    left = previous[previous_cols].rename(
        columns={column: f"previous_{column}" for column in previous_cols if column not in keys}
    )
    right = current[current_cols].rename(
        columns={column: f"current_{column}" for column in current_cols if column not in keys}
    )
    delta = left.merge(right, on=keys, how="outer", indicator=True)

    def _classify(row: pd.Series) -> str:
        if row["_merge"] == "right_only":
            return "added"
        if row["_merge"] == "left_only":
            return "missing_in_current_vintage"
        changed_fields = [
            "pair_status",
            "pair_is_subtotal",
            "flow_is_parent",
            "product_is_parent",
        ]
        if any(row[f"previous_{field}"] != row[f"current_{field}"] for field in changed_fields):
            return "status_changed"
        return "unchanged"

    delta["delta_status"] = delta.apply(_classify, axis=1)
    delta["recommended_review_state"] = delta["delta_status"].map(
        {
            "added": "review_before_acceptance",
            "missing_in_current_vintage": "pending_confirmation",
            "status_changed": "review_before_acceptance",
            "unchanged": "carry_forward",
        }
    )
    delta["recommended_mapping_action"] = delta["delta_status"].map(
        {
            "added": "do_not_add_mapping_automatically",
            "missing_in_current_vintage": "retain_mapping_and_mark_pair_pending",
            "status_changed": "retain_mapping_pending_review",
            "unchanged": "none",
        }
    )
    return delta.drop(columns="_merge").sort_values(keys).reset_index(drop=True)


# --- Pair mappings and separate-axis compilation ---------------------------

def load_active_mapping_contract(
    workbook_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load complete active pair relationships plus incomplete-row diagnostics."""
    workbook_path = Path(workbook_path)
    relationship_frames: list[pd.DataFrame] = []
    incomplete_frames: list[pd.DataFrame] = []

    for mapping_name, spec in MAPPING_SPECS.items():
        frame = pd.read_excel(workbook_path, sheet_name=spec["sheet_name"], dtype=object)
        frame.columns = [str(column).strip() for column in frame.columns]
        frame.insert(0, "workbook_row_number", frame.index + 2)
        active = pd.Series(True, index=frame.index)
        for flag_column in ["remove_row", "duplicate_to_remove"]:
            if flag_column in frame:
                active &= ~frame[flag_column].map(_truthy)
        frame = frame.loc[active].copy()

        normalised = pd.DataFrame(
            {
                "mapping_name": mapping_name,
                "source_sheet": spec["sheet_name"],
                "workbook_row_number": frame["workbook_row_number"],
                "source_system": spec["source_system"],
                "source_flow": frame[spec["source_flow_column"]].map(_clean),
                "source_product": frame[spec["source_product_column"]].map(_clean),
                "target_system": spec["target_system"],
                "target_flow": frame[spec["target_flow_column"]].map(_clean),
                "target_product": frame[spec["target_product_column"]].map(_clean),
                "source_pair_is_subtotal": (
                    frame.get(
                        spec["source_subtotal_column"],
                        pd.Series(False, index=frame.index),
                    )
                    .map(_truthy)
                ),
                "target_pair_is_subtotal": (
                    frame.get(spec["target_subtotal_column"], pd.Series(False, index=frame.index))
                    .map(_truthy)
                ),
                "comparison_scope": [
                    _normalise_scope(value, spec["target_system"])
                    for value in frame.get("esto_dataset_scope", pd.Series("BOTH", index=frame.index))
                ],
                "notes": frame.get("Note", frame.get("notes", pd.Series("", index=frame.index))).map(_clean),
            }
        )
        complete_mask = normalised[
            ["source_flow", "source_product", "target_flow", "target_product"]
        ].ne("").all(axis=1)
        incomplete = normalised.loc[~complete_mask].copy()
        if not incomplete.empty:
            incomplete["diagnostic_reason"] = "active_pair_row_has_blank_key"
            incomplete_frames.append(incomplete)
        relationship_frames.append(normalised.loc[complete_mask])

    relationships = pd.concat(relationship_frames, ignore_index=True)
    relationships = (
        relationships.sort_values(RELATIONSHIP_KEY_COLUMNS + ["workbook_row_number"], kind="stable")
        .drop_duplicates(RELATIONSHIP_KEY_COLUMNS)
        .reset_index(drop=True)
    )
    incomplete = (
        pd.concat(incomplete_frames, ignore_index=True)
        if incomplete_frames
        else pd.DataFrame(columns=[*relationships.columns, "diagnostic_reason"])
    )
    return relationships, incomplete


def _axis_cardinality(
    frame: pd.DataFrame,
    source_column: str,
    target_column: str,
) -> pd.Series:
    """Classify axis cardinality per row."""
    source_degree = frame.groupby(
        ["mapping_name", "comparison_scope", source_column], dropna=False
    )[target_column].transform("nunique")
    target_degree = frame.groupby(
        ["mapping_name", "comparison_scope", target_column], dropna=False
    )[source_column].transform("nunique")
    result = pd.Series("one_to_one", index=frame.index)
    result[(source_degree > 1) & (target_degree == 1)] = "one_to_many"
    result[(source_degree == 1) & (target_degree > 1)] = "many_to_one"
    result[(source_degree > 1) & (target_degree > 1)] = "many_to_many"
    return result


def derive_axis_mappings(
    relationships: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Derive review-only flow and product axis mappings from current pairs."""
    flow_columns = [
        "mapping_name",
        "comparison_scope",
        "source_system",
        "source_flow",
        "target_system",
        "target_flow",
    ]
    product_columns = [
        "mapping_name",
        "comparison_scope",
        "source_system",
        "source_product",
        "target_system",
        "target_product",
    ]
    flow = relationships[flow_columns].drop_duplicates().reset_index(drop=True)
    product = relationships[product_columns].drop_duplicates().reset_index(drop=True)
    flow["relationship_semantics"] = _axis_cardinality(flow, "source_flow", "target_flow")
    product["relationship_semantics"] = _axis_cardinality(
        product, "source_product", "target_product"
    )
    flow["notes"] = "Derived from active reviewed pair mappings; prototype only."
    product["notes"] = "Derived from active reviewed pair mappings; prototype only."
    return flow, product


def remove_exact_duplicate_mapping_rows(
    frame: pd.DataFrame,
    key_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Consolidate repeated editable mapping keys while retaining the first row.

    Mapping labels are compared after trimming surrounding whitespace. For
    ESTO-targeting sheets, the two mapping columns define identity; multiple
    scope rows are consolidated into one row. ``BOTH`` supersedes either
    single-dataset scope, and an ``ESTO`` plus ``ESTO_EXTENDED`` pair also
    becomes ``BOTH``. Different targets remain distinct, so this does not
    collapse legitimate one-to-many or many-to-one relationships.
    """
    result = frame.copy()
    result.columns = [str(column).strip() for column in result.columns]
    missing_columns = sorted(set(key_columns) - set(result.columns))
    if missing_columns:
        raise ValueError(
            f"Editable mapping table is missing columns: {missing_columns}"
        )

    scope_column = "esto_dataset_scope" if "esto_dataset_scope" in key_columns else None
    mapping_key_columns = [
        column for column in key_columns if column != "esto_dataset_scope"
    ]
    normalised = pd.DataFrame(index=result.index)
    for column in mapping_key_columns:
        values = result[column].map(_clean)
        normalised[column] = values
    populated = normalised.ne("").any(axis=1)
    duplicate = populated & normalised.duplicated(subset=mapping_key_columns, keep="first")
    audit = result.loc[duplicate, key_columns].copy()
    audit.insert(0, "workbook_row_number", audit.index + 2)

    cleaned = result.loc[~duplicate].copy()
    if scope_column:
        for _, indexes in normalised.loc[populated].groupby(
            mapping_key_columns,
            dropna=False,
        ).groups.items():
            scopes = {
                _clean(result.at[index, scope_column]).upper()
                for index in indexes
            }
            consolidated_scope = (
                "BOTH"
                if "BOTH" in scopes or {"ESTO", "ESTO_EXTENDED"} <= scopes
                else next(iter(scopes))
            )
            retained_index = min(indexes)
            cleaned.loc[retained_index, scope_column] = consolidated_scope
    cleaned = cleaned.reset_index(drop=True)
    return cleaned, audit.reset_index(drop=True)


def build_axis_mappings_from_editable_sheets(
    sheet_frames: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build compiler-ready axes from the six user-editable sheet frames.

    Every nonblank row is an accepted relation. Deleting a row therefore
    withdraws that relation from the next compilation.
    """
    required_sheets = set(EDITABLE_AXIS_SHEET_SPECS)
    present_sheets = required_sheets & set(sheet_frames)
    if present_sheets != required_sheets:
        missing = sorted(required_sheets - present_sheets)
        raise ValueError(
            "Editable single-axis contract is incomplete. Missing sheets: "
            f"{missing}"
        )

    axis_frames: dict[str, list[pd.DataFrame]] = {
        "flow": [],
        "product": [],
    }
    for sheet_name, spec in EDITABLE_AXIS_SHEET_SPECS.items():
        source_column = spec["source_column"]
        target_column = spec["target_column"]
        required_columns = {source_column, target_column}
        scope_column = spec.get("scope_column")
        if scope_column:
            required_columns.add(scope_column)

        frame = sheet_frames[sheet_name].copy()
        frame.columns = [str(column).strip() for column in frame.columns]
        missing_columns = sorted(required_columns - set(frame.columns))
        if missing_columns:
            raise ValueError(
                f"{sheet_name} is missing columns: {missing_columns}"
            )
        key_columns = [source_column, target_column]
        if scope_column:
            key_columns.append(scope_column)
        frame, _ = remove_exact_duplicate_mapping_rows(
            frame,
            key_columns,
        )

        source_values = frame[source_column].map(_clean)
        target_values = frame[target_column].map(_clean)
        populated = source_values.ne("") | target_values.ne("")
        if spec["source_system"] == "LEAP" and spec["axis"] == "flow":
            physical_roots = ("demand\\", "transformation\\", "resources\\")
            physical_branch_path = (
                populated
                & source_values.str.casefold().str.startswith(physical_roots)
            )
            if physical_branch_path.any():
                workbook_rows = (frame.index[physical_branch_path] + 2).tolist()
                raise ValueError(
                    f"{sheet_name} uses full physical LEAP branch paths "
                    f"at workbook rows {workbook_rows[:20]}. leap_sector must "
                    "use the parsed balance-flow key without the leading "
                    r"'Demand\', 'Transformation\', or 'Resources\' root."
                )
        incomplete = populated & (source_values.eq("") | target_values.eq(""))
        if incomplete.any():
            workbook_rows = (frame.index[incomplete] + 2).tolist()
            raise ValueError(
                f"{sheet_name} has partially blank axis rows at workbook "
                f"rows {workbook_rows[:20]}"
            )

        frame = frame.loc[populated].copy()
        source_values = source_values.loc[populated]
        target_values = target_values.loc[populated]
        if scope_column:
            raw_scopes = frame[scope_column].map(_clean)
            invalid_scope = ~raw_scopes.str.upper().isin(
                {"ESTO", "ESTO_EXTENDED", "BOTH"}
            )
            if invalid_scope.any():
                workbook_rows = (frame.index[invalid_scope] + 2).tolist()
                raise ValueError(
                    f"{sheet_name} has invalid esto_dataset_scope values at "
                    f"workbook rows {workbook_rows[:20]}"
                )
            scopes = raw_scopes.map(
                lambda value: _normalise_scope(value, spec["target_system"])
            )
        else:
            scopes = pd.Series("NINTH", index=frame.index)

        axis_name = spec["axis"]
        normalised = pd.DataFrame(
            {
                "mapping_name": spec["mapping_name"],
                "comparison_scope": scopes,
                "source_system": spec["source_system"],
                f"source_{axis_name}": source_values,
                "target_system": spec["target_system"],
                f"target_{axis_name}": target_values,
            }
        )
        axis_frames[axis_name].append(normalised)

    results: dict[str, pd.DataFrame] = {}
    for axis_name, frames in axis_frames.items():
        source_column = f"source_{axis_name}"
        target_column = f"target_{axis_name}"
        result = (
            pd.concat(frames, ignore_index=True)
            .drop_duplicates()
            .sort_values(
                [
                    "mapping_name",
                    "comparison_scope",
                    source_column,
                    target_column,
                ],
                kind="stable",
            )
            .reset_index(drop=True)
        )
        result["relationship_semantics"] = _axis_cardinality(
            result,
            source_column,
            target_column,
        )
        result["notes"] = "Accepted in editable single-axis contract."
        results[axis_name] = result
    return results["flow"], results["product"]


def load_or_bootstrap_editable_axis_contract(
    workbook_path: Path,
    bootstrap_relationships: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    """Load the editable axes, deriving them only when no axis sheets exist."""
    workbook_path = Path(workbook_path)
    existing_sheets: set[str] = set()
    if workbook_path.exists():
        with pd.ExcelFile(workbook_path) as workbook:
            existing_sheets = set(workbook.sheet_names)

    required_sheets = set(EDITABLE_AXIS_SHEET_SPECS)
    present_sheets = required_sheets & existing_sheets
    if present_sheets and present_sheets != required_sheets:
        missing = sorted(required_sheets - present_sheets)
        raise ValueError(
            "Editable single-axis contract is incomplete. Missing sheets: "
            f"{missing}"
        )
    if present_sheets == required_sheets:
        sheet_frames = {
            sheet_name: pd.read_excel(
                workbook_path,
                sheet_name=sheet_name,
                dtype=object,
            )
            for sheet_name in EDITABLE_AXIS_SHEET_SPECS
        }
        flow_axis, product_axis = build_axis_mappings_from_editable_sheets(
            sheet_frames
        )
        return flow_axis, product_axis, False

    flow_axis, product_axis = derive_axis_mappings(bootstrap_relationships)
    return flow_axis, product_axis, True


def analyse_axis_components(
    axis_mappings: pd.DataFrame,
    axis_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attach deterministic graph-component cardinality to one axis relation.

    The proposed axis contract allows one-to-one, one-to-many, and many-to-one
    connected components. Small many-to-many components remain visible for
    semantic review because a few are intentional hierarchy bridges. Oversized
    components, and product components spanning multiple numbered target
    families, are blocking because they are characteristic of row shifts or
    accidental global-axis propagation.
    """
    axis_name = _clean(axis_name).casefold()
    if axis_name not in {"flow", "product"}:
        raise ValueError("axis_name must be 'flow' or 'product'.")
    source_column = f"source_{axis_name}"
    target_column = f"target_{axis_name}"
    required = {
        "mapping_name",
        "comparison_scope",
        "source_system",
        "target_system",
        source_column,
        target_column,
    }
    missing = sorted(required - set(axis_mappings.columns))
    if missing:
        raise ValueError(
            f"{axis_name} axis mappings are missing required columns: {missing}"
        )

    group_columns = [
        "mapping_name",
        "comparison_scope",
        "source_system",
        "target_system",
    ]
    annotated_frames: list[pd.DataFrame] = []
    component_records: list[dict[str, Any]] = []

    grouped = axis_mappings.groupby(group_columns, dropna=False, sort=True)
    for group_key, group in grouped:
        adjacency: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
        for source_key, target_key in group[
            [source_column, target_column]
        ].itertuples(index=False, name=None):
            source_node = ("source", _clean(source_key))
            target_node = ("target", _clean(target_key))
            adjacency[source_node].add(target_node)
            adjacency[target_node].add(source_node)

        component_number = 0
        visited: set[tuple[str, str]] = set()
        for start_node in sorted(adjacency):
            if start_node in visited:
                continue
            component_number += 1
            frontier = [start_node]
            visited.add(start_node)
            source_keys: set[str] = set()
            target_keys: set[str] = set()
            while frontier:
                node = frontier.pop()
                if node[0] == "source":
                    source_keys.add(node[1])
                else:
                    target_keys.add(node[1])
                for neighbour in adjacency[node]:
                    if neighbour not in visited:
                        visited.add(neighbour)
                        frontier.append(neighbour)

            if len(source_keys) > 1 and len(target_keys) > 1:
                component_cardinality = "many_to_many"
                contract_status = "axis_component_review_required"
            elif len(source_keys) == 1 and len(target_keys) > 1:
                component_cardinality = "one_to_many"
                contract_status = "axis_component_allowed"
            elif len(source_keys) > 1 and len(target_keys) == 1:
                component_cardinality = "many_to_one"
                contract_status = "axis_component_allowed"
            else:
                component_cardinality = "one_to_one"
                contract_status = "axis_component_allowed"

            node_count = len(source_keys) + len(target_keys)
            target_families = {
                match.group(1)
                for target_key in target_keys
                if (
                    match := re.match(
                        r"^(\d{2})(?:[._]|\s|$)",
                        target_key,
                    )
                )
            }
            is_cross_family_product_component = (
                axis_name == "product" and len(target_families) > 1
            )
            is_oversized_component = (
                node_count > MAX_AXIS_COMPONENT_NODE_COUNT
            )
            blocking_reasons: list[str] = []
            if is_cross_family_product_component:
                blocking_reasons.append("cross_family_product_component")
            if is_oversized_component:
                blocking_reasons.append("oversized_axis_component")
            if blocking_reasons:
                contract_status = "blocking_suspicious_axis_component"

            group_values = dict(zip(group_columns, group_key))
            component_id = (
                f"{axis_name}_{group_values['mapping_name']}_"
                f"{group_values['comparison_scope']}_{component_number:04d}"
            )
            edge_mask = (
                group[source_column].map(_clean).isin(source_keys)
                & group[target_column].map(_clean).isin(target_keys)
            )
            component_edges = group.loc[edge_mask].copy()
            component_edges["axis_name"] = axis_name
            component_edges["axis_component_id"] = component_id
            component_edges["axis_component_cardinality"] = component_cardinality
            component_edges["axis_contract_status"] = contract_status
            annotated_frames.append(component_edges)
            component_records.append(
                {
                    **group_values,
                    "axis_name": axis_name,
                    "axis_component_id": component_id,
                    "source_key_count": len(source_keys),
                    "target_key_count": len(target_keys),
                    "node_count": node_count,
                    "edge_count": len(component_edges),
                    "axis_component_cardinality": component_cardinality,
                    "axis_contract_status": contract_status,
                    "axis_blocking_reason": "|".join(blocking_reasons),
                    "target_code_families": "|".join(
                        sorted(target_families)
                    ),
                    "source_keys": "|".join(sorted(source_keys)),
                    "target_keys": "|".join(sorted(target_keys)),
                }
            )

    annotated = (
        pd.concat(annotated_frames, ignore_index=True)
        if annotated_frames
        else axis_mappings.assign(
            axis_name=axis_name,
            axis_component_id="",
            axis_component_cardinality="",
            axis_contract_status="",
        )
    )
    inventory = pd.DataFrame(component_records)
    return annotated, inventory


def assert_no_blocking_axis_components(
    component_inventory: pd.DataFrame,
) -> None:
    """Stop compilation when an axis component is suspiciously broad."""
    if component_inventory.empty:
        return
    blocking = component_inventory[
        component_inventory["axis_contract_status"]
        .astype(str)
        .str.startswith("blocking_")
    ]
    if blocking.empty:
        return
    examples = blocking[
        [
            "mapping_name",
            "comparison_scope",
            "axis_name",
            "source_key_count",
            "target_key_count",
            "axis_blocking_reason",
            "source_keys",
            "target_keys",
        ]
    ].head(5).to_dict("records")
    raise ValueError(
        "Blocking suspicious within-axis connected components were found. "
        "Correct the editable single-axis workbook before compilation. "
        f"Examples: {examples}"
    )


def load_axis_component_exceptions(workbook_path: Path) -> pd.DataFrame:
    """Load explicit allowed many-to-many component exceptions, if present."""
    workbook_path = Path(workbook_path)
    if not workbook_path.exists():
        return pd.DataFrame(columns=AXIS_COMPONENT_EXCEPTION_COLUMNS)
    with pd.ExcelFile(workbook_path) as workbook:
        if "exceptions" not in workbook.sheet_names:
            return pd.DataFrame(columns=AXIS_COMPONENT_EXCEPTION_COLUMNS)
    exceptions = pd.read_excel(workbook_path, sheet_name="exceptions", dtype=object)
    exceptions.columns = [str(column).strip() for column in exceptions.columns]
    missing = sorted(set(AXIS_COMPONENT_EXCEPTION_COLUMNS) - set(exceptions.columns))
    if missing:
        raise ValueError(f"exceptions is missing columns: {missing}")
    exceptions = exceptions[AXIS_COMPONENT_EXCEPTION_COLUMNS].copy()
    enabled_values = exceptions["enabled"].map(_clean).str.casefold()
    invalid_enabled = ~enabled_values.isin({"true", "false"})
    if invalid_enabled.any():
        rows = (exceptions.index[invalid_enabled] + 2).tolist()
        raise ValueError(
            "exceptions has invalid enabled values at workbook rows "
            f"{rows[:20]}; use TRUE or FALSE."
        )
    exceptions["enabled"] = enabled_values.eq("true")
    for column in AXIS_COMPONENT_EXCEPTION_COLUMNS:
        if column == "enabled":
            continue
        exceptions[column] = exceptions[column].map(_clean)
    populated = exceptions.drop(columns=["enabled", "notes"]).ne("").any(axis=1)
    exceptions = exceptions.loc[populated].reset_index(drop=True)
    invalid_type = ~exceptions["exception_type"].eq(
        "allowed_many_to_many_component"
    )
    if invalid_type.any():
        values = exceptions.loc[invalid_type, "exception_type"].tolist()
        raise ValueError(
            "exceptions has unsupported exception_type values: "
            f"{values[:10]}"
        )
    required = [
        column
        for column in AXIS_COMPONENT_EXCEPTION_COLUMNS
        if column not in {"enabled", "notes"}
    ]
    incomplete = exceptions.loc[exceptions["enabled"], required].eq("").any(axis=1)
    if incomplete.any():
        rows = (exceptions.index[incomplete] + 2).tolist()
        raise ValueError(f"exceptions has incomplete rows at workbook rows {rows[:20]}")
    return exceptions


def apply_axis_component_exceptions(
    component_inventory: pd.DataFrame,
    exceptions: pd.DataFrame,
) -> pd.DataFrame:
    """Mark exact approved many-to-many components without hiding them."""
    result = component_inventory.copy()
    result["exception_type"] = ""
    result["exception_notes"] = ""
    for exception in exceptions.itertuples(index=False):
        if not exception.enabled:
            continue
        match_columns = [
            "mapping_name",
            "comparison_scope",
            "axis_name",
            "source_keys",
            "target_keys",
        ]
        matches = pd.Series(True, index=result.index)
        for column in match_columns:
            matches &= result[column].map(_clean).eq(
                _clean(getattr(exception, column))
            )
        if matches.sum() != 1:
            raise ValueError(
                "Each exception must match exactly one current axis component. "
                f"Exception: {exception}; matches: {int(matches.sum())}."
            )
        result.loc[matches, "axis_contract_status"] = (
            "axis_component_exception_allowed"
        )
        result.loc[matches, "exception_type"] = exception.exception_type
        result.loc[matches, "exception_notes"] = exception.notes
    return result


def annotate_pair_universe_temporal_evidence(
    registry: pd.DataFrame,
    historical_boundary_year: int,
) -> pd.DataFrame:
    """Mark exact registry members and their boundary/projection evidence.

    This deliberately retains structurally present zero-only pairs. Temporal
    evidence is descriptive and can be filtered into named consumer views
    without changing membership of the accepted exact-pair universe.
    """
    result = registry.copy()
    if result.empty:
        return result
    dataset = result["dataset"].fillna("").astype(str).str.strip().str.upper()
    first_year = pd.to_numeric(
        result.get("first_observed_year", pd.Series(pd.NA, index=result.index)),
        errors="coerce",
    )
    last_year = pd.to_numeric(
        result.get("last_observed_year", pd.Series(pd.NA, index=result.index)),
        errors="coerce",
    )
    result["pair_exists_in_dataset"] = True
    result["pair_universe_member"] = True
    result["historical_boundary_year"] = int(historical_boundary_year)
    result["historical_boundary_active"] = (
        dataset.isin({"ESTO", "ESTO_EXTENDED"})
        & last_year.eq(int(historical_boundary_year))
    )
    result["projection_future_active"] = (
        dataset.eq("NINTH")
        & last_year.gt(int(historical_boundary_year))
    )
    result["active_before_or_at_boundary"] = (
        first_year.le(int(historical_boundary_year))
        & last_year.notna()
    )
    result["temporal_evidence_status"] = np.select(
        [
            result["historical_boundary_active"],
            result["projection_future_active"],
            result["pair_status"].eq("zero_only"),
        ],
        [
            "historical_boundary_active",
            "projection_future_active",
            "structural_zero_only",
        ],
        default="nonzero_outside_selected_boundary_window",
    )
    result["pair_universe_authority"] = "generated_exact_source_pair"
    return result


def build_bootstrap_leap_pair_universe(
    current_relationships: pd.DataFrame,
) -> pd.DataFrame:
    """Bootstrap exact LEAP pairs until model-branch parsing is supplied.

    This is intentionally labelled as circular review evidence. It enables the
    compiler prototype without claiming that current pair sheets are the future
    LEAP structural authority.
    """
    leap = current_relationships[
        current_relationships["source_system"].eq("LEAP")
    ].copy()
    if leap.empty:
        return pd.DataFrame(
            columns=[
                "dataset",
                "flow",
                "product",
                "pair_is_subtotal",
                "pair_exists_in_dataset",
                "pair_universe_member",
                "pair_status",
                "pair_universe_authority",
            ]
        )
    universe = (
        leap.groupby(["source_flow", "source_product"], as_index=False)
        .agg(pair_is_subtotal=("source_pair_is_subtotal", "max"))
        .rename(
            columns={
                "source_flow": "flow",
                "source_product": "product",
            }
        )
    )
    universe.insert(0, "dataset", "LEAP")
    universe["pair_exists_in_dataset"] = True
    universe["pair_universe_member"] = True
    universe["pair_status"] = "bootstrap_reviewed_pair"
    universe["historical_boundary_active"] = pd.NA
    universe["projection_future_active"] = pd.NA
    universe["temporal_evidence_status"] = "not_yet_parsed_from_leap_branches"
    universe["pair_universe_authority"] = (
        "bootstrap_from_current_reviewed_pair_contract"
    )
    return universe


def _registry_pair_status_lookup(registry: pd.DataFrame) -> dict[tuple[str, str], str]:
    """Return pair status keyed by exact flow/product labels."""
    if registry.empty:
        return {}
    return {
        (_clean(row.flow), _clean(row.product)): _clean(row.pair_status)
        for row in registry[["flow", "product", "pair_status"]].itertuples(index=False)
    }


def build_registry_scope_lookups(
    esto_registry: pd.DataFrame,
    ninth_registry: pd.DataFrame,
    esto_extended_registry: pd.DataFrame | None = None,
) -> dict[tuple[str, str], dict[tuple[str, str], str]]:
    """Build target-system/scope registry lookups for compilation."""
    esto_lookup = _registry_pair_status_lookup(esto_registry)
    ninth_lookup = _registry_pair_status_lookup(ninth_registry)
    extended_lookup = _registry_pair_status_lookup(
        esto_extended_registry if esto_extended_registry is not None else pd.DataFrame()
    )
    both_lookup: dict[tuple[str, str], str] = {}
    for pair in set(esto_lookup) | set(extended_lookup):
        base_status = esto_lookup.get(pair, "absent")
        extended_status = extended_lookup.get(pair, "absent")
        if base_status == "absent" or extended_status == "absent":
            both_lookup[pair] = "absent"
        elif base_status == "data_valid" and extended_status == "data_valid":
            both_lookup[pair] = "data_valid"
        else:
            both_lookup[pair] = "zero_only"
    return {
        ("ESTO", "ESTO"): esto_lookup,
        ("ESTO", "ESTO_EXTENDED"): extended_lookup,
        ("ESTO", "BOTH"): both_lookup if extended_lookup else esto_lookup,
        ("NINTH", "NINTH"): ninth_lookup,
    }


def compile_axis_relationships(
    current_relationships: pd.DataFrame,
    flow_mappings: pd.DataFrame,
    product_mappings: pd.DataFrame,
    registry_lookups: dict[tuple[str, str], dict[tuple[str, str], str]],
    *,
    source_pair_universes: dict[str, pd.DataFrame] | None = None,
    allowed_target_pair_statuses: tuple[str, ...] = ("data_valid",),
) -> pd.DataFrame:
    """Compile target pairs from axes and exact source/target pair universes."""
    if source_pair_universes is None:
        source_pairs = current_relationships[SOURCE_PAIR_COLUMNS].drop_duplicates()
        source_pairs["source_pair_exists_in_dataset"] = True
        source_pairs["source_pair_universe_authority"] = (
            "current_reviewed_pair_contract"
        )
    else:
        source_frames: list[pd.DataFrame] = []
        context_columns = [
            "mapping_name",
            "comparison_scope",
            "source_system",
            "target_system",
        ]
        contexts = flow_mappings[context_columns].drop_duplicates()
        for context in contexts.itertuples(index=False):
            universe = source_pair_universes.get(
                _clean(context.source_system),
                pd.DataFrame(),
            )
            if universe.empty:
                continue
            source_frame = universe.rename(
                columns={
                    "flow": "source_flow",
                    "product": "source_product",
                    "pair_exists_in_dataset": "source_pair_exists_in_dataset",
                    "pair_universe_authority": "source_pair_universe_authority",
                }
            ).copy()
            source_frame["mapping_name"] = context.mapping_name
            source_frame["comparison_scope"] = context.comparison_scope
            source_frame["source_system"] = context.source_system
            source_frame["target_system"] = context.target_system
            for column, default in [
                ("source_pair_exists_in_dataset", True),
                ("source_pair_universe_authority", "generated_pair_universe"),
            ]:
                if column not in source_frame:
                    source_frame[column] = default
            source_frames.append(
                source_frame[
                    SOURCE_PAIR_COLUMNS
                    + [
                        "source_pair_exists_in_dataset",
                        "source_pair_universe_authority",
                    ]
                ]
            )
        source_pairs = (
            pd.concat(source_frames, ignore_index=True).drop_duplicates()
            if source_frames
            else pd.DataFrame(
                columns=SOURCE_PAIR_COLUMNS
                + [
                    "source_pair_exists_in_dataset",
                    "source_pair_universe_authority",
                ]
            )
        )

    compiled = source_pairs.merge(
        flow_mappings.drop(columns=["relationship_semantics", "notes"], errors="ignore"),
        on=["mapping_name", "comparison_scope", "source_system", "source_flow", "target_system"],
        how="left",
        validate="many_to_many",
    )
    compiled = compiled.merge(
        product_mappings.drop(columns=["relationship_semantics", "notes"], errors="ignore"),
        on=["mapping_name", "comparison_scope", "source_system", "source_product", "target_system"],
        how="left",
        validate="many_to_many",
    )
    compiled = compiled.dropna(subset=["target_flow", "target_product"]).copy()

    statuses: list[str] = []
    for row in compiled.itertuples(index=False):
        lookup = registry_lookups.get((row.target_system, row.comparison_scope), {})
        statuses.append(lookup.get((_clean(row.target_flow), _clean(row.target_product)), "absent"))
    compiled["target_pair_registry_status"] = statuses
    compiled["target_pair_exists_in_dataset"] = compiled[
        "target_pair_registry_status"
    ].ne("absent")
    compiled["registry_allowed"] = compiled[
        "target_pair_registry_status"
    ].isin(set(allowed_target_pair_statuses))
    compiled["compiler_status"] = np.where(
        compiled["registry_allowed"],
        "compiled_from_independent_axes",
        "rejected_by_target_registry",
    )
    return (
        compiled.drop_duplicates(RELATIONSHIP_KEY_COLUMNS)
        .sort_values(RELATIONSHIP_KEY_COLUMNS, kind="stable")
        .reset_index(drop=True)
    )


def build_compiled_mapping_sheet_frames(
    relationships: pd.DataFrame,
    current_relationships: pd.DataFrame,
    registries_by_scope: dict[tuple[str, str], pd.DataFrame],
    use_current_reviewed_subtotal_flags: bool = False,
) -> dict[str, pd.DataFrame]:
    """Return generated pair sheets with the canonical maintained columns.

    Registry subtotal metadata is authoritative by default. The former
    reviewed-flag precedence remains available only through the explicit
    legacy switch.
    """
    if use_current_reviewed_subtotal_flags:
        working = add_target_pair_metadata(
            relationships,
            current_relationships,
            registries_by_scope,
        )
        current_source_subtotals = (
            current_relationships.groupby(SOURCE_PAIR_COLUMNS, as_index=False)
            .agg(source_pair_is_subtotal=("source_pair_is_subtotal", "max"))
        )
        working = working.merge(
            current_source_subtotals,
            on=SOURCE_PAIR_COLUMNS,
            how="left",
        )
    else:
        working = add_registry_target_pair_metadata(
            relationships,
            registries_by_scope,
        )

    registry_subtotals: dict[
        tuple[str, str, str],
        bool,
    ] = {}
    for (system, scope), registry in registries_by_scope.items():
        if registry.empty:
            continue
        for row in registry[
            ["flow", "product", "pair_is_subtotal"]
        ].itertuples(index=False):
            registry_subtotals[
                (_clean(system), _clean(row.flow), _clean(row.product))
            ] = bool(_truthy(row.pair_is_subtotal))

    source_flags: list[bool] = []
    for row in working.itertuples(index=False):
        if use_current_reviewed_subtotal_flags:
            reviewed = getattr(row, "source_pair_is_subtotal", pd.NA)
            if not pd.isna(reviewed):
                source_flags.append(_truthy(reviewed))
                continue
        source_flags.append(
            registry_subtotals.get(
                (
                    _clean(row.source_system),
                    _clean(row.source_flow),
                    _clean(row.source_product),
                ),
                False,
            )
        )
    working["source_pair_is_subtotal"] = source_flags

    outputs: dict[str, pd.DataFrame] = {}
    for mapping_name, spec in MAPPING_SPECS.items():
        subset = working[working["mapping_name"].eq(mapping_name)].copy()
        output = pd.DataFrame(
            {
                spec["source_flow_column"]: subset["source_flow"],
                spec["source_product_column"]: subset["source_product"],
                spec["target_flow_column"]: subset["target_flow"],
                spec["target_product_column"]: subset["target_product"],
                spec["source_subtotal_column"]: subset[
                    "source_pair_is_subtotal"
                ].map(_truthy),
                spec["target_subtotal_column"]: subset[
                    "target_pair_is_subtotal"
                ].map(_truthy),
                "duplicate_to_remove": False,
            }
        )
        if spec["target_system"] == "ESTO":
            output["esto_dataset_scope"] = subset["comparison_scope"].map(_clean)
        outputs[spec["sheet_name"]] = (
            output.drop_duplicates()
            .sort_values(list(output.columns[:4]), kind="stable")
            .reset_index(drop=True)
        )
    return outputs


def compare_compiled_relationships(
    current_relationships: pd.DataFrame,
    compiled_candidates: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compare strict axis compilation with current reviewed relationships."""
    current = current_relationships[RELATIONSHIP_KEY_COLUMNS].drop_duplicates()
    compiled = compiled_candidates.loc[
        compiled_candidates["registry_allowed"], RELATIONSHIP_KEY_COLUMNS
    ].drop_duplicates()
    comparison = current.merge(
        compiled,
        on=RELATIONSHIP_KEY_COLUMNS,
        how="outer",
        indicator=True,
    )
    comparison["relationship_status"] = comparison["_merge"].map(
        {
            "both": "exact_relationship_match",
            "left_only": "current_relationship_not_compiled",
            "right_only": "extra_factorised_relationship",
        }
    )
    comparison = comparison.drop(columns="_merge")

    current_counts = current.groupby(SOURCE_PAIR_COLUMNS, dropna=False).size().rename("current_target_count")
    compiled_counts = compiled.groupby(SOURCE_PAIR_COLUMNS, dropna=False).size().rename("compiled_target_count")
    match_counts = (
        comparison[comparison["relationship_status"].eq("exact_relationship_match")]
        .groupby(SOURCE_PAIR_COLUMNS, dropna=False)
        .size()
        .rename("exact_target_count")
    )
    source_summary = (
        pd.concat([current_counts, compiled_counts, match_counts], axis=1)
        .fillna(0)
        .reset_index()
    )
    for column in ["current_target_count", "compiled_target_count", "exact_target_count"]:
        source_summary[column] = source_summary[column].astype(int)
    source_summary["missing_target_count"] = (
        source_summary["current_target_count"] - source_summary["exact_target_count"]
    )
    source_summary["extra_target_count"] = (
        source_summary["compiled_target_count"] - source_summary["exact_target_count"]
    )
    source_summary["reproduction_status"] = np.select(
        [
            source_summary["missing_target_count"].eq(0)
            & source_summary["extra_target_count"].eq(0),
            source_summary["missing_target_count"].gt(0)
            & source_summary["extra_target_count"].eq(0),
            source_summary["missing_target_count"].eq(0)
            & source_summary["extra_target_count"].gt(0),
        ],
        ["lossless_without_override", "missing_current_targets", "extra_factorised_targets"],
        default="missing_and_extra_targets",
    )

    candidate_status = compiled_candidates[
        RELATIONSHIP_KEY_COLUMNS + ["target_pair_registry_status"]
    ].drop_duplicates(RELATIONSHIP_KEY_COLUMNS)
    comparison = comparison.merge(
        candidate_status,
        on=RELATIONSHIP_KEY_COLUMNS,
        how="left",
    )
    missing = comparison["relationship_status"].eq("current_relationship_not_compiled")
    comparison.loc[missing & comparison["target_pair_registry_status"].isna(), "target_pair_registry_status"] = "absent"

    governance_rows: list[dict[str, Any]] = []
    for row in comparison.itertuples(index=False):
        if row.relationship_status == "current_relationship_not_compiled":
            status = _clean(row.target_pair_registry_status) or "absent"
            reason = (
                "reserved_zero_only_target_pair"
                if status == "zero_only"
                else "reserved_target_pair_absent_from_registry"
            )
            action = "include"
            human_note = (
                "Generated review-only override candidate. Confirm semantics "
                "before acceptance."
            )
            review_status = "unreviewed"
        elif row.relationship_status == "extra_factorised_relationship":
            reason = "provisionally_accepted_cartesian_relationship"
            action = "retain"
            human_note = (
                "Provisionally accepted to continue process development. "
                "Retain in the generated master until a later review removes "
                "or context-qualifies this relationship."
            )
            review_status = "provisionally_accepted"
        else:
            continue
        governance_rows.append(
            {
                **{column: getattr(row, column) for column in RELATIONSHIP_KEY_COLUMNS},
                "override_action": action,
                "reason_code": reason,
                "human_note": human_note,
                "review_status": review_status,
            }
        )
    governance_frame = pd.DataFrame(governance_rows)
    return comparison, source_summary, governance_frame


def apply_generated_overrides(
    compiled_candidates: pd.DataFrame,
    overrides: pd.DataFrame,
) -> pd.DataFrame:
    """Apply explicit include/exclude actions; retain actions are no-ops."""
    compiled = compiled_candidates.loc[
        compiled_candidates["registry_allowed"], RELATIONSHIP_KEY_COLUMNS
    ].drop_duplicates()
    if overrides.empty:
        return compiled.reset_index(drop=True)
    exclusions = overrides[overrides["override_action"].eq("exclude")][RELATIONSHIP_KEY_COLUMNS]
    inclusions = overrides[overrides["override_action"].eq("include")][RELATIONSHIP_KEY_COLUMNS]
    if not exclusions.empty:
        compiled = compiled.merge(
            exclusions.assign(_exclude=True),
            on=RELATIONSHIP_KEY_COLUMNS,
            how="left",
        )
        exclude_mask = compiled["_exclude"].fillna(False).astype(bool)
        compiled = compiled.loc[~exclude_mask].drop(columns="_exclude")
    compiled = pd.concat([compiled, inclusions], ignore_index=True)
    return (
        compiled.drop_duplicates(RELATIONSHIP_KEY_COLUMNS)
        .sort_values(RELATIONSHIP_KEY_COLUMNS, kind="stable")
        .reset_index(drop=True)
    )


def analyse_product_context_dependence(
    current_relationships: pd.DataFrame,
    source_pair_summary: pd.DataFrame,
) -> pd.DataFrame:
    """Measure target-product variation and whether valid-pair filtering explains it."""
    records: list[dict[str, Any]] = []
    summary_lookup = source_pair_summary.set_index(SOURCE_PAIR_COLUMNS)["reproduction_status"]
    group_columns = [
        "mapping_name",
        "comparison_scope",
        "source_system",
        "source_product",
        "target_system",
    ]
    for group_values, group in current_relationships.groupby(group_columns, dropna=False):
        targets_by_flow = (
            group.groupby("source_flow", dropna=False)["target_product"]
            .apply(lambda values: "|".join(sorted(set(values))))
        )
        if targets_by_flow.nunique() <= 1:
            continue
        pair_statuses: list[str] = []
        for source_flow in targets_by_flow.index:
            key = (*group_values[:3], source_flow, group_values[3], group_values[4])
            # Reorder to SOURCE_PAIR_COLUMNS.
            lookup_key = (
                group_values[0],
                group_values[1],
                group_values[2],
                source_flow,
                group_values[3],
                group_values[4],
            )
            pair_statuses.append(_clean(summary_lookup.get(lookup_key, "not_evaluated")))
        explained = all(status == "lossless_without_override" for status in pair_statuses)
        records.append(
            {
                "mapping_name": group_values[0],
                "comparison_scope": group_values[1],
                "source_system": group_values[2],
                "source_product": group_values[3],
                "target_system": group_values[4],
                "source_flow_count": len(targets_by_flow),
                "distinct_target_product_sets": targets_by_flow.nunique(),
                "target_sets_by_source_flow": " || ".join(
                    f"{flow} => {targets}" for flow, targets in targets_by_flow.items()
                ),
                "explained_by_valid_pair_filtering": explained,
                "review_status": (
                    "explained_by_registry"
                    if explained
                    else "unresolved_flow_qualified_product_semantics"
                ),
            }
        )
    return pd.DataFrame(records)


# --- Graph and Common ESTO structure comparison ----------------------------

def _union_find_components(
    relationship_frame: pd.DataFrame,
) -> dict[tuple[str, str, str], str]:
    """Return raw target-pair graph component signatures by scope/system/pair."""
    parent: dict[tuple[str, str, str, str], tuple[str, str, str, str]] = {}

    def find(node: tuple[str, str, str, str]) -> tuple[str, str, str, str]:
        parent.setdefault(node, node)
        if parent[node] != node:
            parent[node] = find(parent[node])
        return parent[node]

    def union(left: tuple[str, str, str, str], right: tuple[str, str, str, str]) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for _, group in relationship_frame.groupby(SOURCE_PAIR_COLUMNS, dropna=False):
        nodes = sorted(
            {
                (
                    _clean(row.comparison_scope),
                    _clean(row.target_system),
                    _clean(row.target_flow),
                    _clean(row.target_product),
                )
                for row in group.itertuples(index=False)
            }
        )
        for node in nodes:
            find(node)
        for node in nodes[1:]:
            union(nodes[0], node)

    groups: dict[tuple[str, str, str, str], list[tuple[str, str, str, str]]] = defaultdict(list)
    for node in parent:
        groups[find(node)].append(node)
    result: dict[tuple[str, str, str], str] = {}
    for nodes in groups.values():
        signature = "|".join(
            f"{scope}:{system}:{flow}::{product}" for scope, system, flow, product in sorted(nodes)
        )
        for scope, system, flow, product in nodes:
            result[(scope, system, f"{flow}::{product}")] = signature
    return result


def compare_raw_target_components(
    current_relationships: pd.DataFrame,
    compiled_relationships: pd.DataFrame,
) -> pd.DataFrame:
    """Compare raw target-pair connected components before Stage-2 rules."""
    current_lookup = _union_find_components(current_relationships)
    compiled_lookup = _union_find_components(compiled_relationships)
    keys = sorted(set(current_lookup) | set(compiled_lookup))
    records = []
    for scope, system, pair in keys:
        current_signature = current_lookup.get((scope, system, pair), "")
        compiled_signature = compiled_lookup.get((scope, system, pair), "")
        records.append(
            {
                "comparison_scope": scope,
                "target_system": system,
                "target_pair": pair,
                "current_component_signature": current_signature,
                "compiled_component_signature": compiled_signature,
                "component_status": (
                    "unchanged"
                    if current_signature == compiled_signature
                    else "changed"
                ),
            }
        )
    return pd.DataFrame(records)


def add_target_pair_metadata(
    relationships: pd.DataFrame,
    current_relationships: pd.DataFrame,
    registries_by_scope: dict[tuple[str, str], pd.DataFrame],
) -> pd.DataFrame:
    """Attach subtotal metadata without changing relationship membership.

    Exact current relationships keep the reviewed workbook flag. New
    factorised candidates use the generated target registry flag.
    """
    result = relationships.copy()
    current_metadata = (
        current_relationships[
            RELATIONSHIP_KEY_COLUMNS + ["target_pair_is_subtotal", "notes"]
        ]
        .drop_duplicates(RELATIONSHIP_KEY_COLUMNS)
        .rename(
            columns={
                "target_pair_is_subtotal": "_current_subtotal",
                "notes": "_current_notes",
            }
        )
    )
    result = result.merge(
        current_metadata,
        on=RELATIONSHIP_KEY_COLUMNS,
        how="left",
        validate="one_to_one",
    )

    registry_subtotal_lookups: dict[
        tuple[str, str],
        dict[tuple[str, str], bool],
    ] = {}
    for scope_key, registry in registries_by_scope.items():
        if registry.empty:
            registry_subtotal_lookups[scope_key] = {}
            continue
        registry_subtotal_lookups[scope_key] = {
            (_clean(row.flow), _clean(row.product)): _truthy(
                row.pair_is_subtotal
            )
            for row in registry[
                ["flow", "product", "pair_is_subtotal"]
            ].drop_duplicates(["flow", "product"]).itertuples(index=False)
        }

    registry_subtotal: list[bool] = []
    for row in result.itertuples(index=False):
        registry_lookup = registry_subtotal_lookups.get(
            (_clean(row.target_system), _clean(row.comparison_scope)),
            {},
        )
        registry_subtotal.append(
            registry_lookup.get(
                (_clean(row.target_flow), _clean(row.target_product)),
                False,
            )
        )
    result["target_pair_is_subtotal"] = (
        result["_current_subtotal"]
        .where(result["_current_subtotal"].notna(), pd.Series(registry_subtotal, index=result.index))
        .map(_truthy)
    )
    result["notes"] = result["_current_notes"].fillna(
        "Compiled from separate flow/product axes; prototype only."
    )
    return result.drop(columns=["_current_subtotal", "_current_notes"])


def add_registry_target_pair_metadata(
    relationships: pd.DataFrame,
    registries_by_scope: dict[tuple[str, str], pd.DataFrame],
) -> pd.DataFrame:
    """Attach target subtotal metadata using generated registries only."""
    result = relationships.copy()
    registry_subtotal_lookups: dict[
        tuple[str, str],
        dict[tuple[str, str], bool],
    ] = {}
    for scope_key, registry in registries_by_scope.items():
        if registry.empty:
            registry_subtotal_lookups[scope_key] = {}
            continue
        registry_subtotal_lookups[scope_key] = {
            (_clean(row.flow), _clean(row.product)): _truthy(
                row.pair_is_subtotal
            )
            for row in registry[
                ["flow", "product", "pair_is_subtotal"]
            ].drop_duplicates(["flow", "product"]).itertuples(index=False)
        }

    result["target_pair_is_subtotal"] = [
        registry_subtotal_lookups.get(
            (_clean(row.target_system), _clean(row.comparison_scope)),
            {},
        ).get(
            (_clean(row.target_flow), _clean(row.target_product)),
            False,
        )
        for row in result.itertuples(index=False)
    ]
    result["notes"] = "Compiled from separate flow/product axes."
    return result


def _mapping_frame_from_contract(
    relationships: pd.DataFrame,
    mapping_name: str,
) -> pd.DataFrame:
    """Convert normalised relationships into one current Stage-1 sheet shape."""
    spec = MAPPING_SPECS[mapping_name]
    subset = relationships[relationships["mapping_name"].eq(mapping_name)].copy()
    frame = pd.DataFrame(
        {
            spec["source_flow_column"]: subset["source_flow"],
            spec["source_product_column"]: subset["source_product"],
            spec["target_flow_column"]: subset["target_flow"],
            spec["target_product_column"]: subset["target_product"],
            spec["target_subtotal_column"]: subset.get(
                "target_pair_is_subtotal",
                pd.Series(False, index=subset.index),
            ),
            "esto_dataset_scope": subset["comparison_scope"],
            "duplicate_to_remove": False,
            "notes": subset.get(
                "notes",
                pd.Series(
                    "Compiled from separate axes; prototype only.",
                    index=subset.index,
                ),
            ),
        }
    )
    return frame.reset_index(drop=True)


def build_stage1_relationships_in_memory(
    relationships: pd.DataFrame,
    workbook_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run the production Stage-1 structural transformations in memory.

    The function intentionally stops before QA/output writers. It uses the
    maintained workbook only for read-only rollup and display metadata.
    """
    from codebase.mapping_tools.build_energy_balance_relationships import (
        RELATIONSHIP_COLUMNS,
        SHEET_CONFIGS,
        _apply_leap_rollup_rules,
        _apply_ninth_rollup_rules,
        _build_flow_prefix_to_label,
        _build_registered_rollup_flow_set,
        _build_rolled_flow_to_components,
        _build_rolled_ninth_sector_to_components,
        build_esto_overrides,
        expand_combined_esto_targets,
        expand_esto_rollup_targets,
        expand_ninth_rollup_targets,
        load_rollup_rules,
    )
    from codebase.mapping_tools.non_expanding_rollups import (
        build_non_expanding_rollup_catalogue,
        non_expanding_rolled_labels,
        split_rollup_rules,
    )

    workbook_path = Path(workbook_path)
    config_by_sheet = {config["sheet_name"]: config for config in SHEET_CONFIGS}
    base_frames: list[pd.DataFrame] = []
    for mapping_name, spec in MAPPING_SPECS.items():
        sheet_frame = _mapping_frame_from_contract(relationships, mapping_name)
        config = config_by_sheet[spec["sheet_name"]]
        normalised = pd.DataFrame(
            {
                "source_flow": sheet_frame[spec["source_flow_column"]].map(_clean),
                "source_product": sheet_frame[spec["source_product_column"]].map(_clean),
                "target_flow": sheet_frame[spec["target_flow_column"]].map(_clean),
                "target_product": sheet_frame[spec["target_product_column"]].map(_clean),
                "esto_pair_is_subtotal": sheet_frame[spec["target_subtotal_column"]].map(_truthy),
                "esto_dataset_scope": sheet_frame["esto_dataset_scope"].map(_clean),
                "notes": sheet_frame["notes"].map(_clean),
            }
        )
        repeated = normalised.loc[
            normalised.index.repeat(len(config["use_cases"]))
        ].reset_index(drop=True)
        repeated["use_case"] = config["use_cases"] * len(normalised)
        repeated["source_system"] = config["source_system"]
        repeated["target_system"] = config["target_system"]
        repeated["source_sector_path"] = repeated["source_flow"]
        repeated["source_fuel"] = repeated["source_product"]
        repeated["include_in_use_case"] = True
        repeated["allocation_method"] = "direct"
        repeated["allocation_source"] = ""
        repeated["allocation_share"] = ""
        repeated["is_rollup_derived"] = False
        repeated["relationship_status"] = "included_in_use_case"
        repeated["relationship_source"] = spec["sheet_name"]
        repeated["source_sheet"] = spec["sheet_name"]
        repeated["source_mapping_file"] = str(workbook_path)
        repeated["source_row_number"] = repeated.index + 2
        repeated["relationship_id"] = [
            f"prototype_rel_{mapping_name}_{index // len(config['use_cases'])}"
            for index in range(len(repeated))
        ]
        repeated["relationship_key"] = (
            repeated["relationship_id"] + "::" + repeated["use_case"]
        )
        repeated["source_sector_code"] = ""
        repeated["source_product_code"] = ""
        repeated["target_sector_code"] = ""
        repeated["target_product_code"] = ""
        repeated["cardinality"] = ""
        repeated["relationship_type"] = ""
        repeated["relationship_level"] = ""
        repeated["exclude_reason"] = ""
        repeated["review_required"] = False
        repeated["review_flags"] = ""
        repeated["remove_row"] = False
        base_frames.append(repeated[RELATIONSHIP_COLUMNS])
    base = pd.concat(base_frames, ignore_index=True)

    leap_rules, esto_rules, ninth_rules = load_rollup_rules(workbook_path)
    leap_ordinary, leap_non_expanding, leap_detached = split_rollup_rules(leap_rules)
    esto_ordinary, esto_non_expanding, esto_detached = split_rollup_rules(esto_rules)
    ninth_ordinary, ninth_non_expanding, ninth_detached = split_rollup_rules(ninth_rules)

    registered_rollups = _build_registered_rollup_flow_set(esto_rules)
    registered_rollups |= set(
        non_expanding_rolled_labels(
            pd.concat([esto_non_expanding, esto_detached], ignore_index=True),
            "rolled_esto_flow",
        )
    )
    base = expand_combined_esto_targets(
        base,
        _build_flow_prefix_to_label(workbook_path),
        registered_rollups,
    )
    base = expand_esto_rollup_targets(
        base,
        _build_rolled_flow_to_components(esto_ordinary),
        registered_rollups,
    )
    base = expand_ninth_rollup_targets(
        base,
        _build_rolled_ninth_sector_to_components(ninth_ordinary),
    )

    frames = [base]
    leap_rollups = _apply_leap_rollup_rules(base, leap_ordinary)
    ninth_rollups = _apply_ninth_rollup_rules(base, ninth_ordinary)
    if not leap_rollups.empty:
        frames.append(leap_rollups)
    if not ninth_rollups.empty:
        frames.append(ninth_rollups)
    stage1 = pd.concat(frames, ignore_index=True)

    non_expanding_catalogue = build_non_expanding_rollup_catalogue(
        {
            "leap_rollup_rules": pd.concat(
                [leap_non_expanding, leap_detached],
                ignore_index=True,
            ),
            "esto_rollup_rules": pd.concat(
                [esto_non_expanding, esto_detached],
                ignore_index=True,
            ),
            "ninth_rollup_rules": pd.concat(
                [ninth_non_expanding, ninth_detached],
                ignore_index=True,
            ),
        }
    )
    return stage1, build_esto_overrides(esto_ordinary), non_expanding_catalogue


def build_common_esto_in_memory(
    stage1_relationships: pd.DataFrame,
    workbook_path: Path,
    overrides: pd.DataFrame,
    non_expanding_catalogue: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    """Run the production Stage-2 component builder for enabled scopes in memory."""
    from codebase.mapping_tools.build_common_esto_structure import (
        COMPARISON_SCOPES,
        COVERAGE_EXCLUSION_COLUMNS,
        DEFAULT_ENABLED_COMPARISON_SCOPES,
        LABEL_OVERRIDE_COLUMNS,
        build_common_esto_for_scope,
        load_code_name_lookups,
        read_table_if_exists,
    )
    from codebase.mapping_tools.build_energy_balance_relationships import (
        build_default_coverage_exclusions,
    )
    from codebase.mapping_tools.non_expanding_rollups import (
        load_non_expanding_flow_labels,
        load_rollup_mode_labels,
    )

    workbook_path = Path(workbook_path)
    try:
        exclusions = pd.read_excel(
            workbook_path,
            sheet_name="coverage_exclusions",
            dtype=object,
        ).fillna("")
    except Exception:
        exclusions = build_default_coverage_exclusions()
    for column in COVERAGE_EXCLUSION_COLUMNS:
        if column not in exclusions:
            exclusions[column] = ""
    exclusions = exclusions[COVERAGE_EXCLUSION_COLUMNS]

    label_overrides = read_table_if_exists(
        workbook_path.parent / "common_esto_label_overrides.csv",
        LABEL_OVERRIDE_COLUMNS,
    )
    flow_names, product_names = load_code_name_lookups(workbook_path)
    non_expanding_labels = load_non_expanding_flow_labels(workbook_path)
    rollup_mode_labels = load_rollup_mode_labels(workbook_path)
    non_expanding_children: dict[str, list[str]] = {}
    for row in non_expanding_catalogue.itertuples(index=False):
        label = _clean(getattr(row, "rolled_flow_label", ""))
        children = [
            child.strip()
            for child in _clean(getattr(row, "child_flow_labels", "")).split(";")
            if child.strip()
        ]
        if label and children:
            existing = non_expanding_children.setdefault(label, [])
            existing.extend(child for child in children if child not in existing)

    common_frames: list[pd.DataFrame] = []
    map_frames: list[pd.DataFrame] = []
    qa_frames: dict[str, list[pd.DataFrame]] = defaultdict(list)
    for scope in DEFAULT_ENABLED_COMPARISON_SCOPES:
        common, mapping, qa = build_common_esto_for_scope(
            comparison_scope=scope,
            scope_config=COMPARISON_SCOPES[scope],
            relationships_df=stage1_relationships,
            exclusions_df=exclusions,
            overrides_df=overrides,
            label_overrides_df=label_overrides,
            flow_code_to_name=flow_names,
            product_code_to_name=product_names,
            non_expanding_labels=non_expanding_labels,
            non_expanding_catalogue_df=non_expanding_catalogue,
            non_expanding_children=non_expanding_children,
            rollup_mode_labels=rollup_mode_labels,
        )
        common_frames.append(common)
        map_frames.append(mapping)
        for name, frame in qa.items():
            qa_frames[name].append(frame)
    common_rows = pd.concat(common_frames, ignore_index=True)
    map_rows = pd.concat(map_frames, ignore_index=True)
    qa_outputs = {
        name: pd.concat(frames, ignore_index=True)
        for name, frames in qa_frames.items()
    }
    return common_rows, map_rows, qa_outputs


def build_common_graph_membership_in_memory(
    stage1_relationships: pd.DataFrame,
    workbook_path: Path,
    overrides: pd.DataFrame,
) -> pd.DataFrame:
    """Build exact production Common ESTO graph membership without rendering.

    Common row labels and axis partitions are presentation over the connected
    components. Skipping those expensive render steps keeps this proof focused
    on the requested membership invariant.
    """
    from codebase.mapping_tools.build_common_esto_structure import (
        COMPARISON_SCOPES,
        COVERAGE_EXCLUSION_COLUMNS,
        DEFAULT_ENABLED_COMPARISON_SCOPES,
        build_connected_components,
        build_manual_override_edges,
        build_required_components,
        isolate_non_expanding_frontiers,
    )
    from codebase.mapping_tools.build_energy_balance_relationships import (
        build_default_coverage_exclusions,
    )
    from codebase.mapping_tools.non_expanding_rollups import (
        load_non_expanding_flow_labels,
    )

    workbook_path = Path(workbook_path)
    try:
        exclusions = pd.read_excel(
            workbook_path,
            sheet_name="coverage_exclusions",
            dtype=object,
        ).fillna("")
    except Exception:
        exclusions = build_default_coverage_exclusions()
    for column in COVERAGE_EXCLUSION_COLUMNS:
        if column not in exclusions:
            exclusions[column] = ""
    exclusions = exclusions[COVERAGE_EXCLUSION_COLUMNS]
    non_expanding_labels = load_non_expanding_flow_labels(workbook_path)

    records: list[dict[str, str]] = []
    for scope in DEFAULT_ENABLED_COMPARISON_SCOPES:
        scope_config = COMPARISON_SCOPES[scope]
        requested_dataset = (
            "ESTO_EXTENDED"
            if scope.startswith("esto_extended_")
            else "ESTO"
        )
        mapping_scope = (
            stage1_relationships.get(
                "esto_dataset_scope",
                pd.Series("BOTH", index=stage1_relationships.index),
            )
            .fillna("BOTH")
            .astype(str)
            .str.upper()
            .str.strip()
        )
        include_flag = (
            stage1_relationships["include_in_use_case"]
            .astype(str)
            .str.casefold()
            .isin(["true", "1", "yes"])
        )
        included = stage1_relationships[
            include_flag
            & stage1_relationships["use_case"].isin(scope_config["use_cases"])
            & stage1_relationships["target_system"].eq("ESTO")
            & mapping_scope.isin(["BOTH", requested_dataset])
        ].copy()
        included["comparison_scope"] = scope

        # The maintained exclusion table is intentionally narrow. Applying its
        # rows as vector masks is equivalent to the production row-wise helper.
        exclusion_mask = pd.Series(False, index=included.index)
        for exclusion in exclusions.itertuples(index=False):
            exclusion_scope = _clean(
                getattr(exclusion, "comparison_scope", "")
            )
            if exclusion_scope and exclusion_scope != scope:
                continue
            row_mask = (
                included["use_case"].map(_clean).eq(
                    _clean(getattr(exclusion, "use_case", ""))
                )
                & included["source_system"].map(_clean).eq(
                    _clean(getattr(exclusion, "source_system", ""))
                )
                & included["target_system"].map(_clean).eq(
                    _clean(getattr(exclusion, "target_system", ""))
                )
                & included["target_flow"].map(_clean).eq(
                    _clean(getattr(exclusion, "target_flow", ""))
                )
            )
            excluded_product = _clean(
                getattr(exclusion, "target_product", "")
            )
            if excluded_product:
                row_mask &= included["target_product"].map(_clean).eq(
                    excluded_product
                )
            exclusion_mask |= row_mask
        included = included.loc[~exclusion_mask].copy()

        required = build_required_components(included)
        eligible = included[
            included["source_system"].isin(
                scope_config["aggregate_source_systems"]
            )
            & included["source_flow"].map(_clean).ne("")
        ].copy()
        subtotal_mask = (
            eligible.get(
                "esto_pair_is_subtotal",
                pd.Series(False, index=eligible.index),
            )
            .fillna(False)
            .map(_truthy)
        )
        rollup_mask = (
            eligible.get(
                "is_rollup_derived",
                pd.Series(False, index=eligible.index),
            )
            .fillna(False)
            .map(_truthy)
        )
        eligible = eligible.loc[~(subtotal_mask | rollup_mask)].copy()
        group_columns = [
            "use_case",
            "source_system",
            "source_flow",
            "source_product",
        ]
        eligible["_allocation_allows_split"] = ~(
            eligible["allocation_method"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.casefold()
            .isin(["", "direct", "none"])
        )
        split_groups = set(
            eligible.loc[
                eligible["_allocation_allows_split"],
                group_columns,
            ].itertuples(index=False, name=None)
        )
        pair_rows = eligible[
            group_columns + ["target_flow", "target_product"]
        ].drop_duplicates()
        source_edges: list[
            tuple[tuple[str, str], tuple[str, str]]
        ] = []
        for group_key, group in pair_rows.groupby(
            group_columns,
            dropna=False,
            sort=False,
        ):
            if group_key in split_groups:
                continue
            pairs = sorted(
                {
                    (_clean(flow), _clean(product))
                    for flow, product in group[
                        ["target_flow", "target_product"]
                    ].itertuples(index=False, name=None)
                }
            )
            if len(pairs) > 1:
                source_edges.extend((pairs[0], pair) for pair in pairs[1:])

        override_edges, _ = build_manual_override_edges(
            overrides,
            comparison_scope=scope,
            required_components_df=required,
        )
        components = build_connected_components(
            required,
            source_edges + override_edges,
        )
        components = isolate_non_expanding_frontiers(
            components,
            non_expanding_labels,
        )
        for component_pairs in components.values():
            cleaned_pairs = sorted(
                {
                    (_clean(flow), _clean(product))
                    for flow, product in component_pairs
                }
            )
            signature = "|".join(
                f"{flow}::{product}" for flow, product in cleaned_pairs
            )
            common_row_id = "graph_" + hashlib.sha1(
                f"{scope}::{signature}".encode("utf-8")
            ).hexdigest()[:16]
            for flow, product in cleaned_pairs:
                records.append(
                    {
                        "comparison_scope": scope,
                        "common_row_id": common_row_id,
                        "component_esto_flow": flow,
                        "component_esto_product": product,
                    }
                )
    return pd.DataFrame(records)


def compare_common_structure_membership(
    current_common_rows: pd.DataFrame,
    compiled_common_rows: pd.DataFrame,
) -> pd.DataFrame:
    """Compare actual Stage-2 component membership independent of display IDs."""
    keys = ["comparison_scope", "component_esto_flow", "component_esto_product"]

    def _membership(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
        membership_records: list[dict[str, str]] = []
        for (scope, common_row_id), group in frame.groupby(
            ["comparison_scope", "common_row_id"],
            dropna=False,
        ):
            membership_records.append(
                {
                    "comparison_scope": scope,
                    "common_row_id": common_row_id,
                    f"{prefix}_component_signature": "|".join(
                        sorted(
                            f"{row.component_esto_flow}::{row.component_esto_product}"
                            for row in group.itertuples(index=False)
                        )
                    ),
                }
            )
        membership = pd.DataFrame(membership_records)
        return frame[keys + ["common_row_id"]].drop_duplicates().merge(
            membership,
            on=["comparison_scope", "common_row_id"],
            how="left",
        ).drop(columns="common_row_id")

    current = _membership(current_common_rows, "current")
    compiled = _membership(compiled_common_rows, "compiled")
    comparison = current.merge(compiled, on=keys, how="outer", indicator=True)
    comparison["membership_status"] = np.select(
        [
            comparison["_merge"].eq("both")
            & comparison["current_component_signature"].eq(
                comparison["compiled_component_signature"]
            ),
            comparison["_merge"].eq("left_only"),
            comparison["_merge"].eq("right_only"),
        ],
        ["unchanged", "missing_from_compiled", "extra_in_compiled"],
        default="component_membership_changed",
    )
    return comparison.drop(columns="_merge").sort_values(keys).reset_index(drop=True)


# --- Explicit source-once delivery contract --------------------------------

def apply_source_once_fixture(
    source_values: pd.DataFrame,
    compiled_membership: pd.DataFrame,
    *,
    tolerance: float = 1e-9,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply explicit relationship semantics to deterministic fixture values.

    Required membership columns are ``source_id``, ``common_row_id`` and
    ``relationship_semantics``. Allocations also require
    ``allocation_share``. A reviewed many-to-many resolution may be identified
    with ``pair_override_id``.
    """
    required_source = {"source_id", "value"}
    required_mapping = {"source_id", "common_row_id", "relationship_semantics"}
    if missing := required_source.difference(source_values.columns):
        raise ValueError(f"Fixture source is missing columns: {sorted(missing)}")
    if missing := required_mapping.difference(compiled_membership.columns):
        raise ValueError(f"Fixture membership is missing columns: {sorted(missing)}")

    source = source_values.copy()
    mapping = compiled_membership.copy()
    source["source_id"] = source["source_id"].map(_clean)
    mapping["source_id"] = mapping["source_id"].map(_clean)
    mapping["common_row_id"] = mapping["common_row_id"].map(_clean)
    mapping["relationship_semantics"] = mapping["relationship_semantics"].map(_clean)
    if "mapping_view" not in mapping:
        mapping["mapping_view"] = "detailed"
    if "pair_override_id" not in mapping:
        mapping["pair_override_id"] = ""

    # Reject unresolved many-to-many membership unless a deliberate aggregate
    # or explicit pair override resolves every affected edge.
    source_degree = mapping.groupby("source_id")["common_row_id"].nunique()
    target_degree = mapping.groupby("common_row_id")["source_id"].nunique()
    risky_sources = set(source_degree[source_degree > 1].index)
    risky_targets = set(target_degree[target_degree > 1].index)
    many_to_many = mapping[
        mapping["source_id"].isin(risky_sources)
        & mapping["common_row_id"].isin(risky_targets)
    ]
    if not many_to_many.empty:
        resolved = (
            many_to_many["relationship_semantics"].eq("deliberate_aggregate_view")
            | many_to_many["pair_override_id"].map(_clean).ne("")
        )
        if not resolved.all():
            raise ValueError("Unresolved many-to-many fixture membership is not allowed.")

    merged = source.merge(mapping, on="source_id", how="left", validate="one_to_many")
    if merged["common_row_id"].isna().any():
        missing_ids = sorted(merged.loc[merged["common_row_id"].isna(), "source_id"].unique())
        raise ValueError(f"Fixture source IDs have no compiled membership: {missing_ids}")

    delivery_records: list[dict[str, Any]] = []
    lineage_records: list[dict[str, Any]] = []
    for (source_id, mapping_view), group in merged.groupby(
        ["source_id", "mapping_view"], dropna=False
    ):
        semantics = set(group["relationship_semantics"])
        if len(semantics) != 1:
            raise ValueError(f"Source {source_id} mixes relationship semantics: {semantics}")
        semantics_value = next(iter(semantics))
        source_value = float(group["value"].iloc[0])
        target_ids = sorted(set(group["common_row_id"]))

        if semantics_value in {"direct", "many_to_one"}:
            if len(target_ids) != 1:
                raise ValueError(f"{semantics_value} source {source_id} has multiple targets.")
            deliveries = {target_ids[0]: source_value}
        elif semantics_value == "recombine_to_common_row":
            if len(target_ids) != 1:
                raise ValueError(
                    f"Recombining source {source_id} does not resolve to one common row."
                )
            deliveries = {target_ids[0]: source_value}
        elif semantics_value == "allocate_across_common_rows":
            if "allocation_share" not in group:
                raise ValueError("Allocated fixture membership requires allocation_share.")
            shares = pd.to_numeric(group["allocation_share"], errors="coerce")
            if shares.isna().any() or abs(float(shares.sum()) - 1.0) > tolerance:
                raise ValueError(f"Allocation shares for {source_id} do not sum to one.")
            deliveries = (
                group.assign(_share=shares)
                .groupby("common_row_id", dropna=False)["_share"]
                .sum()
                .mul(source_value)
                .to_dict()
            )
        elif semantics_value == "deliberate_aggregate_view":
            if len(target_ids) != 1:
                raise ValueError(
                    f"Deliberate aggregate source {source_id} must resolve to one view row."
                )
            deliveries = {target_ids[0]: source_value}
        else:
            raise ValueError(
                f"Source {source_id} has unresolved relationship semantics {semantics_value!r}."
            )

        for common_row_id, delivered_value in deliveries.items():
            delivery_records.append(
                {
                    "source_id": source_id,
                    "mapping_view": mapping_view,
                    "common_row_id": common_row_id,
                    "relationship_semantics": semantics_value,
                    "delivered_value": delivered_value,
                }
            )
        for row in group.itertuples(index=False):
            lineage_records.append(
                {
                    "source_id": source_id,
                    "mapping_view": mapping_view,
                    "common_row_id": row.common_row_id,
                    "relationship_semantics": semantics_value,
                    "source_value": source_value,
                    "component_flow": getattr(row, "component_flow", ""),
                    "component_product": getattr(row, "component_product", ""),
                    "pair_override_id": getattr(row, "pair_override_id", ""),
                }
            )

    delivered = pd.DataFrame(delivery_records)
    final = (
        delivered.groupby(["mapping_view", "common_row_id"], dropna=False, as_index=False)[
            "delivered_value"
        ].sum()
    )
    lineage = pd.DataFrame(lineage_records)
    return final, lineage


def select_alias_candidate(
    candidates: pd.DataFrame,
    *,
    source_id_column: str = "source_id",
    priority_column: str = "alias_priority",
    value_column: str = "value",
    zero_tolerance: float = ZERO_TOLERANCE,
) -> pd.DataFrame:
    """Select one non-zero alias/fallback representation per alias group."""
    required = {"alias_group_id", source_id_column, priority_column, value_column}
    if missing := required.difference(candidates.columns):
        raise ValueError(f"Alias candidates are missing columns: {sorted(missing)}")
    selected: list[pd.DataFrame] = []
    for _, group in candidates.groupby("alias_group_id", dropna=False):
        working = group.copy()
        working["_nonzero"] = pd.to_numeric(
            working[value_column], errors="coerce"
        ).fillna(0.0).abs().gt(zero_tolerance)
        eligible = working[working["_nonzero"]]
        if eligible.empty:
            eligible = working
        minimum_priority = pd.to_numeric(
            eligible[priority_column], errors="coerce"
        ).fillna(np.inf).min()
        chosen = eligible[
            pd.to_numeric(eligible[priority_column], errors="coerce")
            .fillna(np.inf)
            .eq(minimum_priority)
        ].sort_values(source_id_column, kind="stable").head(1)
        selected.append(chosen.drop(columns="_nonzero"))
    return pd.concat(selected, ignore_index=True) if selected else candidates.iloc[0:0].copy()


# --- LEAP authority evidence ------------------------------------------------

def inventory_leap_templates(template_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Inventory per-economy LEAP templates and branch support.

    The template set is structural evidence. This function deliberately does
    not manufacture demand branch/fuel Cartesian products from it.
    """
    template_dir = Path(template_dir)
    inventory_records: list[dict[str, Any]] = []
    branch_support: dict[str, set[str]] = defaultdict(set)
    for path in sorted(template_dir.glob("*.xlsx")):
        try:
            frame = pd.read_excel(
                path,
                sheet_name="Export",
                header=2,
                usecols=lambda column: str(column).strip()
                in {"Branch Path", "Variable", "Scenario", "Region"},
                dtype=object,
            )
            branches = frame.get("Branch Path", pd.Series(dtype=object)).map(_clean)
            branches = branches[branches.ne("")]
            region_values = frame.get("Region", pd.Series(dtype=object)).map(_clean)
            region = next((value for value in region_values if value), path.stem)
            for branch in set(branches):
                branch_support[branch].add(path.name)
            inventory_records.append(
                {
                    "template_file": path.name,
                    "region": region,
                    "row_count": len(frame),
                    "unique_branch_count": branches.nunique(),
                    "source_fingerprint": file_sha256(path),
                    "status": "structural_authority_candidate",
                }
            )
        except Exception as error:
            inventory_records.append(
                {
                    "template_file": path.name,
                    "region": "",
                    "row_count": 0,
                    "unique_branch_count": 0,
                    "source_fingerprint": file_sha256(path),
                    "status": f"read_error:{type(error).__name__}:{error}",
                }
            )
    branch_records = []
    for branch, files in sorted(branch_support.items()):
        explicit_fuel_leaf = any(
            marker in branch
            for marker in [
                "\\Feedstock Fuels\\",
                "\\Auxiliary Fuels\\",
                "\\Output Fuels\\",
            ]
        )
        branch_records.append(
            {
                "branch_path": branch,
                "template_support_count": len(files),
                "template_files": "|".join(sorted(files)),
                "explicit_fuel_leaf_path": explicit_fuel_leaf,
                "pair_registry_role": (
                    "explicit_transformation_fuel_leaf_evidence"
                    if explicit_fuel_leaf
                    else "branch_structure_only"
                ),
            }
        )
    return pd.DataFrame(inventory_records), pd.DataFrame(branch_records)


def latest_leap_balance_exports(export_root: Path) -> list[Path]:
    """Select the latest top-level workbook per economy and scenario."""
    from codebase.mapping_tools.parse_leap_balance_export import (
        scenario_code_from_balance_export_filename,
    )

    selected: list[Path] = []
    export_root = Path(export_root)
    if not export_root.exists():
        return selected
    for economy_dir in sorted(export_root.iterdir()):
        if not economy_dir.is_dir() or economy_dir.name == "00_APEC":
            continue
        candidates = [
            path
            for path in economy_dir.glob("*.xlsx")
            if not path.name.startswith("~$")
        ]
        by_scenario: dict[str, list[Path]] = defaultdict(list)
        for path in candidates:
            scenario = scenario_code_from_balance_export_filename(path) or "UNKNOWN"
            by_scenario[scenario].append(path)
        for paths in by_scenario.values():
            selected.append(max(paths, key=lambda item: (item.stat().st_mtime_ns, item.name)))
    return sorted(selected)


def build_observed_leap_pair_evidence(
    export_root: Path,
    *,
    zero_tolerance: float = ZERO_TOLERANCE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build partial observed LEAP pair evidence from current balance exports."""
    from codebase.mapping_tools.parse_leap_balance_export import parse_leap_balance_xlsx

    file_records: list[dict[str, Any]] = []
    frames: list[pd.DataFrame] = []
    for path in latest_leap_balance_exports(export_root):
        economy = path.parent.name
        parsed = parse_leap_balance_xlsx(path, economy_override=economy)
        frames.append(parsed)
        file_records.append(
            {
                "economy": economy,
                "file": path.name,
                "row_count": len(parsed),
                "source_fingerprint": file_sha256(path),
            }
        )
    if not frames:
        return pd.DataFrame(), pd.DataFrame(file_records)
    observed = pd.concat(frames, ignore_index=True)
    observed["value"] = pd.to_numeric(observed["value"], errors="coerce")
    observed["_nonzero"] = observed["value"].notna() & observed["value"].abs().gt(zero_tolerance)
    records: list[dict[str, Any]] = []
    for (flow, product), group in observed.groupby(["leap_flow", "leap_product"], dropna=False):
        active = group[group["_nonzero"]]
        records.append(
            {
                "dataset": "LEAP_OBSERVED_PARTIAL",
                "flow": _clean(flow),
                "product": _clean(product),
                "first_observed_year": (
                    int(active["year"].min()) if not active.empty else pd.NA
                ),
                "last_observed_year": (
                    int(active["year"].max()) if not active.empty else pd.NA
                ),
                "economy_support_count": active["economy"].nunique(),
                "year_support_count": active["year"].nunique(),
                "nonzero_observation_count": len(active),
                "pair_status": (
                    "observed_data_valid" if not active.empty else "observed_zero_only"
                ),
                "authority_status": "partial_observation_not_global_validity",
            }
        )
    evidence = pd.DataFrame(records)
    if not evidence.empty:
        evidence["first_observed_year"] = evidence["first_observed_year"].astype("Int64")
        evidence["last_observed_year"] = evidence["last_observed_year"].astype("Int64")
    return evidence, pd.DataFrame(file_records)


# --- Narrow review outputs --------------------------------------------------

def build_added_esto_pair_review(
    esto_delta: pd.DataFrame,
    current_relationships: pd.DataFrame,
    compiled_candidates: pd.DataFrame,
    ninth_registry: pd.DataFrame,
) -> pd.DataFrame:
    """Build review rows for newly added ESTO pairs."""
    output_columns = [
        "esto_flow",
        "esto_product",
        "current_pair_status",
        "flow_axis_already_mapped_from_leap",
        "product_axis_already_mapped_from_leap",
        "direct_leap_relationship_count",
        "factorised_leap_candidate_count",
        "missing_leap_coverage",
        "corresponding_ninth_mapping_count",
        "corresponding_ninth_pair_is_data_valid",
        "missing_ninth_counterpart_acknowledged",
        "flow_is_parent",
        "product_is_parent",
        "pair_is_subtotal",
        "review_status",
    ]
    added = esto_delta[esto_delta["delta_status"].eq("added")].copy()
    if added.empty:
        return pd.DataFrame(columns=output_columns)
    leap_esto = current_relationships[current_relationships["mapping_name"].eq("leap_to_esto")]
    ninth_esto = current_relationships[current_relationships["mapping_name"].eq("ninth_to_esto")]
    candidate_leap = compiled_candidates[
        compiled_candidates["mapping_name"].eq("leap_to_esto")
        & compiled_candidates["registry_allowed"]
    ]
    valid_ninth_pairs = {
        (row.flow, row.product)
        for row in ninth_registry[ninth_registry["pair_status"].eq("data_valid")].itertuples()
    }

    records = []
    for row in added.itertuples(index=False):
        target_pair = (_clean(row.flow), _clean(row.product))
        direct_leap = leap_esto[
            leap_esto["target_flow"].eq(target_pair[0])
            & leap_esto["target_product"].eq(target_pair[1])
        ]
        direct_ninth = ninth_esto[
            ninth_esto["target_flow"].eq(target_pair[0])
            & ninth_esto["target_product"].eq(target_pair[1])
        ]
        leap_candidates = candidate_leap[
            candidate_leap["target_flow"].eq(target_pair[0])
            & candidate_leap["target_product"].eq(target_pair[1])
        ]
        ninth_sources_valid = any(
            (candidate.source_flow, candidate.source_product) in valid_ninth_pairs
            for candidate in direct_ninth.itertuples()
        )
        records.append(
            {
                "esto_flow": target_pair[0],
                "esto_product": target_pair[1],
                "current_pair_status": getattr(row, "current_pair_status", ""),
                "flow_axis_already_mapped_from_leap": leap_esto["target_flow"].eq(target_pair[0]).any(),
                "product_axis_already_mapped_from_leap": leap_esto["target_product"].eq(target_pair[1]).any(),
                "direct_leap_relationship_count": len(direct_leap),
                "factorised_leap_candidate_count": len(leap_candidates),
                "missing_leap_coverage": len(direct_leap) == 0,
                "corresponding_ninth_mapping_count": len(direct_ninth),
                "corresponding_ninth_pair_is_data_valid": ninth_sources_valid,
                "missing_ninth_counterpart_acknowledged": len(direct_ninth) == 0,
                "flow_is_parent": getattr(row, "current_flow_is_parent", False),
                "product_is_parent": getattr(row, "current_product_is_parent", False),
                "pair_is_subtotal": getattr(row, "current_pair_is_subtotal", False),
                "review_status": "review_only_do_not_write_mapping",
            }
        )
    return pd.DataFrame(records, columns=output_columns)


def build_power_process_case_evidence(
    review_workbook_path: Path,
    esto_registry: pd.DataFrame,
    esto_extended_registry: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Test the 27 reviewed power-process rollups without modifying them.

    The detailed process proposal currently lives in the separate review
    workbook. Treating that workbook as evidence, rather than as accepted
    configuration, keeps the canonical worktree baseline unchanged.
    """
    review_workbook_path = Path(review_workbook_path)
    if not review_workbook_path.exists():
        return pd.DataFrame(), pd.DataFrame()

    rollups = pd.read_excel(
        review_workbook_path,
        sheet_name="esto_rollup_rules",
        dtype=object,
    ).fillna("")
    include = rollups.get("include", pd.Series(False, index=rollups.index)).map(_truthy)
    group_ids = rollups.get(
        "rollup_group_id",
        pd.Series("", index=rollups.index),
    ).map(_clean)
    detailed = rollups[
        include & group_ids.str.startswith("power_process::")
    ].copy()
    mappings, _ = load_active_mapping_contract(review_workbook_path)
    leap_esto = mappings[mappings["mapping_name"].eq("leap_to_esto")].copy()
    base_status = _registry_pair_status_lookup(esto_registry)
    extended_status = _registry_pair_status_lookup(esto_extended_registry)

    group_records: list[dict[str, Any]] = []
    mapping_records: list[dict[str, Any]] = []
    for group_id, group in detailed.groupby("rollup_group_id", dropna=False):
        rolled_flows = sorted(
            {_clean(value) for value in group["rolled_esto_flow"] if _clean(value)}
        )
        component_flows = sorted(
            {_clean(value) for value in group["input_esto_flow"] if _clean(value)}
        )
        rolled_flow = rolled_flows[0] if len(rolled_flows) == 1 else ""
        direct = leap_esto[leap_esto["target_flow"].eq(rolled_flow)].copy()
        valid_mapping_count = 0
        for row in direct.itertuples(index=False):
            component_statuses_base = [
                base_status.get((flow, _clean(row.target_product)), "absent")
                for flow in component_flows
            ]
            component_statuses_extended = [
                extended_status.get((flow, _clean(row.target_product)), "absent")
                for flow in component_flows
            ]
            both_valid_somewhere = all(
                base == "data_valid" or extended == "data_valid"
                for base, extended in zip(
                    component_statuses_base,
                    component_statuses_extended,
                    strict=True,
                )
            )
            valid_mapping_count += int(both_valid_somewhere)
            mapping_records.append(
                {
                    "rollup_group_id": group_id,
                    "rolled_esto_flow": rolled_flow,
                    "source_flow": row.source_flow,
                    "source_product": row.source_product,
                    "target_product": row.target_product,
                    "component_flows": "|".join(component_flows),
                    "base_component_statuses": "|".join(component_statuses_base),
                    "extended_component_statuses": "|".join(
                        component_statuses_extended
                    ),
                    "both_component_pairs_valid_in_at_least_one_esto_registry": (
                        both_valid_somewhere
                    ),
                    "prototype_semantics": "recombine_to_common_row",
                    "source_delivery_rule": "deliver_once_after_component_recombination",
                }
            )
        group_records.append(
            {
                "rollup_group_id": group_id,
                "rolled_esto_flow": rolled_flow,
                "component_flow_count": len(component_flows),
                "component_flows": "|".join(component_flows),
                "direct_leap_mapping_count": len(direct),
                "valid_direct_leap_mapping_count": valid_mapping_count,
                "all_direct_mappings_have_two_valid_components": (
                    len(direct) > 0 and valid_mapping_count == len(direct)
                ),
                "review_status": (
                    "representable_by_separate_axes"
                    if len(component_flows) == 2
                    and len(direct) > 0
                    and valid_mapping_count == len(direct)
                    else "needs_review"
                ),
            }
        )
    return pd.DataFrame(group_records), pd.DataFrame(mapping_records)


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    """Write a deterministic JSON manifest."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


#%%
