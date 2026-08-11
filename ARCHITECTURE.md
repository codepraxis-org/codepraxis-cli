# How this works

This explains the shape of the CLI and why it is shaped that way. It is written
for someone new to the codebase. If you only want to *use* the tool, read the
README or run `codepraxis guide`.

---

## What we are actually building

CodePraxis gives candidates real engineering work instead of algorithm puzzles.
A company sends someone a question; they open a browser and land in a real
editor, in a real container, with real code in front of them. They fix or build
something, and hidden tests decide whether it worked.

This CLI is how a company **makes** those questions.

The hard part is not the file format. The hard part is that a good question is
hard to write, and a bad one is expensive: it either passes everyone, fails
everyone, or measures something other than the job. So most of the design here
is about making the good version the easy one.

---

## The core idea: a question is a folder

```
challenges/webhook-debug/
  spec.md              the plan — what this tests and why
  publish.json         catalog identity — id, title, difficulty, time limit
  metadata.json        the workspace directory name
  backend.conf         question type and language
  setup.sh             installs what the question needs
  source/              what the candidate starts from
  ._tests/test_1.py    the tests, which the candidate never sees
  ._course_data/
    course_toc.json    picks the active test module
    feature.md         the instructions tab
solution/              the reference solution — a SIBLING, never inside
```

Two files are ours, not the runner's. `spec.md` is the plan, kept in version
control beside the code it describes so that an edit six months later can
recover the original intent. `publish.json` is the question's catalog identity;
before it was adopted, those values were passed as one-off command-line flags,
which meant a question's identity lived in someone's shell history.

`solution/` sits outside the pack on purpose. That is what keeps it out of the
archive that goes to candidates.

### The rule everything rests on

Every question is run **twice**:

- with `source/` **plus** `solution/` overlaid — this must pass every test
- with `source/` **alone** — this must fail

The second one is what authors forget. If the starter passes, the tests do not
discriminate and every candidate scores full marks. A question that cannot fail
is not measuring anything.

---

## The lifecycle

```
plan  →  build  →  review  →  try  →  ship  →  edit
```

| Step | What happens | Where it runs |
|---|---|---|
| **plan** | Talk it through, agree what to test, write `spec.md`. No code. | Claude, via the plugin |
| **build** | Write the pack, tests, setup script and reference solution. | Claude, via the plugin |
| **review** | Audit the result and repair what fails. Runs inside build. | Claude + CLI checks |
| **try** | Open it exactly as a candidate would. Nothing published. | CLI → platform |
| **ship** | Publish as a draft, then promote to live. | CLI → platform |
| **edit** | Pull a question back down, change it, publish a new version. | CLI → platform |

Two of those steps are Claude workflows and four are CLI operations. That split
matters: **judgement lives in the plugin, mechanics live in the CLI.** Deciding
whether a question is any good is not something a Python function can do.
Deciding whether the tests pass is not something a language model should be
trusted with.

---

## Why plan mode carries most of the weight

Everything after planning is mechanical. Planning is the only step where a
wrong answer produces a bad question, so it gets two phases and two gates.

**Phase one is conversation.** Claude establishes three things early, because
everything else derives from them: how long the assessment is, what stack it
uses, and where it is coming from — a fresh idea, an existing question in some
other format, or a repository to mine. Then it keeps asking until it
understands, which is three more questions for some subjects and ten for
others.

It stops asking when it can write down three things: the signal in one
falsifiable sentence, the exact invocation and output contract, and at least
three cases that fail for different reasons. Without a stopping rule an
open-ended interview becomes an interrogation.

**Phase two is the document.** Only written once a short sketch has been agreed,
because producing a polished plan for the wrong question wastes everyone's time.

### Gate A — can a model just solve it?

Candidates have an AI agent and an LLM endpoint inside the container. So a
question a model answers from the brief alone is not an assessment.

The draft brief is handed to a model, cold, and the attempt is judged against
the case table. If it solves it, **the plan stops** and Claude says which
property made it trivial. Partial success is the target. A total miss usually
means the brief is unclear rather than the question being hard.

What survives the probe, strongest first: context the model has never seen
(your repo, your schema quirk, your log format), debugging rather than
authoring, decisions with no single right answer, integration volume, and
hidden cases that punish the obvious approach.

