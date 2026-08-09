"""In-memory representation of a challenge pack.

Pure data: constructing a :class:`Pack` never executes pack code. Loading lives
in :mod:`praxis.packio`, execution in :mod:`praxis.execution`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from . import contract


@dataclass(frozen=True)
class Backend:
    """Parsed ``backend.conf``.

    ``BACKEND`` selects how the runner configures the workspace and which
    execution semantics apply; ``LANGUAGE`` is documentation for the author.
    """

    backend: str
    language: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "Backend":
        return cls(
            backend=str(data.get("BACKEND", "")).strip().upper(),
            language=str(data.get("LANGUAGE", "")).strip().upper(),
        )


@dataclass(frozen=True)
class Pack:
    """A challenge pack on disk.

    ``root`` is the directory holding ``metadata.json`` — the same directory
    that gets zipped and uploaded.
    """

    root: Path
    name: str
    backend: Backend
    metadata: Mapping[str, Any]
    #: Active test module resolved from ``course_toc.json``.
    active_test_index: int
    #: Reference solution overlaid for the SOLUTION fixture. Sibling of ``root``
    #: so it is never included in the uploaded zip.
    solution_dir: Optional[Path] = None

    @property
    def tests_dir(self) -> Path:
        return self.root / contract.TESTS_DIR

    @property
    def course_data_dir(self) -> Path:
        return self.root / contract.COURSE_DATA_DIR

    @property
    def source_dir(self) -> Path:
        return self.root / contract.SOURCE_DIR

    @property
    def active_test_file(self) -> Path:
        return self.tests_dir / f"test_{self.active_test_index}.py"

    @property
    def has_solution(self) -> bool:
        return self.solution_dir is not None and self.solution_dir.is_dir()

    def container_workspace(self) -> str:
        """Where the runner would mount this pack's workspace.

        Tests routinely embed assumptions about this path, so the local harness
        reports it even though it materialises the workspace elsewhere.
        """
        return contract.CONTAINER_WORKSPACE_TEMPLATE.format(
            user=contract.CONTAINER_USER,
            foldername=self.name,
        )
