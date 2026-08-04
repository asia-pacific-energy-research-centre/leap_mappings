"""The synthetic-reference-row rules and loader are copied, so guard the copies.

`leap_mappings` is the canonical home: these rules describe which ESTO and 9th
rows the *mapping* expects to exist, which is this repository's subject matter.

`leap_initialisation` keeps a copy rather than importing this one, and that is
forced rather than chosen. Both repositories name their top-level package
``codebase``, so the portable release splits them across two executables; the
balance-review path runs in one and the mapping chain in the other, and neither
can import the other's modules. A shared runtime import is therefore impossible
and duplication is the only option left.

Duplication that nothing checks is duplication that drifts. These tests fail the
moment the copies diverge, which is the whole protection. If a change is needed,
make it in this repository and copy it across in the same commit.
"""

from pathlib import Path

import pytest


MAPPINGS_ROOT = Path(__file__).resolve().parents[1]
INIT_ROOT = MAPPINGS_ROOT.parent / "leap_initialisation"

CANONICAL_RULES = MAPPINGS_ROOT / "config" / "synthetic_reference_rows.csv"
COPIED_RULES = INIT_ROOT / "config" / "runtime_tables" / "synthetic_reference_rows.csv"

LOADER_RELATIVE = Path("codebase/utilities/leap_results_dashboard_v2/reference_loader.py")
CANONICAL_LOADER = MAPPINGS_ROOT / LOADER_RELATIVE
COPIED_LOADER = INIT_ROOT / LOADER_RELATIVE


def _normalised(path: Path) -> bytes:
    """Return the file's bytes with line endings normalised.

    The two checkouts differ in line endings for reasons that have nothing to do
    with content, so comparing raw bytes would fail permanently and teach people
    to ignore this test.
    """
    return path.read_bytes().replace(b"\r\n", b"\n")


requires_sibling = pytest.mark.skipif(
    not INIT_ROOT.is_dir(),
    reason="leap_initialisation checkout is not beside this one",
)


def test_the_canonical_rules_file_exists() -> None:
    """This repository is the canonical home for the rules.

    The consumer that matters is the ESTO read path. `ninth_to_esto_mapping_
    coverage.DEFAULT_SYNTHETIC_RULES_PATH` also names this file, though that
    module cannot currently be imported at all (see the test below).
    """
    assert CANONICAL_RULES.is_file(), f"{CANONICAL_RULES} is missing"


def test_the_dead_coverage_module_still_names_the_canonical_path() -> None:
    """`ninth_to_esto_mapping_coverage` is unreachable, and this records it.

    It imports ``codebase.scrapbook.utilities``, which does not exist, and
    nothing else references it — so its default rules path pointing at a missing
    file was never a live bug, just unreachable code. The constant is asserted
    textually rather than by import, because importing the module raises.

    If that module is ever revived or deleted, this test is the reminder that
    its rules path has to move with it.
    """
    source = (
        MAPPINGS_ROOT / "codebase" / "utilities" / "ninth_to_esto_mapping_coverage.py"
    ).read_text(encoding="utf-8")
    assert 'DEFAULT_SYNTHETIC_RULES_PATH = REPO_ROOT / "config" / "synthetic_reference_rows.csv"' in source


@requires_sibling
def test_the_rules_file_matches_the_leap_initialisation_copy() -> None:
    assert COPIED_RULES.is_file(), f"{COPIED_RULES} is missing"
    assert _normalised(CANONICAL_RULES) == _normalised(COPIED_RULES), (
        "The synthetic-reference-row rules have diverged between repositories.\n"
        f"  canonical: {CANONICAL_RULES}\n"
        f"  copy     : {COPIED_RULES}\n"
        "The two tools would then disagree about which rows exist, and the "
        "balance review and the dashboard would show different structures for "
        "the same economy. Copy the canonical file across."
    )


@requires_sibling
def test_the_loader_matches_the_leap_initialisation_copy() -> None:
    assert COPIED_LOADER.is_file(), f"{COPIED_LOADER} is missing"
    assert _normalised(CANONICAL_LOADER) == _normalised(COPIED_LOADER), (
        "reference_loader.py has diverged between repositories.\n"
        f"  canonical: {CANONICAL_LOADER}\n"
        f"  copy     : {COPIED_LOADER}\n"
        "It holds append_synthetic_reference_rows, so a divergence means the two "
        "tools create different synthetic rows from the same rules. Copy the "
        "canonical file across."
    )


def test_every_created_row_can_be_attributed_to_its_rule() -> None:
    """Injected rows must stay tagged.

    A synthetic row is a zero that ESTO never published. Without a tag it is
    indistinguishable from a real zero, and "is this value real?" becomes
    unanswerable in every downstream consumer.
    """
    source = CANONICAL_LOADER.read_text(encoding="utf-8")
    for marker in ("_synthetic_esto_row", "_synthetic_ninth_row", "_synthetic_rule_name"):
        assert marker in source, f"{marker} tagging was removed from the loader"
