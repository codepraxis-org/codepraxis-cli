# codepraxis

Build real-world coding assessments from your own repository.

```bash
pip install codepraxis

codepraxis example                    # see a real question, no account needed
codepraxis login
codepraxis install claude-plugin      # design and build questions with Claude
codepraxis                            # where am I, what is next
codepraxis guide                      # the whole thing explained
```

## What this is

CodePraxis gives candidates real engineering work instead of algorithm puzzles.
They open a browser, land in a real editor in a real container, and fix or build
something. Hidden tests decide whether it worked.

This CLI is how you make those questions — keeping them in your own git
repository, editing them with your own tools, and checking them before they
reach anyone.

A question is a directory: starter code, a test module, instructions.

## The steps

```
plan  →  build  →  try  →  ship
```

| | |
|---|---|
| **plan** | Talk it through, agree what to test. No code yet. |
| **build** | Claude writes the question, tests it, and fixes what fails. |
| **try** | Open it exactly as a candidate would. Nothing published. |
| **ship** | Publish as a draft, then go live. |
| **edit** | Pull one back down to change it later. |

Run `codepraxis` at any point to see where you are and what to type next.

## Working with Claude Code

```bash
codepraxis install claude-plugin
```

Writes a local plugin into `.codepraxis/claude-plugin/`, then prints the two
commands that enable it. You get:

- **`/codepraxis:plan`** — design a question: what it tests, what the candidate
  starts from, the cases, how long it should take
- **`/codepraxis:build`** — write it, run it, repair what fails
- **`/codepraxis:validate`** — check an existing question and fix it
- a **pack-authoring skill** that loads automatically when Claude touches a
  question, so it already knows the contract

Re-run with `--force` to overwrite an existing install.

Planning refuses to proceed on a question a model can solve from the brief
alone. Candidates have an AI agent in the container, so a question that is one
prompt away from done measures nothing.

## Doing it by hand

The CLI works without Claude:

```bash
codepraxis new my-question                 # scaffold one that already passes
codepraxis lint my-question                # static checks, no execution
codepraxis validate my-question            # run it, fast and advisory
codepraxis ship my-question                # validates in the runner, then publishes
codepraxis list                            # your company's questions
codepraxis edit 214 --open                 # update details, open a preview
codepraxis ship my-question --challenge-id 214   # publish an edit, not a duplicate
```

## Two kinds of checking

| Command | Runs | Speed | Counts? |
|---|---|---|---|
| `codepraxis lint` | Static rules over the files | milliseconds | Advisory |
| `codepraxis validate --local` | Pure-Python harness on your machine | seconds | No — advisory |
| `codepraxis validate --remote` | The real runner image, on CodePraxis | ~1 min | **Yes — gates publish** |

`lint` never imports your code, so it is safe on a question you did not write
and fast enough for every save.

`--local` reproduces how the runner loads, orders and scores a question, so it
catches most mistakes in the inner loop. It is **not** the container: it does
not run `setup.sh` and does not have the image's package set. Anything it
cannot check is reported as a `note` rather than silently passing. Publishing
always requires a remote run.

## The rule that matters most

Every question is validated twice:

- **solution** — `source/` overlaid with `solution/`. Must pass everything.
- **starter** — `source/` alone. Must *fail*.

The starter run is the one authors forget. A question whose starter already
passes has tests that do not discriminate, and every candidate scores full
marks.

```
webhook-debug  (local)
  solution  18/18 passed
  starter   0/18 passed
  PASSED  8.9s
```

Three verdicts: **PASSED**, **FAILED**, and **INCONCLUSIVE** (this tier lacked
the infrastructure to judge it — not a failure, and it does not fail the
command). `--json` always emits a single document with a `packs` array.

## Questions that call a model

By default there is no model endpoint locally, so cases that need one are
reported **unverifiable** rather than failed — a question is not broken just
because your laptop has no LLM proxy. Point it at a real endpoint and they run
for real:

