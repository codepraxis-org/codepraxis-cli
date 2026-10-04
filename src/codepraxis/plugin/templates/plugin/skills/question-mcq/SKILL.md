---
name: question-mcq
description: Use when planning or writing an MCQ question bank (type mcq) for the Knowledge check round. What a good multiple-choice question is here, how to calibrate difficulty 1 to 5, how deep the bank must be for the adaptive round, when to use code, tables or an image, and the house rules. The files to produce are in output.md.
---

# MCQ question banks

A bank is a set of multiple-choice questions on one subject. A template's
**Knowledge check** round draws from one or more banks and adapts: it starts at
difficulty 3 and moves up after a right answer, down after a wrong one. What you
are measuring is **whether the candidate can apply what they know to a real
situation**, quickly, without help.

## When a bank beats a coding or interview question

- You want breadth: many areas checked lightly in a few minutes.
- The knowledge has one defensible answer: how a tool behaves, which fix is
  right, what a query returns.
- You want a fast screen before a longer coding or interview round.

When the skill is judgement with several good answers, or building something,
use an interview or coding question instead.

## What a good MCQ is

- **A real situation, not trivia.** The stem is something that happens in the
  job: a log line, a failing query, a config, a decision to make. Never "What
  does X stand for?", "Which year…", or a definition to recall.
  - Trivia: "What is the default isolation level in PostgreSQL?"
  - Real: "Two sessions read a balance, each subtracts 50 and writes it back,
    under PostgreSQL's default isolation. Starting from 100, what can the final
    balance be?"
- **One clearly best answer.** A senior person reads it once and agrees on the
  key. If experts could argue for two options, rewrite the stem until the facts
  decide it (add the constraint that rules one out).
- **Plausible distractors built from real mistakes.** Each wrong option is what
  someone who half-knows the topic would pick: the common misconception, the fix
  that treats the symptom, the right idea applied in the wrong place, the answer
  that was true in an older version. No joke options, no obviously absurd ones.
- **No hints in the wording.** The key is not the longest, most qualified or
  most technical option; it does not repeat the stem's words while the others
  don't; it is not the only one that fits the grammar. "Always" and "never" are
  not only in distractors. Options are the same kind of thing (four fixes, four
  outputs) and about the same length. Avoid "All of the above" and "None of the
  above". Spread the key across positions.
- **Answerable from the stem alone.** Everything needed is on the screen: the
  code, the numbers, the config. No guessing what the author meant.
- **One idea per question.** A question that needs three separate facts tells
  you nothing about which one was missing.
