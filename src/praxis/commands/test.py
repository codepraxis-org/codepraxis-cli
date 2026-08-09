"""``praxis test`` — run a pack locally.

The command orchestrates and nothing else: it resolves a pack, asks an executor
to run it, hands the result to a reporter, and turns it into an exit code. The
executor and reporter arrive as arguments, so this is testable without touching
a subprocess or a terminal.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence

from ..domain.results import Fixture
from ..execution.executor import Executor
from ..packio.discovery import find_packs, resolve_pack_dir
from ..packio.loader import load_pack
from ..reporting.reporter import Reporter

EXIT_OK = 0
EXIT_FAILED = 1


def run(
    root: Path,
    selector: Optional[str],
    executor: Executor,
    reporter: Reporter,
    fixtures: Optional[Sequence[Fixture]] = None,
) -> int:
    """Run one pack, or every pack under ``root`` when ``selector`` is None."""
    pack_dirs: List[Path]
    if selector:
        pack_dirs = [resolve_pack_dir(root, selector)]
    else:
        pack_dirs = find_packs(root)

    if not pack_dirs:
        raise _no_packs(root)

    exit_code = EXIT_OK
    for pack_dir in pack_dirs:
        pack = load_pack(pack_dir)
        chosen = list(fixtures) if fixtures else _default_fixtures(pack)
        result = executor.execute(pack, chosen)
        reporter.report(result)
        if not result.ok:
            exit_code = EXIT_FAILED
    return exit_code


def _default_fixtures(pack) -> List[Fixture]:
    """Run both fixtures when a solution exists.

    The starter run is what proves the tests discriminate, so it is never opt-in;
    the solution run is skipped only when the pack has no reference solution yet.
    """
    if pack.has_solution:
        return [Fixture.SOLUTION, Fixture.STARTER]
    return [Fixture.STARTER]


def _no_packs(root: Path):
    from ..errors import PackError

    return PackError(
        f"No challenge packs found under {root}. "
        f"A pack is a directory containing metadata.json and backend.conf."
    )
