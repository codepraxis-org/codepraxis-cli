"""Command-line entry point.

Argument parsing and dependency wiring, nothing else. Concrete executors and
reporters are chosen here and injected into commands, so commands stay
independent of how results are produced or rendered.

The surface is subcommands: ``codepraxis ship``, not ``codepraxis --publish``.
The flag forms still work — they are accepted, hidden from help, and mapped
onto the same handlers — because scripts and CI jobs were written against them
and silently breaking those is worse than carrying the aliases.

A bare ``codepraxis`` prints status, not help. It is the first thing everyone
types, so it answers "what do I type next" rather than listing every flag.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .commands import approve as approve_command
from .commands import catalog as catalog_command
from .commands import example as example_command
from .commands import find_repos as find_repos_command
from .commands import guide as guide_command
from .commands import lint as lint_command
from .commands import login as login_command
from .commands import publish as publish_command
from .commands import status as status_command
from .commands import validate as validate_command
from .domain.results import Fixture
from .errors import PraxisError
from .execution.local.executor import LocalExecutor
from .plugin import installer
from .reporting.human import HumanReporter
from .reporting.json_reporter import JsonReporter
from .scaffold import generator

EXIT_USAGE = 2

INSTALLABLES = ("claude-plugin",)

EPILOG = """\
Typical flow:
  codepraxis install claude-plugin     design and build with Claude
  codepraxis validate my-question      check it locally
  codepraxis ship my-question          publish as a draft

  codepraxis                           where am I, what is next
  codepraxis guide                     the whole thing explained
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codepraxis",
        description="Author, validate and publish CodePraxis questions.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"codepraxis {__version__}")

    _add_legacy_flags(parser)

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    _add_guide(subparsers)
    _add_login(subparsers)
    _add_find_repos(subparsers)
    _add_new(subparsers)
    _add_approve(subparsers)
    _add_lint(subparsers)
    _add_validate(subparsers)
    _add_ship(subparsers)
    _add_list(subparsers)
    _add_edit(subparsers)
    _add_delete(subparsers)
    _add_install(subparsers)
    _add_example(subparsers)

    return parser


# --------------------------------------------------------------------------
# Subcommands
# --------------------------------------------------------------------------


def _add_guide(subparsers) -> None:
    cmd = subparsers.add_parser(
        "guide",
        help="How this works, start to finish.",
        description="What a question is, the steps to build one, and what makes a good one.",
    )
    cmd.set_defaults(handler=lambda args: guide_command.run())


def _add_login(subparsers) -> None:
    cmd = subparsers.add_parser(
        "login",
        help="Store an API key and show which company it publishes as.",
    )
    cmd.set_defaults(handler=lambda args: login_command.run())


def _add_find_repos(subparsers) -> None:
    cmd = subparsers.add_parser(
        "find-repos",
        help="Find a real repository to build a question from.",
        description=(
            "Searches GitHub for repositories a question can be built on. A question "
            "built on real code resists being answered from the brief alone, because "
            "the model has never seen that code. Results are filtered to licences we "
            "may redistribute, and sampled rather than ranked so two authors "
            "searching the same words do not land on the same repository."
        ),
    )
    cmd.add_argument("topic", help='What to test, e.g. "tool calling agent".')
    cmd.add_argument("--language", help="Restrict to one language, e.g. python.")
    cmd.add_argument("--limit", type=int, default=5, help="How many to show (default: 5).")
    cmd.add_argument(
        "--seed",
        type=int,
        help="Reproduce a previous run. Without it, results are sampled fresh each time.",
    )
    cmd.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Where existing questions live, to skip repos already used (default: ./challenges).",
    )
    cmd.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    cmd.set_defaults(handler=_handle_find_repos)


def _handle_find_repos(args: argparse.Namespace) -> int:
    root = args.root if args.root is not None else Path.cwd() / "challenges"
    return find_repos_command.find_repos(
        topic=args.topic,
        language=args.language,
        limit=args.limit,
        seed=args.seed,
        root=root,
        as_json=args.json,
    )


def _add_new(subparsers) -> None:
    cmd = subparsers.add_parser(
        "new",
        help="Scaffold a question by hand that already validates.",
        description=(
            "Writes a complete, passing pack you can edit: solution passes, starter "
            "fails. Running `codepraxis validate` on it should go green immediately, "
            "which also proves your setup works. To design a question with Claude "
            "instead, run `codepraxis install claude-plugin`."
        ),
    )
    cmd.add_argument("name", help="Question name (lowercase letters, digits, underscores).")
    cmd.add_argument("--root", type=Path, default=None, help="Where to create it (default: ./challenges).")
    cmd.add_argument("--backend", default="AI", help="BACKEND value: AI, DSA, EMB or LNX.")
    cmd.add_argument("--language", default="PYTHON", help="LANGUAGE value.")
    cmd.add_argument("--force", action="store_true", help="Overwrite an existing directory.")
    cmd.set_defaults(handler=_handle_new)


