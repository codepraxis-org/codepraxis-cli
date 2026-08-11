---
name: question-design
description: Use when deciding what a CodePraxis question should test, whether a question is any good, or why one is not discriminating — designing cases, judging AI-resistance, scoping to a duration, or reviewing a question before it reaches candidates. For the mechanical file and testCases rules, see pack-contract.
---

# What makes a question worth asking

CodePraxis exists because algorithm puzzles measure who practises algorithm
puzzles. A question here should look like a morning of the job.

This is the editorial half. `pack-contract` covers what the runner requires;
this covers what makes a question actually separate people.

## The signal comes first

One falsifiable sentence. Not *"tests Python"* but *"can they decompose an
ambiguous natural-language-to-SQL problem where the answer is not directly in
the schema."*

If you cannot write that sentence, you do not have a question yet — you have a
topic. Everything downstream is derived from it: the cases exist to detect it,
the rubric describes doing it well, the duration is how long it takes.

## Duration is a budget, not a label

Sixty minutes and three hours are structurally different questions. State where
the time goes — reading, orienting, writing, debugging, buffer — and make the
slices sum. If they do not, the scope is wrong.

At sixty minutes the brief must be short and setup near-instant: five minutes
reading plus two minutes installing is twelve per cent of the assessment.

## Candidates have AI, so the question must survive it

There is an agent and an LLM endpoint inside the container. A question a model
answers from the brief alone is a typing test.

The check is empirical, not a vibe: attempt the brief cold, with nothing but the
text a candidate gets, and judge the result against the case table.

**What survives, strongest first:**

- **Context the model has never seen** — their repository, their schema quirk,
  their log format. This is why a question built from a real codebase passes
  almost by construction.
- **Debugging rather than authoring.** Models write new code far better than
  they find why existing code is subtly wrong.
- **A decision with no single right answer**, where the candidate must choose
  and defend.
- **Integration volume** — many small correct things wired together; models
  drift across long multi-file changes.
- **Hidden cases that punish the obvious approach.**

**Reject:** anything with a canonical answer online, pure algorithm
implementation, CRUD scaffolding, and any brief so complete that it *is* the
specification.

**The tension:** clarity and AI-resistance pull against each other. Be precise
about the **contract** — invocation, output format, error behaviour — and silent
about the **approach**. Say what "done" looks like; do not say how to get there.

## Cases exist to separate people

There is no target number. Write as many distinct separations as the question
needs and no more.

- **Every case earns its place.** If two fail for the same reason, one is
  decoration.
- **The visible ones are the whole feedback loop.** They should confirm the
  candidate is on the rails and cover the shape of the problem — not the edge
  cases.
- **Hidden cases may test more, never something new.** A hidden case checking a
  requirement the brief never states is a gotcha, not an assessment.
- **Include one adversarial case** — the "this is not in the data, say so"
  case. It catches the candidate who guesses rather than checks.
- **Score should be a gradient, not a cliff.** If everything fails until the
  last piece lands, someone who did most of the work scores zero and you learn
  nothing about them. Make a first pass reachable early.

## The starting state is a design decision

What you hand over decides what you are measuring. Give them a working service
with a bug and you measure debugging; give them an empty file and you measure
setup speed for fifteen minutes.

Say explicitly what is already built and what is missing, and why the line is
there. It is the most commonly skipped decision and one of the most
consequential.

## Things that quietly ruin a question

- **A reference solution that pattern-matches the tests.** Hardcoding an
  expected number passes validation and proves nothing about whether the
  question is solvable. This is the most common way a question ships broken.
- **A brief naming a file that does not exist.** Rename something in `source/`
  and forget the brief, and every candidate hits it.
- **Assumed knowledge that is really a proxy filter.** Requiring obscure
  framework internals selects for familiarity with your stack, not engineering
  ability. Say what knowledge is assumed and check the role needs it.
- **A rubric that promises human review nobody has time for.** If the brief says
  architecture is evaluated, someone must actually read it — say how many
  minutes per candidate that costs.
- **Non-deterministic grading with strict assertions.** If a model is in the
  loop, phrasing varies. Assert on the fact, not the sentence.

## Building from an existing repository

The strongest path, because a model has never seen the company's code. It is a
reduction problem, not an authoring one:

1. **Find a seam** — a module with a clear interface and existing tests.
2. **Pick the cut** — delete an implementation so they rebuild it, inject a
   defect so they debug it, or add a requirement so they extend it.
3. **Reuse their tests.** Selecting cases beats writing them, and it collapses
   the hardest part of authoring.

Before anything ships: strip credentials, environment files, internal hostnames
and customer data, and show exactly which files would leave the company. The
source goes into a container the candidate controls.

## Sitting the question is worth more than reviewing it

Ten minutes actually attempting it finds more than any amount of reading. Time
the first real step and compare it against the plan's budget — that number is
usually wrong the first time.
