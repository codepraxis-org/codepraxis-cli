"""Resolve which test module is active, exactly as the runner does.

Mirrors ``setupCodeBase.py`` (the block that reads ``course_toc.json`` before
copying ``._tests/test_{n}.py`` to ``._tests/test.py``):

1. first instruction whose ``metadata.STATUS`` is ``IN_PROGRESS``
2. else first whose ``STATUS`` is ``FAIL``
3. else the LAST key in the file, by insertion order
4. if that still yields 0, the runner raises

Insertion order matters, so the TOC must be parsed with ordering preserved —
``json.load`` into a dict does this on every supported Python version.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..errors import PackError

STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_FAIL = "FAIL"


def _index_of(instruction_key: str) -> int:
    """``instruction_3`` -> 3. Returns 0 when the suffix is not an integer.

    The runner does ``int(key.split('_')[1])``, which raises on a malformed key;
    we return 0 so the caller can produce a clean diagnostic instead.
    """
    parts = instruction_key.split("_")
    if len(parts) < 2 or not parts[1].isdigit():
        return 0
    return int(parts[1])


def _status_of(entry: Any) -> str:
    if not isinstance(entry, Mapping):
        return ""
    metadata = entry.get("metadata")
    if not isinstance(metadata, Mapping):
        return ""
    return str(metadata.get("STATUS", ""))


def resolve_active_index(toc: Mapping[str, Any]) -> int:
    """Return the ``n`` in ``._tests/test_{n}.py`` the runner would select."""
    if not toc:
        raise PackError("course_toc.json is empty; no active test case could be resolved")

    for key, entry in toc.items():
        if _status_of(entry) == STATUS_IN_PROGRESS:
            index = _index_of(key)
            if index:
                return index

    for key, entry in toc.items():
        if _status_of(entry) == STATUS_FAIL:
            index = _index_of(key)
            if index:
                return index

    last_key = next(reversed(list(toc.keys())))
    index = _index_of(last_key)
    if index:
        return index

    raise PackError(
        "No active test case found in course_toc.json "
        "(no instruction has STATUS IN_PROGRESS or FAIL, and the last key has no numeric suffix)"
    )
