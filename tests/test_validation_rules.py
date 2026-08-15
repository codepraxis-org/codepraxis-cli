"""Static rules must catch contract violations without running pack code.

Every fixture here is synthetic — see CONTRIBUTING.md on the content boundary.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codepraxis.domain.results import Severity
from codepraxis.packio.loader import load_pack
from codepraxis.validation.registry import has_errors, lint

GOOD_TESTS = '''
class testCases:
    def __init__(self, user_wxpace) -> None:
        self.RUN = 1
        self.RunCaseInputs = ["x"]
        self.userWxpace = user_wxpace
        self.exe = ""
        self.default_timeout_window = 5000
        self.usage = "prod"
        self.msg = ""

    def test_case_1(self, timeout_window=5000, override=1):
        self.msg = "PASS"
        return "expected", "ok"
'''


def build(tmp_path: Path, tests: str = GOOD_TESTS, feature: str = "# demo\n", name: str = "demo") -> Path:
    # The wrapper layout: <question>/pack, with the reference solution beside
    # it. Building packs as top-level directories is what the layout rule
    # rejects, so fixtures must not do it either.
    pack = tmp_path / "challenges" / name / "pack"
    (pack / "source").mkdir(parents=True)
    (pack / "._tests").mkdir()
    (pack / "._course_data").mkdir()

    (pack / "metadata.json").write_text(json.dumps({"name": name}))
    (pack / "backend.conf").write_text(json.dumps({"BACKEND": "AI", "LANGUAGE": "PYTHON"}))
    (pack / "source" / "README.md").write_text("stub")
    (pack / "._tests" / "test_1.py").write_text(tests)
    (pack / "._course_data" / "feature.md").write_text(feature)
    (pack / "._course_data" / "course_toc.json").write_text(
        json.dumps({"instruction_1": {"file": "feature.md", "metadata": {"STATUS": "IN_PROGRESS"}}})
    )
    return pack


def codes(findings):
    return {finding.code for finding in findings}


def _plugin_dir() -> Path:
    """The plugin the repo's own marketplace manifest points at."""
    repo_root = Path(__file__).resolve().parents[1]
    manifest = json.loads((repo_root / ".claude-plugin" / "marketplace.json").read_text())
    return repo_root / manifest["plugins"][0]["source"]


def test_a_well_formed_pack_is_clean(tmp_path):
    assert lint(load_pack(build(tmp_path))) == []


class TestConstructorArity:
    def test_two_argument_constructor_is_an_error(self, tmp_path):
        """The exact bug that made a real pack unloadable in the container."""
        tests = GOOD_TESTS.replace("def __init__(self, user_wxpace)", "def __init__(self, user_bin, wxpace)")
        findings = lint(load_pack(build(tmp_path, tests=tests)))

        assert "testcases.constructor-arity" in codes(findings)
        assert has_errors(findings)

    def test_missing_class_is_an_error(self, tmp_path):
        findings = lint(load_pack(build(tmp_path, tests="class somethingElse:\n    pass\n")))
        assert "testcases.missing-class" in codes(findings)


class TestNaming:
    def test_zero_padded_names_are_rejected(self, tmp_path):
        tests = GOOD_TESTS.replace("def test_case_1(", "def test_case_01(")
        assert "testcases.naming" in codes(lint(load_pack(build(tmp_path, tests=tests))))

    def test_duplicate_ordinals_are_rejected(self, tmp_path):
        tests = GOOD_TESTS + '''
    def test_case_1_extra(self, timeout_window=5000, override=1):
        self.msg = "PASS"
        return "e", "o"
'''
        assert "testcases.naming" in codes(lint(load_pack(build(tmp_path, tests=tests))))

    def test_a_pack_with_no_cases_is_rejected(self, tmp_path):
        tests = GOOD_TESTS.split("    def test_case_1")[0]
        assert "testcases.no-cases" in codes(lint(load_pack(build(tmp_path, tests=tests))))


class TestHygiene:
    def test_solution_inside_the_pack_is_an_error(self, tmp_path):
        """The mistake that would ship the answer to every candidate."""
        pack = build(tmp_path)
        (pack / "solution").mkdir()
        (pack / "solution" / "answer.py").write_text("VALUE = 1")

        findings = lint(load_pack(pack))
        assert "pack.solution-inside" in codes(findings)
        assert has_errors(findings)

    def test_pycache_is_flagged_as_a_warning(self, tmp_path):
        pack = build(tmp_path)
        (pack / "._tests" / "__pycache__").mkdir()

        findings = lint(load_pack(pack))
        assert "pack.forbidden-files" in codes(findings)
        assert not has_errors(findings)

    def test_requirements_in_source_is_flagged(self, tmp_path):
        pack = build(tmp_path)
        (pack / "source" / "requirements.txt").write_text("numpy\n")
        assert "pack.forbidden-files" in codes(lint(load_pack(pack)))


