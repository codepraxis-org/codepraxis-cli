"""How results are classified and reported.

Two behaviours worth pinning down:

* A case that fails only because this machine has no model endpoint is
  *unverifiable*, not failed — reporting it as a failure sends authors chasing a
  bug that does not exist off-platform.
* Once an endpoint is configured, that leniency stops. A failure is a failure.

Fixtures are synthetic — see CONTRIBUTING.md on the content boundary.
"""

from __future__ import annotations

import io
import json

from codepraxis.domain.results import (
    CaseResult,
    CaseStatus,
    Fixture,
    FixtureRun,
    RunResult,
)
from codepraxis.execution.local import backends
from codepraxis.execution.local.executor import LocalExecutor
from codepraxis.reporting.json_reporter import JsonReporter


def case(status, output=""):
    return {"status": status, "output": output, "name": "test_case_1"}


class TestClassification:
    def test_llm_connection_failure_is_unverifiable(self):
        adapter = backends.adapter_for("AI")
        status = LocalExecutor._classify(
            case("fail", "OPENAI_API_KEY must be set for the local LiteLLM proxy"),
            adapter,
            llm_configured=False,
        )
        assert status is CaseStatus.UNVERIFIABLE

    def test_ordinary_failure_stays_a_failure(self):
        adapter = backends.adapter_for("AI")
        status = LocalExecutor._classify(
            case("fail", "Expected 4 but got 5"), adapter, llm_configured=False
        )
        assert status is CaseStatus.FAIL

    def test_no_leniency_once_an_endpoint_is_configured(self):
        """With a key supplied, an LLM failure is a real failure."""
        adapter = backends.adapter_for("AI")
        status = LocalExecutor._classify(
            case("fail", "LLM request failed (500)"), adapter, llm_configured=True
        )
        assert status is CaseStatus.FAIL

    def test_passing_cases_are_never_demoted(self):
        adapter = backends.adapter_for("AI")
        status = LocalExecutor._classify(
            case("pass", "localhost:1010"), adapter, llm_configured=False
        )
        assert status is CaseStatus.PASS

    def test_backends_without_markers_are_untouched(self):
        adapter = backends.adapter_for("DSA")
        status = LocalExecutor._classify(
            case("fail", "connection refused"), adapter, llm_configured=False
        )
        assert status is CaseStatus.FAIL


def build_result(statuses, pack="demo"):
    return RunResult(
        pack_name=pack,
        executor="local",
        runs=(
            FixtureRun(
                fixture=Fixture.SOLUTION,
                cases=tuple(CaseResult(name=f"test_case_{i}", status=s) for i, s in enumerate(statuses)),
            ),
        ),
    )


class TestInconclusive:
    def test_a_run_with_unverifiable_cases_is_inconclusive(self):
        result = build_result([CaseStatus.PASS, CaseStatus.UNVERIFIABLE])
        assert result.inconclusive is True

    def test_a_clean_run_is_not_inconclusive(self):
        result = build_result([CaseStatus.PASS, CaseStatus.FAIL])
        assert result.inconclusive is False


class TestJsonReporter:
    def test_multiple_packs_emit_one_parseable_document(self):
        """Concatenated top-level objects are not valid JSON; CI must be able to parse this."""
        stream = io.StringIO()
        reporter = JsonReporter(stream=stream)

        reporter.report(build_result([CaseStatus.PASS], pack="one"))
        reporter.report(build_result([CaseStatus.FAIL], pack="two"))
        reporter.close()

        payload = json.loads(stream.getvalue())
        assert [p["pack"] for p in payload["packs"]] == ["one", "two"]

    def test_top_level_ok_requires_every_pack_to_pass(self):
        stream = io.StringIO()
        reporter = JsonReporter(stream=stream)
        reporter.report(build_result([CaseStatus.PASS], pack="one"))
        reporter.report(build_result([CaseStatus.FAIL], pack="two"))
        reporter.close()

        assert json.loads(stream.getvalue())["ok"] is False

    def test_nothing_is_written_before_close(self):
        stream = io.StringIO()
        reporter = JsonReporter(stream=stream)
        reporter.report(build_result([CaseStatus.PASS]))

        assert stream.getvalue() == ""


class TestResponseUnwrapping:
    """The platform wraps every response in {success, message, data}."""

    def test_enveloped_responses_are_unwrapped(self):
        from codepraxis.execution.remote.client import _unwrap

        payload = {"success": True, "message": "ok", "data": {"validation_run_id": "vr_1"}}
        assert _unwrap(payload) == {"validation_run_id": "vr_1"}

    def test_null_data_becomes_an_empty_mapping(self):
        from codepraxis.execution.remote.client import _unwrap

        assert _unwrap({"success": True, "message": "ok", "data": None}) == {}

    def test_bare_responses_pass_through(self):
        """Stays correct if an endpoint ever returns an unenveloped object."""
        from codepraxis.execution.remote.client import _unwrap

        assert _unwrap({"status": "passed"}) == {"status": "passed"}


