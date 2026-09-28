"""Checking and saving an AI interview question.

``question.json`` names the files it shows by their name in ``entities/``. The
platform names them by entity id. So each file is uploaded once (again only if
it changes), its id remembered, and every file name in the question swapped for
its id before the question is checked or saved.

What a name in ``entities/`` can be:

- a file, typed by its extension (anything unknown is code);
- a folder, uploaded as one ``repo``: an explorer and an editor on the candidate's
  screen, the whole folder as text for the interviewer;
- slides or a Word document, converted to PDF on the way up (needs LibreOffice).

Beside any of them, ``<name>.description.md`` is the author's own account of it:
what the interviewer reads in its place. Audio and video need one, because nothing
else can turn them into text.
"""

from __future__ import annotations

import base64
import copy
import io
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

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
    ".mp4": "video", ".mov": "video", ".webm": "video", ".m4v": "video",
    ".mp3": "audio", ".wav": "audio", ".m4a": "audio", ".ogg": "audio", ".aac": "audio", ".flac": "audio",
}

#: Served with these, so the browser plays or shows the file instead of downloading it.
_CONTENT_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
    ".webp": "image/webp", ".pdf": "application/pdf",
    ".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".ogg": "audio/ogg",
    ".aac": "audio/aac", ".flac": "audio/flac",
}

#: Shown as a PDF: a browser cannot show these, so push converts them.
_CONVERT_TO_PDF = {".pptx", ".ppt", ".odp", ".docx", ".doc", ".odt"}
_SLIDES = {".pptx", ".ppt", ".odp"}

#: Beside a file or folder: what the interviewer reads in its place.
DESCRIPTION_SUFFIX = ".description.md"
#: Types nothing on the platform can read, so a description is required.
_NEEDS_DESCRIPTION = {"audio", "video"}

#: One upload goes up as JSON; much past this and the request times out.
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

#: The platform refuses a bigger repo; checked here first to say so before uploading.
REPO_MAX_FILES = 200
REPO_MAX_TEXT_BYTES = 500 * 1024
_REPO_SKIPPED = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".vscode",
    ".DS_Store", ".pytest_cache", ".mypy_cache",
}


def entity_type(path: Path) -> str:
    """The entity type for a name in ``entities/``: a folder is a repo; a file goes
    by its extension, and anything not listed is code."""
    if path.is_dir():
        return "repo"
    return _TYPES.get(path.suffix.lower(), "code")


def description_for(path: Path) -> Optional[str]:
    """The author's description beside this file or folder, if there is one."""
    beside = path.with_name(path.name + DESCRIPTION_SUFFIX)
    if beside.is_file():
        text = beside.read_text(encoding="utf-8").strip()
        return text or None
    return None


def zip_repo(folder: Path) -> bytes:
    """A folder as the zip a repo entity holds: its text files, in a fixed order with
    fixed timestamps, so the same folder always zips to the same bytes and an
    unchanged repo is not uploaded again.

    Refused here, with the numbers, when it is over the platform's limit.
    """
    files = []
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder).as_posix()
        if path.is_dir() or any(part in _REPO_SKIPPED for part in rel.split("/")):
            continue
        raw = path.read_bytes()
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            continue  # binaries are neither shown nor read
        files.append((rel, raw))
    if not files:
        raise PraxisError(f"{folder.name}/ has no text files to show.")
    total = sum(len(raw) for _, raw in files)
    if len(files) > REPO_MAX_FILES or total > REPO_MAX_TEXT_BYTES:
        raise PraxisError(
            f"This repo is too big: {folder.name}/ has {len(files)} files and {total // 1024} KB "
            f"of text, and the limit is {REPO_MAX_FILES} files and {REPO_MAX_TEXT_BYTES // 1024} KB. "
            "Keep only the files the question needs."
        )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for rel, raw in files:
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    return buffer.getvalue()


def _soffice() -> Optional[str]:
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    mac = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    return str(mac) if mac.exists() else None


def convert_to_pdf(path: Path) -> Optional[bytes]:
    """The file as a PDF, or None when LibreOffice is not installed."""
    soffice = _soffice()
    if soffice is None:
        return None
    with tempfile.TemporaryDirectory() as out:
        progress.line(f"  converting {path.name} to PDF…")
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", out, str(path)],
                check=True, capture_output=True, timeout=180,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise PraxisError(f"LibreOffice could not convert {path.name} to PDF: {exc}") from exc
        pdf = Path(out) / (path.stem + ".pdf")
        if not pdf.is_file():
            raise PraxisError(f"LibreOffice did not produce a PDF for {path.name}.")
        return pdf.read_bytes()


def _upload_form(path: Path, source: bytes, description: Optional[str]) -> tuple[str, bytes, dict]:
    """What goes up for one name: its type, its bytes and its meta."""
    suffix = path.suffix.lower()
    if path.is_dir():
        return "repo", source, {"filename": path.name}
    if suffix in _CONVERT_TO_PDF:
        pdf = convert_to_pdf(path)
        if pdf is not None:
            return "pdf", pdf, {
                "filename": path.stem + ".pdf",
                "content_type": "application/pdf",
                "converted_from": path.name,
            }
        if suffix in _SLIDES:
            raise PraxisError(
                f"{path.name}: slides are shown as a PDF. Install LibreOffice so push can "
                "convert them, or export a PDF yourself and reference that instead."
            )
        progress.line(f"  ! {path.name}: LibreOffice not found, so it goes up as a download link, not a PDF.")
    kind = entity_type(path)
    if kind in _NEEDS_DESCRIPTION and not description:
        raise PraxisError(
            f"{path.name} needs a description: the interviewer cannot watch or listen, so write "
            f"what it should know about the file in {path.name}{DESCRIPTION_SUFFIX}, beside it."
        )
    meta = {"filename": path.name}
    if suffix in _CONTENT_TYPES:
        meta["content_type"] = _CONTENT_TYPES[suffix]
    return kind, source, meta


