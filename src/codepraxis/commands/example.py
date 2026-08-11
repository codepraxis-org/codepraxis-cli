"""``codepraxis example`` — open the featured challenge in a live container.

The fastest way to understand what a pack becomes: the platform allocates a
throwaway container, clones the featured challenge into it, and returns a URL
you can open in a browser to see exactly what a candidate sees.

Deliberately unauthenticated. This is the first thing someone runs after
installing, usually before they have a key, so requiring login would put a
signup in front of the demo.
"""

from __future__ import annotations

import webbrowser

from ..errors import PraxisError
from ..execution.remote.client import ApiClient
from ..execution.remote.config import RemoteConfig

EXIT_OK = 0

FEATURED_PATH = "/challenges/featured"
TRIAL_PATH = "/challenges/trial/setup-codebase"


def run(client: ApiClient | None = None, open_browser: bool = False) -> int:
    client = client or ApiClient(RemoteConfig.resolve_public())

    challenge = (client.get(FEATURED_PATH) or {}).get("challenge") or {}
    _describe(challenge)

    print("\nStarting a container… this usually takes under a minute.")
    session = client.post_json(TRIAL_PATH, {})

    url = session.get("container_url")
    if not url:
        raise PraxisError("The platform started a session but returned no container URL.")

    print(f"\n  {url}\n")
    _footer(session)

    if open_browser:
        webbrowser.open(url)

    return EXIT_OK


def _describe(challenge: dict) -> None:
    name = challenge.get("challenge_name") or "Featured challenge"
    print(name)

    description = challenge.get("description")
    if description:
        print(f"  {str(description).strip().splitlines()[0]}")

    difficulty = {1: "Easy", 2: "Medium", 3: "Hard"}.get(challenge.get("difficulty"))
    # Drop blanks: the field frequently carries an empty trailing entry.
    stack = [item for item in (challenge.get("tech_stack") or []) if str(item).strip()]
    bits = [bit for bit in (difficulty, ", ".join(stack) if stack else None) if bit]
    if bits:
        print(f"  {' · '.join(bits)}")

    if challenge.get("max_time"):
        print(f"  {challenge['max_time']} minutes")


def _footer(session: dict) -> None:
    expires = session.get("attempt_expires_at")
    if expires:
        print(f"The container is temporary and expires at {expires}.")
    else:
        print("The container is temporary and will be reclaimed when idle.")
    print("Nothing you do in it is recorded as an attempt.")
