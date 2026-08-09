"""Materialise the candidate workspace on the local filesystem.

The runner does this with rsync into ``/home/praxis/{foldername}``:

    rsync -a /praxis/codeFromServer/{foldername}/source/ /home/praxis/{foldername}/

Note the trailing slash — ``source/``'s *contents* land in the workspace, not a
nested ``source`` directory. For the SOLUTION fixture, ``solution/`` is then
overlaid preserving relative paths, matching how the question-bank validator
untars the reference solution over the workspace.
"""

from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ...domain.pack import Pack
from ...domain.results import Fixture
from ...errors import HarnessError

#: Copied into the workspace like anything else — tests may inspect git history,
#: and the authoring guide requires ``source/`` to carry a baseline commit.
_EXCLUDED_NAMES = frozenset({"__pycache__", ".DS_Store"})


def _ignore(_dir: str, names: list) -> set:
    return {name for name in names if name in _EXCLUDED_NAMES or name.endswith(".pyc")}


def _overlay(src: Path, dest: Path) -> None:
    """Copy ``src``'s contents over ``dest``, preserving relative paths."""
    for entry in sorted(src.rglob("*")):
        if any(part in _EXCLUDED_NAMES for part in entry.parts):
            continue
        relative = entry.relative_to(src)
        target = dest / relative
        if entry.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry, target)


@contextmanager
def materialize(pack: Pack, fixture: Fixture) -> Iterator[Path]:
    """Build a throwaway workspace and yield its path.

    The workspace is created inside a temporary directory that stands in for
    ``/home/praxis``, so a test resolving ``self.userWxpace / ".."`` sees a
    plausible layout. Everything is removed on exit, pass or fail.
    """
    if not pack.source_dir.is_dir():
        raise HarnessError(f"Pack has no {pack.source_dir.name}/ directory: {pack.source_dir}")

    if fixture is Fixture.SOLUTION and not pack.has_solution:
        raise HarnessError(
            "This pack has no solution/ directory, so the SOLUTION fixture cannot be built. "
            "A reference solution is required before a pack can be published."
        )

    home = Path(tempfile.mkdtemp(prefix="praxis-ws-"))
    workspace = home / pack.name
    try:
        shutil.copytree(pack.source_dir, workspace, ignore=_ignore)
        if fixture is Fixture.SOLUTION:
            _overlay(pack.solution_dir, workspace)
        yield workspace
    finally:
        shutil.rmtree(home, ignore_errors=True)