```bash
export OPENAI_API_KEY=...              # or --llm-api-key
export OPENAI_BASE_URL=...             # or --llm-base-url
codepraxis validate my-question
```

Once a key is configured the leniency stops: a model failure is then a real
failure, because it can be judged.

## Layout

```
challenges/my-question/
├── spec.md                  the plan — what this tests and why
├── publish.json             title, difficulty, time limit, tech stack
├── metadata.json            {"name": "..."} — becomes the workspace directory
├── backend.conf             {"BACKEND": "AI", "LANGUAGE": "PYTHON"}
├── setup.sh                 optional; installs dependencies (remote only)
├── source/                  what the candidate starts from
├── ._tests/test_1.py        a `testCases` class
└── ._course_data/
    ├── course_toc.json      selects the active test module
    └── feature.md           the Instructions tab
solution/                    sibling, never uploaded — the reference solution
```

`setup.sh` runs on **every** container load, not once at build time. Pin your
versions: an unpinned install resolves to whatever is current that day, and a
breaking release later fails during a candidate's assessment.

## Authentication

```bash
codepraxis login
```

Prompts for an API key (hidden input), verifies it, and stores it at
`~/.config/codepraxis/config.json` with `0600` permissions. It prints which
company the key publishes as — worth reading, because that is what every
publish is scoped to.

In CI, skip the prompt:

```bash
export CODEPRAXIS_TOKEN=...
export CODEPRAXIS_API_URL=...        # optional; defaults to the production API
```

## Publishing

```bash
codepraxis ship my-question            # draft, with confirmation
codepraxis ship my-question --live     # straight to candidates
codepraxis ship my-question --yes      # non-interactive, for CI
```

Publishing is deliberately strict, because a published question can be assigned
to candidates immediately:

- **Remote validation runs first.** Local results never qualify. Reuse an
  earlier passing run with `--validation-run-id`.
- **A reference solution is required.** It is what proves the question is
  solvable.
- **It publishes as a draft** unless you pass `--live`.
- **The company comes from your API key.** The CLI never sends a company id —
  ownership is derived server-side, so a compromised or mistyped client cannot
  publish into someone else's catalog.

### Publishing an edit

Changing the *content* of a question means re-publishing it. Pass the id, or
you get a second copy:

```bash
codepraxis ship my-question --challenge-id 214
```

With `--challenge-id` the platform adds a new version and keeps the question's
id, assignments and history.

### Deleting

```bash
codepraxis delete 214
```

Asks first, and the platform refuses once the question has been assigned to
anyone — deleting it then would orphan attempts and reports. To take an
assigned question out of circulation, set it back to draft with
`codepraxis edit 214 --status draft`.

## Older command forms

`--publish`, `--list`, `--edit`, `--delete`, `--login`, `--install` and
`--example` still work. They are hidden from help and print a pointer to the
subcommand that replaced them.

## Development

```bash
python3.11 -m pip install -e '.[dev]'
pytest
ruff check src tests scripts
```

The package has **no runtime dependencies**. The harness must run on an
author's machine with nothing but a Python interpreter, so keep it that way —
the remote tier uses `urllib` from the standard library for the same reason.

See [ARCHITECTURE.md](ARCHITECTURE.md) for how the pieces fit together.

### Conformance tests

The harness mirrors the production runner's behaviour (`setupCodeBase.py`,
`koro/test_loader.py`, `koro/test_runner.py`). Mirrors drift, so
`tests/conformance/` replays the harness across a corpus of real questions and
asserts the expected verdicts.

That corpus is **private and lives outside this repository**:

```bash
PRAXIS_CONFORMANCE_PACKS=/path/to/question-bank pytest tests/conformance
```

Without the variable the conformance tests skip.

> **Do not vendor questions into this repository.** This package is published
> publicly. No challenge content, no reference solutions, no fixtures derived
> from real questions. Scaffold templates must be written from scratch.
