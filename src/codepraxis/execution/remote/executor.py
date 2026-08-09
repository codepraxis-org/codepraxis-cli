"""The remote execution tier: validate a pack in the real runner.

This is the authoritative tier. It runs the pack in the production runner image
on CodePraxis infrastructure, so it exercises everything the local harness
cannot — ``setup.sh``, the image's package set, the LLM proxy, real container
CPU and memory, and the packaged zip layout. Only a passing remote run permits
publishing.

.. note::
   The wire contract below is **provisional** and is the specification the
   platform endpoint is being built against. Until the server implements it,
   this executor fails with a clear message rather than a stack trace.

Contract:

  ``POST {api}/v1/validation-runs``    multipart: the packed pack zip
      -> 202 ``{"validation_run_id": "...", "status": "queued"}``
  ``GET  {api}/v1/validation-runs/{id}``
      -> 200 ``{"status": "queued|running|passed|failed", "result": {...}}``

``result`` uses the same shape as ``codepraxis validate --local --json``, so a
single parser serves both tiers.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Sequence

from ... import __version__
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
        config: RemoteConfig | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._config = config
        self._timeout = timeout_seconds

    def supports(self, pack: Pack) -> bool:
        # The real runner supports every backend; that is the point of this tier.
        return True

    def execute(self, pack: Pack, fixtures: Sequence[Fixture]) -> RunResult:
        config = self._config or RemoteConfig.resolve()
        started = time.time()

        run_id = self._submit(config, pack)
        payload = self._await_result(config, run_id)

        return self._to_result(pack, payload, (time.time() - started) * 1000)

    # -- wire --------------------------------------------------------------

    def _headers(self, config: RemoteConfig) -> dict:
        return {
            "Authorization": f"Bearer {config.token}",
            # Lets the server reject or warn on a CLI too old for the current
            # pack contract, instead of failing somewhere obscure.
            "X-Praxis-CLI-Version": __version__,
        }

    def _request(self, config: RemoteConfig, method: str, path: str, body: bytes | None = None) -> dict:
        url = f"{config.api_url}{path}"
        request = urllib.request.Request(url, data=body, method=method, headers=self._headers(config))
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            if exc.code == 401:
                raise PraxisError("Authentication failed. Run `codepraxis login` again.") from exc
            if exc.code == 403:
                raise PraxisError(
                    "This API key lacks the `challenges:write` scope needed to validate packs."
                ) from exc
            if exc.code == 404:
                raise PraxisError(
                    f"Remote validation is not available at {config.api_url} "
                    f"(404 for {path}). Check CODEPRAXIS_API_URL, or use --local for now."
                ) from exc
            raise PraxisError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise PraxisError(f"Could not reach {config.api_url}: {exc.reason}") from exc

    def _submit(self, config: RemoteConfig, pack: Pack) -> str:
        from ...packio.archive import build_validation_bundle

        # The bundle carries the solution alongside the pack so the server can
        # run both fixtures; the solution never reaches a candidate artifact.
        archive = build_validation_bundle(pack)
        payload = self._request(config, "POST", "/v1/validation-runs", body=archive)
        run_id = payload.get("validation_run_id")
        if not run_id:
            raise PraxisError("The platform accepted the pack but returned no validation_run_id")
        return str(run_id)

    def _await_result(self, config: RemoteConfig, run_id: str) -> dict:
        deadline = time.time() + self._timeout
        while time.time() < deadline:
            payload = self._request(config, "GET", f"/v1/validation-runs/{run_id}")
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
