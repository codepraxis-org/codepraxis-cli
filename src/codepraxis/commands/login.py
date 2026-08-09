"""``codepraxis --login`` — store an API key and confirm who it belongs to.

The key is verified against the platform before it is written, so a typo fails
here rather than at the next publish. The response also tells the author which
company they are acting for, which is what every later publish is scoped to.
"""

from __future__ import annotations

import getpass
import os
import sys

from ..errors import PraxisError
from ..execution.remote.client import ApiClient
from ..execution.remote.config import (
    DEFAULT_API_URL,
    ENV_API_URL,
    RemoteConfig,
    read_stored,
    write_stored,
)

EXIT_OK = 0


def run(api_url: str | None = None, token: str | None = None) -> int:
    stored = read_stored()
    resolved_url = api_url or os.environ.get(ENV_API_URL) or stored.get("api_url") or DEFAULT_API_URL
    resolved_url = resolved_url.rstrip("/")

    key = token or _prompt(resolved_url)
    if not key:
        raise PraxisError("No API key entered.")

    # Verify before persisting: a stored bad key produces confusing failures
    # much later, in commands that look unrelated to authentication.
    client = ApiClient(RemoteConfig(api_url=resolved_url, token=key))
    identity = client.get("/v1/me")

    company = identity.get("company") or {}
    company_name = company.get("name") or identity.get("company_name")
    company_id = company.get("id") or identity.get("company_id")

    path = write_stored(
        {
            "api_url": resolved_url,
            "token": key,
            "company": company_name,
            "company_id": company_id,
        }
    )

    who = identity.get("email") or identity.get("user") or "this key"
    print(f"Logged in as {who}")
    if company_name:
        print(f"Publishing as: {company_name}" + (f" (id {company_id})" if company_id else ""))
    else:
        # Without a company the key cannot publish; say so now rather than
        # letting the author discover it at the end of an authoring session.
        print("warning: this key is not associated with a company; publishing will be rejected.")
    print(f"Credentials written to {path} (permissions 0600)")
    return EXIT_OK


def _prompt(api_url: str) -> str:
    if not sys.stdin.isatty():
        raise PraxisError(
            "No API key given and stdin is not a terminal. "
            "Set CODEPRAXIS_TOKEN in the environment instead (this is the CI path)."
        )
    print(f"Signing in to {api_url}")
    print("Create a key at your CodePraxis dashboard -> Settings -> API keys.")
    # getpass keeps the key out of the terminal scrollback and shell history.
    return getpass.getpass("API key: ").strip()
