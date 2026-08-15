"""Load a :class:`Pack` from a directory.

Filesystem in, domain object out. Nothing here imports or executes pack code —
that boundary is what lets ``praxis lint`` inspect an untrusted pack safely.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..domain import contract
from ..domain.pack import Backend, Pack
from ..errors import PackError
from .toc import resolve_active_index

#: Sibling of the pack directory, never inside it — keeping the reference
#: solution out of the pack is what stops it being uploaded to candidates.
SOLUTION_DIR_NAME = "solution"
ATTEMPT_DIR_NAME = ".attempt"


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise PackError(f"Missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PackError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(value, dict):
        raise PackError(f"{path} must contain a JSON object")
    return value


def missing_required_paths(pack_dir: Path) -> list:
    """Required entries absent from ``pack_dir``, in declaration order."""
    return [rel for rel in contract.REQUIRED_PACK_PATHS if not (pack_dir / rel).exists()]


def find_solution_dir(pack_dir: Path) -> Path | None:
    """Locate the reference solution beside the pack.

    Layouts supported, in order of preference:
      ``<pack_dir>/../solution``  — CLI layout, and the question-bank CI layout
    """
    candidate = pack_dir.parent / SOLUTION_DIR_NAME
    return candidate if candidate.is_dir() else None


def find_attempt_dir(pack_dir: Path) -> Path | None:
    """Locate an attempt beside the pack.

    Sibling of the pack like ``solution/``, and dot-prefixed because it is
    scratch: written by whoever is measuring the question, never committed,
    never uploaded.
    """
    candidate = pack_dir.parent / ATTEMPT_DIR_NAME
    return candidate if candidate.is_dir() else None


def load_pack(pack_dir: Path) -> Pack:
    """Build a :class:`Pack` from ``pack_dir``.

    Raises :class:`PackError` for anything that makes the pack unloadable.
    Softer problems (style, panel-row mismatches) belong in ``praxis lint`` so
    that a pack with warnings can still be executed.
    """
    pack_dir = pack_dir.expanduser().resolve()
    if not pack_dir.is_dir():
        raise PackError(f"Not a directory: {pack_dir}")

    missing = missing_required_paths(pack_dir)
    if missing:
        raise PackError(f"Pack at {pack_dir} is missing required files: {', '.join(missing)}")

    metadata = read_json(pack_dir / contract.METADATA_FILE)
    name = metadata.get("name")
    if not isinstance(name, str) or not name.strip():
        raise PackError(f"{contract.METADATA_FILE} must include a non-empty string 'name'")

    backend = Backend.from_mapping(read_json(pack_dir / contract.BACKEND_CONF_FILE))

    toc = read_json(pack_dir / contract.COURSE_DATA_DIR / contract.COURSE_TOC_FILE)
    active_index = resolve_active_index(toc)

    active_test = pack_dir / contract.TESTS_DIR / f"test_{active_index}.py"
    if not active_test.exists():
        raise PackError(
            f"course_toc.json selects instruction {active_index} "
            f"but {contract.TESTS_DIR}/test_{active_index}.py does not exist"
        )

    return Pack(
        root=pack_dir,
        name=name.strip(),
        backend=backend,
        metadata=metadata,
        active_test_index=active_index,
        solution_dir=find_solution_dir(pack_dir),
        attempt_dir=find_attempt_dir(pack_dir),
    )
