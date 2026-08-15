"""Finding source repositories for a question.

Three properties matter enough to pin down:

* **Only redistributable licences.** The code goes into a container the
  candidate controls. A copyleft or unlicensed repository reaching a customer
  is the one failure here with consequences outside the product.
* **Sampled, not ranked.** If every author searching the same words gets the
  same repository, the same codebase appears in assessments at several
  companies and solutions circulate.
* **Inspection is rationed.** /languages spends GitHub's core quota, which is
  60 an hour unauthenticated. Inspecting everything would exhaust an author's
  hour in three searches.

Fixtures are synthetic — see CONTRIBUTING.md on the content boundary.
"""

from __future__ import annotations

from pathlib import Path

from codepraxis.discovery import repos as discovery


def item(name, licence="mit", stars=100, size=500, language="Python"):
    return {
        "full_name": name,
        "description": f"{name} description",
        "html_url": f"https://github.com/{name}",
        "license": {"key": licence},
        "stargazers_count": stars,
        "size": size,
        "pushed_at": "2026-06-01T00:00:00Z",
        "language": language,
        "default_branch": "main",
    }


class FakeClient:
    """Stands in for the GitHub API, and counts what was spent."""

    def __init__(self, items, source_bytes=200_000, fail_languages=False):
        self._items = items
        self._source_bytes = source_bytes
        self._fail_languages = fail_languages
        self.language_calls = 0
        self.queries: list[str] = []

    def search(self, query, sort=None, pages=2):
        self.queries.append(query)
        return self._items

    def languages(self, full_name):
        self.language_calls += 1
        if self._fail_languages:
            raise RuntimeError("rate limited")
        return {"Python": self._source_bytes}

    def head_commit(self, full_name, branch):
        return "a" * 40


class TestQuery:
    def test_only_redistributable_licences_are_requested(self):
        query = discovery.build_query("agent", "python")
        assert "license:mit" in query
        assert "license:apache-2.0" in query
        assert "gpl" not in query

    def test_excludes_archived_and_forks(self):
        query = discovery.build_query("agent")
        assert "archived:false" in query
        assert "fork:false" in query

    def test_has_a_star_floor_but_no_ceiling(self):
        """A popular repo is not disqualified — the candidate is not asked to
        reproduce it, and AI-solvability is measured directly later."""
        query = discovery.build_query("agent")
        assert "stars:>=10" in query
        assert ".." not in query.split("stars:")[1].split()[0]


class TestFiltering:
    def test_disallowed_licence_never_survives(self):
        """Belt and braces: the query already asks, but a silent qualifier
        failure must not put GPL code in front of a customer."""
        client = FakeClient([item("a/gpl", licence="gpl-3.0"), item("b/ok")])
        found = discovery.find("agent", client=client, limit=5)
        assert [r.full_name for r in found] == ["b/ok"]

    def test_missing_licence_is_rejected(self):
        client = FakeClient([item("a/none", licence="")])
        assert discovery.find("agent", client=client) == []

    def test_toy_repositories_are_dropped(self):
        client = FakeClient([item("a/toy")], source_bytes=1_000)
        assert discovery.find("agent", client=client) == []

    def test_large_repositories_are_flagged_not_dropped(self):
        client = FakeClient([item("a/big")], source_bytes=5_000_000)
        found = discovery.find("agent", client=client)
        assert len(found) == 1
        assert any("seam" in note for note in found[0].notes)

    def test_duplicates_collapse(self):
        client = FakeClient([item("a/same"), item("a/same")])
        assert len(discovery.find("agent", client=client)) == 1


class TestSampling:
    def _names(self, seed):
        client = FakeClient([item(f"o/r{n}") for n in range(20)])
        return [r.full_name for r in discovery.find("agent", client=client, limit=3, seed=seed)]

    def test_same_seed_reproduces(self):
        assert self._names(7) == self._names(7)

    def test_different_seeds_differ(self):
        """Not a guarantee for any single pair, but over 20 candidates two
        seeds landing identically would mean sampling is not happening."""
        assert self._names(1) != self._names(2)

    def test_results_are_not_just_the_top_of_the_list(self):
        client = FakeClient([item(f"o/r{n}") for n in range(20)])
        found = discovery.find("agent", client=client, limit=3, seed=5)
        assert [r.full_name for r in found] != ["o/r0", "o/r1", "o/r2"]


class TestQuotaDiscipline:
    def test_inspection_stops_once_enough_are_found(self):
        """/languages is on the 60-an-hour core quota, so a small --limit must
        cost a small number of requests."""
        client = FakeClient([item(f"o/r{n}") for n in range(50)])
        discovery.find("agent", client=client, limit=2)
        assert client.language_calls == 2

    def test_inspection_is_capped_even_when_everything_is_rejected(self):
        client = FakeClient([item(f"o/r{n}") for n in range(50)], source_bytes=100)
        discovery.find("agent", client=client, limit=10)
        assert client.language_calls <= discovery.MAX_INSPECTIONS

    def test_rate_limited_inspection_says_so(self):
        """Degrading silently would show a repository whose size was never
        checked, which is what the floor exists to prevent."""
        client = FakeClient([item("a/ok")], fail_languages=True)
        found = discovery.find("agent", client=client)
        assert len(found) == 1
        assert any("rate limit" in note for note in found[0].notes)


class TestExclusion:
    def test_repos_already_used_locally_are_skipped(self, tmp_path: Path):
        question = tmp_path / "existing"
        question.mkdir()
        (question / "spec.md").write_text(
            "---\nquestion: existing\nrepo: github.com/a/taken @ abc1234\n---\n",
            encoding="utf-8",
        )
        client = FakeClient([item("a/taken"), item("b/free")])
        found = discovery.find("agent", client=client, root=tmp_path)
        assert [r.full_name for r in found] == ["b/free"]

    def test_a_missing_challenges_directory_is_not_an_error(self, tmp_path: Path):
        assert discovery.used_repos(tmp_path / "nope") == set()

    def test_explicit_exclusions_are_honoured(self):
        client = FakeClient([item("a/one"), item("b/two")])
        found = discovery.find("agent", client=client, exclude=["A/ONE"])
        assert [r.full_name for r in found] == ["b/two"]


class TestPinning:
    def test_commit_is_resolved_only_on_request(self):
        """Pinning every candidate would double the core-quota cost to record
        SHAs for repositories the author is about to discard."""
        client = FakeClient([item("a/ok")])
        found = discovery.find("agent", client=client)
        assert found[0].commit is None

        assert discovery.pin(found[0], client=client) == "a" * 40
        assert found[0].commit == "a" * 40
