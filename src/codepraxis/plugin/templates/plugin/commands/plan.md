---
description: Design a CodePraxis question — talk it through, find real code, write the plan
argument-hint: "<what you want to test, or a repo>"
allowed-tools: Read, Glob, Grep, WebFetch, Write, Task, Bash(codepraxis:*), Bash(git clone:*)
---

Design a question for: **$ARGUMENTS**

**You are not building anything here.** No pack, no tests, no source files. The
only file you may write is `spec.md`. Building happens later, in a separate
command, after a human approves what you write.

The `question-design` skill covers what makes a question worth asking. Read it
rather than re-deriving it. This file is the procedure.

## Step 1 — Talk first

Nothing can be searched until you know what to search for. The answers here
*become* the search query.

Establish:

- **The role and the stack.** "AI engineer, Python, LangChain" is a search.
  "Someone good" is not.
- **What good looks like** — the signal. Asking about *people* gets a real
  answer where asking about skills gets a list: what a strong hire did that a
  weak one couldn't. But that is a technique, not a script. Ask it in your own
  words, once, and only if you actually need it.

  **Skip it entirely when the signal is already there.** "assess embedded
  engineers for an NPU role" plus "C, memory management, pthreads" is a signal.
  Asking the set-piece question on top of that reads as a form to fill in, and
  the answer you get back will just repeat what they already told you.
- **How long the assessment runs**, and roughly where that time goes. Just ask.
  Do not derive it — they know their own process.
- **Do they have a repository?**

If they are vague, do not interrogate. Propose two or three concrete
directions from their domain and let them reject the wrong ones. Most people
cannot specify, but everyone can react.

## Step 2 — Get real code

**A question built on a real repository is hard to game**, because the model
has never seen that code. Push for this.

**They have one** — best case. Before anything else, show the exact file list
that would leave their company. The code goes into a container the candidate
controls; that is the only irreversible step in this flow. Strip credentials,
`.env` files, internal hostnames and customer data, and get confirmation.

**They don't** — find one:

```bash
codepraxis find-repos "<topic>" --language <lang> --json
```

Licences are already filtered to ones we may redistribute, and results are
sampled rather than ranked.

**Show them the shortlist and let them pick.** Three or four, each with enough
to judge it on — what it is, its size, and the seam you would build on. Say
which you would choose and why, then **stop and wait**.

```
1. Isty001/mem-pool  · MIT · ~1,060 lines C
   Fixed/variable-size pool allocator. Free lists guarded by one
   pthread_mutex_t. Seam: pool_fixed_alloc in src/fixed.c, ~100 lines.

2. mlyszczek/librb  · BSD-3 · ~2,400 lines C
   Thread-aware ring buffer. Single file, so less room for a feature
   with more than one decision in it.

3. johnosullivan/esp32-iridium-modem  · MIT · ~5,900 lines C
   Genuinely embedded firmware, but the seam is buried in AT-command
   parsing rather than concurrency.

I'd pick 1 — the locking is real rather than decorative. Which do you
want?
```

Do not pick for them and move on. The repository decides what the question can
possibly be about, and they know their hiring bar; presenting a choice as
already-made is the fastest way to build the wrong question convincingly.

If a search comes back thin, say so and search again with different words
rather than settling for the best of a bad set.

**They insist on inventing one** — allowed, but only when they ask for it
explicitly. Never the default. Say what they are giving up: a model has seen
every public tutorial, so an invented question starts out easier to game.

## Step 3 — Read it, then offer a menu

**Understand the architecture fully; read one or two candidate modules
deeply.** Not the whole repository — that is slow and mostly wasted.

The question you are answering: **is there a seam?** A self-contained module
with a clear interface a candidate can work inside. If there is not, say so and
move to the next repository rather than forcing a question out of this one.

Then offer a short menu, each option rated:

