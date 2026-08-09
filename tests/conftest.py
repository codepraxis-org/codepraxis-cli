"""Shared fixtures.

The conformance corpus is private and lives outside this repository. Point the
suite at a checkout with ``PRAXIS_CONFORMANCE_PACKS``; without it, conformance
tests skip. See CONTRIBUTING.md.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

CORPUS_ENV = "PRAXIS_CONFORMANCE_PACKS"


@pytest.fixture(scope="session")
def corpus_root() -> Path:
    raw = os.environ.get(CORPUS_ENV)
    if not raw:
        pytest.skip(f"{CORPUS_ENV} is not set; skipping conformance against the private pack corpus")
    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        pytest.skip(f"{CORPUS_ENV}={root} is not a directory")
    return root
