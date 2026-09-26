"""Coding questions: push to the platform, pull back, launch in a container, test there.

``push``    local question -> platform (Azure Blob + database), as a draft. A
            draft keeps one version; a published question gets a new version.
``pull``    platform -> local, solution included.
``launch``  the pushed question in the API key owner's container, loaded the
            way the website loads it, so setup.sh runs as for a candidate.
``exec`` and ``test`` first send the files that changed locally to the launched
container, so an edit is tried in seconds without pushing.
"""

from __future__ import annotations

import io
import re
import stat
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import progress
from .errors import PraxisError
from .platform import Backend, Container, HttpError, NotFound, Unreachable, website_url
from .question import Question, ignored, sha256

#: setup.sh must finish within this. It runs on every candidate's container load.
SETUP_LIMIT_SECONDS = 120


# ── push and pull ───────────────────────────────────────────────────────


#: The base commit every candidate's workspace starts from. Progress is saved
#: as git history on top of it, so a workspace without one saves nothing.
BASE_COMMIT_AUTHOR = ("CodeGuru", "guru@codepraxis.com")
BASE_COMMIT_MESSAGE = "Setting up the test environment"
#: Fixed, so the same files always give the same commit.
BASE_COMMIT_DATE = "2026-01-01T00:00:00+0000"


def bundle(q: Question) -> bytes:
    """``pack/<folder>/...`` plus ``solution/...``, the layout the backend takes.

    ``source/._git`` is added: a fresh repository with one commit of ``source/``.
    The container renames it to ``.git`` when it serves the question (unless the
    candidate has saved history of their own). Any ``.git`` the author keeps in
    ``source/`` is ignored, so their history never reaches a candidate.
    """
    import tempfile

    folder = q.folder_name()
    buffer = io.BytesIO()
    with tempfile.TemporaryDirectory(prefix="codepraxis-base-") as work, \
            zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for rel, local in q.pack_files().items():
            _add(archive, f"pack/{folder}/{rel}", local.disk)
        for rel, disk in base_repository(q, Path(work)).items():
            _add(archive, f"pack/{folder}/source/._git/{rel}", disk)
        for rel, local in q.solution_files().items():
            _add(archive, f"solution/{rel[len('source/'):]}", local.disk)
    return buffer.getvalue()


def base_repository(q: Question, work: Path) -> dict:
    """The ``.git`` of a one-commit repository of ``source/``: {path inside .git: file}.

    Built under ``work`` with the git CLI, isolated from the author's own git
    configuration and hooks.
    """
    import os
    import shutil
    import subprocess

    if shutil.which("git") is None:
        raise PraxisError("git is not installed; push needs it to build the base commit for source/.")
    tree = work / "source"
    for rel, local in q.pack_files().items():
        if rel.startswith("source/"):
            target = tree / rel[len("source/"):]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local.disk, target)
    tree.mkdir(exist_ok=True)
    name, email = BASE_COMMIT_AUTHOR
    env = {
        "PATH": os.environ.get("PATH", ""), "HOME": str(work), "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_AUTHOR_DATE": BASE_COMMIT_DATE,
        "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email, "GIT_COMMITTER_DATE": BASE_COMMIT_DATE,
    }
    isolated = ["-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-c", "init.templateDir="]

    def git(*args: str) -> None:
        try:
            subprocess.run(["git", *isolated, *args], cwd=tree, env=env, check=True,
                           capture_output=True, timeout=60)
        except subprocess.CalledProcessError as exc:
            raise PraxisError(f"git {args[0]} failed building the base commit: "
                              f"{exc.stderr.decode(errors='replace').strip()}") from exc
        except subprocess.TimeoutExpired as exc:
            raise PraxisError(f"git {args[0]} took over 60s building the base commit.") from exc

    git("init", "-q", "-b", "main")
    git("add", "-A")
    git("commit", "-q", "--allow-empty", "-m", BASE_COMMIT_MESSAGE)
    git_dir = tree / ".git"
    return {p.relative_to(git_dir).as_posix(): p for p in sorted(git_dir.rglob("*")) if p.is_file()}


