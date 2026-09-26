# Architecture

The CLI is a thin client. Nothing about a question is executed locally.

| Module | Does |
|---|---|
| `cli.py` | Parses commands and prints results |
| `question.py` | Finds a question folder, maps its files to container paths, keeps `.codepraxis.json` (the open container, uploaded entity ids) |
| `coding.py` | Push and pull, launch (open the container, wait up to 2 minutes for `setup.sh`), sending changed files by hash, Run and Submit, and the starter/solution test |
| `interview.py` | Uploads entity files once per change, swaps file names for entity ids and back, runs the check, pushes and pulls the question |
| `progress.py` | Stage output: `→` start, `✓`/`✗` end with the time, `…` while waiting |
| `platform.py` | `Backend` (the public API, with `CODEPRAXIS_API_KEY`) and `Container` (the question's container, called directly) |
| `plugin/` | The Claude Code plugin, served from this repository by the marketplace manifest |

## Services

Backend, `https://www.codepraxis.co/api/public`, bearer API key:

- `GET /categories`
- `POST /challenges/direct?status=draft[&challenge_id=]` (push): a zip of `pack/<folder>/...` plus `solution/...`; a draft keeps one version, a published question gets a new one; the solution is kept privately
- `GET /challenges/{id}/files` (pull): the same zip back
- `GET /interview-questions/{id}` (pull): the question with each file it shows
- `POST /challenges/{id}/open`: the key owner's container, with the question loaded by the normal setup
- `DELETE /container`: hand that container back
- `POST /entities`, `POST /interview-questions`, `POST /interview-questions/check`

Container, `https://<container>/uvi`, no key:

- `/author/files` (list with hashes, read, write, delete), `/author/exec`, `/author/logs`, `/author/status`
- `/run?foldername=`, `/submit?challengeID=<challenge version id>`: the candidate's own Run and Submit

Paths in `/author/files` are pack-relative: `source/...` is the workspace, anything
else is the pack (`._tests/`, `._course_data/`, `setup.sh`, ...).
