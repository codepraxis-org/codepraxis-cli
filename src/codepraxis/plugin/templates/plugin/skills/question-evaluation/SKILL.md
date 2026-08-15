---
name: question-evaluation
description: Use when judging whether a CodePraxis question is any good — after planning it, after building it, or before shipping it. Covers the review checklist, how to measure whether a model can answer it from the brief alone, and how to write the report. For what makes a question worth asking see question-design; for the runner's rules see pack-contract.
---

# Judging a question

`codepraxis validate` answers *does it run*. This answers *is it worth asking*.

Two halves. The review is cheap and always runs. The simulation costs a
container run and answers the one question nobody can answer by reading.

**Findings warn, they never block.** Say plainly that a question is not ready
and why, then stop. Whether to ship anyway is the author's call — you are not
in a position to overrule a human on a judgement like this, and a hard block
would only teach people to skip the step.

## What evidence exists when

Run the checks you have evidence for; skip the rest silently rather than
guessing.

| | after plan | after build | before ship |
|---|---|---|---|
| Review — signal, cases, time, contract | ✅ | ✅ | ✅ |
| Review — solution, starter, brief/files | spec only | ✅ | ✅ |
| Simulation | **no** | ✅ | reuse the report |

**The simulation does not run during planning.** It takes minutes, and planning
is a conversation — making someone wait on a background agent mid-discussion is
worse than the estimate it replaces. There is also no pack yet, so the best it
could produce is a guess about a brief, while the same work after build is
scored by the question's real tests.

At ship, reuse `evaluation.md` if the pack has not changed since. Re-running
costs a container run to re-learn what you already know.

## The review

Work through these against `spec.md` and, once it exists, the pack. Report what
fails and why it matters — not a score.

**Signal.** One falsifiable sentence, and the question actually tests it. If
the spec says "tests Python" there is no question yet, only a topic.

**Every case discriminates.** Two cases failing for the same reason means one
is decoration. Cases exist to separate people; a case that separates nobody is
runtime the candidate pays for on every submit.

**A gradient, not a cliff.** If everything fails until the last piece lands,
someone who did most of the work scores zero and you learn nothing about them.
A first pass should be reachable early.

**Time budget.** The slices sum to the stated duration. Setup cost is paid on
*every* container load, not once.

**Contract precise, approach silent.** The brief must say exactly what "done"
looks like — invocation, output shape, error behaviour — and must not hint at
how. Vagueness about the contract is a bug; vagueness about the approach is
the point.

Once the pack exists, four more that only the files can answer:

**The solution does the work.** A reference solution that hardcodes an expected
value passes validation and proves nothing about whether the question is
solvable. This is the most common way a question ships broken — check it
first.

**The starter fails for the right reason.** Missing work, not a syntax error or
a bad import.

**The brief names files that exist.** Rename something in `source/` and forget
the brief, and every candidate hits it.

**No hidden case tests something unstated.** That is a gotcha, not an
assessment.

## The simulation

The empirical half: can a model answer this from the brief alone?

> **It must run in a clean context.** If the same context that designed or
> built the question also attempts it, it already knows the answer and the
> number is worthless — worse than worthless, because it looks like evidence.
> Use a subagent. Give it the brief and `source/`, nothing else. Never the
> spec, never `solution/`, never the conversation.

Run it **once**, and wait for it. One subagent, one attempt, then report. Do not
chain a second one to test a revised framing in the same pass — that is another
several minutes with nobody told why, and the revision can be measured on the
next build instead.

**After build** it is measurable:

1. Subagent writes its attempt to `challenges/<slug>/.attempt/`
2. `codepraxis validate <slug> --fixture attempt`
3. Read the per-case results

That prints `MEASURED the attempt passed N/M cases`. Fewer is better.

| Result | Reading |
|---|---|
| Passes most cases | Too easy. The brief is doing the work — bury a fact the model cannot guess, or move from authoring to debugging |
| Passes some | The target. A model should accelerate a candidate, not replace them |
| Passes none | Usually the brief is unclear rather than the question hard. Look again before celebrating |

**What it does not measure.** A model finishing in two minutes says nothing
about whether a person takes ninety. It is a signal about answerability, not
difficulty, and must never be reported as a time estimate.

It is also one sample. Treat "passed 4 of 7" as a reading, not a constant.

## Difficulty comes from this, not from taste

The spec's difficulty is 1–10, and when the candidate has AI it is the same
question as *how well does a model do on this*. So derive it from the
simulation rather than inventing a number:

- model passes most cases → low, 1–3
- model passes some → middle, 4–7
- model passes almost none → high, 8–10

Adjust for volume and reading load, then say which way you adjusted and why.

## The report

Write `challenges/<slug>/evaluation.md` — chat output dies with the session,
and this needs to survive until approve time, which may be the next day.

Keep it short enough to read before approving.

```markdown
# Evaluation — <slug>

**Verdict:** ready | not ready
**Difficulty:** 7/10 — a model passed 1 of 3 bugs cold

## Blocking
- The reference solution hardcodes the expected total, so the question is
  not proven solvable.

## Worth fixing
- Cases 3 and 5 both fail on an empty list; one is decoration.

## Checked and fine
Signal, time budget, starter fails correctly, brief matches the files.
```

Nothing in "Blocking" prevents shipping. It means: if you ship this, these are
the things you are choosing to ship with.
