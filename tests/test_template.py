"""Assessment templates: refs, the body POST /templates takes, push, pull and the library."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codepraxis import cli, platform, template
from codepraxis.errors import PraxisError
from codepraxis.question import Question

CHALLENGES = [
    {"challenge_id": 51, "challenge_name": "Build an agent loop", "status": "published", "max_time": 60,
     "categories": ["ai_eng"], "description": "Tools and memory.", "tech_stack": ["Python"]},
    {"challenge_id": 52, "challenge_name": "Rerun-safe invoice load", "status": "draft", "max_time": 40,
     "categories": ["oracle-ebs"], "description": "PL/SQL interface."},
    {"challenge_id": 53, "challenge_name": "Reconcile two ledgers", "status": "published", "max_time": 45,
     "categories": ["oracle-ebs"], "description": "SQL."},
    {"challenge_id": 27, "challenge_name": "Old refactor", "status": "archived", "max_time": 30, "categories": []},
]
INTERVIEW = [
    {"id": 7, "name": "Agent evals", "status": "ready", "duration": 15, "categories": ["ai_eng"],
     "description": "Evaluating an agent.", "topics": ["evals"], "is_platform": True},
    {"id": 8, "name": "RAG in production", "status": "ready", "duration": 12, "categories": ["ai_eng"]},
    {"id": 9, "name": "Prompt caching", "status": "draft", "duration": 18, "categories": ["ai_eng"]},
    {"id": 10, "name": "Old question", "status": "retired", "duration": 10, "categories": []},
    {"id": 6, "name": "Quick check", "status": "ready", "duration": 5, "categories": []},
]
BANKS = [
    {"bank_id": 11, "name": "MCP servers", "category": "ai_eng", "question_count": 30},
    {"bank_id": 12, "name": "React effects", "category": "frontend", "question_count": 30},
]
CATEGORIES = [{"slug": "ai_eng", "name": "AI Engineer"}, {"slug": "oracle-ebs", "name": "Oracle EBS"}]


class FakeBackend:
    """The platform's library and template API in memory.

    Saving a draft again replaces it under a new id (same lineage and version);
    saving a published template publishes its next version.
    """

    def __init__(self):
        self.templates: dict[int, dict] = {}
        self.calls: list[tuple[str, object]] = []
        self.next_id = 200

    def get(self, path):
        self.calls.append(("GET", path))
        if path.startswith("/challenges?scope=library"):
            return {"challenges": CHALLENGES}
        if path.startswith("/interview-questions"):
            # Retired questions are listed only when asked for, as on the platform.
            wanted = path.split("status=")[1] if "status=" in path else None
            return {"questions": [q for q in INTERVIEW if (q["status"] == wanted if wanted
                                                            else q["status"] != "retired")]}
        if path == "/question-banks":
            return {"banks": BANKS}
        if path == "/categories":
            return {"categories": CATEGORIES}
        template_id = int(path.rsplit("/", 1)[1])
        if template_id not in self.templates:
            raise platform.NotFound("Template not found", 404)
        return self.templates[template_id]

    def post_json(self, path, body, timeout=60):
        self.calls.append(("POST", path, body))
        new_id, self.next_id = self.next_id, self.next_id + 1
        if "source_template_id=" in path:
            source = self.templates[int(path.split("source_template_id=")[1])]
            draft = source["status"] == "draft"
            lineage, version = source["lineage_id"], source["version"] + (0 if draft else 1)
            status = "draft" if draft else "active"
            if draft:
                del self.templates[source["template_id"]]
        else:
            lineage, version, status = new_id, 1, "draft" if "status=draft" in path else "active"
        interview = body.get("ai_interview") or {}
        self.templates[new_id] = {
            "template_id": new_id, "name": body["name"], "description": body.get("description"),
            "status": status, "version": version, "lineage_id": lineage, "company_id": None,
            "category": {"category_id": 1, "slug": body["category"], "name": "x"} if body.get("category") else None,
            "proctoring": body["proctoring"], "rules": {"ai_assistant_enabled": body["rules"]["ai_assistant_enabled"],
                                                         "total_time": None},
            "evaluation_type": body["evaluation_type"],
            "ai_interview": interview, "mcq": body.get("mcq") or {}, "code_review": body.get("code_review") or {},
            "assessment_coding_challenge_ids": body.get("coding_challenge_ids", []),
            "assessment_coding_question_times": body.get("coding_question_times", []),
            "coding_pools": body.get("coding_pools", []),
        }
        return self.templates[new_id]


def _library():
    return template.fetch_library(FakeBackend(), retired=True)


def _project(tmp_path: Path) -> Path:
    """A project with one pushed coding question, one pushed interview question,
    one pushed bank, and one coding question never pushed."""
    pushed = tmp_path / "challenges" / "agent_loop"
    (pushed / "pack").mkdir(parents=True)
    (pushed / "pack" / "publish.json").write_text(json.dumps({"challenge_id": 51}))
    fresh = tmp_path / "challenges" / "brand_new"
    (fresh / "pack").mkdir(parents=True)
    rag = tmp_path / "challenges" / "rag"
    rag.mkdir(parents=True)
    (rag / "question.json").write_text(json.dumps({"id": 8, "name": "RAG"}))
    bank = tmp_path / "mcq" / "mcp"
    bank.mkdir(parents=True)
    (bank / "bank.json").write_text("{}")
    (bank / ".codepraxis.json").write_text(json.dumps({"bank_id": 11}))
    return tmp_path


def _template(**changes):
    data = {
        "name": "AI Engineer",
        "description": "Agents in production.",
        "category": "ai_eng",
        "proctoring": {"webcam_proctoring": True, "screen_recording": True, "identity_photo": False},
        "ai_assistant": True,
        "coding": {"questions": [{"ref": "agent_loop", "minutes": 50}],
                   "pools": [{"refs": [52, 53], "pick": 1, "minutes": 40}]},
        "code_review": {"minutes": 10},
        "interview": {"questions": [7, [8, 9]]},
        "mcq": {"banks": ["mcp", 12], "questions": 10, "minutes": 12},
    }
    data.update(changes)
    return data


def _template_dir(root: Path, data=None) -> Path:
    folder = root / "templates" / "ai_engineer"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "template.json").write_text(json.dumps(data if data is not None else _template()))
    return folder


class TestFindingATemplate:
    def test_a_template_json_makes_it_a_template_found_under_templates(self, tmp_path):
        _template_dir(tmp_path)
        q = Question.find("ai_engineer", cwd=tmp_path)
        assert q.kind == "template"

    def test_container_commands_say_a_template_has_no_container(self, tmp_path):
        with pytest.raises(PraxisError, match="A template has no container"):
            Question(_template_dir(tmp_path)).require_coding("launch")


class TestRefs:
    def test_an_integer_is_a_platform_id(self, tmp_path):
        assert template.resolve(51, "coding", tmp_path).id == 51

    def test_a_local_folder_gives_the_id_it_was_pushed_under(self, tmp_path):
        root = _project(tmp_path)
        assert template.resolve("agent_loop", "coding", root).id == 51
        assert template.resolve("challenges/rag", "interview", root).id == 8
        ref = template.resolve("mcp", "mcq", root)
        assert (ref.id, ref.local, ref.label) == (11, "mcp", "11 (mcp)")

    def test_a_folder_not_pushed_yet_says_to_push_it(self, tmp_path):
        with pytest.raises(PraxisError, match="'brand_new' is not pushed yet .*`codepraxis push brand_new`"):
            template.resolve("brand_new", "coding", _project(tmp_path))

    def test_a_folder_of_the_wrong_kind_is_named(self, tmp_path):
        with pytest.raises(PraxisError, match="'rag' is an interview question, not a coding question"):
            template.resolve("rag", "coding", _project(tmp_path))

    def test_a_missing_folder_is_named(self, tmp_path):
        with pytest.raises(PraxisError, match="No local question 'ghost'"):
            template.resolve("ghost", "coding", _project(tmp_path))


class TestTheBody:
    def test_every_round_becomes_what_post_templates_takes(self, tmp_path):
        report = template.check(_template(), _project(tmp_path), _library())
        assert report.errors == [] and report.warnings == []
        body = report.body
        assert body["name"] == "AI Engineer" and body["category"] == "ai_eng"
        assert body["coding_challenge_ids"] == [51] and body["coding_question_times"] == [50]
        assert body["coding_pools"] == [{"challenge_ids": [52, 53], "pick_count": 1, "time_limit": 40}]
        assert body["code_review"] == {"time_limit": 10}
        assert body["rules"] == {"ai_assistant_enabled": True}
        assert body["proctoring"] == {"webcam_proctoring": True, "screen_recording": True, "identity_photo": False}
        assert body["evaluation_type"] == "ai_interview"
        # A group lasts as long as its longest question: 15 + max(12, 18).
        assert body["ai_interview"] == {"total_minutes": 33, "groups": [{"question_ids": [7]},
                                                                       {"question_ids": [8, 9]}],
                                        "question_ids": [7, 8]}
        assert body["mcq"] == {"question_bank_ids": [11, 12], "question_count": 10, "time_limit": 12}
        assert report.minutes == {"coding": 90, "code_review": 10, "interview": 33, "mcq": 12}
        assert report.total == 145

    def test_drafts_are_listed_but_allowed(self, tmp_path):
        report = template.check(_template(), _project(tmp_path), _library())
        assert report.ok
        assert [(d.round, d.ref.id) for d in report.drafts] == [("coding", 52), ("interview", 9)]

    def test_a_published_template_may_not_take_drafts(self, tmp_path):
        report = template.check(_template(), _project(tmp_path), _library(), published=True)
        assert len(report.errors) == 1
        assert "This template is published" in report.errors[0]
        assert "coding 52 'Rerun-safe invoice load', interview 9 'Prompt caching'" in report.errors[0]

    def test_coding_minutes_default_to_the_questions_own(self, tmp_path):
        data = _template(coding={"questions": [{"ref": 53}]})
        report = template.check(data, _project(tmp_path), _library())
        assert report.body["coding_question_times"] == [45] and report.minutes["coding"] == 45

    def test_no_interview_is_a_standard_template(self, tmp_path):
        report = template.check(_template(interview=None, mcq=None), _project(tmp_path), _library())
        assert report.ok
        assert report.body["evaluation_type"] == "standard"
        assert "ai_interview" not in report.body and "mcq" not in report.body

    def test_code_review_needs_a_coding_round(self, tmp_path):
        report = template.check(_template(coding=None), _project(tmp_path), _library())
        assert report.errors == ["code_review needs a coding round: it asks about the code the candidate submitted."]
        assert "code_review" not in report.body and "coding_challenge_ids" not in report.body

    @pytest.mark.parametrize("change, message", [
        ({"coding": {"pools": [{"refs": [52], "pick": 1, "minutes": 40}]}}, "a pool needs at least 2 alternatives"),
        ({"coding": {"pools": [{"refs": [52, 53], "pick": 3, "minutes": 40}]}}, "pick must be 1 to the number"),
        ({"coding": {"questions": [{"ref": 999}]}}, "coding question 999 is not in the library"),
        ({"coding": {"questions": [{"ref": 51}, {"ref": "agent_loop"}]}}, "coding question 51 is already"),
        ({"interview": {"questions": [7, 7]}}, "interview question 7 is already"),
        ({"interview": {"questions": [10]}}, "interview question 10 is retired"),
        ({"coding": {"questions": [{"ref": 27}]}}, "coding question 27 is archived"),
        ({"interview": {"questions": [6]}}, "adds up to 5 minutes; it must be 10 to 90"),
        ({"mcq": {"banks": [11], "questions": 60, "minutes": 12}}, "mcq questions must be 1 to 50"),
        ({"mcq": {"banks": [11], "questions": 10}}, "mcq minutes must be 1 to 180"),
        ({"mcq": {"banks": [13], "questions": 10, "minutes": 5}}, "MCQ bank 13 is not in the library"),
        ({"category": "nope"}, "Unknown category 'nope'"),
        ({"name": ""}, "The template needs a name"),
    ])
    def test_errors(self, tmp_path, change, message):
        cats = {c["slug"] for c in CATEGORIES}
        report = template.check(_template(**change), _project(tmp_path), _library(), categories=cats)
        assert any(message in e for e in report.errors), report.errors

    def test_no_rounds_is_an_error(self, tmp_path):
        report = template.check(_template(coding=None, code_review=None, interview=None, mcq=None),
                                _project(tmp_path), _library())
        assert report.errors == ["The template has no rounds: add coding, interview or mcq."]

    def test_an_unpushed_local_ref_is_an_error_with_its_place(self, tmp_path):
        data = _template(coding={"questions": [{"ref": "brand_new", "minutes": 30}]})
        report = template.check(data, _project(tmp_path), _library())
        assert report.errors[0].startswith("coding question 1: 'brand_new' is not pushed yet")


class TestPushAndPull:
    def test_first_push_saves_a_draft_and_a_repush_replaces_it(self, tmp_path, capsys, monkeypatch):
        monkeypatch.delenv(platform.ENV_API_URL, raising=False)
        root = _project(tmp_path)
        q = Question(_template_dir(root))
        backend = FakeBackend()
        result = template.push(q, backend)
        posts = [c for c in backend.calls if c[0] == "POST"]
        assert [c[1] for c in posts] == ["/templates?status=draft"]
        assert posts[0][2]["coding_challenge_ids"] == [51]
        assert q.state() == {"template_id": 200, "version": 1, "status": "draft", "lineage_id": 200}
        out = capsys.readouterr().out
        assert "Saved template 200 as a draft (version 1)" in out
        assert "https://www.codepraxis.co/company/templates/200" in out
        assert "Publish it in the dashboard once its questions are published." in out
        assert result["url"].endswith("/company/templates/200")

        # Saving a draft again replaces it: a new id, the same lineage and version.
        template.push(q, backend)
        assert backend.calls[-1][1] == "/templates?source_template_id=200"
        assert q.state() == {"template_id": 201, "version": 1, "status": "draft", "lineage_id": 200}
        assert 200 not in backend.templates
        assert "Replaced template 201 as a draft" in capsys.readouterr().out

    def test_a_published_template_gets_a_new_published_version(self, tmp_path, capsys):
        root = _project(tmp_path)
        data = _template(coding={"questions": [{"ref": 51, "minutes": 50}]}, interview={"questions": [7, 8]})
        q = Question(_template_dir(root, data))
        backend = FakeBackend()
        template.push(q, backend)
        backend.templates[200]["status"] = "active"  # published in the dashboard
        q.save_state(status="published")
        template.push(q, backend)
        assert backend.calls[-1][1] == "/templates?source_template_id=200"
        assert q.state()["template_id"] == 201 and q.state()["version"] == 2 and q.state()["status"] == "published"
        out = capsys.readouterr().out
        assert "Published version 2 of the template: id 201" in out
        assert "This template is live" in out

    def test_errors_stop_the_push_before_anything_is_sent(self, tmp_path):
        root = _project(tmp_path)
        q = Question(_template_dir(root, _template(coding=None)))
        backend = FakeBackend()
        with pytest.raises(PraxisError, match="1 problem"):
            template.push(q, backend)
        assert not [c for c in backend.calls if c[0] == "POST"]

    def test_a_refusal_shows_the_platforms_reason(self, tmp_path):
        class Refusing(FakeBackend):
            def post_json(self, path, body, timeout=60):
                raise platform.HttpError("failed", 422, "Draft questions: coding 52")

        with pytest.raises(PraxisError, match="refused the template: Draft questions: coding 52"):
            template.push(Question(_template_dir(_project(tmp_path))), Refusing())

    def test_pull_writes_integer_refs_and_a_push_after_it_sends_the_same_body(self, tmp_path):
        root = _project(tmp_path)
        backend = FakeBackend()
        sent = template.push(Question(_template_dir(root)), backend)
        into = tmp_path / "pulled"
        q = template.pull(backend, sent["template_id"], into)
        pulled = json.loads((into / "template.json").read_text())
        assert pulled == {
            "name": "AI Engineer", "description": "Agents in production.", "category": "ai_eng",
            "proctoring": {"webcam_proctoring": True, "screen_recording": True, "identity_photo": False},
            "ai_assistant": True,
            "coding": {"questions": [{"ref": 51, "minutes": 50}],
                       "pools": [{"refs": [52, 53], "pick": 1, "minutes": 40}]},
            "code_review": {"minutes": 10},
            "interview": {"questions": [7, [8, 9]]},
            "mcq": {"banks": [11, 12], "questions": 10, "minutes": 12},
        }
        assert q.state()["template_id"] == 200
        original = template.check(_template(), root, _library()).body
        again = template.check(pulled, root, _library()).body
        assert again == original

    def test_a_template_saved_before_groups_comes_back_one_question_each(self):
        local = template.to_local({"name": "t", "evaluation_type": "ai_interview",
                                   "ai_interview": {"question_ids": [7, 8], "total_minutes": 30},
                                   "mcq": {"question_bank_id": 11, "question_count": 8, "time_limit": 10},
                                   "code_review": {}})
        assert local["interview"] == {"questions": [7, 8]}
        assert local["mcq"] == {"banks": [11], "questions": 8, "minutes": 10}
        assert local["coding"] is None and local["code_review"] is None

    def test_pull_warns_when_the_interview_minutes_differ_from_its_questions(self, tmp_path, capsys):
        backend = FakeBackend()
        backend.templates[116] = {"template_id": 116, "name": "AI Engineer", "status": "active", "version": 1,
                                  "lineage_id": 116, "evaluation_type": "ai_interview",
                                  "ai_interview": {"groups": [{"question_ids": [7]}, {"question_ids": [8]}],
                                                   "total_minutes": 45}}
        template.pull(backend, 116, tmp_path / "t")
        out = capsys.readouterr().out
        assert "set to 45 minutes on the platform; its questions add up to 27" in out

    def test_the_cli_pulls_by_id_into_templates_and_tests_it(self, tmp_path, monkeypatch, capsys):
        root = _project(tmp_path)
        backend = FakeBackend()
        template.push(Question(_template_dir(root)), backend)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(cli, "Backend", lambda: backend)
        (tmp_path / "templates" / "ai_engineer" / ".codepraxis.json").unlink()
        assert cli.main(["pull", "200", "--template", "--into", "templates/copy"]) == cli.EXIT_OK
        assert cli.main(["test", "copy"]) == cli.EXIT_OK
        out = capsys.readouterr().out
        assert "total             145 min" in out
        assert "still drafts" in out
        # And by folder, from the id it remembered.
        assert cli.main(["pull", "copy"]) == cli.EXIT_OK

    def test_the_cli_test_fails_on_errors(self, tmp_path, monkeypatch, capsys):
        root = _project(tmp_path)
        _template_dir(root, _template(coding=None))
        monkeypatch.chdir(root)
        monkeypatch.setattr(cli, "Backend", FakeBackend)
        assert cli.main(["test", "ai_engineer"]) == cli.EXIT_FAILED
        assert "✗ code_review needs a coding round" in capsys.readouterr().out


class TestTheLibrary:
    def test_interview_statuses_read_as_the_dashboard_says_them(self):
        statuses = {i.id: i.status for i in template.fetch_library(FakeBackend())["interview"]}
        assert statuses == {7: "published", 8: "published", 9: "draft", 6: "published"}
        assert {i.id: i.status for i in _library()["interview"]}[10] == "retired"

    def test_coding_and_banks_filter_by_category_and_words(self):
        found = template.fetch_library(FakeBackend(), category="oracle-ebs", words="ledgers")
        assert [i.id for i in found["coding"]] == [53]
        assert found["mcq"] == []
        assert [i.id for i in template.fetch_library(FakeBackend(), ("mcq",), category="ai_eng")["mcq"]] == [11]
        assert [i.id for i in template.fetch_library(FakeBackend(), ("coding",), words="python")["coding"]] == [51]

    def test_the_interview_search_is_the_platforms(self):
        backend = FakeBackend()
        template.fetch_library(backend, ("interview",), category="ai_eng", words="agent evals")
        assert backend.calls == [("GET", "/interview-questions?q=agent+evals&category=ai_eng")]

    def test_the_cli_prints_a_table_per_kind_or_json(self, monkeypatch, capsys):
        monkeypatch.setattr(cli, "Backend", FakeBackend)
        assert cli.main(["library"]) == cli.EXIT_OK
        out = capsys.readouterr().out
        assert "Coding (4)" in out and "Interview (4)" in out and "MCQ banks (2)" in out
        assert "     51  published   60m  Build an agent loop" in out
        assert "     11  published   30q  MCP servers" in out
        assert cli.main(["library", "--kind", "interview", "--json"]) == cli.EXIT_OK
        data = json.loads(capsys.readouterr().out)
        assert list(data) == ["interview"]
        assert data["interview"][0] == {"kind": "interview", "id": 7, "status": "published", "name": "Agent evals",
                                        "minutes": 15, "categories": ["ai_eng"],
                                        "description": "Evaluating an agent.", "topics": ["evals"],
                                        "is_platform": True}
