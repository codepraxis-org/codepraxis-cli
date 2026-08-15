"""Finding a repository worth building a question from.

A question built on real code is hard to game, because the model has never
seen that code. This turns "I want to test AI engineers" into a handful of
repositories an author can actually choose between.

Two decisions shape everything here.

**We filter for legality first.** The code ends up in a container the candidate
controls, so it has to be code we are allowed to redistribute. Roughly a
quarter of GitHub carries no licence at all, which means all rights reserved.

**We sample rather than rank.** If every author searching "tool calling agent"
receives the same top repository, the same codebase turns up in assessments at
several companies and solutions start circulating. Filter hard, then choose
randomly from what survives.
"""

from __future__ import annotations

import random
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import github

#: Licences that permit redistribution inside an assessment. Copyleft is
#: excluded deliberately: a candidate's container is arguably distribution, and
#: we are not going to reason about that per question. Repositories with no
#: licence never appear at all — GitHub omits them from a `license:` search.
ALLOWED_LICENSES = ("mit", "apache-2.0", "bsd-3-clause", "bsd-2-clause", "isc")

#: A floor only. There is no ceiling: a popular repository is not disqualified,
#: because the candidate is not asked to reproduce it — they are asked to change
#: it in a way we chose. What popularity buys a model is faster orientation,
#: not the answer, and the AI-solvability check measures that directly.
MIN_STARS = 10

#: Kilobytes, and a loose sanity check rather than a quality signal. Repository
#: size includes git history and binaries. The real gate is whether the
#: architecture has a seam, which only reading it can answer.
MIN_SIZE_KB = 50
MAX_SIZE_KB = 5000

#: Dead repositories have stale dependencies that will not install in the
#: container.
MAX_AGE_DAYS = 550

#: Bytes of primary-language source. The floor drops single-file toys; there is
#: no ceiling, only a note once a repository is large enough to need a clear
#: seam.
MIN_SOURCE_BYTES = 30_000
LARGE_SOURCE_BYTES = 1_000_000

#: Rotated at random so repeated searches reach different parts of the result
#: space. None is GitHub's relevance ranking.
SORT_MODES = (None, "stars", "updated")

#: How many results to pull before sampling. Wider pool, less collision.
#: Search has its own generous quota (10/min unauthenticated), so paging here
#: is cheap — unlike inspection below.
SEARCH_PAGES = 2

#: Ceiling on close inspection, which is the expensive part.
#:
#: /languages is on GitHub's *core* quota: 60 requests an hour unauthenticated,
#: not the 10 a minute that search gets. Inspecting ten repositories to show
#: five would exhaust an author's whole hour in three searches. So we inspect
#: lazily — only until we have enough to show — and stop at this ceiling even
#: if that means returning fewer.
MAX_INSPECTIONS = 8


@dataclass
class Repo:
    """A candidate repository, as the author needs to judge it."""

    full_name: str
    description: str
    url: str
    license: str
    stars: int
    size_kb: int
    pushed_at: str
    language: str
    default_branch: str
    source_bytes: int = 0
    commit: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def approx_lines(self) -> int:
        """Rough line count from source bytes.

        ~33 bytes per line holds well enough across mainstream languages for
        the only question being asked: can someone orient in this?
        """
        return int(self.source_bytes / 33) if self.source_bytes else 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "full_name": self.full_name,
            "description": self.description,
            "url": self.url,
            "license": self.license,
            "stars": self.stars,
            "size_kb": self.size_kb,
            "pushed_at": self.pushed_at,
            "language": self.language,
            "default_branch": self.default_branch,
            "source_bytes": self.source_bytes,
            "approx_lines": self.approx_lines,
            "commit": self.commit,
            "notes": self.notes,
        }


