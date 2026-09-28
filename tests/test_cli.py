"""The CLI's own logic, against fake platform and container clients."""

from __future__ import annotations

import io
import base64
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
        "pack/setup.sh": "set -euo pipefail\npip install x\n",
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

    def status(self):
        return {"last_submit_at": getattr(self, "results_at", 0)}

    def logs(self, source, tail=200):
        return {"text": getattr(self, "results_text", "{}")}

    def rerun_setup(self, timeout_s=120):
        from codepraxis.platform import NotFound

        if getattr(self, "old_image", True):
            raise NotFound("no /author/setup", 404)
        self.setup_reruns = getattr(self, "setup_reruns", 0) + 1
        return {"ran": True, "exit_code": 0, "root_exit_code": 0, "seconds": 3, "tail": ""}

    def exec(self, command, timeout_s=120):
        self.execs = getattr(self, "execs", []) + [command]
        return {"exit_code": 0, "stdout": "", "stderr": "", "seconds": 1}


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
        result = coding.send_changes(q, container)
        assert result.written == ["source/main.py"]
        assert result.deleted == ["source/output.log"]
        assert not result.setup_changed

    def test_grader_files_are_sent_before_the_workspace(self, tmp_path):
        q = _coding_question(tmp_path)
        container = FakeContainer({})
        coding.send_changes(q, container)
        first_source = min(i for i, p in enumerate(container.writes) if p.startswith("source/"))
        assert all(not p.startswith("source/") for p in container.writes[:first_source])

    def test_a_changed_setup_sh_is_flagged_for_rerunning(self, tmp_path):
        q = _coding_question(tmp_path)
        local = {p: f.read() for p, f in q.pack_files().items()}
        container = FakeContainer({**local, "setup.sh": b"old setup"})
        assert coding.send_changes(q, container).setup_changed


def _result(statuses):
    return lambda files: {"results": {"test_cases": {
        f"test_case_{i}": {"status": s} for i, s in enumerate(statuses, start=1)}}}


class TestTheFullTest:
    def _session(self, container):
        return coding.Session(container, challenge_version_id=7)

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


class FakeStatusContainer:
    """Answers status with a scripted sequence, then logs."""

    folder = "invoice_rerun"

    def __init__(self, statuses):
        self.statuses = list(statuses)

    def status(self):
        return {"setup": self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]}

    def logs(self, source, tail=200):
        return {"text": "Collecting oracledb\nERROR: No matching distribution"}


def _setup(**kw):
    return {"has_setup_sh": True, "exit_code": None, "root_exit_code": None, "last_line": "", **kw}


class TestWaitingForSetup:
    @pytest.fixture(autouse=True)
    def fast(self, monkeypatch):
        monkeypatch.setattr(coding.time, "sleep", lambda s: None)

    def test_both_runs_finishing_cleanly_is_success(self):
        coding.wait_for_setup(FakeStatusContainer([_setup(), _setup(exit_code=0, root_exit_code=0)]))

    def test_a_failed_candidate_run_stops_with_its_log(self):
        with pytest.raises(PraxisError, match="exit 1") as err:
            coding.wait_for_setup(FakeStatusContainer([_setup(exit_code=1)]))
        assert "No matching distribution" in str(err.value)

    def test_a_failed_root_run_is_caught_too(self):
        with pytest.raises(PraxisError, match="root"):
            coding.wait_for_setup(FakeStatusContainer([_setup(exit_code=0, root_exit_code=2)]))

    def test_more_than_the_limit_is_refused(self, monkeypatch):
        clock = iter(range(0, 10_000, 50))
        monkeypatch.setattr(coding.time, "time", lambda: next(clock))
        with pytest.raises(PraxisError, match="must finish within 120"):
            coding.wait_for_setup(FakeStatusContainer([_setup()]))

    def test_an_older_image_that_reports_no_root_run_still_finishes(self):
        old = {"has_setup_sh": True, "exit_code": 0, "state": "done"}
        coding.wait_for_setup(FakeStatusContainer([old]))


class TestSetupRules:
    def test_a_setup_sh_without_set_e_is_flagged(self, tmp_path):
        q = _coding_question(tmp_path)
        (q.pack / "setup.sh").write_text("pip install x\n")
        assert coding.setup_sh_problems(q)

    def test_set_euo_pipefail_satisfies_it(self, tmp_path):
        assert coding.setup_sh_problems(_coding_question(tmp_path)) == []


