"""Active-instruction resolution must match the runner's precedence exactly.

Fixtures here are synthetic — see CONTRIBUTING.md on the content boundary.
"""

from __future__ import annotations

import pytest

from praxis.errors import PackError
from praxis.packio.toc import resolve_active_index


def toc(*entries):
    """Build a course_toc mapping from (index, status) pairs, order preserved."""
    return {f"instruction_{index}": {"file": "feature.md", "metadata": {"STATUS": status}} for index, status in entries}


def test_prefers_in_progress():
    assert resolve_active_index(toc((1, "DONE"), (2, "IN_PROGRESS"), (3, "FAIL"))) == 2


def test_in_progress_wins_even_when_later_than_fail():
    # The runner scans for IN_PROGRESS across the whole file before considering
    # FAIL, so position does not override status precedence.
    assert resolve_active_index(toc((1, "FAIL"), (2, "IN_PROGRESS"))) == 2


def test_falls_back_to_fail():
    assert resolve_active_index(toc((1, "DONE"), (2, "FAIL"), (3, "DONE"))) == 2


def test_falls_back_to_last_key_when_no_status_matches():
    assert resolve_active_index(toc((1, "DONE"), (2, "DONE"), (7, "DONE"))) == 7


def test_single_instruction_in_progress():
    assert resolve_active_index(toc((1, "IN_PROGRESS"))) == 1


def test_empty_toc_is_rejected():
    with pytest.raises(PackError):
        resolve_active_index({})


def test_malformed_key_without_numeric_suffix_is_rejected():
    with pytest.raises(PackError):
        resolve_active_index({"instruction_x": {"metadata": {"STATUS": "DONE"}}})


def test_entry_without_metadata_is_tolerated():
    # A malformed entry should not crash resolution; the last-key fallback applies.
    assert resolve_active_index({"instruction_1": {}, "instruction_4": {}}) == 4
