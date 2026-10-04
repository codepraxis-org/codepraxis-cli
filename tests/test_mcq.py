"""MCQ banks: the local checks, preview.md, image paths ↔ entity ids, push and pull."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from codepraxis import cli, mcq, platform
from codepraxis.errors import PraxisError
from codepraxis.question import Question, sha256

PNG_FLOW = b"\x89PNG\r\n\x1a\nflow"
PNG_OPTION = b"\x89PNG\r\n\x1a\noption"


def _question(key, difficulty, **extra):
    q = {
        "key": key,
        "type": "single_select",
        "difficulty": difficulty,
        "prompt": f"Which retry policy fits case {key}?",
        "options": [{"text": "Retry at once"}, {"text": "Back off exponentially"}, {"text": "Never retry"}],
        "correct": [2],
        "explanation": "Backing off spreads the load.",
    }
    q.update(extra)
    return q


def _full_bank():
    """Three questions at every difficulty; the first uses both kinds of image."""
    questions = [_question(f"q-{d}-{i}", d) for d in range(1, 6) for i in range(3)]
    questions[0] = _question(
        "q-1-0", 1,
        prompt="Read the sequence:\n\n![the call sequence](images/flow.png)\n\nWhat happens next?",
        options=[
            {"text": "The client retries"},
            {"text": "", "image": "images/option_b.png"},
            {"text": "```python\nprint(1)\n```"},
            {"text": "| a | b |\n|---|---|\n| 1 | 2 |"},
        ],
        correct=[2],
    )
    return {"name": "Retries and timeouts", "description": "Retry policy.", "category": "ai_eng",
            "questions": questions}


def _bank_dir(tmp_path: Path, bank=None, images=True) -> Path:
    root = tmp_path / "mcq" / "retries"
    (root / "images").mkdir(parents=True)
    if images:
        (root / "images" / "flow.png").write_bytes(PNG_FLOW)
        (root / "images" / "option_b.png").write_bytes(PNG_OPTION)
    (root / "bank.json").write_text(json.dumps(bank if bank is not None else _full_bank()))
    return root


def _errors(bank, root):
    return mcq.check(bank, root).errors


class TestFindingABank:
    def test_a_bank_json_makes_it_an_mcq_bank_found_under_mcq(self, tmp_path):
        _bank_dir(tmp_path)
        q = Question.find("retries", cwd=tmp_path)
        assert q.kind == "mcq"

    def test_container_commands_say_a_bank_has_no_container(self, tmp_path):
        q = Question(_bank_dir(tmp_path))
        with pytest.raises(PraxisError, match="MCQ bank has no container"):
            q.require_coding("launch")


class TestChecks:
    def test_a_good_bank_has_no_errors_or_warnings(self, tmp_path):
        root = _bank_dir(tmp_path)
        report = mcq.check(_full_bank(), root)
        assert report.errors == [] and report.warnings == []
        assert report.by_difficulty == {1: 3, 2: 3, 3: 3, 4: 3, 5: 3}

    def test_bank_level_rules(self, tmp_path):
        root = _bank_dir(tmp_path)
        assert _errors({"name": " ", "questions": []}, root) == [
            "The bank needs a name.", "The bank needs at least one question."]

    @pytest.mark.parametrize("change, message", [
        ({"type": "pick_one"}, "type must be one of single_select, multi_select"),
        ({"difficulty": 0}, "difficulty must be 1 to 5"),
        ({"difficulty": 6}, "difficulty must be 1 to 5"),
        ({"difficulty": "hard"}, "difficulty must be 1 to 5"),
        ({"prompt": "  "}, "the question text is empty"),
        ({"options": [{"text": "only one"}], "correct": [1]}, "needs 2 to 6 options"),
        ({"options": [{"text": str(i)} for i in range(7)]}, "needs 2 to 6 options"),
        ({"options": [{"text": "a"}, {"text": ""}]}, "option 2: needs text or an image"),
        ({"options": [{"text": "Same"}, {"text": "same "}]}, "two options have the same text"),
        ({"correct": []}, "mark at least one correct option"),
        ({"correct": [4]}, "points to an option that does not exist"),
        ({"correct": ["two"]}, "mark at least one correct option"),
        ({"correct": [1, 2]}, "a single_select question has exactly one correct option"),
    ])
    def test_question_rules_match_the_server(self, tmp_path, change, message):
        bank = _full_bank()
        bank["questions"][5].update(change)
        errors = _errors(bank, _bank_dir(tmp_path, bank))
        assert len(errors) == 1 and errors[0].startswith("Question 6 (q-2-2)") and message in errors[0], errors

    def test_multi_select_may_have_several_correct(self, tmp_path):
        bank = _full_bank()
        bank["questions"][5].update(type="multi_select", correct=[1, 2])
        assert _errors(bank, _bank_dir(tmp_path, bank)) == []

    def test_options_that_are_images_may_share_empty_text(self, tmp_path):
        bank = _full_bank()
        bank["questions"][5]["options"] = [{"text": "", "image": "images/flow.png"},
                                           {"text": "", "image": "images/option_b.png"}]
        bank["questions"][5]["correct"] = [1]
        assert _errors(bank, _bank_dir(tmp_path, bank)) == []

    def test_duplicate_keys_name_the_first(self, tmp_path):
        bank = _full_bank()
        bank["questions"][4]["key"] = "q-1-0"
        assert _errors(bank, _bank_dir(tmp_path, bank)) == ["Question 5 (q-1-0): key repeats question 1."]

    def test_every_image_must_exist_under_images_with_an_image_extension(self, tmp_path):
        bank = _full_bank()
        bank["questions"][1]["prompt"] = "![a](images/ghost.png) ![b](diagram.png) ![c](images/../x.png)"
        bank["questions"][2]["options"][0] = {"text": "x", "image": "images/flow.svg"}
        root = _bank_dir(tmp_path, bank)
        (root / "images" / "flow.svg").write_text("<svg/>")
        errors = _errors(bank, root)
        assert "Question 2 (q-1-1): image 'images/ghost.png' does not exist." in errors
        assert any("'diagram.png' must be a file under images/" in e for e in errors)
        assert any("'images/../x.png' must be a file under images/" in e for e in errors)
        assert any(e.startswith("Question 3 (q-1-2), option 1: image 'images/flow.svg' must be one of") for e in errors)
        assert len(errors) == 4

    def test_an_image_already_on_the_platform_is_accepted(self, tmp_path):
        bank = _full_bank()
        bank["questions"][1]["prompt"] = "See ![a](entity:41)"
        bank["questions"][1]["options"][0] = {"text": "", "image_entity_id": 42}
        assert _errors(bank, _bank_dir(tmp_path, bank)) == []

    def test_unknown_keys_are_warned_not_refused(self, tmp_path):
        bank = _full_bank()
        bank["owner"] = "x"
        bank["questions"][0]["hint"] = "y"
        bank["questions"][0]["options"][0]["why"] = "z"
        report = mcq.check(bank, _bank_dir(tmp_path, bank))
        assert report.ok
        assert report.warnings == [
            "bank.json: unknown key 'owner'; the platform ignores it.",
            "Question 1 (q-1-0): unknown key 'hint'; the platform ignores it.",
            "Question 1 (q-1-0), option 1: unknown key 'why'; the platform ignores it.",
        ]

    def test_a_shallow_difficulty_is_warned(self, tmp_path):
        bank = _full_bank()
        bank["questions"] = [q for q in bank["questions"] if q["difficulty"] != 5][:-1]
        report = mcq.check(bank, _bank_dir(tmp_path, bank))
        assert report.ok
        assert report.by_difficulty == {1: 3, 2: 3, 3: 3, 4: 2, 5: 0}
        assert [w.split(";")[0] for w in report.warnings] == [
            "Difficulty 4 has 2 questions", "Difficulty 5 has 0 questions"]


class TestPreview:
    def test_every_question_is_rendered_with_images_answers_and_explanations(self, tmp_path):
        bank = _full_bank()
        text = mcq.render_preview(bank, mcq.check(bank, _bank_dir(tmp_path)))
        assert text.startswith("# Retries and timeouts\n\nRetry policy.\n")
        assert "Category `ai_eng` · 15 questions · by difficulty 1: 3 · 2: 3 · 3: 3 · 4: 3 · 5: 3" in text
        assert text.count("\n## ") == 15 and "## Problems" not in text
        assert "*Difficulty 1 · single select*" in text
        assert "![the call sequence](images/flow.png)" in text
        assert "**A.** The client retries\n" in text
        assert "**B.** ✅\n\n![Option B](images/option_b.png)" in text
        assert "**C.**\n\n```python\nprint(1)\n```" in text
        assert "**D.**\n\n| a | b |" in text
        assert "**Answer:** B" in text
        assert "**Explanation:** Backing off spreads the load." in text

    def test_problems_are_listed_at_the_top(self, tmp_path):
        bank = _full_bank()
        bank["questions"][0]["correct"] = []
        text = mcq.render_preview(bank, mcq.check(bank, _bank_dir(tmp_path, bank)))
        assert "## Problems\n\n- ✗ Question 1 (q-1-0): mark at least one correct option" in text

    def test_the_test_command_writes_preview_and_fails_on_errors(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        bank = _full_bank()
        root = _bank_dir(tmp_path, bank)
        assert cli.main(["test", "retries"]) == cli.EXIT_OK
        assert (root / "preview.md").read_text().startswith("# Retries and timeouts")
        bank["questions"][0]["difficulty"] = 9
        (root / "bank.json").write_text(json.dumps(bank))
        assert cli.main(["test", "retries"]) == cli.EXIT_FAILED
        out = capsys.readouterr().out
        assert "✗ Question 1 (q-1-0): difficulty must be 1 to 5." in out
        assert "By difficulty: 1: 2 · 2: 3" in out


class TestImagePaths:
    def test_images_are_found_with_their_descriptions(self):
        bank = _full_bank()
        bank["questions"][1]["options"][0] = {"text": "Plain retry", "image": "./images/flow.png"}
        bank["questions"][2]["options"][0] = {"text": "x ![](images/inline.png)"}
        assert mcq.referenced_images(bank) == {
            "flow.png": "the call sequence", "option_b.png": None, "inline.png": None}

    def test_paths_become_entity_ids_and_come_back(self):
        bank = _full_bank()
        bank["questions"][1]["prompt"] = 'Two: ![a](images/flow.png "title") and ![b](<images/flow.png>)'
        out = mcq.to_platform(bank, {"flow.png": 7, "option_b.png": 8}, bank_id=12)
        assert out["id"] == 12 and out["category"] == "ai_eng"
        first = out["questions"][0]
        assert first["prompt"] == "Read the sequence:\n\n![the call sequence](entity:7)\n\nWhat happens next?"
        assert first["options"][1] == {"text": "", "image_entity_id": 8}
        assert "image" not in json.dumps(first["options"][0])
        assert out["questions"][1]["prompt"] == 'Two: ![a](entity:7 "title") and ![b](entity:7)'
        assert bank["questions"][0]["options"][1] == {"text": "", "image": "images/option_b.png"}  # input untouched

        back = mcq.to_local({**out, "questions": out["questions"]}, {7: "flow.png", 8: "option_b.png"})
        assert back["questions"][0]["prompt"] == bank["questions"][0]["prompt"]
        assert back["questions"][0]["options"][1] == {"text": "", "image": "images/option_b.png"}
        assert set(back) == {"name", "description", "category", "questions"}

    def test_an_id_with_no_file_is_kept(self):
        data = {"name": "b", "questions": [{"prompt": "![x](entity:9)", "options": [
            {"text": "", "image_entity_id": 9}, {"text": "y"}], "correct": [1]}]}
        back = mcq.to_local(data, {})
        assert back["questions"][0]["prompt"] == "![x](entity:9)"
        assert back["questions"][0]["options"][0] == {"text": "", "image_entity_id": 9}

    def test_no_bank_id_means_a_new_bank(self):
        assert "id" not in mcq.to_platform(_full_bank(), {"flow.png": 1, "option_b.png": 2})


class FakeBackend:
    """The platform's question-bank API in memory."""

    def __init__(self, reject=None):
        self.entities: dict[int, dict] = {}
        self.banks: dict[int, dict] = {}
        self.calls: list[tuple[str, dict]] = []
        self.reject = reject

    def post_json(self, path, payload, timeout=60):
        self.calls.append((path, payload))
        if path == "/entities":
            entity_id = 100 + len(self.entities)
            self.entities[entity_id] = payload
            return {"entity_id": entity_id, "type": "image"}
        assert path == "/question-banks"
        if self.reject:
            raise platform.HttpError("POST /question-banks failed (422)", 422, {"problems": self.reject})
        bank_id = payload.get("id") or 500 + len(self.banks)
        created = bank_id not in self.banks
        self.banks[bank_id] = payload
        counts = {str(d): sum(1 for q in payload["questions"] if q["difficulty"] == d) for d in range(1, 6)}
        return {"bank_id": bank_id, "question_count": len(payload["questions"]), "by_difficulty": counts,
                "category": payload["category"], "visibility": "public", "created": created,
                "dashboard_path": f"/company/question-bank/{bank_id}"}

    def get(self, path):
        bank_id = int(path.rsplit("/", 1)[1])
        stored = self.banks[bank_id]
        return {
            "id": bank_id, "name": stored["name"], "description": stored["description"],
            "category": stored["category"], "questions": stored["questions"],
            "entities": {str(i): {"filename": e["meta"]["filename"], "url": f"https://blob.example/{i}?sig=x"}
                         for i, e in self.entities.items()},
        }

    def download(self, url):
        entity_id = int(url.split("/")[-1].split("?")[0])
        return base64.b64decode(self.entities[entity_id]["content_base64"])


