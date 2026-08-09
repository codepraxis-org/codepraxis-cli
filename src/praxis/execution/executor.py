"""The execution seam.

Every tier — local in-process harness, the hosted validation service, a local
Docker runner — implements :class:`Executor` and returns the same
:class:`~praxis.domain.results.RunResult`. Commands and reporters depend on this
protocol, never on a concrete executor, so adding a tier touches no existing
call site.
"""

from __future__ import annotations

from typing import Sequence

try:  # pragma: no cover - typing shim for Python 3.7
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing_extensions import Protocol, runtime_checkable  # type: ignore

from ..domain.pack import Pack
from ..domain.results import Fixture, RunResult


@runtime_checkable
class Executor(Protocol):
    """Runs a pack's tests and reports what happened."""

    #: Stable identifier recorded on the result: "local", "remote", "docker".
    name: str

    def supports(self, pack: Pack) -> bool:
        """Whether this executor can faithfully run ``pack``.

        Returning ``False`` is how a tier declines work it would otherwise
        report misleading results for — the local harness cannot emulate a QEMU
        target, so it says so instead of failing every case.
        """

    def execute(self, pack: Pack, fixtures: Sequence[Fixture]) -> RunResult:
        """Run ``pack`` against each fixture and return a combined result."""
