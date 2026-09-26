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

## Coding questions: the loop

Everything runs in the question's container, never on this machine. The
container is an ordinary candidate container, so what works there works for
candidates.

1. **Write the files** that `output.md` lists, locally under `challenges/$1/`.
2. **Push:** `codepraxis push $1`.
   - The first push saves the question as a draft (so the platform can load
     it), opens it in a container, waits for `setup.sh`, and prints how it
     went. A cold start can take a few minutes.
   - Later pushes send only the files that changed and remove files that exist
     only in the container. A changed `setup.sh` is run again.
3. **Try it:** `codepraxis exec $1 "<command>"` runs a command in the workspace
   as the candidate user (add `--timeout 600` for slow ones). Use it to run the
   starter, query a database, check a file. `exec` pushes first.
4. **Run the visible cases:** `codepraxis test $1 --visible`. This is the
   candidate's Run button; it prints each case's Input, Expected and Output.
5. Fix and repeat from step 2. Each loop takes seconds.

When something fails, read the log before guessing:

| Command | Shows |
|---|---|
| `codepraxis logs $1 setup` | `setup.sh`'s output and exit code |
| `codepraxis logs $1 grader` | The grader's own output: a case that raised, a timeout, a grader that didn't load |
| `codepraxis logs $1 exec` | Every `exec` command and its output |
| `codepraxis logs $1 run` | The last Run's cases, as the candidate's panel shows them |
| `codepraxis logs $1 results` | The last Submit's full result |

If you changed a file inside the container (with `exec`), bring it back with
`codepraxis pull $1 [path]`; the local files are what gets published.

The container is reclaimed after 30 idle minutes; the next push opens a new
one. `codepraxis stop $1` hands it back early.

## Interview questions

There is no container. Write `question.json` and put the files it shows in
`entities/`. Run `codepraxis test $1`: it uploads the files (again only when
they change) and runs the platform's checks. Fix every blocker.

## Before you stop

- The solution does the real work. Nothing hardcodes an expected value.
- The starter runs and fails because work is missing, not because of a syntax
  error or a bad import.
- Every file the brief names exists in `source/`.
- No hidden case tests a rule the brief never states.
- The visible cases finish in seconds.

Report only when the visible cases pass in the container (or, for an
interview, when `test` shows no blockers), or when you are genuinely stuck. Do
not narrate each fix. Then: `/codepraxis:test $1`.
