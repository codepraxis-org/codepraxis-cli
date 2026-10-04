---
description: Plan an assessment question for a position and write its spec.md
argument-hint: "<which position are you hiring for?>"
allowed-tools: Read, Glob, Grep, WebFetch, Write, Bash(git clone:*), Bash(codepraxis categories:*)
---

Plan an assessment question for: **$ARGUMENTS**

You write one file, `challenges/<slug>/spec.md` (`mcq/<slug>/spec.md` for an MCQ
bank). You do not build anything here.

## 1. Get the basics

Ask for these together, in one message. Skip any the conversation already
answers, and don't design anything until you have all of them.

1. **Position name.** The role they're hiring for.
2. **Job description.** Ask them to paste it.
3. **Time.** How many minutes the candidate gets for this question.
4. **Question kind.** One of:
   - a coding question **without** AI (the candidate works alone),
   - a coding question **with** AI (the candidate has the AI agent),
   - an **AI interview** question (a conversation, no coding environment),
   - an **MCQ bank**: multiple-choice questions for a template's Knowledge check
     round (adaptive, difficulty 1 to 5).

If they aren't sure which kind fits, recommend one from the job description in
one or two sentences and let them choose.

## 2. Read the skill for that kind

| Question kind | `type:` in the spec | Skill to read now |
|---|---|---|
| Coding without AI | `coding` | `question-coding` |
| Coding with AI | `coding-ai` | `question-coding-ai` |
| AI interview | `interview` | `question-interview` |
| MCQ bank | `mcq` | `question-mcq` |

The skill for the question type they chose says what a good question of that
type looks like and the rules it must follow. Everything you propose from here on must fit it.

## 3. Ask where the question comes from

Ask which of these they want:

1. **"I have a question in mind."** They describe it, even briefly.
2. **"Make a question from a repository."** They give a repository (theirs or any other) to build the question on.
3. **"Create one for me."** You propose questions from the job description.

### 3a. They have a question in mind

Based on the question kind they chose, use that kind's skill: it says what a
good question looks like. Brainstorm with them until you find the right
question together. Take their idea and reframe it in that structure: the
question, what it assesses, what the candidate starts with, and how it's
checked.

Be creative: alongside their idea, offer a few related variations, such as the
same question with an added twist (a failure mid-run, messy data, a rule the
candidate must notice). Present their reframed idea and the variations, saying
plainly what you changed and why, and let them pick.

### 3b. Make a question from a repository

Read enough of it to understand the architecture, then read one or two modules
in depth. Find the seams: self-contained places a candidate can work inside.
Propose **up to three** questions on it, each fitting the skill for the
question type they chose. Fewer is fine if the repository doesn't support three
good ones.

Before anything leaves their machine, list the exact files the candidate would
get (for an interview, the files they're shown) and strip credentials, `.env` files, internal
hostnames and customer data. Confirm the list with them.

### 3c. You create the question

You create everything yourself. Understand the job description: what this
person actually does on a normal day and on a bad one. From that, propose **up
to three** questions, each fitting the skill for the question type they chose.

For the one they pick, you will write the material yourself. For a coding
question that is a codebase: realistic code, data and tooling from the world
of this job, into which the question's defects or missing pieces are then
placed. For an interview question it is what the candidate is shown: code, a
diagram, a document or a ticket. The skill for the question type says how big
it should be and how it's structured. It must read like a real team's work,
never generic filler.

For every option you propose (3a, 3b or 3c), give:

- **Title:** one line.
- **The question:** what it is, in two or three sentences.
- **What it assesses:** the skills from the job description it tests.
- **What the candidate starts with:** the files, data or setup they're given.
  For an interview: what they're shown, and how they answer (typing, drawing
  or picking a choice).

Recommend one, and let them pick.

## 4. Write the spec

Once they've picked, write `challenges/<slug>/spec.md`. It must contain
everything needed to build the question without asking again.

For every question type, pick `categories` from the list `codepraxis
categories` prints; if none fits, use `misc`. Coding and interview questions
share the same categories. Categories only matter when the admin account
pushes.

```markdown
---
question: <slug>
type: coding | coding-ai | interview
max_time: 40
ai_enabled: false
difficulty: 2                       # 1 easy, 2 medium, 3 hard
tech_stack: [Oracle PL/SQL, SQL]
repo: github.com/owner/name @ <sha> # or: invented
position: <position name>
categories: [<existing category slug>]
---

# <Title>

## Signal
<one falsifiable sentence: what a strong candidate does that a weak one doesn't>

## The problem
<the situation in the candidate's world>

## Starting state
<every file or table the candidate gets, and what is broken or missing in it>

## Solution
<what the reference solution does; for a debug question, each planted defect
and its fix>

## How we check it
By running their code:
1. <case> — visible
2. <case> — hidden: <what it catches>

By AI review:                       # only when needed
3. <decision the reviewer checks, and its checklist>

## Environment
<setup.sh needs, external services such as a database, data to seed>

## Brief outline
<the headings the candidate's instructions will have, and the exact contract
they must state>
```

For an `interview` question, use this instead:

```markdown
---
question: <slug>
type: interview
mode: open-probe | draw-probe       # mcq is not available yet
duration: 15                        # minutes for the whole question
seniority: senior
topics: [<the competency it scores>, <others it touches>]
categories: [<existing category slug>]
repo: github.com/owner/name @ <sha> # or: invented
position: <position name>
---

# <Title>

## Signal
<one falsifiable sentence: what a strong candidate does that a weak one doesn't>

## What they're shown
<each file, and when: with the opening question, with a probe, or with a hint>

## Opening question
<the situation, exactly as the candidate reads it>

## Answer key
Must reach: <each concept>
Red flags: <each one>
Good extras: <each one>
Never say: <the phrases that would give it away>

## Probes
1. <build | debug | lead> — <what it asks>; good answer: <…>; hint: <…>; <minutes>
   1.1 <the follow-up one level deeper> …

## Timing
<minutes for the opening question, and for each probe>
```

For an `mcq` bank, plan the bank, not each question:

```markdown
---
question: <slug>
type: mcq
category: <existing category slug, or misc>
position: <position name>
size: 25                            # at least 3 per difficulty, more at 2 to 4
---

# <Bank name>

## Covers
<the sub-topics, each one line, and which difficulties each will have>

## Distribution
1: 3 · 2: 6 · 3: 7 · 4: 6 · 5: 3

## Sources
<the real situations the questions come from: a repo, the job description, docs>

## Images
<which questions need one, and what it shows; none if no question needs one>
```

Never write runner vocabulary ("override 2") in the spec; say "By running their
code" or "By AI review".

## 5. Hand off

Say what you planned in two lines, then: `/codepraxis:build <slug>`.
