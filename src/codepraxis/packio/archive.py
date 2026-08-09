"""Package a pack for upload.

Two different archives, for two different purposes:

``build_pack_zip``
    Exactly what candidates receive. The runner unzips it into
    ``/praxis/codeFromServer/`` and expects ``metadata.json`` one level below a
    single top-level folder. **Never contains the reference solution.**

``build_validation_bundle``
    What remote validation receives: the pack *and* the solution, so the server
    can run both fixtures. The solution is kept in a sibling directory inside
    the bundle so it can never be mistaken for pack content and shipped onward.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from ..domain.pack import Pack
from ..errors import PackError

#: Never packaged, regardless of where they appear.
_EXCLUDED_NAMES = frozenset({"__pycache__", ".DS_Store"})

#: Refuse absurd uploads early with a clear message rather than timing out.
MAX_BUNDLE_BYTES = 64 * 1024 * 1024


def _should_skip(path: Path) -> bool:
    return any(part in _EXCLUDED_NAMES for part in path.parts) or path.suffix == ".pyc"


def _add_tree(archive: zipfile.ZipFile, source: Path, prefix: str) -> None:
    for entry in sorted(source.rglob("*")):
        if not entry.is_file() or _should_skip(entry.relative_to(source)):
            continue
        archive.write(entry, f"{prefix}/{entry.relative_to(source).as_posix()}")


def _finish(buffer: io.BytesIO, label: str) -> bytes:
    payload = buffer.getvalue()
    if len(payload) > MAX_BUNDLE_BYTES:
        raise PackError(
            f"{label} is {len(payload) // (1024 * 1024)} MB, over the "
            f"{MAX_BUNDLE_BYTES // (1024 * 1024)} MB limit. "
            f"Large fixtures usually belong in setup.sh instead of source/."
        )
    return payload


def build_pack_zip(pack: Pack) -> bytes:
    """The candidate-facing artifact: one top-level folder named for the pack."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        _add_tree(archive, pack.root, pack.name)
    return _finish(buffer, "Pack")


def build_validation_bundle(pack: Pack) -> bytes:
    """Pack plus reference solution, for server-side validation."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        _add_tree(archive, pack.root, f"pack/{pack.name}")
        if pack.has_solution:
            _add_tree(archive, pack.solution_dir, "solution")
    return _finish(buffer, "Validation bundle")