There is a real tension here. The clearer a brief is, the more one-shot-able it
becomes. The resolution is to be **precise about the contract and silent about
the approach**.

### Gate B — can we actually provision it?

Any stack is allowed. `setup.sh` runs on every container load, so Java, Go,
Rust or a database server are all just installs. The gate does not grant
permission; it checks that setup really provisions what the question needs and
prices the cost. Only genuine impossibility stops a plan — Docker-in-Docker
without privilege, or anything needing more than one container.

---

## Things about the container that change question design

These are real constraints, and several of them silently break otherwise
sensible questions.

- **`curl` is not there.** It is installed during the image build and purged on
  the way out. `wget`, pip and npm survive.
- **Git cannot reach a network.** `git-upload-pack` and friends are removed.
  Candidates can commit locally — and some questions grade that history — but
  nothing clones or pushes.
- **Setup runs on every load, by every candidate.** Not once at build time. A
  three-minute install is three minutes of a sixty-minute assessment. It also
  means unpinned versions rot: `pip install openai` resolves to whatever is
  current that day, and a breaking release later fails during someone's
  assessment rather than during ours. Pin everything.
- **Setup runs in parallel with the first test load.** The runner imports the
  test module right after spawning setup, which is why test modules must import
  setup-installed packages inside methods rather than at the top.
- **Test cases run one at a time.** A sequential loop, each case waiting for its
  own timeout window plus the default. Total submit time is the sum of every
  case, so a question with ten slow cases makes the candidate wait minutes on
  every submit.

Free in the image: Python 3, Node 20, gcc, g++, make, clangd, .NET 8, the ARM
toolchain, QEMU, Renode, git, tmux, and an editor with Python and C++ tooling.

---

## How the code is laid out

```
src/codepraxis/
  cli.py            argument parsing and wiring, nothing else
  commands/         one module per user-facing action
  domain/           what a pack is, what a result is, the runner contract
  packio/           finding, loading, archiving packs
  validation/       the lint rules
  execution/
    local/          the pure-Python harness
    remote/         the platform client
  reporting/        human and JSON output
  scaffold/         templates for `codepraxis new`
  plugin/           the Claude Code plugin, shipped inside the wheel
```

A few decisions worth knowing:

**No runtime dependencies.** The local harness has to run on an author's
machine with nothing but a Python interpreter. Even the network code uses
`urllib` rather than `requests`. Keep it that way.

**`cli.py` only wires things up.** Executors and reporters are chosen there and
injected, so commands do not know whether they are running locally or remotely,
or whether output is going to a terminal or to JSON.

**`domain/contract.py` is a mirror.** Every constant in it has a counterpart in
the production runner, with the source file and line recorded next to it.
Mirrors drift, so `tests/conformance/` replays the harness against a corpus of
real questions and asserts the verdicts. That corpus is private and lives
outside this repository — point `PRAXIS_CONFORMANCE_PACKS` at it.

---

## Local and remote are a trust boundary

| | Runs | Speed | Counts? |
|---|---|---|---|
| `validate --local` | Pure Python, on your machine | seconds | No — advisory |
| `validate --remote` | The real runner image | ~1 min | **Yes — gates publish** |

Local reproduces how the runner loads, orders and scores a question, so it
catches most mistakes in the inner loop. It is **not** the container: it does
not run `setup.sh`, does not have the image's packages, and has no LLM proxy.
Anything it cannot check is reported as a note rather than passing silently.

Publishing always requires a remote run. Local results never qualify, because a
published question can be sent to candidates immediately.

---

## Publishing rules

- **Remote validation runs first**, and the run is consumed, so one validation
  cannot justify publishing repeatedly.
- **A reference solution is required.** It is what proves the question is
  solvable.
- **Draft by default.** `--live` is deliberate.
- **The company comes from your API key.** The CLI never sends a company id.
  Ownership is derived server-side, so a compromised or mistyped client cannot
  publish into someone else's catalog.
- **`--challenge-id` adds a version** to an existing question, keeping its id,
  assignments and history. Without it, publishing always creates a new
  question — right the first time, a duplicate every time after.

---

## The command surface

