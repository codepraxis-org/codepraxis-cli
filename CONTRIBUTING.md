# Contributing

## The content boundary

This package is published to PyPI. Anything committed here becomes public.

**Never commit:**

- Challenge packs, questions, or reference solutions
- Test fixtures derived from real question content
- API keys, storage connection strings, registry credentials
- Runner image internals (`koro`, `perry`, proctoring, evaluation logic)

The CLI deliberately contains nothing proprietary: it runs the *author's* tests
against the *author's* code. Keeping that true is what makes public
distribution safe. If a change would put platform internals in this repo, the
change belongs on the server instead.

Test fixtures must be synthetic and written from scratch. The conformance suite
reads a private corpus through `PRAXIS_CONFORMANCE_PACKS` and skips when unset.

## Architecture

Layers, innermost first. Dependencies point inward only.

| Layer | Responsibility | Must not |
|---|---|---|
| `domain/` | Data and the mirrored runner contract | Touch the filesystem, subprocesses, or the network |
| `packio/` | Filesystem → `Pack` | Import or execute pack code |
| `validation/` | Static rules over a `Pack` | Execute pack code |
| `execution/` | Run packs, produce `RunResult` | Print anything |
| `reporting/` | Render a `RunResult` | Read the filesystem |
| `commands/` | Orchestrate the above | Instantiate concrete executors or reporters |
| `cli.py` | Parse args, inject dependencies | Contain logic |

The load-bearing rule: **every executor returns the same `RunResult`.** Local,
remote and docker tiers are interchangeable, so reporting and exit codes are
written once.

### Adding things

- **A lint rule** — a new file in `validation/rules/`, registered. No edits elsewhere.
- **A backend** (`backend.conf`'s `BACKEND`) — a new `BackendAdapter` in
  `execution/local/backends.py`, registered. Declare honestly whether the local
  tier can run it; a backend that needs container-only infrastructure should set
  `locally_supported = False` rather than emit false failures.
- **An output format** — a new class satisfying `Reporter`.
- **An execution tier** — a new class satisfying `Executor`.

### Mirroring the runner

`domain/contract.py` mirrors constants and semantics from the runner image and
records provenance per constant. When you change it:

1. Cite the runner source for the new behaviour.
2. Add a conformance case that would fail under the old behaviour.

Where the local tier cannot reproduce the runner, emit a
`Severity.UNVERIFIABLE` diagnostic. Never guess — a false pass locally is worse
than no local check at all, because it costs an author a full remote cycle to
discover.