class TestQuestionLayout:
    """Two questions must never resolve to the same reference solution.

    The solution is found as the pack's sibling. When packs were themselves the
    top-level directories, every pack under a shared parent pointed at the same
    `solution/`, so scaffolding a second question overwrote the first one's
    reference solution — silently, with no history to recover it from.
    """

    def _flat_pack(self, tmp_path, name="demo"):
        """A pack at the top level: the layout that caused the collision."""
        nested = build(tmp_path, name=name)
        flat = nested.parent
        for entry in list(nested.iterdir()):
            entry.rename(flat / entry.name)
        nested.rmdir()
        return flat

    def test_a_top_level_pack_is_an_error(self, tmp_path):
        findings = lint(load_pack(self._flat_pack(tmp_path)))

        assert "pack.layout" in codes(findings)
        assert has_errors(findings)

    def test_the_error_says_how_to_migrate(self, tmp_path):
        findings = lint(load_pack(self._flat_pack(tmp_path)))
        message = next(f.message for f in findings if f.code == "pack.layout")

        assert "demo/pack/" in message
        assert "demo/solution/" in message

    def test_it_counts_the_questions_that_would_collide(self, tmp_path):
        self._flat_pack(tmp_path, name="first")
        findings = lint(load_pack(self._flat_pack(tmp_path, name="second")))
        message = next(f.message for f in findings if f.code == "pack.layout")

        assert "2 questions share" in message

    def test_the_wrapper_layout_is_clean(self, tmp_path):
        assert lint(load_pack(build(tmp_path))) == []


class TestScaffoldIsolation:
    """Scaffolding twice must not touch the first question's solution."""

    def test_two_questions_get_separate_solutions(self, tmp_path):
        from codepraxis.scaffold.generator import create

        first = create(tmp_path / "challenges", "first_question")
        second = create(tmp_path / "challenges", "second_question")

        assert first.solution_dir != second.solution_dir
        assert first.solution_dir.is_dir() and second.solution_dir.is_dir()

    def test_a_non_empty_solution_is_never_overwritten(self, tmp_path):
        """Even --force stops here: a solution is the proof a question is solvable."""
        from codepraxis.errors import PraxisError
        from codepraxis.scaffold.generator import create

        result = create(tmp_path / "challenges", "demo_pack")
        precious = result.solution_dir / "main.py"
        precious.write_text("# hand-written reference solution\n")

        with pytest.raises(PraxisError, match="Refusing to write over a reference solution"):
            create(tmp_path / "challenges", "demo_pack", force=True)

        assert precious.read_text() == "# hand-written reference solution\n"


class TestQuestionSelector:
    """Authors refer to a question by name, not by the literal 'pack' directory."""

    def test_a_question_resolves_by_its_name(self, tmp_path):
        from codepraxis.packio.discovery import resolve_pack_dir

        build(tmp_path, name="webhook_debug")
        resolved = resolve_pack_dir(tmp_path / "challenges", "webhook_debug")

        assert resolved.name == "pack"
        assert resolved.parent.name == "webhook_debug"

    def test_the_question_directory_path_also_works(self, tmp_path):
        from codepraxis.packio.discovery import resolve_pack_dir

        build(tmp_path, name="webhook_debug")
        resolved = resolve_pack_dir(tmp_path, "challenges/webhook_debug")

        assert resolved.name == "pack"

    def test_two_questions_do_not_collide_on_the_name_pack(self, tmp_path):
        """Selecting by directory name would make every question answer to 'pack'."""
        from codepraxis.packio.discovery import resolve_pack_dir

        build(tmp_path, name="first_question")
        build(tmp_path, name="second_question")

        first = resolve_pack_dir(tmp_path / "challenges", "first_question")
        second = resolve_pack_dir(tmp_path / "challenges", "second_question")

        assert first != second


class TestInstructions:
    @pytest.mark.parametrize("body", ["Use $x = 1$ here.", "$$E = mc^2$$", r"\(a+b\)", r"Use \frac{a}{b}"])
    def test_latex_is_flagged(self, tmp_path, body):
        findings = lint(load_pack(build(tmp_path, feature=f"# demo\n\n{body}\n")))
        assert "instructions.notation" in codes(findings)

    def test_prose_and_currency_are_not_flagged(self, tmp_path):
        """A lone dollar amount must not trip the inline-maths pattern."""
        feature = "# demo\n\nThe budget is 5 dollars. Costs are listed in USD.\n"
        assert "instructions.notation" not in codes(lint(load_pack(build(tmp_path, feature=feature))))

    def test_notation_is_a_warning_not_an_error(self, tmp_path):
        findings = lint(load_pack(build(tmp_path, feature="# demo\n\n$$x$$\n")))
        assert not has_errors(findings)
        assert all(f.severity is Severity.WARNING for f in findings if f.code == "instructions.notation")