def _add(archive: zipfile.ZipFile, name: str, disk: Path) -> None:
    info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    executable = disk.stat().st_mode & stat.S_IXUSR
    info.external_attr = ((0o755 if executable else 0o644) | stat.S_IFREG) << 16
    archive.writestr(info, disk.read_bytes())


def dashboard_link(challenge_id) -> str:
    return f"{website_url()}/company/challenges/{challenge_id}"


def push(q: Question, backend: Backend) -> dict:
    """Save the question to the platform. Never changes whether it is live."""
    challenge_id = q.read_publish().get("challenge_id")
    path = "/challenges/direct?status=draft" + (f"&challenge_id={challenge_id}" if challenge_id else "")
    files = len(q.pack_files())
    with progress.step(f"Pushing {q.slug} ({files} files, solution kept private)") as s:
        result = backend.post_zip(path, bundle(q))
        if result.get("challenge_id"):
            q.remember_challenge_id(int(result["challenge_id"]))
        if result.get("created"):
            s.result(f"Created as a draft: challenge {result['challenge_id']}")
        elif result.get("version_reused"):
            s.result(f"Draft updated (same version {result['challenge_version_id']})")
        else:
            s.result(f"New version {result['challenge_version_id']} saved")
    if result.get("status") == "published" and not result.get("version_reused"):
        progress.warn("This question is live: candidates get this new version from now on.")
    if result.get("categories"):
        progress.line(f"  categories: {', '.join(result['categories'])}")
    progress.line(f"  {dashboard_link(result.get('challenge_id'))}")
    return result


def pull(backend: Backend, challenge_id: int, into: Path) -> Question:
    """Write the pushed question into ``into`` (``challenges/<folder>/``, created if needed)."""
    with progress.step(f"Pulling challenge {challenge_id}") as s:
        blob = backend.get_bytes(f"/challenges/{challenge_id}/files")
        archive = zipfile.ZipFile(io.BytesIO(blob))
        pack_names = [n for n in archive.namelist() if n.startswith("pack/")]
        folder = pack_names[0].split("/")[1] if pack_names else str(challenge_id)
        root = into if into.name == folder or (into / "pack").is_dir() else into / folder
        written = solution = 0
        for name in archive.namelist():
            if name.endswith("/"):
                continue
            if name.startswith(f"pack/{folder}/"):
                rel = name[len(f"pack/{folder}/"):]
                if ignored(rel):  # the generated base repository is rebuilt on push
                    continue
                target = root / "pack" / rel
            elif name.startswith("solution/"):
                target = root / "solution" / name[len("solution/"):]
                solution += 1
            else:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
            written += 1
        q = Question(root)
        q.remember_challenge_id(int(challenge_id))
        s.result(f"Pulled {written} files into {root}" + ("" if solution else " (no solution was stored)"))
    return q


# ── the container ───────────────────────────────────────────────────────


@dataclass
class Session:
    container: Container
    challenge_version_id: int


def launch(q: Question, backend: Backend, *, fresh: bool = False) -> Session:
    """Open the pushed question in the key owner's container and wait for setup.sh."""
    challenge_id = q.read_publish().get("challenge_id")
    if not challenge_id:
        raise PraxisError(f"'{q.slug}' hasn't been pushed yet. Run `codepraxis push {q.slug}` first.")
    if fresh:
        with progress.step("Handing the old container back"):
            backend.delete("/container")
        q.save_state(base_url=None, folder=None)

    def waiting(elapsed: float) -> str:
        return "a cold start can take up to 3 minutes" if elapsed < 180 else "longer than a usual cold start"

    with progress.step(f"Opening challenge {challenge_id} in a container", waiting=waiting) as s:
        def retrying(attempt: int, exc: Exception) -> None:
            s.note(f"request {attempt} was cut off ({str(exc)[:80]}); the platform is still starting "
                   "the container, asking again in 15s")

        opened = backend.open_challenge(int(challenge_id), on_retry=retrying)
        folder = opened.get("folder") or q.folder_name()
        q.save_state(
            challenge_id=int(challenge_id),
            challenge_version_id=int(opened["challenge_version_id"]),
            base_url=opened["base_url"],
            folder=folder,
        )
        s.result(f"Opened version {opened['challenge_version_id']} as {folder}")
    progress.line(f"  {opened.get('container_url') or opened['base_url']}")
    container = Container(opened["base_url"], folder)
    wait_for_setup(container)
    # A container that already had this version keeps its files, and a draft's
    # version id doesn't change when it is re-pushed; make it match local files.
    send_changes(q, container)
    return Session(container, int(opened["challenge_version_id"]))


