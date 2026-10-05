"""A question on the author's disk, and what the CLI remembers about it.

A question is a folder, ``challenges/<slug>/``:

    coding (``coding`` and ``coding-ai``)   interview
    ├── spec.md                              ├── spec.md
    ├── pack/          -> candidates         ├── question.json
    └── solution/      never shipped         └── entities/

An MCQ bank is a folder too, ``mcq/<slug>/``: ``bank.json`` (every question),
``images/`` (every image they use) and ``preview.md`` (written by ``test``).
An assessment template is ``templates/<slug>/template.json``: its rounds, and the
questions in them by platform id or by local folder.

The CLI keeps ``.codepraxis.json`` in that folder: which container the question
is open in, which entity files (or bank images) were uploaded under which id, a
bank's id, and a template's id, version and status. It holds no secrets, and the author can delete it to start fresh.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import PraxisError

STATE_FILE = ".codepraxis.json"
# .vscode is the candidate editor's own, created in the workspace; never the question's.
# ._git is the base repository push generates for source/; never kept on disk.
IGNORED_NAMES = frozenset({"__pycache__", ".DS_Store", ".git", "._git", ".pytest_cache", ".vscode"})
IGNORED_SUFFIXES = (".pyc",)


def ignored(rel: str) -> bool:
    parts = rel.split("/")
    return any(p in IGNORED_NAMES for p in parts) or rel.endswith(IGNORED_SUFFIXES)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class LocalFile:
    """One file as the container names it: ``source/...`` or a pack path."""

    path: str
    disk: Path
    executable: bool

    def read(self) -> bytes:
        return self.disk.read_bytes()


class Question:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.slug = root.name

    # ── finding it ────────────────────────────────────────────────────

    @classmethod
    def find(cls, name: str, cwd: Path | None = None) -> Question:
        """``name`` is a slug under ``challenges/``, ``mcq/`` or ``templates/``, or a path to the folder."""
        cwd = cwd or Path.cwd()
        for candidate in (Path(name), cwd / name, cwd / "challenges" / name, cwd / "mcq" / name,
                          cwd / "templates" / name):
            if candidate.is_dir() and any(
                (candidate / marker).exists() for marker in ("pack", "question.json", "bank.json", "template.json")
            ):
                return cls(candidate.resolve())
        raise PraxisError(
            f"No question '{name}'. Expected challenges/{name}/ with a pack/ folder (coding) "
            f"or a question.json (AI interview), mcq/{name}/ with a bank.json (MCQ bank), "
            f"or templates/{name}/ with a template.json (assessment template)."
        )

    @property
    def kind(self) -> str:
        if (self.root / "question.json").is_file():
            return "interview"
        if (self.root / "bank.json").is_file():
            return "mcq"
        if (self.root / "template.json").is_file():
            return "template"
        return "coding"

    def require_coding(self, command: str) -> None:
        if self.kind == "mcq":
            raise PraxisError(
                f"`codepraxis {command}` is for coding questions. An MCQ bank has no container: "
                "use `codepraxis test` to check it and write preview.md, and `codepraxis push` to save it."
            )
        if self.kind == "template":
            raise PraxisError(
                f"`codepraxis {command}` is for coding questions. A template has no container: "
                "use `codepraxis test` to check its questions and minutes, and `codepraxis push` to save it."
            )
        if self.kind != "coding":
            raise PraxisError(
                f"`codepraxis {command}` is for coding questions. An AI interview question has no "
                "container: use `codepraxis test` to check it and `codepraxis push` to save it."
            )

    # ── coding files ──────────────────────────────────────────────────

    @property
    def pack(self) -> Path:
        return self.root / "pack"

    @property
    def solution(self) -> Path:
        return self.root / "solution"

    def folder_name(self) -> str:
        """The workspace folder name, from ``pack/metadata.json``."""
        try:
            return json.loads((self.pack / "metadata.json").read_text())["name"]
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            raise PraxisError(f"{self.pack / 'metadata.json'} must be {{\"name\": \"<folder>\"}}: {exc}") from exc

    def pack_files(self) -> dict[str, LocalFile]:
        """Every pack file under its container path. ``pack/source/x`` is ``source/x``."""
        files: dict[str, LocalFile] = {}
        for disk in sorted(self.pack.rglob("*")):
            if not disk.is_file():
                continue
            rel = disk.relative_to(self.pack).as_posix()
            if ignored(rel):
                continue
            files[rel] = LocalFile(rel, disk, os.access(disk, os.X_OK))
        return files

    def solution_files(self) -> dict[str, LocalFile]:
        """Solution files under the workspace paths they replace: ``solution/x`` is ``source/x``."""
        files: dict[str, LocalFile] = {}
        if not self.solution.is_dir():
            return files
        for disk in sorted(self.solution.rglob("*")):
            if disk.is_file():
                rel = disk.relative_to(self.solution).as_posix()
                if not ignored(rel):
                    files[f"source/{rel}"] = LocalFile(f"source/{rel}", disk, os.access(disk, os.X_OK))
        return files

    def visible_case_count(self) -> int | None:
        """``self.RUN`` from the active grader, so hidden cases can be told apart."""
        for test in sorted((self.pack / "._tests").glob("test_*.py")):
            match = re.search(r"self\.RUN\s*=\s*(\d+)", test.read_text(errors="replace"))
            if match:
                return int(match.group(1))
        return None

    @property
    def publish_json(self) -> Path:
        return self.pack / "publish.json"

    def read_publish(self) -> dict:
        try:
            return json.loads(self.publish_json.read_text())
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as exc:
            raise PraxisError(f"{self.publish_json} is not valid JSON: {exc}") from exc

    def remember_challenge_id(self, challenge_id: int) -> None:
        """Write ``challenge_id`` into publish.json, so the next publish is a new version."""
        data = self.read_publish()
        if data.get("challenge_id") == challenge_id:
            return
        data["challenge_id"] = challenge_id
        self.publish_json.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    # ── interview files ───────────────────────────────────────────────

    @property
    def question_json(self) -> Path:
        return self.root / "question.json"

    @property
    def entities_dir(self) -> Path:
        return self.root / "entities"

    def read_question(self) -> dict:
        try:
            return json.loads(self.question_json.read_text())
        except json.JSONDecodeError as exc:
            raise PraxisError(f"{self.question_json} is not valid JSON: {exc}") from exc

    def remember_question_id(self, question_id: int) -> None:
        data = self.read_question()
        if data.get("id") == question_id:
            return
        data = {"id": question_id, **{k: v for k, v in data.items() if k != "id"}}
        self.question_json.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    # ── MCQ bank files ────────────────────────────────────────────────

    @property
    def bank_json(self) -> Path:
        return self.root / "bank.json"

    @property
    def images_dir(self) -> Path:
        return self.root / "images"

    def read_bank(self) -> dict:
        try:
            data = json.loads(self.bank_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PraxisError(f"{self.bank_json} is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise PraxisError(f"{self.bank_json} must be one JSON object with a name and questions.")
        return data

    # ── state ─────────────────────────────────────────────────────────

    def state(self) -> dict:
        try:
            return json.loads((self.root / STATE_FILE).read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_state(self, **changes) -> dict:
        data = {**self.state(), **changes}
        (self.root / STATE_FILE).write_text(json.dumps(data, indent=2) + "\n")
        return data