class TestScaffold:
    """A generated pack must be immediately valid — that is the whole point."""

    def test_generated_pack_lints_clean(self, tmp_path):
        from codepraxis.scaffold.generator import create

        result = create(tmp_path / "challenges", "sum_the_arguments")
        assert lint(load_pack(result.pack_dir)) == []

    def test_solution_lands_beside_the_pack_not_inside_it(self, tmp_path):
        from codepraxis.scaffold.generator import create

        result = create(tmp_path / "challenges", "demo_pack")

        assert result.solution_dir.parent == result.pack_dir.parent
        assert not (result.pack_dir / "solution").exists()

    def test_names_are_normalised(self, tmp_path):
        from codepraxis.scaffold.generator import create, normalize_name

        assert normalize_name("My-Great Pack") == "my_great_pack"
        assert create(tmp_path / "c", "My-Great Pack").question_dir.name == "my_great_pack"

    @pytest.mark.parametrize("bad", ["a", "9lives", "", "!!"])
    def test_unusable_names_are_rejected(self, tmp_path, bad):
        from codepraxis.errors import PraxisError
        from codepraxis.scaffold.generator import create

        with pytest.raises(PraxisError):
            create(tmp_path / "c", bad)

    def test_refuses_to_clobber_without_force(self, tmp_path):
        from codepraxis.errors import PraxisError
        from codepraxis.scaffold.generator import create

        create(tmp_path / "c", "demo_pack")
        with pytest.raises(PraxisError, match="already exists"):
            create(tmp_path / "c", "demo_pack")

    def test_unknown_backend_is_rejected(self, tmp_path):
        from codepraxis.errors import PraxisError
        from codepraxis.scaffold.generator import create

        with pytest.raises(PraxisError, match="Unknown BACKEND"):
            create(tmp_path / "c", "demo_pack", backend="NOPE")


class TestExampleCommand:
    """--example must work with no credentials at all."""

    class FakeClient:
        def __init__(self):
            self.calls = []

        def get(self, path):
            self.calls.append(("GET", path))
            return {"challenge": {"challenge_name": "Demo", "difficulty": 2, "tech_stack": ["Python", ""]}}

        def post_json(self, path, payload):
            self.calls.append(("POST", path))
            return {"container_url": "https://container.example/?folder=/home/praxis/demo"}

    def test_fetches_the_featured_challenge_then_starts_a_container(self, capsys):
        from codepraxis.commands import example

        client = self.FakeClient()
        assert example.run(client=client) == 0

        assert client.calls == [("GET", "/challenges/featured"), ("POST", "/challenges/trial/setup-codebase")]
        assert "https://container.example" in capsys.readouterr().out

    def test_missing_container_url_is_an_error(self):
        from codepraxis.commands import example
        from codepraxis.errors import PraxisError

        client = self.FakeClient()
        client.post_json = lambda path, payload: {}

        with pytest.raises(PraxisError, match="no container URL"):
            example.run(client=client)

    def test_public_config_needs_no_token(self, monkeypatch, tmp_path):
        """Resolving credentials must not raise when there is no key."""
        from codepraxis.execution.remote.config import RemoteConfig

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.delenv("CODEPRAXIS_TOKEN", raising=False)

        assert RemoteConfig.resolve_public().token == ""


