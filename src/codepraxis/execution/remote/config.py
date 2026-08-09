"""Where the CLI finds its platform credentials.

Resolution order, first hit wins:

1. explicit constructor arguments
2. environment (``CODEPRAXIS_API_URL``, ``CODEPRAXIS_TOKEN``)
3. ``~/.config/codepraxis/config.json``, written by ``codepraxis login``

Keeping this separate from the executor means credential handling is testable
without a network, and the executor never reads the environment itself.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from ...errors import PraxisError

DEFAULT_API_URL = "https://api.codepraxis.com"

ENV_API_URL = "CODEPRAXIS_API_URL"
ENV_TOKEN = "CODEPRAXIS_TOKEN"


def config_path() -> Path:
    """Location of the on-disk credentials file."""
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "codepraxis" / "config.json"


@dataclass(frozen=True)
class RemoteConfig:
    api_url: str
    token: str

    @classmethod
    def resolve(cls, api_url: str | None = None, token: str | None = None) -> RemoteConfig:
        """Build a config or explain precisely what is missing."""
        stored: dict = {}
        path = config_path()
        if path.is_file():
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise PraxisError(f"Could not read {path}: {exc}. Re-run `codepraxis login`.") from exc

        resolved_url = api_url or os.environ.get(ENV_API_URL) or stored.get("api_url") or DEFAULT_API_URL
        resolved_token = token or os.environ.get(ENV_TOKEN) or stored.get("token")

        if not resolved_token:
            raise PraxisError(
                "Not authenticated. Run `codepraxis login`, or set "
                f"{ENV_TOKEN} in the environment (useful in CI)."
            )

        return cls(api_url=resolved_url.rstrip("/"), token=resolved_token)