def upload_entities(q: Question, backend: Backend, names: set[str]) -> dict[str, int]:
    """Entity ids for these files, uploading any that are new or changed.

    A file's description is part of it: changing either uploads it again.
    """
    cached = q.state().get("entities", {})
    ids: dict[str, int] = {}
    for name in sorted(names):
        path = q.entities_dir / name
        if not path.exists():
            raise PraxisError(f"question.json shows '{name}', but {path} doesn't exist.")
        description = description_for(path)
        source = zip_repo(path) if path.is_dir() else path.read_bytes()
        digest = sha256(source) if description is None else sha256(source + b"\0" + description.encode())
        hit = cached.get(name)
        if hit and hit.get("sha256") == digest:
            ids[name] = int(hit["entity_id"])
            continue
        kind, data, meta = _upload_form(path, source, description)
        if len(data) > MAX_UPLOAD_BYTES:
            raise PraxisError(
                f"{name} is {len(data) // (1024 * 1024)} MB; one file can be at most "
                f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
            )
        progress.line(f"  uploading {name} ({kind}, {len(data) // 1024} KB)…")
        body = {
            "type": kind,
            "content_base64": base64.b64encode(data).decode(),
            "meta": meta,
        }
        if description:
            body["normalized_form"] = description
        result = backend.post_json("/entities", body, timeout=300)
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
    if "seed_highlights" in out:
        out["seed_highlights"] = _highlight_ids(out["seed_highlights"], ids, "the opening question")
    for hint in out.get("seed_hints") or []:
        hint["entities"] = _ids(hint.get("entities"), ids)
    for probe in _walk(out.get("probes") or []):
        probe["entities"] = _ids(probe.get("entities"), ids)
        if "editable" in probe:
            probe["editable"] = _ids(probe.get("editable"), ids, where=f"probe {probe.get('id')}'s editable")
        if "highlights" in probe:
            probe["highlights"] = _highlight_ids(probe["highlights"], ids, f"probe {probe.get('id')}")
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
    """Write a saved question into ``into``: question.json with file names, and entities/.

    A repo comes back as its folder and a description beside its file, so a pull
    followed by a push uploads nothing that did not change.
    """
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
            target = root / "entities" / name
            if entity.get("type") == "repo":
                target.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    for member in archive.infolist():
                        if member.is_dir() or member.filename.startswith(("/", "..")) or "/../" in member.filename:
                            continue
                        dest = target / member.filename
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(archive.read(member))
                source = zip_repo(target)
            else:
                target.write_bytes(content)
                source = content
            description = entity.get("description")
            if description:
                (root / "entities" / (name + DESCRIPTION_SUFFIX)).write_text(description + "\n", encoding="utf-8")
                description = description_for(target)
            names[int(entity["entity_id"])] = name
            digest = sha256(source) if not description else sha256(source + b"\0" + description.encode())
            cache[name] = {"sha256": digest, "entity_id": int(entity["entity_id"])}
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


def _ids(values, ids: dict[str, int], where: str = "") -> list:
    out = []
    for v in values or []:
        if isinstance(v, str):
            if v not in ids:
                raise PraxisError(f"{where or 'The question'} names '{v}', which the question doesn't show.")
            out.append(ids[v])
        else:
            out.append(v)
    return out


def _highlight_ids(values, ids: dict[str, int], where: str) -> list:
    """Highlights as the platform stores them.

    Written ``{"file": "loader.sql", "lines": [88, 110]}`` (``path`` too, for a file
    inside a repo); stored ``{entity_id, path, start_line, end_line}``.
    """
    out = []
    for h in values or []:
        if not isinstance(h, dict) or "entity_id" in h:
            out.append(h)
            continue
        name = h.get("file")
        if name not in ids:
            raise PraxisError(f"A highlight at {where} names '{name}', which the question doesn't show.")
        lines = h.get("lines")
        if lines:
            start, end = int(lines[0]), int(lines[-1])
        else:
            start, end = int(h.get("start_line") or 0), int(h.get("end_line") or h.get("start_line") or 0)
        item = {"entity_id": ids[name], "start_line": start, "end_line": end}
        if h.get("path"):
            item["path"] = h["path"]
        out.append(item)
    return out


def _highlight_names(values, names: dict[int, str]) -> list:
    out = []
    for h in values or []:
        if isinstance(h, dict) and h.get("entity_id") is not None and int(h["entity_id"]) in names:
            item = {"file": names[int(h["entity_id"])], "lines": [h.get("start_line"), h.get("end_line")]}
            if h.get("path"):
                item["path"] = h["path"]
            out.append(item)
        else:
            out.append(h)
    return out


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
    if out.get("seed_highlights"):
        out["seed_highlights"] = _highlight_names(out["seed_highlights"], names)
    elif "seed_highlights" in out:
        del out["seed_highlights"]
    for hint in out.get("seed_hints") or []:
        hint["entities"] = [names.get(int(v), v) for v in hint.get("entities") or []]
    for probe in _walk(out.get("probes") or []):
        probe["entities"] = [names.get(int(v), v) for v in probe.get("entities") or []]
        if probe.get("editable"):
            probe["editable"] = [names.get(int(v), v) for v in probe["editable"]]
        elif "editable" in probe:
            del probe["editable"]
        if probe.get("highlights"):
            probe["highlights"] = _highlight_names(probe["highlights"], names)
        elif "highlights" in probe:
            del probe["highlights"]
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
