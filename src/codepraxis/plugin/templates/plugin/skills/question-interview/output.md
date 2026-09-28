# Output: AI interview questions (`interview`)

An interview question is one row in the interview bank (the `questions`
table), plus any entities it shows. There is no container. You write:

```
challenges/<slug>/
├── spec.md
├── question.json            the question
└── entities/                files the question shows, if any
    ├── architecture.png
    └── loader.sql
```

`codepraxis push` uploads each file in `entities/`, puts the returned ids
into `question.json` where the file name is used, and saves the question as a
**draft**. The author publishes it from the website, which first checks that it
can run.

## question.json

```json
{
  "name": "Rerun-safe invoice interface",
  "mode": "open-probe",
  "topics": ["Interfaces and conversions", "EBS core"],
  "categories": ["oracle-integration-cloud"],
  "seniority": "senior",
  "duration": 15,
  "seed_duration": 5,
  "description_sections": {
    "signal": "Can they make a nightly interface safe to rerun, or do they only know the happy path?",
    "implement": "- **Find why a rerun duplicated invoices**\n- **Make it rerun-safe** without relying on the import",
    "audience": "**Good for:** senior EBS technical consultants.\n\n**Needs:** PL/SQL, Payables open interface."
  },

  "seed_question": "The nightly program below loads supplier invoices. Last night it failed halfway and operations reran it. This morning 14 invoices exist twice.\n\n**Walk me through how you'd find out why.**",
  "entity_refs": [{"file": "loader.sql", "editable": false}],

  "question_prompt": "Press for a diagnostic path grounded in evidence. A strong answer reaches commit placement and the self-billed invoice numbers without being led.",
  "answer_key": {
    "required_concepts": [
      "the staging status is only updated after the loop, so rows sent before the failure stay NEW",
      "the rerun sends those rows again",
      "a deterministic key (the source document id) detects invoices that already exist"
    ],
    "red_flags": [
      "deleting the duplicates by hand and rerunning",
      "blaming the import program without evidence"
    ],
    "good_additional_points": [
      "committing each invoice together with its staging status",
      "a reconciliation that counts invoices that exist, not rows sent"
    ]
  },
  "withheld_solution_parts": ["commit inside the loop"],
  "seed_hints": [
    {"id": 1, "text": "What state is a staging row in after the program dies halfway?", "entities": []}
  ],
  "max_probes": 3,
  "probes": [
    {
      "id": 1,
      "description": "Only the self-billed invoices were duplicated. Why those?",
      "solution": "Their invoice numbers are generated on each run, so the import's duplicate check can't match them.",
      "withheld_solution_parts": ["sequence"],
      "hints": [{"id": 1, "text": "Compare how those invoices get their numbers with the others.", "entities": []}],
      "duration": 4,
      "entities": [],
      "next": [
        {
          "id": 1,
          "description": "How would you make the rerun safe without relying on the import?",
          "solution": "Check the invoices table by source document id before sending, and commit each invoice with its status.",
          "withheld_solution_parts": [],
          "hints": [{"id": 1, "text": "What could the program check before it sends an invoice?", "entities": []}],
          "duration": 4,
          "entities": [],
          "next": []
        }
      ]
    }
  ]
}
```

## Fields

| Field | Candidate sees it | What it is |
|---|---|---|
| `name` | yes | A few words naming the subject, up to 80 characters |
| `mode` | no | `open-probe` or `draw-probe` (below); `mcq` is not available yet |
| `topics` | no | Ordered competencies; the first is the one the report scores |
| `categories` | public only | Category slugs, the same list coding questions use (below) |
| `seniority` | no | The level it's pitched at |
| `duration` | no | Minutes for the whole question |
| `seed_duration` | no | Minutes for the opening question before probing starts |
| `description_sections` | no | The question's page for whoever assembles an interview (below). Never shown to the candidate |
| `seed_question` | yes | The opening question, in markdown |
| `entity_refs` | yes | Entities shown with the opening question: `[{"file": "...", "editable": false}]` |
| `mcq_choices` | yes | `mcq` only: `[{"id": "a", "text": "..."}]`, or `{"id": "a", "file": "..."}` for a choice that is an entity |
| `question_prompt` | no | Brief for the interviewer: what to press on, and how hard |
| `answer_key` | no | Open answers: `required_concepts`, `red_flags`, `good_additional_points`. MCQ: `{"mcq_choice": ["a"]}`, the correct choice id or ids |
| `withheld_solution_parts` | no | Phrases the interviewer must never say about the opening question |
| `seed_hints` | on request | `[{"id", "text", "entities"}]`; each hint used lowers the score |
| `max_probes` | no | How many probes may fire |
| `probes` | when fired | The probe tree (below) |