class TestPushAndPull:
    def test_push_uploads_images_once_and_a_repush_replaces_the_same_bank(self, tmp_path, capsys, monkeypatch):
        monkeypatch.delenv(platform.ENV_API_URL, raising=False)
        root = _bank_dir(tmp_path)
        backend = FakeBackend()
        result = mcq.push(Question(root), backend)
        assert result["bank_id"] == 500 and result["created"]
        uploads = [p for p, _ in backend.calls if p == "/entities"]
        assert len(uploads) == 2
        flow = backend.entities[100]
        assert flow["type"] == "image" and base64.b64decode(flow["content_base64"]) == PNG_FLOW
        assert flow["meta"] == {"filename": "flow.png", "content_type": "image/png"}
        assert flow["normalized_form"] == "the call sequence"
        assert "normalized_form" not in backend.entities[101]  # empty option text: the server describes it
        sent = backend.banks[500]
        assert "id" not in sent
        assert "![the call sequence](entity:100)" in sent["questions"][0]["prompt"]
        assert sent["questions"][0]["options"][1] == {"text": "", "image_entity_id": 101}
        state = json.loads((root / ".codepraxis.json").read_text())
        assert state["bank_id"] == 500 and state["images"]["flow.png"]["entity_id"] == 100
        out = capsys.readouterr().out
        assert "Created bank 500 in the public library: 15 question(s)" in out
        assert "By difficulty: 1: 3 · 2: 3 · 3: 3 · 4: 3 · 5: 3" in out
        assert "https://www.codepraxis.co/company/question-bank/500" in out

        backend.calls.clear()
        (root / "images" / "option_b.png").write_bytes(PNG_OPTION + b"changed")
        again = mcq.push(Question(root), backend)
        assert again["bank_id"] == 500 and not again["created"]
        assert [p for p, _ in backend.calls] == ["/entities", "/question-banks"]  # only the changed image
        assert backend.calls[-1][1]["id"] == 500

    def test_local_errors_stop_the_push_before_anything_is_uploaded(self, tmp_path):
        bank = _full_bank()
        bank["questions"][0]["options"][1]["image"] = "images/ghost.png"
        backend = FakeBackend()
        with pytest.raises(PraxisError, match="1 problem"):
            mcq.push(Question(_bank_dir(tmp_path, bank)), backend)
        assert backend.calls == []

    def test_every_problem_in_a_422_is_printed(self, tmp_path, capsys):
        backend = FakeBackend(reject=["Unknown category 'ai_eng'.", "Question 2: image entity 9 does not exist."])
        with pytest.raises(PraxisError, match="2 problem"):
            mcq.push(Question(_bank_dir(tmp_path)), backend)
        out = capsys.readouterr().out
        assert "✗ Unknown category 'ai_eng'." in out
        assert "✗ Question 2: image entity 9 does not exist." in out

    def test_pull_rebuilds_the_folder_and_a_push_after_it_uploads_no_image(self, tmp_path):
        backend = FakeBackend()
        mcq.push(Question(_bank_dir(tmp_path)), backend)
        into = tmp_path / "pulled"
        q = mcq.pull(backend, 500, into)
        assert (into / "images" / "flow.png").read_bytes() == PNG_FLOW
        pulled = json.loads((into / "bank.json").read_text())
        original = _full_bank()
        assert pulled["questions"][0]["prompt"] == original["questions"][0]["prompt"]
        assert pulled["questions"][0]["options"][1] == {"text": "", "image": "images/option_b.png"}
        assert pulled["questions"][0]["key"] == "q-1-0"
        assert mcq.check(pulled, into).errors == []
        state = q.state()
        assert state["bank_id"] == 500
        assert state["images"]["flow.png"] == {"sha256": sha256(PNG_FLOW), "entity_id": 100}

        backend.calls.clear()
        mcq.push(q, backend)
        assert [p for p, _ in backend.calls] == ["/question-banks"]
        assert backend.calls[0][1]["id"] == 500

    def test_two_images_with_one_name_are_kept_apart_on_pull(self, tmp_path):
        backend = FakeBackend()
        backend.entities = {
            7: {"meta": {"filename": "chart.png"}, "content_base64": base64.b64encode(b"one").decode()},
            8: {"meta": {"filename": "sub/chart.png"}, "content_base64": base64.b64encode(b"two").decode()},
        }
        backend.banks[3] = {"name": "Charts", "description": None, "category": None, "questions": [{
            "type": "single_select", "difficulty": 2, "prompt": "![a](entity:7)",
            "options": [{"text": "", "image_entity_id": 7}, {"text": "", "image_entity_id": 8}], "correct": [1]}]}
        mcq.pull(backend, 3, tmp_path / "charts")
        pulled = json.loads((tmp_path / "charts" / "bank.json").read_text())
        assert pulled["questions"][0]["options"] == [
            {"text": "", "image": "images/chart.png"}, {"text": "", "image": "images/chart_2.png"}]
        assert (tmp_path / "charts" / "images" / "chart_2.png").read_bytes() == b"two"

    def test_the_cli_pulls_a_bank_by_id_into_mcq_by_name(self, tmp_path, monkeypatch):
        backend = FakeBackend()
        mcq.push(Question(_bank_dir(tmp_path)), backend)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(cli, "Backend", lambda: backend)
        assert cli.main(["pull", "500", "--mcq"]) == cli.EXIT_OK
        assert (tmp_path / "mcq" / "retries_and_timeouts" / "bank.json").is_file()
        # And by folder, from the id it remembered.
        assert cli.main(["pull", "retries_and_timeouts"]) == cli.EXIT_OK