Everything is a subcommand. The old flag forms (`--publish`, `--list`,
`--edit`, `--delete`, `--login`, `--install`, `--example`) still work, are
hidden from help, and print a pointer to their replacement. They shipped in a
released version, so CI jobs depend on them, and breaking those silently is
worse than carrying the aliases.

```
codepraxis                  where am I, what is next
codepraxis guide            the whole thing explained
codepraxis login
codepraxis install claude-plugin
codepraxis new <name>
codepraxis lint [question]
codepraxis validate [question] --local | --remote
codepraxis ship [question] [--live] [--challenge-id N]
codepraxis list
codepraxis edit <id> [--title ...] [--open]
codepraxis delete <id>
codepraxis example
```

A bare `codepraxis` prints status, not help. It used to dump the argparse
listing — a wall of flags that tells a new author nothing about what to *do* —
and it is the first thing everyone types, which makes it the best onboarding
surface we have. It reads the directory and answers one question, in the spirit
of `git status`:

```
codepraxis — authoring as Acme Corp

  challenges/webhook-debug
    plan        ready
    pack        8 cases
    solution    present
    published   #214 · draft

Next:
    codepraxis ship --live challenges/webhook-debug
```

It only reports what it can determine from local files. Whether a question has
*passed* validation is deliberately not guessed at — the CLI does not record run
results, and inventing a state we cannot observe is worse than omitting it.

Two more onboarding rules: **every command ends by printing the next one**, and
the guide leaves out anything Claude handles for the author. The `testCases`
contract and the pack layout are not in it, because an author using the plugin
never writes either by hand and showing them makes the job look harder than it
is.

---

## The Claude Code plugin

The plugin is **served from this repository**. A `.claude-plugin/marketplace.json`
at the repo root makes the repo itself a Claude Code marketplace, so enabling it
is two lines that are identical on every machine:

```
/plugin marketplace add codepraxis-org/codepraxis-cli
/plugin install codepraxis@codepraxis
```

That is the whole reason the repository is public. It also decouples two things
that update at different speeds: **the CLI is a tool you install; the plugin is
content that should update on its own.** A wording fix in a prompt reaches every
user on the next marketplace refresh, with no PyPI release involved.

The plugin lives at `src/codepraxis/plugin/templates/plugin/`, which the root
manifest points at. Keeping it inside the package rather than at the repo root
is deliberate: it is the same directory the wheel ships, so there is exactly one
copy. A second copy at the root would be a second thing to keep in sync, and it
would drift.

```
.claude-plugin/marketplace.json          the repo IS the marketplace
src/codepraxis/plugin/templates/
  marketplace.json                       used only by the local install
  plugin/
    .claude-plugin/plugin.json
    commands/                            the slash commands
    skills/                              loaded when Claude touches a question
```

### The local fallback

`codepraxis install claude-plugin` writes the same layout into
`.codepraxis/claude-plugin/`, for working offline or trying a prompt edit before
merging it. Nothing is fetched from the network — templates are copied out with
`importlib.resources`, so it works from a wheel, a zip or an editable install.

Two details that were bugs before:

- **The printed path is `./`-relative, not absolute.** Claude Code reads a bare
  `foo/bar` as a GitHub owner/repo and tries to clone it, so the prefix is
  required — but an absolute path is machine-specific, and these instructions
  get copied between laptops.
- **The local marketplace is named `codepraxis-local`, the hosted one
  `codepraxis`.** Marketplace names are global, so sharing one means a local
  install silently displaces the hosted plugin, or is refused outright.

Installing refuses to overwrite an existing install without `--force`, because
an author may have edited the commands and silently reverting that is worse
than failing.

The skills are split by rate of change: **pack-contract** is mechanical and
changes when the runner changes; **question-design** is editorial and changes
when our opinion of a good question changes. Mixing them in one file meant
every editorial tweak touched the same file as the runner mirror.

---

## Where to start reading

- `cli.py` — the whole surface in one file
- `domain/contract.py` — everything the runner requires, with provenance
- `packio/loader.py` — how a directory becomes a `Pack`
- `execution/local/executor.py` — the harness that mirrors the runner
- `plugin/templates/` — the prompts that drive plan and build
