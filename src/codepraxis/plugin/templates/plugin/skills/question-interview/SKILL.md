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

## Use what the candidate can see and do

A question is stronger when the candidate works from something concrete
instead of a description. Use these whenever they fit:

**What you can show them** (entities, attached to the opening question, a
probe or a hint):

- **Code, one file or several:** "Here's the loader a junior wrote. What would
  you change before it goes live?"
- **A diagram or screenshot (image):** "This is the integration's architecture.
  Where would you expect it to fail under load?"
- **A PDF or Word document:** a design document, a log extract, a runbook, a
  spec to critique.
- **Markdown:** a ticket, an incident timeline, a table of numbers.
- **A whiteboard drawing:** a diagram they can read, or complete themselves.

**How they can answer:**

- **Typing** in the chat (`open-probe`), which is the default.
- **Drawing** on a whiteboard and explaining it (`draw-probe`), for design and
  architecture questions. You can give them a starting drawing to extend.
- **Picking a choice** (`mcq`) is **not available yet**: the interview does not
  show the choices to the candidate. Don't write `mcq` questions. For a
  multiple-choice knowledge check, add the questions to an MCQ question bank
  and turn on the template's Knowledge check round instead.

Mixing them works well: show a diagram in the opening question, then have them
draw the fix in a probe. Video, audio and slide decks can't be used yet: export
slides to PDF, and describe a recording in markdown.

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
| 10–15 min | 1 seed, 3–4 probes | 2 levels |
| 20 min | 1 seed, 5–6 probes | 3 levels |

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

## Before you propose it

- [ ] The seed is a situation from this job.
- [ ] The probes cover build, debug and lead, or say why not.
- [ ] Every probe has an answer a senior person would give.
- [ ] It fits the time table above.