class TestPullingAnInterviewQuestionBack:
    def test_ids_become_the_same_file_names_again(self):
        ids = {"loader.sql": 1, "diagram.png": 2, "log.md": 3, "deep.excalidraw": 4}
        stored = interview.with_entity_ids(QUESTION, ids)
        back = interview.with_file_names(stored, {v: k for k, v in ids.items()})
        assert back["entity_refs"] == QUESTION["entity_refs"]
        assert back["mcq_choices"][0] == {"id": "a", "file": "diagram.png"}
        assert back["probes"][0]["next"][0]["entities"] == ["deep.excalidraw"]

    def test_two_files_with_one_name_are_kept_apart(self):
        assert interview._unique_name("a.png", {"a.png"}) == "a_2.png"


class TestProgress:
    def test_a_step_says_when_it_starts_and_how_it_ended(self, capsys):
        from codepraxis import progress

        with progress.step("Pushing x") as s:
            s.result("Draft updated")
        out = capsys.readouterr().out
        assert "→ Pushing x…" in out and "✓ Draft updated" in out

    def test_a_failing_step_says_so_with_the_reason(self, capsys):
        from codepraxis import progress

        with pytest.raises(PraxisError), progress.step("Opening"):
            raise PraxisError("pool is empty\nmore detail")
        assert "✗ Opening" in capsys.readouterr().out


class TestRerunningSetup:
    def test_the_script_is_passed_in_not_read_from_the_root_only_pack(self, tmp_path):
        q = _coding_question(tmp_path)
        local = {p: f.read() for p, f in q.pack_files().items()}
        container = FakeContainer({**local, "setup.sh": b"old setup"})
        coding.send_changes(q, container)
        (command,) = container.execs
        assert "/praxis/" not in command
        assert command.startswith("bash -s -- invoice_rerun <<'CODEPRAXIS_SETUP_SH_END'")
        assert "pip install x" in command


class TestASubmitThatWasCutOff:
    def test_the_results_file_is_read_once_the_grader_finishes(self, tmp_path, monkeypatch):
        from codepraxis.platform import HttpError

        monkeypatch.setattr(coding.time, "sleep", lambda s: None)
        container = FakeContainer({})

        def cut_off(files):
            container.results_at = 100
            container.results_text = json.dumps({"test_cases": {"test_case_1": {"status": "PASS"}}})
            raise HttpError("GET /uvi/submit failed (500): WebSocket connection closed: keepalive ping timeout", 500)

        container.submits = [cut_off]
        cases = coding.submit(container, 7, "solution")
        assert [c.passed for c in cases] == [True]

    def test_any_other_failure_is_not_waited_out(self):
        from codepraxis.platform import HttpError

        container = FakeContainer({})

        def broken(files):
            raise HttpError("GET /uvi/submit failed (500): something else", 500)

        container.submits = [broken]
        with pytest.raises(HttpError):
            coding.submit(container, 7, "solution")


class TestTheBaseCommit:
    def test_the_bundle_ships_a_one_commit_repository_of_source(self, tmp_path):
        import subprocess

        q = _coding_question(tmp_path)
        (q.pack / "source" / ".git").mkdir()
        (q.pack / "source" / ".git" / "HEAD").write_text("the author's own history")
        archive = zipfile.ZipFile(io.BytesIO(coding.bundle(q)))
        names = archive.namelist()
        assert "pack/invoice_rerun/source/._git/HEAD" in names
        assert not any("/source/.git/" in n for n in names)  # the author's .git never ships

        out = tmp_path / "out"
        for n in names:
            if n.startswith("pack/invoice_rerun/source/._git/"):
                target = out / ".git" / n[len("pack/invoice_rerun/source/._git/"):]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(n))
        log = subprocess.run(["git", "--git-dir", str(out / ".git"), "log", "--format=%an <%ae>|%s|%D"],
                             capture_output=True, text=True, check=True).stdout.strip().splitlines()
        assert log == ["CodeGuru <guru@codepraxis.com>|Setting up the test environment|HEAD -> main"]
        files = subprocess.run(["git", "--git-dir", str(out / ".git"), "ls-tree", "-r", "--name-only", "HEAD"],
                               capture_output=True, text=True, check=True).stdout.split()
        assert files == ["main.py"]

    def test_the_same_files_give_the_same_commit(self, tmp_path):
        q = _coding_question(tmp_path)
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        first = {k for k in coding.base_repository(q, tmp_path / "a") if k.startswith("objects/")}
        second = {k for k in coding.base_repository(q, tmp_path / "b") if k.startswith("objects/")}
        assert first == second


