# codepraxis

Author and validate CodePraxis challenge packs from your own repository.

```bash
pip install codepraxis
codepraxis validate --local my-challenge
```

## What this is

A challenge pack is a directory — starter code, a test module, instructions.
This CLI lets you keep packs in your own git repository, iterate on them with
your own editor, and check them before they reach candidates.

Two tiers, one result shape:

| Command | Runs | Speed | Authoritative? |
|---|---|---|---|
| `codepraxis validate --local` | Pure-Python harness on your machine | seconds | No — advisory |
| `codepraxis validate --remote` | The real runner image, on CodePraxis | ~1 min | **Yes — gates publish** |

`--local` reproduces how the runner loads, orders and scores a pack, so it
catches most authoring mistakes in the inner loop. It is **not** the container:
it does not run `setup.sh`, does not have the image's package set, and has no
LLM proxy. Anything it cannot check is reported as a `note` rather than
silently passing. Publishing always requires a remote run.

## The two fixtures

Every pack is validated twice:

- **solution** — `source/` overlaid with `solution/`. Must pass everything.
- **starter** — `source/` alone. Must *fail*.

The starter run is the one authors forget. A pack whose starter already passes
has tests that do not discriminate, and every candidate will score full marks.

```
askgit  (local)
  solution  18/18 passed
  starter   0/18 passed
  PASSED  8.9s
```

## Pack layout

```
my-challenge/
├── metadata.json            # {"name": "..."} — becomes the workspace directory
├── backend.conf             # {"BACKEND": "AI", "LANGUAGE": "PYTHON"}
├── setup.sh                 # optional; installs dependencies (remote only)
├── source/                  # what the candidate starts from
├── ._tests/test_1.py        # a `testCases` class
└── ._course_data/
    ├── course_toc.json      # selects the active test module
    └── feature.md           # the Instructions tab
solution/                    # sibling, never uploaded — the reference solution
```

## Authoring with Claude Code

```bash
codepraxis --install claude-plugin
```

Writes a local plugin into `.codepraxis/claude-plugin/`, then tells you the two
commands to enable it. You get:

- **`/codepraxis:new`** — scaffold a pack from a description
- **`/codepraxis:validate`** — validate and fix what fails, in a loop
- **`pack-authoring` skill** — loads automatically when Claude touches a pack,
  so it already knows the `testCases` contract and the two-fixture rule

Re-run with `--force` to overwrite an existing install.

## Authentication

`--remote` needs a key:

```bash
export CODEPRAXIS_TOKEN=...          # or `codepraxis login` for a stored config
export CODEPRAXIS_API_URL=...        # optional; defaults to the production API
```

## Development

```bash
python3.11 -m pip install -e '.[dev]'
pytest
ruff check src tests scripts
```

The package has **no runtime dependencies**. The harness must run on an author's
machine with nothing but a Python interpreter, so keep it that way — the remote
tier uses `urllib` from the standard library for the same reason.

### Conformance tests

The harness mirrors the production runner's behaviour (`setupCodeBase.py`,
`koro/test_loader.py`, `koro/test_runner.py`). Mirrors drift, so
`tests/conformance/` replays the harness across a corpus of real packs and
asserts the expected verdicts.

That corpus is **private and lives outside this repository**:

```bash
PRAXIS_CONFORMANCE_PACKS=/path/to/question-bank pytest tests/conformance
```

Without the variable the conformance tests skip.

> **Do not vendor packs into this repository.** This package is published
> publicly. No challenge content, no reference solutions, no fixtures derived
> from real questions. Scaffold templates must be written from scratch.
