"""Checking, previewing, pushing and pulling an MCQ question bank.

A bank is a folder, ``mcq/<slug>/`` (spec: authoring-design/mcq-banks-spec.md):

    bank.json          every question, reviewable
    images/            every image the bank uses
    .codepraxis.json   the bank's id, and which image went up under which entity id
    preview.md         written by ``test``: every question rendered, images inline

``bank.json`` names images by their path under ``images/``: in Markdown
(``![alt](images/flow.png)``) inside a prompt or an option's text, and as an
option's ``image``. The platform names them by entity id. So each image is
uploaded once (again only when its bytes change), and every path is swapped for
``entity:<id>`` (Markdown) or ``image_entity_id`` (an option) before the bank goes
up. ``pull`` does the reverse.

The local checks are the server's (``app/services/assessment/mcq_bank.py``), plus
what only the author's disk can answer: that every image exists, and how deep the
bank is at each difficulty.
"""

from __future__ import annotations

import base64
import copy
import json
import re
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from . import progress
from .errors import PraxisError
from .interview import MAX_UPLOAD_BYTES, _unique_name
from .platform import Backend, HttpError, website_url
from .question import Question, sha256

QUESTION_TYPES = ("single_select", "multi_select")
MIN_OPTIONS, MAX_OPTIONS = 2, 6
MIN_DIFFICULTY, MAX_DIFFICULTY = 1, 5
MAX_QUESTIONS = 500
#: The adaptive round starts at 3 and moves one level per answer; a level with
#: fewer than this runs out of fresh questions.
MIN_PER_DIFFICULTY = 3

IMAGES = "images"
PREVIEW = "preview.md"
LETTERS = "ABCDEF"

IMAGE_CONTENT_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp",
}

BANK_KEYS = {"name", "description", "category", "questions"}
QUESTION_KEYS = {"key", "type", "difficulty", "prompt", "options", "correct", "explanation"}
OPTION_KEYS = {"text", "image", "image_entity_id"}

#: ``![alt](target "title")``; the target may be wrapped in <>, which allows spaces.
MARKDOWN_IMAGE = re.compile(
    r'!\[(?P<alt>[^\]]*)\]\(\s*(?:<(?P<angled>[^>]+)>|(?P<bare>[^)\s]+))(?P<title>\s+"[^"]*")?\s*\)'
)
#: An image already on the platform, as the server writes it.
ENTITY_REF = re.compile(r"entity:(\d+)")


def markdown_images(text: str) -> list[tuple[str, str]]:
    """``(alt, target)`` for every Markdown image in ``text``."""
    return [(m.group("alt"), m.group("angled") or m.group("bare")) for m in MARKDOWN_IMAGE.finditer(text or "")]


def image_name(target: str) -> str | None:
    """The path under ``images/`` that a reference names (``images/a/b.png`` is
    ``a/b.png``), or None when it isn't one."""
    target = target.strip()
    if target.startswith("./"):
        target = target[2:]
    parts = PurePosixPath(target).parts
    if len(parts) < 2 or parts[0] != IMAGES or any(p in ("..", ".") for p in parts):
        return None
    return "/".join(parts[1:])


# ── checking ──────────────────────────────────────────────────────────────


