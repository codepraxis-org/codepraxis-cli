"""Replay the local harness across a corpus of real packs.

The harness mirrors the production runner. Mirrors drift, and drift is silent —
a pack that stops loading, or a starter that quietly starts passing, looks like
a normal result. This suite is the net: every pack in the corpus must load, its
solution must pass, and its starter must not.

The corpus is private (see conftest). These tests skip when it is unavailable,
so they are safe to run in a public CI.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from praxis.domain.results import Fixture
from praxis.execution.local.executor import LocalExecutor
from praxis.packio.discovery import find_packs
from praxis.packio.loader import load_pack


def _pack_dirs(corpus_root: Path) -> List[Path]:
    found = find_packs(corpus_root)
    if not found:
        pytest.skip(f"No packs discovered under {corpus_root}")
    return found


@pytest.fixture(scope="session")
def pack_dirs(corpus_root: Path) -> List[Path]:
    return _pack_dirs(corpus_root)


def test_every_pack_loads(pack_dirs: List[Path]) -> None:
    """Loading must never raise: a pack that cannot load cannot be validated."""
    failures = []
    for pack_dir in pack_dirs:
        try:
            load_pack(pack_dir)
        except Exception as exc:  # noqa: BLE001 - collect all, report together
            failures.append(f"{pack_dir.name}: {exc}")
    assert not failures, "packs failed to load:\n  " + "\n  ".join(failures)


def test_solution_passes_and_starter_fails(pack_dirs: List[Path]) -> None:
    """The core invariant every publishable pack must satisfy.

    Run as one test over the whole corpus rather than parametrised per pack:
    the failure message should show every drifting pack at once, since a
    contract change typically breaks many.
    """
    executor = LocalExecutor()
    failures = []

    for pack_dir in pack_dirs:
        pack = load_pack(pack_dir)
        if not pack.has_solution:
            continue
        if not executor.supports(pack):
            continue

        result = executor.execute(pack, [Fixture.SOLUTION, Fixture.STARTER])

        solution = result.run_for(Fixture.SOLUTION)
        starter = result.run_for(Fixture.STARTER)

        if solution is None or not solution.all_passed:
            passed = solution.passed_count if solution else 0
            total = len(solution.cases) if solution else 0
            failures.append(f"{pack.name}: solution passed only {passed}/{total}")

        if starter is not None and starter.all_passed:
            failures.append(f"{pack.name}: starter passes every case — tests do not discriminate")

        for diagnostic in result.errors:
            failures.append(f"{pack.name}: {diagnostic}")

    assert not failures, "conformance failures:\n  " + "\n  ".join(failures)