def connect(q: Question) -> Session:
    """The container the question was launched in, if it is still there."""
    state = q.state()
    if not (state.get("base_url") and state.get("folder")):
        raise PraxisError(f"'{q.slug}' isn't launched. Run `codepraxis launch {q.slug}` first.")
    container = Container(state["base_url"], state["folder"])
    try:
        container.status()
    except (NotFound, Unreachable) as exc:
        raise PraxisError(
            f"The container '{q.slug}' was launched in is gone (reclaimed after 30 idle minutes, or "
            f"stopped). Run `codepraxis launch {q.slug}` again."
        ) from exc
    return Session(container, int(state["challenge_version_id"]))


def wait_for_setup(container: Container, limit: int = SETUP_LIMIT_SECONDS) -> None:
    """Wait for setup.sh (both runs: the candidate's and root's) and stop if either failed.

    setup.sh must finish within ``limit`` seconds: every candidate waits for it.
    """
    latest = {"status": {}}

    def waiting(elapsed: float) -> str:
        last = latest["status"].get("setup", {}).get("last_line") or "no output yet"
        return f"setup.sh still running (limit {limit}s); latest: {last[:160]}"

    with progress.step("Waiting for setup.sh", waiting=waiting) as s:
        started = time.time()
        while True:
            status = container.status()
            latest["status"] = status
            setup = status.get("setup", {})
            if not setup.get("has_setup_sh"):
                s.result("No setup.sh")
                return
            user_code, root_code = setup.get("exit_code"), setup.get("root_exit_code")
            if user_code is not None and user_code != 0:
                raise PraxisError(f"setup.sh failed (exit {user_code}).{_setup_tail(container)}")
            if root_code is not None and root_code != 0:
                raise PraxisError(f"setup.sh failed when run as root (exit {root_code}).{_setup_tail(container)}")
            # An image from before the root run was logged reports only the user run.
            root_known = root_code is not None or "root_exit_code" not in setup
            if user_code == 0 and root_known:
                s.result(f"setup.sh finished in about {time.time() - started:.0f}s")
                return
            if time.time() - started > limit:
                raise PraxisError(
                    f"setup.sh is still running after {limit} seconds, and it must finish within "
                    f"{limit}: every candidate waits for it.{_setup_tail(container)}"
                )
            time.sleep(3)


def _setup_tail(container: Container) -> str:
    try:
        text = container.logs("setup", tail=20).get("text", "")
    except PraxisError:
        return ""
    return f" Its last lines:\n{_indent(text)}\nFull log: `codepraxis logs <q> setup`."


# ── sending changed files ───────────────────────────────────────────────


@dataclass
class SyncResult:
    written: list
    deleted: list
    setup_changed: bool


