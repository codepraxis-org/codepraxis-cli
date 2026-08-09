"""Machine-readable output for CI.

The shape here is the contract other tools consume, so it is written explicitly
rather than derived by reflection over the dataclasses — a field rename in the
domain layer should not silently reshape published JSON.
"""

from __future__ import annotations

import json
import sys
from typing import IO

from ..domain.results import RunResult


class JsonReporter:
    """Buffers every result and emits one document on close.

    Validating several packs used to print several top-level objects back to
    back, which no JSON parser accepts. Output is always a single object with a
    ``packs`` array, whether one pack ran or forty.
    """

    def __init__(self, stream: IO[str] = sys.stdout, indent: int = 2) -> None:
        self._out = stream
        self._indent = indent
        self._results: list = []

    def report(self, result: RunResult) -> None:
        self._results.append(result)

    def close(self) -> None:
        payload = {
            "ok": all(result.ok for result in self._results) if self._results else False,
            "packs": [self._serialize(result) for result in self._results],
        }
        json.dump(payload, self._out, indent=self._indent)
        self._out.write("\n")

    @staticmethod
    def _serialize(result: RunResult) -> dict:
        return {
            "pack": result.pack_name,
            "executor": result.executor,
            "ok": result.ok,
            "duration_ms": round(result.duration_ms, 2),
            "diagnostics": [
                {
                    "severity": diagnostic.severity.value,
                    "code": diagnostic.code,
                    "message": diagnostic.message,
                    "location": diagnostic.location,
                }
                for diagnostic in result.diagnostics
            ],
            "fixtures": [
                {
                    "fixture": run.fixture.value,
                    "passed": run.passed_count,
                    "total": len(run.cases),
                    "cases": [
                        {
                            "name": case.name,
                            "status": case.status.value,
                            "hidden": case.hidden,
                            "expected": case.expected,
                            "output": case.output,
                            "duration_ms": round(case.duration_ms, 2),
                        }
                        for case in run.cases
                    ],
                    "diagnostics": [
                        {
                            "severity": diagnostic.severity.value,
                            "code": diagnostic.code,
                            "message": diagnostic.message,
                            "location": diagnostic.location,
                        }
                        for diagnostic in run.diagnostics
                    ],
                }
                for run in result.runs
            ],
        }
