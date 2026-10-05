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

## MCQ banks

```bash
codepraxis test $1
```

It runs locally, nothing is uploaded: the platform's rules (type, difficulty 1
to 5, 2 to 6 options, text or an image per option, `correct` positions, one
correct for `single_select`, no repeated option text or keys, every image a
png/jpg/jpeg/gif/webp under `images/`), warnings for unknown keys and for any
difficulty with fewer than 3 questions, and the count per difficulty. It writes
`preview.md` and exits non-zero on any error.

Then read `preview.md` as a reviewer: is the ✅ option right, would an expert
agree it is the only best one, does each distractor come from a real mistake, does
anything in the wording give the key away, is each image needed to answer, does
each difficulty match the table in the `question-mcq` skill. Fix `bank.json` and
test again.

## Templates

```bash
codepraxis test $1
```

It resolves every ref in `template.json` (a local folder must have been pushed),
checks each question or bank is in the library this key can use and not retired,
that no question appears twice, that code review comes with a coding round, and
that each round is within the platform's limits. It prints each round's questions
with their status and minutes, each round's minutes and the total, and lists the
questions still in draft with `!`: allowed in a draft template, but they must be
published in the dashboard before the template is. It exits non-zero on any `✗`.

## Then

Fix what the report shows and rerun until it is clean. Then say in two lines
what each hidden case catches (or, for an interview, what each probe tests; for
an MCQ bank, the count per difficulty and what the questions cover),
and hand off: `/codepraxis:ship $1`. For a template, give the minutes per round
and the total, and the questions still in draft.
