"""Stage-by-stage output, so whoever runs a command always knows where it is.

Every step prints when it starts and how it ended:

    → Opening the question in a container…
      … still opening (30s): cold starts take up to 3 minutes
    ✓ Opening the question in a container (41s)

A step that waits prints a line every few seconds with what it is waiting for
and the latest thing it saw, so a slow step never looks like a hung one.
"""

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Callable

TICK_SECONDS = 10


def line(text: str = "") -> None:
    print(text, flush=True)


def done(text: str) -> None:
    line(f"✓ {text}")


def failed(text: str) -> None:
    line(f"✗ {text}")


def next_step(text: str) -> None:
    line(f"Next: {text}")


class Step:
    def __init__(self, title: str) -> None:
        self.title = title
        self.started = time.time()
        self.outcome: str | None = None

    @property
    def elapsed(self) -> float:
        return time.time() - self.started

    def note(self, text: str) -> None:
        line(f"  {text}")

    def result(self, text: str) -> None:
        """What to say on success instead of the title, e.g. "Draft updated"."""
        self.outcome = text


@contextmanager
def step(title: str, waiting: Callable[[float], str] | None = None) -> Iterator[Step]:
    """A stage of a command.

    ``waiting`` is for a stage that blocks on the network: it is called every
    few seconds with the elapsed time and returns what to print, e.g. the
    latest setup.sh line.
    """
    current = Step(title)
    line(f"→ {title}…")
    stop = threading.Event()
    ticker = None
    if waiting is not None:
        def tick() -> None:
            while not stop.wait(TICK_SECONDS):
                try:
                    detail = waiting(current.elapsed)
                except Exception:  # noqa: BLE001 - a progress line must never break the step
                    detail = ""
                line(f"  … {int(current.elapsed)}s{': ' + detail if detail else ''}")
        ticker = threading.Thread(target=tick, daemon=True)
        ticker.start()
    try:
        yield current
    except BaseException as exc:
        stop.set()
        failed(f"{title} ({current.elapsed:.0f}s): {_first_line(exc)}")
        raise
    finally:
        stop.set()
        if ticker is not None:
            ticker.join(timeout=1)
    done(f"{current.outcome or title} ({current.elapsed:.1f}s)")


def _first_line(exc: BaseException) -> str:
    text = str(exc) or type(exc).__name__
    return text.splitlines()[0]


def warn(text: str) -> None:
    print(f"! {text}", file=sys.stdout, flush=True)
