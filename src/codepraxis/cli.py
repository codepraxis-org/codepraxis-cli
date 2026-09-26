"""The ``codepraxis`` command line.

Building a question happens in a real container, never locally:

    codepraxis categories                   the categories a public question can go into
    codepraxis push    <q>                  send changed files; the first push opens the container
    codepraxis pull    <q> [path]           get files back from the container
    codepraxis exec    <q> "<command>"      run a command in the workspace as the candidate
    codepraxis test    <q> [--visible]      Run, or the full starter and solution check
    codepraxis logs    <q> [source]         setup, grader, exec, run or results
    codepraxis publish <q>                  save the question as a draft and print its URL
    codepraxis stop    <q>                  hand the container back early

The API key comes from ``CODEPRAXIS_API_KEY``. ``<q>`` is a folder under
``challenges/``, or a path to one.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, coding, interview
from .errors import PraxisError
from .platform import Backend, Container, NotFound, Unreachable
from .plugin import installer
from .question import Question

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

LOG_SOURCES = ("setup", "grader", "exec", "run", "results")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codepraxis",
        description="Build CodePraxis questions in a real container and publish them as drafts.",
    )
    parser.add_argument("--version", action="version", version=f"codepraxis {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    cmd = sub.add_parser("categories", help="List the categories a public question can go into.")
    cmd.set_defaults(handler=cmd_categories)

    cmd = sub.add_parser("push", help="Send changed files to the container; the first push opens it.")
    cmd.add_argument("question")
    cmd.set_defaults(handler=cmd_push)

    cmd = sub.add_parser("pull", help="Get files back from the container into the local pack.")
    cmd.add_argument("question")
    cmd.add_argument("path", nargs="?", help="One file, e.g. source/main.py. Default: every file that differs.")
    cmd.set_defaults(handler=cmd_pull)

    cmd = sub.add_parser("exec", help="Run a command in the workspace as the candidate user.")
    cmd.add_argument("question")
    cmd.add_argument("shell_command", metavar="command")
    cmd.add_argument("--timeout", type=int, default=120, help="Seconds, at most 600. Default 120.")
    cmd.set_defaults(handler=cmd_exec)

    cmd = sub.add_parser("test", help="Coding: Run, or starter-fails/solution-passes. Interview: the checks.")
    cmd.add_argument("question")
    cmd.add_argument("--visible", action="store_true", help="Only the visible cases (the candidate's Run).")
    cmd.set_defaults(handler=cmd_test)

    cmd = sub.add_parser("logs", help="The question's logs in the container.")
    cmd.add_argument("question")
    cmd.add_argument("source", nargs="?", default="setup", choices=LOG_SOURCES)
    cmd.add_argument("--tail", type=int, default=200, help="Lines to show. Default 200.")
    cmd.set_defaults(handler=cmd_logs)

    cmd = sub.add_parser("publish", help="Save the question to the platform as a draft and print its URL.")
    cmd.add_argument("question")
    cmd.set_defaults(handler=cmd_publish)

    cmd = sub.add_parser("stop", help="Hand the container back now instead of after 30 idle minutes.")
    cmd.add_argument("question")
    cmd.set_defaults(handler=cmd_stop)

    cmd = sub.add_parser("install", help="Install the Claude Code plugin into this repository.")
    cmd.add_argument("target", choices=("claude-plugin",))
    cmd.add_argument("--force", action="store_true", help="Overwrite an existing install.")
    cmd.set_defaults(handler=cmd_install)
    return parser


# ── commands ────────────────────────────────────────────────────────────


def cmd_categories(args) -> int:
    for category in Backend().get("/categories").get("categories", []):
        print(f"{category['slug']:32} {category['name']}")
    return EXIT_OK


def cmd_push(args) -> int:
    q = Question.find(args.question)
    q.require_coding("push")
    coding.push(q, Backend())
    return EXIT_OK


def cmd_pull(args) -> int:
    q = Question.find(args.question)
    q.require_coding("pull")
    container = _open_container(q)
    local = q.pack_files()
    if args.path:
        paths = [args.path]
    else:
        from .question import sha256

        remote = container.list_files()
        paths = [f["path"] for f in remote
                 if f["path"] not in local or sha256(local[f["path"]].read()) != f["sha256"]]
    if not paths:
        print("Local pack already matches the container.")
    for path in paths:
        target = q.pack / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(container.read_file(path))
        print(f"  pulled  {path}")
    return EXIT_OK


def cmd_exec(args) -> int:
    q = Question.find(args.question)
    q.require_coding("exec")
    session = coding.push(q, Backend())
    result = session.container.exec(args.shell_command, timeout_s=args.timeout)
    sys.stdout.write(result.get("stdout") or "")
    sys.stderr.write(result.get("stderr") or "")
    if result.get("timed_out"):
        print(f"\n(timed out after {args.timeout}s)", file=sys.stderr)
        return EXIT_FAILED
    return int(result.get("exit_code") or 0)


def cmd_test(args) -> int:
    q = Question.find(args.question)
    backend = Backend()
    if q.kind == "interview":
        if args.visible:
            raise PraxisError("--visible is for coding questions.")
        return EXIT_OK if interview.check(q, backend) else EXIT_FAILED
    session = coding.push(q, backend)
    if args.visible:
        cases, error = coding.run_visible(session.container)
        if not cases:
            raise PraxisError("Run produced no cases." + (f" The grader's log ends:\n{error}" if error else ""))
        coding.print_cases(cases)
        return EXIT_OK
    return EXIT_OK if coding.full_test(q, session) else EXIT_FAILED


def cmd_logs(args) -> int:
    q = Question.find(args.question)
    q.require_coding("logs")
    result = _open_container(q).logs(args.source, tail=args.tail)
    if not result.get("exists"):
        print(f"No {args.source} log yet.")
        return EXIT_OK
    print(result.get("text", ""))
    return EXIT_OK


def cmd_publish(args) -> int:
    q = Question.find(args.question)
    backend = Backend()
    if q.kind == "interview":
        result = interview.save(q, backend)
        verb = "Saved" if result.get("created") else "Updated"
        where = "the public bank" if result.get("visibility") == "public" else "your company"
        print(f"{verb} as a draft in {where}: question {result['question_id']}")
        if result.get("categories"):
            print(f"  categories: {', '.join(result['categories'])}")
        print(f"  {result['url']}")
    else:
        result = coding.save_draft(q, backend)
        print(f"Saved as a draft: challenge {result.get('challenge_id')}, version {result.get('challenge_version_id')}")
        if result.get("categories"):
            print(f"  categories: {', '.join(result['categories'])}")
        print(f"  {coding.dashboard_link(result.get('challenge_id'))}")
    print("Publish it from that page when it's ready.")
    return EXIT_OK


def cmd_stop(args) -> int:
    q = Question.find(args.question)
    q.require_coding("stop")
    released = Backend().delete("/container").get("released")
    q.save_state(base_url=None, folder=None)
    print("Container handed back." if released else "No container was open.")
    return EXIT_OK


def cmd_install(args) -> int:
    result = installer.install(Path.cwd(), force=args.force)
    print(installer.describe(result))
    return EXIT_OK


# ── helpers ─────────────────────────────────────────────────────────────


def _open_container(q: Question) -> Container:
    """The container the question is open in, for commands that only read from it."""
    state = q.state()
    if state.get("base_url") and state.get("folder"):
        container = Container(state["base_url"], state["folder"])
        try:
            container.status()
            return container
        except (NotFound, Unreachable):
            pass
    raise PraxisError(f"'{q.slug}' isn't open in a container. Run `codepraxis push {q.slug}` first.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return EXIT_USAGE
    try:
        return handler(args)
    except PraxisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAILED
    except KeyboardInterrupt:  # pragma: no cover
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
