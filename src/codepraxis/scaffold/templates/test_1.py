"""Grader for __TITLE__.

The runner imports this file and instantiates ``testCases`` with the candidate's
workspace path. A case passes if and only if ``self.msg == "PASS"`` when the
method returns — the return value is what the candidate panel displays, not the
verdict.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class testCases:
    def __init__(self, user_wxpace) -> None:
        # Exactly one argument after self: the runner calls
        # testCases(workspace_path). A second argument breaks the pack.
        self.RUN = 2                      # cases shown to the candidate
        self.RunCaseInputs = [            # one entry per visible case
            "1 2 3",
            "-5 5",
        ]
        self.userWxpace = user_wxpace
        self.exe = ""
        self.default_timeout_window = 20000   # MILLISECONDS
        self.usage = "prod"
        self.sim = "qemu"
        self.msg = ""

    # -- helpers -----------------------------------------------------------

    def _run(self, arguments: list[str]) -> str:
        main = Path(self.userWxpace).resolve() / "main.py"
        if not main.exists():
            raise AssertionError("main.py not found in the workspace")

        result = subprocess.run(
            [sys.executable, str(main), *arguments],
            cwd=str(main.parent),
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            raise AssertionError(f"main.py exited {result.returncode}: {result.stderr[-300:]}")
        return result.stdout.strip()

    # -- cases -------------------------------------------------------------
    # Name them test_case_1, test_case_2, … Unpadded integers only: ordering
    # uses the first number in the name, so test_case_01 is ambiguous.

    def test_case_1(self, timeout_window=20000, override=1):
        expected = "1 2 3 sums to 6"
        try:
            output = self._run(["1", "2", "3"])
            assert output == "6", f"expected 6, got {output!r}"
            self.msg = "PASS"
            return expected, output
        except Exception as exc:  # noqa: BLE001 - the message is shown to the candidate
            self.msg = f"FAIL: {exc}"
            return expected, self.msg

    def test_case_2(self, timeout_window=20000, override=1):
        expected = "-5 5 sums to 0"
        try:
            output = self._run(["-5", "5"])
            assert output == "0", f"expected 0, got {output!r}"
            self.msg = "PASS"
            return expected, output
        except Exception as exc:  # noqa: BLE001
            self.msg = f"FAIL: {exc}"
            return expected, self.msg
