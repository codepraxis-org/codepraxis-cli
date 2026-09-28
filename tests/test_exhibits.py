"""The exhibit helpers: pure-Python parts only (rendering needs Chrome and ffmpeg)."""

import pytest

from codepraxis import exhibits


def test_write_creates_folders_and_writes_utf8(tmp_path):
    out = exhibits.write(tmp_path / "entities" / "note.md", "£18.40 per sq ft")
    assert out.read_text(encoding="utf-8") == "£18.40 per sq ft"


def test_an_env_var_overrides_the_search(monkeypatch):
    monkeypatch.setenv("CODEPRAXIS_CHROME", "/opt/my-chrome")
    assert exhibits.chrome() == "/opt/my-chrome"


def test_a_missing_program_says_what_to_install(monkeypatch):
    monkeypatch.delenv("CODEPRAXIS_CHROME", raising=False)
    monkeypatch.delenv("CODEPRAXIS_FFMPEG", raising=False)
    monkeypatch.setattr(exhibits.shutil, "which", lambda name: None)
    monkeypatch.setattr(exhibits.os.path, "exists", lambda path: False)
    with pytest.raises(exhibits.ExhibitToolMissing, match="Chrome"):
        exhibits.chrome()
    with pytest.raises(exhibits.ExhibitToolMissing, match="ffmpeg"):
        exhibits.ffmpeg()
