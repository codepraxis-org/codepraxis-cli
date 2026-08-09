"""Command-line entry point.

Argument parsing and dependency wiring, nothing else. Concrete executors and
reporters are chosen here and injected into commands, so commands stay
independent of how results are produced or rendered.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .commands import login as login_command
from .commands import publish as publish_command
from .commands import validate as validate_command
from .domain.results import Fixture
from .errors import PraxisError
from .execution.local.executor import LocalExecutor
from .plugin import installer
from .reporting.human import HumanReporter
from .reporting.json_reporter import JsonReporter

EXIT_USAGE = 2

INSTALLABLES = ("claude-plugin",)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codepraxis",
        description="Author, validate and publish CodePraxis challenge packs.",
        epilog=(
            "Typical flow:\n"
            "  codepraxis --login\n"
            "  codepraxis validate --local my-challenge     # fast, advisory\n"
            "  codepraxis validate --remote my-challenge    # the real runner\n"
            "  codepraxis --publish my-challenge            # validates, then publishes\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"codepraxis {__version__}")

    # Top-level actions. Mutually exclusive because each is a whole task.
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--login",
        action="store_true",
        help="Store an API key and show which company it publishes as.",
    )
    actions.add_argument(
        "--publish",
        nargs="?",
        const="",
        metavar="PACK",
        help="Validate a pack in the runner, then publish it to your company.",
    )
    actions.add_argument(
        "--install",
        choices=INSTALLABLES,
        metavar="TARGET",
        help="Install an integration. Currently: claude-plugin.",
    )

    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Directory to search for packs (default: current directory).",
    )
    parser.add_argument("--force", action="store_true", help="With --install, overwrite an existing install.")
    parser.add_argument("--yes", action="store_true", help="With --publish, skip the confirmation prompt.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="With --publish, publish straight to candidates instead of as a draft.",
    )
    parser.add_argument(
        "--validation-run-id",
        help="With --publish, reuse a passing validation run instead of running a new one.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show passing cases and anything the tier cannot verify.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")

    subparsers = parser.add_subparsers(dest="command")

    check = subparsers.add_parser(
        "validate",
        help="Validate a pack: the solution must pass, the starter must fail.",
        description=(
            "Runs a pack's testCases against the reference solution and the starter. "
            "--local is a fast advisory check on your machine; --remote runs the real "
            "runner image on CodePraxis and is what publishing requires."
        ),
    )
    check.add_argument(
        "selector",
        nargs="?",
        help="Pack directory or name. Defaults to every pack found under --root.",
    )
    check.add_argument("--root", type=Path, default=None, help="Directory to search for packs.")

    tier = check.add_mutually_exclusive_group()
    tier.add_argument(
        "--local",
        dest="tier",
        action="store_const",
        const="local",
        help="Run on this machine (default). Fast, advisory, no network.",
    )
    tier.add_argument(
        "--remote",
        dest="tier",
        action="store_const",
        const="remote",
        help="Run in the real runner image on CodePraxis. Required before publishing.",
    )
    check.set_defaults(tier="local")

    check.add_argument(
        "--fixture",
        choices=[fixture.value for fixture in Fixture],
        action="append",
        dest="fixtures",
        help="Run only this fixture. Repeatable. Defaults to solution + starter.",
    )
    check.add_argument(
        "--llm-base-url",
        help=(
            "OpenAI-compatible endpoint for packs that call a model. Defaults to "
            "OPENAI_BASE_URL. Without a key, model-dependent cases are reported "
            "unverifiable rather than failed."
        ),
    )
    check.add_argument(
        "--llm-api-key",
        help="API key for --llm-base-url. Defaults to OPENAI_API_KEY (preferred: keep it in the environment).",
    )
    check.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    check.add_argument("-v", "--verbose", action="store_true", help="Show passing cases and notes.")
    check.set_defaults(handler=_handle_validate)

    return parser


def _reporter(args: argparse.Namespace):
    return JsonReporter() if args.json else HumanReporter(verbose=args.verbose)


def _build_executor(args: argparse.Namespace):
    if args.tier == "remote":
        # Imported lazily so a local run never pays for the network stack, and
        # a missing credential file cannot break an offline run.
        from .execution.remote.executor import RemoteExecutor

        return RemoteExecutor()
    return LocalExecutor(
        llm_base_url=getattr(args, "llm_base_url", None),
        llm_api_key=getattr(args, "llm_api_key", None),
    )


def _handle_validate(args: argparse.Namespace) -> int:
    fixtures = [Fixture(value) for value in args.fixtures] if args.fixtures else None
    return validate_command.run(
        root=args.root or Path.cwd(),
        selector=args.selector,
        executor=_build_executor(args),
        reporter=_reporter(args),
        fixtures=fixtures,
    )


def _handle_install(target: str, force: bool) -> int:
    if target == "claude-plugin":
        result = installer.install(Path.cwd(), force=force)
        print(installer.describe(result))
        return 0
    raise PraxisError(f"Unknown install target: {target}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.login:
            return login_command.run()
        if args.publish is not None:
            return publish_command.run(
                root=args.root,
                selector=args.publish or None,
                reporter=_reporter(args),
                assume_yes=args.yes,
                live=args.live,
                validation_run_id=args.validation_run_id,
            )
        if args.install:
            return _handle_install(args.install, args.force)
        if not getattr(args, "handler", None):
            parser.print_help()
            return EXIT_USAGE
        return args.handler(args)
    except PraxisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except KeyboardInterrupt:  # pragma: no cover
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
