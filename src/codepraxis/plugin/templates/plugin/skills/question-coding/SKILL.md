---
name: question-coding
description: Use when planning a coding question where the candidate has no AI agent (type coding). What a good question looks like, which patterns work, how to size it for the time, and a worked example. The files to produce are in output.md.
---

# Coding questions without AI

The candidate works alone in a real container for a fixed time. What you are
measuring is whether they can do the job's core technical work, correctly,
under realistic conditions.

## Start from the job description

1. List the skills the job description ranks highest, or mentions most.
2. Pick **one core skill** the question is really about, plus one or two
   supporting skills it touches on the way.
3. Ask: what goes wrong in this job on a bad day? That failure is usually the
   question.

## Patterns that work

| Pattern | The candidate… | Good for |
|---|---|---|
| **Debug a real failure** | gets working-looking code, a symptom and a log, and finds 3–4 defects with different causes | Seniors and leads; hardest to fake |
| **Harden a data flow** | makes a load, sync or integration survive bad rows, reruns and partial failure | Integration, data and ERP roles |
| **Reconcile or analyse** | writes queries that explain a gap until it is fully accounted for | Data, finance-technical and support roles |
| **Tune without changing output** | makes slow code efficient, measured in counted work, not time | Database and backend roles |
| **Extend existing code** | adds one feature to a small real codebase without breaking it | Mid-level developers |

Prefer debugging over writing from scratch: finding why existing code is
subtly wrong is what experienced people do daily, and it lets a short question
go deep.

## How a question is shaped

**State the problem, never the path.** The question says what is wrong or what
is needed: "we're facing this problem, fix it", or "we need this, build it".
It never says which file to change or which function to update. Finding that
is part of the work. A question that names the file and function can be copied
out and solved elsewhere with AI.

**The solution spans several files.** Two to three files is ideal, so the
candidate has to understand how the pieces fit before changing any of them.
One file is acceptable only when the question can't be shaped any other way.

**Put a twist in the material.** Each question hides one thing in the code or
data that the brief doesn't mention, which the candidate discovers while
working. For example, an agent that must query a database where two values
are stored in one column, so they have to split it first. The twist changes
*how* they reach the result, never *what* the result must be.

**Leave real design decisions.** There should be two or three points where
more than one design works (where to validate, how to make a rerun safe, where
state lives). The code review round that follows reads their code and their
design; give it something to discuss.

**Keep the brief short and plain.** The brief is written in the build step,
and it has only:

- the problem name,
- a short description of the problem, in a few sentences,
- what they have, what "done" means, and the constraints (how it's run, what
  must not change).

Use simple, everyday words and short sentences. No jargon the job doesn't
use, no long explanations, no hints about the fix.

## Rules every question follows

1. **It happens in this job.** Start from a failure or request a team actually
   gets, never a textbook topic.
2. **Real names.** Tables, APIs, file formats and commands follow the real
   product, so an experienced person feels at home and an inexperienced one is
   exposed.
3. **Hidden cases punish the obvious approach.** Messy data and real failure
   sequences are where experience shows. Where it fits, include one adversarial
   case, such as "this isn't in the data, say so".
4. **State the outcome, never the approach.** The brief says exactly what
   "done" looks like (how it's run, the output, error behaviour). Hidden cases
   test that outcome, including on the twist; they never add a new
   requirement.
5. **A gradient, not a cliff.** Order hidden cases easy to hard, so someone who
   did most of the work scores most of the marks.
6. **Repeatable grading.** No timing assertions. Measure work in counts (rows
   read, API calls, function calls).

## Avoid

- Algorithm puzzles, definitions, trivia, CRUD scaffolding.
- Anything with a well-known answer online.

## Size it for the time

| Time | Reading | Writing | Hidden cases |
|---|---|---|---|
| 30 min | ≤ 5 min, given code ≤ 80 lines | 40–60 lines, or 2–3 defects | 3–4 |
| 40 min | ≤ 7 min, given code ≤ 120 lines | 60–90 lines, or 3–4 defects | 4–5 |
| 60 min | ≤ 10 min, given code ≤ 180 lines | 100–140 lines, or 4–5 defects | 5–6 |

Too big: give more in the starter or cut a case. Never raise the time.

## Example: the interface that duplicated invoices on rerun

- **Role:** Senior Oracle EBS technical lead. 40 minutes, no AI.
- **Signal:** can they find why an interface that "works" creates duplicates
  after a rerun and reports a false reconciliation, and make it rerun-safe?
- **Situation:** a nightly PL/SQL program loads invoices into Payables. It failed
  halfway, operations reran it, 14 invoices now exist twice, and the
  reconciliation email said everything matched.
- **Given:** the nightly load code (a loader package and a reconciliation
  package), the failed night's log, a mock Payables schema with the real
  interface tables, and a `run.py` tool. The brief doesn't say which file is
  wrong.
- **Twist:** self-billed invoices arrive with no invoice number, which the
  candidate only notices in the data.
- **Design decisions:** where the unit of work ends; where rejected rows live.
- **Planted defects:** commit inside the loop (rerun duplicates); a header sent
  when its lines failed; completion status always "success"; reconciliation
  counts interface rows instead of created invoices.
- **Hidden cases:** a bad row must not stop the run; import dies halfway, rerun
  creates no duplicate; one bad line rejects the whole invoice with the real
  reason; honest status; reconciliation matches what exists.

## Before you propose it

- [ ] The brief states the problem and never names a file or function.
- [ ] The solution spans two to three files.
- [ ] There is a twist in the material and two or three real design decisions.
- [ ] It happened, or plausibly happens, in this job.
- [ ] It fits the time table above.
- [ ] Every hidden case tests a rule the brief will state.
- [ ] Someone who did most of the work gets most of the marks.
