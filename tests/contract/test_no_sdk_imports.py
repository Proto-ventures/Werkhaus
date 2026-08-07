"""The rule that makes dashboard-first real.

The dashboard never sees an SDK type, concept, or vocabulary word. If an
``openhands`` import ever appears under ``werkhaus/contract`` or ``werkhaus/api``,
the stub and the real engine have stopped being swappable and nobody will notice
until the swap fails.

All SDK imports belong under ``werkhaus/engines/openhands/``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GUARDED = ["werkhaus/contract", "werkhaus/api", "werkhaus/brain", "werkhaus/share"]


def _python_files(rel: str) -> list[Path]:
    return sorted((REPO / rel).rglob("*.py"))


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            # level > 0 is a relative import; it cannot reach openhands.
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("package", GUARDED)
def test_guarded_packages_do_not_import_the_sdk(package: str) -> None:
    offenders = [
        path.relative_to(REPO)
        for path in _python_files(package)
        if "openhands" in _imported_roots(path)
    ]
    assert not offenders, (
        f"{package} must not import openhands.*; move it under "
        f"werkhaus/engines/openhands/. Offenders: {offenders}"
    )


def test_guard_actually_scans_files() -> None:
    """A guard that silently scans nothing passes forever."""
    assert _python_files("werkhaus/contract"), "no files scanned — guard is inert"


def test_guard_detects_a_violation(tmp_path: Path) -> None:
    """Prove the detector works, so a green run means something."""
    bad = tmp_path / "bad.py"
    bad.write_text("from openhands.sdk import LLM\n")
    assert "openhands" in _imported_roots(bad)
