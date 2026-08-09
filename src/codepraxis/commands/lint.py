"""``codepraxis lint`` — static checks only, no execution.

Fast enough to run on every save, and safe to run against a pack you did not
write, because no pack code is imported.
"""

from __future__ import annotations

from pathlib import Path

from ..domain.results import RunResult
from ..errors import PackError
from ..packio.discovery import find_packs, resolve_pack_dir
from ..packio.loader import load_pack
from ..reporting.reporter import Reporter
from ..validation.registry import has_errors
from ..validation.registry import lint as run_rules

EXIT_OK = 0
EXIT_FAILED = 1


def run(root: Path, selector: str | None, reporter: Reporter) -> int:
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
            findings = run_rules(pack)
            reporter.report(
                RunResult(pack_name=pack.name, executor="lint", diagnostics=tuple(findings))
            )
            if has_errors(findings):
                exit_code = EXIT_FAILED
    finally:
        reporter.close()
    return exit_code