def build_query(topic: str, language: str | None = None) -> str:
    """Compose the search, letting GitHub do the filtering it is good at."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)).strftime("%Y-%m-%d")

    parts = [topic.strip()]
    if language:
        parts.append(f"language:{language}")
    parts.extend(
        [
            " ".join(f"license:{name}" for name in ALLOWED_LICENSES),
            f"stars:>={MIN_STARS}",
            f"size:{MIN_SIZE_KB}..{MAX_SIZE_KB}",
            f"pushed:>{cutoff}",
            # Sharper quality signals than a star count: archived means
            # explicitly dead, and a fork is somebody else's work.
            "archived:false",
            "fork:false",
            "is:public",
        ]
    )
    return " ".join(part for part in parts if part)


def used_repos(root: Path) -> set[str]:
    """Repositories already turned into questions locally.

    Reads the ``repo:`` line out of each ``spec.md``. Free collision avoidance,
    and it catches the likeliest case: one company writing two questions on the
    same codebase without noticing.
    """
    found: set[str] = set()
    if not root.is_dir():
        return found

    for spec in root.glob("*/spec.md"):
        try:
            text = spec.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # The host prefix must be consumed explicitly. Left to a lazy wildcard,
        # "github.com/a/taken" captures "github.com/a" — which matches nothing
        # and silently disables the exclusion.
        match = re.search(
            r"^repo:\s*(?:https?://)?(?:www\.)?(?:github\.com/)?([\w.-]+/[\w.-]+)",
            text,
            re.MULTILINE,
        )
        if match:
            found.add(match.group(1).lower())
    return found


def _to_repo(item: dict[str, Any]) -> Repo | None:
    full_name = item.get("full_name")
    if not full_name:
        return None
    licence = (item.get("license") or {}).get("key") or ""
    return Repo(
        full_name=full_name,
        description=(item.get("description") or "").strip(),
        url=item.get("html_url") or f"https://github.com/{full_name}",
        license=licence,
        stars=int(item.get("stargazers_count") or 0),
        size_kb=int(item.get("size") or 0),
        pushed_at=(item.get("pushed_at") or "")[:10],
        language=item.get("language") or "",
        default_branch=item.get("default_branch") or "main",
    )


def _eligible(repo: Repo) -> bool:
    """Re-check what the query already asked for.

    GitHub's qualifiers are not always exact, and shipping a GPL repository to
    a customer because a filter silently failed is not a risk worth taking.
    """
    return bool(repo.full_name) and repo.license in ALLOWED_LICENSES


def find(
    topic: str,
    language: str | None = None,
    limit: int = 5,
    seed: int | None = None,
    exclude: Iterable[str] = (),
    root: Path | None = None,
    client=github,
) -> list[Repo]:
    """Search, filter, sample, then inspect the shortlist closely."""
    rng = random.Random(seed)
    excluded = {name.lower() for name in exclude}
    if root is not None:
        excluded |= used_repos(root)

    query = build_query(topic, language)
    items = client.search(query, sort=rng.choice(SORT_MODES), pages=SEARCH_PAGES)

    pool: list[Repo] = []
    seen: set[str] = set()
    for item in items:
        repo = _to_repo(item)
        if repo is None or not _eligible(repo):
            continue
        key = repo.full_name.lower()
        if key in seen or key in excluded:
            continue
        seen.add(key)
        pool.append(repo)

    if not pool:
        return []

    # Sample from the whole qualifying pool, not the top of it. This is what
    # stops two companies searching the same words getting the same repository.
    rng.shuffle(pool)

    # Inspect lazily: stop as soon as we have enough, so a small --limit costs
    # a small number of core-quota requests.
    chosen: list[Repo] = []
    for repo in pool[:MAX_INSPECTIONS]:
        if len(chosen) >= limit:
            break
        if _inspect(repo, client):
            chosen.append(repo)
    return chosen


def _inspect(repo: Repo, client) -> bool:
    """Measure real source size. True if the repository is worth showing.

    One request against GitHub's *core* quota, which is why this runs lazily
    and never on the whole pool. A repository under the source floor is a toy
    and gets dropped.
    """
    try:
        by_language = client.languages(repo.full_name)
    except Exception:  # noqa: BLE001 - one bad repo must not fail the search
        by_language = {}
        # Say so rather than quietly showing a repository whose size was never
        # checked. The usual cause is the core quota, and a silently unchecked
        # toy repository is exactly what the floor exists to catch.
        repo.notes.append("size unchecked — GitHub rate limit")

    if by_language:
        primary = max(by_language, key=lambda key: by_language[key])
        repo.source_bytes = int(by_language[primary])
        if not repo.language:
            repo.language = primary

    if repo.source_bytes and repo.source_bytes < MIN_SOURCE_BYTES:
        return False

    if repo.source_bytes >= LARGE_SOURCE_BYTES:
        repo.notes.append("large — needs a clear seam")
    if repo.stars >= 20_000:
        repo.notes.append("widely known; a model will orient fast here")
    return True


def pin(repo: Repo, client=github) -> str | None:
    """Resolve the current commit for one chosen repository.

    Deliberately not part of the search. Pinning every candidate would double
    the core-quota cost to record SHAs for repositories the author is about to
    discard; only the one that becomes a question needs it, and the spec is
    where it belongs.
    """
    repo.commit = client.head_commit(repo.full_name, repo.default_branch)
    return repo.commit
