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
    def __init__(self, stream: IO[str] = sys.stdout, indent: int = 2) -> None:
        self._out = stream
        self._indent = indent

    def report(self, result: RunResult) -> None:
        json.dump(self._serialize(result), self._out, indent=self._indent)
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
