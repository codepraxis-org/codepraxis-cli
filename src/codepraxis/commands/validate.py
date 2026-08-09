"""``codepraxis validate`` — run a pack's tests.

The command orchestrates and nothing else: it resolves packs, asks an executor
to run them, hands results to a reporter, and turns them into an exit code.
Which executor (local or remote) is chosen in ``cli.py``, so this code is
identical for both tiers and testable without a subprocess or a network.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path

from ..domain.results import Fixture, RunResult
from ..errors import PackError
from ..execution.executor import Executor
from ..packio.discovery import find_packs, resolve_pack_dir
from ..packio.loader import load_pack
from ..reporting.reporter import Reporter
from ..validation.registry import has_errors
from ..validation.registry import lint as run_rules

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
    try:
        for pack_dir in pack_dirs:
            pack = load_pack(pack_dir)

            # Static rules first. A pack whose testCases cannot be constructed
            # produces an opaque traceback when executed, so there is nothing to
            # learn from running it — report the real cause and move on.
            findings = run_rules(pack)
            if has_errors(findings):
                reporter.report(
                    RunResult(pack_name=pack.name, executor="lint", diagnostics=tuple(findings))
                )
                exit_code = EXIT_FAILED
                continue

            chosen = list(fixtures) if fixtures else _default_fixtures(pack)
            result = executor.execute(pack, chosen)
            # Warnings from the static pass travel with the execution result so
            # the author sees one report, not two.
            result = dataclasses.replace(
                result, diagnostics=tuple(findings) + tuple(result.diagnostics)
            )
            reporter.report(result)
            # An inconclusive run means this tier lacked the infrastructure to
            # judge the pack, not that the pack is wrong. Failing the command
            # would block an inner loop over something the author cannot fix.
            if not result.ok and not result.inconclusive:
                exit_code = EXIT_FAILED
    finally:
        reporter.close()
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
