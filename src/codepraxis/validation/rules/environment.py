"""Rules about the runner environment a test file will actually meet.

These catch assumptions that hold on the author's machine and break in the
container. Each one costs nothing to check statically and would otherwise cost
a 60-second remote round trip to discover.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterable

from ...domain.pack import Pack
from ...domain.results import Diagnostic, Severity


def _third_party_imports(tree: ast.AST) -> set[str]:
    """Top-level modules imported here that are not in the standard library.

    ``sys.stdlib_module_names`` arrived in 3.10. Below that the set is unknown
    and the honest answer is to report nothing rather than guess and produce a
    warning that depends on which interpreter the author happens to run.
    """
    stdlib = getattr(sys, "stdlib_module_names", None)
    if stdlib is None:
        return set()

    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            # A relative import is the pack's own code, not a dependency.
            names = [node.module] if node.module and node.level == 0 else []
        else:
            continue

        for name in names:
            root = name.split(".")[0]
            if root and root not in stdlib and not root.startswith("_"):
                found.add(root)
    return found


def _parse(pack: Pack) -> ast.AST | None:
    path = pack.active_test_file
    if not path.is_file():
        return None
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"), str(path))
    except SyntaxError:
        # Reported by the rules that own syntax; nothing to add here.
        return None


class SubprocessInterpreterRule:
    """Spawning Python inside a test lands in a different environment.

    The runner has two. The interpreter that imports the test module carries
    ``typing_extensions``, ``redis`` and whatever ``setup.sh`` installed. A
    subprocess started from ``sys.executable`` — or from a bare ``python3`` —
    gets ``/usr/lib/python3.10`` with none of it. The same case can therefore
    pass written in-process and fail written as a subprocess, on an import error
    naming a package the author can see installed.

    **Only fires when the pack uses third-party packages at all.** Spawning the
    candidate's program is the normal way to test a command-line question, and
    is exactly what ``codepraxis new`` generates — warning on it unconditionally
    would put a diagnostic on every scaffolded pack and teach authors to skip
    lint. A third-party import in the test file is the signal that this question
    depends on things ``setup.sh`` installed, which is precisely when the split
    matters.
    """

    code = "env.subprocess-interpreter"

    def check(self, pack: Pack) -> Iterable[Diagnostic]:
        tree = _parse(pack)
        if tree is None:
            return []

        third_party = _third_party_imports(tree)
        if not third_party:
            return []

        findings: list[Diagnostic] = []
        seen_lines: set[int] = set()
        named = ", ".join(sorted(third_party)[:3])

        for node in ast.walk(tree):
            line = getattr(node, "lineno", None)
            if line is None or line in seen_lines:
                continue

            hit = self._describe(node)
            if hit is None:
                continue

            seen_lines.add(line)
            findings.append(
                Diagnostic(
                    Severity.WARNING,
                    self.code,
                    (
                        f"{hit} starts a second Python that does not share this one's "
                        f"packages — it gets a bare /usr/lib/python3.10. This pack "
                        f"imports {named}, so if the spawned code needs any of that it "
                        f"will fail in the container only. Prefer importing the "
                        f"candidate's module directly."
                    ),
                    f"{pack.active_test_file}:{line}",
                )
            )

        return findings

    @staticmethod
    def _describe(node: ast.AST) -> str | None:
        # sys.executable
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "executable"
            and isinstance(node.value, ast.Name)
            and node.value.id == "sys"
        ):
            return "sys.executable"

        # A literal "python"/"python3" as the command of a spawn.
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            first = node.value.strip().split()
            if first and first[0] in {"python", "python3", "python3.10"}:
                return f'"{node.value[:40]}"'

        return None
