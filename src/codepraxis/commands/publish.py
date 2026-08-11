"""``codepraxis ship`` — publish a validated pack to your company.

Publishing is outward-facing and effectively irreversible: candidates can be
assigned the challenge immediately. So the flow is deliberately strict.

1. **Validate remotely first.** A pack is only publishable off the back of a
   passing run in the real runner. Local results never qualify — they cannot
   observe ``setup.sh``, the image's packages, or the LLM proxy.
2. **Show the company and confirm.** The server derives ownership from the API
   key; the CLI never sends a company id, because a client-supplied owner is
   exactly the tenancy hole this design avoids. The name is displayed so the
   author can catch a wrong-key mistake before it lands.
3. **Publish as a draft by default.** Reaching candidates is a separate,
   deliberate act in the dashboard unless ``--live`` is passed.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ..domain import spec
from ..domain.results import Fixture
from ..errors import PraxisError
from ..execution.remote.client import ApiClient
from ..execution.remote.config import RemoteConfig
from ..execution.remote.executor import RemoteExecutor
from ..packio.discovery import resolve_pack_dir
from ..packio.loader import load_pack
from ..reporting.reporter import Reporter

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_ABORTED = 2


def run(
    root: Path,
    selector: str | None,
    reporter: Reporter,
    assume_yes: bool = False,
    live: bool = False,
    validation_run_id: str | None = None,
    challenge_id: int | None = None,
    client: ApiClient | None = None,
) -> int:
    if not selector:
        raise PraxisError(
            "Publishing needs an explicit pack: `codepraxis ship <name>`. "
            "Refusing to publish every pack it can find."
        )

    pack_dir = resolve_pack_dir(root, selector)

    # A published question can be sent to candidates immediately, so it must
    # trace back to a plan someone signed off on. This also stops a question
    # that skipped planning entirely from reaching the catalog.
    spec.require_approved(pack_dir)

    pack = load_pack(pack_dir)

    if not pack.has_solution:
        raise PraxisError(
            f"{pack.name} has no solution/ directory. A reference solution is required "
            f"before publishing — it is what proves the challenge is solvable."
        )

    # Credentials are resolved lazily so an injected client (tests, and any
    # future caller that already authenticated) never touches the filesystem.
    config = None
    if client is None:
        config = RemoteConfig.resolve()
        client = ApiClient(config)

    run_id = validation_run_id
    if run_id is None:
        run_id = _validate(pack, client, reporter)

    company = _company_name(client, config)
    if not _confirm(pack.name, company, live, assume_yes, challenge_id):
        print("Aborted.", file=sys.stderr)
        return EXIT_ABORTED

    body = {
        # No company_id: the server derives ownership from the API key.
        "name": pack.name,
        "validation_run_id": run_id,
        "status": "published" if live else "draft",
    }
    # With an id, this publishes a new version of an existing question. Without
    # one the platform creates a new question — which is why editing a pack and
    # re-publishing used to leave a duplicate behind.
    if challenge_id is not None:
        body["challenge_id"] = challenge_id

    payload = client.post_json("/challenges", body)

    challenge_id = payload.get("challenge_id")
    version_id = payload.get("challenge_version_id")
    container_url = payload.get("container_url")
    preview_error = payload.get("preview_error")
    state = "published" if live else "draft"
    created = payload.get("created", True)

    verb = "published" if created else "updated"
    print(f"{pack.name} {verb} for {company} ({state})")
    if challenge_id:
        label = "challenge" if created else "challenge (new version of)"
        print(f"  {label} {challenge_id}, version {version_id}")
    if container_url:
        print(f"  {container_url}")
    elif preview_error:
        print(f"  Preview container unavailable: {preview_error}")
    if not live:
        print("  Publish it to candidates from the dashboard when you are ready.")
    return EXIT_OK


def _validate(pack, client: ApiClient, reporter: Reporter) -> str:
    """Run remote validation and refuse to continue unless it passes."""
    print(f"Validating {pack.name} in the runner before publishing…")
    executor = RemoteExecutor(client=client)
    result = executor.execute(pack, [Fixture.SOLUTION, Fixture.STARTER])
    reporter.report(result)

    if not result.ok:
        raise PraxisError(
            "Remote validation failed, so nothing was published. "
            "Fix the pack and try again, or re-run with --validation-run-id to reuse a passing run."
        )

    if not executor.last_run_id:
        raise PraxisError("Validation passed but the platform returned no run id to publish against.")
    return executor.last_run_id


def _company_name(client: ApiClient, config: RemoteConfig | None) -> str:
    """Ask the server who this key acts for; fall back to what login cached."""
    cached = config.company if config else None
    try:
        identity = client.get("/me")
    except PraxisError:
        return cached or "your company"
    company = identity.get("company") or {}
    return company.get("name") or cached or "your company"


def _confirm(pack_name: str, company: str, live: bool, assume_yes: bool, challenge_id: int | None = None) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        raise PraxisError(
            "Publishing needs confirmation, but stdin is not a terminal. "
            "Pass --yes to publish non-interactively (CI)."
        )
    visibility = "LIVE to candidates" if live else "as a draft"
    target = f"as a new version of question {challenge_id}" if challenge_id else "as a new question"
    print(f"\nAbout to publish {pack_name} to {company} {target}, {visibility}.")
    return input("Continue? [y/N] ").strip().lower() in {"y", "yes"}
