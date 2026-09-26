"""Checking and saving an AI interview question.

``question.json`` names the files it shows by their name in ``entities/``. The
platform names them by entity id. So each file is uploaded once (again only if
it changes), its id remembered, and every file name in the question swapped for
its id before the question is checked or saved.
"""

from __future__ import annotations

import base64
import copy
import json
from pathlib import Path

from . import progress
from .errors import PraxisError
from .platform import Backend, website_url
from .question import Question, sha256

_TYPES = {
    ".md": "markdown", ".markdown": "markdown",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image", ".webp": "image",
    ".excalidraw": "excalidraw",
    ".pdf": "pdf",
    ".docx": "doc", ".doc": "doc",
    ".mp4": "video", ".mov": "video", ".webm": "video",
}


def entity_type(path: Path) -> str:
    """The entity type for a file; anything not listed is code."""
    return _TYPES.get(path.suffix.lower(), "code")


def upload_entities(q: Question, backend: Backend, names: set[str]) -> dict[str, int]:
    """Entity ids for these files, uploading any that are new or changed."""
    cached = q.state().get("entities", {})
    ids: dict[str, int] = {}
    for name in sorted(names):
        path = q.entities_dir / name
        if not path.is_file():
            raise PraxisError(f"question.json shows '{name}', but {path} doesn't exist.")
        data = path.read_bytes()
        digest = sha256(data)
        hit = cached.get(name)
        if hit and hit.get("sha256") == digest:
            ids[name] = int(hit["entity_id"])
            continue
        kind = entity_type(path)
        progress.line(f"  uploading {name} ({kind}, {len(data) // 1024} KB)…")
        result = backend.post_json("/entities", {
            "type": kind,
            "content_base64": base64.b64encode(data).decode(),
            "meta": {"filename": name},
        }, timeout=180)
        ids[name] = int(result["entity_id"])
        cached[name] = {"sha256": digest, "entity_id": ids[name]}
        q.save_state(entities=cached)
    return ids


def referenced_files(question: dict) -> set[str]:
    """Every entity file name the question uses, anywhere in it."""
    names: set[str] = set()
    for ref in question.get("entity_refs") or []:
        if isinstance(ref, dict) and ref.get("file"):
            names.add(ref["file"])
    for choice in question.get("mcq_choices") or []:
        if isinstance(choice, dict) and choice.get("file"):
            names.add(choice["file"])
    for hint in question.get("seed_hints") or []:
        names.update(_file_names(hint.get("entities")))
    for probe in _walk(question.get("probes") or []):
        names.update(_file_names(probe.get("entities")))
        for hint in probe.get("hints") or []:
            names.update(_file_names(hint.get("entities")))
    return names


def with_entity_ids(question: dict, ids: dict[str, int]) -> dict:
    """The question as the platform stores it: file names replaced by entity ids."""
    out = copy.deepcopy(question)
    out["entity_refs"] = [
        {"id": ids[ref["file"]], "editable": bool(ref.get("editable", False))} if "file" in ref else ref
        for ref in out.get("entity_refs") or []
    ]
    choices = []
    for choice in out.get("mcq_choices") or []:
        if "file" in choice:
            choice = {**{k: v for k, v in choice.items() if k != "file"}, "entity_id": ids[choice["file"]]}
        choices.append(choice)
    if choices:
        out["mcq_choices"] = choices
    for hint in out.get("seed_hints") or []:
        hint["entities"] = _ids(hint.get("entities"), ids)
    for probe in _walk(out.get("probes") or []):
        probe["entities"] = _ids(probe.get("entities"), ids)
        for hint in probe.get("hints") or []:
            hint["entities"] = _ids(hint.get("entities"), ids)
    return out


def prepared(q: Question, backend: Backend) -> dict:
    question = q.read_question()
    ids = upload_entities(q, backend, referenced_files(question))
    return with_entity_ids(question, ids)


def check(q: Question, backend: Backend) -> bool:
    """The platform's pre-publish check. True when nothing blocks publishing."""
    with progress.step("Uploading new or changed files in entities/"):
        question = prepared(q, backend)
    with progress.step("Running the platform's checks") as s:
        result = backend.post_json("/interview-questions/check", question)
        s.result(f"Checks ran: {len(result.get('blockers') or [])} blocker(s), "
                 f"{len(result.get('warnings') or [])} warning(s)")
    blockers = [f for f in result.get("blockers") or [] if isinstance(f, dict)]
    warnings = [f for f in result.get("warnings") or [] if isinstance(f, dict)]
    findings = blockers + warnings
    for label, group in (("✗ blocker", blockers), ("! warning", warnings)):
        for f in group:
            where = f" ({f['field']})" if f.get("field") else ""
            progress.line(f"{label}{where}: {f.get('message')}")
            if f.get("fix"):
                progress.line(f"    fix: {f['fix']}")
    if not findings:
        progress.done("No problems found.")
    elif not blockers:
        progress.done("Nothing blocks publishing.")
    return not blockers