Each **probe** is `{id, description, solution, withheld_solution_parts, hints,
duration, entities, next}`:

- `id`: a number, unique among its siblings.
- `description`: what the candidate is asked when it fires.
- `solution`: what a good answer contains, written for the interviewer.
- `entities`: file names shown when this probe fires.
- `next`: the probes one level deeper.

## Description sections

What the question's page shows to whoever is putting an interview together:
a few short sections, not the probes or the answer key. Same keys as a coding
question's `description_sections`, with interview headings:

| Key | Heading | What goes in it |
|---|---|---|
| `signal` | What it tests | One sentence |
| `task` | The question | One or two sentences. Without it the page shows `seed_question` |
| `starting_state` | What they see | The files, in a sentence: "the data model screenshot, the SQL, last month's output as a PDF" |
| `implement` | What they're asked | Three or four bullets, one per stage, bold lead words |
| `audience` | Who to ask it to | `**Good for:**`, `**Needs:**`, `**Worth knowing:**` |

Markdown, short. Don't describe each file's contents: name it.

## Categories

Where the question appears on the website. Get the list with `codepraxis
categories` and use the slugs that fit; if none does, use `misc`. They're the
same categories coding questions use, so an Oracle Integration Cloud interview
question sits beside the Oracle Integration Cloud coding questions.

- Only the admin account's questions (the public bank) have categories. Any
  other company's questions ignore them.
- Sending `categories` replaces the question's categories. An unknown slug is
  skipped; a new public question with none that exist goes to `misc`.
  Categories are never created by pushing.
- `categories` is not `topics`. A topic is the skill the question is scored on;
  a category is where it is filed.

## Modes

| `mode` | The candidate answers by… |
|---|---|
| `open-probe` | Typing, in the chat |
| `draw-probe` | Drawing on a whiteboard and explaining it in the chat |
| `mcq` | Not available yet: the interview doesn't show the choices. Use an MCQ question bank and the template's Knowledge check round |

`open-probe` and `draw-probe` are the only modes the interviewer can run today.

## Entities

Files the candidate is shown. Each one is converted to text so the interviewer
can read it too.

| Type | Files | Shown as |
|---|---|---|
| `markdown` | `.md` | Formatted text |
| `code` | `.py`, `.sql`, `.js`, … | Code with highlighting |
| `image` | `.png`, `.jpg` | An image (the interviewer reads a description of it) |
| `pdf` | `.pdf` | A link that opens the document |
| `doc` | `.docx` | A link that opens the document |
| `excalidraw` | `.excalidraw` | A whiteboard drawing; with `"editable": true` the candidate draws on it and their version is saved as their answer |

**Several code files** work: attach each file as its own `code` entity, in the
order the candidate should read them.

**Not usable yet: video, audio and slide decks.** The platform has no way to
turn them into text for the interviewer, so a question that uses one can't be
published. Until that lands, export slides to PDF and describe a recording in
markdown.

An entity can be attached to the opening question (`entity_refs`), to a probe
(shown when it fires) or to a hint (shown when it's used). In `question.json`,
refer to entities by their file name in `entities/`; `push` swaps in the ids.

## The check

`codepraxis test` runs the full check. Fix every **blocker** before the
question is published: the website's Publish button only refuses unreadable entities, so this
is the only place the rest are caught. Fix warnings unless you have a reason.

Blockers:

- No `topics`, no `answer_key`, or no `required_concepts` in it (open answers).
- No `duration`, or it's shorter than the opening question's minutes plus the
  longest chain of probe minutes.
- A phrase from `withheld_solution_parts` appears in the opening question, a
  probe or a hint.
- A probe with no `description` or `solution`; a probe or hint `id` used twice
  among siblings; probes deeper than `max_probes`.
- `mcq`: no choices, no `answer_key.mcq_choice`, or a key naming a choice that
  doesn't exist.
- An entity the interviewer can't read (video, for now).

Warnings:

- No `seniority`, no `question_prompt`, or no `max_probes`.
- No hints on the opening question or on a probe.
- No minutes on the opening question or on a probe.
- A very short opening question, or choices set on a question that isn't `mcq`.
