---
description: Publish a CodePraxis question as a draft and return its link
argument-hint: "[question name]"
allowed-tools: Read, Glob, Bash(codepraxis:*)
---

Publish `$1`.

A published question can be assigned to a real candidate immediately, so this
step is deliberate and it is not yours to decide alone.

## Check first, in this order

1. `codepraxis validate $1` passes locally.
2. `challenges/$1/spec.md` says `status: approved`.
3. A reference solution exists at `challenges/$1/solution/`.
4. They have actually opened it themselves, `/codepraxis:try`. If they have
   not, say so and recommend it before publishing rather than after.

If any of these fail, stop and say which one.

## Then evaluate, before publishing

Run the `question-evaluation` skill, **before** the publish, not after. Once
it is live a bad verdict is a rollback rather than a decision.

If `challenges/$1/evaluation.md` already exists and the pack has not changed
since, read it rather than re-running the simulation; it costs a container run.

Report the verdict in one line. **A poor verdict does not stop the publish**, 
it is theirs to weigh. Say what is wrong, say you are publishing anyway if they
confirm, and let them decide.

## Publish as a draft

```bash
codepraxis ship $1
```

The CLI runs the authoritative validation in the real runner image first; a
local pass does not qualify. It publishes as a **draft**, prints the question id
and a URL.

**Give them the URL in your reply.** That link is the whole point of this step, 
it is what they send to their team.

## Do not go live on your own

Going live means candidates start receiving it. That is the user's call, not
yours. Tell them the command and stop:

```bash
codepraxis ship $1 --live
```

## Write the catalog copy

The hiring team never opens the pack. They decide whether to ask this question
from two pieces of copy in the catalog, so both are part of shipping, not an
afterthought. Write them into `challenges/$1/pack/publish.json`.

**`description`, one or two sentences.** What the candidate does. It renders
clamped to two lines in the question list, so keep it under about 220
characters. The row already shows the title, difficulty, tech stack and
duration, so do not spend it repeating them: "Implement a rate limiter in
Python (Medium, 60 min)" says nothing the row is not already showing.

**Write it in plain English.** A recruiter reads this, not only an engineer.
Short sentences, ordinary words, and no stacking three clauses behind a colon.
Where a question has one detail that makes it interesting, say that detail
plainly rather than gesturing at it.

- Too dense: "Answer plain-English questions about a Git repository from the
  command line: work out which Git operation a question implies, run it
  read-only, and refuse cleanly when the question is outside what the history
  can answer."
- Plain: "Build a command-line tool that answers questions about a Git repo in
  plain English, like "who committed last?". It has to pick the right Git
  command, and say so when it cannot answer."

Both say the same thing. The second one can be read once, at speed, by someone
deciding whether to open it.

**`description_sections`, the detail page.** A JSON object; every key optional,
markdown bodies limited to headings, bold, bullets and inline code. Rendered in
this order:

- **`signal`** what the question actually measures.
- **`task`** what the candidate spends the time doing.
- **`starting_state`** what is given and what is missing.
- **`implement`** the concrete deliverables, as a bullet list.
- **`audience`** which roles it suits, what it assumes, where not to use it.
- **`scoring`** optional; what the report will say.

### Plain English applies to the sections too

Same register as `description`. These are read by a hiring manager and a
recruiter side by side, and the recruiter is not going to look anything up.

- Ask `signal` as a question starting "Can they…", one line.
- Write `starting_state` as two short paragraphs, what they get and what they
  write, rather than a "Given / Missing" table.
- Label `audience` as **Good for** / **Needs** / **Worth knowing**, not
  "Fits / Assumes / Note".
- In `implement`, bold the deliverable and explain it in ordinary words after
  the comma.

Some before and after:

- Dense: "Whether an engineer can implement a sliding-window algorithm whose
  termination depends on the interaction between window size and overlap."
- Plain: "Can they write a loop that is guaranteed to finish, including the
  settings that would otherwise make it run forever?"

Where a question has one detail that makes it interesting, say it outright.
"the missing director column is the whole question, the rest is plumbing" tells
a reader more than a paragraph about data modelling.

### The rule that matters most

**`signal` has to read to someone who has never opened the question.** It names
the capability under test, never the question's internals. You have just spent
hours inside this pack, so the sentence you reach for first will almost always
fail this.

- Fails: "whether they notice the usage counter is not thread-safe" — the
  reader has no idea there is a usage counter.
- Passes: "whether they find a concurrency bug nobody told them to look for."

Name the internals later, in `starting_state` and `implement`, once the earlier
sections have established the setup.

### Where the content comes from

Most of it already exists by the time you ship, so do not invent it:

- `signal` is the spec's signal sentence, rewritten to stand alone.
- `task` is `pack/._course_data/feature.md`, condensed.
- `starting_state` is the starting-state decision, what `pack/source/` contains
  and what was deliberately left out.
- `implement` is the case table read as scope rather than as tests.
- `audience` is the one part nothing upstream produces. Write it from the role
  the question is for, and be honest about where it does not belong, "do not
  use for" is more useful to a recruiter than another line of praise.

Write for a hiring manager and a recruiter reading side by side: the manager
judges the technical substance, the recruiter needs to know it fits the role
and the time. Say what the question is, not how good it is.

## Republishing a change

If this question already has an id, pass it, otherwise you create a second copy
instead of a new version, and the original keeps its assignments while the fix
sits somewhere else:

```bash
codepraxis ship $1 --challenge-id <id>
```

Get the id from `codepraxis list` or from `challenges/$1/pack/publish.json`.
