# codepraxis

Author and validate CodePraxis challenge packs from your own repository.

```bash
pip install codepraxis
codepraxis --example                         # see a real challenge, no account needed
codepraxis new my-challenge                  # scaffold one that already validates
codepraxis lint my-challenge                 # static checks, no execution
codepraxis validate --local my-challenge     # run it, fast and advisory
codepraxis --login
codepraxis --publish my-challenge            # validates in the runner, then publishes
codepraxis --list                            # list company questions
codepraxis --edit 123 --open                 # update metadata/open a preview container
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
it does not run `setup.sh` and does not have the image's package set. Anything
it cannot check is reported as a `note` rather than silently passing.
Publishing always requires a remote run.

### Packs that call a model

By default there is no model endpoint locally, so cases that need one are
reported **unverifiable** rather than failed — a pack is not broken just because
your laptop has no LLM proxy. Point it at a real endpoint and they run for real:

```bash
export OPENAI_API_KEY=...              # or --llm-api-key
export OPENAI_BASE_URL=...             # or --llm-base-url
codepraxis validate --local my-challenge
```

Once a key is configured the leniency stops: a model failure is then a real
failure, because it can be judged.

## Try it first

```bash
codepraxis --example
```

Starts a throwaway container with the featured challenge already cloned into it
and prints a URL. That is exactly what a candidate sees. No login, no account,
nothing recorded as an attempt. Add `--open` to launch it in your browser.

## Starting a new pack

```bash
codepraxis new my-challenge
codepraxis validate --local my-challenge     # → PASSED
```

The generated pack is complete and already passing — solution passes, starter
fails. Edit `._course_data/feature.md`, `source/`, `._tests/test_1.py` and
`../solution/` to make it yours.

## Two kinds of checking

| Command | Runs | Cost |
|---|---|---|
| `codepraxis lint` | Static rules over the files | milliseconds, no execution |
| `codepraxis validate` | The tests, against both fixtures | seconds (local) or ~1 min (remote) |

`lint` never imports pack code, so it is safe on a pack you did not write and
fast enough for every save. It catches things that otherwise only surface inside
a container — a two-argument `testCases.__init__`, zero-padded case names, a
`solution/` directory nested inside the pack, LaTeX in the Instructions brief.
`validate` runs it automatically first and stops if it finds an error, because
executing a pack whose class cannot be constructed only produces a confusing
traceback.

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

Three verdicts: **PASSED**, **FAILED**, and **INCONCLUSIVE** (this tier lacked
the infrastructure to judge it — not a failure, and it does not fail the
command). `--json` always emits a single document with a `packs` array, however
many packs ran.

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

- **`/codepraxis:new`** — design, build, validate, publish and return a URL
- **`/codepraxis:validate`** — validate and fix what fails, in a loop
- **`pack-authoring` skill** — loads automatically when Claude touches a pack,
  so it already knows the `testCases` contract and the two-fixture rule

Re-run with `--force` to overwrite an existing install.

## Authentication

```bash
codepraxis --login
```

Prompts for an API key (hidden input), verifies it against the platform, and
stores it at `~/.config/codepraxis/config.json` with `0600` permissions. It
prints which company the key publishes as — worth reading, because that is what
every publish is scoped to.

In CI, skip the prompt:

```bash
export CODEPRAXIS_TOKEN=...
export CODEPRAXIS_API_URL=...        # optional; defaults to the production API
```

## Publishing

```bash
codepraxis --publish my-challenge            # draft, with confirmation
codepraxis --publish my-challenge --live     # straight to candidates
codepraxis --publish my-challenge --yes      # non-interactive, for CI
```

Publishing is deliberately strict, because a published challenge can be
assigned to candidates immediately:

- **Remote validation runs first.** Local results never qualify. Reuse an
  earlier passing run with `--validation-run-id` if you have one.
- **A reference solution is required.** It is what proves the challenge is
  solvable.
- **It publishes as a draft** unless you pass `--live`.
- **The company comes from your API key.** The CLI never sends a company id —
  ownership is derived server-side, so a compromised or mistyped client can't
  publish into someone else's catalog.

You'll be shown the company and asked to confirm before anything is created.
When the platform can start a preview container, `--publish` prints that URL so
you can inspect the question immediately.

## Company catalog

```bash
codepraxis --list
codepraxis --edit 123 --title "Debug webhook delivery" --status draft
codepraxis --edit 123 --open
```

`--list` shows the questions owned by your API key's company, including drafts.
`--edit` updates question metadata and returns a container URL for inspection.
Code changes still go through the pack workflow: edit locally, validate, and
publish a new version.

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
