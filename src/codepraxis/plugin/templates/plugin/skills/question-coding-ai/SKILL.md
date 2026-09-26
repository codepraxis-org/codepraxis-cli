---
name: question-coding-ai
description: Use when planning a coding question where the candidate has the AI agent (type coding-ai). What changes when an agent writes the code, which patterns survive it, how to size it, and a worked example. The files to produce are the same as for coding questions, in question-coding/output.md.
---

# Coding questions with AI

The candidate has an agent that writes code fast. Typing is no longer what you
measure. You measure **judgement**: whether they know the domain well enough to
make the decisions the agent can't, check its output against rules it doesn't
know, and defend their choices afterwards.

The patterns and the rules in `question-coding` still apply (real job, real
names, stated contract, easy-to-hard cases, no timing). This file covers what
changes.

## What makes a question survive an agent

An agent given only the brief will produce something that runs and passes the
visible cases. The question is only useful if it **fails hidden cases the
candidate should have known to check**. Build it from these:

1. **Domain rules the agent won't apply unless told.** Invoice numbers are
   unique per supplier, not globally. A submitted job is invisible until the
   session commits. A parent job can succeed while its child fails.
2. **Named decisions.** 4–6 decisions, each with at least two defensible
   options. The brief names each decision, never its answer. The candidate
   records each one in `DECISIONS.md`: chosen, rejected, why. Put
   `DECISIONS.md` in `source/` with one empty heading per decision.
3. **Several parts that must agree.** A mapping document, the code and the
   tests must say the same thing. Agents drift across files; a candidate who
   doesn't read the output ships the drift.
4. **Triage, not just fixing.** A list of tickets where some aren't bugs, or
   logs where some failures aren't the code's fault. The agent fixes whatever
   it is pointed at.

## Avoid

- Anything the agent solves from the brief alone. The test: a model given only
  the brief must fail **at least a third** of the hidden cases.
- Decisions with one right answer. That's a hidden requirement, not a decision.
- Grading the choice itself. Grade the consequences by running their code. An
  AI review of `DECISIONS.md` against the code is optional: add it only when a
  decision can't be checked by running the code.

## Size it for the time

| Time | Files the candidate delivers | Decisions | Hidden cases |
|---|---|---|---|
| 45 min | 3–4 | 4–5 | 5–6 |
| 60 min | 4–5 | 5–6 | 6–8 |

The time goes on reading, steering and checking, not typing.

## Example: the AP invoice interface, designed and built

- **Role:** Senior Oracle EBS technical lead. 45 minutes, AI on.
- **Signal:** can they design a production interface and catch the agent's EBS
  mistakes?
- **Situation:** invoices will arrive daily as a file; nothing exists yet.
- **Decisions:** unit of work (per invoice, file or batch); what happens when
  one line fails; where rejected rows live; where the business unit comes from;
  the duplicate key; what counts as a warning.
- **What the agent gets wrong unsteered:** inserts into the final tables
  directly, checks invoice numbers globally, commits per row, hard-codes the
  business unit.
- **Hidden cases:** no duplicates on rerun whatever unit of work was chosen;
  same invoice number for two suppliers both load; the program works for two
  business units; reconciliation ties.
- **Follow-up for the interview:** "You committed per invoice. What changes at
  200,000 invoices a night?"

## Before you propose it

- [ ] 4–6 named decisions, each with two defensible options.
- [ ] At least three domain rules the agent won't apply unprompted.
- [ ] A model given only the brief would fail a third of the hidden cases.
- [ ] Every hidden case tests a stated rule or a recorded decision.
