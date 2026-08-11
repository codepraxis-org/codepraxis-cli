---
description: Design a CodePraxis question — talk it through, then write the plan
argument-hint: "<what you want to test, a doc, or a repo>"
allowed-tools: Read, Glob, Grep, WebFetch, Write, Bash(codepraxis:*)
---

Design a question for: **$ARGUMENTS**

**You are not building anything in this command.** No scaffolding, no pack, no
tests, no source files. The only file you may create is `spec.md`. Building
happens later, in a separate command, after a human approves what you write
here.

## Phase 1 — talk, then sketch

Establish three things early, because everything else depends on them:

1. **How long is the assessment?** Sixty minutes and three hours are different
   questions, not the same question with a different timer.
2. **What stack?** Any stack is fine — `setup.sh` runs on every container load,
   so anything installable is allowed. You need to know so you can budget the
   install and pin versions.
3. **Where is this coming from?** A fresh idea, a question they already have in
   another format, or a repository to mine.

Then keep asking until you actually understand the question. For some subjects
that is three more questions, for others ten. There is no fixed list.

**Most people cannot specify, but everyone can react.** If the answer is vague
— "test if they know Python" — do not interrogate them. Propose two or three
concrete questions from their domain and let them shoot the ideas down. The
other move that works: ask about people, not skills. *"Your best engineer, and
a hire that did not work out — what did the good one do that the other didn't?"*
That produces a real signal statement. *"What should we test?"* never does.

**You are done asking when you can write down three things:** the signal in one
falsifiable sentence, the exact invocation and output contract, and at least
three cases that fail for different reasons. Stop there. Everything else you
propose rather than ask.

Then post a **short sketch in chat** — a few sentences: the scenario, what the
candidate does, how it is graded, roughly how hard. Cheap to throw away. Wait
for them to react before writing anything to disk.

## Phase 2 — the two checks

Once the sketch is agreed, run these yourself and report what you find.

**Does it fit the time?** Write out where the candidate's time goes — reading,
orienting, writing, debugging, buffer. If the slices do not sum to the
duration, shrink the scope and say so.

**Can a model just solve it?** Candidates have an AI agent and an LLM endpoint
inside the container. Take the brief you have drafted, attempt it cold as if you
were the candidate with nothing but that text, and judge the attempt against
your own case table.

- **If you solve it** — say so plainly, do not write the spec, and propose a
  specific change. Bury the fact in data the model cannot guess. Remove the
  approach hint. Move from authoring to debugging. Then re-check.
- **If you get part way** — that is the target. A model should accelerate the
  candidate, not replace their judgement.
- **If you get nowhere** — usually the brief is unclear rather than the question
  being hard. Look again before proceeding.

What survives this, strongest first: context the model has never seen (their
repo, their schema quirk, their log format); debugging rather than authoring;
a decision with no single right answer; integration volume; hidden cases that
punish the obvious approach.

Reject outright: anything with a canonical answer online, pure algorithm
implementation, CRUD scaffolding, and any brief so complete that it *is* the
specification.

Be precise about the **contract** and silent about the **approach** — that is
how a brief stays clear without becoming one-shot-able.

## Phase 3 — write the plan

Write `challenges/<slug>/spec.md`. Nothing else. Frontmatter first:

```markdown
---
question: <slug>
status: draft
duration: 60
stack: Python, FastAPI
---
```

Then, in this order:

1. **Signal** — one falsifiable sentence. Not "Python skills".
2. **Duration and time budget** — the slices, summing to the duration.
3. **Stack and environment** — what `setup.sh` installs, with pinned versions,
   and how many seconds that costs on every load.
4. **Who it is for** — role, seniority, and what prior knowledge is assumed.
5. **Scenario** — the real situation this mirrors, in their domain.
6. **Starting state** — what is already built in `source/` versus what is
   missing, and why that line.
7. **Deliverable contract** — entry point, invocation, output format, error
   behaviour. This is what the tests will assert.
8. **Test cases** — one row each: visible or hidden, what it discriminates that
   nothing else does, what a plausible-but-wrong solution does on it, and
   roughly how long it takes to run.
9. **AI resistance** — what you found in phase 2, and the property that defeats
   one-shotting.
10. **Rubric** — what "good" means beyond pass/fail, and the per-candidate
    review cost if a human reviews anything.

On test cases: there is no target count. Cases exist to separate candidates, so
write as many distinct separations as the question needs and no more. If two
cases fail for the same reason, one is decoration. The first few are visible to
the candidate — `RUN` sets how many — and they are the only feedback loop while
someone works, so they must run in seconds. Hidden cases may test more, but
never something the brief does not state; that is a gotcha, not an assessment.
Cases run one after another, so their runtimes add up on every submit.

## Then stop

Post a summary and tell them to read `spec.md`. Do not build. Do not offer to
build. The next step is theirs:

```
codepraxis approve <slug>     then  /codepraxis:build
```

If they want changes, revise the spec and re-post. Do not proceed until it is
approved — and approval means the command above has been run, not that they
said "looks good" in chat.
