---
description: Build an approved CodePraxis question and fix what fails
argument-hint: "[question name]"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(codepraxis:*)
---

Build the question `$1` from its approved plan.

## Before anything else

Read `challenges/$1/spec.md`. If it does not exist, or its frontmatter does not
say `status: approved`, **stop**. Tell them to run `/codepraxis:plan` first, or
`codepraxis approve $1` if the plan is already written. Do not build from an
unapproved plan, and do not offer to approve it yourself — approval is theirs.

The spec is the specification. Do not redesign it while implementing. If you hit
something it got wrong, say so and ask, rather than quietly deciding.

## Scaffold, then fill in

```bash
codepraxis new $1
```

That writes a complete, already-passing question so you start from something
green:

```
challenges/$1/
  spec.md
  pack/
    metadata.json      backend.conf      setup.sh
    source/            what the candidate starts from
    ._tests/test_1.py  the testCases class
    ._course_data/     course_toc.json and feature.md
  solution/            the reference answer, never uploaded
```

Then replace the placeholder content with the real question:

- **`pack/._course_data/feature.md`** — the brief. Scenario, exact invocation,
  output contract, a worked example, and what is evaluated. Precise about the
  contract, silent about the approach.
- **`pack/source/`** — the starting state the spec describes, plus a README
  saying what is broken and how to run it. No working implementation.
- **`pack/._tests/test_1.py`** — the case table from the spec, in order, with
  the visible ones first.
- **`solution/`** — the reference answer. It overlays `source/`, so mirror those
  paths.
- **`pack/setup.sh`** — only if dependencies are needed, with pinned versions.

The `pack-contract` skill has the `testCases` rules. Follow it exactly; those
constraints come from the runner, not from taste.

## Then argue with your own work

Run `codepraxis validate $1` and iterate until it passes. Then check the things
validation cannot, and fix what you find:

- **Does the solution actually solve the problem?** If it pattern-matches the
  test inputs — hardcoding an expected number or name — it proves nothing about
  whether the question is solvable. Rewrite it to do the real work. This is the
  single most common way a question ships broken.
- **Does the starter fail for the right reason?** It must fail because the work
  is missing, not because of a syntax error or a bad import.
- **Does every case discriminate?** If two fail for the same reason, cut one.
- **Does the brief match the files?** Every path it names must exist in
  `source/`. Renaming a file and leaving the brief pointing at the old name is
  a real bug that reaches candidates.
- **Does any hidden case test something the brief never states?**
- **Do the visible cases run in seconds?** They are re-run constantly.

Only report to the user when it passes, or when you are genuinely stuck. Do not
narrate each fix.

## Then evaluate it

Validation says it runs. It does not say the question is any good.

Invoke the `question-evaluation` skill. The pack exists now, so the full review
applies and the simulation is measurable: a **clean subagent** — not you, you
have seen the solution — writes an attempt to `challenges/$1/.attempt/`, and
`codepraxis validate $1 --fixture attempt` scores it against the real cases.

That prints `MEASURED the attempt passed N/M cases`. Fewer is better: it means
the question is not answerable from the brief alone. If a model passes most of
them, say so plainly — the question needs work, whatever validation says.

Write `challenges/$1/evaluation.md`, and update the spec's `difficulty` and
`ai_solvability` from what was measured rather than what was guessed.

## When it passes

Say what was built, what each case catches, and how long you expect it to take.
Give the evaluation verdict in one line. Then hand over:

```
/codepraxis:try $1
```

Do not publish. Shipping is a separate, deliberate step.
