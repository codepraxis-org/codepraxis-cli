---
description: Scaffold a new CodePraxis challenge pack from a description
argument-hint: "<what the challenge should test>"
allowed-tools: Bash(codepraxis validate:*), Read, Write, Edit, Glob
---

Create a new CodePraxis challenge pack for: **$ARGUMENTS**

Build it in this order, and validate before you claim it is done.

1. **Decide the shape.** A realistic engineering task with one obvious entry
   point, concrete sample input, and an output contract a test can check
   automatically. Not a toy exercise, not a puzzle.

2. **Write the pack** under `challenges/<slug>/`:
   - `metadata.json` — a unique snake_case `name`
   - `backend.conf` — `BACKEND` and `LANGUAGE`
   - `source/` — the minimal stub the grader calls, plus a `README.md` saying
     what is broken and how to run it. No working implementation.
   - `._tests/test_1.py` — the `testCases` class
   - `._course_data/course_toc.json` and `feature.md` — the candidate brief
   - `setup.sh` at the pack root if dependencies are needed

3. **Write the reference solution** in `challenges/<slug>/../solution/` — a
   sibling of the pack, never inside it.

4. **Validate**: `codepraxis validate --local <slug>`. Iterate until the
   solution passes everything and the starter passes nothing.

Consult the `pack-authoring` skill for the `testCases` contract. The two
mistakes worth checking before you finish: a starter that already passes, and a
two-argument `__init__`.
