"""Rules over the ``testCases`` class, checked by parsing rather than running.

Both of these catch bugs that otherwise only surface inside a container, minutes
later, as an error that does not name its cause.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable

from ...domain import contract
from ...domain.pack import Pack
from ...domain.results import Diagnostic, Severity

#: koro orders cases by the first run of digits in the method name.
_FIRST_NUMBER = re.compile(r"\d+")


def _parse(pack: Pack) -> ast.Module | None:
    try:
        return ast.parse(pack.active_test_file.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        # A file that will not parse is reported by the executor with a real
        # traceback; duplicating that here would only add noise.
        return None


def _test_class(tree: ast.Module) -> ast.ClassDef | None:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == contract.TEST_CLASS_NAME:
            return node
    return None


class ConstructorArityRule:
    """``testCases.__init__`` must take exactly one argument after ``self``.

    The runner calls ``testCases(workspace_path)``. A two-argument constructor
    fails at import time with ``missing 1 required positional argument`` — a
    message that names the parameter, not the mistake. Parsing catches it before
    a container is ever allocated.
    """

    code = "testcases.constructor-arity"

    def check(self, pack: Pack) -> Iterable[Diagnostic]:
        tree = _parse(pack)
        if tree is None:
            return []

        klass = _test_class(tree)
        if klass is None:
            return [
                Diagnostic(
                    Severity.ERROR,
                    "testcases.missing-class",
                    f"No class named {contract.TEST_CLASS_NAME!r} in this file; "
                    f"the runner looks for exactly that name.",
                    str(pack.active_test_file),
                )
            ]

        for node in klass.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != "__init__":
                continue

            positional = [arg.arg for arg in node.args.args]
            # self + the workspace path.
            if len(positional) == 2:
                return []

            names = ", ".join(positional[1:]) or "(none)"
            return [
                Diagnostic(
                    Severity.ERROR,
                    self.code,
                    (
                        f"__init__ takes {len(positional) - 1} argument(s) after self ({names}); "
                        f"the runner calls {contract.TEST_CLASS_NAME}(workspace_path) with exactly one."
                    ),
                    f"{pack.active_test_file}:{node.lineno}",
                )
            ]

        return [
            Diagnostic(
                Severity.ERROR,
                "testcases.no-init",
                f"{contract.TEST_CLASS_NAME} defines no __init__; it must accept the workspace path.",
                str(pack.active_test_file),
            )
        ]


class TestCaseNamingRule:
    """Case names must sort unambiguously and there must be at least one.

    Ordering uses the first run of digits anywhere in the name, so
    ``test_case_01`` and ``test_case_1`` both sort as 1 and their relative order
    is undefined.
    """

    code = "testcases.naming"

    def check(self, pack: Pack) -> Iterable[Diagnostic]:
        tree = _parse(pack)
        if tree is None:
            return []

        klass = _test_class(tree)
        if klass is None:
            return []

        findings: list[Diagnostic] = []
        names: list[str] = []

        for node in klass.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith(contract.TEST_CASE_PREFIX):
                continue
            names.append(node.name)

            suffix = node.name[len(contract.TEST_CASE_PREFIX) :].lstrip("_")
            if len(suffix) > 1 and suffix[0] == "0" and suffix.isdigit():
                findings.append(
                    Diagnostic(
                        Severity.ERROR,
                        self.code,
                        (
                            f"{node.name} is zero-padded, so it sorts ambiguously against "
                            f"test_case_{int(suffix)}. Use unpadded integers."
                        ),
                        f"{pack.active_test_file}:{node.lineno}",
                    )
                )
            elif not _FIRST_NUMBER.search(node.name):
                findings.append(
                    Diagnostic(
                        Severity.ERROR,
                        self.code,
                        f"{node.name} has no number, so the runner cannot order it.",
                        f"{pack.active_test_file}:{node.lineno}",
                    )
                )

        if not names:
            findings.append(
                Diagnostic(
                    Severity.ERROR,
                    "testcases.no-cases",
                    f"No {contract.TEST_CASE_PREFIX}* methods found; the pack would grade nothing.",
                    str(pack.active_test_file),
                )
            )

        ordinals = [int(_FIRST_NUMBER.search(name).group()) for name in names if _FIRST_NUMBER.search(name)]
        duplicates = sorted({value for value in ordinals if ordinals.count(value) > 1})
        if duplicates:
            findings.append(
                Diagnostic(
                    Severity.ERROR,
                    self.code,
                    f"Multiple cases share the ordinal(s) {duplicates}; their execution order is undefined.",
                    str(pack.active_test_file),
                )
            )

        return findings
