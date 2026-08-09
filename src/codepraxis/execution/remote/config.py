"""Where the CLI finds its platform credentials.

Resolution order, first hit wins:

1. explicit arguments
2. environment (``CODEPRAXIS_API_URL``, ``CODEPRAXIS_TOKEN``)
3. ``~/.config/codepraxis/config.json``, written by ``codepraxis --login``

Keeping this separate from the client means credential handling is testable
without a network, and nothing else in the package reads the environment.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from ...errors import PraxisError

#: Public entry point for the platform API. The backend sits behind the web
#: app rather than a dedicated api.* host, so the prefix is part of the base
#: URL. Override with CODEPRAXIS_API_URL for staging or a local server.
DEFAULT_API_URL = "https://www.codepraxis.co/api/public"

ENV_API_URL = "CODEPRAXIS_API_URL"
ENV_TOKEN = "CODEPRAXIS_TOKEN"


def config_path() -> Path:
    """Location of the on-disk credentials file."""
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "codepraxis" / "config.json"


def read_stored() -> dict:
    path = config_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PraxisError(f"Could not read {path}: {exc}. Re-run `codepraxis --login`.") from exc


def write_stored(data: dict) -> Path:
    """Persist credentials with owner-only permissions.

    The file holds a live API key, so it is created 0600 rather than inheriting
    the process umask.
    """
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return path


@dataclass(frozen=True)
class RemoteConfig:
    api_url: str
    token: str
    #: Display name of the company this key belongs to, cached at login purely
    #: so the CLI can show it before a publish. The server is authoritative.
    company: str | None = None

    @classmethod
    def resolve(cls, api_url: str | None = None, token: str | None = None) -> RemoteConfig:
        """Build a config, or explain precisely what is missing."""
        stored = read_stored()

        resolved_url = api_url or os.environ.get(ENV_API_URL) or stored.get("api_url") or DEFAULT_API_URL
        resolved_token = token or os.environ.get(ENV_TOKEN) or stored.get("token")

        if not resolved_token:
            raise PraxisError(
                "Not authenticated. Run `codepraxis --login`, or set "
                f"{ENV_TOKEN} in the environment (useful in CI)."
            )

        return cls(
            api_url=resolved_url.rstrip("/"),
            token=resolved_token,
            company=stored.get("company"),
        )
