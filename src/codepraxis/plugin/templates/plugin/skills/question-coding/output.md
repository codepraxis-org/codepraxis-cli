# Output: coding questions (`coding` and `coding-ai`)

The files a coding question is made of, and the rules the runner enforces. Used by
`build` and `test` for both `coding` and `coding-ai` questions; the only
difference in the files is `"ai_enabled"` in `publish.json`.

## Layout

```
challenges/<slug>/
├── spec.md                  the plan; never shipped
├── pack/                    shipped to every candidate
│   ├── metadata.json        the workspace folder name
│   ├── backend.conf         always the same (below)
│   ├── publish.json         the catalog entry (below)
│   ├── setup.sh             optional; installs dependencies and extensions
│   ├── source/              the candidate's workspace
│   ├── ._tests/             the grader, flat
│   │   └── test_1.py
│   └── ._course_data/
│       ├── course_toc.json
│       └── feature.md       the problem statement
└── solution/                the reference answer; never shipped
```

## metadata.json

The name of the candidate's workspace folder. Use a short version of the
question title, lowercase, words joined with underscores (never dashes). It is
also the question's slug.

```json
{"name": "invoice_rerun_duplicates"}
```

## backend.conf

Always exactly this. Don't change it.

```json
{"BACKEND": "AI", "LANGUAGE": "PYTHON"}
```

## source/

What the candidate sees. Everything in `source/` is copied as it is into their
workspace when the container opens. Keep it to what the question needs: the
starting code, data and tools, and a `README.md`.

**Git.** The candidate's progress is saved only as git history, so their
workspace starts as a repository with one base commit of `source/`. You don't
create it: `codepraxis push` builds it (branch `main`, author `CodeGuru
<guru@codepraxis.com>`, "Setting up the test environment") and ships it as
`source/._git`, which the container turns into `.git`. Don't put a `.git` of
your own in `source/`; it is ignored, so your history never reaches a
candidate.

## ._tests/

The grader. Keep it flat: `test_1.py` and any files it needs sit directly in
`._tests/`, never in sub-folders. The candidate never sees this folder.

## ._course_data/

`course_toc.json` selects which test file is active. For one test file it is
always:

```json
{"instruction_1": {"file": "feature.md", "metadata": {"STATUS": "IN_PROGRESS"}}}
```

`feature.md` is the problem statement (below).

## solution/

The reference answer. It mirrors `source/` paths and is laid over it during
`codepraxis test`. It is a sibling of `pack/`, never inside it, and never
reaches a candidate.

## publish.json

The question's catalog entry. Write it in the build step, from `spec.md`.
`codepraxis push` reads it and writes the question to the database.

```json
{
  "challenge_name": "EBS Invoice Interface: Duplicates on Rerun",
  "description": "One or two sentences shown in the question list.",
  "tech_stack": ["Oracle PL/SQL", "SQL"],
  "difficulty": 2,
  "max_time": 40,
  "ai_enabled": false,
  "delivery_mode": "oa",
  "categories": ["oracle-integration-cloud"],
  "description_sections": {
    "signal": "What a strong candidate does that a weak one doesn't.",
    "task": "The situation, and what they must make true.",
    "starting_state": "**Given:** ...\n\n**Missing:** ...",
    "implement": "- **Point:** one line each",
    "audience": "**Fits:** ...\n\n**Assumes:** ...\n\n**Note:** time, AI on or off."
  }
}
```

| Field | Required | What it is |
|---|---|---|
| `challenge_name` | yes | The title in the question list and on the question page |
| `description` | yes | One or two sentences for the question list |
| `tech_stack` | yes | Tags, as a list |
| `difficulty` | yes | 1 easy, 2 medium, 3 hard |
| `max_time` | yes | Minutes |
| `ai_enabled` | yes | `false` for `coding`, `true` for `coding-ai` |
| `delivery_mode` | no | `oa` (default), or `take_home` for questions that are only sent, never browsed |
| `categories` | public only | Category slugs (below) |
| `description_sections` | yes | The five sections the question page shows, all five, in markdown. Written for the hiring company, not the candidate |
| `challenge_id` | added by the CLI | Written back after the first push; keep it, so the next push updates this question instead of creating a duplicate |

**Where the question appears** depends on the account whose API key pushes it:

- **The admin account** pushes to the public catalog, verified, in the
  categories named in `categories`.
