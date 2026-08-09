"""Rules about what a pack ships.

The pack directory is uploaded verbatim and mounted into a candidate's
container, so anything in it is something a candidate can read.
"""

from __future__ import annotations

from collections.abc import Iterable

from ...domain import contract
from ...domain.pack import Pack
from ...domain.results import Diagnostic, Severity

#: Build noise that should never be packaged.
_FORBIDDEN_DIRS = ("__pycache__", ".pytest_cache", ".ruff_cache", "node_modules")
_FORBIDDEN_SUFFIXES = (".pyc", ".pyo")

#: Guidance from the authoring spec: dependencies belong in setup.sh, because
#: source/ is the candidate's workspace and a requirements file there is both
#: misleading and never installed.
_DISCOURAGED_IN_SOURCE = ("requirements.txt",)


class SolutionInsidePackRule:
    """``solution/`` must be a sibling of the pack, never inside it.

    A solution directory inside the pack is uploaded with everything else, which
    hands the answer to every candidate. This is the single highest-consequence
    packaging mistake, so it is an error rather than a warning.
    """

    code = "pack.solution-inside"

    def check(self, pack: Pack) -> Iterable[Diagnostic]:
        findings: list[Diagnostic] = []
        for candidate in (pack.root / "solution", pack.source_dir / "solution"):
            if candidate.is_dir():
                findings.append(
                    Diagnostic(
                        Severity.ERROR,
                        self.code,
                        (
                            f"{candidate} is inside the pack, so it would be uploaded to candidates. "
                            f"Move it beside the pack directory instead."
                        ),
                        str(candidate),
                    )
                )
        return findings


class ForbiddenFilesRule:
    """Build artefacts and misplaced dependency files."""

    code = "pack.forbidden-files"

    def check(self, pack: Pack) -> Iterable[Diagnostic]:
        findings: list[Diagnostic] = []

        for entry in sorted(pack.root.rglob("*")):
            relative = entry.relative_to(pack.root)

            if entry.is_dir() and entry.name in _FORBIDDEN_DIRS:
                findings.append(
                    Diagnostic(
                        Severity.WARNING,
                        self.code,
                        f"{relative} would be packaged; it is build noise.",
                        str(entry),
                    )
                )
            elif entry.is_file() and entry.suffix in _FORBIDDEN_SUFFIXES:
                findings.append(
                    Diagnostic(
                        Severity.WARNING,
                        self.code,
                        f"{relative} is a compiled artefact and should not be packaged.",
                        str(entry),
                    )
                )

        for name in _DISCOURAGED_IN_SOURCE:
            candidate = pack.source_dir / name
            if candidate.is_file():
                findings.append(
                    Diagnostic(
                        Severity.WARNING,
                        self.code,
                        (
                            f"{contract.SOURCE_DIR}/{name} is never installed by the runner. "
                            f"Install dependencies from setup.sh instead."
                        ),
                        str(candidate),
                    )
                )

        return findings