def _add_approve(subparsers) -> None:
    cmd = subparsers.add_parser(
        "approve",
        help="Accept a question's plan so it can be built.",
        description=(
            "Records approval in the plan itself. Building is blocked until this "
            "runs, because a plan agreed only in conversation leaves nothing for a "
            "later session, another machine, or a colleague to check."
        ),
    )
    cmd.add_argument("selector", nargs="?", help="Question name or directory. Defaults to the one waiting.")
    cmd.add_argument("--root", type=Path, default=None, help="Directory to search.")
    cmd.set_defaults(handler=lambda args: approve_command.run(args.root or Path.cwd(), args.selector))


def _add_lint(subparsers) -> None:
    cmd = subparsers.add_parser(
        "lint",
        help="Static checks only — no execution, no container.",
        description=(
            "Reads the question and reports problems without importing or running "
            "any of its code. Fast enough for every save, and safe on a pack you "
            "did not write."
        ),
    )
    cmd.add_argument("selector", nargs="?", help="Question directory or name.")
    cmd.add_argument("--root", type=Path, default=None, help="Directory to search.")
    cmd.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    cmd.add_argument("-v", "--verbose", action="store_true", help="Show notes as well as problems.")
    cmd.set_defaults(handler=_handle_lint)


def _add_validate(subparsers) -> None:
    cmd = subparsers.add_parser(
        "validate",
        help="Run it: the solution must pass, the starter must fail.",
        description=(
            "Runs the tests against the reference solution and against the starter. "
            "--local is a fast advisory check on your machine; --remote runs the real "
            "runner image and is what publishing requires."
        ),
    )
    cmd.add_argument(
        "selector",
        nargs="?",
        help="Question directory or name. Defaults to every question found under --root.",
    )
    cmd.add_argument("--root", type=Path, default=None, help="Directory to search.")

    tier = cmd.add_mutually_exclusive_group()
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
        help="Run in the real runner image. Required before publishing.",
    )
    cmd.set_defaults(tier="local")

    cmd.add_argument(
        "--fixture",
        choices=[fixture.value for fixture in Fixture],
        action="append",
        dest="fixtures",
        help="Run only this fixture. Repeatable. Defaults to solution + starter.",
    )
    cmd.add_argument(
        "--llm-base-url",
        help=(
            "OpenAI-compatible endpoint for questions that call a model. Defaults to "
            "OPENAI_BASE_URL. Without a key, model-dependent cases are reported "
            "unverifiable rather than failed."
        ),
    )
    cmd.add_argument(
        "--llm-api-key",
        help="API key for --llm-base-url. Defaults to OPENAI_API_KEY.",
    )
    cmd.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    cmd.add_argument("-v", "--verbose", action="store_true", help="Show passing cases and notes.")
    cmd.set_defaults(handler=_handle_validate)


def _add_ship(subparsers) -> None:
    cmd = subparsers.add_parser(
        "ship",
        aliases=["publish"],
        help="Validate in the runner, then publish to your company.",
        description=(
            "Publishes as a draft unless --live. Remote validation runs first and "
            "local results never qualify: a published question can be sent to "
            "candidates immediately."
        ),
    )
    cmd.add_argument("selector", nargs="?", help="Question directory or name.")
    cmd.add_argument("--root", type=Path, default=Path.cwd(), help="Directory to search.")
    cmd.add_argument("--live", action="store_true", help="Publish straight to candidates instead of as a draft.")
    cmd.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    cmd.add_argument(
        "--challenge-id",
        type=int,
        help=(
            "Publish a new version of this existing question instead of creating "
            "another one. Get the id from `codepraxis list`."
        ),
    )
    cmd.add_argument(
        "--validation-run-id",
        help="Reuse a passing validation run instead of running a new one.",
    )
    cmd.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    cmd.add_argument("-v", "--verbose", action="store_true", help="Show passing cases and notes.")
    cmd.set_defaults(handler=_handle_ship)


def _add_list(subparsers) -> None:
    cmd = subparsers.add_parser(
        "list",
        help="List the questions your company owns, drafts included.",
    )
    cmd.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    cmd.set_defaults(handler=lambda args: catalog_command.list_questions(as_json=args.json))


