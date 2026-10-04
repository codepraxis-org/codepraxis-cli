---
name: question-interview
description: Use when planning an AI interview question (type interview). What a good interview question looks like, what the candidate can be shown and how they can answer, how the seed and probes should work, how to size it, and a worked example. The files to produce are in output.md.
---

# AI interview questions

The AI interviewer opens with a seed question, then follows the candidate's
answers down a tree of probes, and grades against an answer key. What you are
measuring is **whether their experience is real and how deep it goes**.

## When an interview beats a coding question

- The skill lives in tools a container can't run: GUI tools, vendor consoles,
  configuration screens.
- The job is judgement: design, trade-offs, leading a team, working with
  clients.
- You want to test many areas lightly rather than one deeply.

## How a good question works

- **The seed is a situation, never a definition.** "Walk me through how you'd
  find out why…", not "what is…".
- **Probes go one level deeper each time**, along three steps: *build* (how
  would you do it), *debug* (it broke; now what), *lead* (a junior did this;
  what do you check).
- **Anchor claims to specifics.** When a candidate says they've done it, a
  probe asks which module, what volume, what broke. Textbook answers with no
  project detail are the sign of padded experience.
- **Each probe tests one thing the seed didn't.**
- **Withhold the giveaways.** List the phrases that would hand over the answer.

## What makes a question excellent

These come from building a bank of interview questions and reviewing every one.
They are the difference between a question that measures real experience and one a
well-read candidate talks through.

