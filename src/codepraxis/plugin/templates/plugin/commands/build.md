---
description: Build a CodePraxis question inside its live container
argument-hint: "<question slug>"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(codepraxis:*)
---

Build the question `$1`.

Read `challenges/$1/spec.md` and follow it; do not redesign it. If the spec is
wrong about something, say so and ask. Read the output file for its type:
`question-coding/output.md` for `coding` and `coding-ai` questions,
`question-interview/output.md` for `interview`. It lists the files to produce
and the rules they follow.

## API key

The CLI reads the key from `CODEPRAXIS_API_KEY`. If a command says the key is
missing, ask the author: "Please give your CodePraxis API key", then set it for
the session and carry on.

## Reading the CLI's output

Every command prints each stage as it goes: `→` when a stage starts, `✓` or `✗`
when it ends (with how long it took), `…` lines while it waits (with what it is
waiting for and the latest thing it saw), `!` for a warning, and a final
`Next:` line. Relay the stage the author is at when a command is slow, and read
the `✗` line and the log it points to before changing anything.

## Coding questions

Everything runs in the question's container, never on this machine. It is an
ordinary candidate container, so what works there works for candidates.

1. **Write the files** that `output.md` lists, locally under `challenges/$1/`.
2. **Push:** `codepraxis push $1` saves the question to the platform. The
   first push creates it as a draft; later pushes update the same draft.
3. **Launch:** `codepraxis launch $1` opens it in a container, the way the
   website does, and waits for `setup.sh`. A cold start can take a few
   minutes; `setup.sh` itself must finish within 2 minutes, or launch stops
   with its last lines. It prints the container's URL: the candidate's view.
4. **Try it:** `codepraxis exec $1 "<command>"` runs a command in the
   workspace as the candidate user (`--timeout 600` for slow ones). Use it to
   run the starter, query a database, check a file.
5. **Run the visible cases:** `codepraxis test $1 --visible`, the candidate's
   Run button. It prints each case's Input, Expected and Output.
6. Edit and repeat 4 and 5. `exec` and `test` first send the files you changed
   to the container, so each loop takes seconds; there is no need to push or
   launch again. A changed `setup.sh` is rerun, within the same 2 minutes.
7. **Push** again whenever you want the platform's copy to match.

When something fails, read the log before guessing:

| Command | Shows |
|---|---|
| `codepraxis logs $1 setup` | `setup.sh`'s output and exit code, both runs (the candidate's, and root's prefixed `setup.sh (root):`) |
| `codepraxis logs $1 grader` | The grader's own output: a case that raised, a timeout, a grader that didn't load |
| `codepraxis logs $1 exec` | Every `exec` command and its output |
| `codepraxis logs $1 run` | The last Run's cases, as the candidate's panel shows them |
| `codepraxis logs $1 results` | The last Submit's full result |

Credentials are replaced by `[redacted]` in everything the container returns.

The container is reclaimed after 30 idle minutes; `launch` again opens a new
one. `codepraxis stop $1` hands it back early. To start from what is saved on
the platform, `codepraxis pull $1` (or `codepraxis pull <id>`) overwrites the
local files, solution included.

## Interview questions

There is no container. Write `question.json` and put the files it shows in
`entities/`. Run `codepraxis test $1`: it uploads new or changed files and runs
the platform's checks. Fix every blocker, then `codepraxis push $1`.

## Before you stop

- The solution does the real work. Nothing hardcodes an expected value.
- The starter runs and fails because work is missing, not because of a syntax
  error or a bad import.
- Every file the brief names exists in `source/`.
- No hidden case tests a rule the brief never states.
- The visible cases finish in seconds, and `setup.sh` in under 2 minutes.

Report only when the visible cases pass in the container (or, for an
interview, when `test` shows no blockers), or when you are genuinely stuck. Do
not narrate each fix. Then: `/codepraxis:test $1`.