@dataclass
class Report:
    """What ``check`` found. Errors block a push; warnings don't."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    by_difficulty: dict[int, int] = field(default_factory=dict)
    question_count: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def _whole_number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def check(bank: dict, root: Path) -> Report:
    """Every rule the server applies, and the image files and depth it can't see.

    Problems name the question by position and key, as the server's do.
    """
    report = Report()
    errors, warnings = report.errors, report.warnings
    images_dir = root / IMAGES

    for extra in sorted(set(bank) - BANK_KEYS):
        warnings.append(f"bank.json: unknown key '{extra}'; the platform ignores it.")
    if not str(bank.get("name") or "").strip():
        errors.append("The bank needs a name.")
    category = bank.get("category")
    if category is not None and not isinstance(category, str):
        errors.append("category must be a category slug (see `codepraxis categories`) or null.")
    questions = bank.get("questions")
    if not isinstance(questions, list) or not questions:
        errors.append("The bank needs at least one question.")
        questions = []
    if len(questions) > MAX_QUESTIONS:
        errors.append(f"A bank holds at most {MAX_QUESTIONS} questions.")
    report.question_count = len(questions)

    def image_ok(target: str, where: str) -> None:
        if ENTITY_REF.fullmatch(target.strip()):
            return  # already uploaded; the server checks it
        name = image_name(target)
        if name is None:
            errors.append(f"{where}: image '{target}' must be a file under {IMAGES}/ (e.g. {IMAGES}/diagram.png).")
            return
        suffix = PurePosixPath(name).suffix.lower()
        if suffix not in IMAGE_CONTENT_TYPES:
            errors.append(f"{where}: image '{target}' must be one of "
                          f"{', '.join(sorted(s[1:] for s in IMAGE_CONTENT_TYPES))}.")
            return
        if not (images_dir / name).is_file():
            errors.append(f"{where}: image '{target}' does not exist.")

    counts = dict.fromkeys(range(MIN_DIFFICULTY, MAX_DIFFICULTY + 1), 0)
    keys_seen: dict[str, int] = {}
    for index, raw in enumerate(questions, start=1):
        if not isinstance(raw, dict):
            errors.append(f"Question {index}: must be an object with a prompt, options and correct.")
            continue
        q = raw
        key = str(q.get("key") or "").strip() or None
        label = f"Question {index}" + (f" ({key})" if key else "")
        for extra in sorted(set(q) - QUESTION_KEYS):
            warnings.append(f"{label}: unknown key '{extra}'; the platform ignores it.")
        if key:
            if key in keys_seen:
                errors.append(f"{label}: key repeats question {keys_seen[key]}.")
            else:
                keys_seen[key] = index

        qtype = q.get("type") or "single_select"
        if qtype not in QUESTION_TYPES:
            errors.append(f"{label}: type must be one of {', '.join(QUESTION_TYPES)}.")
        difficulty = _whole_number(q.get("difficulty"))
        if difficulty is None or not MIN_DIFFICULTY <= difficulty <= MAX_DIFFICULTY:
            errors.append(f"{label}: difficulty must be {MIN_DIFFICULTY} to {MAX_DIFFICULTY}.")
        else:
            counts[difficulty] += 1

        prompt = str(q.get("prompt") or "").strip()
        if not prompt:
            errors.append(f"{label}: the question text is empty.")
        for _alt, target in markdown_images(prompt):
            image_ok(target, label)

        options = q.get("options") if isinstance(q.get("options"), list) else []
        if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
            errors.append(f"{label}: needs {MIN_OPTIONS} to {MAX_OPTIONS} options.")
        plain_texts: list[str] = []
        for pos, raw_opt in enumerate(options, start=1):
            where = f"{label}, option {pos}"
            if not isinstance(raw_opt, dict):
                errors.append(f"{where}: must be an object with text and/or image.")
                continue
            for extra in sorted(set(raw_opt) - OPTION_KEYS):
                warnings.append(f"{where}: unknown key '{extra}'; the platform ignores it.")
            text = str(raw_opt.get("text") or "").strip()
            image = raw_opt.get("image")
            entity_id = raw_opt.get("image_entity_id")
            has_image = False
            if image not in (None, ""):
                has_image = True
                if not isinstance(image, str):
                    errors.append(f"{where}: image must be a path under {IMAGES}/.")
                else:
                    image_ok(image, where)
            if entity_id is not None:
                has_image = True
                if _whole_number(entity_id) is None:
                    errors.append(f"{where}: image_entity_id must be a number.")
            if not text and not has_image:
                errors.append(f"{where}: needs text or an image.")
            for _alt, target in markdown_images(text):
                image_ok(target, where)
            if text and not has_image:
                plain_texts.append(text.lower())
        if len(plain_texts) != len(set(plain_texts)):
            errors.append(f"{label}: two options have the same text.")

        correct_in = q.get("correct")
        correct: list[int] = []
        if isinstance(correct_in, list):
            values = [_whole_number(c) for c in correct_in]
            correct = sorted({v for v in values if v is not None}) if None not in values else []
        if not correct:
            errors.append(f"{label}: mark at least one correct option (\"correct\": [positions, from 1]).")
        elif any(not 1 <= c <= len(options) for c in correct):
            errors.append(f"{label}: a correct answer points to an option that does not exist.")
        elif qtype == "single_select" and len(correct) != 1:
            errors.append(f"{label}: a single_select question has exactly one correct option.")

    report.by_difficulty = counts
    if questions:
        for level, n in counts.items():
            if n < MIN_PER_DIFFICULTY:
                warnings.append(
                    f"Difficulty {level} has {n} question{'s' if n != 1 else ''}; the adaptive round needs at "
                    f"least {MIN_PER_DIFFICULTY} at every level (more at 2 to 4)."
                )
    return report


def depth_line(by_difficulty: dict) -> str:
    """``1: 3 · 2: 6 · …`` from a count per difficulty (int or JSON string keys)."""
    counts = {int(k): int(v) for k, v in (by_difficulty or {}).items()}
    return " · ".join(f"{d}: {counts.get(d, 0)}" for d in range(MIN_DIFFICULTY, MAX_DIFFICULTY + 1))


# ── preview.md ────────────────────────────────────────────────────────────


def render_preview(bank: dict, report: Report | None = None) -> str:
    """Every question as the author should review it, in any Markdown viewer.

    Images keep their ``images/...`` paths, which resolve from the bank's folder
    where preview.md is written. Correct options carry ✅; the explanation (never
    shown to candidates) follows each question.
    """
    out: list[str] = [f"# {str(bank.get('name') or 'Untitled bank').strip()}", ""]
    if str(bank.get("description") or "").strip():
        out += [str(bank["description"]).strip(), ""]
    questions = bank.get("questions") if isinstance(bank.get("questions"), list) else []
    meta = [f"{len(questions)} question{'s' if len(questions) != 1 else ''}"]
    if bank.get("category"):
        meta.insert(0, f"Category `{bank['category']}`")
    if report is not None:
        meta.append(f"by difficulty {depth_line(report.by_difficulty)}")
    out += [" · ".join(meta), ""]
    if report is not None and (report.errors or report.warnings):
        out += ["## Problems", ""]
        out += [f"- ✗ {e}" for e in report.errors]
        out += [f"- ! {w}" for w in report.warnings]
        out.append("")

    for index, q in enumerate(questions, start=1):
        out += ["---", ""]
        if not isinstance(q, dict):
            out += [f"## {index}. (not a question object)", ""]
            continue
        key = str(q.get("key") or "").strip()
        qtype = str(q.get("type") or "single_select").replace("_", " ")
        out += [f"## {index}. {key}" if key else f"## {index}.", ""]
        out += [f"*Difficulty {q.get('difficulty', '?')} · {qtype}*", ""]
        out += [str(q.get("prompt") or "").strip() or "*(empty prompt)*", ""]
        correct = {c for c in q.get("correct") or [] if isinstance(c, int) and not isinstance(c, bool)}
        options = q.get("options") if isinstance(q.get("options"), list) else []
        right: list[str] = []
        for pos, opt in enumerate(options, start=1):
            letter = LETTERS[pos - 1] if pos <= len(LETTERS) else str(pos)
            opt = opt if isinstance(opt, dict) else {}
            mark = " ✅" if pos in correct else ""
            if mark:
                right.append(letter)
            text = str(opt.get("text") or "").strip()
            if text and "\n" not in text:
                out += [f"**{letter}.** {text}{mark}", ""]
            else:
                out += [f"**{letter}.**{mark}", ""]
                if text:
                    out += [text, ""]
            if opt.get("image"):
                out += [f"![Option {letter}]({opt['image']})", ""]
            elif opt.get("image_entity_id") is not None:
                out += [f"*(image entity {opt['image_entity_id']}, not downloaded)*", ""]
        out += [f"**Answer:** {', '.join(right) or '*(none marked)*'}", ""]
        explanation = str(q.get("explanation") or "").strip()
        out += [f"**Explanation:** {explanation}" if explanation else "**Explanation:** *(none)*", ""]
    return "\n".join(out).rstrip() + "\n"


# ── images: paths ↔ entity ids ────────────────────────────────────────────


def referenced_images(bank: dict) -> dict[str, str | None]:
    """Every image the bank uses (its path under ``images/``), in order of first
    use, with the description it goes up with: the Markdown alt text, else the
    option's text for an option image, else None."""
    found: dict[str, str | None] = {}

    def add(target: str, description: str | None) -> None:
        name = image_name(target) if isinstance(target, str) else None
        if name is None:
            return
        description = (description or "").strip() or None
        if name not in found or (found[name] is None and description):
            found[name] = description

    for q in bank.get("questions") or []:
        if not isinstance(q, dict):
            continue
        for alt, target in markdown_images(str(q.get("prompt") or "")):
            add(target, alt)
        for opt in q.get("options") or []:
            if not isinstance(opt, dict):
                continue
            text = str(opt.get("text") or "")
            for alt, target in markdown_images(text):
                add(target, alt)
            if opt.get("image"):
                add(opt["image"], text)
    return found


