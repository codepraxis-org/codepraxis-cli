"""Rule registry and the static pass.

Adding a rule means writing a class and registering it here — no dispatcher to
edit, no existing file to touch beyond the one-line registration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..domain.results import Diagnostic, Severity
from .rule import Rule
from .rules.environment import SubprocessInterpreterRule
from .rules.hygiene import ForbiddenFilesRule, QuestionLayoutRule, SolutionInsidePackRule
from .rules.instructions import InstructionsNotationRule
from .rules.testcases import ConstructorArityRule, TestCaseNamingRule

#: Order is the order diagnostics are reported in. Structural problems come
#: first because they explain the ones that follow.
_RULES: list[Rule] = [
    ConstructorArityRule(),
    TestCaseNamingRule(),
    QuestionLayoutRule(),
    SolutionInsidePackRule(),
    ForbiddenFilesRule(),
    InstructionsNotationRule(),
    SubprocessInterpreterRule(),
]

if TYPE_CHECKING:  # pragma: no cover
    from ..domain.pack import Pack


def all_rules() -> list[Rule]:
    return list(_RULES)


def register(rule: Rule) -> None:
    """Add a rule. Replaces any existing rule with the same code."""
    global _RULES
    _RULES = [existing for existing in _RULES if existing.code != rule.code] + [rule]


def lint(pack: Pack) -> list[Diagnostic]:
    """Run every rule over ``pack``.

    A rule that raises is reported rather than allowed to abort the pass — one
    broken rule must not hide every other finding.
    """
    findings: list[Diagnostic] = []
    for rule in _RULES:
        try:
            findings.extend(rule.check(pack))
        except Exception as exc:  # noqa: BLE001 - a bad rule must not mask the rest
            findings.append(
                Diagnostic(
                    severity=Severity.WARNING,
                    code=f"{rule.code}.crashed",
                    message=f"Rule {rule.code} could not run: {exc}",
                )
            )
    return findings


def has_errors(findings: list[Diagnostic]) -> bool:
    return any(finding.severity is Severity.ERROR for finding in findings)
