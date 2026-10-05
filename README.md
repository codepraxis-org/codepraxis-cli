# codepraxis

Build CodePraxis questions in the same container a candidate gets, and save
them to the platform as drafts.

```bash
pip install codepraxis
export CODEPRAXIS_API_KEY=...        # dashboard → Settings → API keys
```

Then, in Claude Code:

```
/plugin marketplace add codepraxis-org/codepraxis-cli
/plugin install codepraxis@codepraxis
```

and run `/codepraxis:plan`, `/codepraxis:build`, `/codepraxis:test`,
`/codepraxis:ship`, or `/codepraxis:assessment` for a whole assessment from a job
description. The plugin drives the CLI below.

## Commands

```
codepraxis push    <q>                  save the question to the platform (a draft keeps one version);
                                        an MCQ bank is checked, then replaced whole;
                                        a template is checked, then saved as a draft (or replaces its draft)
codepraxis pull    <q|id> [--mcq|--template]
                                        get it back from the platform, solution included (--mcq: a bank,
                                        images included; --template: a template, refs as platform ids)
codepraxis launch  <q> [--fresh]        open it in a container, the way a candidate gets it
codepraxis exec    <q> "<command>"      run a command there as the candidate (sends changes first)
codepraxis test    <q> [--visible]      Run, or the starter/solution check (sends changes first);
                                        an MCQ bank: the local checks, and preview.md;
                                        a template: every question checked, minutes per round
codepraxis library [--kind K] [--category C] [--q words] [--json]
                                        the questions and banks a template can use
codepraxis logs    <q> [source]         setup, grader, exec, run or results
codepraxis categories                   the categories a public question can go into
codepraxis stop    <q>                  hand the container back now
codepraxis install claude-plugin        write the plugin into this repository instead
```

`<q>` is a folder under `challenges/`: a `pack/` (and `solution/`) for a coding
question, or a `question.json` (and `entities/`) for an AI interview question.
An MCQ bank is a folder under `mcq/` with a `bank.json` and `images/`; `test`
checks it locally and writes `preview.md` (every question, images inline, ✅ on
the key) to review, and `push` uploads new or changed images and replaces the
bank, keeping its id in `.codepraxis.json`.

An assessment template is a folder under `templates/` with a `template.json`:
its rounds (coding, code review, AI interview, knowledge check) and the
questions in them, each a platform id or a local question folder that has been
pushed. `test` resolves and checks every question against the library and prints
the minutes per round; `push` saves it as a **draft** template (a later push
replaces the draft; once published in the dashboard, a push publishes its next
version). Draft questions are allowed in a draft template; publish them in the
dashboard first, then the template. The CLI never publishes a template.

Nothing runs on your machine. `push` saves the question to the platform as a
draft (a published question gets a new version); the reference solution is kept
privately. `launch` loads the pushed question into your container, where
`setup.sh` runs as it does for candidates and must finish within 2 minutes.
`exec` and `test` send your changed files to that container first, so each edit
is tried in seconds. A draft can be previewed but not assigned; publish it from
its page on the website.

Every command prints its stages: `→` started, `✓`/`✗` finished (with the time),
`…` while waiting (with what it is waiting for), and a final `Next:`.

`CODEPRAXIS_API_URL` points the CLI at another platform (default
`https://www.codepraxis.co/api/public`).