def _paths_to_ids(text: str, ids: dict[str, int]) -> str:
    def swap(m: re.Match) -> str:
        target = m.group("angled") or m.group("bare")
        name = image_name(target)
        if name is None or name not in ids:
            return m.group(0)
        return f"![{m.group('alt')}](entity:{ids[name]}{m.group('title') or ''})"

    return MARKDOWN_IMAGE.sub(swap, text or "")


def to_platform(bank: dict, ids: dict[str, int], bank_id: int | None = None) -> dict:
    """The bank as ``POST /question-banks`` takes it: image paths become
    ``entity:<id>`` in Markdown and ``image_entity_id`` on options; keys the
    platform doesn't know are left out."""
    questions = []
    for q in bank.get("questions") or []:
        q = q if isinstance(q, dict) else {}
        options = []
        for opt in q.get("options") or []:
            opt = opt if isinstance(opt, dict) else {}
            option: dict[str, Any] = {"text": _paths_to_ids(str(opt.get("text") or ""), ids)}
            entity_ref = ENTITY_REF.fullmatch(str(opt.get("image") or "").strip())
            if entity_ref:
                option["image_entity_id"] = int(entity_ref.group(1))
            elif opt.get("image"):
                name = image_name(str(opt["image"]))
                if name is None or name not in ids:
                    raise PraxisError(f"Option image '{opt['image']}' was not uploaded.")
                option["image_entity_id"] = ids[name]
            elif opt.get("image_entity_id") is not None:
                option["image_entity_id"] = opt["image_entity_id"]
            options.append(option)
        out: dict[str, Any] = {}
        if q.get("key"):
            out["key"] = q["key"]
        out.update({
            "type": q.get("type") or "single_select",
            "difficulty": q.get("difficulty"),
            "prompt": _paths_to_ids(str(q.get("prompt") or ""), ids),
            "options": options,
            "correct": q.get("correct"),
        })
        if q.get("explanation"):
            out["explanation"] = q["explanation"]
        questions.append(out)
    payload: dict[str, Any] = {}
    if bank_id:
        payload["id"] = int(bank_id)
    payload.update({
        "name": bank.get("name"),
        "description": bank.get("description"),
        "category": bank.get("category"),
        "questions": questions,
    })
    return payload


