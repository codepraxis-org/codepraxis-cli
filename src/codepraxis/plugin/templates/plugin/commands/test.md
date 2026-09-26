---
description: Test a CodePraxis question the way a candidate will meet it
argument-hint: "<question slug>"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(codepraxis:*)
---

Test the question `$1`.

```bash
codepraxis test $1
```

## Coding questions

This pushes the current files, then runs the candidate's Submit twice in the
container:

1. **Starter:** the workspace as a candidate gets it. Every **hidden** case must
   fail.
2. **Solution:** `solution/` written over the workspace. **Every** case must
   pass. The starter is put back afterwards, even if something failed.

It prints each case's result, with its Input, Expected and Output, and ends
with one line per check:

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
| `setup.sh failed` | The candidate would see "Setup Failed" | `codepraxis logs $1 setup`; fix `setup.sh` |

Visible cases may pass on the starter when the question is a debug question
whose defects only show in hidden cases. Say so in the report rather than
"fixing" it.

## Interview questions

`test` uploads the files in `entities/` that are new or changed, then runs the
same checks the website uses: the fields, the probe tree, the answer key, and
that every entity can be read. It lists each **blocker** and **warning** with
its fix, and exits non-zero if there is any blocker. The website's Publish
button only refuses unreadable entities, so this is where the rest are caught.

## Then

Fix what the report shows and rerun until it is clean. Then say in two lines
what each hidden case catches (or, for an interview, what each probe tests),
and hand off: `/codepraxis:ship $1`.
