---
name: assessment-from-jd
description: Use when building a whole assessment (a template) from a job description. How to read the JD into must-have skills and a time budget, how to pick existing questions from the library, when a gap needs a new question, how to size the rounds, and how to save it as a draft template. The files to produce are in output.md.
---

# An assessment from a job description

A template is the whole assessment a candidate sits: up to four rounds, in this
order, each optional.

| Round | What it measures | Built from |
|---|---|---|
| **Coding** | Can they do the job's core technical work, alone or with the AI agent | Coding questions, or pools of interchangeable ones |
| **Code review** | Do they understand and defend the code they just wrote | Nothing to pick: written from their submission. Only after a coding round |
| **AI interview** | How real and how deep their experience is: judgement, design, debugging | Interview questions, one asked per group |
| **Knowledge check** | Breadth, fast: what they know across the stack | MCQ banks; adaptive, difficulty 1 to 5 |

What you are building is **the shortest assessment that covers every must-have
skill in the JD once**, with the strongest signal on the skill the role is really
about.

## 1. Read the job description

Write these down before looking at any question:

- **Role and seniority.** Title, years, and whether they lead others.
- **Must-have skills.** At most 6, ranked by how much the job depends on them. A
  skill the JD repeats, or puts in the title, ranks first. "Nice to have" items are
  not must-haves.
- **The core skill.** The one thing a bad hire in this role gets wrong. It gets the
  coding round, or the richest interview question.
- **Time budget.** What the author gives you; otherwise **90 to 120 minutes**.
  Juniors nearer 90, seniors and leads nearer 120.
- **AI assistant.** On when the job is done with AI tools today (the author says),
  off otherwise. It applies to the whole template.

Ask the author only for what the JD can't answer (usually the time budget and
whether the AI assistant is on). Ask in one message.

## 2. Decide the rounds

| Seniority | Typical shape (about 100 to 120 minutes) |
|---|---|
| Junior / mid | Coding 45 to 60 · code review 10 · knowledge check 10 to 15 · interview 15 to 30 |
| Senior | Coding 45 to 60 · code review 10 · interview 30 to 45 · knowledge check 10 |
| Lead / architect | Coding 30 to 45 (debug or review) · interview 45 to 60 · knowledge check optional |
| Role with no code (functional, configuration, support) | Interview 45 to 60 · knowledge check 15 to 20 |

- **Map every must-have to exactly one round.** A skill tested twice wastes the
  candidate's time; a skill tested nowhere is a gap.
- Code review only comes with a coding round. Keep it at 10 minutes.
- The interview takes 10 to 90 minutes in all; it lasts as long as its questions
  (the longest of each group, added up).
- A knowledge check is about one minute per question: 10 questions, 10 to 12
  minutes.

## 3. Pick from the library first

```bash
codepraxis library --json                         # everything this key can use
codepraxis library --kind interview --category <slug> --q "<words>"
```

For each must-have, look for a question that tests it. A question fits when:

- **Its categories, description and topics match the JD**, not just its title. Read
  the description: an "Oracle SQL" question about reporting does not test PL/SQL
  interfaces.
- **Its seniority and minutes fit** the slot you planned for it.
- **It is not a near-duplicate** of another question you picked (same scenario,
  same skill). Two banks on the same framework are near-duplicates too.

Prefer, in order: **published platform questions** (`"status": "published"`,
`"is_platform": true` for interview), then the company's own published ones, then
drafts. A draft can go in a draft template, but someone must publish it in the
dashboard before the template can be published.

Interview questions can be grouped as **alternatives** (each candidate is asked one
of the group), so candidates who share notes don't all see the same question.
Group only questions that test the same skill at the same depth, with durations
within a few minutes of each other.

## 4. Fill each gap with a new question

When no question fits a must-have, plan a new one with the skill for its kind:

| Gap | Skill to read | Then |
|---|---|---|
| Hands-on work in code, SQL, config files | `question-coding` (or `question-coding-ai` when the AI assistant is on) | `/codepraxis:plan`, `/codepraxis:build`, `codepraxis push` |
| Judgement, design, tools a container can't run | `question-interview` | the same |
| Breadth across a stack | `question-mcq` | the same |

New questions are pushed as **drafts**. Keep them few: a template that needs more
than two new questions usually means the JD has more must-haves than one
assessment should test. Say so and cut.

Reference a new question in `template.json` by its folder (`"invoice_rerun"`); the
CLI reads the id it was pushed under.

## 5. Write and save

1. Write `templates/<slug>/PLAN.md` and `templates/<slug>/template.json` (see
   `output.md`).
2. `codepraxis test <slug>`: every ref resolved and found in the library, each
   round's minutes and the total, and which questions are still drafts. Fix every
   `✗`. Check the total against the budget.
3. Show the author PLAN.md and the summary `test` printed. Change what they ask.
4. `codepraxis push <slug>`: saved as a **draft** template, with its link.

## 6. Hand off

Tell the author, with the link:

1. Review the template in the dashboard.
2. Publish each draft question it uses (each question's own page).
3. Then publish the template (its Publish button refuses while any question is
   still a draft, and names them).

A published template can be set on a position and sent. Later pushes of a draft
replace it; a push to a published template publishes its next version at once.

## House rules

- **No generic questions.** Every question must trace to a line of the JD in
  PLAN.md. "General coding ability" is not a JD line.
- **One skill, one round.** No skill is tested twice.
- **No company, person or invented product names** in anything you write.
- **Plain English** in the name and description: recruiters read them. The
  description says who it is for and what each round covers, in one or two
  sentences, with no answers in it.
