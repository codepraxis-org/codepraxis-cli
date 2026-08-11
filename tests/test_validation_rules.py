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
    pack = tmp_path / "challenges" / name
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
        assert create(tmp_path / "c", "My-Great Pack").pack_dir.name == "my_great_pack"

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
