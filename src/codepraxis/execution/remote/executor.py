"""The remote execution tier: validate a pack in the real runner.

This is the authoritative tier. It runs the pack in the production runner image
on CodePraxis infrastructure, so it exercises everything the local harness
cannot — ``setup.sh``, the image's package set, the LLM proxy, real container
CPU and memory, and the packaged zip layout.

Only a passing remote run permits publishing, and the run id it returns is what
``codepraxis --publish`` presents as evidence.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from ...domain.pack import Pack
from ...domain.results import (
    CaseResult,
    CaseStatus,
    Diagnostic,
    Fixture,
    FixtureRun,
    RunResult,
    Severity,
)
from ...errors import PraxisError
from ...packio.archive import build_validation_bundle
from .client import ApiClient
from .config import RemoteConfig

POLL_INTERVAL_SECONDS = 3
DEFAULT_TIMEOUT_SECONDS = 900

_TERMINAL = frozenset({"passed", "failed", "error"})

_STATUS_MAP = {
    "pass": CaseStatus.PASS,
    "fail": CaseStatus.FAIL,
    "timeout": CaseStatus.TIMEOUT,
    "error": CaseStatus.ERROR,
}

_SEVERITY_MAP = {
    "error": Severity.ERROR,
    "warning": Severity.WARNING,
    "unverifiable": Severity.UNVERIFIABLE,
}


class RemoteExecutor:
    """Submits a pack to the platform and waits for the verdict."""

    name = "remote"

    def __init__(
        self,
        client: ApiClient | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._client = client
        self._timeout = timeout_seconds
        #: Set after a run so `publish` can cite the validation it relied on.
        self.last_run_id: str | None = None

    def supports(self, pack: Pack) -> bool:
        # The real runner supports every backend; that is the point of this tier.
        return True

    def execute(self, pack: Pack, fixtures: Sequence[Fixture]) -> RunResult:
        client = self._client or ApiClient(RemoteConfig.resolve())
        started = time.time()

        run_id = self.submit(client, pack)
        payload = self.await_result(client, run_id)

        return self._to_result(pack, payload, (time.time() - started) * 1000)

    # -- steps -------------------------------------------------------------

    def submit(self, client: ApiClient, pack: Pack) -> str:
        # The bundle carries the reference solution alongside the pack so the
        # server can run both fixtures; the solution never reaches a
        # candidate-facing artifact.
        bundle = build_validation_bundle(pack)
        payload = client.post_bytes("/v1/validation-runs", bundle)
        run_id = payload.get("validation_run_id")
        if not run_id:
            raise PraxisError("The platform accepted the pack but returned no validation_run_id")
        self.last_run_id = str(run_id)
        return self.last_run_id

    def await_result(self, client: ApiClient, run_id: str) -> dict:
        deadline = time.time() + self._timeout
        while time.time() < deadline:
            payload = client.get(f"/v1/validation-runs/{run_id}")
            if str(payload.get("status", "")).lower() in _TERMINAL:
                return payload
            time.sleep(POLL_INTERVAL_SECONDS)
        raise PraxisError(
            f"Validation run {run_id} did not finish within {self._timeout}s. "
            f"It may still be running; check the dashboard."
        )

    # -- parsing -----------------------------------------------------------

    def _to_result(self, pack: Pack, payload: dict, duration_ms: float) -> RunResult:
        result = payload.get("result") or {}

        runs = []
        for entry in result.get("fixtures", []):
            try:
                fixture = Fixture(entry.get("fixture", ""))
            except ValueError:
                continue
            runs.append(
                FixtureRun(
                    fixture=fixture,
                    cases=tuple(
                        CaseResult(
                            name=case.get("name", "?"),
                            status=_STATUS_MAP.get(case.get("status", ""), CaseStatus.ERROR),
                            expected=case.get("expected", ""),
                            output=case.get("output", ""),
                            duration_ms=float(case.get("duration_ms", 0.0)),
                            hidden=bool(case.get("hidden")),
                        )
                        for case in entry.get("cases", [])
                    ),
                    diagnostics=tuple(_diagnostics(entry.get("diagnostics", []))),
                )
            )

        return RunResult(
            pack_name=pack.name,
            executor=self.name,
            runs=tuple(runs),
            diagnostics=tuple(_diagnostics(result.get("diagnostics", []))),
            duration_ms=duration_ms,
        )


def _diagnostics(raw: Sequence[dict]) -> list[Diagnostic]:
    return [
        Diagnostic(
            severity=_SEVERITY_MAP.get(item.get("severity", ""), Severity.WARNING),
            code=item.get("code", "remote"),
            message=item.get("message", ""),
            location=item.get("location"),
        )
        for item in raw
    ]
