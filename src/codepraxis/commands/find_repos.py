"""`codepraxis find-repos` — source material for a question."""

from __future__ import annotations

import json
from pathlib import Path

from ..discovery import repos as discovery

EXIT_OK = 0


def find_repos(
    topic: str,
    language: str | None = None,
    limit: int = 5,
    seed: int | None = None,
    root: Path | None = None,
    as_json: bool = False,
) -> int:
    found = discovery.find(
        topic=topic,
        language=language,
        limit=limit,
        seed=seed,
        root=root,
    )

    if as_json:
        print(json.dumps({"repos": [repo.as_dict() for repo in found]}, indent=2))
        return EXIT_OK

    if not found:
        _print_nothing_found(topic, language)
        return EXIT_OK

    print(f"{len(found)} candidate{'s' if len(found) != 1 else ''} for “{topic}”\n")
    for repo in found:
        _print_repo(repo)

    print(
        "Licences are filtered to ones we may redistribute, and results are\n"
        "sampled rather than ranked so two authors do not land on the same repo.\n"
        "Read the architecture before choosing: the question is whether there is\n"
        "a self-contained module a candidate can work inside."
    )
    return EXIT_OK


def _print_repo(repo: discovery.Repo) -> None:
    facts = [f"★ {repo.stars:,}", repo.license.upper()]
    if repo.approx_lines:
        facts.append(f"~{repo.approx_lines:,} lines {repo.language}".rstrip())
    elif repo.language:
        facts.append(repo.language)
    if repo.pushed_at:
        facts.append(f"pushed {repo.pushed_at}")

    print(f"  {repo.full_name}")
    print(f"    {'  ·  '.join(facts)}")
    if repo.description:
        print(f"    {_clip(repo.description, 90)}")
    for note in repo.notes:
        print(f"    ! {note}")
    if repo.commit:
        # The spec pins this, so a later build vendors exactly what was read.
        print(f"    {repo.url}  @ {repo.commit[:7]}")
    else:
        print(f"    {repo.url}")
    print()


def _print_nothing_found(topic: str, language: str | None) -> None:
    print(f"No repositories matched “{topic}”"
          + (f" in {language}." if language else ".")
          + "\n")
    print(
        "The filters are deliberately strict — a permissive licence, alive in the\n"
        "last ~18 months, not archived, not a fork. Things that usually help:\n"
        "  · broader words: “rag pipeline” rather than “llamaindex rag reranker”\n"
        "  · drop --language, or try the ecosystem's main one\n"
        "  · run it again — results are sampled, so a second run differs"
    )


def _clip(text: str, width: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"
