"""Output seam.

Commands hand a :class:`~praxis.domain.results.RunResult` to a reporter and
never format anything themselves, so adding JUnit or SARIF output is a new
class rather than an edit to command code.
"""

from __future__ import annotations

try:  # pragma: no cover - typing shim for Python 3.7
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing_extensions import Protocol, runtime_checkable  # type: ignore

from ..domain.results import RunResult


@runtime_checkable
class Reporter(Protocol):
    """Renders a run result to some destination."""

    def report(self, result: RunResult) -> None:
        ...
