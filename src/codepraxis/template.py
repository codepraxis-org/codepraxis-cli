"""Assessment templates: the library, and checking, pushing and pulling a template.

A template is a folder, ``templates/<slug>/``, beside ``challenges/`` and ``mcq/``:

    template.json      the rounds and the questions in them (below)
    .codepraxis.json   the template's id, version and status, once pushed

``template.json``::

    {"name": "...", "description": "...", "category": "<slug>",
     "proctoring": {"webcam_proctoring": true, "screen_recording": true, "identity_photo": true},
     "ai_assistant": false,
     "coding": {"questions": [{"ref": 51, "minutes": 60}],
                "pools": [{"refs": [52, "invoice_rerun"], "pick": 1, "minutes": 40}]},
     "code_review": {"minutes": 10},
     "interview": {"questions": [7, [8, "rerun_safe_loader"]]},
     "mcq": {"banks": [9, "retries"], "questions": 10, "minutes": 12}}

A *ref* is a platform id (an integer), or a local question folder (its slug or a
path) that has been pushed: the id is read from it. In the interview, a list is a
group of alternatives; each candidate is asked one of them. The interview's
minutes come from the questions: the longest of each group, added up.

The first push saves a new template as a **draft**; it may hold draft questions.
Later pushes go to the same template: a draft is replaced (the platform answers
with a new id, which is remembered), a published template gets a new published
version. Publishing a draft happens in the dashboard, once every question in it
is published.
"""

from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import progress
from .errors import PraxisError
from .mcq import _slug, _whole_number
from .platform import Backend, HttpError, NotFound, website_url
from .question import Question

TEMPLATE_JSON = "template.json"

KINDS = ("coding", "interview", "mcq")
TEMPLATE_KEYS = {"name", "description", "category", "proctoring", "ai_assistant",
                 "coding", "code_review", "interview", "mcq"}
PROCTORING_KEYS = ("webcam_proctoring", "screen_recording", "identity_photo")

#: The platform's limits (``AiInterviewConfig``, ``McqRoundConfig``, ``CodeReviewRoundConfig``).
INTERVIEW_MINUTES = (10, 90)
INTERVIEW_MAX_QUESTIONS = 20
MCQ_QUESTIONS = (1, 50)
ROUND_MINUTES = (1, 180)

#: What a round is called on screen.
ROUND_NAMES = {"coding": "coding", "code_review": "code review", "interview": "interview",
               "mcq": "knowledge check"}

#: The platform's own word for a published question, per kind.
_PUBLISHED = {"published": "published", "ready": "published", "active": "published"}
#: Listed in this order; a retired or archived question can't go in a template.
_RANK = {"published": 0, "draft": 1}
UNUSABLE = ("retired", "archived")


def dashboard_link(template_id) -> str:
    return f"{website_url()}/company/templates/{template_id}"


def status_of(raw) -> str:
    """``published``, ``draft`` or ``retired``, whatever the kind calls it."""
    raw = str(raw or "").lower()
    return _PUBLISHED.get(raw, raw or "published")


# ── the library ───────────────────────────────────────────────────────────


@dataclass
class Item:
    """One question (or bank) the key can put in a template."""

    kind: str
    id: int
    status: str
    name: str
    minutes: int | None
    categories: list[str]
    description: str = ""
    extra: dict = field(default_factory=dict)

    def as_json(self) -> dict:
        return {"kind": self.kind, "id": self.id, "status": self.status, "name": self.name,
                "minutes": self.minutes, "categories": self.categories, "description": self.description,
                **self.extra}


def _coding_item(c: dict) -> Item:
    return Item(
        "coding", int(c["challenge_id"]), status_of(c.get("status")),
        str(c.get("challenge_name") or c.get("name") or ""), _whole_number(c.get("max_time")),
        list(c.get("categories") or []), str(c.get("description") or ""),
        {k: c[k] for k in ("tech_stack", "difficulty", "ai_enabled") if c.get(k) is not None},
    )


