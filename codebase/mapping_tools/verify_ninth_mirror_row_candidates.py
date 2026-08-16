#%%
"""
Offline verification for proposing exact source-issue review candidates.

Background: the anchor validator (source_parent_anchor_validation.py) flags
rows where NINTH's own reported total for a (sector, fuel) combination
doesn't match what its mapped Common ESTO frontier finds -- reason
"parent_child_source_inconsistency". Some of these are genuine NINTH
self-inconsistencies (the same real value reported at two different depths
of NINTH's own hierarchy, disagreeing with itself); others are missing
Common ESTO frontier coverage, or a different structural gap entirely. Four
prior sessions tried to teach the validator to tell these apart
automatically and failed every time (see
docs/prompts/anchor_validator_fixes_findings_20260723.md and the
mirror-row-gap memory). This script is deliberately NOT automatic detection
embedded in the validator -- it is an offline, human-reviewed check: a human
reads its confirmed/not-confirmed split before anything is written to the
exception workbook, so its false positives get caught before they reach a
shared file. A raw-source confirmation produced here is still evidence for a
user to review; it does not prove that the mapping is correct or automatically
confirm an anchor exception.

Two independent single-axis checks, run against raw NINTH data only
(data/merged_file_energy_ALL_20251106.csv -- never the mapped/converted
data, so a confirmation can never be an artifact of this repo's own mapping
code):
  - product-axis candidates (parent_code = a fuel, other_axis_value = a
    sector path): does the node's own subfuel breakdown, or its sector
    children one level deeper, sum to something different than its own
    declared total? See verify_product_axis_candidates().
  - flow-axis candidates (parent_code = a sector, possibly "/"-joined;
    other_axis_value = one or more "fuel/subfuel" paths joined by " + " for
    a shared-frontier connected-component group): does a real, nonzero
    sector child one level deeper sum to something different? See
    verify_flow_axis_candidates().

Both checks are conservative by construction: only genuinely NONZERO
children count as evidence. NINTH's raw file is full of explicit 0.0
placeholder rows at every level (routine tabular completeness, not real
breakdown data) -- the first version of this script (2026-07-24) treated a
lone 0.0 row as contradicting evidence and wrongly "confirmed" all 956
candidates it was run against; this was caught by hand-verifying a sample
against the raw file before trusting the output. Anything this script marks
NOT_CONFIRMED needs manual review, not a stronger heuristic bolted on here --
see "What this rules out" in the findings doc above before extending this.

IMPORTANT before running this and trusting its output: the anchor
validator's own failure population must be stable for the result to mean
anything. Check ``frontier_row_count`` on the candidates first -- if the
vast majority are 0 (registered Common ESTO frontier is entirely absent,
not just numerically different), the dominant failure mode is a coverage
gap, not a mirror-row self-inconsistency, and this script's confirmations
will legitimately come back near-zero (this happened on 2026-07-27, when a
concurrent session's in-progress work on Common ESTO structure-building
changed the failure population's character -- see
docs/prompts/mirror_row_gap_exception_curation_handoff_20260727.md).

Usage:
    python codebase/mapping_tools/verify_ninth_mirror_row_candidates.py \\
        --out-dir results/mirror_row_gap_verification

Writes verify_product_confirmed.csv / verify_product_not_confirmed.csv /
verify_product_sanity_mismatches.csv and verify_flow_confirmed.csv /
verify_flow_not_confirmed.csv to --out-dir. Review the confirmed CSVs before
writing them into config/mapping_issue_exception_sets.xlsx's
source_mismatch_allowed sheet. Operational rows require:
enabled, review_status, exception_id, issue_class, source_system,
validation_axis, parent_code, other_axis_value, economy, scenario, year,
parent_value, and notes. The validator matches that exact source context and
annotates the failure without changing its status or reason.
"""

#%%
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.mapping_tools.typed_output import read_manifested_parquet

NINTH_PATH = Path("data/merged_file_energy_ALL_20251106.csv")
ANCHOR_PATH = Path("results/tree_structure/source_parent_anchor_validation.parquet")
SECTOR_COLS = ["sectors", "sub1sectors", "sub2sectors", "sub3sectors", "sub4sectors"]
TOLERANCE = 0.01
PRODUCT_AXIS_FAMILIES = ["15_solid_biomass", "16_others", "08_gas", "09_06_gas_processing_plants"]