class TestRerunningSetupOnANewImage:
    def test_the_platform_runner_is_used_when_the_image_has_it(self, tmp_path):
        q = _coding_question(tmp_path)
        local = {p: f.read() for p, f in q.pack_files().items()}
        container = FakeContainer({**local, "setup.sh": b"old setup"})
        container.old_image = False
        coding.send_changes(q, container)
        assert container.setup_reruns == 1
        assert not getattr(container, "execs", [])



class TestOpenChallengeWaitsThroughAColdStart:
    """The backend answers 503 while a container starts; a proxy cut-off is 500/502/504."""

    def _backend(self, monkeypatch, replies):
        backend = platform.Backend(key="sk_test", url="https://api.example")
        calls, sleeps = [], []

        def fake_call(method, path, **kwargs):
            calls.append(path)
            reply = replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply

        monkeypatch.setattr(backend, "_call", fake_call)
        monkeypatch.setattr(platform.time, "sleep", sleeps.append)
        return backend, calls, sleeps

    def test_503_still_starting_is_retried_after_five_seconds(self, monkeypatch):
        opened = {"base_url": "https://c", "folder": "q", "challenge_version_id": 11}
        starting = platform.HttpError("still starting", 503)
        backend, calls, sleeps = self._backend(monkeypatch, [starting, starting, opened])
        notes = []

        assert backend.open_challenge(7, on_retry=lambda a, e, w: notes.append(w)) == opened
        assert calls == ["/challenges/7/open"] * 3
        assert sleeps == [5, 5] and notes == [5, 5]

    def test_proxy_cut_off_still_waits_fifteen_seconds(self, monkeypatch):
        opened = {"base_url": "https://c", "folder": "q", "challenge_version_id": 11}
        backend, _, sleeps = self._backend(monkeypatch, [platform.HttpError("cut off", 504), opened])

        assert backend.open_challenge(7) == opened
        assert sleeps == [15]

    def test_client_error_is_not_retried(self, monkeypatch):
        backend, calls, sleeps = self._backend(monkeypatch, [platform.HttpError("forbidden", 403)])

        with pytest.raises(platform.HttpError):
            backend.open_challenge(7)
        assert calls == ["/challenges/7/open"] and sleeps == []


# ── interview files: repos, descriptions, conversions, highlights ──────────

def _question_dir(tmp_path, question=None):
    root = tmp_path / "q"
    (root / "entities").mkdir(parents=True)
    (root / "question.json").write_text(json.dumps(question or {}))
    return root


class _RecordingBackend:
    def __init__(self):
        self.bodies = []

    def post_json(self, path, payload, timeout=60):
        self.bodies.append(payload)
        return {"entity_id": 100 + len(self.bodies)}