def send_changes(q: Question, container: Container) -> SyncResult:
    """Make the container's copy match the local pack: send what differs, remove extras.

    Grader files go first, so the grader is reloaded before the workspace
    changes. A changed setup.sh is run again, within the same time limit.
    """
    with progress.step("Sending changed files to the container") as s:
        local = q.pack_files()
        remote = {f["path"]: f for f in container.list_files()}
        written, deleted = [], []
        for path in sorted(local, key=lambda p: (p.startswith("source/"), p)):
            data = local[path].read()
            if remote.get(path, {}).get("sha256") != sha256(data):
                container.write_file(path, data, executable=local[path].executable)
                written.append(path)
                s.note(f"sent     {path}")
        for path in sorted(set(remote) - set(local)):
            if not ignored(path):
                container.delete_file(path)
                deleted.append(path)
                s.note(f"removed  {path}")
        s.result("Container already up to date" if not (written or deleted)
                 else f"Sent {len(written)}, removed {len(deleted)}")
    result = SyncResult(written, deleted, setup_changed="setup.sh" in written and "setup.sh" in remote)
    if result.setup_changed:
        rerun_setup(container, local["setup.sh"].read().decode("utf-8", errors="replace"))
    return result


def rerun_setup(container: Container, script: str) -> None:
    """Run a changed setup.sh again, as the candidate user.

    The candidate can't read /praxis, where the pack lives (it is 700 root), so
    the script is passed in on stdin rather than run from its path; the platform
    copies it to /tmp for the same reason. This reruns the candidate's run only:
    `launch --fresh` repeats the whole setup, root's run included.
    """
    folder = container.folder
    marker = "CODEPRAXIS_SETUP_SH_END"
    command = f"bash -s -- {folder} <<'{marker}'\n{script.rstrip()}\n{marker}"

    def waiting(elapsed: float) -> str:
        return f"setup.sh still running (limit {SETUP_LIMIT_SECONDS}s)"

    with progress.step("setup.sh changed; running it again as the candidate", waiting=waiting) as s:
        result = container.exec(command, timeout_s=SETUP_LIMIT_SECONDS)
        output = (result.get("stdout") or "") + (result.get("stderr") or "")
        if result.get("timed_out"):
            raise PraxisError(
                f"setup.sh took longer than {SETUP_LIMIT_SECONDS}s, the limit.\n{_indent(_tail(output, 20))}"
            )
        if result.get("exit_code") != 0:
            raise PraxisError(f"setup.sh failed (exit {result.get('exit_code')}):\n{_indent(_tail(output, 20))}")
        s.result(f"setup.sh finished in {result.get('seconds', 0):.0f}s")


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


def _grader_wait(what: str):
    return lambda elapsed: f"{what} still running"


def run_visible(container: Container) -> list[Case]:
    with progress.step("Running the visible cases (the candidate's Run)", waiting=_grader_wait("Run")) as s:
        result = container.run()
        test_cases = result.get("test_cases")
        if test_cases is None:  # a container image from before Run returned its cases
            import json

            test_cases = json.loads(container.logs("run").get("text") or "{}").get("test_cases", {})
        cases = cases_from(test_cases)
        _stop_on_grader_error(cases, result.get("grader_error"))
        s.result(f"Run finished: {sum(c.passed for c in cases)}/{len(cases)} passed")
    return cases


#: The longest a Submit may take once its request has been cut off.
SUBMIT_WAIT_SECONDS = 600


def submit(container: Container, challenge_version_id: int, label: str) -> list[Case]:
    with progress.step(f"Submitting the {label} (all cases)", waiting=_grader_wait("Submit")) as s:
        before = container.status().get("last_submit_at") or 0
        try:
            result = container.submit(challenge_version_id)
            test_cases = (result.get("results") or {}).get("test_cases", {})
            grader_error = result.get("grader_error")
        except HttpError as exc:
            # Images before 26 Sep cut a Submit over ~40s off (a keepalive ping the
            # grading agent can't answer) while the grader carries on. Wait for it
            # to write its results rather than touch the workspace mid-run.
            if "keepalive" not in str(exc) and "WebSocket" not in str(exc):
                raise
            s.note("the request was cut off, but the grader is still running; waiting for its results")
            test_cases, grader_error = _wait_for_results(container, before), None
        cases = cases_from(test_cases)
        _stop_on_grader_error(cases, grader_error)
        s.result(f"Submitted the {label}: {sum(c.passed for c in cases)}/{len(cases)} passed")
    return cases


