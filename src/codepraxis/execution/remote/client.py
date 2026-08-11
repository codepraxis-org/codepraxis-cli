"""HTTP transport for the CodePraxis platform API.

One place for auth headers, error translation and retries, so ``login``,
``validate --remote`` and ``publish`` behave identically and none of them
reimplements error handling.

Endpoints used, served by ``api_authoring_controller`` under ``/api/public``
(so ``CODEPRAXIS_API_URL`` points at that prefix):

  ``GET  /me``                          -> who this key belongs to
  ``POST /validation-runs``             -> submit a bundle, returns a run id
  ``GET  /validation-runs/{id}``        -> poll status + result
  ``POST /challenges``                  -> publish a validated pack
  ``GET  /challenges``                  -> list company challenges
  ``PATCH /challenges/{id}``            -> edit challenge metadata

All four require an API key holding the ``challenges:write`` scope, except
``/me`` which only requires a valid key.

Uses ``urllib`` rather than ``requests`` to keep the package dependency-free.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from ... import __version__
from ...errors import PraxisError
from .config import RemoteConfig

DEFAULT_TIMEOUT_SECONDS = 60


def _unwrap(payload: Any) -> Any:
    """Return the meaningful body of a platform response.

    The platform wraps every response in ``{"success", "message", "data"}``.
    Unwrapping once here keeps that envelope out of every caller, and means a
    caller reading ``result["status"]`` gets the resource's status rather than
    silently getting nothing.

    Responses that are not enveloped are passed through untouched, so this stays
    correct if an endpoint ever returns a bare object.
    """
    if isinstance(payload, dict) and "success" in payload and "data" in payload:
        return payload.get("data") or {}
    return payload


class ApiClient:
    """Thin, typed wrapper over the platform's HTTP API."""

    def __init__(self, config: RemoteConfig, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._config = config
        self._timeout = timeout

    @property
    def api_url(self) -> str:
        return self._config.api_url

    def _headers(self, content_type: str | None = None) -> dict:
        headers = {
            # Lets the server reject or warn on a CLI too old for the current
            # pack contract, instead of failing somewhere obscure.
            "X-Praxis-CLI-Version": __version__,
            "Accept": "application/json",
        }
        # Public endpoints are called without credentials; sending an empty
        # bearer token would be rejected as a malformed header.
        if self._config.token:
            headers["Authorization"] = f"Bearer {self._config.token}"
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self._config.api_url}{path}"
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers=self._headers(content_type),
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                payload = response.read().decode("utf-8")
                return _unwrap(json.loads(payload)) if payload else {}
        except urllib.error.HTTPError as exc:
            raise self._translate(exc, method, path) from exc
        except urllib.error.URLError as exc:
            # A bare socket/TLS error is opaque ("tlsv1 unrecognized name"), and
            # the usual cause is a wrong base URL, so name the override here.
            raise PraxisError(
                f"Could not reach {self._config.api_url}: {exc.reason}. "
                f"If your platform is hosted elsewhere, set CODEPRAXIS_API_URL."
            ) from exc
        except json.JSONDecodeError as exc:
            raise PraxisError(f"{method} {path} returned a non-JSON response") from exc

    def get(self, path: str) -> dict[str, Any]:
        return self.request("GET", path)

    def post_json(self, path: str, payload: dict) -> dict[str, Any]:
        return self.request(
            "POST",
            path,
            body=json.dumps(payload).encode("utf-8"),
            content_type="application/json",
        )

    def patch_json(self, path: str, payload: dict) -> dict[str, Any]:
        return self.request(
            "PATCH",
            path,
            body=json.dumps(payload).encode("utf-8"),
            content_type="application/json",
        )

    def delete(self, path: str) -> dict[str, Any]:
        return self.request("DELETE", path)

    def post_bytes(self, path: str, blob: bytes) -> dict[str, Any]:
        return self.request("POST", path, body=blob, content_type="application/zip")

    # -- errors ------------------------------------------------------------

    def _translate(self, exc: urllib.error.HTTPError, method: str, path: str) -> PraxisError:
        """Turn an HTTP status into something an author can act on."""
        detail = ""
        try:
            raw = exc.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw)
            detail = parsed.get("detail") or parsed.get("message") or raw
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            detail = ""
        detail = str(detail)[:500]

        if exc.code == 401:
            return PraxisError("Authentication failed. Run `codepraxis login` again.")
        if exc.code == 403:
            return PraxisError(
                detail or "This API key is not permitted to do that. It may lack the required scope."
            )
        if exc.code == 404:
            return PraxisError(
                f"{path} not found at {self._config.api_url}. "
                f"Check CODEPRAXIS_API_URL, or upgrade the CLI if the platform has moved on."
            )
        if exc.code == 409:
            return PraxisError(detail or "Conflict: that resource already exists.")
        if exc.code == 413:
            return PraxisError("The pack is too large for the platform to accept.")
        if exc.code == 422:
            return PraxisError(detail or "The platform rejected the pack as invalid.")
        if exc.code == 426:
            return PraxisError(detail or "This CLI is too old for the platform. Run `pip install -U codepraxis`.")
        if exc.code == 429:
            return PraxisError("Rate limited. Wait a moment and try again.")
        return PraxisError(f"{method} {path} failed with HTTP {exc.code}: {detail}")
