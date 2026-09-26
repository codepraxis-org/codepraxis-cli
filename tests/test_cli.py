"""The CLI's own logic, against fake platform and container clients."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from codepraxis import coding, interview, platform
from codepraxis.errors import PraxisError
from codepraxis.question import Question, sha256


def _coding_question(tmp_path: Path) -> Question:
    root = tmp_path / "challenges" / "invoice_rerun"
    files = {
        "pack/metadata.json": '{"name": "invoice_rerun"}',
        "pack/backend.conf": '{"BACKEND": "AI", "LANGUAGE": "PYTHON"}',
        "pack/setup.sh": "pip install x\n",
        "pack/._tests/test_1.py": "class testCases:\n    def __init__(self, w):\n        self.RUN = 2\n",
        "pack/._course_data/feature.md": "# Problem",
        "pack/source/main.py": "print('starter')\n",
        "pack/source/__pycache__/main.cpython-311.pyc": "junk",
        "solution/main.py": "print('solution')\n",
    }
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    return Question(root)


class FakeContainer:
    """In-memory container: files by path, and scripted Submit results."""

    folder = "invoice_rerun"

    def __init__(self, files=None, submits=None):
        self.files = dict(files or {})
        self.submits = list(submits or [])
        self.writes, self.deletes = [], []

    def list_files(self):
        return [{"path": p, "sha256": sha256(d)} for p, d in self.files.items()]

    def write_file(self, path, content, executable=False):
        self.files[path] = content
        self.writes.append(path)

    def delete_file(self, path):
        self.files.pop(path, None)
        self.deletes.append(path)

    def submit(self, version_id):
        return self.submits.pop(0)(self.files)


class TestFindingAQuestion:
    def test_by_slug_under_challenges(self, tmp_path):
        _coding_question(tmp_path)
        assert Question.find("invoice_rerun", cwd=tmp_path).kind == "coding"

    def test_an_interview_question_is_recognised(self, tmp_path):
        root = tmp_path / "challenges" / "rag"
        root.mkdir(parents=True)
        (root / "question.json").write_text("{}")
        assert Question.find("rag", cwd=tmp_path).kind == "interview"

    def test_a_missing_question_says_what_was_expected(self, tmp_path):
        with pytest.raises(PraxisError, match="pack/"):
            Question.find("nope", cwd=tmp_path)


class TestLocalFiles:
    def test_pack_paths_match_the_container_and_skip_caches(self, tmp_path):
        paths = set(_coding_question(tmp_path).pack_files())
        assert "source/main.py" in paths and "._tests/test_1.py" in paths
        assert not any("__pycache__" in p for p in paths)

    def test_solution_files_land_on_workspace_paths(self, tmp_path):
        assert list(_coding_question(tmp_path).solution_files()) == ["source/main.py"]

    def test_visible_case_count_comes_from_the_grader(self, tmp_path):
        assert _coding_question(tmp_path).visible_case_count() == 2

    def test_challenge_id_is_written_back_into_publish_json(self, tmp_path):
        q = _coding_question(tmp_path)
        q.remember_challenge_id(86)
        assert json.loads(q.publish_json.read_text())["challenge_id"] == 86


class TestTheDraftBundle:
    def test_pack_under_its_folder_and_solution_beside_it(self, tmp_path):
        names = zipfile.ZipFile(io.BytesIO(coding.bundle(_coding_question(tmp_path)))).namelist()
        assert "pack/invoice_rerun/source/main.py" in names
        assert "solution/main.py" in names
        assert not any("__pycache__" in n for n in names)

    def test_files_are_readable_in_the_zip(self, tmp_path):
        archive = zipfile.ZipFile(io.BytesIO(coding.bundle(_coding_question(tmp_path))))
        mode = archive.getinfo("pack/invoice_rerun/setup.sh").external_attr >> 16
        assert mode & 0o444 == 0o444


class TestSync:
    def test_only_changed_files_are_sent_and_extras_removed(self, tmp_path):
        q = _coding_question(tmp_path)
        local = {p: f.read() for p, f in q.pack_files().items()}
        remote = {**local, "source/main.py": b"old", "source/output.log": b"written by a run"}
        container = FakeContainer(remote)
        result = coding.sync(q, container, quiet=True)
        assert result.written == ["source/main.py"]
        assert result.deleted == ["source/output.log"]
        assert not result.setup_changed

    def test_grader_files_are_sent_before_the_workspace(self, tmp_path):
        q = _coding_question(tmp_path)
        container = FakeContainer({})
        coding.sync(q, container, quiet=True)
        first_source = min(i for i, p in enumerate(container.writes) if p.startswith("source/"))
        assert all(not p.startswith("source/") for p in container.writes[:first_source])

    def test_a_changed_setup_sh_is_flagged_for_rerunning(self, tmp_path):
        q = _coding_question(tmp_path)
        local = {p: f.read() for p, f in q.pack_files().items()}
        container = FakeContainer({**local, "setup.sh": b"old setup"})
        assert coding.sync(q, container, quiet=True).setup_changed


def _result(statuses):
    return lambda files: {"results": {"test_cases": {
        f"test_case_{i}": {"status": s} for i, s in enumerate(statuses, start=1)}}}


class TestTheFullTest:
    def _session(self, container):
        return coding.Session(container, challenge_version_id=7, opened_now=False)

    def test_passes_when_starter_fails_hidden_and_solution_passes_all(self, tmp_path):
        q = _coding_question(tmp_path)
        local = {p: f.read() for p, f in q.pack_files().items()}
        container = FakeContainer(local, [_result(["PASS", "FAIL", "FAIL", "FAIL"]), _result(["PASS"] * 4)])
        assert coding.full_test(q, self._session(container))
        assert container.files["source/main.py"] == b"print('starter')\n"  # starter put back

    def test_fails_when_the_starter_already_passes_a_hidden_case(self, tmp_path):
        q = _coding_question(tmp_path)
        container = FakeContainer({}, [_result(["PASS", "FAIL", "PASS"]), _result(["PASS"] * 3)])
        assert not coding.full_test(q, self._session(container))

    def test_the_starter_is_restored_even_when_submit_fails(self, tmp_path):
        q = _coding_question(tmp_path)
        local = {p: f.read() for p, f in q.pack_files().items()}

        def boom(files):
            raise PraxisError("submit failed")

        container = FakeContainer(local, [_result(["FAIL", "FAIL", "FAIL"]), boom])
        with pytest.raises(PraxisError):
            coding.full_test(q, self._session(container))
        assert container.files["source/main.py"] == b"print('starter')\n"

    def test_a_grader_that_produced_nothing_is_an_error(self, tmp_path):
        q = _coding_question(tmp_path)
        container = FakeContainer({}, [lambda f: {"results": {"test_cases": {}}, "grader_error": "ImportError"}])
        with pytest.raises(PraxisError, match="ImportError"):
            coding.full_test(q, self._session(container))


class TestCases:
    def test_run_and_submit_keys_both_order_by_number(self):
        cases = coding.cases_from({"Case 10": {"status": "PASS"}, "Case 2": {"status": "FAIL"},
                                   "test_case_1": {"status": "PASS"}})
        assert [c.number for c in cases] == [1, 2, 10]


QUESTION = {
    "name": "Rerun-safe invoice interface",
    "entity_refs": [{"file": "loader.sql", "editable": False}],
    "mcq_choices": [{"id": "a", "file": "diagram.png"}, {"id": "b", "text": "No"}],
    "seed_hints": [{"id": 1, "text": "Look", "entities": ["log.md"]}],
    "probes": [{"id": 1, "description": "d", "entities": ["diagram.png"],
                "hints": [{"id": 1, "text": "h", "entities": ["log.md"]}],
                "next": [{"id": 1, "description": "deeper", "entities": ["deep.excalidraw"]}]}],
}


class TestInterviewEntities:
    def test_every_file_name_is_found_anywhere_in_the_tree(self):
        assert interview.referenced_files(QUESTION) == {"loader.sql", "diagram.png", "log.md", "deep.excalidraw"}

    def test_file_names_become_entity_ids(self):
        ids = {"loader.sql": 1, "diagram.png": 2, "log.md": 3, "deep.excalidraw": 4}
        out = interview.with_entity_ids(QUESTION, ids)
        assert out["entity_refs"] == [{"id": 1, "editable": False}]
        assert out["mcq_choices"][0] == {"id": "a", "entity_id": 2}
        assert out["seed_hints"][0]["entities"] == [3]
        assert out["probes"][0]["hints"][0]["entities"] == [3]
        assert out["probes"][0]["next"][0]["entities"] == [4]
        assert QUESTION["entity_refs"][0] == {"file": "loader.sql", "editable": False}  # input untouched

    def test_types_come_from_the_extension(self):
        assert [interview.entity_type(Path(n)) for n in ("a.md", "b.png", "c.pdf", "d.docx", "e.sql")] == [
            "markdown", "image", "pdf", "doc", "code"]

    def test_an_unchanged_file_is_not_uploaded_again(self, tmp_path):
        root = tmp_path / "q"
        (root / "entities").mkdir(parents=True)
        (root / "question.json").write_text("{}")
        (root / "entities" / "loader.sql").write_text("select 1")
        q = Question(root)
        calls = []

        class FakeBackend:
            def post_json(self, path, payload, timeout=60):
                calls.append(path)
                return {"entity_id": 41}

        assert interview.upload_entities(q, FakeBackend(), {"loader.sql"}) == {"loader.sql": 41}
        assert interview.upload_entities(q, FakeBackend(), {"loader.sql"}) == {"loader.sql": 41}
        assert calls == ["/entities"]

    def test_a_missing_file_is_named(self, tmp_path):
        root = tmp_path / "q"
        root.mkdir()
        (root / "question.json").write_text("{}")
        with pytest.raises(PraxisError, match="ghost.png"):
            interview.upload_entities(Question(root), object(), {"ghost.png"})


class TestTheApiKey:
    def test_missing_key_asks_for_it(self, monkeypatch):
        monkeypatch.delenv(platform.ENV_API_KEY, raising=False)
        with pytest.raises(PraxisError, match="Please give your CodePraxis API key"):
            platform.api_key()

    def test_dashboard_links_drop_the_api_prefix(self, monkeypatch):
        monkeypatch.delenv(platform.ENV_API_URL, raising=False)
        assert platform.website_url() == "https://www.codepraxis.co"
