"""The static-analysis seam.

A rule reads a :class:`~codepraxis.domain.pack.Pack` and reports problems. It
must **never execute pack code** — that is what makes ``codepraxis lint``
instant and safe to run against a pack you did not write.

Anything needing a live ``testCases`` instance (``RUN``, ``RunCaseInputs``)
belongs in the executor instead; those attributes only exist once the class has
been constructed.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

try:  # pragma: no cover - typing shim for older Pythons
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing_extensions import Protocol, runtime_checkable  # type: ignore

from ..domain.results import Diagnostic

if TYPE_CHECKING:  # pragma: no cover
    from ..domain.pack import Pack


@runtime_checkable
class Rule(Protocol):
    """One static check over a pack."""

    #: Stable identifier, also used as the diagnostic code prefix.
    code: str

    def check(self, pack: Pack) -> Iterable[Diagnostic]:
        """Yield a diagnostic per problem found. Yield nothing when clean."""
