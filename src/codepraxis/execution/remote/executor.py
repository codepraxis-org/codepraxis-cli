"""The remote execution tier: validate a pack in the real runner.

This is the authoritative tier. It runs the pack in the production runner image
on CodePraxis infrastructure, so it exercises everything the local harness
cannot — ``setup.sh``, the image's package set, the LLM proxy, real container
CPU and memory, and the packaged zip layout.

Only a passing remote run permits publishing, and the run id it returns is what
``codepraxis ship`` presents as evidence.
"""

from __future__ import annotations

import sys
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

#: How often to print a progress line. Polling is every 3s, but saying so that
#: often is noise; this is slow enough to stay readable and fast enough that a
#: stalled run is obvious.
PROGRESS_INTERVAL_SECONDS = 15

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
        quiet: bool = False,
    ) -> None:
        self._client = client
        self._timeout = timeout_seconds
        self._quiet = quiet
        #: Set after a run so `publish` can cite the validation it relied on.
        self.last_run_id: str | None = None

    def supports(self, pack: Pack) -> bool:
        # The real runner supports every backend; that is the point of this tier.
        return True

    def execute(self, pack: Pack, fixtures: Sequence[Fixture]) -> RunResult:
        client = self._client or ApiClient(RemoteConfig.resolve())
        started = time.time()

        self._say(f"Uploading {pack.name} to the runner…")
        run_id = self.submit(client, pack)
        # Printed before any waiting: without it there is nothing to quote when
        # a run has to be chased on the dashboard, and nothing to prove the
        # upload even landed.
        self._say(f"Validation run {run_id}")
        self._say(
            f"Running in the real image. Typically about a minute; "
            f"gives up after {self._timeout // 60} minutes."
        )

        payload = self.await_result(client, run_id)

        return self._to_result(pack, payload, (time.time() - started) * 1000)

    def _say(self, message: str) -> None:
        """Progress to stderr, flushed.

        stderr because stdout may be a machine-readable report — `--json` has to
        stay parseable. Flushed because Python block-buffers a pipe, so
        `ship | tail` showed nothing at all until the process exited: fifteen
        minutes indistinguishable from a hang.
        """
        if self._quiet:
            return
        print(message, file=sys.stderr, flush=True)

    # -- steps -------------------------------------------------------------

    def submit(self, client: ApiClient, pack: Pack) -> str:
        # The bundle carries the reference solution alongside the pack so the
        # server can run both fixtures; the solution never reaches a
        # candidate-facing artifact.
        bundle = build_validation_bundle(pack)
        payload = client.post_bytes("/validation-runs", bundle)
        run_id = payload.get("validation_run_id")
        if not run_id:
            raise PraxisError("The platform accepted the pack but returned no validation_run_id")
        self.last_run_id = str(run_id)
        return self.last_run_id

    def await_result(self, client: ApiClient, run_id: str) -> dict:
        started = time.time()
        deadline = started + self._timeout
        last_note = ""
        next_tick = started + PROGRESS_INTERVAL_SECONDS

        while time.time() < deadline:
            payload = client.get(f"/validation-runs/{run_id}")
            status = str(payload.get("status", "")).lower()
            if status in _TERMINAL:
                self._say(f"  {int(time.time() - started)}s  {status}")
                return payload

            # Report the stage when the server tells us one, and otherwise tick
            # so a long wait is visibly progress rather than a hang.
            note = str(payload.get("stage") or status or "waiting")
            now = time.time()
            if note != last_note or now >= next_tick:
                self._say(f"  {int(now - started)}s  {note}")
                last_note = note
                next_tick = now + PROGRESS_INTERVAL_SECONDS

            time.sleep(POLL_INTERVAL_SECONDS)

        raise PraxisError(
            f"Validation run {run_id} did not finish within {self._timeout}s. "
            f"It may still be running — check the dashboard, or query it with "
            f"that run id."
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