class TestPluginInstructions:
    """`/plugin marketplace add` reads a bare `foo/bar` as a GitHub repo.

    So the printed path must be "./"-prefixed: that cannot be parsed as
    owner/repo, and unlike an absolute path it is the same string on every
    machine — which is the whole point, since the instructions get copied
    between laptops.
    """

    def test_marketplace_command_uses_a_dot_relative_path(self, tmp_path, monkeypatch):
        from codepraxis.plugin import installer

        monkeypatch.chdir(tmp_path)
        result = installer.install(tmp_path)
        line = next(
            text
            for text in installer.describe(result).splitlines()
            if "marketplace add" in text and installer.HOSTED_MARKETPLACE not in text
        )

        path = line.split("marketplace add", 1)[1].strip()
        assert path.startswith("./"), f"{path!r} would be read as a GitHub owner/repo"
        assert "/Users/" not in path and not path.startswith("/"), (
            f"{path!r} is machine-specific; the same instructions are used on every machine"
        )
        assert Path(path).is_dir()

    def test_the_marketplace_manifest_is_where_the_command_points(self, tmp_path, monkeypatch):
        from codepraxis.plugin import installer

        monkeypatch.chdir(tmp_path)
        result = installer.install(tmp_path)

        assert (result.root / ".claude-plugin" / "marketplace.json").is_file()
        assert (result.root / "plugin" / ".claude-plugin" / "plugin.json").is_file()

    def test_the_local_marketplace_is_named_apart_from_the_hosted_one(self, tmp_path, monkeypatch):
        """Marketplace names are global in Claude Code.

        Sharing a name means installing locally silently displaces the hosted
        plugin, or is refused outright — which is exactly the collision this
        naming avoids.
        """
        from codepraxis.plugin import installer

        monkeypatch.chdir(tmp_path)
        result = installer.install(tmp_path)
        manifest = json.loads((result.root / ".claude-plugin" / "marketplace.json").read_text())

        assert manifest["name"] == installer.LOCAL_NAME
        assert manifest["name"] != installer.HOSTED_NAME
        assert manifest["plugins"][0]["source"] == "./plugin"

    def test_plan_cannot_see_the_build_instructions(self):
        """The failure this whole split exists to prevent.

        When planning and building were steps 1 and 2 of one command file, an
        agent read "write down the architecture" as an internal note, never
        stopped, and went straight into scaffolding and writing pack files. A
        model does everything it can see: if the planning prompt contains the
        implementation steps, it drifts into them. Separate files, and the
        planning one must not describe how to build.
        """
        commands = _plugin_dir() / "commands"
        plan = (commands / "plan.md").read_text()

        forbidden = ["codepraxis new", "codepraxis ship", "._tests/test_1.py", "setup.sh at the pack root"]
        leaked = [phrase for phrase in forbidden if phrase in plan]
        assert not leaked, f"plan.md describes building: {leaked}"

    def test_plan_cannot_edit_files(self):
        """Tool scoping is the backstop for when the wording fails."""
        plan = (_plugin_dir() / "commands" / "plan.md").read_text()
        allowed = next(line for line in plan.splitlines() if line.startswith("allowed-tools:"))

        assert "Edit" not in allowed, "planning must not be able to modify existing files"

    def test_build_refuses_without_an_approved_plan(self):
        build = (_plugin_dir() / "commands" / "build.md").read_text()

        assert "status: approved" in build
        assert "stop" in build.lower()

    def test_every_lifecycle_command_exists(self):
        commands = _plugin_dir() / "commands"
        present = {path.stem for path in commands.glob("*.md")}

        # plan/build/ship carry the workflow; the rest are used on demand.
        assert present == {"plan", "build", "ship", "try", "evaluate", "edit"}

    def test_planning_starts_from_real_code(self):
        """A question built on a repository the model has never seen is the
        thing that makes it hard to answer from the brief alone. If planning
        stops pushing for that, every question drifts back to invented ones."""
        plan = (_plugin_dir() / "commands" / "plan.md").read_text()

        assert "find-repos" in plan
        assert "seam" in plan

    def test_the_simulation_is_never_run_by_the_author_context(self):
        """The context that designed or built a question knows its answers, so
        its own attempt measures nothing. Every place that triggers a
        simulation must say so, or the number silently becomes theatre."""
        plugin = _plugin_dir()
        sources = [
            plugin / "commands" / "plan.md",
            plugin / "commands" / "build.md",
            plugin / "commands" / "evaluate.md",
            plugin / "skills" / "question-evaluation" / "SKILL.md",
        ]
        for path in sources:
            text = path.read_text().lower()
            assert "subagent" in text, f"{path.name} must dispatch a subagent"

    def test_specs_never_leak_runner_vocabulary(self):
        """spec.md is read by a hiring manager who has never seen the runner.
        'override 2' means nothing to them."""
        plan = (_plugin_dir() / "commands" / "plan.md").read_text()

        spec_template = plan.split("```markdown")[1].split("```")[0]
        assert "override" not in spec_template.lower()
        assert "By AI review" in spec_template

    def test_the_repository_marketplace_points_at_a_real_plugin(self):
        """The hosted marketplace is served from the repo root.

        If this manifest's source path drifts from where the plugin actually
        lives, `/plugin marketplace add codepraxis-org/codepraxis-cli` resolves
        to nothing — and it fails for every user at once, not just us.
        """
        repo_root = Path(__file__).resolve().parents[1]
        manifest_path = repo_root / ".claude-plugin" / "marketplace.json"
        assert manifest_path.is_file(), "the repo must carry a root marketplace manifest"

        manifest = json.loads(manifest_path.read_text())
        source = repo_root / manifest["plugins"][0]["source"]

        assert (source / ".claude-plugin" / "plugin.json").is_file()
        assert (source / "commands").is_dir()
        assert (source / "skills").is_dir()
