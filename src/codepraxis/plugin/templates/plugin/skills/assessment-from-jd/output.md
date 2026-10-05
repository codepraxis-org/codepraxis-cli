# Output: an assessment template

A template is one folder beside `challenges/` and `mcq/`. There is no container.
You write:

```
templates/<slug>/
├── PLAN.md            JD requirement → round → question, with minutes
├── template.json      the rounds and their questions (below)
└── .codepraxis.json   written by the CLI: the template's id, version and status
```

## PLAN.md

Short: the author reads it to agree the plan, the next author to change it.

```markdown
# <Template name>

Role: <title>, <seniority>, <years>. AI assistant: on | off.
Budget: 110 minutes. Total: 107 minutes.

| JD requirement | Round | Question | Status | Minutes |
|---|---|---|---|---|
| "Builds and supports PL/SQL interfaces" | Coding | 52 Rerun-safe invoice load | published | 50 |
| (same) | Code review | from their submission | | 10 |
| "Tunes slow month-end programs" | Interview | 7 Month-end tuning · or 12 Slow concurrent request | published | 15 |
| "Designs approval workflows" | Interview | `po_approval` (new) | draft | 15 |
| "Knows EBS modules and tables" | Knowledge check | bank 7 EBS Technical, 12 questions | published | 12 |

## Gaps

- `po_approval`: no interview question on approval workflows. Planned with
  question-interview; pushed as draft 488.

## Left out

- "Nice to have: OAF personalisation": not a must-have.
```

## template.json

```json
{
  "name": "Oracle EBS Technical Consultant, Senior",
  "description": "For senior EBS technical consultants. A PL/SQL interface to make rerun-safe, a review of that code, an interview on tuning and workflows, and a knowledge check on EBS tables and modules.",
  "category": "oracle-e-business-suite",
  "proctoring": {"webcam_proctoring": true, "screen_recording": true, "identity_photo": true},
  "ai_assistant": false,
  "coding": {
    "questions": [{"ref": 52, "minutes": 50}],
    "pools": []
  },
  "code_review": {"minutes": 10},
  "interview": {"questions": [[7, 12], "po_approval"]},
  "mcq": {"banks": [7], "questions": 12, "minutes": 12}
}
```

| Field | Required | What it is |
|---|---|---|
| `name` | yes | What recruiters see: the role and level |
| `description` | no, but write it | One or two plain sentences: who it is for, what each round covers |
| `category` | no | A slug from `codepraxis categories`, or `null` |
| `proctoring` | no | `webcam_proctoring`, `screen_recording`, `identity_photo`, each `true` or `false` (default `false`) |
| `ai_assistant` | no | `true` gives every candidate the AI agent in every round. Default `false` |
| `coding` | no | `null` for no coding round |
| `coding.questions` | | `[{"ref": <ref>, "minutes": N}]`. `minutes` defaults to the question's own |
| `coding.pools` | | `[{"refs": [<ref>, <ref>, …], "pick": 1, "minutes": N}]`: each candidate gets `pick` of them, `minutes` each. At least 2 refs |
| `code_review` | no | `{"minutes": 10}`, or `null`. Only with a coding round |
| `interview` | no | `{"questions": [<ref>, [<ref>, <ref>], …]}`, or `null`. A list is a group of alternatives: one is asked |
| `mcq` | no | `{"banks": [<ref>, …], "questions": 1 to 50, "minutes": 1 to 180}`, or `null` |

A **ref** is a platform id (a number from `codepraxis library`), or a local
question folder (`"invoice_rerun"`, `"challenges/invoice_rerun"`, `"mcq/ebs_tables"`)
that has been pushed: the CLI reads its id from the folder.

Minutes:

- Coding: each question's `minutes`, plus `pick × minutes` per pool.
- Interview: from the questions themselves, the longest of each group, added up.
  It must come to 10 to 90 minutes. To change it, change the questions.
- Code review and knowledge check: their `minutes`.

## Commands

```bash
codepraxis library [--kind coding|interview|mcq] [--category <slug>] [--q "<words>"] [--json]
codepraxis test <slug>      # resolve every ref, check it, print minutes per round and the total
codepraxis push <slug>      # save as a draft template; prints its link
codepraxis pull <id> --template [--into templates/<slug>]
```

- `library` prints one table per kind: id, status, minutes (`q` for a bank's
  question count), name, categories. `--json` adds descriptions, topics,
  seniority and tech stack, for choosing.
- `test` exits non-zero on any `✗`: a ref that is not pushed, not in the library or
  retired; a repeated question; code review with no coding; a round outside its
  limits; no rounds at all. It lists questions that are still drafts (allowed in a
  draft template) with `!`.
- `push` runs the same checks first. The first push saves a **new draft** and keeps
  its id in `.codepraxis.json`. A later push **replaces the draft** (the platform
  gives it a new id; the CLI remembers it). Once the template is published in the
  dashboard, a push **publishes its next version at once**, and may not hold draft
  questions.
- Publishing is done in the dashboard, never by the CLI: first the draft
  questions, then the template.
- `pull <id> --template` writes `template.json` with every ref a platform id, and
  remembers the id, so the next push edits that template. `pull <slug>` refreshes
  a folder that was pushed.
