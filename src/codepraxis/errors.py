"""Error types surfaced to the CLI."""

from __future__ import annotations


class PraxisError(RuntimeError):
    """Base class for errors that should print as a clean message, not a traceback."""


class PackError(PraxisError):
    """The pack on disk is malformed or incomplete."""


class HarnessError(PraxisError):
    """The harness could not load or execute the pack's tests."""