def normalize_economy_ninth(economy_anchor: str) -> str:
    """Anchor validator economy codes have no underscore ("01AUS"); the raw
    NINTH file uses one ("01_AUS")."""
    if len(economy_anchor) >= 3 and economy_anchor[:2].isdigit():
        return f"{economy_anchor[:2]}_{economy_anchor[2:]}"
    return economy_anchor


#%%
# Product-axis: parent_code = fuel, other_axis_value = sector path.

def _verify_product_node(ninth_df, economy, scenario, year, sector_path, fuel_code):
    segments = sector_path.split("/") if sector_path else []
    year_col = str(int(year))

    base = (
        (ninth_df["economy"] == economy)
        & (ninth_df["scenarios"] == scenario)
        & (ninth_df["fuels"] == fuel_code)
    )
    node_mask = base.copy()
    for i, col in enumerate(SECTOR_COLS):
        node_mask &= (ninth_df[col] == segments[i]) if i < len(segments) else (ninth_df[col] == "x")
    node_rows = ninth_df[node_mask]

    declared_rows = node_rows[node_rows["subfuels"] == "x"]
    if declared_rows.empty:
        return {"status": "no_declared_row"}
    declared_value = pd.to_numeric(declared_rows[year_col], errors="coerce").iloc[0]

    fuel_children_all = node_rows[node_rows["subfuels"] != "x"]
    fuel_children_vals = pd.to_numeric(fuel_children_all[year_col], errors="coerce")
    fuel_children_nonzero = fuel_children_all[fuel_children_vals.abs() > TOLERANCE]
    fuel_children_sum = (
        pd.to_numeric(fuel_children_nonzero[year_col], errors="coerce").sum()
        if not fuel_children_nonzero.empty else None
    )
    fuel_mismatch = (
        abs(declared_value - fuel_children_sum) > TOLERANCE * max(abs(declared_value), 1)
        if fuel_children_sum is not None else False
    )

    next_idx = len(segments)
    sector_children_sum = None
    sector_mismatch = False
    if next_idx < len(SECTOR_COLS):
        sec_mask = base.copy() & (ninth_df["subfuels"] == "x")
        for i, col in enumerate(SECTOR_COLS):
            if i < len(segments):
                sec_mask &= ninth_df[col] == segments[i]
            elif i == next_idx:
                sec_mask &= ninth_df[col] != "x"
            else:
                sec_mask &= ninth_df[col] == "x"
        sector_children_all = ninth_df[sec_mask]
        sector_children_vals = pd.to_numeric(sector_children_all[year_col], errors="coerce")
        sector_children_nonzero = sector_children_all[sector_children_vals.abs() > TOLERANCE]
        if not sector_children_nonzero.empty:
            sector_children_sum = pd.to_numeric(sector_children_nonzero[year_col], errors="coerce").sum()
            sector_mismatch = abs(declared_value - sector_children_sum) > TOLERANCE * max(abs(declared_value), 1)

    return {
        "status": "ok",
        "declared_value": declared_value,
        "fuel_children_sum": fuel_children_sum,
        "sector_children_sum": sector_children_sum,
        "fuel_mismatch": fuel_mismatch,
        "sector_mismatch": sector_mismatch,
        "confirmed": bool(fuel_mismatch) or bool(sector_mismatch),
    }


def verify_product_axis_candidates(ninth_df, anchor_df, families=PRODUCT_AXIS_FAMILIES):
    failed = anchor_df[
        (anchor_df["status"] == "failed")
        & (anchor_df["source_system"] == "NINTH")
        & (anchor_df["reason"] == "parent_child_source_inconsistency")
        & (anchor_df["parent_code"].isin(families))
        & (anchor_df["validation_axis"] == "product")
    ].copy()

    confirmed_rows, not_confirmed_rows, sanity_mismatches = [], [], []
    for _, row in failed.iterrows():
        economy = normalize_economy_ninth(row["economy"])
        result = _verify_product_node(
            ninth_df, economy, row["scenario"], row["year"], row["other_axis_value"], row["parent_code"]
        )
        if result.get("status") != "ok":
            not_confirmed_rows.append({**row.to_dict(), "verify_status": result.get("status")})
            continue
        anchor_pv = float(row["parent_value"])
        if abs(result["declared_value"] - anchor_pv) > 0.02 * max(abs(anchor_pv), 1):
            sanity_mismatches.append({**row.to_dict(), "raw_declared_value": result["declared_value"]})
            continue
        record = {
            **row.to_dict(),
            "raw_declared_value": result["declared_value"],
            "raw_fuel_children_sum": result["fuel_children_sum"],
            "raw_sector_children_sum": result["sector_children_sum"],
            "fuel_mismatch": result["fuel_mismatch"],
            "sector_mismatch": result["sector_mismatch"],
        }
        if result["confirmed"]:
            confirmed_rows.append(record)
        else:
            not_confirmed_rows.append({**record, "verify_status": "no_single_axis_mismatch_reproduced"})

    return pd.DataFrame(confirmed_rows), pd.DataFrame(not_confirmed_rows), pd.DataFrame(sanity_mismatches)