def _interview_item(q: dict) -> Item:
    return Item(
        "interview", int(q["id"]), status_of(q.get("status")), str(q.get("name") or ""),
        _whole_number(q.get("duration")), list(q.get("categories") or []), str(q.get("description") or ""),
        {k: q[k] for k in ("mode", "seniority", "topics", "is_platform") if q.get(k) is not None},
    )


def _bank_item(b: dict) -> Item:
    # A bank has no draft: it is usable as soon as it is pushed.
    return Item(
        "mcq", int(b["bank_id"]), "published", str(b.get("name") or ""), None,
        [b["category"]] if b.get("category") else [], "",
        {"question_count": int(b.get("question_count") or 0)},
    )


def fetch_library(backend: Backend, kinds=KINDS, *, category: str | None = None,
                  words: str | None = None, retired: bool = False) -> dict[str, list[Item]]:
    """What the key can put in a template, per kind. The interview list is
    filtered by the platform (a category there includes its sub-categories); the
    others here. ``retired`` adds the retired interview questions the platform
    leaves out, so a template that still names one can say so."""
    found: dict[str, list[Item]] = {}
    if "coding" in kinds:
        data = backend.get("/challenges?scope=library&limit=500")
        found["coding"] = [_coding_item(c) for c in data.get("challenges") or []]
    if "interview" in kinds:
        params = urllib.parse.urlencode({k: v for k, v in (("q", words), ("category", category)) if v})
        data = backend.get("/interview-questions" + (f"?{params}" if params else ""))
        found["interview"] = [_interview_item(q) for q in data.get("questions") or []]
        if retired:
            data = backend.get("/interview-questions?status=retired")
            found["interview"] += [_interview_item(q) for q in data.get("questions") or []]
    if "mcq" in kinds:
        data = backend.get("/question-banks")
        found["mcq"] = [_bank_item(b) for b in data.get("banks") or []]
    for kind in ("coding", "mcq"):
        if kind in found:
            found[kind] = [i for i in found[kind] if _matches(i, category, words)]
    return found


def _matches(item: Item, category: str | None, words: str | None) -> bool:
    if category and category not in item.categories:
        return False
    text = " ".join([item.name, item.description, *map(str, item.extra.get("tech_stack") or [])]).lower()
    return all(w in text for w in (words or "").lower().split())


def print_library(found: dict[str, list[Item]]) -> None:
    """One compact table per kind: id, status, minutes, name, categories."""
    for kind in KINDS:
        if kind not in found:
            continue
        items = found[kind]
        progress.line(f"{ROUND_NAMES[kind].capitalize() if kind != 'mcq' else 'MCQ banks'} ({len(items)})")
        if not items:
            progress.line("  (none)")
        for i in sorted(items, key=lambda i: (_RANK.get(i.status, 3), i.name.lower())):
            minutes = f"{i.minutes}m" if i.minutes else f"{i.extra.get('question_count', 0)}q" if kind == "mcq" else "-"
            name = i.name if len(i.name) <= 60 else i.name[:59] + "…"
            progress.line(f"  {i.id:>5}  {i.status:9}  {minutes:>4}  {name:60}  {', '.join(i.categories)}")
        progress.line()


# ── refs ──────────────────────────────────────────────────────────────────


def project_root(q: Question) -> Path:
    """The folder holding ``challenges/``, ``mcq/`` and ``templates/``."""
    return q.root.parent.parent if q.root.parent.name == "templates" else Path.cwd()


@dataclass
class Ref:
    """A ref in template.json, resolved to a platform id."""

    raw: Any
    kind: str
    id: int | None = None
    local: str | None = None  # the folder, for a local ref

    @property
    def label(self) -> str:
        return f"{self.id} ({self.local})" if self.local else str(self.id)


