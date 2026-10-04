"""The ``codepraxis`` command line.

    codepraxis push    <q>                  save the question to the platform (as a draft); a bank is replaced
    codepraxis pull    <q|id> [--mcq]       get a question (or, with --mcq, a bank) back from the platform
    codepraxis launch  <q> [--fresh]        open it in a container, the way a candidate gets it
    codepraxis exec    <q> "<command>"      run a command there as the candidate (sends changes first)
    codepraxis test    <q> [--visible]      Run, or the starter/solution check (sends changes first);
                                            for an MCQ bank, the local checks and preview.md
    codepraxis logs    <q> [source]         setup, grader, exec, run or results
    codepraxis categories                   the categories a public question can go into
    codepraxis stop    <q>                  hand the container back now

The API key comes from ``CODEPRAXIS_API_KEY``. ``<q>`` is a folder under
``challenges/`` (or ``mcq/`` for an MCQ bank), or a path to one.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, coding, interview, mcq, progress
from .errors import PraxisError
from .platform import Backend
from .plugin import installer
from .question import Question

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

LOG_SOURCES = ("setup", "grader", "exec", "run", "results")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codepraxis",
        description="Build CodePraxis questions in a real container and save them to the platform as drafts.",
    )
    parser.add_argument("--version", action="version", version=f"codepraxis {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    cmd = sub.add_parser("push", help="Save the question to the platform (a draft keeps one version); "
                                      "an MCQ bank replaces the bank.")
    cmd.add_argument("question")
    cmd.set_defaults(handler=cmd_push)

    cmd = sub.add_parser("pull", help="Get a question back from the platform, solution included.")
    cmd.add_argument("question", help="A question or bank folder, or an id.")
    kind = cmd.add_mutually_exclusive_group()
    kind.add_argument("--interview", action="store_true", help="The id is an AI interview question.")
    kind.add_argument("--mcq", action="store_true", help="The id is an MCQ question bank.")
    cmd.add_argument("--into", type=Path, help="Folder to write into. Default: challenges/<name> "
                                                "(mcq/<bank name> for a bank).")
    cmd.set_defaults(handler=cmd_pull)

    cmd = sub.add_parser("launch", help="Open the pushed question in a container, as a candidate gets it.")
    cmd.add_argument("question")
    cmd.add_argument("--fresh", action="store_true", help="Hand the current container back and start clean.")
    cmd.set_defaults(handler=cmd_launch)

    cmd = sub.add_parser("exec", help="Run a command in the workspace as the candidate (sends changes first).")
    cmd.add_argument("question")
    cmd.add_argument("shell_command", metavar="command")
    cmd.add_argument("--timeout", type=int, default=120, help="Seconds, at most 600. Default 120.")
    cmd.set_defaults(handler=cmd_exec)

    cmd = sub.add_parser("test", help="Coding: Run, or starter-fails/solution-passes. Interview: the checks. "
                                      "MCQ bank: the local checks, and preview.md.")
    cmd.add_argument("question")
    cmd.add_argument("--visible", action="store_true", help="Only the visible cases (the candidate's Run).")
    cmd.set_defaults(handler=cmd_test)

    cmd = sub.add_parser("logs", help="The question's logs in the container.")
    cmd.add_argument("question")
    cmd.add_argument("source", nargs="?", default="setup", choices=LOG_SOURCES)
    cmd.add_argument("--tail", type=int, default=200, help="Lines to show. Default 200.")
    cmd.set_defaults(handler=cmd_logs)

    cmd = sub.add_parser("categories", help="List the categories a public question can go into.")
    cmd.set_defaults(handler=cmd_categories)

    cmd = sub.add_parser("stop", help="Hand the container back now instead of after 30 idle minutes.")
    cmd.add_argument("question")
    cmd.set_defaults(handler=cmd_stop)

    cmd = sub.add_parser("install", help="Write the Claude Code plugin into this repository.")
    cmd.add_argument("target", choices=("claude-plugin",))
    cmd.add_argument("--force", action="store_true", help="Overwrite an existing install.")
    cmd.set_defaults(handler=cmd_install)
    return parser


# ── commands ────────────────────────────────────────────────────────────


def cmd_push(args) -> int:
    q = Question.find(args.question)
    if q.kind == "mcq":
        mcq.push(q, Backend())
        progress.next_step("add the bank to a template's Knowledge check round on the website.")
    elif q.kind == "interview":
        interview.save(q, Backend())
    else:
        _warn_setup_rules(q)
        coding.push(q, Backend())
        progress.next_step(f"`codepraxis launch {q.slug}` to try it in a container.")
    return EXIT_OK


def cmd_pull(args) -> int:
    backend = Backend()
    folder = Path(args.question)
    existing = None
    for candidate in (folder, Path.cwd() / args.question, Path.cwd() / "challenges" / args.question,
                      Path.cwd() / "mcq" / args.question):
        if candidate.is_dir():
            existing = Question.find(str(candidate))
            break
    if existing is not None:
        if existing.kind == "mcq":
            bank_id = existing.state().get("bank_id")
            if not bank_id:
                raise PraxisError(f"{existing.root / '.codepraxis.json'} has no bank_id: it was never pushed.")
            mcq.pull(backend, int(bank_id), existing.root)
        elif existing.kind == "interview":
            question_id = existing.read_question().get("id")
            if not question_id:
                raise PraxisError(f"{existing.question_json} has no id: it was never pushed.")
            interview.pull(backend, int(question_id), existing.root)
        else:
            challenge_id = existing.read_publish().get("challenge_id")
            if not challenge_id:
                raise PraxisError(f"{existing.publish_json} has no challenge_id: it was never pushed.")
            coding.pull(backend, int(challenge_id), existing.root)
        return EXIT_OK
    if not args.question.isdigit():
        raise PraxisError(f"'{args.question}' is neither a question folder nor an id.")
    question_id = int(args.question)
    if args.mcq:
        q = mcq.pull(backend, question_id, args.into)
        progress.next_step(f"`codepraxis test {q.root}` to check it and write preview.md.")
    elif args.interview:
        interview.pull(backend, question_id, args.into or Path.cwd() / "challenges" / f"interview_{question_id}")
    else:
        coding.pull(backend, question_id, args.into or Path.cwd() / "challenges")
    return EXIT_OK


def cmd_launch(args) -> int:
    q = Question.find(args.question)
    q.require_coding("launch")
    _warn_setup_rules(q)
    coding.launch(q, Backend(), fresh=args.fresh)
    progress.next_step(f"`codepraxis test {q.slug} --visible`, or `codepraxis exec {q.slug} \"<command>\"`.")
    return EXIT_OK


def cmd_exec(args) -> int:
    q = Question.find(args.question)
    q.require_coding("exec")
    session = coding.connect(q)
    coding.send_changes(q, session.container)
    with progress.step(f"Running `{args.shell_command}` as the candidate",
                       waiting=lambda elapsed: f"still running (timeout {args.timeout}s)") as s:
        result = session.container.exec(args.shell_command, timeout_s=args.timeout)
        s.result(f"Exit {result.get('exit_code')} after {result.get('seconds', 0)}s"
                 if not result.get("timed_out") else f"Timed out after {args.timeout}s")
    sys.stdout.write(result.get("stdout") or "")
    sys.stdout.write(result.get("stderr") or "")
    if result.get("timed_out"):
        return EXIT_FAILED
    return int(result.get("exit_code") or 0)


def cmd_test(args) -> int:
    q = Question.find(args.question)
    if q.kind == "mcq":
        if args.visible:
            raise PraxisError("--visible is for coding questions.")
        ok = mcq.test(q)
        progress.next_step(f"review {q.slug}/preview.md, then `codepraxis push {q.slug}`." if ok
                           else "fix the errors above and test again.")
        return EXIT_OK if ok else EXIT_FAILED
    if q.kind == "interview":
        if args.visible:
            raise PraxisError("--visible is for coding questions.")
        ok = interview.check(q, Backend())
        progress.next_step(f"`codepraxis push {q.slug}`" if ok else "fix the blockers above and test again.")
        return EXIT_OK if ok else EXIT_FAILED
    _warn_setup_rules(q)
    session = coding.connect(q)
    coding.send_changes(q, session.container)
    if args.visible:
        coding.print_cases(coding.run_visible(session.container))
        return EXIT_OK
    ok = coding.full_test(q, session)
    progress.next_step(f"`codepraxis push {q.slug}` to save it." if ok
                       else "fix what failed above, then test again.")
    return EXIT_OK if ok else EXIT_FAILED


def cmd_logs(args) -> int:
    q = Question.find(args.question)
    q.require_coding("logs")
    result = coding.connect(q).container.logs(args.source, tail=args.tail)
    if not result.get("exists"):
        progress.line(f"No {args.source} log yet.")
        return EXIT_OK
    progress.line(result.get("text", ""))
    return EXIT_OK


def cmd_categories(args) -> int:
    for category in Backend().get("/categories").get("categories", []):
        progress.line(f"{category['slug']:32} {category['name']}")
    return EXIT_OK


def cmd_stop(args) -> int:
    q = Question.find(args.question)
    q.require_coding("stop")
    with progress.step("Handing the container back") as s:
        released = Backend().delete("/container").get("released")
        q.save_state(base_url=None, folder=None)
        s.result("Container handed back" if released else "No container was open")
    return EXIT_OK


def cmd_install(args) -> int:
    result = installer.install(Path.cwd(), force=args.force)
    progress.line(installer.describe(result))
    return EXIT_OK


def _warn_setup_rules(q: Question) -> None:
    for problem in coding.setup_sh_problems(q):
        progress.warn(problem)


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
        print(f"error: {exc}", file=sys.stderr, flush=True)
        return EXIT_FAILED
    except KeyboardInterrupt:  # pragma: no cover
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
