#%%
"""Build a human-review file for subtotal mismatches and blank subtotal cells.

The canonical mapping workbook is read only. For each mapping row, the script
learns the usual subtotal status of every category from nonblank subtotal cells.
A category is "usually subtotal" when True is at least as common as False, so
ties deliberately favour subtotal. The two categories in a key pair are joined
with OR, then the source and target pair proposals are joined with OR. This
single dominant proposal resolves each reviewed row to matching subtotal flags.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

#%%
# --- Stable paths and sheet definitions ---

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKBOOK_PATH = REPO_ROOT / "config" / "outlook_mappings_master.xlsx"
OUTPUT_PATH = REPO_ROOT / "results" / "maintenance" / "subtotal_mismatch_suggested_improvements.csv"

SHEET_CONFIGS = {
    "leap_combined_ninth": {
        "source_keys": ("leap_sector_name_full_path", "raw_leap_fuel_name"),
        "target_keys": ("ninth_sector", "ninth_fuel"),
        "source_subtotal": "leap_is_subtotal",
        "target_subtotal": "ninth_pair_is_subtotal",
        "source_system": "leap",
        "target_system": "ninth",
    },
    "leap_combined_esto": {
        "source_keys": ("leap_sector_name_full_path", "raw_leap_fuel_name"),
        "target_keys": ("esto_flow", "esto_product"),
        "source_subtotal": "leap_is_subtotal",
        "target_subtotal": "esto_pair_is_subtotal",
        "source_system": "leap",
        "target_system": "esto",
    },
    "ninth_pairs_to_esto_pairs": {
        "source_keys": ("ninth_sector", "ninth_fuel"),
        "target_keys": ("esto_flow", "esto_product"),
        "source_subtotal": "ninth_pair_is_subtotal",
        "target_subtotal": "esto_pair_is_subtotal",
        "source_system": "ninth",
        "target_system": "esto",
    },
}


#%%
# --- Helpers ---

def _normalise_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).split())


def _normalise_bool(value: object) -> bool | None:
    if pd.isna(value) or str(value).strip() == "":
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"Unexpected subtotal value: {value!r}")


def _load_mapping_sheets(workbook_path: Path) -> dict[str, pd.DataFrame]:
    sheets = {}
    for sheet_name in SHEET_CONFIGS:
        frame = pd.read_excel(workbook_path, sheet_name=sheet_name, dtype=object)
        frame.insert(0, "workbook_row", frame.index + 2)
        sheets[sheet_name] = frame
    return sheets


def _build_category_evidence(
    sheets: dict[str, pd.DataFrame],
) -> dict[tuple[str, int, str], dict[str, int | bool]]:
    """Count True/False evidence for each category on each system axis."""
    counts: dict[tuple[str, int, str], dict[str, int]] = {}
    for sheet_name, frame in sheets.items():
        config = SHEET_CONFIGS[sheet_name]
        for side in ("source", "target"):
            system = config[f"{side}_system"]
            subtotal_col = config[f"{side}_subtotal"]
            for axis_index, key_col in enumerate(config[f"{side}_keys"], start=1):
                for key_value, subtotal_value in zip(frame[key_col], frame[subtotal_col]):
                    category = _normalise_text(key_value)
                    parsed = _normalise_bool(subtotal_value)
                    if not category or parsed is None:
                        continue
                    bucket = counts.setdefault((system, axis_index, category), {"true": 0, "false": 0})
                    bucket["true" if parsed else "false"] += 1

    evidence: dict[tuple[str, int, str], dict[str, int | bool]] = {}
    for key, bucket in counts.items():
        true_count = bucket["true"]
        false_count = bucket["false"]
        evidence[key] = {
            "true_count": true_count,
            "false_count": false_count,
            "usual_is_subtotal": true_count >= false_count,
        }
    return evidence


def _category_proposal(
    evidence: dict[tuple[str, int, str], dict[str, int | bool]],
    system: str,
    axis_index: int,
    category: object,
) -> tuple[bool | None, int, int]:
    key = (system, axis_index, _normalise_text(category))
    item = evidence.get(key)
    if item is None:
        return None, 0, 0
    return bool(item["usual_is_subtotal"]), int(item["true_count"]), int(item["false_count"])


def _or_known(values: list[bool | None]) -> bool | None:
    known = [value for value in values if value is not None]
    return any(known) if known else None


def build_review_rows(workbook_path: Path = WORKBOOK_PATH) -> pd.DataFrame:
    sheets = _load_mapping_sheets(workbook_path)
    evidence = _build_category_evidence(sheets)
    output_rows: list[dict[str, object]] = []

    for sheet_name, frame in sheets.items():
        config = SHEET_CONFIGS[sheet_name]
        source_col = config["source_subtotal"]
        target_col = config["target_subtotal"]

        for _, row in frame.iterrows():
            current_source = _normalise_bool(row[source_col])
            current_target = _normalise_bool(row[target_col])
            has_blank = current_source is None or current_target is None
            has_mismatch = (
                current_source is not None
                and current_target is not None
                and current_source != current_target
            )
            if not has_blank and not has_mismatch:
                continue

            proposals: dict[str, bool | None] = {}
            detail: dict[str, object] = {}
            for side in ("source", "target"):
                system = str(config[f"{side}_system"])
                axis_values = []
                for axis_index, key_col in enumerate(config[f"{side}_keys"], start=1):
                    proposal, true_count, false_count = _category_proposal(
                        evidence, system, axis_index, row[key_col]
                    )
                    axis_values.append(proposal)
                    detail[f"{side}_axis_{axis_index}_usual_is_subtotal"] = proposal
                    detail[f"{side}_axis_{axis_index}_true_count"] = true_count
                    detail[f"{side}_axis_{axis_index}_false_count"] = false_count
                proposals[side] = _or_known(axis_values)

            dominant_proposal = _or_known([proposals["source"], proposals["target"]])
            issue_type = "blank_and_mismatch" if has_blank and has_mismatch else "blank" if has_blank else "mismatch"
            output = {
                "INSERT": "",
                "sheet_name": sheet_name,
                "workbook_row": int(row["workbook_row"]),
                "issue_type": issue_type,
            }
            for key_col in (*config["source_keys"], *config["target_keys"]):
                output[key_col] = row[key_col]
            output.update({
                f"current_{source_col}": current_source,
                f"current_{target_col}": current_target,
                f"suggested_{source_col}": dominant_proposal,
                f"suggested_{target_col}": dominant_proposal,
                "source_pair_usual_is_subtotal": proposals["source"],
                "target_pair_usual_is_subtotal": proposals["target"],
                "suggestion_rule": "majority_per_category_tie_true_then_or_within_and_across_pairs",
            })
            output.update(detail)
            output_rows.append(output)

    return pd.DataFrame(output_rows)


def run(
    workbook_path: Path = WORKBOOK_PATH,
    output_path: Path = OUTPUT_PATH,
) -> pd.DataFrame:
    review = build_review_rows(workbook_path=workbook_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(output_path, index=False)
    print(f"Written: {output_path} ({len(review):,} review rows)")
    if not review.empty:
        print(review.groupby(["sheet_name", "issue_type"]).size().to_string())
    return review


#%%
# --- Notebook run block ---

CREATE_SUBTOTAL_MISMATCH_REVIEW = True

if CREATE_SUBTOTAL_MISMATCH_REVIEW:
    REVIEW_ROWS = run()

#%%
