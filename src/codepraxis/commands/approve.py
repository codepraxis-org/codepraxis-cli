"""``codepraxis approve`` — accept a plan, on the record.

This is the handshake between planning and building. It is a command rather
than a spoken "yes" in chat because the next step may run in a fresh session,
on another machine, or by a colleague — none of whom can see the conversation
where approval was given.
"""

from __future__ import annotations

from pathlib import Path

from ..domain import contract
from ..domain import spec as spec_module
from ..errors import PraxisError
from ..packio import discovery

EXIT_OK = 0


def run(root: Path, selector: str | None = None) -> int:
    question = _resolve_question(root, selector)

    existing = spec_module.read(question)
    if existing is None:
        raise PraxisError(
            f"{question.name} has no {contract.SPEC_FILE}. Run /codepraxis:plan to design it first."
        )

    if existing.approved:
        print(f"{question.name} was already approved ({existing.approved_at}).")
        return EXIT_OK

    approved = spec_module.approve(question)
    print(f"Approved {question.name} ({approved.approved_at}).")
    print()
    print("Next:")
    print("    /codepraxis:build")
    return EXIT_OK


def _resolve_question(root: Path, selector: str | None) -> Path:
    """Find the question to approve.

    A question with a plan but no pack yet is the normal case here — planning
    runs before any code exists — so this cannot go through pack discovery.
    """
    root = root.resolve()

    if selector:
        for candidate in ((root / selector), Path(selector).expanduser()):
            if (candidate / contract.SPEC_FILE).is_file():
                return candidate.resolve()
        # Fall back to pack discovery so a pack path or name also works.
        return spec_module.question_dir_for(discovery.resolve_pack_dir(root, selector))

    planned = sorted(
        path.parent
        for path in root.rglob(contract.SPEC_FILE)
        if path.is_file() and not any(part.startswith(".") for part in path.relative_to(root).parts)
    )
    unapproved = [q for q in planned if not (spec_module.read(q) or spec_module.parse("")).approved]

    if len(unapproved) == 1:
        return unapproved[0]
    if not unapproved:
        raise PraxisError(f"No unapproved plans found under {root}.")

    listed = "\n  ".join(q.name for q in unapproved)
    raise PraxisError(f"Several plans are waiting for approval; name one:\n  {listed}")
