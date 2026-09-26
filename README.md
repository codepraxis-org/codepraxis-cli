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
codepraxis categories                   the categories a public question can go into
codepraxis push    <q>                  send changed files; the first push opens the container
codepraxis pull    <q> [path]           get files back from the container
codepraxis exec    <q> "<command>"      run a command in the workspace as the candidate
codepraxis test    <q> [--visible]      Run, or the full starter and solution check
codepraxis logs    <q> [source]         setup, grader, exec, run or results
codepraxis publish <q>                  save the question as a draft and print its URL
codepraxis stop    <q>                  hand the container back early
codepraxis install claude-plugin        write the plugin into this repository instead
```

`<q>` is a folder under `challenges/`: a `pack/` (and `solution/`) for a coding
question, or a `question.json` (and `entities/`) for an AI interview question.

Nothing runs on your machine. The first `push` saves the question as a draft and
opens it in your container, where `setup.sh` runs as it does for candidates.
After that, pushes send only changed files, and `test` uses the candidate's own
Run and Submit. A draft can be previewed but not assigned; publish it from its
page on the website.

`CODEPRAXIS_API_URL` points the CLI at another platform (default
`https://www.codepraxis.co/api/public`).