class TestInterviewFiles:
    def test_a_folder_is_a_repo_zipped_the_same_way_every_time(self, tmp_path):
        repo = tmp_path / "invoice_loader"
        (repo / "src").mkdir(parents=True)
        (repo / "src" / "loader.py").write_text("print(1)\n")
        (repo / "README.md").write_text("# loader\n")
        (repo / ".git").mkdir()
        (repo / ".git" / "HEAD").write_text("ref")
        (repo / "logo.png").write_bytes(b"\x89PNG\x00\xff")
        assert interview.entity_type(repo) == "repo"
        first, second = interview.zip_repo(repo), interview.zip_repo(repo)
        assert first == second
        import zipfile, io as _io
        assert sorted(zipfile.ZipFile(_io.BytesIO(first)).namelist()) == ["README.md", "src/loader.py"]

    def test_a_repo_over_the_limit_is_refused_before_uploading(self, tmp_path):
        repo = tmp_path / "big"
        repo.mkdir()
        (repo / "a.sql").write_text("x" * (interview.REPO_MAX_TEXT_BYTES + 1))
        with pytest.raises(PraxisError, match="This repo is too big"):
            interview.zip_repo(repo)

    def test_a_description_goes_up_with_its_file_and_a_new_one_uploads_again(self, tmp_path):
        root = _question_dir(tmp_path)
        (root / "entities" / "demo.mp4").write_bytes(b"\x00\x01")
        (root / "entities" / "demo.mp4.description.md").write_text("The OPP log filling up.\n")
        backend = _RecordingBackend()
        q = Question(root)
        assert interview.upload_entities(q, backend, {"demo.mp4"}) == {"demo.mp4": 101}
        assert interview.upload_entities(q, backend, {"demo.mp4"}) == {"demo.mp4": 101}
        (root / "entities" / "demo.mp4.description.md").write_text("The OPP log, then the heap error.\n")
        assert interview.upload_entities(q, backend, {"demo.mp4"}) == {"demo.mp4": 102}
        first = backend.bodies[0]
        assert first["type"] == "video" and first["normalized_form"] == "The OPP log filling up."
        assert first["meta"] == {"filename": "demo.mp4", "content_type": "video/mp4"}

    def test_audio_and_video_need_a_description(self, tmp_path):
        root = _question_dir(tmp_path)
        (root / "entities" / "call.mp3").write_bytes(b"ID3")
        with pytest.raises(PraxisError, match="call.mp3.description.md"):
            interview.upload_entities(Question(root), _RecordingBackend(), {"call.mp3"})

    def test_slides_need_libreoffice_and_word_falls_back_to_a_link(self, tmp_path, monkeypatch):
        monkeypatch.setattr(interview, "_soffice", lambda: None)
        root = _question_dir(tmp_path)
        (root / "entities" / "deck.pptx").write_bytes(b"PK")
        (root / "entities" / "spec.docx").write_bytes(b"PK")
        with pytest.raises(PraxisError, match="slides are shown as a PDF"):
            interview.upload_entities(Question(root), _RecordingBackend(), {"deck.pptx"})
        backend = _RecordingBackend()
        interview.upload_entities(Question(root), backend, {"spec.docx"})
        assert backend.bodies[0]["type"] == "doc"

    def test_a_converted_file_goes_up_as_a_pdf(self, tmp_path, monkeypatch):
        monkeypatch.setattr(interview, "convert_to_pdf", lambda path: b"%PDF-1.7")
        root = _question_dir(tmp_path)
        (root / "entities" / "deck.pptx").write_bytes(b"PK")
        backend = _RecordingBackend()
        interview.upload_entities(Question(root), backend, {"deck.pptx"})
        body = backend.bodies[0]
        assert body["type"] == "pdf" and body["meta"]["filename"] == "deck.pdf"
        assert body["meta"]["converted_from"] == "deck.pptx"

    def test_highlights_and_editable_files_are_written_by_name_and_sent_by_id(self):
        question = {
            "entity_refs": [{"file": "loader.sql"}],
            "seed_highlights": [{"file": "loader.sql", "lines": [88, 110]}],
            "probes": [{"id": 1, "description": "d", "entities": ["repo"], "editable": ["repo"],
                        "highlights": [{"file": "repo", "path": "src/a.py", "lines": [3, 3]}]}],
        }
        ids = {"loader.sql": 1, "repo": 2}
        out = interview.with_entity_ids(question, ids)
        assert out["seed_highlights"] == [{"entity_id": 1, "start_line": 88, "end_line": 110}]
        assert out["probes"][0]["editable"] == [2]
        assert out["probes"][0]["highlights"] == [{"entity_id": 2, "start_line": 3, "end_line": 3, "path": "src/a.py"}]
        back = interview.with_file_names(out, {v: k for k, v in ids.items()})
        assert back["seed_highlights"] == [{"file": "loader.sql", "lines": [88, 110]}]
        assert back["probes"][0]["editable"] == ["repo"]
        assert back["probes"][0]["highlights"] == [{"file": "repo", "lines": [3, 3], "path": "src/a.py"}]

    def test_a_highlight_on_a_file_the_question_does_not_show_is_named(self):
        with pytest.raises(PraxisError, match="ghost.sql"):
            interview.with_entity_ids({"seed_highlights": [{"file": "ghost.sql", "lines": [1, 2]}]}, {})

    def test_a_pulled_repo_comes_back_as_its_folder_with_its_description(self, tmp_path):
        import zipfile, io as _io
        buffer = _io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("src/a.py", "a = 1\n")

        class PullBackend:
            def get(self, path):
                return {"question": {"entity_refs": [{"id": 5, "editable": True}]}, "entities": [{
                    "entity_id": 5, "type": "repo", "filename": "invoice_loader",
                    "content_base64": base64.b64encode(buffer.getvalue()).decode(),
                    "description": "The loader.",
                }]}

        q = interview.pull(PullBackend(), 487, tmp_path / "pulled")
        assert (tmp_path / "pulled" / "entities" / "invoice_loader" / "src" / "a.py").read_text() == "a = 1\n"
        assert (tmp_path / "pulled" / "entities" / "invoice_loader.description.md").read_text().strip() == "The loader."
        assert json.loads((tmp_path / "pulled" / "question.json").read_text())["entity_refs"] == [
            {"file": "invoice_loader", "editable": True}
        ]
        # Pushing straight back uploads nothing.
        assert interview.upload_entities(q, _RecordingBackend(), {"invoice_loader"}) == {"invoice_loader": 5}
