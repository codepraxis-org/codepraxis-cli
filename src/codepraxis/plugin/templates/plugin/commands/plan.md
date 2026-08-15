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
- **What good looks like.** Ask about people, not skills: *"Your best engineer,
  and a hire that didn't work out — what did the good one do that the other
  didn't?"* That produces a real signal statement. *"What should we test?"*
  never does.
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
sampled rather than ranked. Present two or three with a recommendation and a
reason, not a list to wade through.

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

## Step 4 — Check it before writing it

Invoke the `question-evaluation` skill on the agreed design. At this stage
there is no pack, so it reviews the shape and — via a **clean subagent that has
not seen this conversation** — reports how far a model gets from the brief
alone.

Do not run this yourself in this context. You designed the question; you know
every answer, so your own attempt measures nothing.

Report the result briefly. If a model would walk it, fix that now: bury a fact
it cannot guess, or move the task from authoring to debugging.

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
