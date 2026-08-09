"""Rules over the candidate-facing brief.

``._course_data/feature.md`` is rendered in the platform's Instructions tab,
which does not render LaTeX. Maths written there reaches the candidate as raw
backslashes.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from ...domain.pack import Pack
from ...domain.results import Diagnostic, Severity

#: Delimiters and commands that will not render in the Instructions tab.
_NOTATION_PATTERNS = (
    (re.compile(r"\$\$.+?\$\$", re.DOTALL), "$$…$$ display maths"),
    (re.compile(r"(?<![\w$])\$[^\s$][^$\n]*\$(?![\w$])"), "$…$ inline maths"),
    (re.compile(r"\\\(.+?\\\)", re.DOTALL), r"\(…\) inline maths"),
    (re.compile(r"\\\[.+?\\\]", re.DOTALL), r"\[…\] display maths"),
    (re.compile(r"\\(?:frac|mathbf|sum|prod|sqrt|alpha|beta|theta|sigma)\b"), "TeX commands"),
)


class InstructionsNotationRule:
    """feature.md must not rely on LaTeX."""

    code = "instructions.notation"

    def check(self, pack: Pack) -> Iterable[Diagnostic]:
        feature = pack.course_data_dir / "feature.md"
        if not feature.is_file():
            return [
                Diagnostic(
                    Severity.ERROR,
                    "instructions.missing",
                    "._course_data/feature.md is missing; the Instructions tab would be empty.",
                    str(feature),
                )
            ]

        try:
            text = feature.read_text(encoding="utf-8")
        except OSError as exc:
            return [
                Diagnostic(Severity.WARNING, self.code, f"Could not read feature.md: {exc}", str(feature))
            ]

        findings: list[Diagnostic] = []
        for pattern, description in _NOTATION_PATTERNS:
            match = pattern.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                findings.append(
                    Diagnostic(
                        Severity.WARNING,
                        self.code,
                        (
                            f"feature.md uses {description}, which the Instructions tab does not render. "
                            f"Put equations in source/README.md and keep the brief in prose."
                        ),
                        f"{feature}:{line}",
                    )
                )
        return findings