- **One story, one chain.** The strongest shape is an opening question and a
  single chain of three probes (12 minutes: 4 + 3 + 2 + 3). Each probe brings new
  evidence into the same story (a log, a dashboard, a colleague's proposal) and moves
  it forward. How far down the chain a candidate gets is the signal.
- **Richest probe first, hardest last.** Most candidates reach probe 1, so put the
  most evidence and the most signal there. Make the last probe the hardest:
  judgement, a design under stated constraints, or judging someone else's claim
  (a junior's sign-off, a vendor's number, a manager's plan).
- **Plant findings in the files.** Every stage's files carry specific things a
  strong candidate finds: a line of code, a number that doesn't add up, a config
  flag, a contradiction between two files, a footnote that undercuts a headline.
  The answer key names them. A weak answer stays generic and names nothing from the
  files; the prompt tells the interviewer to ask for a line or a number when that
  happens.
- **Make your own files, from one script.** Generate every exhibit in
  `entity-src/make_entities.py` (see `output.md`) so all numbers agree across files,
  assert the invariants (totals add up, the chart matches the CSV), and never use
  real companies' documents: models have read them, and the specifics must be yours.
- **The probe brief never gives the finding away.** The interviewer often
  paraphrases a probe's `description` to the candidate. Write "Show the trial balance
  compare. Ask what differs and why", never "Show the compare, which ties at every
  account" (a real miss: the interviewer repeated it, and it was false). Facts the
  interviewer may give go in as "If they ask X: Y".
- **Every probe adds a file.** New evidence is what moves the story; a probe that
  only asks a new question tests less.
- **Problem first, no story nouns.** The candidate should understand the problem in
  30 seconds, then spend the time on the technology. No company, person or invented
  product names anywhere: seed, probes, hints or files. Use roles ("your team", "the
  customer", "your manager"). No invented ids (ticket, incident, PR numbers) unless
  the candidate needs one to point into a file. Plain file names (`incident-ticket.md`,
  `dashboard.png`), one clock, no time zones unless they matter. Real technology keeps
  its real name (Oracle EBS, PostgreSQL, pytest).
- **Files are technical evidence.** Code, logs, data, configs, diagrams, dashboards.
  A story prop (a voice note, a chat thread, a sales call, an email between people)
  stays only when it carries a technical fact the candidate needs; otherwise it is one
  line the interviewer says ("Your manager wants to switch to a bigger model").

## Use what the candidate can see and do

A question is stronger when the candidate works from something concrete
instead of a description. Use these whenever they fit:

**What you can show them** (files, on the opening question, a probe or a hint).
They open as tabs, like an editor, and stay for the rest of the question:

- **Code, one file:** "Here's the loader a junior wrote. What would you change
  before it goes live?" Shown in a real editor.
- **A repo (a folder):** a small codebase with an explorer, when the question is
  about how pieces fit together.
- **A screenshot or diagram (image):** "This is the integration's architecture.
  Where would you expect it to fail under load?"
- **A PDF, slides or a Word document:** a design document, a runbook, a spec to
  critique. Slides and Word are converted to PDF on push.
- **Markdown or a log:** a ticket, an incident timeline, a table of numbers.
- **Audio or video:** a support call, a screen recording. Write what it shows in
  a description beside it: that is all the interviewer can know of it.
- **A whiteboard drawing:** a diagram they read, or one they start drawing from.

**Point at what matters:** highlight lines per stage, so a probe can say "look
here" without saying why. A probe's files and highlights arrive together, and the
file comes to the front.

**How they can answer:**

- **Typing** in the chat (`open-probe`), which is the default.
- **Attaching lines:** they select lines in any file and attach them, so "this
  line" is exact. Nothing to set up; it is always available.
- **Editing a file** you mark editable: "fix this function", "add the missing
  guard". Their version goes with the answer and the interviewer reads it.
- **Drawing** on a whiteboard and explaining it (`draw-probe`), for design and
  architecture questions. Mark a diagram editable to have them start from it.
- **Picking a choice** (`mcq`) is **not available yet**: the interview does not
  show the choices to the candidate. Don't write `mcq` questions. For a
  multiple-choice knowledge check, add the questions to an MCQ question bank
  and turn on the template's Knowledge check round instead.

Mixing them works well: show code in the opening question, highlight the lines a
probe is about, give a log file with the probe, and have them edit the fix. See
`output.md` for how each is written.

## Rules every question follows

1. **It happens in this job.** The seed comes from a real situation in the role.
2. **Real names.** Tools, tables and terms follow the real product.
3. **Grade reasoning, not vocabulary.** The answer key lists what a good answer
   *reaches*, written so the interviewer can check it the same way every time.

## Avoid

- Definition questions and trivia.
- Probes that only rephrase the seed.
- An answer key that rewards vocabulary instead of reasoning.

## Size it for the time

| Time | Seed + probes | Probe depth |
|---|---|---|
| 5–8 min | 1 seed, 2 probes | 1 level |
| **12 min (recommended)** | **1 seed (4 min), one chain of 3 probes (3 + 2 + 3)** | **3 levels** |
| 10–15 min | 1 seed, 3–4 probes | 2 levels |
| 20 min | 1 seed, 5–6 probes | 3 levels |

Give the opening 2 to 4 files, and each probe 1 or 2 new ones: 4 to 8 in all. A
candidate can read about a page, a chart and a short log in 4 minutes.

## Example: the report that shows no data

- **Role:** Senior Oracle EBS technical lead. 12 minutes.
- **Seed:** "A custom report works for India users but returns nothing for the
  UK team. Walk me through how you'd find out why."
- **Probe 1 (debug):** "It's a multi-org setup. What would you check first?"
  Answer key: operating-unit context not set for a multi-unit responsibility.
- **Probe 2 (build):** "How would you fix it without hard-coding the unit?"
- **Probe 3 (lead):** "A junior's version queries the `_ALL` table directly.
  What's wrong with that?" Answer key: it bypasses security and leaks other
  units' data.
- **Withheld:** "MO_GLOBAL", "set_policy_context".

## Example: a chart used to approve unattended agents (AI engineer, 12 min)

- **Opening:** a bank's AI council wants to let a model run 3-hour operations tasks
  unattended, citing a time-horizon study. Files: the study's chart (a logistic fit
  computed from generated task data), the task-level CSV, the council paper (PDF).
  Planted: 3h10m is the 50% point (a coin flip), the paper reads human task time as
  agent run time, only 10 of 146 tasks are ops tasks and none is over 75 minutes.
- **Probe 1 (richest):** the methodology appendix (PDF): the success criterion was
  loosened after the pilot, the baselines are generalists paid by the hour.
- **Probe 2:** the first five runbooks the pilot would run: read the chart at each
  length; two can't be undone.
- **Probe 3 (hardest):** a slide forecasting an unattended quarterly close from a
  doubling trend; its table doubles every 6 months while it says 7, and the close is
  186 steps, not one.

## Before you propose it

- [ ] The seed opens on the problem, with the numbers that matter and no company,
      person or invented product names (files and probes too).
- [ ] One chain of three probes, the richest first and the hardest last (or say why
      not).
- [ ] Every stage's files plant things a strong candidate can find, and the answer
      key names them.
- [ ] No probe description or hint states what the candidate should find.
- [ ] Every probe adds at least one file, and every file is technical evidence.
- [ ] Every probe has an answer a senior person would give.
- [ ] It fits the time table above.
- [ ] The page (`description_sections`) is plain English a recruiter follows with no
      context: the problem, what they see, numbered steps with minutes, who it's for.
