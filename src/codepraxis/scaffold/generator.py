"""Generate a new pack from templates.

The generated pack is deliberately *complete and passing*: run
``codepraxis validate --local`` on it straight away and it goes green. That
gives an author a known-good starting point and proves their toolchain works
before they have written anything.

Templates ship inside the wheel and are read through ``importlib.resources`` so
this works from an installed package as well as a source checkout.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from ..domain import contract
from ..errors import PraxisError

#: metadata.json "name" becomes a directory name inside the container, so it is
#: restricted to what a shell and a filesystem both handle without quoting.
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,49}$")

KNOWN_BACKENDS = ("AI", "DSA", "EMB", "LNX")


@dataclass(frozen=True)
class ScaffoldResult:
    pack_dir: Path
    solution_dir: Path
    files: list


def normalize_name(raw: str) -> str:
    """Turn a user-supplied slug into a valid pack name."""
    name = raw.strip().lower().replace("-", "_").replace(" ", "_")
    name = re.sub(r"_+", "_", name).strip("_")
    if not _NAME_PATTERN.match(name):
        raise PraxisError(
            f"{raw!r} is not a usable pack name. Use 3-50 characters, lowercase "
            f"letters, digits and underscores, starting with a letter."
        )
    return name


def title_from(name: str) -> str:
    return name.replace("_", " ").strip().title()


def _template(filename: str) -> str:
    return (resources.files("codepraxis.scaffold") / "templates" / filename).read_text(encoding="utf-8")


def _render(filename: str, name: str, backend: str, language: str) -> str:
    return (
        _template(filename)
        .replace("__PACK_NAME__", name)
        .replace("__TITLE__", title_from(name))
        .replace("__BACKEND__", backend)
        .replace("__LANGUAGE__", language)
    )


def create(
    root: Path,
    raw_name: str,
    backend: str = "AI",
    language: str = "PYTHON",
    force: bool = False,
) -> ScaffoldResult:
    """Write a new pack under ``root`` and return what was created.

    The pack directory and its ``solution/`` sibling are laid out the way the
    tooling expects: the solution is *beside* the pack so it can never be
    packaged and shipped to a candidate.
    """
    name = normalize_name(raw_name)
    backend = backend.strip().upper()
    language = language.strip().upper()

    if backend not in KNOWN_BACKENDS:
        raise PraxisError(f"Unknown BACKEND {backend!r}. Expected one of: {', '.join(KNOWN_BACKENDS)}")

    pack_dir = (root / name).resolve()
    solution_dir = pack_dir.parent / "solution"

    if pack_dir.exists() and not force:
        raise PraxisError(f"{pack_dir} already exists. Choose another name, or pass --force.")

    written = []

    def write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)

    write(pack_dir / contract.METADATA_FILE, _render("metadata.json", name, backend, language))
    write(pack_dir / contract.BACKEND_CONF_FILE, _render("backend.conf", name, backend, language))
    write(pack_dir / contract.SOURCE_DIR / "main.py", _render("main.py", name, backend, language))
    write(pack_dir / contract.SOURCE_DIR / "README.md", _render("README.md", name, backend, language))
    write(pack_dir / contract.TESTS_DIR / "test_1.py", _render("test_1.py", name, backend, language))
    write(
        pack_dir / contract.COURSE_DATA_DIR / contract.COURSE_TOC_FILE,
        _render("course_toc.json", name, backend, language),
    )
    write(pack_dir / contract.COURSE_DATA_DIR / "feature.md", _render("feature.md", name, backend, language))

    # The reference solution overlays source/, so it mirrors those paths.
    write(solution_dir / "main.py", _render("solution.py", name, backend, language))

    return ScaffoldResult(pack_dir=pack_dir, solution_dir=solution_dir, files=written)


def describe(result: ScaffoldResult, root: Path) -> str:
    def relative(path: Path) -> str:
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)

    return "\n".join(
        [
            f"Created {relative(result.pack_dir)} ({len(result.files)} files)",
            f"  solution: {relative(result.solution_dir)}  (beside the pack — never uploaded)",
            "",
            "It already validates. Check your setup:",
            "",
            f"  codepraxis validate --local {result.pack_dir.name}",
            "",
            "Then make it your own:",
            "",
            "  ._course_data/feature.md   what the candidate reads",
            "  source/                    what they start from",
            "  ._tests/test_1.py          how it is graded",
            "  ../solution/               the reference answer",
        ]
    )
