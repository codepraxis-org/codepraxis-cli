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


def build_pack(
    root: Path,
    name: str = "demo",
    with_solution: bool = True,
    approved: bool = True,
) -> Path:
    # The wrapper layout: <question>/pack, with the solution and the plan
    # beside it at the question level.
    question = root / "challenges" / name
    pack = question / "pack"
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

    status = "approved" if approved else "draft"
    (question / "spec.md").write_text(
        f"---\nquestion: {name}\nstatus: {status}\n---\n\n# {name}\n\nWhat this tests.\n"
    )

    if with_solution:
        solution = question / "solution"
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


class TestRepublishingAnEdit:
    """Editing a pack and publishing again must update, not duplicate.

    Without a challenge_id the platform creates a new question every time, which
    is how a typo fix used to leave two copies in the catalog.
    """

    def test_challenge_id_is_sent_when_given(self, tmp_path):
        build_pack(tmp_path)
        client = FakeClient()

        publish.run(
            root=tmp_path,
            selector="demo",
            reporter=NullReporter(),
            assume_yes=True,
            validation_run_id="vr_1",
            challenge_id=64,
            client=client,
        )

        assert client.posted[0][1]["challenge_id"] == 64

    def test_no_challenge_id_means_create(self, tmp_path):
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

        assert "challenge_id" not in client.posted[0][1]

    def test_output_says_updated_when_the_platform_reused_a_question(self, tmp_path, capsys):
        build_pack(tmp_path)
        client = FakeClient()
        client.post_json = lambda path, payload: {
            "challenge_id": 64,
            "challenge_version_id": 91,
            "created": False,
        }

        publish.run(
            root=tmp_path,
            selector="demo",
            reporter=NullReporter(),
            assume_yes=True,
            validation_run_id="vr_1",
            challenge_id=64,
            client=client,
        )

        output = capsys.readouterr().out
        assert "updated" in output
        assert "published for" not in output


class TestDelete:
    class Client:
        def __init__(self, payload=None):
            self.deleted = []
            self.payload = payload or {"challenge_id": 7, "versions_removed": 2}

        def delete(self, path):
            self.deleted.append(path)
            return self.payload

    def test_deletes_after_confirmation_is_waived(self, capsys):
        from codepraxis.commands import catalog

        client = self.Client()
        assert catalog.delete_question(7, client=client, assume_yes=True) == 0
        assert client.deleted == ["/challenges/7"]
        assert "Deleted question 7" in capsys.readouterr().out

    def test_refuses_without_a_terminal_and_without_yes(self):
        from codepraxis.commands import catalog
        from codepraxis.errors import PraxisError

        client = self.Client()
        with pytest.raises(PraxisError, match="not a terminal"):
            catalog.delete_question(7, client=client)
        assert client.deleted == []


class TestPlanApproval:
    """Publishing must trace back to a plan a human accepted.

    A published question can be assigned to candidates immediately, so the gate
    is state on disk rather than a "yes" in chat: the transcript where approval
    was given is not available to a later session, another machine, or a
    colleague running the publish.
    """

    def test_an_unapproved_plan_blocks_publishing(self, tmp_path):
        build_pack(tmp_path, approved=False)
        client = FakeClient()

        with pytest.raises(PraxisError, match="has not been approved"):
            publish.run(tmp_path, "demo", reporter=NullReporter(), assume_yes=True, client=client)

    def test_a_missing_plan_blocks_publishing(self, tmp_path):
        pack = build_pack(tmp_path)
        (pack.parent / "spec.md").unlink()
        client = FakeClient()

        with pytest.raises(PraxisError, match="no spec.md"):
            publish.run(tmp_path, "demo", reporter=NullReporter(), assume_yes=True, client=client)

    def test_the_refusal_names_the_command_that_unblocks_it(self, tmp_path):
        """A gate an author cannot get past is a gate they work around."""
        build_pack(tmp_path, approved=False)

        with pytest.raises(PraxisError) as caught:
            publish.run(tmp_path, "demo", reporter=NullReporter(), assume_yes=True, client=FakeClient())

        assert "codepraxis approve demo" in str(caught.value)

    def test_approving_then_publishing_works(self, tmp_path):
        from codepraxis.commands import approve

        build_pack(tmp_path, approved=False)
        approve.run(tmp_path, "demo")

        client = FakeClient()
        exit_code = publish.run(
            tmp_path,
            "demo",
            reporter=NullReporter(),
            assume_yes=True,
            validation_run_id="vr_1",
            client=client,
        )

        assert exit_code == 0
        assert client.posted[0][0] == "/challenges"

    def test_approval_survives_a_reread(self, tmp_path):
        """Approval is on disk, so a fresh process sees it."""
        from codepraxis.commands import approve
        from codepraxis.domain import spec

        build_pack(tmp_path, approved=False)
        question = tmp_path / "challenges" / "demo"

        assert not spec.read(question).approved
        approve.run(tmp_path, "demo")
        assert spec.read(question).approved
        assert spec.read(question).approved_at

    def test_approving_preserves_the_plan_body(self, tmp_path):
        """Rewriting frontmatter must never touch what the author wrote."""
        from codepraxis.commands import approve
        from codepraxis.domain import spec

        build_pack(tmp_path, approved=False)
        question = tmp_path / "challenges" / "demo"
        (question / "spec.md").write_text(
            "---\nstatus: draft\n---\n\n# Plan\n\nSignal: can they debug a retry loop.\n"
        )

        approve.run(tmp_path, "demo")
        assert "Signal: can they debug a retry loop." in spec.read(question).body
