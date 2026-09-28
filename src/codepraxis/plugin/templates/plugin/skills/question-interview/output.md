# Output: AI interview questions (`interview`)

An interview question is one row in the interview bank (the `questions`
table), plus any entities it shows. There is no container. You write:

```
challenges/<slug>/
├── spec.md
├── question.json                        the question
├── entity-src/make_entities.py          makes every file in entities/ (see "Making the files")
└── entities/                            files the question shows, if any
    ├── architecture.png
    ├── loader.sql
    ├── invoice_loader/                  a folder: shown as a repo (explorer + editor)
    │   ├── README.md
    │   └── src/loader.py
    ├── walkthrough.mp4
    └── walkthrough.mp4.description.md   what the interviewer reads for the video
```

`codepraxis push` uploads each file (and folder) `question.json` names, puts the
returned ids into `question.json` where the name is used, and saves the question
as a **draft**. The author publishes it from the website, which first checks that
it can run.

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
| `seed_highlights` | yes | Lines lit up when the question opens: `[{"file": "loader.sql", "lines": [88, 110]}]`, with `"path"` for a file inside a repo |
| `max_probes` | no | How many probes may fire |
| `probes` | when fired | The probe tree (below) |

Each **probe** is `{id, description, solution, withheld_solution_parts, hints,
duration, entities, editable, highlights, next}`:

- `id`: a number, unique among its siblings.
- `description`: what the candidate is asked when it fires.
- `solution`: what a good answer contains, written for the interviewer.
- `entities`: file names shown when this probe fires. They join the files already
  on screen; nothing shown earlier disappears.
- `editable`: which of this probe's own `entities` the candidate may edit.
- `highlights`: lines lit up when this probe opens, in the `seed_highlights`
  shape. May point at any file on screen by then, including the opening question's.
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

Files the candidate is shown, as tabs across the top of the file pane (like an
editor), each named by its file name. **Name files neutrally**: the candidate
sees the names, so never `bug_is_here.sql`.

| What you put in `entities/` | Type | The candidate sees |
|---|---|---|
| `.py`, `.sql`, `.js`, `.log`, any other text | `code` | Monaco editor with colouring and line numbers |
| A **folder** | `repo` | An explorer beside the editor, each open file a tab |
| `.md` | `markdown` | Rendered, with a Source view for picking lines |
| `.png`, `.jpg`, `.gif`, `.webp` | `image` | The image, fitted; a click zooms |
| `.pdf` | `pdf` | The PDF inside its tab |
| `.pptx`, `.ppt`, `.docx`, `.doc` | converted to `pdf` | The PDF. `push` converts with LibreOffice; without it, slides are refused and Word goes up as a download link |
| `.mp4`, `.mov`, `.webm` | `video` | A player |
| `.mp3`, `.wav`, `.m4a`, `.ogg` | `audio` | A player |
| `.excalidraw` | `excalidraw` | A diagram they can pan and zoom |

**Where files appear.** On the opening question (`entity_refs`), on a probe
(`entities`, shown when it fires) or on a hint (`entities`, shown when it's given,
on a tab marked **Hint**). Once shown, a file stays for the rest of the question,
and a file that arrives mid-question is marked New and opened. Refer to files by
their name in `entities/`; `push` swaps in the ids.

**Descriptions.** The interviewer never sees a file, only a text version of it:
code and markdown as they are, a PDF's text, an image described by a vision model,
a repo as its file list then every file. To write that text yourself, put
`<name>.description.md` beside the file (or folder). It replaces the automatic
text. **Audio and video need one**: nothing can read them, so `push` refuses a
recording without a description. Describe what is seen as well as what is said.

**Repos.** At most 200 text files and 500 KB of text between them; `push` refuses
a bigger folder, and so does the platform. `.git`, `node_modules`, caches and
binary files are left out. The interviewer reads the whole repo on every turn of
a stage that shows it, so keep only what the question needs.

**Read-only or editable.** Every file is read-only unless marked: `"editable":
true` on an `entity_refs` entry, or its name in a probe's `editable` list. Only
code, markdown, repos and diagrams can be editable.

- An editable code file, markdown file or repo is typed into, and the
  candidate's version goes with their next answer. The interviewer reads their
  version from then on, marked as the candidate's.
- An editable `.excalidraw` on a `draw-probe` question is where the whiteboard
  starts: they draw on your diagram rather than a blank canvas, and their drawing
  is read as a revision of it.

**Attaching lines.** In any text file, read-only or not, the candidate can select
lines and **Attach to answer**. The lines go with their answer labelled with the
file and line numbers, so the interviewer knows exactly what "this" means.

**Highlights.** `seed_highlights` and a probe's `highlights` light up line ranges
when that stage opens, and bring their file to the front. Use them to point at
what a stage is about without saying it. Lines are 1-based and inclusive; a file
in a repo needs `"path"`. The interviewer can also highlight lines while it
talks (the screen supports it); it will once its prompt is given the ability.

## Making the files

Generate every file in `entities/` from one script, `entity-src/make_entities.py`,
so numbers agree across files and a fix is one edit and a rerun:

- Derive each number once (simulate the runs, the eval, the bill) and write every
  file from those values. `assert` the invariants: totals add up, percentages match
  their counts, the chart and the CSV agree, the dates fall on the weekdays you say.
- Keep it deterministic (fixed seeds), so a rerun re-uploads only what changed.
- Use the helpers in `codepraxis.exhibits` (standard library only; they call Chrome,
  ffmpeg and a text-to-speech command when you use them):

  ```python
  from codepraxis.exhibits import write, html_to_png, html_to_pdf, frames_to_video, dialogue_to_audio, MAC_VOICES

  write(OUT / "incident.log", log_text)
  html_to_png(dashboard_html, OUT / "dashboard.png", 1200, 700)      # a screen, a slide, a diagram
  html_to_pdf(report_html, OUT / "report.pdf")                        # text the interviewer can read
  frames_to_video([(frame1_html, 3), (frame2_html, 4)], OUT / "replay.mp4")
  dialogue_to_audio([(MAC_VOICES["uk_male"], "Thanks for joining."),
                     (MAC_VOICES["us_female"], "Happy to.")], OUT / "call.m4a")
  ```

  Draw charts with any library (matplotlib works well) and save the PNG.
- **Look at every image** before you push: legible at about 1000 px wide, nothing
  overflowing or clipped, no large empty areas. Read every PDF page.
- **Describe every image, audio and video** in `<file>.description.md` with every
  number, label and relationship the question depends on; the interviewer reads
  nothing else. For audio, the full transcript with who speaks; for video, what
  happens with timestamps.
- Realistic formats: real log lines, real stack traces, real diff headers, real YAML.
  Trim long files and say so in the file (`[... 412 lines not shown ...]`).

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
- An entity the interviewer can't read (no text for it).
- A highlight on a file not on the candidate's screen at that stage, or a range
  that runs backwards.
- A probe's `editable` naming a file that probe doesn't show.

Warnings:

- No `seniority`, no `question_prompt`, or no `max_probes`.
- No hints on the opening question or on a probe.
- No minutes on the opening question or on a probe.
- A very short opening question, or choices set on a question that isn't `mcq`.
- A `withheld_solution_parts` phrase that appears nowhere in that stage's answer
  key or solution: quote it the way the solution words it.
