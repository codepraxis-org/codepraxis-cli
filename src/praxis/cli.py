"""Command-line entry point.

This module does argument parsing and dependency wiring, nothing else. Every
concrete executor and reporter is chosen here and injected into the command, so
commands stay independent of how results are produced or rendered.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .commands import test as test_command
from .domain.results import Fixture
from .errors import PraxisError
from .execution.local.executor import LocalExecutor
from .reporting.human import HumanReporter
from .reporting.json_reporter import JsonReporter

EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="praxis",
        description="Author and validate CodePraxis challenge packs.",
    )
    parser.add_argument("--version", action="version", version=f"praxis {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "test",
        help="Run a pack's tests locally (fast, advisory).",
        description=(
            "Runs the pack's testCases against the starter and, when present, the "
            "reference solution. Local results are advisory: publishing requires "
            "`praxis validate --remote`."
        ),
    )
    run_parser.add_argument(
        "selector",
        nargs="?",
        help="Pack directory or name. Defaults to every pack found under --root.",
    )
    run_parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Directory to search for packs (default: current directory).",
    )
    run_parser.add_argument(
        "--fixture",
        choices=[fixture.value for fixture in Fixture],
        action="append",
        dest="fixtures",
        help="Run only this fixture. Repeatable. Defaults to solution + starter.",
    )
    run_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a human summary.",
    )
    run_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show passing cases and the checks this tier cannot verify.",
    )
    run_parser.set_defaults(handler=_handle_test)

    return parser


def _handle_test(args: argparse.Namespace) -> int:
    reporter = JsonReporter() if args.json else HumanReporter(verbose=args.verbose)
    fixtures: Optional[List[Fixture]] = (
        [Fixture(value) for value in args.fixtures] if args.fixtures else None
    )
    return test_command.run(
        root=args.root,
        selector=args.selector,
        executor=LocalExecutor(),
        reporter=reporter,
        fixtures=fixtures,
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except PraxisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except KeyboardInterrupt:  # pragma: no cover
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
