---
description: Build an approved CodePraxis question and fix what fails
argument-hint: "[question name]"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(codepraxis:*)
---

Build the question `$1` from its approved plan.

## Before anything else

Read `challenges/$1/spec.md`. If it does not exist, or its frontmatter does not
say `status: approved`, **stop**. Tell them to run `/codepraxis:plan` first, or
`codepraxis approve $1` if the plan is already written. Do not build from an
unapproved plan, and do not offer to approve it yourself — approval is theirs.

The spec is the specification. Do not redesign it while implementing. If you hit
something it got wrong, say so and ask, rather than quietly deciding.

## Scaffold, then fill in

```bash
codepraxis new $1
```

That writes a complete, already-passing question so you start from something
green:

```
challenges/$1/
  spec.md
  pack/
    metadata.json      backend.conf      setup.sh
    source/            what the candidate starts from
    ._tests/test_1.py  the testCases class
    ._course_data/     course_toc.json and feature.md
  solution/            the reference answer, never uploaded
```

Then replace the placeholder content with the real question:

- **`pack/._course_data/feature.md`** — the brief. Scenario, exact invocation,
  output contract, a worked example, and what is evaluated. Precise about the
  contract, silent about the approach.
- **`pack/source/`** — the starting state the spec describes, plus a README
  saying what is broken and how to run it. No working implementation.
- **`pack/._tests/test_1.py`** — the case table from the spec, in order, with
  the visible ones first.
- **`solution/`** — the reference answer. It overlays `source/`, so mirror those
  paths.
- **`pack/setup.sh`** — only if dependencies are needed, with pinned versions.

The `pack-contract` skill has the `testCases` rules. Follow it exactly; those
constraints come from the runner, not from taste.

## Then argue with your own work

Run `codepraxis validate $1` and iterate until it passes. Then check the things
validation cannot, and fix what you find:

- **Does the solution actually solve the problem?** If it pattern-matches the
  test inputs — hardcoding an expected number or name — it proves nothing about
  whether the question is solvable. Rewrite it to do the real work. This is the
  single most common way a question ships broken.
- **Does the starter fail for the right reason?** It must fail because the work
  is missing, not because of a syntax error or a bad import.
- **Does every case discriminate?** If two fail for the same reason, cut one.
- **Does the brief match the files?** Every path it names must exist in
  `source/`. Renaming a file and leaving the brief pointing at the old name is
  a real bug that reaches candidates.
- **Does any hidden case test something the brief never states?**
- **Do the visible cases run in seconds?** They are re-run constantly.

Only report to the user when it passes, or when you are genuinely stuck. Do not
narrate each fix.

## Then run it once on the real image

```bash
codepraxis validate $1 --remote
```

**Do this here, not at publish time.** It costs about a minute and it is the
only thing that catches the class of bug local validation cannot see:

- The runner is **Python 3.10**. Anything newer is a trap, and some of it is
  semantic rather than syntactic — `Union[X, X]` collapses on 3.12+ and raises
  `TypeError` on 3.10 — so neither lint nor a local run finds it.
- `setup.sh` is not executed locally at all.
- Three of koro's four test modes cannot be judged locally.
- A subprocess in the container gets a different Python than your test module.

Skipping it does not avoid the cost, it defers it: the first remote run then
happens inside `ship`, which waits up to fifteen minutes and is a far worse
place to discover a missing package.

Say it is running and that it takes about a minute. A remote failure here is a
build failure — fix it and re-run, rather than carrying it into publishing.

## Then evaluate it

Validation says it runs. It does not say the question is any good.

Invoke the `question-evaluation` skill. The pack exists now, so the full review
applies and the simulation is measurable: a **clean subagent** — not you, you
have seen the solution — writes an attempt to `challenges/$1/.attempt/`, and
`codepraxis validate $1 --fixture attempt` scores it against the real cases.

The review costs nothing — always do it. The simulation costs minutes, so:

**Don't repeat it.** If `challenges/$1/evaluation.md` already exists and the
pack has not meaningfully changed since — a typo in the brief does not count —
reuse that number and say you are reusing it. Rebuilds are common; re-measuring
an unchanged question just spends someone's afternoon confirming what is
already written down.

**Announce it, then let them decline.** One line before it starts: what it is
doing, roughly how long, and that they can skip it. Something like *"Running
the AI-resistance check — a fresh model attempts this cold, takes a few
minutes. Say skip if you'd rather not."*

Default to running it. If they skip, say plainly what that costs: `difficulty`
stays an estimate, and nobody knows whether the question survives a candidate
with an agent until someone checks. Note it in `evaluation.md` as not measured
rather than leaving the field looking authoritative.

Run it once and wait. Do not chain a second attempt at a revised framing in the
same pass — that is another several minutes, and the revision can be measured
on the next build.

That prints `MEASURED the attempt passed N/M cases`. Fewer is better: it means
the question is not answerable from the brief alone. If a model passes most of
them, say so plainly — the question needs work, whatever validation says.

Write `challenges/$1/evaluation.md`, and update the spec's `difficulty` and
`ai_solvability` from what was measured rather than what was guessed.

## When it passes

Say what was built, what each case catches, and how long you expect it to take.
Give the evaluation verdict in one line. Then hand over:

```
/codepraxis:try $1
```

Do not publish. Shipping is a separate, deliberate step.
