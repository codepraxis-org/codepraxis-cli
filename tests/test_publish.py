"""Publishing guards.

These cover the rules that protect a candidate-facing action: a pack cannot be
published without a reference solution or a passing remote validation, and the
CLI never asserts which company owns the result.

Packs here are synthetic — see CONTRIBUTING.md on the content boundary.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codepraxis.commands import publish
from codepraxis.errors import PackError, PraxisError

TEST_MODULE = '''
class testCases:
    def __init__(self, user_wxpace) -> None:
        self.RUN = 1
        self.RunCaseInputs = ["an input"]
        self.userWxpace = user_wxpace
        self.exe = ""
        self.default_timeout_window = 5000
        self.usage = "prod"
        self.msg = ""

    def test_case_1(self, timeout_window=5000, override=1):
        self.msg = "PASS"
        return "expected", "ok"
'''


def build_pack(root: Path, name: str = "demo", with_solution: bool = True) -> Path:
    pack = root / "challenges" / name
    (pack / "source").mkdir(parents=True)
    (pack / "._tests").mkdir()
    (pack / "._course_data").mkdir()

    (pack / "metadata.json").write_text(json.dumps({"name": name}))
    (pack / "backend.conf").write_text(json.dumps({"BACKEND": "AI", "LANGUAGE": "PYTHON"}))
    (pack / "source" / "README.md").write_text("stub\n")
    (pack / "._tests" / "test_1.py").write_text(TEST_MODULE)
    (pack / "._course_data" / "feature.md").write_text("# demo\n")
    (pack / "._course_data" / "course_toc.json").write_text(
        json.dumps({"instruction_1": {"file": "feature.md", "metadata": {"STATUS": "IN_PROGRESS"}}})
    )

    if with_solution:
        solution = pack.parent / "solution"
        solution.mkdir()
        (solution / "answer.py").write_text("VALUE = 1\n")

    return pack


class FakeClient:
    """Records calls so tests can assert on the request body."""

    def __init__(self, identity: dict | None = None) -> None:
        self.identity = identity or {"company": {"name": "Acme", "id": 42}}
        self.posted: list[tuple] = []

    def get(self, path: str) -> dict:
        if path == "/me":
            return self.identity
        raise AssertionError(f"unexpected GET {path}")

    def post_json(self, path: str, payload: dict) -> dict:
        self.posted.append((path, payload))
        return {"challenge_id": 7, "challenge_version_id": 9}

    def post_bytes(self, path: str, blob: bytes) -> dict:  # pragma: no cover
        raise AssertionError("publish should not submit a bundle when reusing a run id")


class NullReporter:
    def report(self, result) -> None:
        pass


def test_refuses_without_a_selector(tmp_path: Path):
    with pytest.raises(PraxisError, match="explicit pack"):
        publish.run(root=tmp_path, selector=None, reporter=NullReporter(), client=FakeClient())


def test_refuses_a_pack_without_a_solution(tmp_path: Path):
    build_pack(tmp_path, with_solution=False)
    with pytest.raises(PraxisError, match="no solution"):
        publish.run(root=tmp_path, selector="demo", reporter=NullReporter(), client=FakeClient())


def test_unknown_pack_is_rejected(tmp_path: Path):
    build_pack(tmp_path)
    with pytest.raises(PackError):
        publish.run(root=tmp_path, selector="missing", reporter=NullReporter(), client=FakeClient())


def test_never_sends_a_company_id(tmp_path: Path):
    """Ownership is derived server-side from the API key.

    A client-supplied company id is the tenancy hole this design exists to
    avoid, so its absence is a regression test, not an implementation detail.
    """
    build_pack(tmp_path)
    client = FakeClient()

    exit_code = publish.run(
        root=tmp_path,
        selector="demo",
        reporter=NullReporter(),
        assume_yes=True,
        validation_run_id="vr_123",
        client=client,
    )

    assert exit_code == 0
    path, payload = client.posted[0]
    assert path == "/challenges"
    assert "company_id" not in payload
    assert "company" not in payload
    assert payload["validation_run_id"] == "vr_123"


def test_defaults_to_draft(tmp_path: Path):
    build_pack(tmp_path)
    client = FakeClient()

    publish.run(
        root=tmp_path,
        selector="demo",
        reporter=NullReporter(),
        assume_yes=True,
        validation_run_id="vr_1",
        client=client,
    )

    assert client.posted[0][1]["status"] == "draft"


class ValidatingClient(FakeClient):
    """Drives the full validate-then-publish path with a canned verdict."""

    def __init__(self, starter_passes: bool) -> None:
        super().__init__()
        self.starter_passes = starter_passes

    def post_bytes(self, path: str, blob: bytes) -> dict:
        assert path == "/validation-runs"
        return {"validation_run_id": "vr_remote", "status": "queued"}

    def get(self, path: str) -> dict:
        if path.startswith("/validation-runs/"):
            starter_status = "pass" if self.starter_passes else "fail"
            return {
                "status": "passed",
                "result": {
                    "fixtures": [
                        {"fixture": "solution", "cases": [{"name": "test_case_1", "status": "pass"}]},
                        {"fixture": "starter", "cases": [{"name": "test_case_1", "status": starter_status}]},
                    ]
                },
            }
        return super().get(path)


def test_validates_remotely_before_publishing(tmp_path: Path):
    build_pack(tmp_path)
    client = ValidatingClient(starter_passes=False)

    exit_code = publish.run(root=tmp_path, selector="demo", reporter=NullReporter(), assume_yes=True, client=client)

    assert exit_code == 0
    assert client.posted[0][1]["validation_run_id"] == "vr_remote"


def test_publish_blocked_when_starter_passes(tmp_path: Path):
    """A non-discriminating pack must never reach candidates."""
    build_pack(tmp_path)
    client = ValidatingClient(starter_passes=True)

    with pytest.raises(PraxisError, match="validation failed"):
        publish.run(root=tmp_path, selector="demo", reporter=NullReporter(), assume_yes=True, client=client)

    assert client.posted == []


def test_live_publishes_immediately(tmp_path: Path):
    build_pack(tmp_path)
    client = FakeClient()

    publish.run(
        root=tmp_path,
        selector="demo",
        reporter=NullReporter(),
        assume_yes=True,
        live=True,
        validation_run_id="vr_1",
        client=client,
    )

    assert client.posted[0][1]["status"] == "published"


def test_prints_container_url_when_platform_returns_one(tmp_path: Path, capsys):
    build_pack(tmp_path)

    class PreviewClient(FakeClient):
        def post_json(self, path: str, payload: dict) -> dict:
            self.posted.append((path, payload))
            return {
                "challenge_id": 7,
                "challenge_version_id": 9,
                "container_url": "https://container.example/?folder=/home/praxis/demo",
            }

    publish.run(
        root=tmp_path,
        selector="demo",
        reporter=NullReporter(),
        assume_yes=True,
        validation_run_id="vr_1",
        client=PreviewClient(),
    )

    assert "https://container.example" in capsys.readouterr().out