def _add_edit(subparsers) -> None:
    cmd = subparsers.add_parser(
        "edit",
        help="Update a question's details and open it in a container.",
        description=(
            "Changes catalog details — title, description, difficulty, limits — and "
            "returns a container URL. Changing the question's CODE means editing the "
            "pack and publishing a new version: `codepraxis ship <pack> --challenge-id <id>`."
        ),
    )
    cmd.add_argument("challenge_id", type=int, metavar="ID", help="Question id, from `codepraxis list`.")
    cmd.add_argument("--title", help="Update the question title.")
    cmd.add_argument("--description", help="Update the question description.")
    cmd.add_argument("--status", choices=("draft", "published"), help="Draft or published.")
    cmd.add_argument("--difficulty", type=int, choices=(1, 2, 3), help="Set difficulty.")
    cmd.add_argument("--max-time", type=int, help="Set the time limit in minutes.")
    cmd.add_argument("--max-attempt", type=int, help="Set maximum attempts.")
    cmd.add_argument("--tech-stack", help="Comma-separated technologies, e.g. 'Python,FastAPI'.")
    cmd.add_argument(
        "--ai-enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Toggle AI assistance.",
    )
    cmd.add_argument("--open", action="store_true", dest="open_browser", help="Open the container in your browser.")
    cmd.set_defaults(handler=_handle_edit)


def _add_delete(subparsers) -> None:
    cmd = subparsers.add_parser(
        "delete",
        aliases=["rm"],
        help="Delete a question your company owns.",
        description=(
            "Asks first. The platform refuses once the question has been assigned to "
            "anyone, because deleting it then would orphan attempts and reports. To "
            "take an assigned question out of circulation, set it back to draft "
            "with `codepraxis edit <id> --status draft`."
        ),
    )
    cmd.add_argument("challenge_id", type=int, metavar="ID", help="Question id, from `codepraxis list`.")
    cmd.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    cmd.set_defaults(
        handler=lambda args: catalog_command.delete_question(args.challenge_id, assume_yes=args.yes)
    )


def _add_install(subparsers) -> None:
    cmd = subparsers.add_parser(
        "install",
        help="Install an integration. Currently: claude-plugin.",
        description=(
            "Writes the CodePraxis authoring plugin into this repository, so Claude "
            "Code can design, build and validate questions for you. Prints the two "
            "commands that enable it."
        ),
    )
    cmd.add_argument("target", choices=INSTALLABLES, metavar="TARGET", help="What to install: claude-plugin.")
    cmd.add_argument("--force", action="store_true", help="Overwrite an existing install.")
    cmd.set_defaults(handler=lambda args: _handle_install(args.target, args.force))


def _add_example(subparsers) -> None:
    cmd = subparsers.add_parser(
        "example",
        help="Open a real question in a live container. No account needed.",
        description=(
            "Starts a throwaway container with the featured question already in it "
            "and prints a URL — exactly what a candidate sees. Nothing is recorded "
            "as an attempt."
        ),
    )
    cmd.add_argument("--open", action="store_true", dest="open_browser", help="Open it in your browser.")
    cmd.set_defaults(handler=lambda args: example_command.run(open_browser=args.open_browser))


# --------------------------------------------------------------------------
# Deprecated flag forms
# --------------------------------------------------------------------------


def _add_legacy_flags(parser: argparse.ArgumentParser) -> None:
    """The pre-subcommand surface, kept working and hidden from help.

    Every one of these shipped in a released version, so CI jobs and shell
    aliases depend on them. They map onto the same handlers and print a pointer
    to the subcommand that replaced them.
    """
    legacy = parser.add_argument_group("deprecated")
    legacy.add_argument("--login", action="store_true", help=argparse.SUPPRESS)
    legacy.add_argument("--publish", nargs="?", const="", metavar="PACK", help=argparse.SUPPRESS)
    legacy.add_argument("--list", action="store_true", help=argparse.SUPPRESS)
    legacy.add_argument("--edit", type=int, metavar="ID", help=argparse.SUPPRESS)
    legacy.add_argument("--delete", type=int, metavar="ID", help=argparse.SUPPRESS)
    legacy.add_argument("--install", choices=INSTALLABLES, metavar="TARGET", help=argparse.SUPPRESS)
    legacy.add_argument("--example", action="store_true", help=argparse.SUPPRESS)

    # Shared by several legacy forms; the subcommands declare their own.
    legacy.add_argument("--root", type=Path, default=Path.cwd(), help=argparse.SUPPRESS)
    legacy.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    legacy.add_argument("--yes", action="store_true", help=argparse.SUPPRESS)
    legacy.add_argument("--live", action="store_true", help=argparse.SUPPRESS)
    legacy.add_argument("--challenge-id", type=int, help=argparse.SUPPRESS)
    legacy.add_argument("--validation-run-id", help=argparse.SUPPRESS)
    legacy.add_argument("-v", "--verbose", action="store_true", help=argparse.SUPPRESS)
    legacy.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    legacy.add_argument("--open", action="store_true", dest="open_browser", help=argparse.SUPPRESS)
    legacy.add_argument("--title", help=argparse.SUPPRESS)
    legacy.add_argument("--description", help=argparse.SUPPRESS)
    legacy.add_argument("--status", choices=("draft", "published"), help=argparse.SUPPRESS)
    legacy.add_argument("--difficulty", type=int, choices=(1, 2, 3), help=argparse.SUPPRESS)
    legacy.add_argument("--max-time", type=int, help=argparse.SUPPRESS)
    legacy.add_argument("--max-attempt", type=int, help=argparse.SUPPRESS)
    legacy.add_argument("--tech-stack", help=argparse.SUPPRESS)
    legacy.add_argument("--ai-enabled", action=argparse.BooleanOptionalAction, default=None, help=argparse.SUPPRESS)