- **`multi_select` only when the real task has several right actions** ("Which
  of these would stop the duplicates?"). Say "Select all that apply". Every
  option must still be clearly right or clearly wrong.
- **The explanation says why the key is right and why each distractor is
  wrong**, in a sentence each. It is never shown to the candidate; reviewers and
  the next author read it.

## Calibrating difficulty 1 to 5

Difficulty is how much a candidate must know and combine, not how obscure the
fact is. Calibrate against someone working in the role.

| Level | What it takes | Example |
|---|---|---|
| 1 | One everyday concept applied directly; the stem names everything needed | "A query must list customers who have never placed an order. Which join finds them?" (LEFT JOIN … WHERE o.id IS NULL; distractors: INNER JOIN, RIGHT JOIN, CROSS JOIN) |
| 2 | One concept, but the candidate must read something short to see it: a few lines of code, an error, an output | A 6-line Python function with a mutable default list; "What does the third call return?" |
| 3 | Two concepts interacting, or finding the cause in a 10 to 20 line snippet, a table or a log | A retry wrapper around a POST that creates an order; a timeout after the server committed. "Which change stops duplicate orders?" (an idempotency key; distractors: longer timeout, fewer retries, a lock in the client) |
| 4 | A trade-off under stated constraints; every option is partly right and the numbers decide | A query pattern, its row counts and write rate, four candidate indexes. "Which index serves this best?" |
| 5 | A subtle interaction that experience teaches: concurrency, edge cases, failure modes the docs mention once | Two transactions under read committed, each checks a rule then writes; "Which outcome is possible?" (write skew) |

Check a level by asking: would most people in the role get it right (1-2), about
half (3), a strong minority (4), only the best (5)?

## Depth for the adaptive round

- **At least 3 questions at every level 1 to 5**, or the round runs out of fresh
  questions at that level. `codepraxis test` warns when a level has fewer.
- **More at 2, 3 and 4**, where most candidates spend the round. A good first
  bank is about 25: 3 / 6 / 7 / 6 / 3.
- Several questions at one level should cover different sub-topics, not the same
  fact reworded: a candidate who sees two of them learns nothing new, and neither
  do you.
- A round can draw from several banks, so a bank can stay focused on one subject.

## Code, tables and images

Prompts and options are Markdown.

- **Code** (fenced blocks with a language) when the question is about reading
  code: what it prints, where it fails, which change fixes it. Keep it to what
  matters, under about 20 lines. Options can be code too.
- **Tables** when the data decides the answer: query results, metrics, a config
  matrix, timings.
- **An image** only when the answer needs it: an architecture diagram to reason
  about, a chart whose shape matters, a console screen whose layout is the point.
  **Every image must be needed to answer.** If the question can be answered
  without looking, cut the image; if it is a picture of text or code, use text or
  code instead. Options can be images (four charts, four diagrams).
- Make your own images (diagrams, charts) from a script so the numbers agree with
  the text; never use another company's screenshots or documents. Give each image
  alt text that says what it shows (it is uploaded as the image's description).
- No PDFs, audio or video in a bank.

## Keeping a bank correct and current

Lessons from the first AI-engineering banks (MCP, LangChain, LangGraph):

- **Run every key you can.** Install the library at the version the stem names, run the
  snippet, and run the distractors too. A key that only "looks right" is the most common defect.
- **Name the version when behaviour depends on it** ("LangGraph 1.x", "MCP revision 2025-11-25",
  "Python SDK 2.x"). An unlabelled stem whose answer changed between versions is wrong for half
  the candidates.
- **Test the job, not the changelog.** At most about a third of a bank may hinge on what is new in
  the latest release, framed as a migration or upgrade problem. The rest must hold across the
  versions people actually run.
- **No fragile internals.** Exact default values, the precise nesting order of several wrappers,
  behaviour only true from one patch version, or behaviour the docs never state are trivia. Ask
  about the consequence a practitioner must understand instead.
- **The key must not stand out.** Check option lengths: if the key is the longest option in more
  than about a third of questions, rebalance. Check that distractors are not ruled out for a
  reason unrelated to the topic (a parameter that does not exist, a typo).
- **Have someone else check it.** A second pass that did not write the bank re-runs the keys
  and looks for a second defensible answer before the bank is pushed.

## House rules

- **Problem first.** The stem opens on the situation and the question; the
  candidate understands it in a few seconds.
- **No company, person or invented product names.** Use roles ("your team", "a
  junior engineer", "the customer"). Real technology keeps its real name
  (PostgreSQL, Kubernetes, Oracle EBS, pytest).
- **Plain English.** Short sentences, no idioms, no jokes: candidates read in
  their second language too.
- **Real behaviour only.** Every key must be true of the named product and
  version; if behaviour changed between versions, say which version.

## Before you push

- [ ] Every stem is a situation from the job, not a definition or a date.
- [ ] Each question has one clearly best answer, and the explanation says why
      each distractor is wrong.
- [ ] Distractors are real mistakes; nothing in the wording points at the key.
- [ ] Difficulties follow the table above; at least 3 per level, more at 2 to 4.
- [ ] Every image is needed to answer and has alt text.
- [ ] No company, person or invented product names; plain English.
- [ ] `codepraxis test` shows no errors, and you have read `preview.md` end to end.
