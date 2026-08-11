"""Find challenge packs beneath a directory.

A pack is any directory containing ``metadata.json`` plus the rest of the
required layout, so discovery works for both the CLI's ``challenges/<slug>/``
convention and other arrangements without hard-coding either.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from ..domain import contract

#: Never descend into these while searching.
SKIP_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        contract.SOURCE_DIR,
        contract.TESTS_DIR,
        contract.COURSE_DATA_DIR,
    }
)

#: Bound the walk so a mistaken run at "/" does not scan the whole disk.
MAX_DEPTH = 6


def looks_like_pack(path: Path) -> bool:
    return (path / contract.METADATA_FILE).is_file() and (path / contract.BACKEND_CONF_FILE).is_file()


def iter_packs(root: Path, max_depth: int = MAX_DEPTH) -> Iterator[Path]:
    """Yield pack directories under ``root``, nearest first.

    A directory that is itself a pack is yielded and not descended into.
    """
    root = root.expanduser().resolve()
    if not root.is_dir():
        return

    if looks_like_pack(root):
        yield root
        return

    frontier = [(root, 0)]
    while frontier:
        current, depth = frontier.pop(0)
        if depth >= max_depth:
            continue
        try:
            children = sorted(p for p in current.iterdir() if p.is_dir())
        except PermissionError:
            continue
        for child in children:
            if child.name in SKIP_DIRS or child.name.startswith("."):
                continue
            if looks_like_pack(child):
                yield child
            else:
                frontier.append((child, depth + 1))


def find_packs(root: Path) -> list[Path]:
    return list(iter_packs(root))


def question_name(pack_dir: Path) -> str:
    """The name an author refers to a pack by.

    Packs live at ``<question>/pack``, so the useful handle is the question
    directory. Selecting by the literal directory name would make every
    question in a repo answer to ``pack``.
    """
    if pack_dir.name == contract.PACK_DIR:
        return pack_dir.parent.name
    return pack_dir.name


def resolve_pack_dir(root: Path, selector: str) -> Path:
    """Resolve a user-supplied selector to a single pack directory.

    ``selector`` may be a path to either the question or the pack inside it,
    or the question's name.
    """
    from ..errors import PackError

    for candidate in ((root / selector).expanduser(), Path(selector).expanduser()):
        if looks_like_pack(candidate):
            return candidate.resolve()
        # A path to the question directory is the natural thing to type, and
        # the pack is one predictable level below it.
        nested = candidate / contract.PACK_DIR
        if looks_like_pack(nested):
            return nested.resolve()

    matches = [p for p in iter_packs(root) if question_name(p) == selector]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise PackError(f"No question named {selector!r} found under {root}")
    listed = "\n  ".join(str(m) for m in matches)
    raise PackError(f"{selector!r} is ambiguous; matched:\n  {listed}")