def _deprecated(old: str, new: str) -> None:
    print(f"note: `{old}` is now `{new}`. The old form still works.", file=sys.stderr)


def _dispatch_legacy(args: argparse.Namespace) -> int | None:
    """Run a legacy flag form, or return None if none was given."""
    if args.login:
        _deprecated("--login", "codepraxis login")
        return login_command.run()

    if args.publish is not None:
        _deprecated("--publish", "codepraxis ship")
        return _handle_ship(args, selector=args.publish or None)

    if args.list:
        _deprecated("--list", "codepraxis list")
        return catalog_command.list_questions(as_json=args.json)

    if args.edit is not None:
        _deprecated("--edit", "codepraxis edit")
        return catalog_command.edit_question(
            challenge_id=args.edit,
            updates=_edit_updates(args),
            open_browser=args.open_browser,
        )

    if args.delete is not None:
        _deprecated("--delete", "codepraxis delete")
        return catalog_command.delete_question(args.delete, assume_yes=args.yes)

    if args.install:
        _deprecated("--install", "codepraxis install")
        return _handle_install(args.install, args.force)

    if args.example:
        _deprecated("--example", "codepraxis example")
        return example_command.run(open_browser=args.open_browser)

    return None


# --------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------


def _reporter(args: argparse.Namespace):
    return JsonReporter() if args.json else HumanReporter(verbose=args.verbose)


def _build_executor(args: argparse.Namespace):
    if getattr(args, "tier", "local") == "remote":
        # Imported lazily so a local run never pays for the network stack, and
        # a missing credential file cannot break an offline run.
        from .execution.remote.executor import RemoteExecutor

        # --json output is parsed by tooling, so progress would corrupt it.
        return RemoteExecutor(quiet=bool(getattr(args, "json", False)))
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


def _handle_lint(args: argparse.Namespace) -> int:
    return lint_command.run(
        root=args.root or Path.cwd(),
        selector=args.selector,
        reporter=_reporter(args),
    )


def _handle_ship(args: argparse.Namespace, selector: str | None = None) -> int:
    return publish_command.run(
        root=args.root or Path.cwd(),
        selector=selector if selector is not None else getattr(args, "selector", None),
        reporter=_reporter(args),
        assume_yes=args.yes,
        live=args.live,
        validation_run_id=args.validation_run_id,
        challenge_id=args.challenge_id,
    )


def _handle_new(args: argparse.Namespace) -> int:
    # Default to ./challenges so the solution/ sibling lands outside the pack
    # without the author having to think about layout.
    root = args.root or (Path.cwd() / "challenges")
    result = generator.create(
        root=root,
        raw_name=args.name,
        backend=args.backend,
        language=args.language,
        force=args.force,
    )
    print(generator.describe(result, Path.cwd()))
    return 0


def _handle_edit(args: argparse.Namespace) -> int:
    return catalog_command.edit_question(
        challenge_id=args.challenge_id,
        updates=_edit_updates(args),
        open_browser=args.open_browser,
    )


def _edit_updates(args: argparse.Namespace) -> dict:
    tech_stack = None
    if args.tech_stack is not None:
        tech_stack = [item.strip() for item in args.tech_stack.split(",") if item.strip()]
    return {
        "challenge_name": args.title,
        "description": args.description,
        "status": args.status,
        "difficulty": args.difficulty,
        "max_time": args.max_time,
        "max_attempt": args.max_attempt,
        "tech_stack": tech_stack,
        "ai_enabled": args.ai_enabled,
    }


def _handle_install(target: str, force: bool) -> int:
    if target == "claude-plugin":
        result = installer.install(Path.cwd(), force=force)
        print(installer.describe(result))
        return 0
    raise PraxisError(f"Unknown install target: {target}")


# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        legacy_result = _dispatch_legacy(args)
        if legacy_result is not None:
            return legacy_result

        handler = getattr(args, "handler", None)
        if handler is None:
            # No subcommand and no legacy flag: answer "what do I type next"
            # rather than printing every flag we have.
            return status_command.run(args.root)
        return handler(args)
    except PraxisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except KeyboardInterrupt:  # pragma: no cover
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