def resolve(raw: Any, kind: str, root: Path, template_root: Path | None = None) -> Ref:
    """A ref as a platform id: an integer is one already; a string is a local
    question folder of this kind, which must have been pushed."""
    if isinstance(raw, int) and not isinstance(raw, bool):
        return Ref(raw, kind, int(raw))
    if not isinstance(raw, str) or not raw.strip():
        raise PraxisError(f"{raw!r} is not a ref: use a platform id (a number) or a local question folder.")
    q = None
    for cwd in (root, template_root):
        if cwd is None:
            continue
        try:
            q = Question.find(raw, cwd=cwd)
            break
        except PraxisError:
            continue
    if q is None or q.kind == "template":
        raise PraxisError(f"No local question '{raw}' (looked in {root / 'challenges'} and {root / 'mcq'}).")
    if q.kind != kind:
        raise PraxisError(f"'{raw}' is {_a(q.kind)}, not {_a(kind)}.")
    if kind == "coding":
        found, where = q.read_publish().get("challenge_id"), "pack/publish.json has no challenge_id"
    elif kind == "interview":
        found, where = q.read_question().get("id"), "question.json has no id"
    else:
        found, where = q.state().get("bank_id"), ".codepraxis.json has no bank_id"
    if not found:
        raise PraxisError(f"'{raw}' is not pushed yet ({where}): run `codepraxis push {raw}` first.")
    return Ref(raw, kind, int(found), q.slug)


def _a(kind: str) -> str:
    return {"mcq": "an MCQ bank", "interview": "an interview question"}.get(kind, f"a {kind} question")


# ── checking ──────────────────────────────────────────────────────────────


@dataclass
class Line:
    """One question in the summary."""

    round: str
    ref: Ref
    item: Item | None
    minutes: int | None
    note: str = ""


