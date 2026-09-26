"""HTTP clients for the CodePraxis backend and for a question's container.

Two services, two clients:

``Backend``
    The public API at ``https://www.codepraxis.co/api/public``, authenticated
    with the author's API key (``CODEPRAXIS_API_KEY``). It publishes questions,
    lists categories, and opens a question in a container.

``Container``
    The container a question was opened in. The CLI talks to it directly:
    ``/uvi/author/*`` for files, commands, logs and status, and the
    candidate's own ``/uvi/run`` and ``/uvi/submit``.

Uses ``urllib`` so the package stays dependency-free.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from . import __version__
from .errors import PraxisError

DEFAULT_API_URL = "https://www.codepraxis.co/api/public"
ENV_API_KEY = "CODEPRAXIS_API_KEY"
ENV_API_URL = "CODEPRAXIS_API_URL"


def api_key() -> str:
    key = os.environ.get(ENV_API_KEY, "").strip()
    if not key:
        raise PraxisError(
            f"Please give your CodePraxis API key: set {ENV_API_KEY} "
            "(create one in the dashboard under Settings, API keys)."
        )
    return key


def api_url() -> str:
    return (os.environ.get(ENV_API_URL) or DEFAULT_API_URL).rstrip("/")


def website_url() -> str:
    """The dashboard's base URL, for links printed to the author."""
    base = api_url()
    for suffix in ("/api/public", "/api"):
        if base.endswith(suffix):
            return base[: -len(suffix)]
    return base


