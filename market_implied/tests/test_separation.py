"""The package must stay independent of :mod:`dnb_p_set`.

The requirement is explicit: this logic stands entirely apart from the DNB
P-set machinery.  These tests fail if anyone ever wires the two together.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = sorted(PACKAGE_ROOT.rglob("*.py"))


def test_there_are_source_files_to_check():
    assert len(SOURCE_FILES) > 5


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_no_module_imports_dnb_p_set(path: Path):
    text = path.read_text(encoding="utf-8")
    # Ignore prose in docstrings; look for real import statements only.
    offenders = re.findall(r"^\s*(?:import|from)\s+dnb_p_set\b", text, flags=re.MULTILINE)
    assert not offenders, f"{path.name} imports dnb_p_set"


def test_importing_the_package_does_not_pull_in_dnb_p_set():
    for name in [n for n in sys.modules if n.startswith(("market_implied", "dnb_p_set"))]:
        del sys.modules[name]
    import market_implied  # noqa: F401

    assert not any(name.startswith("dnb_p_set") for name in sys.modules)


def test_only_numpy_and_pandas_are_required():
    """Keep the dependency surface small enough to lift out of this repo."""
    third_party = set()
    for path in SOURCE_FILES:
        for match in re.findall(
            r"^\s*(?:from|import)\s+([a-zA-Z_][\w]*)", path.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        ):
            third_party.add(match)
    allowed_stdlib = {
        "__future__", "argparse", "dataclasses", "json", "pathlib", "typing",
        "sys", "re", "abc", "collections", "math", "itertools", "functools",
    }
    external = third_party - allowed_stdlib - {"market_implied", "pytest"}
    assert external <= {"numpy", "pandas"}, f"unexpected dependency: {sorted(external)}"