- **Any other company's account** pushes into that company's own questions.
  `categories` is ignored.

**Choosing categories.** Get the current list with `codepraxis categories`
(it calls `GET /api/public/categories`) and use the slugs of the ones that fit.
If none fits, use `misc`. An unknown slug is skipped, and a question with no
valid category goes to `misc`; categories are never created by pushing.

**Drafts.** A question pushed for the first time is a draft. A draft can be
previewed, but not assigned or added to a template. The author publishes it
from the question's page on the website.

## setup.sh

- Runs on **every** container load, twice at once: as the candidate user and
  as root. Both runs must succeed. Every second it takes, every candidate waits.
- **Starts with `set -euo pipefail`.** Without it, a failing step (a `pip
  install` that can't find a version) is ignored and setup still reports
  success; the candidate then meets the failure mid-question. The CLI warns when
  it is missing.
- **Finishes within 2 minutes.** `codepraxis launch` stops a setup that runs
  longer. Install only what the question needs, pinned, and nothing large.
- `pip install --user`, and **pin every version**: an unpinned install resolves
  to whatever is current on the day and breaks later.
- Already in the image: Python 3, Node 20, gcc/g++/make, .NET 8, git, tmux.
  Don't reinstall them. Anything else, such as `oracledb==2.5.1
  cryptography==43.0.3` for an Oracle SQL question, is installed here.
- `curl` is not installed (use `wget` or Python). Git cannot reach the network.
- **Editor extensions.** The candidate's editor is VS Code running as
  code-server, so extensions come from code-server's marketplace (Open VSX),
  not Microsoft's. Install them with a pinned version:
  `code-server --install-extension <publisher>.<name>@<version>`.

## Questions with a database (Oracle)

Each candidate gets their own Oracle schema; no login is ever shipped in the
pack. Copy the pattern from `question-bank/challenges/ebs_ap_invoice_interface_rerun`:

- `source/db/`: `connection.json` (dsn, wallet dir and wallet password only),
  the wallet, `schema.sql`, `seed.sql`, and `provision.py`.
- `setup.sh`, after installing `oracledb==2.5.1 cryptography==43.0.3`, runs
  `db/provision.py` for the candidate's run only (`if [ "$(id -u)" -ne 0 ]`),
  after waiting for the workspace to be copied in. It asks the platform for a
  schema (`POST /api/misc/oracle-schema`), keeps the login in
  `~/.config/codepraxis/<folder>.json` (outside the workspace), and installs
  the tables with `run.py reset --schema`. It reuses the schema while its login
  works; schemas are removed three hours after creation.
- `run.py` and the grader's `oradb.py` read the login from that file; the
  grader calls `oradb.use_workspace(self.userWxpace)` before connecting.
- Seed with one PL/SQL block (one round trip), and reset per case.

## feature.md: the problem statement

`._course_data/feature.md` is what the candidate reads, in the Instructions
tab. It is the most important file in the question: everything they need to
solve the problem must be in it, and nothing else. Keep it short, like a good
HackerRank problem statement.

A typical shape:

```markdown
# <Problem name>

<The problem: what's happening, and what they need to make true.>

## What you have
<The code, data and tools they're given.>

## Requirements
<What "done" means.>

## Constraints
<How it's run and submitted, and what must not change.>
```

Add an example or other sections when the problem needs them; leave out any
that don't help.

Rules:

- Write what the candidate needs, and nothing more. Don't pad it.
- Plain, everyday English.
- State the problem, never the path: never name the file or function to
  change, and never mention the twist.
- Every rule a hidden case checks must be stated here.

## README.md

`source/README.md` is secondary: how to run things and how the workspace is
laid out. It may list the files, but never says which one to change. It never
repeats or extends the requirements; those live only in `feature.md`.

Every file `feature.md` or `README.md` mentions must exist in `source/`.

## The grader: `._tests/test_1.py`

The grader is run by Koro, the platform's test runner. It is one Python class,
`testCases`, with one method per test case.

### The class

```python
class testCases:
    def __init__(self, user_wxpace) -> None:     # exactly one argument after self
        self.RUN = 2                              # how many cases are visible
        self.RunCaseInputs = [                    # one line per visible case, shown before it runs
            "Clean file: every invoice loads",
            "An invoice on a closed supplier site",
        ]
        self.userWxpace = user_wxpace             # the candidate's workspace path
        self.exe = self.userWxpace + "main.py"    # what the case runs, relative to the workspace
        self.default_timeout_window = 60000       # milliseconds
        self.usage = "prod"
        self.msg = ""                             # the verdict for override=1 cases
```

- **Visible vs hidden.** The first `RUN` cases are visible: the candidate runs
  them with **Run** and sees their results. The rest are hidden and only run on
  **Submit**. `RunCaseInputs` must have exactly `RUN` entries.
- **Cases** are methods named `test_case_1`, `test_case_2`, … (no zero-padding;
  they run in number order). Any other method is a helper and is ignored.
- **`self.exe`** is the program the runner starts for override `0` and default
  cases. Relative paths are resolved from the workspace.
- **Imports.** Wrap imports of packages that `setup.sh` installs in
  `try/except`, or import them inside the method: the grader is loaded while
  setup may still be running.
- **`timeout_window`** is per case, in milliseconds.

### What the candidate sees

Every visible case shows three things on the results panel, with a pass or fail
mark. Each must be exact:

- **Input:** exactly what the case gives the candidate's code. The panel shows
  the case's line from `RunCaseInputs`, so that line must be the exact input
  the test passes (for stdin cases), or the exact setup (for other cases:
  "Seed: 12 invoices, 16 rows; import fails after 5; program run twice").
- **Expected:** the exact result we expect ("3", or "12 invoices, 16 rows
  PROCESSED, retcode 0").
- **Output:** exactly what the candidate's code produced, on a pass and on a
  fail ("13 invoices for 12 documents").

| `override` | The runner… | Return | Expected | Output |
|---|---|---|---|---|
| `0` | Runs `self.exe` with the input on stdin, trims its stdout, and compares it with the expected string exactly | `(input, expected_output)` | Your expected output | Their output |
| `1` | Runs your method; the verdict is `self.msg == "PASS"` | `(expected, output)` | `expected` | On pass the returned `output`; on fail `self.msg` |
| `2` | Sends the named files to an AI with your checklist; it never runs code | `(panel_text, [[files], checklist])` | `panel_text` | The AI's verdict and reason |
| none | Runs a reference program in `._tests/` (`main.py`) and `self.exe` with the same input, and compares outputs | `input` | The reference's output | Their output |

Inside an override `1` case, `execute_bin(input, exe)` runs a program with
`input` on stdin and returns `(stdout, stderr, seconds)`. The runner provides
it; don't import it.

### Writing cases like HackerRank

Where the question has an input and an output, show them the way a problem
site does: the exact input, and the exact output expected for it. Put the same
input in `RunCaseInputs`, so the panel shows it.

```python
self.RUN = 2
self.RunCaseInputs = ["1 2", "3\n10 20 30"]

def test_case_1(self, timeout_window=5000, override=0):
    return "1 2\n", "3"            # expected output: no trailing newline

def test_case_2(self, timeout_window=5000, override=0):
    return "3\n10 20 30\n", "60"
```

For anything that isn't a single input and output (a database, files, an API),
use override `1`. Return the exact expected result and what their code actually
produced; on a failure, put what it produced in `self.msg`:

```python
self.RunCaseInputs = [..., "Seed: 12 invoices, 16 rows; import fails after 5; program run twice"]

def test_case_3(self, timeout_window=90000, override=1):
    expected = "12 invoices, one per document; 0 rows left unfinished"
    try:
        ...                                        # set up, run their code twice, count
        actual = f"{invoices} invoices for {documents} documents; {left} rows left unfinished"
        self.msg = "PASS" if actual == expected else actual
        return expected, actual
    except Exception as exc:
        self.msg = f"The program raised: {exc}"
        return expected, self.msg
```

Write both values in the candidate's terms ("13 invoices for 12 documents"),
never the grader's internals.

### Choosing an override

- **`0`** when a case is one input and one exact output.
- **`1`** for everything else that runs their code. This is most cases.
- **`2`** only for judging a written file or the structure of the code, never
  for "does it work".
- **none** when a reference program defines the right answer and writing the
  expected output by hand isn't practical.

## The two fixtures

`codepraxis test` runs the grader twice:

- **Starter** (`source/` alone): must **fail** every hidden case, each for its
  own reason. What in `source/` makes each case fail today? If nothing, the case
  is decoration.
- **Solution** (`source/` + `solution/`): must **pass** everything.

Keep `source/` minimal: the stub the grader calls, never a working
implementation.
