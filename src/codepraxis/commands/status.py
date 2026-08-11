"""``codepraxis`` with no arguments — where am I, and what do I type next.

A bare invocation used to print argparse help: a wall of flags that tells a new
author nothing about what to *do*. It is also the first thing everyone types,
which makes it the best onboarding surface the CLI has.

So this reads the directory and answers one question — what is the next step —
in the same spirit as ``git status``.

Everything reported here is determined from local files. Whether a pack has
*passed* validation is deliberately not guessed at: the CLI does not record run
results, and inventing a state we cannot observe is worse than omitting it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ..domain import contract
from ..domain import spec as spec_module
from ..execution.remote import config as remote_config
from ..packio import discovery
from ..plugin import installer

EXIT_OK = 0

#: Cheap enough to run on every pack in a directory; a real parse would mean
#: importing candidate code just to print a status line.
_TEST_CASE_DEF = re.compile(rf"^\s*def\s+{contract.TEST_CASE_PREFIX}", re.MULTILINE)


@dataclass(frozen=True)
class PackStatus:
    path: Path
    question_dir: Path
    has_spec: bool
    spec_approved: bool
    complete: bool
    missing: list[str]
    has_solution: bool
    case_count: int | None
    challenge_id: int | None
    published_status: str | None

    @property
    def name(self) -> str:
        return self.question_dir.name

    @property
    def next_command(self) -> str:
        if not self.has_spec:
            return f"codepraxis plan          # {self.name} has no {contract.SPEC_FILE}"
        if not self.spec_approved:
            return f"codepraxis approve {self.name}"
        if not self.complete:
            return f"codepraxis build         # {self.name} is missing {', '.join(self.missing)}"
        if not self.has_solution:
            return f"codepraxis build         # {self.name} has no reference solution"
        if self.challenge_id is None:
            return f"codepraxis validate {self.name}"
        if self.published_status == "draft":
            return f"codepraxis ship --live {self.name}"
        return f"codepraxis edit {self.challenge_id}"


def inspect_pack(path: Path) -> PackStatus:
    missing = [rel for rel in contract.REQUIRED_PACK_PATHS if not (path / rel).exists()]

    # spec.md and the solution live at the question level, beside the pack —
    # the spec describes the whole question, and keeping the solution out of
    # the pack is what stops it being packaged for candidates.
    question_dir = path.parent if path.name == contract.PACK_DIR else path
    plan = spec_module.read(question_dir)

    challenge_id: int | None = None
    published_status: str | None = None
    publish_file = path / contract.PUBLISH_FILE
    if publish_file.is_file():
        try:
            data = json.loads(publish_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        raw_id = data.get("challenge_id")
        challenge_id = raw_id if isinstance(raw_id, int) else None
        published_status = data.get("status")

    return PackStatus(
        path=path,
        question_dir=question_dir,
        has_spec=plan is not None,
        spec_approved=plan is not None and plan.approved,
        complete=not missing,
        missing=missing,
        has_solution=(question_dir / contract.SOLUTION_DIR).is_dir(),
        case_count=_count_cases(path),
        challenge_id=challenge_id,
        published_status=published_status,
    )


def run(root: Path | None = None) -> int:
    root = (root or Path.cwd()).resolve()
    stored = remote_config.read_stored()
    company = stored.get("company")
    logged_in = bool(stored.get("token"))

    if not logged_in:
        _print_signed_out()
        return EXIT_OK

    print(f"codepraxis — authoring as {company or 'your company'}\n")

    packs = [inspect_pack(path) for path in discovery.find_packs(root)]
    if not packs:
        _print_empty()
        return EXIT_OK

    for pack in packs:
        _print_pack(pack)

    print("Next:")
    print(f"    {packs[0].next_command}\n")
    return EXIT_OK


def _print_signed_out() -> None:
    print("codepraxis — build real-world coding assessments\n")
    print("  You are not logged in.\n")
    print("  See a real question first, no account needed:")
    print("      codepraxis example\n")
    print("  Or log in to start authoring:")
    print("      codepraxis login\n")
    print("  The whole thing explained:")
    print("      codepraxis guide\n")


def _print_empty() -> None:
    print("  No questions here yet.\n")
    print("  Design one with Claude — run these in Claude Code:")
    print(f"      /plugin marketplace add {installer.HOSTED_MARKETPLACE}")
    print(f"      /plugin install {installer.PLUGIN_NAME}@{installer.HOSTED_NAME}")
    print("      /codepraxis:plan\n")
    print("  Or scaffold one by hand:")
    print("      codepraxis new my-question\n")
    print("  The whole thing explained:")
    print("      codepraxis guide\n")


def _print_pack(pack: PackStatus) -> None:
    print(f"  {_display(pack.question_dir)}")

    if not pack.has_spec:
        plan_state = f"no {contract.SPEC_FILE}"
    else:
        plan_state = "approved" if pack.spec_approved else "waiting for approval"
    print(f"    plan        {plan_state}")

    if pack.complete:
        detail = f"{pack.case_count} cases" if pack.case_count else "complete"
        print(f"    pack        {detail}")
    else:
        print(f"    pack        missing {', '.join(pack.missing)}")

    print(f"    solution    {'present' if pack.has_solution else 'missing'}")

    if pack.challenge_id is None:
        print("    published   not yet")
    else:
        state = pack.published_status or "unknown"
        print(f"    published   #{pack.challenge_id} · {state}")
    print()


def _count_cases(path: Path) -> int | None:
    test_file = path / contract.TESTS_DIR / "test_1.py"
    if not test_file.is_file():
        return None
    try:
        return len(_TEST_CASE_DEF.findall(test_file.read_text(encoding="utf-8"))) or None
    except OSError:
        return None


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)
