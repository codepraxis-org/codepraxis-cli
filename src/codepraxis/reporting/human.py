"""Terminal output for humans.

Optimised for the inner loop: the verdict and the reason a case failed should
be legible without scrolling.
"""

from __future__ import annotations

import os
import sys
from typing import IO

from ..domain.results import CaseStatus, Fixture, FixtureRun, RunResult, Severity

_FIXTURE_LABEL = {
    Fixture.STARTER: "starter",
    Fixture.SOLUTION: "solution",
}

_STATUS_MARK = {
    CaseStatus.PASS: "ok",
    CaseStatus.FAIL: "FAIL",
    CaseStatus.TIMEOUT: "TIMEOUT",
    CaseStatus.ERROR: "ERROR",
}


class _Style:
    """ANSI styling that disables itself when output is not a terminal."""

    def __init__(self, stream: IO[str]) -> None:
        self.enabled = (
            hasattr(stream, "isatty")
            and stream.isatty()
            and os.environ.get("NO_COLOR") is None
            and os.environ.get("TERM") != "dumb"
        )

    def _wrap(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def good(self, text: str) -> str:
        return self._wrap(text, "32")

    def bad(self, text: str) -> str:
        return self._wrap(text, "31")

    def warn(self, text: str) -> str:
        return self._wrap(text, "33")

    def dim(self, text: str) -> str:
        return self._wrap(text, "2")

    def bold(self, text: str) -> str:
        return self._wrap(text, "1")


class HumanReporter:
    """Writes a readable summary to a stream."""

    def __init__(self, stream: IO[str] = sys.stdout, verbose: bool = False) -> None:
        self._out = stream
        self._style = _Style(stream)
        self._verbose = verbose

    def report(self, result: RunResult) -> None:
        style = self._style
        self._line(style.bold(f"{result.pack_name}") + style.dim(f"  ({result.executor})"))

        for run in result.runs:
            self._report_fixture(run)

        self._report_diagnostics(result)
        self._report_verdict(result)

    # -- sections ----------------------------------------------------------

    def _report_fixture(self, run: FixtureRun) -> None:
        style = self._style
        label = _FIXTURE_LABEL.get(run.fixture, run.fixture.value)
        total = len(run.cases)
        passed = run.passed_count

        expectation_met = not run.all_passed if run.fixture is Fixture.STARTER else run.all_passed
        headline = f"{label:<9} {passed}/{total} passed"
        self._line("  " + (style.good(headline) if expectation_met else style.bad(headline)))

        for case in run.cases:
            failed = case.status is not CaseStatus.PASS
            if not failed and not self._verbose:
                continue
            mark = _STATUS_MARK[case.status]
            tag = style.dim(" (hidden)") if case.hidden else ""
            marker = style.good(mark) if not failed else style.bad(mark)
            self._line(f"    {marker:<12} {case.name}{tag}")
            if failed and case.output:
                for text_line in str(case.output).strip().splitlines()[:6]:
                    self._line(style.dim(f"      {text_line}"))

        for diagnostic in run.diagnostics:
            self._diagnostic(diagnostic, indent="    ")

    def _report_diagnostics(self, result: RunResult) -> None:
        for diagnostic in result.diagnostics:
            if diagnostic.severity is Severity.UNVERIFIABLE and not self._verbose:
                continue
            self._diagnostic(diagnostic, indent="  ")

        skipped = sum(
            1
            for diagnostic in result.diagnostics
            if diagnostic.severity is Severity.UNVERIFIABLE
        )
        if skipped and not self._verbose:
            self._line(
                self._style.dim(
                    f"  {skipped} thing(s) this tier cannot verify — re-run with -v, "
                    f"or use `codepraxis validate --remote`"
                )
            )

    def _report_verdict(self, result: RunResult) -> None:
        style = self._style
        seconds = result.duration_ms / 1000.0

        starter = result.run_for(Fixture.STARTER)
        if starter is not None and starter.all_passed:
            self._line(
                style.bad("  FAILED")
                + " the starter passes every test, so the tests do not discriminate"
            )
            self._line(style.dim(f"  {seconds:.1f}s"))
            return

        if result.ok:
            self._line(style.good("  PASSED") + style.dim(f"  {seconds:.1f}s"))
        else:
            self._line(style.bad("  FAILED") + style.dim(f"  {seconds:.1f}s"))

    # -- helpers -----------------------------------------------------------

    def _diagnostic(self, diagnostic, indent: str) -> None:
        style = self._style
        prefix = {
            Severity.ERROR: style.bad("error"),
            Severity.WARNING: style.warn("warn "),
            Severity.UNVERIFIABLE: style.dim("note "),
        }[diagnostic.severity]
        self._line(f"{indent}{prefix} {diagnostic.message}")

    def _line(self, text: str) -> None:
        self._out.write(text + "\n")
