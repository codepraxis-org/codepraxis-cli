# Output: MCQ question banks (`mcq`)

A bank is one folder. There is no container and no spec.md is required (a plan
can live in `spec.md` beside it). You write:

```
mcq/<slug>/
├── bank.json          every question (below)
├── images/            every image the bank uses: png, jpg, jpeg, gif or webp
│   ├── retry-flow.png
│   ├── backoff-a.png
│   └── …
├── image-src/         optional: the script that makes images/, so numbers agree
├── .codepraxis.json   written by the CLI: the bank's id, uploaded image ids
└── preview.md         written by `codepraxis test`: every question rendered
```

## bank.json

```json
{
  "name": "HTTP retries and timeouts",
  "description": "Retries, idempotency and timeouts in services that call each other over HTTP.",
  "category": "misc",
  "questions": [
    {
      "key": "retry-001",
      "type": "single_select",
      "difficulty": 3,
      "prompt": "A checkout service calls the payment service with a 2-second timeout and retries once. The diagram shows one request.\n\n![Checkout calls payment; payment commits the charge at 2.4 s; checkout times out at 2.0 s and sends the request again](images/retry-flow.png)\n\nThe customer is charged twice. Which change stops this without losing retries?",
      "options": [
        {"text": "Raise the timeout to 5 seconds"},
        {"text": "Send an idempotency key with each charge"},
        {"text": "Retry only when payment answers 500"},
        {"text": "Wait 1 second before retrying"}
      ],
      "correct": [2],
      "explanation": "The charge committed before the timeout fired, so any retry repeats it. An idempotency key lets the payment service recognise the repeat and return the first result. A longer timeout or a delay only makes it rarer; retrying only on 500 stops it by giving up the retry after a timeout."
    },
    {
      "key": "retry-002",
      "type": "single_select",
      "difficulty": 2,
      "prompt": "This helper retries a call with backoff:\n\n```python\ndef call_with_retry(fn, attempts=3):\n    for i in range(attempts):\n        try:\n            return fn()\n        except TimeoutError:\n            time.sleep(2 ** i)\n```\n\nWhat happens when `fn` times out on every attempt?",
      "options": [
        {"text": "It raises the last `TimeoutError`"},
        {"text": "It returns `None` after sleeping 1, 2 and 4 seconds"},
        {"text": "It retries forever"},
        {"text": "It returns `None` after sleeping 0, 1 and 2 seconds"}
      ],
      "correct": [2],
      "explanation": "The loop swallows every TimeoutError and falls off the end, so it returns None; it sleeps 2**0, 2**1 and 2**2 seconds. It never re-raises, and range(3) ends."
    },
    {
      "key": "retry-003",
      "type": "multi_select",
      "difficulty": 4,
      "prompt": "A service's calls to a search backend over one day:\n\n| Percentile | Latency |\n|---|---|\n| p50 | 80 ms |\n| p99 | 900 ms |\n| p99.9 | 4 s |\n\nThe caller's own budget is 1.5 seconds per request, and it retries once. Which settings keep a request inside its budget? Select all that apply.",
      "options": [
        {"text": "700 ms timeout, one retry with a 700 ms timeout"},
        {"text": "1.5 s timeout, one retry with a 1.5 s timeout"},
        {"text": "A second request at 900 ms, first answer wins, both cut at 1.5 s"},
        {"text": "No timeout on either attempt, one retry on error"}
      ],
      "correct": [1, 3],
      "explanation": "700 + 700 ms fits in 1.5 s; a hedged request at p99 with a hard stop at 1.5 s fits too. Two 1.5 s attempts can take 3 s, and no timeout can wait the full 4 s tail."
    },
    {
      "key": "retry-004",
      "type": "single_select",
      "difficulty": 3,
      "prompt": "50 clients fail at the same moment. Each retries up to 4 times with exponential backoff and full jitter, base 100 ms. Each chart plots every client's delay before each retry. Which chart matches?",
      "options": [
        {"text": "", "image": "images/backoff-a.png"},
        {"text": "", "image": "images/backoff-b.png"},
        {"text": "", "image": "images/backoff-c.png"},
        {"text": "", "image": "images/backoff-d.png"}
      ],
      "correct": [3],
      "explanation": "C: the range of delays doubles at each retry and is spread from 0 up to it. A is a fixed delay, B is exponential with no jitter (every client retries together), D is jitter with no growth."
    }
  ]
}
```

The example is four questions to show each form (an image in the prompt, code, a
table with `multi_select`, image options). A real bank has at least 3 at every
difficulty; `test` warns until it does.

| Field | Required | What it is |
|---|---|---|
| `name` | yes | The bank's name, a few words |
| `description` | no | One plain line: what the bank covers |
| `category` | no | A slug from `codepraxis categories` (`misc` if none fits), or `null`. The template builder groups banks by it |
| `questions` | yes | 1 to 500 questions |
| `key` | no, but use it | A stable id you choose (`retry-001`). Unique in the bank; problems and pulls name it |
| `type` | yes | `single_select` (exactly one correct) or `multi_select` (one or more). Default `single_select` |
| `difficulty` | yes | 1 (easy) to 5 (hard); see SKILL.md |
| `prompt` | yes | Markdown: text, fenced code, tables, images `![alt](images/x.png)` |
| `options` | yes | 2 to 6. Each `{"text": "..."}` (Markdown), `{"text": "", "image": "images/x.png"}`, or both |
| `correct` | yes | Option positions, counting from 1: `[2]`, or `[1, 3]` for `multi_select` |
| `explanation` | no, but write it | Why the key is right and each distractor wrong. Never shown to the candidate |

Rules `codepraxis test` and the platform check:

- Every option has text or an image; no two text-only options have the same
  text (ignoring case).
- `correct` points at options that exist; a `single_select` has exactly one.
- Keys don't repeat.
- Every image is a file under `images/` (subfolders are fine), with a png, jpg,
  jpeg, gif or webp extension, and no spaces in its name. Nothing outside
  `images/`, no web URLs, no PDFs.
- Unknown keys are warned about and left out.
- Depth: a warning when any difficulty 1 to 5 has fewer than 3 questions.

## Commands

```bash
codepraxis test mcq/<slug>        # the checks above, and preview.md
# read mcq/<slug>/preview.md: every question, its images, ✅ on the key, the explanation
codepraxis push mcq/<slug>        # uploads new or changed images, then saves the bank
```

- `test` exits non-zero on any error. Fix them all, then read `preview.md` end to
  end in any Markdown viewer before pushing: a wrong key or a giveaway in the
  wording is easy to see there.
- `push` runs the same checks first and stops on any error. It uploads each image
  that is new or changed (by its bytes), with its alt text (or, for an option
  image, the option's text) as its description, and swaps `images/x.png` for the
  platform's image ids. It prints the bank id, the question count, the count per
  difficulty, and the bank's link. If the platform refuses the bank, it lists
  every problem.
- **A push replaces the whole bank.** The first push creates it and keeps its id
  in `.codepraxis.json`; every later push replaces the name, description,
  category and all questions. Questions in candidates' past attempts keep their
  own copy. Deleting `.codepraxis.json` makes the next push a new bank.
- The bank is live as soon as it is pushed: there is no draft. Pushing with the
  platform account's key puts it in the public library; any other key keeps it in
  that company.
- `codepraxis pull <id> --mcq [--into mcq/<slug>]` gets a bank back: `bank.json`
  with `images/` paths, and every image. `codepraxis pull mcq/<slug>` refreshes a
  folder that was pushed. A push straight after a pull uploads no image again.
- To use the bank, add it to a template's Knowledge check round on the website.
