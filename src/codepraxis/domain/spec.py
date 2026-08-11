"""The plan, and whether a human approved it.

`spec.md` is written before any code and lives at the question level. It exists
because the gap between "an agent understood the task" and "an agent started
writing files" had nothing in it: an agent that has just done ten tool calls of
research reads "write down the architecture" as an internal step and keeps
going, because stopping feels like failing to finish.

So approval is *state on disk*, not a moment in a conversation. A chat exchange
leaves no trace — compact the transcript, or run the next step in a fresh
session or on another machine, and there is nothing left to check. A file
survives all three.

The format is YAML-ish frontmatter, parsed here rather than with a dependency,
because the package has no runtime dependencies and this is three keys.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import contract

#: Frontmatter delimiter, at the very start of the file.
_FENCE = "---"

_KEY_VALUE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")

STATUS_DRAFT = "draft"
STATUS_APPROVED = "approved"


@dataclass(frozen=True)
class Spec:
    path: Path
    status: str
    fields: dict[str, str]
    body: str

    @property
    def approved(self) -> bool:
        return self.status == STATUS_APPROVED

    @property
    def approved_at(self) -> str | None:
        return self.fields.get("approved_at")


def spec_path(question_dir: Path) -> Path:
    return question_dir / contract.SPEC_FILE


def question_dir_for(pack_dir: Path) -> Path:
    """The question directory a pack belongs to.

    Packs live at ``<question>/pack``; anything else is treated as its own
    question so this stays total rather than raising on unusual layouts.
    """
    return pack_dir.parent if pack_dir.name == contract.PACK_DIR else pack_dir


def parse(text: str, path: Path | None = None) -> Spec:
    """Read frontmatter and body. A file with no frontmatter is a draft.

    Missing status is deliberately *not* an error: a hand-written spec should
    still be readable. It simply is not approved, which is the safe default.
    """
    path = path or Path(contract.SPEC_FILE)
    fields: dict[str, str] = {}
    body = text

    lines = text.splitlines()
    if lines and lines[0].strip() == _FENCE:
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == _FENCE:
                body = "\n".join(lines[index + 1 :]).lstrip("\n")
                break
            match = _KEY_VALUE.match(line.strip())
            if match:
                fields[match.group(1)] = match.group(2).strip().strip("\"'")

    return Spec(
        path=path,
        status=fields.get("status", STATUS_DRAFT).lower(),
        fields=fields,
        body=body,
    )


def read(question_dir: Path) -> Spec | None:
    path = spec_path(question_dir)
    if not path.is_file():
        return None
    return parse(path.read_text(encoding="utf-8"), path)


def approve(question_dir: Path) -> Spec:
    """Record that a human approved this plan.

    Rewrites only the frontmatter, so an author's edits to the plan itself are
    never touched.
    """
    from ..errors import PraxisError

    existing = read(question_dir)
    if existing is None:
        raise PraxisError(
            f"No {contract.SPEC_FILE} in {question_dir}. Plan the question before approving it."
        )

    fields = dict(existing.fields)
    fields["status"] = STATUS_APPROVED
    fields.setdefault("question", question_dir.name)
    fields["approved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    rendered = [_FENCE, *(f"{key}: {value}" for key, value in fields.items()), _FENCE, "", existing.body]
    spec_path(question_dir).write_text("\n".join(rendered).rstrip() + "\n", encoding="utf-8")

    return read(question_dir)  # type: ignore[return-value]


def require_approved(pack_dir: Path) -> Spec:
    """The gate `build` and `ship` sit behind.

    Raises with the specific next step rather than a generic refusal — an
    author blocked by a gate they do not understand simply works around it.
    """
    from ..errors import PraxisError

    question = question_dir_for(pack_dir)
    spec = read(question)

    if spec is None:
        raise PraxisError(
            f"{question.name} has no {contract.SPEC_FILE}, so there is no plan to build from.\n"
            f"Run /codepraxis:plan to design the question first."
        )

    if not spec.approved:
        raise PraxisError(
            f"{question.name}'s plan has not been approved.\n"
            f"Read {spec.path}, then run `codepraxis approve {question.name}` to accept it."
        )

    return spec
