# Releasing

`codepraxis` is published to PyPI. **A version number can never be reused** —
even a deleted release permanently burns its version. Treat every publish as
irreversible.

## One-time setup

The GitHub side is done: `codepraxis-org/codepraxis-cli` is private, and the
`pypi` and `testpypi` environments exist. What remains can only be done from a
browser signed in to PyPI — there is no API for creating a Trusted Publisher.

### 1. TestPyPI — https://test.pypi.org

Do this one first; it is the rehearsal target and mistakes there are cheap.

Account settings → **Publishing** → *Add a new pending publisher*:

| Field | Value |
|---|---|
| PyPI Project Name | `codepraxis` |
| Owner | `codepraxis-org` |
| Repository name | `codepraxis-cli` |
| Workflow name | `release.yml` |
| Environment name | `testpypi` |

### 2. PyPI — https://pypi.org

Same form, one field different:

| Field | Value |
|---|---|
| PyPI Project Name | `codepraxis` |
| Owner | `codepraxis-org` |
| Repository name | `codepraxis-cli` |
| Workflow name | `release.yml` |
| Environment name | **`pypi`** |

A *pending* publisher claims the name `codepraxis` and creates the project on
first upload, so registering a placeholder release is unnecessary — but do add
it before someone else takes the name.

### 3. Enable 2FA

On both accounts, for every maintainer.

No API tokens are stored anywhere. Trusted Publishing exchanges a short-lived
GitHub OIDC token for an upload credential, so there is no long-lived secret to
leak, rotate, or print into a log.

## The human gate

Publishing must never happen by accident, so something has to stand between a
push and PyPI. Which mechanism is available depends on the repository's
visibility.

### Today: a structural gate

Environment protection rules — required reviewers — are unavailable on private
repositories under **GitHub Free**; GitHub rejects them with HTTP 422. So the
gate is the workflow's shape instead:

- **A tag only ever publishes to TestPyPI.** There is no path from
  `git push --tags` to a permanent PyPI release.
- **PyPI requires a deliberate manual dispatch**: Actions → release → *Run
  workflow* → `target: pypi`.

### Once the repository is public: a reviewer gate

Environment protection rules are free on **public** repositories, so the
awkward two-step is no longer necessary. Making the repo public — which changes
nothing about what is exposed, since PyPI already ships the full source — lets
the gate become a person instead of a procedure:

1. Settings → Environments → `pypi` → **Required reviewers**, add the
   maintainers.
2. Relax the `pypi` job's condition in `release.yml` so a tag can reach it:

   ```yaml
   # was: github.event_name == 'workflow_dispatch' && inputs.target == 'pypi'
   if: startsWith(github.ref, 'refs/tags/v') || inputs.target == 'pypi'
   ```

Then `git push origin v0.5.0` runs every gate, publishes to TestPyPI, and
*waits* for a human to approve the PyPI step. Same protection, one command, and
the approval is recorded against a named person rather than being invisible in
someone's shell history.

Keep the manual dispatch as-is; it stays useful for re-publishing a build
without cutting a new tag.

## Cutting a release

Version lives in exactly one place: `src/codepraxis/__init__.py`. Hatchling reads it
from there, so there is nothing to keep in sync.

```bash
# 1. Bump the version
vim src/codepraxis/__init__.py          # __version__ = "0.2.0"

# 2. Verify locally, exactly as CI will
python -m build
python scripts/check_artifact.py dist
python -m twine check --strict dist/*

# 3. Smoke-test the built wheel in a clean environment
python -m venv /tmp/smoke && /tmp/smoke/bin/pip install dist/*.whl
/tmp/smoke/bin/codepraxis --version

# 4. Tag — runs every gate and publishes to TestPyPI
git tag v0.2.0 && git push origin v0.2.0
pip install --index-url https://test.pypi.org/simple/ codepraxis==0.2.0

# 5. Promote to PyPI, deliberately
gh workflow run release.yml -f target=pypi
```

Step 5 is the only thing that writes to PyPI, and it cannot happen by accident.
The build re-runs every gate before uploading, including a check that the tag
matches `__version__`.

## What the gates check

| Gate | Catches |
|---|---|
| `check_artifact.py` | Challenge packs, solutions, or credentials swept into a public artifact |
| `twine check --strict` | Metadata that renders wrong on the project page |
| Clean-venv smoke test | A module that imports from the source tree but is missing from the wheel |
| CI matrix | A syntax or stdlib feature newer than the `requires-python` floor |

The artifact check is the important one. This package is public and the
question bank is not; see CONTRIBUTING.md.

## Versioning

Semantic versioning, where the public contract is **the CLI surface and the pack
format** — not the Python API. `codepraxis.*` modules are internal and may change in
any release.

- **patch** — bug fixes, better diagnostics
- **minor** — new commands, new lint rules, new pack fields
- **major** — a pack that validated before now fails, or a command changes shape

Because the CLI talks to the platform, every request carries
`X-Praxis-CLI-Version`. When the server drops support for a pack contract, it
returns a clear upgrade error rather than failing obscurely — so shipping a
breaking pack-format change means updating the server's minimum supported
version in the same release.

## Yanking

If a release is broken, `yank` rather than delete:

```bash
# PyPI → Manage → Releases → Yank
```

Yanking hides it from new resolutions while leaving pinned installs working.
Deleting breaks anyone who pinned it and still does not free the version.
