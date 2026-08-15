---
description: Publish a CodePraxis question as a draft and return its link
argument-hint: "[question name]"
allowed-tools: Read, Glob, Bash(codepraxis:*)
---

Publish `$1`.

A published question can be assigned to a real candidate immediately, so this
step is deliberate and it is not yours to decide alone.

## Check first, in this order

1. `codepraxis validate $1` passes locally.
2. `challenges/$1/spec.md` says `status: approved`.
3. A reference solution exists at `challenges/$1/solution/`.
4. They have actually opened it themselves — `/codepraxis:try`. If they have
   not, say so and recommend it before publishing rather than after.

If any of these fail, stop and say which one.

## Then evaluate, before publishing

Run the `question-evaluation` skill — **before** the publish, not after. Once
it is live a bad verdict is a rollback rather than a decision.

If `challenges/$1/evaluation.md` already exists and the pack has not changed
since, read it rather than re-running the simulation; it costs a container run.

Report the verdict in one line. **A poor verdict does not stop the publish** —
it is theirs to weigh. Say what is wrong, say you are publishing anyway if they
confirm, and let them decide.

## Publish as a draft

```bash
codepraxis ship $1
```

The CLI runs the authoritative validation in the real runner image first; a
local pass does not qualify. It publishes as a **draft**, prints the question id
and a URL.

**Give them the URL in your reply.** That link is the whole point of this step —
it is what they send to their team.

## Do not go live on your own

Going live means candidates start receiving it. That is the user's call, not
yours. Tell them the command and stop:

```bash
codepraxis ship $1 --live
```

## Republishing a change

If this question already has an id, pass it — otherwise you create a second copy
instead of a new version, and the original keeps its assignments while the fix
sits somewhere else:

```bash
codepraxis ship $1 --challenge-id <id>
```

Get the id from `codepraxis list` or from `challenges/$1/pack/publish.json`.
