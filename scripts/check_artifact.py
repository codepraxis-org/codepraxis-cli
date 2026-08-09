#!/usr/bin/env python3
"""Fail the release if a built artifact contains anything it should not.

This package is published publicly, so the content boundary in CONTRIBUTING.md
has to be machine-enforced. Documentation does not survive a rushed release.

Checks every wheel and sdist in ``dist/`` for:
  - challenge pack structure (``._tests/``, ``._course_data/``, ``metadata.json``)
  - reference solutions
  - credential-shaped strings
  - the runner-image internals that must never leave the platform

Usage: python scripts/check_artifact.py [dist_dir]
"""

from __future__ import annotations

import re
import sys
import tarfile
import zipfile
from collections.abc import Iterable
from pathlib import Path

#: Path fragments that indicate challenge content was swept into the build.
FORBIDDEN_PATH_PATTERNS = (
    re.compile(r"(^|/)\._tests(/|$)"),
    re.compile(r"(^|/)\._course_data(/|$)"),
    re.compile(r"(^|/)solution(/|$)"),
    re.compile(r"(^|/)metadata\.json$"),
    re.compile(r"(^|/)backend\.conf$"),
    re.compile(r"(^|/)question[-_]bank(/|$)"),
    re.compile(r"(^|/)\.env$"),
    re.compile(r"(^|/)containerconfig\.json$"),
)

#: Substrings that must not appear in any shipped file's contents. Kept narrow
#: so ordinary prose about the platform does not trip the check.
FORBIDDEN_CONTENT = (
    "DefaultEndpointsProtocol=",  # Azure storage connection string
    "AccountKey=",
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
)

#: Only inspect the contents of text-ish files; wheels contain no binaries today
#: but a future dependency might.
TEXT_SUFFIXES = frozenset({".py", ".md", ".txt", ".toml", ".cfg", ".json", ".yaml", ".yml", ""})


def _iter_members(archive: Path) -> Iterable[tuple[str, bytes]]:
    if archive.suffix == ".whl":
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                if info.is_dir():
                    continue
                yield info.filename, bundle.read(info)
    elif archive.name.endswith(".tar.gz"):
        with tarfile.open(archive, "r:gz") as bundle:
            for member in bundle.getmembers():
                if not member.isfile():
                    continue
                handle = bundle.extractfile(member)
                yield member.name, handle.read() if handle else b""


def check(archive: Path) -> list[str]:
    problems: list[str] = []

    for name, payload in _iter_members(archive):
        # Strip the sdist's top-level "codepraxis-1.2.3/" prefix so patterns
        # match the same way for wheels and sdists.
        relative = name.split("/", 1)[1] if archive.name.endswith(".tar.gz") and "/" in name else name

        for pattern in FORBIDDEN_PATH_PATTERNS:
            if pattern.search(relative):
                problems.append(f"{archive.name}: forbidden path {relative!r} (matched {pattern.pattern})")

        if Path(relative).suffix not in TEXT_SUFFIXES:
            continue
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for needle in FORBIDDEN_CONTENT:
            if needle in text:
                problems.append(f"{archive.name}: {relative} contains a forbidden string ({needle!r})")

    return problems


def main(argv: list[str]) -> int:
    dist = Path(argv[1] if len(argv) > 1 else "dist")
    archives = sorted(list(dist.glob("*.whl")) + list(dist.glob("*.tar.gz")))

    if not archives:
        print(f"error: no artifacts found in {dist}/ — run `python -m build` first", file=sys.stderr)
        return 2

    problems: list[str] = []
    for archive in archives:
        problems.extend(check(archive))

    if problems:
        print("Artifact check FAILED:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(f"Artifact check passed for {len(archives)} artifact(s):")
    for archive in archives:
        print(f"  {archive.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
