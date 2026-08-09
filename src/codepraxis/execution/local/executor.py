"""The local execution tier: run a pack's tests with nothing but Python.

Fast (sub-second for most packs) and advisory. It reproduces the runner's
loading, ordering and pass/fail semantics, but it is not the container: no
``setup.sh``, no image package set, no LLM proxy. Every such gap is emitted as
an ``UNVERIFIABLE`` diagnostic so a local pass is never mistaken for a
validation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path

from ...domain import contract
from ...domain.pack import Pack
from ...domain.results import CaseResult, CaseStatus, Diagnostic, Fixture, FixtureRun, RunResult, Severity
from ...errors import HarnessError
from . import backends, workspace

WORKER = Path(__file__).with_name("worker.py")

#: Ceiling on a whole fixture run, independent of per-case timeouts. Guards
#: against a pack that blocks somewhere SIGALRM cannot interrupt.
DEFAULT_WALL_CLOCK_SECONDS = 600

_STATUS_MAP = {
    "pass": CaseStatus.PASS,
    "fail": CaseStatus.FAIL,
    "timeout": CaseStatus.TIMEOUT,
    "error": CaseStatus.ERROR,
}


class LocalExecutor:
    """Executes packs in a subprocess on the author's machine."""

    name = "local"

    def __init__(
        self,
        python: str = sys.executable,
        wall_clock_seconds: int = DEFAULT_WALL_CLOCK_SECONDS,
        llm_base_url: str | None = None,
        llm_api_key: str | None = None,
    ) -> None:
        self._python = python
        self._wall_clock = wall_clock_seconds
        # Packs reach the model through OPENAI_BASE_URL / OPENAI_API_KEY (see the
        # authoring guide's hosted-LLM helper). Point those at a real endpoint
        # and AI packs become genuinely runnable here instead of unverifiable.
        self._llm_base_url = llm_base_url or os.environ.get("OPENAI_BASE_URL")
        self._llm_api_key = llm_api_key or os.environ.get("OPENAI_API_KEY")

    @property
    def _llm_configured(self) -> bool:
        return bool(self._llm_api_key)

    def supports(self, pack: Pack) -> bool:
        return backends.adapter_for(pack.backend.backend).locally_supported

    def execute(self, pack: Pack, fixtures: Sequence[Fixture]) -> RunResult:
        adapter = backends.adapter_for(pack.backend.backend)
        diagnostics: list[Diagnostic] = list(adapter.diagnostics())
        diagnostics.extend(self._environment_diagnostics())

        started = time.time()
        runs: list[FixtureRun] = []

        if adapter.locally_supported:
            for fixture in fixtures:
                runs.append(self._run_fixture(pack, fixture, adapter))

        return RunResult(
            pack_name=pack.name,
            executor=self.name,
            runs=tuple(runs),
            diagnostics=tuple(diagnostics),
            duration_ms=(time.time() - started) * 1000,
        )

    # -- internals ---------------------------------------------------------

    def _environment_diagnostics(self) -> list[Diagnostic]:
        """Differences between this machine and the container that change results."""
        notes = [
            Diagnostic(
                severity=Severity.UNVERIFIABLE,
                code="local.no-setup-sh",
                message=(
                    "setup.sh is not executed locally. Packages it installs, and the "
                    "import-time race against it, are only exercised by `--remote`."
                ),
            ),
            Diagnostic(
                severity=Severity.UNVERIFIABLE,
                code="local.interpreter-mismatch",
                message=(
                    f"Running Python {sys.version_info.major}.{sys.version_info.minor} on "
                    f"{sys.platform}; the runner image is linux/amd64. Packages resolved here "
                    f"may not exist there."
                ),
            ),
        ]
        if self._llm_configured:
            notes.append(
                Diagnostic(
                    severity=Severity.WARNING,
                    code="local.llm-endpoint",
                    message=(
                        f"Model calls go to {self._llm_base_url or 'the default OpenAI endpoint'}, "
                        f"not the container's proxy. Behaviour and cost may differ."
                    ),
                )
            )

        if not hasattr(__import__("signal"), "SIGALRM"):
            notes.append(
                Diagnostic(
                    severity=Severity.WARNING,
                    code="local.no-sigalrm",
                    message=(
                        "This platform has no SIGALRM, so per-case timeout_window is not "
                        "enforced locally; only the overall wall clock applies."
                    ),
                )
            )
        return notes

    def _run_fixture(self, pack: Pack, fixture: Fixture, adapter: backends.BackendAdapter) -> FixtureRun:
        try:
            with workspace.materialize(pack, fixture) as ws:
                payload = self._invoke_worker(pack, ws, adapter)
        except HarnessError as exc:
            return FixtureRun(
                fixture=fixture,
                diagnostics=(Diagnostic(Severity.ERROR, "harness.workspace", str(exc)),),
            )

        diagnostics: list[Diagnostic] = []
        if payload.get("fatal"):
            diagnostics.append(
                Diagnostic(
                    severity=Severity.ERROR,
                    code="harness.load-failed",
                    message=f"Could not load or instantiate {contract.TEST_CLASS_NAME}:\n{payload['fatal']}",
                    location=str(pack.active_test_file),
                )
            )

        diagnostics.extend(self._attribute_diagnostics(pack, payload.get("attributes") or {}))

        cases = tuple(
            CaseResult(
                name=case["name"],
                status=self._classify(case, adapter, self._llm_configured),
                expected=case.get("expected", ""),
                output=case.get("output", ""),
                duration_ms=float(case.get("duration_ms", 0.0)),
                hidden=bool(case.get("hidden")),
            )
            for case in payload.get("cases", [])
        )

        if any(case.status is CaseStatus.UNVERIFIABLE for case in cases):
            diagnostics.append(
                Diagnostic(
                    severity=Severity.UNVERIFIABLE,
                    code="local.missing-infrastructure",
                    message=(
                        "Some cases need infrastructure this machine does not have "
                        "(typically the LLM proxy). They are reported as unverifiable "
                        "rather than failed — run `codepraxis validate --remote` to judge them."
                    ),
                )
            )

        return FixtureRun(fixture=fixture, cases=cases, diagnostics=tuple(diagnostics))

    @staticmethod
    def _classify(case: dict, adapter: backends.BackendAdapter, llm_configured: bool) -> CaseStatus:
        """Map a worker result to a status, demoting infrastructure failures.

        A case that failed only because no model endpoint is reachable says
        nothing about the pack, so it is reported UNVERIFIABLE rather than FAIL.

        Once an endpoint IS configured the demotion stops: a failure then is a
        real failure, and hiding it would defeat the point of running at all.
        """
        status = _STATUS_MAP.get(case.get("status", ""), CaseStatus.ERROR)
        if status is CaseStatus.PASS or not adapter.unverifiable_markers or llm_configured:
            return status

        haystack = f"{case.get('output', '')}".lower()
        if any(marker.lower() in haystack for marker in adapter.unverifiable_markers):
            return CaseStatus.UNVERIFIABLE
        return status

    def _attribute_diagnostics(self, pack: Pack, attributes: dict) -> list[Diagnostic]:
        """Check the testCases surface the runner and candidate panel rely on."""
        collected: list[Diagnostic] = []
        location = str(pack.active_test_file)

        run_count = attributes.get("RUN")
        discovered = attributes.get("discovered") or []

        if not run_count:
            collected.append(
                Diagnostic(
                    Severity.ERROR,
                    "testcases.no-run",
                    f"{contract.TEST_CLASS_NAME}.RUN is missing or zero; the runner refuses the pack.",
                    location,
                )
            )
        elif discovered and int(run_count) > len(discovered):
            collected.append(
                Diagnostic(
                    Severity.ERROR,
                    "testcases.run-too-high",
                    f"RUN={run_count} but only {len(discovered)} test_case_* methods exist.",
                    location,
                )
            )

        inputs = attributes.get("RunCaseInputs")
        if inputs is None:
            collected.append(
                Diagnostic(
                    Severity.WARNING,
                    "panel.no-inputs",
                    "RunCaseInputs is absent; the candidate panel will show no Input row.",
                    location,
                )
            )
        elif run_count and len(inputs) != int(run_count):
            collected.append(
                Diagnostic(
                    Severity.WARNING,
                    "panel.inputs-mismatch",
                    f"RUN={run_count} but RunCaseInputs has {len(inputs)} entries; panel rows will not line up.",
                    location,
                )
            )

        padded = [name for name in discovered if _is_zero_padded(name)]
        if padded:
            collected.append(
                Diagnostic(
                    Severity.ERROR,
                    "testcases.zero-padded",
                    (
                        f"Zero-padded case names sort ambiguously in the runner: {', '.join(padded)}. "
                        f"Use test_case_1, test_case_2, …"
                    ),
                    location,
                )
            )

        return collected

    def _invoke_worker(self, pack: Pack, ws: Path, adapter: backends.BackendAdapter) -> dict:
        with tempfile.TemporaryDirectory(prefix="praxis-run-") as scratch:
            config_path = Path(scratch) / "config.json"
            results_path = Path(scratch) / "results.json"
            config_path.write_text(
                json.dumps(
                    {
                        "test_file": str(pack.active_test_file),
                        "workspace": str(ws),
                        "injected_names": list(adapter.injected_names),
                        "expected_attrs": list(contract.EXPECTED_TEST_CASE_ATTRS),
                        "limit": None,
                    }
                ),
                encoding="utf-8",
            )

            worker_env = dict(os.environ)
            if self._llm_base_url:
                worker_env["OPENAI_BASE_URL"] = self._llm_base_url
            if self._llm_api_key:
                worker_env["OPENAI_API_KEY"] = self._llm_api_key

            try:
                completed = subprocess.run(
                    [self._python, str(WORKER), str(config_path), str(results_path)],
                    cwd=str(ws.parent),
                    capture_output=True,
                    text=True,
                    timeout=self._wall_clock,
                    env=worker_env,
                )
            except subprocess.TimeoutExpired:
                return {
                    "cases": [],
                    "attributes": {},
                    "fatal": f"The pack did not finish within {self._wall_clock}s and was killed.",
                }

            if not results_path.exists():
                detail = (completed.stderr or completed.stdout or "").strip()[-2000:]
                return {
                    "cases": [],
                    "attributes": {},
                    "fatal": detail or f"Worker exited with status {completed.returncode} and wrote no results.",
                }

            return json.loads(results_path.read_text(encoding="utf-8"))


def _is_zero_padded(name: str) -> bool:
    tail = name[len(contract.TEST_CASE_PREFIX) :].lstrip("_")
    return len(tail) > 1 and tail[0] == "0" and tail.isdigit()