class HttpError(PraxisError):
    """The server answered with an error status."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


class NotFound(HttpError):
    """The server answered 404."""


class Unreachable(PraxisError):
    """The server could not be reached at all."""


def _request(
    method: str,
    url: str,
    *,
    body: bytes | None = None,
    content_type: str | None = None,
    headers: dict | None = None,
    timeout: float = 60,
) -> Any:
    all_headers = {"Accept": "application/json", "X-Praxis-CLI-Version": __version__, **(headers or {})}
    if content_type:
        all_headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=body, method=method, headers=all_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise _http_error(exc, method, url) from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        reason = getattr(exc, "reason", exc)
        raise Unreachable(f"Could not reach {url.split('?')[0]}: {reason}") from exc
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PraxisError(f"{method} {url.split('?')[0]} returned something that isn't JSON") from exc
    # The backend wraps responses as {"success", "message", "data"}.
    if isinstance(payload, dict) and "success" in payload and "data" in payload:
        return payload.get("data") or {}
    return payload


def _http_error(exc: urllib.error.HTTPError, method: str, url: str) -> PraxisError:
    detail: Any = ""
    try:
        parsed = json.loads(exc.read().decode("utf-8", errors="replace"))
        detail = parsed.get("detail") or parsed.get("message") or parsed
        if isinstance(parsed.get("data"), dict) and parsed["data"].get("errors"):
            detail = parsed["data"]["errors"]
    except (json.JSONDecodeError, UnicodeDecodeError, OSError, AttributeError):
        pass
    if not isinstance(detail, str):
        detail = json.dumps(detail)[:800]
    path = urllib.parse.urlparse(url).path
    if exc.code == 401:
        return HttpError(f"The API key was refused. Check {ENV_API_KEY}.", 401)
    if exc.code == 404:
        return NotFound(detail or f"{path} not found", 404)
    return HttpError(f"{method} {path} failed ({exc.code}): {detail}", exc.code)


class Backend:
    """The CodePraxis public API, as the API key's owner."""

    def __init__(self, key: str | None = None, url: str | None = None) -> None:
        self._key = key or api_key()
        self._url = (url or api_url()).rstrip("/")

    def _call(self, method: str, path: str, *, body: bytes | None = None, content_type: str | None = None,
              timeout: float = 60) -> Any:
        return _request(method, f"{self._url}{path}", body=body, content_type=content_type,
                        headers={"Authorization": f"Bearer {self._key}"}, timeout=timeout)

    def get(self, path: str) -> Any:
        return self._call("GET", path)

    def get_bytes(self, path: str) -> bytes:
        """A binary download (a question's zip), not a JSON response."""
        request = urllib.request.Request(
            f"{self._url}{path}", method="GET",
            headers={"Authorization": f"Bearer {self._key}", "X-Praxis-CLI-Version": __version__},
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise _http_error(exc, "GET", f"{self._url}{path}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise Unreachable(f"Could not reach {self._url}: {getattr(exc, 'reason', exc)}") from exc

    def post_json(self, path: str, payload: Any, timeout: float = 60) -> Any:
        return self._call("POST", path, body=json.dumps(payload).encode(), content_type="application/json",
                          timeout=timeout)

    def post_zip(self, path: str, blob: bytes) -> Any:
        return self._call("POST", path, body=blob, content_type="application/zip", timeout=180)

    def delete(self, path: str) -> Any:
        return self._call("DELETE", path)

    #: How long launch keeps asking while the platform starts a container.
    OPEN_DEADLINE_SECONDS = 480

    def open_challenge(self, challenge_id: int, on_retry=None) -> dict:
        """Open a question in the key owner's container.

        A cold start can take minutes, but the website's proxy cuts any request
        off at 45 seconds (it answers 500, 502 or 504) while the backend carries
        on starting the container. Asking again is safe: the backend reuses the
        container it is preparing, and answers quickly once it is ready.
        """
        deadline = time.time() + self.OPEN_DEADLINE_SECONDS
        attempt = 0
        while True:
            attempt += 1
            try:
                return self._call("POST", f"/challenges/{challenge_id}/open", timeout=120)
            except (HttpError, Unreachable) as exc:
                cut_off = isinstance(exc, Unreachable) or getattr(exc, "status", 0) in (500, 502, 503, 504)
                if not cut_off or time.time() > deadline:
                    raise
                if on_retry:
                    on_retry(attempt, exc)
                time.sleep(15)


class Container:
    """A question's container: its author endpoints and its Run and Submit."""

    def __init__(self, base_url: str, folder: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.folder = folder

    def _url(self, path: str, **params: Any) -> str:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        return f"{self.base_url}/uvi{path}" + (f"?{query}" if query else "")

    def status(self) -> dict:
        return _request("GET", self._url("/author/status", folder=self.folder), timeout=30)

    def list_files(self) -> list[dict]:
        return _request("GET", self._url("/author/files", folder=self.folder), timeout=60).get("files", [])

    def read_file(self, path: str) -> bytes:
        data = _request("GET", self._url("/author/files", folder=self.folder, path=path), timeout=60)
        return base64.b64decode(data["content_base64"])

    def write_file(self, path: str, content: bytes, executable: bool = False) -> dict:
        body = {"folder": self.folder, "path": path, "executable": executable,
                "content_base64": base64.b64encode(content).decode()}
        return _request("PUT", self._url("/author/files"), body=json.dumps(body).encode(),
                        content_type="application/json", timeout=120)

    def delete_file(self, path: str) -> dict:
        return _request("DELETE", self._url("/author/files", folder=self.folder, path=path), timeout=60)

    def exec(self, command: str, timeout_s: int = 120) -> dict:
        body = {"folder": self.folder, "command": command, "timeout_s": timeout_s}
        return _request("POST", self._url("/author/exec"), body=json.dumps(body).encode(),
                        content_type="application/json", timeout=timeout_s + 30)

    def logs(self, source: str, tail: int = 200) -> dict:
        return _request("GET", self._url("/author/logs", folder=self.folder, source=source, tail=tail), timeout=30)

    def run(self) -> dict:
        return _request("GET", self._url("/run", foldername=self.folder), timeout=180)

    def submit(self, challenge_version_id: int) -> dict:
        return _request("GET", self._url("/submit", challengeID=str(challenge_version_id)), timeout=660)
