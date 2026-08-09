# Releasing

`codepraxis` is published to PyPI. **A version number can never be reused** —
even a deleted release permanently burns its version. Treat every publish as
irreversible.

## One-time setup

1. **Claim the name.** Register `codepraxis` on PyPI before the first real
   release, so nobody else takes it. An initial `0.0.0` placeholder is enough.
2. **Enable 2FA** on the PyPI account and any maintainer accounts.
3. **Configure Trusted Publishing** (PyPI → project → Publishing). Add a
   GitHub publisher:

   | Field | Value |
   |---|---|
   | Owner | `codepraxis-org` |
   | Repository | `praxis-cli` |
   | Workflow | `release.yml` |
   | Environment | `pypi` |

   Repeat on TestPyPI with environment `testpypi`.

4. **Create the GitHub environments** `pypi` and `testpypi`. Put required
   reviewers on `pypi` so a publish needs a second pair of eyes.

No API tokens anywhere. Trusted Publishing exchanges a short-lived GitHub OIDC
token for an upload credential, so there is no long-lived secret to leak,
rotate, or accidentally print in a log.

## Cutting a release

Version lives in exactly one place: `src/praxis/__init__.py`. Hatchling reads it
from there, so there is nothing to keep in sync.

```bash
# 1. Bump the version
vim src/praxis/__init__.py          # __version__ = "0.2.0"

# 2. Verify locally, exactly as CI will
python -m build
python scripts/check_artifact.py dist
python -m twine check --strict dist/*

# 3. Smoke-test the built wheel in a clean environment
python -m venv /tmp/smoke && /tmp/smoke/bin/pip install dist/*.whl
/tmp/smoke/bin/praxis --version

# 4. Dry run to TestPyPI
gh workflow run release.yml -f target=testpypi
pip install --index-url https://test.pypi.org/simple/ codepraxis

# 5. Ship
git tag v0.2.0 && git push origin v0.2.0
```

Pushing a `v*` tag runs the full gate and publishes to PyPI.

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
format** — not the Python API. `praxis.*` modules are internal and may change in
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