#%%
# Flow-axis: parent_code = sector (possibly "/"-joined), other_axis_value =
# one or more "fuel/subfuel" paths joined by " + ".

def _resolve_ancestor_path(ninth_df, code, cache):
    leaf_code = code.split("/")[-1] if "/" in code else code
    if leaf_code in cache:
        return cache[leaf_code]
    result = (None, None)
    for i, col in enumerate(SECTOR_COLS):
        match = ninth_df.loc[ninth_df[col] == leaf_code, SECTOR_COLS[: i + 1]]
        if not match.empty:
            result = (match.iloc[0].tolist(), i)
            break
    cache[leaf_code] = result
    return result


def _parse_product_group(other_axis_value: str):
    members = []
    for part in other_axis_value.split(" + "):
        part = part.strip()
        if "/" in part:
            fuel_code, subfuel_code = part.split("/", 1)
        else:
            fuel_code, subfuel_code = part, None
        members.append((fuel_code.strip(), subfuel_code.strip() if subfuel_code else None))
    return members


def _node_value_for_group(ninth_df, economy, scenario, year, sector_path_cols, product_members):
    year_col = str(int(year))
    total, any_row = 0.0, False
    base = (ninth_df["economy"] == economy) & (ninth_df["scenarios"] == scenario)
    for i, col in enumerate(SECTOR_COLS):
        base &= (ninth_df[col] == sector_path_cols[i]) if i < len(sector_path_cols) else (ninth_df[col] == "x")
    for fuel_code, subfuel_code in product_members:
        mask = base & (ninth_df["fuels"] == fuel_code) & (ninth_df["subfuels"] == (subfuel_code or "x"))
        rows = ninth_df[mask]
        if not rows.empty:
            any_row = True
            total += pd.to_numeric(rows[year_col], errors="coerce").sum()
    return total if any_row else None


