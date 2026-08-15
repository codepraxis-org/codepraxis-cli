"""Result types shared by every executor.

``LocalExecutor`` and ``RemoteExecutor`` both produce a :class:`RunResult`, so
reporting, exit codes and CI integration are written once and stay identical
across execution tiers.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass, field


class Severity(enum.Enum):
    """How much weight a diagnostic carries."""

    ERROR = "error"
    WARNING = "warning"
    #: Something this tier structurally cannot check — e.g. the local tier
    #: cannot observe ``setup.sh`` or the container's package set. Reported so
    #: authors never mistake a local pass for a full validation.
    UNVERIFIABLE = "unverifiable"


class CaseStatus(enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    TIMEOUT = "timeout"
    ERROR = "error"
    #: The case could not be judged here — it needs infrastructure this tier
    #: does not have (the LLM proxy, a package installed by setup.sh). Counting
    #: it as a failure would send authors chasing a bug that does not exist.
    UNVERIFIABLE = "unverifiable"


class Fixture(enum.Enum):
    """Which code is under test in the workspace."""

    #: Only ``source/`` — the candidate's starting point. Expected to FAIL;
    #: a starter that passes means the tests do not discriminate.
    STARTER = "starter"
    #: ``source/`` overlaid with ``solution/`` — expected to PASS.
    SOLUTION = "solution"
    #: ``source/`` overlaid with ``.attempt/`` — someone's try at the question,
    #: used to measure how far a model gets from the brief alone.
    #:
    #: Deliberately has no expectation. STARTER failing and SOLUTION passing are
    #: correctness checks; this is a measurement, and any score it produces is
    #: information rather than a verdict.
    ATTEMPT = "attempt"


@dataclass(frozen=True)
class Diagnostic:
    severity: Severity
    code: str
    message: str
    location: str | None = None

    def __str__(self) -> str:
        where = f" ({self.location})" if self.location else ""
        return f"[{self.code}] {self.message}{where}"


@dataclass(frozen=True)
class CaseResult:
    """One ``test_case_*`` invocation."""

    name: str
    status: CaseStatus
    #: koro reports the returned tuple's first element as ``expected``.
    expected: str = ""
    #: On pass, the tuple's second element; on fail, ``self.msg``.
    output: str = ""
    duration_ms: float = 0.0
    #: True when the case sits beyond ``RUN`` — executed for author feedback
    #: but not shown in the candidate panel.
    hidden: bool = False

    @property
    def passed(self) -> bool:
        return self.status is CaseStatus.PASS


@dataclass(frozen=True)
class FixtureRun:
    """All cases executed against one fixture."""

    fixture: Fixture
    cases: Sequence[CaseResult] = field(default_factory=tuple)
    diagnostics: Sequence[Diagnostic] = field(default_factory=tuple)

    @property
    def visible(self) -> list[CaseResult]:
        return [case for case in self.cases if not case.hidden]

    @property
    def passed_count(self) -> int:
        return sum(1 for case in self.cases if case.passed)

    @property
    def all_passed(self) -> bool:
        return bool(self.cases) and all(case.passed for case in self.cases)

    @property
    def any_passed(self) -> bool:
        return any(case.passed for case in self.cases)

    @property
    def unverifiable(self) -> list:
        return [case for case in self.cases if case.status is CaseStatus.UNVERIFIABLE]


@dataclass(frozen=True)
class RunResult:
    """The outcome of running a pack, from any executor."""

    pack_name: str
    #: Identifies the tier that produced this: "local", "remote".
    executor: str
    runs: Sequence[FixtureRun] = field(default_factory=tuple)
    diagnostics: Sequence[Diagnostic] = field(default_factory=tuple)
    duration_ms: float = 0.0

    def run_for(self, fixture: Fixture) -> FixtureRun | None:
        for run in self.runs:
            if run.fixture is fixture:
                return run
        return None

    @property
    def errors(self) -> list[Diagnostic]:
        collected = [d for d in self.diagnostics if d.severity is Severity.ERROR]
        for run in self.runs:
            collected.extend(d for d in run.diagnostics if d.severity is Severity.ERROR)
        return collected

    @property
    def inconclusive(self) -> bool:
        """At least one case needed infrastructure this tier does not have.

        An inconclusive run is neither a pass nor a failure: it says nothing
        about the pack, only about where it ran. Callers must not treat it as a
        failure, or a perfectly good pack looks broken on the author's laptop.
        """
        return any(run.unverifiable for run in self.runs)

    @property
    def ok(self) -> bool:
        """The pack is sound: the solution passes, the starter does not.

        The starter check is what proves the tests discriminate. A pack whose
        starter already passes will score every candidate full marks.
        """
        if self.errors:
            return False

        solution = self.run_for(Fixture.SOLUTION)
        if solution is not None and not solution.all_passed:
            return False

        starter = self.run_for(Fixture.STARTER)
        if starter is not None and starter.all_passed:
            return False

        return solution is not None or starter is not None
