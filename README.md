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
`/codepraxis:ship`. The plugin drives the CLI below.

## Commands

```
codepraxis push    <q>                  save the question to the platform (a draft keeps one version)
codepraxis pull    <q|id>               get it back from the platform, solution included
codepraxis launch  <q> [--fresh]        open it in a container, the way a candidate gets it
codepraxis exec    <q> "<command>"      run a command there as the candidate (sends changes first)
codepraxis test    <q> [--visible]      Run, or the starter/solution check (sends changes first)
codepraxis logs    <q> [source]         setup, grader, exec, run or results
codepraxis categories                   the categories a public question can go into
codepraxis stop    <q>                  hand the container back now
codepraxis install claude-plugin        write the plugin into this repository instead
```

`<q>` is a folder under `challenges/`: a `pack/` (and `solution/`) for a coding
question, or a `question.json` (and `entities/`) for an AI interview question.

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