@dataclass
class Report:
    """What ``check`` found. Errors block a push; warnings don't."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    minutes: dict[str, int] = field(default_factory=dict)
    drafts: list[Line] = field(default_factory=list)
    body: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def total(self) -> int:
        return sum(self.minutes.values())


def _in(value, bounds) -> bool:
    n = _whole_number(value)
    return n is not None and bounds[0] <= n <= bounds[1]


def check(template: dict, root: Path, library: dict[str, list[Item]], *, published: bool = False,
          categories: set[str] | None = None, template_root: Path | None = None) -> Report:
    """Every ref resolved and found in the library, each round within the
    platform's limits, and the body ``POST /templates`` takes.

    ``published`` is True when the template being replaced is published: its new
    version is published at once, so no question in it may be a draft.
    """
    report = Report()
    errors, warnings = report.errors, report.warnings
    by_id = {kind: {i.id: i for i in library.get(kind, [])} for kind in KINDS}

    for extra in sorted(set(template) - TEMPLATE_KEYS):
        warnings.append(f"template.json: unknown key '{extra}'; it is ignored.")
    name = str(template.get("name") or "").strip()
    if not name:
        errors.append("The template needs a name.")
    category = template.get("category")
    if category is not None and not isinstance(category, str):
        errors.append("category must be a category slug (see `codepraxis categories`) or null.")
    elif category and categories is not None and category not in categories:
        errors.append(f"Unknown category '{category}' (see `codepraxis categories`).")
    proctoring = template.get("proctoring") or {}
    if not isinstance(proctoring, dict) or set(proctoring) - set(PROCTORING_KEYS):
        errors.append(f"proctoring takes {', '.join(PROCTORING_KEYS)}, each true or false.")
        proctoring = {}

    def ref(raw, kind: str, where: str) -> tuple[Ref, Item | None] | None:
        try:
            r = resolve(raw, kind, root, template_root)
        except PraxisError as exc:
            errors.append(f"{where}: {exc}")
            return None
        item = by_id[kind].get(r.id)
        if item is None:
            what = "MCQ bank" if kind == "mcq" else f"{kind} question"
            errors.append(f"{where}: {what} {r.label} is not in the library this API key can use.")
        elif item.status in UNUSABLE:
            errors.append(f"{where}: {kind} question {r.label} is {item.status}.")
        return r, item

    def add(round_name: str, r: Ref, item: Item | None, minutes: int | None, note: str = "") -> None:
        line = Line(round_name, r, item, minutes, note)
        report.lines.append(line)
        if item is not None and item.status == "draft":
            report.drafts.append(line)

    body: dict[str, Any] = {
        "name": name,
        "description": template.get("description"),
        "category": category if isinstance(category, str) and category else None,
    }

    # Coding: single questions, then pools of alternatives.
    coding = template.get("coding") or {}
    coding_ids: list[int] = []
    coding_times: list[int] = []
    pools: list[dict] = []
    seen_coding: set[int] = set()
    coding_minutes = 0
    if not isinstance(coding, dict):
        errors.append("coding must be {\"questions\": [...], \"pools\": [...]} or null.")
        coding = {}
    for n, entry in enumerate(coding.get("questions") or [], start=1):
        where = f"coding question {n}"
        entry = entry if isinstance(entry, dict) else {"ref": entry}
        found = ref(entry.get("ref"), "coding", where)
        if found is None:
            continue
        r, item = found
        minutes = entry.get("minutes")
        if minutes is None:
            minutes = item.minutes if item else None
        elif not _in(minutes, ROUND_MINUTES):
            errors.append(f"{where}: minutes must be {ROUND_MINUTES[0]} to {ROUND_MINUTES[1]}.")
        minutes = _whole_number(minutes)
        if r.id in seen_coding:
            errors.append(f"{where}: coding question {r.id} is already in the template.")
        seen_coding.add(r.id)
        coding_ids.append(r.id)
        coding_times.append(minutes or 0)
        coding_minutes += minutes or 0
        add("coding", r, item, minutes)
    for n, pool in enumerate(coding.get("pools") or [], start=1):
        where = f"coding pool {n}"
        if not isinstance(pool, dict):
            errors.append(f"{where}: must be {{\"refs\": [...], \"pick\": 1, \"minutes\": N}}.")
            continue
        refs = pool.get("refs") or []
        pick = _whole_number(pool.get("pick", 1))
        if len(refs) < 2:
            errors.append(f"{where}: a pool needs at least 2 alternatives.")
        if pick is None or not 1 <= pick <= max(len(refs), 1):
            errors.append(f"{where}: pick must be 1 to the number of alternatives.")
            pick = 1
        resolved = [ref(raw, "coding", f"{where}, alternative {i}") for i, raw in enumerate(refs, start=1)]
        resolved = [f for f in resolved if f is not None]
        minutes = pool.get("minutes")
        if minutes is None:
            minutes = max((item.minutes or 0 for _r, item in resolved if item), default=0) or None
        elif not _in(minutes, ROUND_MINUTES):
            errors.append(f"{where}: minutes must be {ROUND_MINUTES[0]} to {ROUND_MINUTES[1]}.")
        minutes = _whole_number(minutes)
        for r, item in resolved:
            if r.id in seen_coding:
                errors.append(f"{where}: coding question {r.id} is already in the template.")
            seen_coding.add(r.id)
            add("coding", r, item, minutes, f"pool {n}: pick {pick} of {len(refs)}")
        pools.append({"challenge_ids": [r.id for r, _ in resolved], "pick_count": pick, "time_limit": minutes})
        coding_minutes += pick * (minutes or 0)
    has_coding = bool(coding_ids or pools)
    if has_coding:
        body["coding_challenge_ids"] = coding_ids
        body["coding_question_times"] = coding_times
        body["coding_pools"] = pools
        report.minutes["coding"] = coding_minutes

    body["proctoring"] = {k: bool(proctoring.get(k, False)) for k in PROCTORING_KEYS}
    body["rules"] = {"ai_assistant_enabled": bool(template.get("ai_assistant", False))}

    # Code review: about the code the candidate submitted, so only after coding.
    code_review = template.get("code_review")
    if code_review:
        minutes = code_review.get("minutes") if isinstance(code_review, dict) else None
        if not has_coding:
            errors.append("code_review needs a coding round: it asks about the code the candidate submitted.")
        elif not _in(minutes, ROUND_MINUTES):
            errors.append(f"code_review minutes must be {ROUND_MINUTES[0]} to {ROUND_MINUTES[1]}.")
        else:
            body["code_review"] = {"time_limit": int(minutes)}
            report.minutes["code_review"] = int(minutes)

    # Interview: one question asked per group; a group lasts as long as its longest.
    interview = template.get("interview")
    body["evaluation_type"] = "standard"
    if interview:
        questions = interview.get("questions") if isinstance(interview, dict) else None
        if not isinstance(questions, list) or not questions:
            errors.append("interview needs questions: [<ref>, [<ref>, <ref>] for alternatives, …].")
            questions = []
        if len(questions) > INTERVIEW_MAX_QUESTIONS:
            errors.append(f"An interview asks at most {INTERVIEW_MAX_QUESTIONS} questions.")
        groups: list[list[int]] = []
        seen_interview: set[int] = set()
        total = 0
        unknown = False  # a question that didn't resolve has no duration to add
        for n, entry in enumerate(questions, start=1):
            alternatives = entry if isinstance(entry, list) else [entry]
            where = f"interview question {n}"
            if not alternatives:
                errors.append(f"{where}: an empty group.")
                continue
            group: list[int] = []
            longest = 0
            for i, raw in enumerate(alternatives, start=1):
                found = ref(raw, "interview", where if len(alternatives) == 1 else f"{where}, alternative {i}")
                if found is None or found[1] is None:
                    unknown = True
                if found is None:
                    continue
                r, item = found
                if r.id in seen_interview:
                    errors.append(f"{where}: interview question {r.id} is already in the template.")
                seen_interview.add(r.id)
                group.append(r.id)
                longest = max(longest, (item.minutes or 0) if item else 0)
                add("interview", r, item, item.minutes if item else None,
                    f"group {n}: one of {len(alternatives)}" if len(alternatives) > 1 else "")
            if group:
                groups.append(group)
                total += longest
        if questions and not unknown and not INTERVIEW_MINUTES[0] <= total <= INTERVIEW_MINUTES[1]:
            errors.append(f"The interview adds up to {total} minutes; it must be {INTERVIEW_MINUTES[0]} to "
                          f"{INTERVIEW_MINUTES[1]}.")
        body["evaluation_type"] = "ai_interview"
        body["ai_interview"] = {
            "total_minutes": total,
            "groups": [{"question_ids": g} for g in groups],
            "question_ids": [g[0] for g in groups],
        }
        report.minutes["interview"] = total

    # Knowledge check: drawn from one or more banks.
    mcq = template.get("mcq")
    if mcq:
        mcq = mcq if isinstance(mcq, dict) else {}
        bank_ids: list[int] = []
        for n, raw in enumerate(mcq.get("banks") or [], start=1):
            found = ref(raw, "mcq", f"mcq bank {n}")
            if found is not None:
                r, item = found
                if r.id in bank_ids:
                    errors.append(f"mcq bank {n}: bank {r.id} is already in the round.")
                bank_ids.append(r.id)
                add("mcq", r, item, None)
        if not mcq.get("banks"):
            errors.append("mcq needs banks: [<ref>, …].")
        if not _in(mcq.get("questions"), MCQ_QUESTIONS):
            errors.append(f"mcq questions must be {MCQ_QUESTIONS[0]} to {MCQ_QUESTIONS[1]}.")
        if not _in(mcq.get("minutes"), ROUND_MINUTES):
            errors.append(f"mcq minutes must be {ROUND_MINUTES[0]} to {ROUND_MINUTES[1]}.")
        body["mcq"] = {"question_bank_ids": bank_ids, "question_count": _whole_number(mcq.get("questions")),
                       "time_limit": _whole_number(mcq.get("minutes"))}
        report.minutes["mcq"] = _whole_number(mcq.get("minutes")) or 0

    if not (has_coding or interview or mcq):
        errors.append("The template has no rounds: add coding, interview or mcq.")
    if published and report.drafts:
        errors.append(
            f"This template is published, so a push publishes a new version at once, and it may not hold "
            f"draft questions: {', '.join(_draft_label(d) for d in report.drafts)}. Publish them first."
        )
    report.body = body
    return report


def _draft_label(line: Line) -> str:
    name = f" '{line.item.name}'" if line.item and line.item.name else ""
    return f"{line.round} {line.ref.id}{name}"


def print_report(report: Report) -> None:
    for problem in report.errors:
        progress.failed(problem)
    for warning in report.warnings:
        progress.warn(warning)
    for round_name in ("coding", "code_review", "interview", "mcq"):
        if round_name not in report.minutes:
            continue
        progress.line(f"  {ROUND_NAMES[round_name]:16} {report.minutes[round_name]:>4} min")
        for line in report.lines:
            if line.round != round_name:
                continue
            item = line.item
            minutes = f"{line.minutes}m" if line.minutes else (
                f"{item.extra.get('question_count', 0)}q" if item and round_name == "mcq" else "-")
            status = item.status if item else "?"
            name = item.name if item else ""
            progress.line(f"    {line.ref.id:>5}  {status:9}  {minutes:>4}  {name}"
                          + (f"  [{line.note}]" if line.note else "")
                          + (f"  ← {line.ref.local}" if line.ref.local else ""))
    if report.minutes:
        progress.line(f"  {'total':16} {report.total:>4} min")
    if report.drafts:
        progress.warn(f"{len(report.drafts)} question(s) still drafts; publish them in the dashboard before "
                      f"the template: {', '.join(_draft_label(d) for d in report.drafts)}.")


# ── template.json ↔ the platform ──────────────────────────────────────────


def read(q: Question) -> dict:
    try:
        data = json.loads((q.root / TEMPLATE_JSON).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PraxisError(f"{q.root / TEMPLATE_JSON} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise PraxisError(f"{q.root / TEMPLATE_JSON} must be one JSON object with a name and its rounds.")
    return data


def to_local(detail: dict) -> dict:
    """``GET /templates/{id}`` as template.json, every ref a platform id."""
    category = detail.get("category")
    proctoring = detail.get("proctoring") or {}
    out: dict[str, Any] = {
        "name": detail.get("name"),
        "description": detail.get("description"),
        "category": category.get("slug") if isinstance(category, dict) else category,
        "proctoring": {k: bool(proctoring.get(k, False)) for k in PROCTORING_KEYS},
        "ai_assistant": bool((detail.get("rules") or {}).get("ai_assistant_enabled", False)),
    }
    ids = detail.get("assessment_coding_challenge_ids") or []
    times = detail.get("assessment_coding_question_times") or []
    pools = detail.get("coding_pools") or []
    if ids or pools:
        coding: dict[str, Any] = {"questions": [
            {"ref": int(c), **({"minutes": int(times[i])} if i < len(times) and times[i] else {})}
            for i, c in enumerate(ids)
        ]}
        if pools:
            coding["pools"] = [
                {"refs": [int(c) for c in p.get("challenge_ids") or []], "pick": int(p.get("pick_count") or 1),
                 **({"minutes": int(p["time_limit"])} if p.get("time_limit") else {})}
                for p in pools
            ]
        out["coding"] = coding
    else:
        out["coding"] = None
    review = detail.get("code_review") or {}
    out["code_review"] = {"minutes": int(review["time_limit"])} if review.get("time_limit") else None
    interview = detail.get("ai_interview") or {}
    if detail.get("evaluation_type") == "ai_interview" and interview:
        groups = [g.get("question_ids") or [] for g in interview.get("groups") or []]
        if not groups:
            groups = [[i] for i in interview.get("question_ids") or []]
        out["interview"] = {"questions": [int(g[0]) if len(g) == 1 else [int(i) for i in g] for g in groups if g]}
    else:
        out["interview"] = None
    mcq = detail.get("mcq") or {}
    banks = mcq.get("question_bank_ids") or ([mcq["question_bank_id"]] if mcq.get("question_bank_id") else [])
    out["mcq"] = {"banks": [int(b) for b in banks], "questions": mcq.get("question_count"),
                  "minutes": mcq.get("time_limit")} if banks else None
    return out


def remember(q: Question, detail: dict) -> dict:
    return q.save_state(template_id=int(detail["template_id"]), version=detail.get("version"),
                        status=status_of(detail.get("status")), lineage_id=detail.get("lineage_id"))


# ── commands ──────────────────────────────────────────────────────────────


def _checked(q: Question, backend: Backend) -> Report:
    template = read(q)
    published = q.state().get("status") == "published"
    with progress.step(f"Checking {q.slug}/{TEMPLATE_JSON} against the library") as s:
        library = fetch_library(backend, retired=True)
        categories = {c["slug"] for c in backend.get("/categories").get("categories", [])}
        report = check(template, project_root(q), library, published=published, categories=categories,
                       template_root=q.root)
        s.result(f"Checked {len(report.lines)} question(s): {len(report.errors)} error(s), "
                 f"{len(report.warnings)} warning(s)")
    print_report(report)
    return report


def test(q: Question, backend: Backend) -> bool:
    """Resolve and check every ref, and print each round's minutes. True when
    nothing blocks a push."""
    return _checked(q, backend).ok


def push(q: Question, backend: Backend) -> dict:
    """Save as a new draft, or replace this template (a draft) or publish its
    next version (a published one)."""
    report = _checked(q, backend)
    if not report.ok:
        raise PraxisError(f"{len(report.errors)} problem(s) in {TEMPLATE_JSON}; fix them and push again.")
    state = q.state()
    source = state.get("template_id")
    path = f"/templates?source_template_id={source}" if source else "/templates?status=draft"
    what = f" (replacing draft {source})" if source and state.get("status") == "draft" else \
        f" (new version of {source})" if source else ""
    with progress.step(f"Pushing {q.slug}{what}") as s:
        try:
            result = backend.post_json(path, report.body)
        except NotFound as exc:
            if source:
                raise PraxisError(
                    f"Template {source} is not on the platform, or this API key can't write it. Remove "
                    f"template_id from {q.slug}/.codepraxis.json to create a new draft instead."
                ) from exc
            raise
        except HttpError as exc:
            if exc.status in (409, 422):
                raise PraxisError(f"The platform refused the template: {exc.detail or exc}") from exc
            raise
        remember(q, result)
        status = status_of(result.get("status"))
        if status == "draft":
            s.result(f"{'Saved' if not source else 'Replaced'} template {result['template_id']} as a draft "
                     f"(version {result.get('version')})")
        else:
            s.result(f"Published version {result.get('version')} of the template: id {result['template_id']}")
    alternatives = any(len(g["question_ids"]) > 1 for g in (report.body.get("ai_interview") or {}).get("groups", []))
    if alternatives and not (result.get("ai_interview") or {}).get("groups"):
        progress.warn("The platform kept only the first question of each interview group, not the alternatives.")
    result["url"] = dashboard_link(result["template_id"])
    progress.line(f"  {result['url']}")
    if status == "draft":
        progress.line("  Publish it in the dashboard once its questions are published.")
    else:
        progress.warn("This template is live: candidates sent it from now on get this version.")
    return result


def default_folder(detail: dict, template_id: int) -> Path:
    return Path.cwd() / "templates" / (_slug(str(detail.get("name") or "")) or f"template_{template_id}")


def pull(backend: Backend, template_id: int, into: Path | None = None) -> Question:
    """Write a template into ``into`` (default ``templates/<name>``): template.json
    with every ref a platform id."""
    with progress.step(f"Pulling template {template_id}") as s:
        detail = backend.get(f"/templates/{template_id}")
        root = into or default_folder(detail, template_id)
        root.mkdir(parents=True, exist_ok=True)
        local = to_local(detail)
        (root / TEMPLATE_JSON).write_text(json.dumps(local, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        q = Question(root)
        state = remember(q, detail)
        s.result(f"Pulled template {template_id} ({state['status']}, version {state.get('version')}) into {root}")
    stored = (detail.get("ai_interview") or {}).get("total_minutes")
    if local.get("interview") and stored:
        durations = {i.id: i.minutes or 0 for i in fetch_library(backend, ("interview",), retired=True)["interview"]}
        computed = sum(max(durations.get(i, 0) for i in (g if isinstance(g, list) else [g]))
                       for g in local["interview"]["questions"])
        if computed != int(stored):
            progress.warn(f"The interview is set to {stored} minutes on the platform; its questions add up to "
                          f"{computed}, which is what a push sets.")
    return q