def _wait_for_results(container: Container, after: float) -> dict:
    """The cases of the Submit that finishes after ``after`` (a results-file time)."""
    import json

    deadline = time.time() + SUBMIT_WAIT_SECONDS
    while time.time() < deadline:
        if (container.status().get("last_submit_at") or 0) > after:
            return json.loads(container.logs("results").get("text") or "{}").get("test_cases", {})
        time.sleep(5)
    raise PraxisError(f"The grader wrote no results within {SUBMIT_WAIT_SECONDS}s. See `codepraxis logs <q> grader`.")


def print_cases(cases: list[Case], visible: int | None = None) -> None:
    for case in cases:
        where = "" if visible is None else (" visible" if case.number <= visible else " hidden")
        mark = "PASS" if case.passed else (case.status or "—")
        progress.line(f"  case {case.number}{where}: {mark}")
        for label, value in (("Input", case.input), ("Expected", case.expected), ("Output", case.output)):
            if value:
                progress.line(f"      {label + ':':9} {_one_line(value)}")


def full_test(q: Question, session: Session) -> bool:
    """Starter must fail every hidden case; starter plus solution must pass everything."""
    container = session.container
    visible = q.visible_case_count()
    solution = q.solution_files()
    if not solution:
        raise PraxisError(f"{q.root / 'solution'} is empty: the full test needs the reference solution.")

    starter_cases = submit(container, session.challenge_version_id, "starter")
    print_cases(starter_cases, visible)
    hidden = [c for c in starter_cases if visible is None or c.number > visible]

    starter_files = q.pack_files()
    try:
        with progress.step(f"Writing solution/ over the workspace ({len(solution)} files)"):
            for path, local in solution.items():
                container.write_file(path, local.read(), executable=local.executable)
        solution_cases = submit(container, session.challenge_version_id, "solution")
    finally:
        # Put the starter back whatever happened, so the container matches the pack.
        with progress.step("Putting the starter back"):
            for path in solution:
                if path in starter_files:
                    container.write_file(path, starter_files[path].read(), executable=starter_files[path].executable)
                else:
                    container.delete_file(path)
    print_cases(solution_cases, visible)

    progress.line("")
    passing_hidden = [c.number for c in hidden if c.passed]
    if not hidden:
        reason = "" if visible is not None else " (no self.RUN in the grader)"
        progress.failed(f"Starter: no hidden cases ran{reason}")
    elif passing_hidden:
        progress.failed(f"Starter passes hidden case(s) {passing_hidden}: they test nothing the starter lacks.")
    else:
        progress.done("Starter fails every hidden case.")
    failing = [c.number for c in solution_cases if not c.passed]
    if failing or not solution_cases:
        progress.failed(f"Solution fails case(s) {failing}.")
    else:
        progress.done("Solution passes every case.")
    return bool(hidden) and not passing_hidden and bool(solution_cases) and not failing


def _stop_on_grader_error(cases: list[Case], error: str | None) -> None:
    if not cases:
        raise PraxisError(
            "The grader produced no cases." + (f" Its log ends:\n{_indent(error)}" if error else
                                               " See `codepraxis logs <q> grader`.")
        )


def setup_sh_problems(q: Question) -> list[str]:
    """What output.md's setup.sh rules say is missing, before anything runs."""
    path = q.pack / "setup.sh"
    if not path.is_file():
        return []
    text = path.read_text(errors="replace")
    problems = []
    exits_on_error = re.search(r"^\s*set\s+-\w*e", text, re.M)
    if not exits_on_error or "pipefail" not in text:
        problems.append("setup.sh has no `set -euo pipefail`: a failing step would still report success.")
    return problems


# ── helpers ─────────────────────────────────────────────────────────────


def _tail(text: str, lines: int) -> str:
    return "\n".join((text or "").splitlines()[-lines:])


def _indent(text: str) -> str:
    return "\n".join(f"    {line}" for line in (text or "").splitlines())


def _one_line(value: str, limit: int = 160) -> str:
    flat = " ⏎ ".join(value.strip().splitlines())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"