def to_local(bank: dict, names: dict[int, str]) -> dict:
    """The reverse of ``to_platform``: ``entity:<id>`` back to ``images/<file>``
    and ``image_entity_id`` back to ``image``. An id with no file is kept."""
    def swap(text: str) -> str:
        return ENTITY_REF.sub(
            lambda m: f"{IMAGES}/{names[int(m.group(1))]}" if int(m.group(1)) in names else m.group(0), text or ""
        )

    questions = []
    for q in copy.deepcopy(bank.get("questions") or []):
        q["prompt"] = swap(q.get("prompt") or "")
        options = []
        for opt in q.get("options") or []:
            option = {"text": swap(opt.get("text") or "")}
            entity_id = opt.get("image_entity_id")
            if entity_id is not None:
                if int(entity_id) in names:
                    option["image"] = f"{IMAGES}/{names[int(entity_id)]}"
                else:
                    option["image_entity_id"] = entity_id
            options.append(option)
        q["options"] = options
        questions.append(q)
    out: dict[str, Any] = {"name": bank.get("name")}
    if bank.get("description"):
        out["description"] = bank["description"]
    out["category"] = bank.get("category")
    out["questions"] = questions
    return out


def upload_images(q: Question, backend: Backend, images: dict[str, str | None]) -> dict[str, int]:
    """Entity ids for these images, uploading any that are new or changed."""
    cached = q.state().get("images", {})
    ids: dict[str, int] = {}
    for name, description in images.items():
        path = q.images_dir / name
        if not path.is_file():
            raise PraxisError(f"bank.json shows '{IMAGES}/{name}', but {path} doesn't exist.")
        data = path.read_bytes()
        digest = sha256(data)
        hit = cached.get(name)
        if hit and hit.get("sha256") == digest:
            ids[name] = int(hit["entity_id"])
            continue
        if len(data) > MAX_UPLOAD_BYTES:
            raise PraxisError(f"{IMAGES}/{name} is {len(data) // (1024 * 1024)} MB; one image can be at most "
                              f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
        progress.line(f"  uploading {IMAGES}/{name} ({max(1, len(data) // 1024)} KB)…")
        meta = {"filename": PurePosixPath(name).name}
        content_type = IMAGE_CONTENT_TYPES.get(PurePosixPath(name).suffix.lower())
        if content_type:
            meta["content_type"] = content_type
        body: dict[str, Any] = {"type": "image", "content_base64": base64.b64encode(data).decode(), "meta": meta}
        if description:
            body["normalized_form"] = description
        result = backend.post_json("/entities", body, timeout=300)
        ids[name] = int(result["entity_id"])
        cached[name] = {"sha256": digest, "entity_id": ids[name]}
        q.save_state(images=cached)
    return ids


# ── commands ──────────────────────────────────────────────────────────────


def _print_report(report: Report) -> None:
    for problem in report.errors:
        progress.failed(problem)
    for warning in report.warnings:
        progress.warn(warning)
    progress.line(f"  By difficulty: {depth_line(report.by_difficulty)}")


def _checked(q: Question) -> tuple[dict, Report]:
    bank = q.read_bank()
    with progress.step(f"Checking {q.slug}/bank.json") as s:
        report = check(bank, q.root)
        s.result(f"Checked {report.question_count} question(s): {len(report.errors)} error(s), "
                 f"{len(report.warnings)} warning(s)")
    _print_report(report)
    return bank, report


def test(q: Question) -> bool:
    """The local checks, and preview.md. True when nothing blocks a push."""
    bank, report = _checked(q)
    (q.root / PREVIEW).write_text(render_preview(bank, report), encoding="utf-8")
    progress.done(f"Wrote {q.slug}/{PREVIEW}: every question, its images and its answer, to review.")
    return report.ok


def push(q: Question, backend: Backend) -> dict:
    """Check, upload new or changed images, and replace the bank on the platform."""
    bank, report = _checked(q)
    if not report.ok:
        raise PraxisError(f"{len(report.errors)} problem(s) in bank.json; fix them and push again.")
    with progress.step(f"Uploading new or changed images in {IMAGES}/"):
        ids = upload_images(q, backend, referenced_images(bank))
    bank_id = q.state().get("bank_id")
    payload = to_platform(bank, ids, bank_id)
    with progress.step(f"Pushing {q.slug}" + (f" (replacing bank {bank_id})" if bank_id else "")) as s:
        try:
            result = backend.post_json("/question-banks", payload, timeout=180)
        except HttpError as exc:
            if exc.status == 404 and bank_id:
                raise PraxisError(
                    f"Bank {bank_id} is not on the platform, or this API key can't write it. Remove bank_id "
                    f"from {q.slug}/.codepraxis.json to create a new bank instead."
                ) from exc
            problems = exc.detail.get("problems") if isinstance(exc.detail, dict) else None
            if exc.status == 422 and problems:
                for problem in problems:
                    progress.failed(str(problem))
                raise PraxisError(f"The platform refused the bank: {len(problems)} problem(s), listed above.") from exc
            raise
        q.save_state(bank_id=int(result["bank_id"]))
        where = "the public library" if result.get("visibility") == "public" else "your company"
        s.result(f"{'Created' if result.get('created') else 'Replaced'} bank {result['bank_id']} in {where}: "
                 f"{result.get('question_count')} question(s)")
    progress.line(f"  By difficulty: {depth_line(result.get('by_difficulty') or {})}")
    if result.get("category"):
        progress.line(f"  category: {result['category']}")
    result["url"] = f"{website_url()}{result.get('dashboard_path') or ''}"
    progress.line(f"  {result['url']}")
    return result


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")[:60]


def _pulled_name(entity_id: int, entity: dict, taken: set) -> str:
    """A safe file name for a pulled image: its uploaded name, without folders or
    spaces, with an image extension."""
    filename = PurePosixPath(str(entity.get("filename") or "")).name
    filename = re.sub(r"\s+", "_", filename)
    if not filename or filename.startswith("."):
        filename = f"entity_{entity_id}"
    if PurePosixPath(filename).suffix.lower() not in IMAGE_CONTENT_TYPES:
        url_suffix = PurePosixPath(urllib.parse.urlparse(str(entity.get("url") or "")).path).suffix.lower()
        filename += url_suffix if url_suffix in IMAGE_CONTENT_TYPES else ".png"
    return _unique_name(filename, taken)


def default_folder(bank: dict, bank_id: int) -> Path:
    return Path.cwd() / "mcq" / (_slug(str(bank.get("name") or "")) or f"bank_{bank_id}")


def pull(backend: Backend, bank_id: int, into: Path | None = None) -> Question:
    """Write a bank into ``into`` (default ``mcq/<name>``): bank.json with image
    paths, and its images under images/. A push right after uploads nothing."""
    with progress.step(f"Pulling MCQ bank {bank_id}") as s:
        data = backend.get(f"/question-banks/{bank_id}")
        root = into or default_folder(data, bank_id)
        (root / IMAGES).mkdir(parents=True, exist_ok=True)
        names: dict[int, str] = {}
        cache: dict[str, dict] = {}
        missing: list[int] = []
        for key, entity in sorted((data.get("entities") or {}).items(), key=lambda kv: int(kv[0])):
            entity_id = int(key)
            if not entity.get("url"):
                missing.append(entity_id)
                continue
            content = backend.download(entity["url"])
            name = _pulled_name(entity_id, entity, set(names.values()))
            (root / IMAGES / name).write_bytes(content)
            names[entity_id] = name
            cache[name] = {"sha256": sha256(content), "entity_id": entity_id}
        local = to_local(data, names)
        (root / "bank.json").write_text(json.dumps(local, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        q = Question(root)
        q.save_state(bank_id=int(data.get("id") or bank_id), images=cache)
        s.result(f"Pulled bank {bank_id}: {len(local['questions'])} question(s) and {len(names)} image(s) into {root}")
    for entity_id in missing:
        progress.warn(f"Image entity {entity_id} could not be downloaded; bank.json keeps it as entity:{entity_id}.")
    return q
