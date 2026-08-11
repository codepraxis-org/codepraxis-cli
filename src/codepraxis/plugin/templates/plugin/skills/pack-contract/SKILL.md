---
name: pack-contract
description: Use when writing or debugging the files inside a CodePraxis question — the testCases class, the pack layout, setup.sh, or anything the runner reads. Covers the mechanical contract, the two-fixture rule, container constraints, and how to read validate output. For deciding whether a question is any good, see question-design.
---

# The pack contract

Everything here comes from the runner, not from taste. Violating any of it makes
a question fail inside the container, usually with an error that does not point
at the cause.

## Layout

```
challenges/<slug>/
├── spec.md                  the plan. not read by the runner
├── pack/
│   ├── metadata.json        {"name": "snake_case_name"}  -> workspace dir name
│   ├── backend.conf         {"BACKEND": "AI", "LANGUAGE": "PYTHON"}
│   ├── publish.json         catalog identity: title, difficulty, time limit
│   ├── setup.sh             optional; installs dependencies
│   ├── source/              copied flat into the candidate workspace
│   │   └── README.md        how to run; current state of the starter
│   ├── ._tests/test_1.py    a `testCases` class
│   └── ._course_data/
│       ├── course_toc.json  selects the active test module
│       └── feature.md       the Instructions tab
└── solution/                SIBLING of pack/, never inside it
```

Each question gets its own directory. The solution is found as the pack's
sibling, so two questions sharing a parent would resolve to the same
`solution/` — that is how one question's reference answer gets overwritten by
another's.

`solution/` must never be inside `pack/`. The pack is uploaded verbatim.

## The rule that matters most

Every question is validated twice:

- **solution** — `source/` + `solution/` overlaid. Must pass **everything**.
- **starter** — `source/` alone. Must **fail**.

A starter that passes means the tests do not discriminate, and every candidate
scores full marks. When you write a case, ask: *what in `source/` makes this
fail today?* If nothing does, the case is decorative.

Keep `source/` minimal — the stub the grader calls, and nothing that implies a
solution architecture. Never leave a working implementation there.

## The `testCases` contract

```python
class testCases:
    def __init__(self, user_wxpace) -> None:   # EXACTLY one arg after self
        self.RUN = 3                            # visible cases; rest are hidden
        self.RunCaseInputs = [...]              # len() must equal RUN
        self.userWxpace = user_wxpace           # the workspace path
        self.exe = ""
        self.default_timeout_window = 60000     # MILLISECONDS
        self.usage = "prod"
        self.msg = ""

    def test_case_1(self, timeout_window=60000, override=1):
        ...
        self.msg = "PASS"                       # pass/fail is decided by THIS
        return "what success looks like", "what happened"
```

Non-negotiables, each of which breaks the runner:

- **One constructor argument.** A two-arg `__init__` fails with
  `missing 1 required positional argument`.
- **`self.msg == "PASS"`** decides the verdict. The return value never does.
- **No zero-padded names.** Ordering uses the first run of digits in the method
  name, so `test_case_01` and `test_case_1` collide. Use `test_case_1`,
  `test_case_2`.
- **`RUN`** is how many cases are visible: the first N, in order. It must be no
  greater than the number of `test_case_*` methods, and `len(RunCaseInputs)`
  must equal it or the candidate's panel misaligns.
- **`timeout_window` is milliseconds**, not seconds.
- **No top-level imports of packages installed by `setup.sh`.** The runner
  imports the test module immediately after spawning `setup.sh`, so the install
  may not have finished. Import inside the method instead.

The returned tuple is `(expected, output)`. Write both for a candidate to read —
"Empty list, then add one note" beats "Case 1 input".

## Cases run one at a time

A sequential loop, each case waiting for its own timeout window *plus* the
default one. Total submit time is the sum of every case, and candidates submit
more than once. A case that calls a model or waits on the network is paid in
full, every run — that is an argument for fewer, sharper cases.

The visible cases are re-run constantly while someone works, so they must
finish in seconds.

## The container

- **`curl` is not installed.** It is present during the image build and purged
  on the way out. `wget`, pip and npm work.
- **Git cannot reach a network.** `git-upload-pack` and friends are removed.
  Candidates can commit locally, but nothing clones or pushes.
- **`setup.sh` runs on every container load**, as the `praxis` user, so pip
  needs `--user`. It is not a build step: a three-minute install costs every
  candidate three minutes. **Pin every version** — an unpinned install resolves
  to whatever is current that day, and a breaking release later fails during
  someone's assessment.
- **Editor extensions can be installed** at setup time; that is a legitimate
  part of question design.

Already in the image: Python 3, Node 20, gcc, g++, make, clangd, .NET 8, the
ARM toolchain, QEMU, Renode, git, tmux. Anything else is a `setup.sh` install.

## Workflow

```bash
codepraxis validate <name>              # seconds; run constantly while editing
codepraxis validate --remote <name>     # the real container; required to publish
```

Local is advisory. It reproduces loading, ordering and scoring, but it does not
run `setup.sh`, does not have the image's packages, and has no LLM proxy — it
reports those as notes rather than passing silently. Never treat a local pass as
validation.

## Reading the output

| Symptom | Cause |
|---|---|
| `starter passes every test` | `source/` contains a working implementation, or the assertions are too weak |
| `missing 1 required positional argument` | Two-argument `__init__` |
| `RUN=n but only m test_case_* methods exist` | `RUN` is higher than the number of cases |
| `RunCaseInputs has n entries` | Panel rows will not line up with `RUN` |
| `Zero-padded case names sort ambiguously` | Rename to unpadded integers |
| `pack.layout` | The pack is at the top level; it belongs at `<question>/pack/` |
| `Test execution error` | The test itself raised; fix the test before the starter |

When a fix is needed, change the **test or the starter**, not the harness.
