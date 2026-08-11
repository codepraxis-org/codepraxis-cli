---
description: Change an existing CodePraxis question and publish a new version
argument-hint: "<question name or id> <what to change>"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(codepraxis:*)
---

Change an existing question: **$ARGUMENTS**

## Work out what kind of change this is

**Details only** — title, description, difficulty, time limit, attempts, tech
stack. No code changes. One command, no rebuild:

```bash
codepraxis edit <id> --title "..." --difficulty 2 --max-time 90
```

**The question itself** — the brief, the starter, the tests, the solution. That
means editing the pack and publishing a new version. Continue below.

## Before you change anything, read the plan

Open `challenges/<name>/spec.md`. It records what the question was *supposed* to
test and why the cases are what they are. Changing a question without reading it
is how a question quietly stops measuring what someone chose it for.

If the change contradicts the plan — a different signal, a different duration,
a different contract — **update the spec first and get it re-approved**:

```bash
codepraxis approve <name>
```

Small fixes that do not change intent (a typo in the brief, a flaky assertion,
a clearer error message) do not need re-approval. Use judgement, and say which
you decided it was.

## If you do not have the question locally

There is no download yet. If the pack is not in this repo, say so plainly rather
than reconstructing it from the container — a rebuilt approximation published
over a real question is worse than not fixing it. `codepraxis list` shows what
exists; the pack has to come from wherever it was authored.

## Make the change

Edit the pack, then validate and re-check the things validation cannot:

```bash
codepraxis validate <name>
```

The solution must still pass everything, the starter must still fail, and any
case you touched must still discriminate. If you changed the brief, confirm
every file it names still exists in `source/`.

## Publish as a new version

Always pass the id. Without it you create a duplicate question, and the original
keeps its assignments and history while your fix lives somewhere else:

```bash
codepraxis ship <name> --challenge-id <id>
```

Candidates who already took the earlier version keep their results. Give them
the URL in your reply.
