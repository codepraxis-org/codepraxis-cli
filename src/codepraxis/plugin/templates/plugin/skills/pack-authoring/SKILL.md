---
name: pack-authoring
description: Use when creating, editing, or debugging a CodePraxis challenge pack — any directory with metadata.json, backend.conf, source/, ._tests/, and ._course_data/. Covers the testCases contract, the two-fixture rule, and how to interpret `codepraxis validate` output.
---

# Authoring CodePraxis challenge packs

A pack is a directory the platform mounts into a container. The candidate gets
`source/`; the grader runs `._tests/test_1.py`.

## Layout

```
<pack>/
├── metadata.json            {"name": "snake_case_name"}   -> workspace dir name
├── backend.conf             {"BACKEND": "AI", "LANGUAGE": "PYTHON"}
├── setup.sh                 optional; installs dependencies
├── source/                  copied flat into the candidate workspace
│   └── README.md            how to run; current state of the starter
├── ._tests/test_1.py        a `testCases` class
└── ._course_data/
    ├── course_toc.json      selects the active test module
    └── feature.md           the Instructions tab
solution/                    SIBLING of <pack>, never inside it
```

`solution/` sits beside the pack so it is never packaged and never shipped to a
candidate. Putting it inside the pack leaks the answer.

## The rule that matters most

Every pack is validated twice:

- **solution** — `source/` + `solution/` overlaid. Must pass **everything**.
- **starter** — `source/` alone. Must **fail**.

A starter that passes means the tests do not discriminate, and every candidate
scores full marks. When you write a test, ask: *what in `source/` makes this
fail today?* If nothing does, the test is decorative.

Keep `source/` minimal — the stub the grader needs to call, and nothing that
implies a solution architecture. Never leave a working implementation there.

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
  name, so `test_case_01` and `test_case_1` collide. Use `test_case_1`, `test_case_2`.
- **`RUN`** must be ≤ the number of `test_case_*` methods, and
  `len(RunCaseInputs)` must equal `RUN` or the candidate panel misaligns.
- **`timeout_window` is milliseconds**, not seconds.
- **No top-level imports of packages installed by `setup.sh`.** The runner
  imports the test module immediately after spawning `setup.sh`, so the install
  may not have finished. Import inside the method instead.

The returned tuple is `(expected, output)`. Write both for a candidate to read —
"Empty list, then add one note" beats "Case 1 input".

## Workflow

```bash
codepraxis validate --local <pack>     # seconds; run constantly while editing
codepraxis validate --remote <pack>    # the real container; required to publish
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
| `Test execution error` | The test itself raised; fix the test before the starter |

When a fix is needed, change the **test or the starter**, not the harness.
