"""A thin GitHub search client.

Uses ``urllib`` rather than ``requests`` to keep the package dependency-free,
matching :mod:`codepraxis.execution.remote.client`.

Unauthenticated search allows 10 requests a minute, which is plenty for one
search per invocation. ``GITHUB_TOKEN`` raises that to 30 and is picked up
automatically when set, but is never required — an author should be able to
find a repository without creating a token first.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ..errors import PraxisError

SEARCH_URL = "https://api.github.com/search/repositories"
REPO_URL = "https://api.github.com/repos"

#: GitHub caps search paging here regardless of what the query matches.
MAX_SEARCH_RESULTS = 1000
PER_PAGE = 100

DEFAULT_TIMEOUT = 20


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "codepraxis-cli",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(url: str, timeout: int = DEFAULT_TIMEOUT) -> Any:
    request = urllib.request.Request(url, headers=_headers(), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise _translate(exc) from exc
    except urllib.error.URLError as exc:
        raise PraxisError(f"Could not reach GitHub: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise PraxisError("GitHub returned a non-JSON response") from exc


def _translate(exc: urllib.error.HTTPError) -> PraxisError:
    if exc.code in (403, 429):
        # Two different quotas sit behind this, and confusing them wastes an
        # author's time: search allows 10 requests a minute, while everything
        # else shares 60 an *hour*. A token lifts both far beyond either.
        reset = exc.headers.get("X-RateLimit-Reset") if exc.headers else None
        when = ""
        if reset and reset.isdigit():
            minutes = max(0, int((int(reset) - time.time()) / 60))
            when = f" Resets in about {minutes} minute{'s' if minutes != 1 else ''}."
        return PraxisError(
            "GitHub rate limit reached." + when + "\n"
            "Unauthenticated: 10 searches a minute, 60 other requests an hour.\n"
            "Set GITHUB_TOKEN to raise that to 5,000 an hour:\n"
            "  export GITHUB_TOKEN=$(gh auth token)"
        )
    if exc.code == 422:
        return PraxisError(
            "GitHub rejected the search query. A topic with unusual punctuation "
            "can do this — try simpler words."
        )
    return PraxisError(f"GitHub search failed ({exc.code} {exc.reason})")


def search(query: str, sort: str | None = None, pages: int = 2) -> list[dict[str, Any]]:
    """Run a repository search and return the raw items.

    ``sort`` of ``None`` means GitHub's own relevance ranking ("best match").
    Paging exists to widen the pool before sampling, not to show the author 200
    results.
    """
    items: list[dict[str, Any]] = []

    for page in range(1, pages + 1):
        if len(items) >= MAX_SEARCH_RESULTS:
            break
        params = {"q": query, "per_page": str(PER_PAGE), "page": str(page)}
        if sort:
            params["sort"] = sort
            params["order"] = "desc"

        payload = _get(f"{SEARCH_URL}?{urllib.parse.urlencode(params)}")
        batch = payload.get("items") or []
        items.extend(batch)
        if len(batch) < PER_PAGE:
            break  # last page

    return items


def languages(full_name: str) -> dict[str, int]:
    """Bytes of source per language.

    The search result's ``size`` is disk usage including git history and
    binaries, so it says little about how much code a candidate faces. This is
    the honest measure, but it costs a request per repository — call it on a
    shortlist, never on every result.
    """
    return _get(f"{REPO_URL}/{full_name}/languages") or {}


def head_commit(full_name: str, branch: str) -> str | None:
    """The current commit on a branch, so a spec can pin what it read.

    Returns None rather than raising: a missing SHA is worth a warning, not a
    failed search.
    """
    try:
        payload = _get(f"{REPO_URL}/{full_name}/commits/{urllib.parse.quote(branch)}")
    except PraxisError:
        return None
    sha = payload.get("sha")
    return sha[:40] if isinstance(sha, str) else None
