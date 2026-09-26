# Architecture

The CLI is a thin client. Nothing about a question is executed locally.

| Module | Does |
|---|---|
| `cli.py` | Parses commands and prints results |
| `question.py` | Finds a question folder, maps its files to container paths, keeps `.codepraxis.json` (the open container, uploaded entity ids) |
| `coding.py` | Saves the draft, opens the container, syncs files by hash, waits for `setup.sh`, runs Run and Submit, and the starter/solution test |
| `interview.py` | Uploads entity files once per change, swaps file names for entity ids, runs the check, saves the question |
| `platform.py` | `Backend` (the public API, with `CODEPRAXIS_API_KEY`) and `Container` (the question's container, called directly) |
| `plugin/` | The Claude Code plugin, served from this repository by the marketplace manifest |

## Services

Backend, `https://www.codepraxis.co/api/public`, bearer API key:

- `GET /categories`
- `POST /challenges/direct?status=draft[&challenge_id=]`: a zip of `pack/<folder>/...` plus `solution/...`; stored without the solution
- `POST /challenges/{id}/open`: the key owner's container, with the question loaded by the normal setup
- `DELETE /container`: hand that container back
- `POST /entities`, `POST /interview-questions`, `POST /interview-questions/check`

Container, `https://<container>/uvi`, no key:

- `/author/files` (list with hashes, read, write, delete), `/author/exec`, `/author/logs`, `/author/status`
- `/run?foldername=`, `/submit?challengeID=<challenge version id>`: the candidate's own Run and Submit

Paths in `/author/files` are pack-relative: `source/...` is the workspace, anything
else is the pack (`._tests/`, `._course_data/`, `setup.sh`, ...).
