#%%
"""Build or inspect the verified ESTO Extended base-plus-delta artifact."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.mapping_tools.esto_extended_delta import (  # noqa: E402
    load_esto_extended_delta_contract,
    write_esto_extended_delta_contract,
)


RELATIONSHIP_DIR = REPO_ROOT / "results" / "mapping_relationships"
ESTO_BASE_PATH = RELATIONSHIP_DIR / "esto_results_exact_rows.csv.gz"
ESTO_EXTENDED_PATH = RELATIONSHIP_DIR / "esto_extended_results_exact_rows.csv.gz"
DELTA_PATH = RELATIONSHIP_DIR / "esto_extended_results_exact_rows.delta.csv.gz"
MANIFEST_PATH = RELATIONSHIP_DIR / "esto_extended_results_exact_rows.delta.json"
COMMON_ESTO_DIR = REPO_ROOT / "results" / "common_esto"
EQUIVALENCE_DIR = REPO_ROOT / "outputs" / "esto_extended_delta_stage3_equivalence"
BASELINE_ZIP_PATH = EQUIVALENCE_DIR / "full_file_common_esto_contract_baseline.zip"
EQUIVALENCE_SUMMARY_PATH = EQUIVALENCE_DIR / "equivalence_summary.json"


def build_delta_contract() -> dict[str, object]:
    """Build, exactly verify, and atomically publish the delta contract."""
    manifest = write_esto_extended_delta_contract(
        esto_base_path=ESTO_BASE_PATH,
        esto_extended_path=ESTO_EXTENDED_PATH,
        delta_path=DELTA_PATH,
        manifest_path=MANIFEST_PATH,
    )
    print(json.dumps(manifest, indent=2))
    return manifest


def verify_delta_contract() -> dict[str, object]:
    """Validate hashes/counts and reconstruct the exact Extended rows in memory."""
    reconstructed, manifest = load_esto_extended_delta_contract(
        esto_base_path=ESTO_BASE_PATH,
        delta_path=DELTA_PATH,
        manifest_path=MANIFEST_PATH,
    )
    print(f"Verified reconstructed rows: {len(reconstructed):,}")
    print(json.dumps(manifest, indent=2))
    return manifest


def _stream_sha256(file_obj) -> str:
    """Hash one binary stream without loading the artifact into memory."""
    digest = hashlib.sha256()
    for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _partition_csv_rows(
    text_stream,
    output_dir: Path,
    prefix: str,
    key_columns: list[str],
    partition_count: int,
) -> tuple[list[Path], list[str], int]:
    """Partition CSV rows by stable key hash for bounded exact comparison."""
    reader = csv.reader(text_stream)
    header = next(reader)
    key_indexes = [header.index(column) for column in key_columns]
    paths = [
        output_dir / f"{prefix}_{partition_number:03d}.csv"
        for partition_number in range(partition_count)
    ]
    files = [
        path.open("w", encoding="utf-8", newline="")
        for path in paths
    ]
    writers = [csv.writer(file_obj) for file_obj in files]
    row_count = 0
    try:
        for row in reader:
            key = "\x1f".join(row[index] for index in key_indexes)
            partition_number = int.from_bytes(
                hashlib.blake2b(
                    key.encode("utf-8"),
                    digest_size=8,
                ).digest(),
                byteorder="big",
            ) % partition_count
            writers[partition_number].writerow(row)
            row_count += 1
    finally:
        for file_obj in files:
            file_obj.close()
    return paths, header, row_count


def _load_unique_keyed_rows(
    path: Path,
    key_indexes: list[int],
    value_index: int,
) -> dict[tuple[str, ...], tuple[str, ...]]:
    """Load a partition using exact CSV fields and parsed float64 value identity."""
    keyed_rows: dict[tuple[str, ...], tuple[str, ...]] = {}
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        for row in csv.reader(file_obj):
            normalized_row = list(row)
            normalized_row[value_index] = float(row[value_index]).hex()
            row_tuple = tuple(normalized_row)
            key = tuple(row_tuple[index] for index in key_indexes)
            if key in keyed_rows:
                raise AssertionError(f"Duplicate fact key in {path.name}: {key}")
            keyed_rows[key] = row_tuple
    return keyed_rows


def _strict_partitioned_fact_equivalence(
    baseline_zip: zipfile.ZipFile,
    current_fact_path: Path,
    key_columns: list[str],
    partition_count: int = 64,
) -> dict[str, object]:
    """Require exact key/value rows while allowing source row-order changes."""
    with tempfile.TemporaryDirectory(
        prefix="esto_extended_fact_equivalence_"
    ) as temporary_name:
        temporary_dir = Path(temporary_name)
        with baseline_zip.open(
            "common_esto_comparison_fact.csv.gz"
        ) as baseline_compressed:
            with gzip.GzipFile(fileobj=baseline_compressed) as baseline_gzip:
                with io.TextIOWrapper(
                    baseline_gzip,
                    encoding="utf-8",
                    newline="",
                ) as baseline_text:
                    baseline_paths, baseline_header, baseline_rows = (
                        _partition_csv_rows(
                            baseline_text,
                            temporary_dir,
                            "baseline",
                            key_columns,
                            partition_count,
                        )
                    )
        with gzip.open(
            current_fact_path,
            "rt",
            encoding="utf-8",
            newline="",
        ) as current_text:
            current_paths, current_header, current_rows = _partition_csv_rows(
                current_text,
                temporary_dir,
                "delta_stage3",
                key_columns,
                partition_count,
            )
        if baseline_header != current_header:
            raise AssertionError("Baseline and delta-backed fact headers differ.")
        if baseline_rows != current_rows:
            raise AssertionError(
                "Baseline and delta-backed fact row counts differ: "
                f"{baseline_rows:,} != {current_rows:,}"
            )
        key_indexes = [
            baseline_header.index(column)
            for column in key_columns
        ]
        value_index = baseline_header.index("value")
        for baseline_path, current_path in zip(
            baseline_paths,
            current_paths,
            strict=True,
        ):
            baseline_keyed = _load_unique_keyed_rows(
                baseline_path,
                key_indexes,
                value_index,
            )
            current_keyed = _load_unique_keyed_rows(
                current_path,
                key_indexes,
                value_index,
            )
            if baseline_keyed != current_keyed:
                differing_keys = (
                    set(baseline_keyed) ^ set(current_keyed)
                )
                if not differing_keys:
                    differing_keys = {
                        key for key in baseline_keyed
                        if baseline_keyed[key] != current_keyed[key]
                    }
                example = next(iter(differing_keys))
                raise AssertionError(
                    "Baseline and delta-backed fact rows differ at key "
                    f"{example}. Baseline={baseline_keyed.get(example)!r}; "
                    f"delta_stage3={current_keyed.get(example)!r}."
                )
    return {
        "equal": True,
        "row_count": baseline_rows,
        "partition_count": partition_count,
        "comparison": "exact_key_fields_and_parsed_float64_values",
    }


def compare_stage3_contract_to_baseline() -> dict[str, object]:
    """Compare delta-backed Stage 3 outputs with the archived full-file contract."""
    current_fact_path = COMMON_ESTO_DIR / "common_esto_comparison_fact.csv.gz"
    current_metadata_path = COMMON_ESTO_DIR / "common_esto_row_metadata.csv"
    current_manifest_path = COMMON_ESTO_DIR / "common_esto_output_contract.json"
    with gzip.open(current_fact_path, "rb") as current_fact:
        current_fact_content_sha256 = _stream_sha256(current_fact)
    with zipfile.ZipFile(BASELINE_ZIP_PATH) as baseline_zip:
        with baseline_zip.open("common_esto_comparison_fact.csv.gz") as compressed:
            with gzip.GzipFile(fileobj=compressed) as decompressed:
                baseline_fact_content_sha256 = _stream_sha256(decompressed)
        with baseline_zip.open("common_esto_row_metadata.csv") as metadata:
            baseline_metadata_sha256 = _stream_sha256(metadata)
        with baseline_zip.open("common_esto_output_contract.json") as manifest_file:
            baseline_manifest = json.load(manifest_file)
        strict_fact_equivalence = None
        if baseline_fact_content_sha256 != current_fact_content_sha256:
            strict_fact_equivalence = _strict_partitioned_fact_equivalence(
                baseline_zip=baseline_zip,
                current_fact_path=current_fact_path,
                key_columns=baseline_manifest["fact"]["key_columns"],
            )

    with current_metadata_path.open("rb") as current_metadata:
        current_metadata_sha256 = _stream_sha256(current_metadata)
    current_manifest = json.loads(current_manifest_path.read_text(encoding="utf-8"))

    manifest_fields = {
        "contract_version": (
            baseline_manifest.get("contract_version"),
            current_manifest.get("contract_version"),
        ),
        "fact_columns": (
            baseline_manifest["fact"].get("columns"),
            current_manifest["fact"].get("columns"),
        ),
        "fact_key_columns": (
            baseline_manifest["fact"].get("key_columns"),
            current_manifest["fact"].get("key_columns"),
        ),
        "fact_row_count": (
            baseline_manifest["fact"].get("row_count"),
            current_manifest["fact"].get("row_count"),
        ),
        "metadata_columns": (
            baseline_manifest["metadata"].get("columns"),
            current_manifest["metadata"].get("columns"),
        ),
        "metadata_key_columns": (
            baseline_manifest["metadata"].get("key_columns"),
            current_manifest["metadata"].get("key_columns"),
        ),
        "metadata_row_count": (
            baseline_manifest["metadata"].get("row_count"),
            current_manifest["metadata"].get("row_count"),
        ),
    }
    mismatched_manifest_fields = [
        field for field, values in manifest_fields.items()
        if values[0] != values[1]
    ]
    result = {
        "baseline_zip_path": str(BASELINE_ZIP_PATH),
        "fact_decompressed_sha256": {
            "baseline": baseline_fact_content_sha256,
            "delta_stage3": current_fact_content_sha256,
            "equal": (
                baseline_fact_content_sha256
                == current_fact_content_sha256
            ),
        },
        "metadata_sha256": {
            "baseline": baseline_metadata_sha256,
            "delta_stage3": current_metadata_sha256,
            "equal": baseline_metadata_sha256 == current_metadata_sha256,
        },
        "strict_fact_equivalence": strict_fact_equivalence,
        "manifest_semantic_fields_equal": not mismatched_manifest_fields,
        "mismatched_manifest_fields": mismatched_manifest_fields,
    }
    if (
        (
            not result["fact_decompressed_sha256"]["equal"]
            and not (
                strict_fact_equivalence
                and strict_fact_equivalence["equal"]
            )
        )
        or not result["metadata_sha256"]["equal"]
        or mismatched_manifest_fields
    ):
        raise AssertionError(json.dumps(result, indent=2))
    EQUIVALENCE_DIR.mkdir(parents=True, exist_ok=True)
    EQUIVALENCE_SUMMARY_PATH.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))
    return result


# User-tuned notebook flags.
BUILD_DELTA_CONTRACT = False
VERIFY_DELTA_CONTRACT = False
COMPARE_STAGE3_CONTRACT_TO_BASELINE = False


#%%
if __name__ == "__main__":
    if BUILD_DELTA_CONTRACT:
        build_delta_contract()
    if VERIFY_DELTA_CONTRACT:
        verify_delta_contract()
    if COMPARE_STAGE3_CONTRACT_TO_BASELINE:
        compare_stage3_contract_to_baseline()
    if (
        not BUILD_DELTA_CONTRACT
        and not VERIFY_DELTA_CONTRACT
        and not COMPARE_STAGE3_CONTRACT_TO_BASELINE
    ):
        print("Enable one workflow flag.")


#%%
