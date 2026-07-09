#%%
"""
Regenerate Common ESTO comparison outputs from cached pipeline intermediates.

This fast path skips Stage 0 maintenance, Stage 1 relationship building,
Stage 2 structure building, tree validation, source-parent anchor validation,
and mapping-candidate diagnostics.
"""

#%%
from datetime import datetime, timezone
from pathlib import Path
import sys

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codebase.mapping_tools.apply_common_esto_structure import (  # noqa: E402
    NINTH_PROJECTION_START_YEAR,
    run_common_esto_comparison_fast_path,
)

#%%
# Stable paths.
RELATIONSHIP_DIR = REPO_ROOT / "results" / "mapping_relationships"
COMMON_ESTO_DIR = REPO_ROOT / "results" / "common_esto"

SOURCE_PATHS = {
    "LEAP": RELATIONSHIP_DIR / "leap_results_converted_to_esto.csv",
    "NINTH": RELATIONSHIP_DIR / "ninth_results_converted_to_esto.csv",
    "ESTO": RELATIONSHIP_DIR / "esto_results_exact_rows.csv",
}
COMMON_ROWS_PATH = COMMON_ESTO_DIR / "common_esto_rows.csv"
OUTPUT_DIR = COMMON_ESTO_DIR

#%%
# Frequently changed run settings.
RUN_REGEN_COMMON_ESTO_FAST_PATH = False
DEFAULT_ECONOMY = "20_USA"
ACTIVE_COMPONENT_ABS_TOLERANCE = 0.0
ESTO_BASE_YEAR = None

#%%
if __name__ == "__main__":
    try:
        if RUN_REGEN_COMMON_ESTO_FAST_PATH:
            RUN_TIMESTAMP = datetime.now(timezone.utc)
            RUN_ID = RUN_TIMESTAMP.strftime("common_esto_fast_path_%Y%m%dT%H%M%S%fZ")
            run_common_esto_comparison_fast_path(
                source_paths=SOURCE_PATHS,
                common_rows_path=COMMON_ROWS_PATH,
                output_dir=OUTPUT_DIR,
                default_economy=DEFAULT_ECONOMY,
                active_component_abs_tolerance=ACTIVE_COMPONENT_ABS_TOLERANCE,
                ninth_projection_start_year=NINTH_PROJECTION_START_YEAR,
                esto_base_year=ESTO_BASE_YEAR,
                run_id=RUN_ID,
                run_timestamp_utc=RUN_TIMESTAMP.isoformat(),
            )
        else:
            print("Set RUN_REGEN_COMMON_ESTO_FAST_PATH = True after checking cached inputs.")
    except Exception as exc:
        print("Common ESTO fast-path regen failed.")
        print(f"Error: {exc}")
        raise

#%%
