---
description: Design, build, validate, publish, and preview a CodePraxis question
argument-hint: "<what the challenge should test>"
allowed-tools: Bash(codepraxis validate:*), Bash(codepraxis ship:*), Read, Write, Edit, Glob
---

Create and publish a new CodePraxis question for: **$ARGUMENTS**

Build it in this order. Do not skip the design step, and do not claim the
question is done until publish returns a URL.

1. **Decide the question architecture.** Write down what skill this tests, the
   expected task shape, the test cases you will need, and roughly how much code
   the candidate should write. Prefer a realistic engineering task with one
   obvious entry point, concrete sample input, and an output contract a test can
   check automatically. Not a toy exercise, not a puzzle.

2. **Implement the pack** under `challenges/<slug>/`:
   - `metadata.json` — a unique snake_case `name`
   - `backend.conf` — `BACKEND` and `LANGUAGE`
   - `source/` — the minimal stub the grader calls, plus a `README.md` saying
     what is broken and how to run it. No working implementation.
   - `._tests/test_1.py` — the `testCases` class
   - `._course_data/course_toc.json` and `feature.md` — the candidate brief
   - `setup.sh` at the pack root if dependencies are needed

3. **Write the reference solution** in `challenges/<slug>/../solution/` — a
   sibling of the pack, never inside it.

4. **Validate without asking the user to choose tiers.** Run
   `codepraxis validate --local <slug>` and iterate until the solution passes
   everything and the starter passes nothing. Then publish with
   `codepraxis ship <slug>`; the CLI runs the authoritative remote
   validation before it publishes.

5. **Publish and return the URL.** When `codepraxis ship <slug>` succeeds,
   copy the container URL from its output into your final answer so the user can
   open the question and inspect it.

Consult the `pack-authoring` skill for the `testCases` contract. The two
mistakes worth checking before you finish: a starter that already passes, and a
two-argument `__init__`.
