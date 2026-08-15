---
description: Judge whether a CodePraxis question is any good, and how far a model gets
argument-hint: "[question name]"
allowed-tools: Read, Write, Glob, Grep, Task, Bash(codepraxis:*)
---

Evaluate `$1`.

`codepraxis validate` answers *does it run*. This answers *is it worth asking*
— whether the cases discriminate, whether the time budget holds, and how far a
model gets from the brief alone.

Follow the `question-evaluation` skill. It has the checklist, the clean-context
rule for the simulation, and the report format.

## Run what the evidence supports

Look at what exists before deciding what to check:

- **`spec.md` only** — review the design. The simulation can attempt the draft
  brief, but there is nothing to run it against yet.
- **A built pack** — the full review, plus a measured simulation via
  `codepraxis validate $1 --fixture attempt`.

Do not report on checks you could not perform. Say what you skipped and why.

## The simulation must not be run by you

You may have written this question, or read its solution earlier in the
session. Either way you cannot attempt it cold. Dispatch a **subagent** with
only the brief and `source/` — never the spec, never `solution/`, never this
conversation.

Its attempt goes in `challenges/$1/.attempt/`, which is gitignored and never
uploaded.

## Write the report, then get out of the way

Write `challenges/$1/evaluation.md` and summarise it in two or three lines.

**Findings never block.** Say plainly if the question is not ready and why. The
decision to ship anyway belongs to the author — a hard block would just teach
people to skip this step.
