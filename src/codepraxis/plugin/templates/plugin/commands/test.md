---
description: Test a CodePraxis question the way a candidate will meet it
argument-hint: "<question slug>"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(codepraxis:*)
---

Test the question `$1`.

## Coding questions

Start from a clean container, exactly as a candidate would, then run the full
check:

```bash
codepraxis push $1
codepraxis launch $1 --fresh
codepraxis test $1
```

`launch --fresh` hands back the old container and loads the pushed question in
a new one, so `setup.sh` runs from scratch (and must finish in 2 minutes). If
the platform restores your earlier workspace into it, `launch` puts the
question's files back before `test` runs.
`test` then runs the candidate's Submit twice:

1. **Starter:** the workspace as a candidate gets it. Every **hidden** case must
   fail.
2. **Solution:** `solution/` written over the workspace. **Every** case must
   pass. The starter is put back afterwards, even if something failed.

It prints each case with its Input, Expected and Output, and ends with:

```
✓ Starter fails every hidden case.
✓ Solution passes every case.
```

It exits non-zero when either check fails. Hidden cases are the ones after the
first `self.RUN`.

| What you see | What it means | What to do |
|---|---|---|
| Solution fails a case | The question can't be passed | Fix the solution or the case |
| Starter passes a hidden case | The case doesn't test anything the starter lacks | Make `source/` fail it, or cut the case |
| Two hidden cases fail on the starter with the same output | One is decoration | Merge or cut one |
| "The grader produced no cases" | The grader itself broke | `codepraxis logs $1 grader` |
| `setup.sh failed` or "still running after 120 seconds" | The candidate would see "Setup Failed", or wait too long | `codepraxis logs $1 setup`; fix `setup.sh` |
| `! setup.sh has no set -euo pipefail` | A failing step would go unnoticed | Add it as the first line |

Visible cases may pass on the starter when the question is a debug question
whose defects only show in hidden cases. Say so in the report rather than
"fixing" it.

## Interview questions

```bash
codepraxis test $1
```

It uploads the files in `entities/` that are new or changed, then runs the same
checks the website uses: the fields, the probe tree, the answer key, and that
every entity can be read. It lists each **blocker** and **warning** with its
fix, and exits non-zero if there is any blocker. The website's Publish button
only refuses unreadable entities, so this is where the rest are caught.

## Then

Fix what the report shows and rerun until it is clean. Then say in two lines
what each hidden case catches (or, for an interview, what each probe tests),
and hand off: `/codepraxis:ship $1`.
