"""``codepraxis validate`` — run a pack's tests.

The command orchestrates and nothing else: it resolves packs, asks an executor
to run them, hands results to a reporter, and turns them into an exit code.
Which executor (local or remote) is chosen in ``cli.py``, so this code is
identical for both tiers and testable without a subprocess or a network.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ..domain.results import Fixture
from ..errors import PackError
from ..execution.executor import Executor
from ..packio.discovery import find_packs, resolve_pack_dir
from ..packio.loader import load_pack
from ..reporting.reporter import Reporter

EXIT_OK = 0
EXIT_FAILED = 1


def run(
    root: Path,
    selector: str | None,
    executor: Executor,
    reporter: Reporter,
    fixtures: Sequence[Fixture] | None = None,
) -> int:
    """Validate one pack, or every pack under ``root`` when ``selector`` is None."""
    pack_dirs = [resolve_pack_dir(root, selector)] if selector else find_packs(root)

    if not pack_dirs:
        raise PackError(
            f"No challenge packs found under {root}. "
            f"A pack is a directory containing metadata.json and backend.conf."
        )

    exit_code = EXIT_OK
    for pack_dir in pack_dirs:
        pack = load_pack(pack_dir)
        chosen = list(fixtures) if fixtures else _default_fixtures(pack)
        result = executor.execute(pack, chosen)
        reporter.report(result)
        if not result.ok:
            exit_code = EXIT_FAILED
    return exit_code


def _default_fixtures(pack) -> list[Fixture]:
    """Run both fixtures when a solution exists.

    The starter run is what proves the tests discriminate, so it is never
    opt-in; the solution run is skipped only when there is no reference
    solution yet.
    """
    if pack.has_solution:
        return [Fixture.SOLUTION, Fixture.STARTER]
    return [Fixture.STARTER]
