---
description: Open a CodePraxis question exactly as a candidate would see it
argument-hint: "[question name]"
allowed-tools: Read, Glob, Bash(codepraxis:*)
---

Open `$1` the way a candidate gets it.

This is read-only. Do not edit the question here — if something is wrong, note
it and fix it with `/codepraxis:build` afterwards.

1. Confirm it validates first: `codepraxis validate $1`. There is no point
   opening a question that does not run.

2. Start a container for it. If the question is already published, open its
   preview:

   ```bash
   codepraxis edit <challenge-id> --open
   ```

   If it is not published yet, say so plainly — a pre-publish container needs
   platform support that does not exist yet, so the honest answer today is
   either publish it as a draft first with `/codepraxis:ship`, or inspect the
   files locally.

3. Tell them what to look at, because ten minutes here finds more than any
   amount of reviewing:

   - Read the brief cold. Is the task obvious without asking anyone?
   - Does the starter run before you change anything?
   - How long does setup take before you can type?
   - Run the visible cases. Do they fail for a reason you can act on?
   - Try the obvious wrong approach. Does it get caught?
   - Time yourself on the first real step, and compare it to the plan's budget.

Report what you would change. Then either `/codepraxis:build` to fix it, or
`/codepraxis:ship` if it is ready.
