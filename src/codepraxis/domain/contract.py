"""The pack execution contract, mirrored from the production runner.

Every constant here has a counterpart in the runner image. When the runner
changes, this file changes with it, and ``tests/conformance`` is what catches
the drift. Provenance is recorded per constant so the mirror can be re-checked
against the source rather than trusted.

Sources (paths relative to the ``docker-image`` repo):
  - ``setupCodeBase.py``  — pack mounting, test-file selection, workspace rsync
  - ``koro/test_loader.py`` — testCases loading, test-case discovery and ordering
  - ``koro/test_runner.py``  — per-override execution semantics
"""

from __future__ import annotations

# --- Pack layout -----------------------------------------------------------
# setupCodeBase.py mounts the pack at /praxis/codeFromServer/{foldername}/ and
# reads these paths beneath it. The leading "._" is literal; the runner does not
# tolerate renamed directories.
TESTS_DIR = "._tests"
COURSE_DATA_DIR = "._course_data"
SOURCE_DIR = "source"
METADATA_FILE = "metadata.json"
BACKEND_CONF_FILE = "backend.conf"
COURSE_TOC_FILE = "course_toc.json"

#: Files/dirs a pack must contain. Mirrors REQUIRED_PACK_FILES in
#: question-bank/tools/common.py so the CLI and the existing CI agree.
REQUIRED_PACK_PATHS = (
    METADATA_FILE,
    BACKEND_CONF_FILE,
    SOURCE_DIR,
    f"{TESTS_DIR}/test_1.py",
    f"{COURSE_DATA_DIR}/{COURSE_TOC_FILE}",
    f"{COURSE_DATA_DIR}/feature.md",
)

# --- Question layout -------------------------------------------------------
# A *question* is a wrapper directory; the *pack* is what the runner mounts.
#
#   challenges/webhook_debug/     <- the question
#     spec.md                     <- the plan, describes the whole question
#     pack/                       <- mounted by the runner
#       metadata.json, source/, ._tests/, ._course_data/, publish.json
#     solution/                   <- reference solution, never packaged
#
# The wrapper exists because the solution is resolved as the pack's sibling.
# When packs were the top-level directories, every pack under `challenges/`
# resolved to the *same* `challenges/solution`, so scaffolding a second
# question wrote into the first one's reference solution — silently, and with
# no git history in a fresh scaffold to recover from. Giving each question its
# own directory makes that collision impossible rather than merely unlikely.

#: The pack directory inside a question. Its name never reaches the container:
#: the workspace directory comes from metadata.json "name".
PACK_DIR = "pack"

#: The reference solution, a sibling of the pack inside the question directory.
SOLUTION_DIR = "solution"

# --- Authoring-side files --------------------------------------------------
# Neither of these is read by the runner. They live in version control beside
# the code they describe because the author, not the runner, needs them.

#: The plan, written before any code and approved by whoever signs the question
#: off. Also what an edit reads months later to recover the original intent.
#: Lives at the *question* level: it describes the question, not just the pack.
SPEC_FILE = "spec.md"

#: Catalog identity — challenge id, title, difficulty, time limit, tech stack.
#: Real packs in the question bank already carry this; before it was adopted
#: here the same values were passed as one-off command-line flags, which meant
#: a question's identity lived in someone's shell history.
PUBLISH_FILE = "publish.json"

# --- Workspace -------------------------------------------------------------
#: setupCodeBase.py rsyncs ``source/`` *contents* (note the trailing slash in the
#: runner's rsync) into /home/praxis/{foldername}/ — a flat copy, not a nested
#: ``source`` directory. ``foldername`` comes from metadata.json's "name".
CONTAINER_USER = "praxis"
CONTAINER_WORKSPACE_TEMPLATE = "/home/{user}/{foldername}"

# --- Runner environment ----------------------------------------------------
#: codingenv/Dockerfile — ``FROM nvidia/cuda:11.8.0-base-ubuntu22.04``, and
#: Ubuntu 22.04's ``python3`` is 3.10.
#:
#: Worth stating as a constant rather than prose: authors on a newer
#: interpreter write code that passes locally and fails on the runner, and the
#: difference is often semantic rather than syntactic — ``Union[X, X]``
#: collapses on 3.12+ and raises TypeError on 3.10 — so nothing static catches
#: it. The local harness compares against this to decide how loudly to warn.
RUNNER_PYTHON = (3, 10)

# --- testCases contract ----------------------------------------------------
#: koro/test_loader.py:87 — ``getattr(test_module, 'testCases')(question_folder)``.
#: Exactly one argument after ``self``: the workspace path.
TEST_CLASS_NAME = "testCases"

#: koro/test_loader.py:18 — checked only in developer mode, but authors should
#: satisfy all of them; a missing attribute here is a warning, not a hard error.
EXPECTED_TEST_CASE_ATTRS = (
    "RUN",
    "RunCaseInputs",
    "exe",
    "userWxpace",
    "default_timeout_window",
    "msg",
)

#: koro/test_loader.py:115 — discovery is ``name.startswith('test_case')``,
#: not a regex match, so ``test_caseFoo`` would also be collected.
TEST_CASE_PREFIX = "test_case"

#: koro/test_loader.py:130 — ordering key is ``int(re.search(r'\d+', name).group())``:
#: the FIRST run of digits anywhere in the method name. This is why zero-padded
#: names collide (``test_case_01`` and ``test_case_1`` both sort as 1) and why
#: the authoring guide forbids them.
TEST_CASE_ORDER_PATTERN = r"\d+"

#: koro/test_loader.py:84 — the runner injects ``execute_bin`` into the test
#: module's namespace before instantiation. Tests may reference it at module
#: scope, so the harness must provide a binding or import fails.
INJECTED_EXECUTE_BIN = "execute_bin"

#: setupCodeBase.py:~225 — for EMB and LINUX question types the runner injects a
#: dummy ``cmd`` handler as well.
INJECTED_CMD = "cmd"

# --- Execution semantics ---------------------------------------------------
#: koro/test_runner.py:151 — ``timeout_secs = timeout / 1000.0``. Both
#: ``default_timeout_window`` and a case's ``timeout_window`` default are in
#: MILLISECONDS.
TIMEOUT_UNIT_MS = True

#: koro/test_runner.py:227 — a case passes if and only if ``self.msg == "PASS"``
#: after the method returns. The return value never decides pass/fail.
PASS_SENTINEL = "PASS"

#: koro/test_runner.py:206 — ``._bad_input`` anywhere in ``str(result)`` forces
#: a failure regardless of ``msg``.
BAD_INPUT_SENTINEL = "._bad_input"

#: koro/test_runner.py:220 — override 1 reads the returned tuple as
#: ``(panel_text, success_message)`` and reports them as (expected, output).
OVERRIDE_DEFAULT = 1