class TestRemoteDefaults:
    def test_default_api_url_includes_the_public_prefix(self):
        """The backend sits behind the web app, so the prefix is part of the base.

        Shipping a bare host meant `codepraxis --login` failed on a TLS error
        before it could reach anything.
        """
        from codepraxis.execution.remote.config import DEFAULT_API_URL

        assert DEFAULT_API_URL.startswith("https://")
        assert DEFAULT_API_URL.endswith("/api/public")
        assert not DEFAULT_API_URL.endswith("/")


class TestStaticOnlyVerdict:
    """A lint result has no fixtures; the solution/starter rules must not apply."""

    def _render(self, diagnostics):
        import io

        from codepraxis.domain.results import RunResult
        from codepraxis.reporting.human import HumanReporter

        stream = io.StringIO()
        reporter = HumanReporter(stream=stream)
        reporter.report(RunResult(pack_name="demo", executor="lint", diagnostics=tuple(diagnostics)))
        reporter.close()
        return stream.getvalue()

    def test_a_clean_lint_reports_ok_not_failed(self):
        assert "OK" in self._render([])
        assert "FAILED" not in self._render([])

    def test_a_lint_with_errors_reports_failed(self):
        from codepraxis.domain.results import Diagnostic, Severity

        output = self._render([Diagnostic(Severity.ERROR, "x.y", "broken")])
        assert "FAILED" in output

    def test_warnings_alone_do_not_fail(self):
        from codepraxis.domain.results import Diagnostic, Severity

        assert "OK" in self._render([Diagnostic(Severity.WARNING, "x.y", "cosmetic")])


class TestOverrideModes:
    """koro has four modes; this tier can only judge override 1.

    Applying override-1 rules to the others reads `self.msg`, finds it unset,
    and reports a confident FAIL for a case that may be perfectly correct —
    exactly the "chasing a bug that does not exist" problem above.
    """

    @staticmethod
    def _entry(override):
        return {"name": "test_case_1", "func": lambda: None, "timeout_window": None, "override": override}

    def test_override_1_is_executed(self):
        from codepraxis.execution.local.worker import _run_case

        class Instance:
            msg = ""

        instance = Instance()

        def passing_case():
            # _run_case clears msg before running, so the case must set it.
            instance.msg = "PASS"
            return "expected", "output"

        entry = self._entry(1)
        entry["func"] = passing_case
        assert _run_case(instance, entry, 1000)["status"] == "pass"

    def test_other_modes_are_unverifiable_not_failed(self):
        from codepraxis.execution.local.worker import _run_case

        for override in (0, 2, None):
            result = _run_case(object(), self._entry(override), 1000)
            assert result["status"] == "unverifiable", override
            assert "--remote" in result["output"], override

    def test_default_mode_names_itself_clearly(self):
        """`override=None` means no override parameter, not "override None"."""
        from codepraxis.execution.local.worker import _run_case

        result = _run_case(object(), self._entry(None), 1000)
        assert "default" in result["output"]

    def test_unverifiable_survives_classification(self):
        adapter = backends.adapter_for("AI")
        status = LocalExecutor._classify(
            case("unverifiable", "override 0 is judged by the runner"),
            adapter,
            llm_configured=True,
        )
        assert status is CaseStatus.UNVERIFIABLE


class TestAttemptFixture:
    """ATTEMPT measures how far someone got; it is not a correctness check.

    STARTER must fail and SOLUTION must pass — those prove the pack is sound.
    An attempt scoring 1/7 is a *good* result: it means the question cannot be
    answered from the brief alone. So it must never colour the verdict.
    """

    @staticmethod
    def _run(fixture, passed, total):
        from codepraxis.domain.results import CaseResult, CaseStatus, FixtureRun

        cases = [
            CaseResult(
                name=f"test_case_{n}",
                status=CaseStatus.PASS if n <= passed else CaseStatus.FAIL,
            )
            for n in range(1, total + 1)
        ]
        return FixtureRun(fixture=fixture, cases=tuple(cases))

    def test_a_partial_attempt_does_not_make_the_pack_unsound(self):
        result = RunResult(
            pack_name="demo",
            executor="local",
            runs=(
                self._run(Fixture.SOLUTION, 2, 2),
                self._run(Fixture.STARTER, 0, 2),
                self._run(Fixture.ATTEMPT, 1, 2),
            ),
        )
        assert result.ok

    def test_an_attempt_passing_everything_still_does_not_fail_the_pack(self):
        """It means the question is weak, which evaluate reports — but the
        pack itself is still mechanically sound, and validate says so."""
        result = RunResult(
            pack_name="demo",
            executor="local",
            runs=(
                self._run(Fixture.SOLUTION, 2, 2),
                self._run(Fixture.STARTER, 0, 2),
                self._run(Fixture.ATTEMPT, 2, 2),
            ),
        )
        assert result.ok

    def test_attempt_only_runs_report_a_measurement(self):
        from codepraxis.reporting.human import HumanReporter

        buffer = io.StringIO()
        HumanReporter(stream=buffer).report(
            RunResult(
                pack_name="demo",
                executor="local",
                runs=(self._run(Fixture.ATTEMPT, 1, 3),),
            )
        )
        output = buffer.getvalue()
        assert "MEASURED" in output
        assert "1/3" in output
        assert "PASSED" not in output
        assert "FAILED" not in output
