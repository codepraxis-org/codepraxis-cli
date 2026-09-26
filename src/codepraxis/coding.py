"""Building a coding question in a real container.

The question is saved as a draft once, so the platform can load it, then opened
in the API key owner's container the way the website opens a question: the
normal setup runs, ``setup.sh`` included. After that, every change is a file
sync, and Run and Submit are the candidate's own.
"""

from __future__ import annotations

import io
import re
import stat
import sys
import time
import zipfile
from dataclasses import dataclass

from .errors import PraxisError
from .platform import Backend, Container, NotFound, Unreachable, website_url
from .question import Question, ignored, sha256

SETUP_WAIT_SECONDS = 15 * 60


def say(message: str = "") -> None:
    print(message, flush=True)


def note(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


# ── the draft ───────────────────────────────────────────────────────────


def bundle(q: Question, with_solution: bool = True) -> bytes:
    """``pack/<folder>/...`` plus ``solution/...``, the layout the backend takes.

    The backend stores the pack without the solution; the solution only travels
    so a later runner-validated publish has it.
    """
    folder = q.folder_name()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for rel, local in q.pack_files().items():
            _add(archive, f"pack/{folder}/{rel}", local.disk)
        if with_solution:
            for rel, local in q.solution_files().items():
                _add(archive, f"solution/{rel[len('source/'):]}", local.disk)
    return buffer.getvalue()


def _add(archive: zipfile.ZipFile, name: str, disk) -> None:
    info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    executable = disk.stat().st_mode & stat.S_IXUSR
    info.external_attr = ((0o755 if executable else 0o644) | stat.S_IFREG) << 16
    archive.writestr(info, disk.read_bytes())


def save_draft(q: Question, backend: Backend) -> dict:
    """Upload the pack as a draft: a new question, or a new version of this one."""
    challenge_id = q.read_publish().get("challenge_id")
    path = "/challenges/direct?status=draft" + (f"&challenge_id={challenge_id}" if challenge_id else "")
    result = backend.post_zip(path, bundle(q))
    if result.get("challenge_id"):
        q.remember_challenge_id(int(result["challenge_id"]))
    return result


def dashboard_link(challenge_id) -> str:
    return f"{website_url()}/company/challenges/{challenge_id}"


# ── the container ───────────────────────────────────────────────────────


@dataclass
class Session:
    container: Container
    challenge_version_id: int
    opened_now: bool


def open_container(q: Question, backend: Backend, *, reuse: bool = True) -> Session:
    """The container this question is open in, opening it if needed.

    Reused while it answers. The pool reclaims one after 30 idle minutes, and a
    reclaimed container simply gets reopened here.
    """
    state = q.state()
    if reuse and state.get("base_url") and state.get("folder"):
        container = Container(state["base_url"], state["folder"])
        try:
            container.status()
            return Session(container, int(state["challenge_version_id"]), opened_now=False)
        except (NotFound, Unreachable):
            note("The container this question was open in has gone; opening a new one.")

    challenge_id = q.read_publish().get("challenge_id") or state.get("challenge_id")
    if not challenge_id:
        say("Saving the question as a draft so the platform can load it…")
        challenge_id = save_draft(q, backend)["challenge_id"]
        say(f"  draft: {dashboard_link(challenge_id)}")

    say("Opening it in a container (a cold start can take a few minutes)…")
    opened = backend.open_challenge(int(challenge_id))
    folder = opened.get("folder") or q.folder_name()
    q.save_state(
        challenge_id=int(challenge_id),
        challenge_version_id=int(opened["challenge_version_id"]),
        base_url=opened["base_url"],
        folder=folder,
    )
    say(f"  {opened.get('container_url') or opened['base_url']}")
    container = Container(opened["base_url"], folder)
    wait_for_setup(container)
    return Session(container, int(opened["challenge_version_id"]), opened_now=True)


def wait_for_setup(container: Container, timeout: int = SETUP_WAIT_SECONDS) -> None:
    """Wait for setup.sh to finish, print how it went, and stop if it failed."""
    deadline = time.time() + timeout
    announced = False
    while True:
        status = container.status()
        setup = status.get("setup", {})
        if not setup.get("has_setup_sh"):
            return
        exit_code = setup.get("exit_code")
        # The exit code is only written when setup.sh ends; a failed run leaves the
        # panel showing "in progress", so the exit code is what says it is over.
        if exit_code is not None or setup.get("state") == "done":
            break
        if time.time() > deadline:
            raise PraxisError("setup.sh is still running after 15 minutes. See `codepraxis logs <q> setup`.")
        if not announced:
            say("Waiting for setup.sh…")
            announced = True
        time.sleep(3)
    tail = container.logs("setup", tail=15).get("text", "")
    if exit_code not in (None, 0):
        raise PraxisError(f"setup.sh failed (exit {exit_code}). Its last lines:\n{_indent(tail)}")
    say("setup.sh finished.")


# ── syncing ─────────────────────────────────────────────────────────────


@dataclass
class SyncResult:
    written: list
    deleted: list
    setup_changed: bool


def sync(q: Question, container: Container, *, quiet: bool = False) -> SyncResult:
    """Make the container's copy of the question match the local pack.

    Compares hashes and sends only what differs. A file that exists only in the
    container (output the code wrote, a file deleted locally) is removed, so the
    container holds exactly what a candidate would get. Grader files go first so
    the grader is reloaded before the workspace changes.
    """
    local = q.pack_files()
    remote = {f["path"]: f for f in container.list_files()}
    order = sorted(local, key=lambda p: (p.startswith("source/"), p))
    written, deleted = [], []
    for path in order:
        data = local[path].read()
        if remote.get(path, {}).get("sha256") != sha256(data):
            container.write_file(path, data, executable=local[path].executable)
            written.append(path)
    for path in sorted(set(remote) - set(local)):
        if not ignored(path):
            container.delete_file(path)
            deleted.append(path)
    # A setup.sh the container already had ran at load; only a changed one needs rerunning.
    result = SyncResult(written, deleted, setup_changed="setup.sh" in written and "setup.sh" in remote)
    if not quiet:
        _report_sync(result)
    return result


def _report_sync(result: SyncResult) -> None:
    if not result.written and not result.deleted:
        say("Container is up to date.")
        return
    for path in result.written:
        say(f"  sent     {path}")
    for path in result.deleted:
        say(f"  removed  {path}")


def rerun_setup(container: Container) -> None:
    """Run the changed setup.sh the way setup does, as the candidate user."""
    say("setup.sh changed; running it again…")
    folder = container.folder
    result = container.exec(f"bash /praxis/codeFromServer/{folder}/setup.sh {folder}", timeout_s=600)
    output = (result.get("stdout") or "") + (result.get("stderr") or "")
    if result.get("exit_code") != 0:
        raise PraxisError(f"setup.sh failed (exit {result.get('exit_code')}):\n{_indent(_tail(output, 20))}")
    say("setup.sh finished.")


def push(q: Question, backend: Backend) -> Session:
    session = open_container(q, backend)
    result = sync(q, session.container)
    if result.setup_changed and not session.opened_now:
        rerun_setup(session.container)
    return session


# ── running the grader ──────────────────────────────────────────────────


@dataclass
class Case:
    number: int
    status: str
    input: str
    expected: str
    output: str

    @property
    def passed(self) -> bool:
        return self.status.upper() == "PASS"


def cases_from(test_cases: dict) -> list[Case]:
    """Cases in number order, from Run's ``Case N`` or Submit's ``test_case_N`` keys."""
    found = []
    for key, case in (test_cases or {}).items():
        match = re.search(r"(\d+)\s*$", key)
        if not match or not isinstance(case, dict):
            continue
        found.append(Case(int(match.group(1)), str(case.get("status") or ""), str(case.get("input") or ""),
                          str(case.get("expected") or ""), str(case.get("output") or "")))
    return sorted(found, key=lambda c: c.number)


def run_visible(container: Container) -> tuple[list[Case], str | None]:
    result = container.run()
    test_cases = result.get("test_cases")
    if test_cases is None:  # a container image from before Run returned its cases
        import json

        panel = container.logs("run").get("text") or "{}"
        test_cases = json.loads(panel).get("test_cases", {})
    return cases_from(test_cases), result.get("grader_error")


def submit(container: Container, challenge_version_id: int) -> tuple[list[Case], str | None]:
    result = container.submit(challenge_version_id)
    return cases_from((result.get("results") or {}).get("test_cases", {})), result.get("grader_error")


def print_cases(cases: list[Case], visible: int | None = None) -> None:
    for case in cases:
        where = "" if visible is None else (" visible" if case.number <= visible else " hidden")
        mark = "PASS" if case.passed else (case.status or "—")
        say(f"  case {case.number}{where}: {mark}")
        for label, value in (("Input", case.input), ("Expected", case.expected), ("Output", case.output)):
            if value:
                say(f"      {label + ':':9} {_one_line(value)}")


def full_test(q: Question, session: Session) -> bool:
    """Starter must fail every hidden case; starter plus solution must pass everything."""
    container = session.container
    visible = q.visible_case_count()
    solution = q.solution_files()
    if not solution:
        raise PraxisError(f"{q.root / 'solution'} is empty: the full test needs the reference solution.")

    say("\nStarter (every hidden case must fail):")
    starter_cases, error = submit(container, session.challenge_version_id)
    _stop_on_grader_error(starter_cases, error)
    print_cases(starter_cases, visible)
    hidden = [c for c in starter_cases if visible is None or c.number > visible]
    starter_ok = bool(hidden) and not any(c.passed for c in hidden)

    say("\nSolution (every case must pass):")
    starter_files = q.pack_files()
    try:
        for path, local in solution.items():
            container.write_file(path, local.read(), executable=local.executable)
        solution_cases, error = submit(container, session.challenge_version_id)
    finally:
        # Put the starter back whatever happened, so the container matches the pack.
        for path in solution:
            if path in starter_files:
                container.write_file(path, starter_files[path].read(), executable=starter_files[path].executable)
            else:
                container.delete_file(path)
    _stop_on_grader_error(solution_cases, error)
    print_cases(solution_cases, visible)
    solution_ok = bool(solution_cases) and all(c.passed for c in solution_cases)

    say("")
    passing_hidden = [c.number for c in hidden if c.passed]
    if not hidden:
        say("✗ Starter: no hidden cases ran" + ("" if visible is not None else " (no self.RUN in the grader)"))
    elif passing_hidden:
        say(f"✗ Starter passes hidden case(s) {passing_hidden}: they test nothing the starter lacks.")
    else:
        say("✓ Starter fails every hidden case.")
    failing = [c.number for c in solution_cases if not c.passed]
    say("✓ Solution passes every case." if solution_ok else f"✗ Solution fails case(s) {failing}.")
    return starter_ok and solution_ok


def _stop_on_grader_error(cases: list[Case], error: str | None) -> None:
    if not cases:
        raise PraxisError(
            "The grader produced no cases." + (f" Its log ends:\n{_indent(error)}" if error else
                                               " See `codepraxis logs <q> grader`.")
        )


# ── helpers ─────────────────────────────────────────────────────────────


def _tail(text: str, lines: int) -> str:
    return "\n".join((text or "").splitlines()[-lines:])


def _indent(text: str) -> str:
    return "\n".join(f"    {line}" for line in (text or "").splitlines())


def _one_line(value: str, limit: int = 160) -> str:
    flat = " ⏎ ".join(value.strip().splitlines())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"