def verify_flow_axis_candidates(ninth_df, anchor_df):
    failed = anchor_df[
        (anchor_df["status"] == "failed")
        & (anchor_df["source_system"] == "NINTH")
        & (anchor_df["reason"] == "parent_child_source_inconsistency")
        & (anchor_df["validation_axis"] == "flow")
    ].copy()

    cache: dict = {}
    confirmed_rows, not_confirmed_rows = [], []
    for _, row in failed.iterrows():
        economy = normalize_economy_ninth(row["economy"])
        scenario, year, parent_code = row["scenario"], row["year"], row["parent_code"]

        ancestor_path, depth = _resolve_ancestor_path(ninth_df, parent_code, cache)
        if ancestor_path is None:
            not_confirmed_rows.append({**row.to_dict(), "verify_status": "parent_code_not_found_in_raw_ninth"})
            continue
        try:
            product_members = _parse_product_group(row["other_axis_value"])
        except Exception:
            not_confirmed_rows.append({**row.to_dict(), "verify_status": "unparseable_product_group"})
            continue

        declared_value = _node_value_for_group(ninth_df, economy, scenario, year, ancestor_path, product_members)
        if declared_value is None:
            not_confirmed_rows.append({**row.to_dict(), "verify_status": "no_declared_row"})
            continue

        anchor_pv = float(row["parent_value"])
        if abs(declared_value - anchor_pv) > 0.02 * max(abs(anchor_pv), 1) and abs(anchor_pv) > TOLERANCE:
            not_confirmed_rows.append({**row.to_dict(), "verify_status": "sanity_mismatch", "raw_declared_value": declared_value})
            continue

        next_idx = depth + 1
        sector_children_sum, sector_mismatch = None, False
        if next_idx < len(SECTOR_COLS):
            year_col = str(int(year))
            base = (ninth_df["economy"] == economy) & (ninth_df["scenarios"] == scenario)
            for i, col in enumerate(SECTOR_COLS):
                if i < len(ancestor_path):
                    base &= ninth_df[col] == ancestor_path[i]
                elif i == next_idx:
                    base &= ninth_df[col] != "x"
                else:
                    base &= ninth_df[col] == "x"
            total, any_nonzero = 0.0, False
            for fuel_code, subfuel_code in product_members:
                mask = base & (ninth_df["fuels"] == fuel_code) & (ninth_df["subfuels"] == (subfuel_code or "x"))
                rows = ninth_df[mask]
                if rows.empty:
                    continue
                vals = pd.to_numeric(rows[year_col], errors="coerce")
                nonzero = rows[vals.abs() > TOLERANCE]
                if not nonzero.empty:
                    any_nonzero = True
                    total += pd.to_numeric(nonzero[year_col], errors="coerce").sum()
            if any_nonzero:
                sector_children_sum = total
                sector_mismatch = abs(declared_value - sector_children_sum) > TOLERANCE * max(abs(declared_value), 1)

        record = {
            **row.to_dict(),
            "raw_declared_value": declared_value,
            "raw_sector_children_sum": sector_children_sum,
        }
        if sector_mismatch:
            confirmed_rows.append(record)
        else:
            not_confirmed_rows.append({**record, "verify_status": "no_single_axis_mismatch_reproduced"})

    return pd.DataFrame(confirmed_rows), pd.DataFrame(not_confirmed_rows)


#%%
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("results/mirror_row_gap_verification"))
    parser.add_argument("--ninth-path", type=Path, default=NINTH_PATH)
    parser.add_argument("--anchor-path", type=Path, default=ANCHOR_PATH)
    args = parser.parse_args()

    print("Loading data...")
    ninth_df = pd.read_csv(args.ninth_path, dtype=object)
    anchor_df = read_manifested_parquet(args.anchor_path).astype(object)

    all_candidates = anchor_df[
        (anchor_df["status"] == "failed")
        & (anchor_df["source_system"] == "NINTH")
        & (anchor_df["reason"] == "parent_child_source_inconsistency")
    ]
    zero_frontier_share = (
        pd.to_numeric(all_candidates["frontier_row_count"], errors="coerce") == 0
    ).mean() if not all_candidates.empty else 0.0
    print(f"Candidates with zero frontier rows: {zero_frontier_share:.0%} of {len(all_candidates):,}")
    if zero_frontier_share > 0.5:
        print(
            "WARNING: majority of candidates have zero Common ESTO frontier coverage -- "
            "the dominant failure mode looks like a coverage gap, not a mirror-row "
            "self-inconsistency. Confirmations below will likely be sparse and may not "
            "be representative. See the module docstring before trusting this run."
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)

    product_confirmed, product_not_confirmed, product_sanity = verify_product_axis_candidates(ninth_df, anchor_df)
    print(f"\nProduct-axis confirmed: {len(product_confirmed)}")
    print(f"Product-axis not confirmed: {len(product_not_confirmed)}")
    print(f"Product-axis sanity mismatches: {len(product_sanity)}")
    product_confirmed.to_csv(args.out_dir / "verify_product_confirmed.csv", index=False)
    product_not_confirmed.to_csv(args.out_dir / "verify_product_not_confirmed.csv", index=False)
    product_sanity.to_csv(args.out_dir / "verify_product_sanity_mismatches.csv", index=False)

    flow_confirmed, flow_not_confirmed = verify_flow_axis_candidates(ninth_df, anchor_df)
    print(f"\nFlow-axis confirmed: {len(flow_confirmed)}")
    print(f"Flow-axis not confirmed: {len(flow_not_confirmed)}")
    flow_confirmed.to_csv(args.out_dir / "verify_flow_confirmed.csv", index=False)
    flow_not_confirmed.to_csv(args.out_dir / "verify_flow_not_confirmed.csv", index=False)

    print(f"\nWrote results to {args.out_dir}")


if __name__ == "__main__":
    main()
