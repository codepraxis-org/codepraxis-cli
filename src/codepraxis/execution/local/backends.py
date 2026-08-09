"""Per-``BACKEND`` behaviour for the local harness.

``backend.conf``'s ``BACKEND`` decides what the runner sets up around the tests.
The local harness can reproduce some of that and not the rest; each adapter
states which, so an unsupported pack produces an honest diagnostic instead of a
wall of spurious failures.

Adding a backend means adding an adapter and registering it — no existing
branch gets edited.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ...domain import contract
from ...domain.results import Diagnostic, Severity


@dataclass(frozen=True)
class BackendAdapter:
    """How the local harness treats one ``BACKEND`` value."""

    key: str
    #: Names injected into the test module before it is executed, mirroring the
    #: runner. Missing an injection turns into an ImportError at module scope.
    injected_names: tuple[str, ...] = (contract.INJECTED_EXECUTE_BIN,)
    #: False when the backend needs container-only infrastructure.
    locally_supported: bool = True
    #: Explains the gap when ``locally_supported`` is False.
    unsupported_reason: str = ""
    #: Things this backend depends on that the local tier cannot observe.
    unverifiable: tuple[str, ...] = ()
    #: Substrings in a failing case's output that mean "this machine lacks the
    #: infrastructure", not "the pack is wrong". Matched case-insensitively.
    #: Such cases are reported UNVERIFIABLE so an author is not sent chasing a
    #: bug that only exists off-platform.
    unverifiable_markers: tuple[str, ...] = ()

    def diagnostics(self) -> Sequence[Diagnostic]:
        collected = []
        if not self.locally_supported:
            collected.append(
                Diagnostic(
                    severity=Severity.ERROR,
                    code="backend.unsupported-locally",
                    message=(
                        f"BACKEND={self.key} cannot run in the local harness: {self.unsupported_reason}. "
                        f"Use `codepraxis validate --remote`."
                    ),
                )
            )
        for note in self.unverifiable:
            collected.append(
                Diagnostic(
                    severity=Severity.UNVERIFIABLE,
                    code="backend.unverifiable",
                    message=note,
                )
            )
        return collected


AI = BackendAdapter(
    key="AI",
    unverifiable=(
        "The hosted LLM proxy at http://localhost:1010/v1 is not running locally; "
        "cases that call it will behave differently in the container.",
    ),
    unverifiable_markers=(
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "localhost:1010",
        "127.0.0.1:1010",
        "connection refused",
        "failed to establish a new connection",
        "max retries exceeded",
        "llm request failed",
    ),
)

DSA = BackendAdapter(key="DSA")

EMB = BackendAdapter(
    key="EMB",
    injected_names=(contract.INJECTED_EXECUTE_BIN, contract.INJECTED_CMD),
    locally_supported=False,
    unsupported_reason="it requires the renode/QEMU monitor started by the runner",
)

LNX = BackendAdapter(
    key="LNX",
    injected_names=(contract.INJECTED_EXECUTE_BIN, contract.INJECTED_CMD),
    locally_supported=False,
    unsupported_reason="it requires the QEMU Linux target started by the runner",
)

#: Unknown backends are executed with the default injections rather than
#: refused, so a newly added runner backend degrades to "try it" instead of
#: blocking the author on a CLI upgrade.
_FALLBACK = BackendAdapter(
    key="",
    unverifiable=("Unrecognised BACKEND; local execution is best-effort.",),
)

_REGISTRY: dict[str, BackendAdapter] = {adapter.key: adapter for adapter in (AI, DSA, EMB, LNX)}


def adapter_for(backend: str) -> BackendAdapter:
    key = (backend or "").strip().upper()
    found = _REGISTRY.get(key)
    if found is not None:
        return found
    return BackendAdapter(
        key=key,
        injected_names=_FALLBACK.injected_names,
        unverifiable=_FALLBACK.unverifiable,
    )


def register(adapter: BackendAdapter) -> None:
    """Register a backend adapter, replacing any existing one with the same key."""
    _REGISTRY[adapter.key.strip().upper()] = adapter