```
A. Retry + validation on tool dispatch
   3 design decisions · ~80 lines · hard to game (7/10)
B. Add a second tool with routing
   2 design decisions · ~50 lines · medium (5/10)
C. Cache the embedding step
   1 design decision · ~30 lines · easy to game (3/10)

I'd pick A. C is a one-liner a model writes instantly.
```

Be hard on the ratings — the assessment has to survive a candidate with an
agent. Aim for **one or two features**, not a project.

Check the chosen feature against the duration from step 1. If ~80 lines and
three design decisions do not fit, cut scope and say so.

### Check it can actually be graded

Confirm each thing being assessed lands in one of the runner's four modes —
`pack-contract` has the details:

- **Behaviour** → override 1, which is unrestricted Python. It can start a
  service and call it, import their module, inspect database state, or time a
  repeated call to prove caching. Do not limit yourself to stdin→stdout
  shapes; real repositories are libraries and services.
- **A fixed simple output** → override 0, but only when the string is exact.
- **A design decision** → override 2, AI review.

Also: what does setup cost on *every* container load, and do the visible cases
finish in seconds? They are the candidate's only feedback loop.

### Consider asking for a written design

For senior questions, where the reasoning matters more than the diff, have the
candidate write a short `design.md` and review it **together with their code**:
*does the implementation do what the document claims?* That catches someone who
describes one design and builds another, which neither file reveals alone.

If you do this, the brief must name the exact filename and ask for any diagram
in text — mermaid or ASCII. An image cannot be graded.

## Step 4 — Sanity-check it yourself, in seconds

Planning is a conversation and must stay at conversation speed.

**Do not run the simulation here.** Do not dispatch a subagent, do not start
background work, do not make them wait. The measurement belongs in
`/codepraxis:build`, where a pack exists and the attempt can be scored by the
real tests instead of guessed at — and where the author is already waiting for
a build rather than sitting in a design discussion.

What you can do in a few seconds, from your own reading:

- Would the brief alone be enough for a model? If yes, say which property makes
  it trivial and fix it now — bury a fact it cannot guess, or move the task from
  authoring to debugging.
- Do the cases separate different failures, or the same one twice?
- Does the scope fit the duration they gave?

Say what you found in a line or two. Then write the spec. Build will produce
the real number and correct your estimate if you were wrong — that is what it
is for.

## Step 5 — Write the plan

Write `challenges/<slug>/spec.md`. Nothing else.

**Keep it short.** A hiring manager should understand what this is and how it
will be judged in about two minutes. Everything in it earns its place.

```markdown
---
question: agent-hardening
status: draft
repo: github.com/owner/name @ a1b2c3d
license: MIT
---

# Harden a tool-calling agent

## The problem
What this repo is, in two sentences. Then what breaks, and what they
must make survive it.

## How they'll solve it
The rough shape of the change — not the code. Roughly N lines across
M files, and whether new dependencies are needed.

## How we'll check it

By running their code:
1. An unknown tool returns an error, not a silent skip
2. Malformed JSON triggers a retry, then fails cleanly

By AI review:
3. Whether the retry strategy is deliberate or incidental

## Config
tech_stack:       Python, OpenAI SDK
max_time:         90
difficulty:       7/10
ai_solvability:   medium — a model fixed 1 of 3 bugs cold
recommended_sku:  small
backend:          AI / PYTHON
```

Two rules for that file:

**Never write "override 2" in a spec.** The reader has not seen the runner.
"By running their code" and "By AI review" are the only two categories they
need; build maps each line to a mode.

**Config maps to real platform fields**, so build and ship fill them without
guessing. Difficulty comes from the evaluation, not from taste.

## Then stop

Post a summary. Point them at `spec.md` and `evaluation.md`. The next step is
theirs:

```
codepraxis approve <slug>     then  /codepraxis:build
```

Do not build. Do not offer to build. If they want changes, revise and re-post —
and approval means that command has been run, not that someone said "looks
good" in chat.
