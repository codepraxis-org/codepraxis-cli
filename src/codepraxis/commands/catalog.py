"""Company challenge catalog commands for the public authoring API."""

from __future__ import annotations

import json
import webbrowser
from typing import Any

from ..errors import PraxisError
from ..execution.remote.client import ApiClient
from ..execution.remote.config import RemoteConfig

EXIT_OK = 0
EXIT_ABORTED = 2


def list_questions(client: ApiClient | None = None, as_json: bool = False) -> int:
    client = client or ApiClient(RemoteConfig.resolve())
    payload = client.get("/challenges")
    challenges = payload.get("challenges") or []

    if as_json:
        print(json.dumps({"challenges": challenges}, indent=2))
        return EXIT_OK

    if not challenges:
        print("No questions found for this company.")
        return EXIT_OK

    for challenge in challenges:
        _print_challenge(challenge)
    return EXIT_OK


def edit_question(
    challenge_id: int,
    updates: dict[str, Any] | None = None,
    client: ApiClient | None = None,
    open_browser: bool = False,
) -> int:
    client = client or ApiClient(RemoteConfig.resolve())
    updates = {key: value for key, value in (updates or {}).items() if value is not None}

    if updates:
        payload = client.patch_json(f"/challenges/{challenge_id}", updates)
        challenge = payload.get("challenge") or {}
        updated_id = challenge.get("challenge_id") or challenge_id
        updated_name = challenge.get("challenge_name") or ""
        print(f"Updated question {updated_id}: {updated_name}")
    else:
        print(f"Opening question {challenge_id} in a container...")

    session = client.post_json(f"/challenges/{challenge_id}/setup-codebase", {})
    url = session.get("container_url")
    if not url:
        raise PraxisError("The platform prepared the question but returned no container URL.")

    print(f"\n  {url}\n")
    print(
        "Use the container to inspect or adjust the question. "
        "Publish a new pack version when code changes are ready."
    )

    if open_browser:
        webbrowser.open(url)

    return EXIT_OK


def _print_challenge(challenge: dict[str, Any]) -> None:
    challenge_id = challenge.get("challenge_id")
    name = challenge.get("challenge_name") or "(untitled)"
    status = challenge.get("status") or "unknown"
    version = challenge.get("challenge_version_id")
    updated = challenge.get("updated_at") or challenge.get("created_at")

    line = f"{challenge_id}\t{name}\t{status}"
    if version:
        line += f"\tv{version}"
    if updated:
        line += f"\t{updated}"
    print(line)


def delete_question(
    challenge_id: int,
    client: ApiClient | None = None,
    assume_yes: bool = False,
) -> int:
    """Delete a question the company owns.

    Confirmed by default: unlike a draft, this is not recoverable from the
    dashboard. The platform refuses outright once the question has been assigned
    to anyone, so the destructive case this guards is an unassigned question the
    author still wanted.
    """
    import sys

    client = client or ApiClient(RemoteConfig.resolve())

    if not assume_yes:
        if not sys.stdin.isatty():
            raise PraxisError(
                "Deleting needs confirmation, but stdin is not a terminal. Pass --yes."
            )
        print(f"Permanently delete question {challenge_id}? This cannot be undone.")
        if input("Continue? [y/N] ").strip().lower() not in {"y", "yes"}:
            print("Aborted.", file=sys.stderr)
            return EXIT_ABORTED

    payload = client.delete(f"/challenges/{challenge_id}")
    removed = payload.get("versions_removed", 0)
    print(f"Deleted question {challenge_id} ({removed} version(s) removed).")
    return EXIT_OK
