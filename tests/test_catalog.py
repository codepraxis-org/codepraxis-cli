from __future__ import annotations

from codepraxis.commands import catalog


class FakeClient:
    def __init__(self) -> None:
        self.calls = []

    def get(self, path: str) -> dict:
        self.calls.append(("GET", path))
        return {
            "challenges": [
                {
                    "challenge_id": 7,
                    "challenge_name": "Debug webhooks",
                    "status": "draft",
                    "challenge_version_id": 11,
                }
            ]
        }

    def patch_json(self, path: str, payload: dict) -> dict:
        self.calls.append(("PATCH", path, payload))
        return {"challenge": {"challenge_id": 7, "challenge_name": payload["challenge_name"]}}

    def post_json(self, path: str, payload: dict) -> dict:
        self.calls.append(("POST", path, payload))
        return {"container_url": "https://container.example/?folder=/home/praxis/debug_webhooks"}


def test_lists_company_questions(capsys):
    client = FakeClient()

    assert catalog.list_questions(client=client) == 0

    assert client.calls == [("GET", "/challenges")]
    output = capsys.readouterr().out
    assert "Debug webhooks" in output
    assert "draft" in output


def test_edit_updates_metadata_and_prints_container_url(capsys):
    client = FakeClient()

    assert catalog.edit_question(
        challenge_id=7,
        updates={"challenge_name": "Debug queues", "description": None},
        client=client,
    ) == 0

    assert client.calls == [
        ("PATCH", "/challenges/7", {"challenge_name": "Debug queues"}),
        ("POST", "/challenges/7/setup-codebase", {}),
    ]
    output = capsys.readouterr().out
    assert "Updated question 7" in output
    assert "https://container.example" in output


def test_edit_can_open_without_metadata_changes(capsys):
    client = FakeClient()

    assert catalog.edit_question(challenge_id=7, updates={}, client=client) == 0

    assert client.calls == [("POST", "/challenges/7/setup-codebase", {})]
    assert "Opening question 7" in capsys.readouterr().out