def save(q: Question, backend: Backend) -> dict:
    """Save as a draft: a new question, or this one again by its id."""
    with progress.step("Uploading new or changed files in entities/"):
        question = prepared(q, backend)
    with progress.step(f"Pushing {q.slug}") as s:
        result = backend.post_json("/interview-questions", question)
        q.remember_question_id(int(result["question_id"]))
        where = "the public bank" if result.get("visibility") == "public" else "your company"
        s.result(f"{'Saved' if result.get('created') else 'Updated'} question {result['question_id']} "
                 f"as a draft in {where}")
    if result.get("categories"):
        progress.line(f"  categories: {', '.join(result['categories'])}")
    result["url"] = f"{website_url()}{result.get('dashboard_path') or ''}"
    progress.line(f"  {result['url']}")
    return result


def pull(backend: Backend, question_id: int, into: Path) -> Question:
    """Write a saved question into ``into``: question.json with file names, and entities/."""
    with progress.step(f"Pulling interview question {question_id}") as s:
        data = backend.get(f"/interview-questions/{question_id}")
        question, entities = data["question"], data.get("entities") or []
        root = into
        root.mkdir(parents=True, exist_ok=True)
        (root / "entities").mkdir(exist_ok=True)
        names: dict[int, str] = {}
        cache = {}
        for entity in entities:
            name = _unique_name(entity["filename"], set(names.values()))
            content = base64.b64decode(entity["content_base64"])
            (root / "entities" / name).write_bytes(content)
            names[int(entity["entity_id"])] = name
            cache[name] = {"sha256": sha256(content), "entity_id": int(entity["entity_id"])}
        (root / "question.json").write_text(json.dumps(with_file_names(question, names), indent=2,
                                                       ensure_ascii=False) + "\n")
        q = Question(root)
        q.save_state(entities=cache)
        s.result(f"Pulled question {question_id} and {len(entities)} file(s) into {root}")
    return q


# ── helpers ─────────────────────────────────────────────────────────────


def _walk(probes: list):
    for probe in probes:
        if isinstance(probe, dict):
            yield probe
            yield from _walk(probe.get("next") or [])


def _file_names(values) -> set[str]:
    return {v for v in values or [] if isinstance(v, str)}


def _ids(values, ids: dict[str, int]) -> list:
    return [ids[v] if isinstance(v, str) else v for v in values or []]


def with_file_names(question: dict, names: dict[int, str]) -> dict:
    """The reverse of ``with_entity_ids``: entity ids back to file names."""
    out = copy.deepcopy(question)
    out["entity_refs"] = [
        {"file": names[int(ref["id"])], "editable": bool(ref.get("editable", False))}
        if isinstance(ref, dict) and ref.get("id") is not None and int(ref["id"]) in names else ref
        for ref in out.get("entity_refs") or []
    ]
    choices = []
    for choice in out.get("mcq_choices") or []:
        entity_id = choice.get("entity_id") if isinstance(choice, dict) else None
        if entity_id is not None and int(entity_id) in names:
            kept = {k: v for k, v in choice.items() if k not in ("entity_id", "text")}
            choice = {**kept, "file": names[int(entity_id)]}
        elif isinstance(choice, dict):
            choice = {k: v for k, v in choice.items() if not (k == "entity_id" and v is None)}
        choices.append(choice)
    if choices:
        out["mcq_choices"] = choices
    for hint in out.get("seed_hints") or []:
        hint["entities"] = [names.get(int(v), v) for v in hint.get("entities") or []]
    for probe in _walk(out.get("probes") or []):
        probe["entities"] = [names.get(int(v), v) for v in probe.get("entities") or []]
        for hint in probe.get("hints") or []:
            hint["entities"] = [names.get(int(v), v) for v in hint.get("entities") or []]
    return out


def _unique_name(name: str, taken: set) -> str:
    if name not in taken:
        return name
    stem, dot, ext = name.rpartition(".")
    stem, ext = (stem, f".{ext}") if dot else (name, "")
    n = 2
    while f"{stem}_{n}{ext}" in taken:
        n += 1
    return f"{stem}_{n}{ext}"
