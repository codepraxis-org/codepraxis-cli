---
description: Validate a CodePraxis pack locally and fix whatever fails
argument-hint: "[pack name or path]"
allowed-tools: Bash(codepraxis validate:*), Read, Edit, Glob, Grep
---

Validate the pack `$1` (or every pack in this repo if no argument was given),
then fix what it reports.

1. Run `codepraxis validate --local $1`.
2. If it passes, say so and stop — do not make changes.
3. If it fails, work through the failures in this order, because earlier ones
   mask later ones:
   - **Harness errors** (`Could not load or instantiate testCases`) — the test
     module does not load. Fix the contract violation first.
   - **Solution failures** — the reference solution should pass everything. A
     failure here means the test is wrong, not the solution.
   - **Starter passing** — the tests do not discriminate. Either `source/`
     contains a working implementation that should be stubbed out, or the
     assertions are too weak to notice. Never "fix" this by weakening the
     solution.
   - **Warnings** — panel row mismatches, missing `RunCaseInputs`.
4. Re-run after each fix. Stop when it passes.

Change the pack — the test file, `source/`, or `solution/`. Never edit the
harness or work around a check.

If the failure is one the local tier flags as unverifiable (a `setup.sh`
dependency, the LLM proxy), say so rather than guessing; it needs
`codepraxis validate --remote`.
