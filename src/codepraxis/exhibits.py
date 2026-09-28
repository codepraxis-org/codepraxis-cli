"""Helpers for making an interview question's files (its exhibits) from a script.

A good interview question hangs on files the author made: a dashboard screenshot, a
report PDF, a log, a call recording. Generating them from one script
(``entity-src/make_entities.py``) keeps every number consistent across files and lets
the author fix one and rerun. Import from that script:

    from codepraxis.exhibits import write, html_to_png, html_to_pdf, frames_to_video, dialogue_to_audio

Standard library only. The heavy lifting is done by programs found at run time:

- ``html_to_png`` / ``html_to_pdf``: Google Chrome or Chromium (headless).
- ``frames_to_video``: Chrome for the frames, ``ffmpeg`` to join them.
- ``dialogue_to_audio``: a text-to-speech command (``say`` on macOS, ``espeak-ng`` or
  ``espeak`` elsewhere) and ``ffmpeg``.

Each helper raises ``ExhibitToolMissing`` naming what to install when a program is
not there. Charts: draw them with any library (matplotlib works well) and save a PNG
into ``entities/``.

Every image, audio or video file needs ``<file>.description.md`` beside it: the
interviewer reads only that. Put every number, label and relationship the question
depends on in it.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

_CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "chrome",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)

#: macOS voices that sound like different people; pass one per speaker.
MAC_VOICES = {
    "us_female": "Samantha",
    "us_male": "Eddy (English (US))",
    "uk_male": "Daniel",
    "uk_female": "Flo (English (UK))",
    "in_male": "Rishi",
    "ie_female": "Moira",
    "au_female": "Karen",
    "za_female": "Tessa",
}


class ExhibitToolMissing(RuntimeError):
    """A program a helper needs is not installed."""


def _find(candidates, env_var: str | None = None) -> str | None:
    if env_var and os.environ.get(env_var):
        return os.environ[env_var]
    for name in candidates:
        if os.path.isabs(name):
            if os.path.exists(name):
                return name
        elif shutil.which(name):
            return shutil.which(name)
    return None


def chrome() -> str:
    """Path to a headless-capable Chrome or Chromium (``CODEPRAXIS_CHROME`` overrides)."""
    found = _find(_CHROME_CANDIDATES, "CODEPRAXIS_CHROME")
    if not found:
        raise ExhibitToolMissing(
            "Google Chrome or Chromium is needed to render HTML to PNG or PDF. Install it, "
            "or set CODEPRAXIS_CHROME to its path.")
    return found


def ffmpeg() -> str:
    found = _find(("ffmpeg", "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"), "CODEPRAXIS_FFMPEG")
    if not found:
        raise ExhibitToolMissing("ffmpeg is needed for audio and video. Install it (for example "
                                 "`brew install ffmpeg` or `apt install ffmpeg`).")
    return found


def write(path, text: str) -> pathlib.Path:
    """Write a text exhibit (UTF-8), creating folders as needed."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _headless(args) -> None:
    subprocess.run([chrome(), "--headless=new", "--disable-gpu", "--hide-scrollbars", *args],
                   check=True, capture_output=True)


def _html_file(html: str, folder=None) -> pathlib.Path:
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8", dir=folder) as handle:
        handle.write(html)
    return pathlib.Path(handle.name)


def html_to_png(html: str, out, width: int, height: int, scale: int = 2) -> pathlib.Path:
    """A screenshot of an HTML page, ``width`` x ``height`` CSS pixels, at ``scale``.

    Size the window to the content: empty space at the bottom looks unfinished, and
    too small a window clips it. Look at the result before you use it.
    """
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    src = _html_file(html)
    try:
        _headless([f"--force-device-scale-factor={scale}", f"--window-size={width},{height}",
                   f"--screenshot={out.resolve()}", src.resolve().as_uri()])
    finally:
        src.unlink()
    return out


def html_to_pdf(html: str, out) -> pathlib.Path:
    """A text-extractable PDF of an HTML page.

    The interviewer reads a PDF's text, so keep every fact in text, not in pictures.
    Set ``@page { size: A4; margin: 14mm; }`` (or ``A4 landscape``) in the page's CSS
    and ``page-break-after: always`` between pages.
    """
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    src = _html_file(html)
    try:
        _headless(["--no-pdf-header-footer", f"--print-to-pdf={out.resolve()}", src.resolve().as_uri()])
    finally:
        src.unlink()
    return out


def frames_to_video(frames, out, width: int = 1280, height: int = 720) -> pathlib.Path:
    """An .mp4 from HTML frames, each shown for its seconds: a terminal replay, a
    console recording, a dashboard changing.

    ``frames`` is a list of ``(html, seconds)``. Keep it to 20 to 90 seconds and write
    ``<file>.mp4.description.md`` with what happens, with timestamps.
    """
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path(tempfile.mkdtemp())
    try:
        lines = []
        for i, (html, seconds) in enumerate(frames):
            png = work / f"f{i:04d}.png"
            src = _html_file(html, work)
            _headless(["--force-device-scale-factor=1", f"--window-size={width},{height}",
                       f"--screenshot={png}", src.as_uri()])
            lines += [f"file '{png}'", f"duration {seconds}"]
        # The concat demuxer needs the last file listed again for its duration to hold.
        lines.append(f"file '{work / f'f{len(frames) - 1:04d}.png'}'")
        (work / "list.txt").write_text("\n".join(lines) + "\n")
        subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", str(work / "list.txt"), "-vf", "fps=25,format=yuv420p",
                        "-c:v", "libx264", "-movflags", "+faststart", str(out)], check=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return out


def _speak(voice: str | None, text: str, out: pathlib.Path) -> None:
    if sys.platform == "darwin" and shutil.which("say"):
        subprocess.run(["say", *(["-v", voice] if voice else []), "-o", str(out.with_suffix(".aiff")), text],
                       check=True)
        subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(out.with_suffix(".aiff")),
                        str(out)], check=True)
        return
    espeak = shutil.which("espeak-ng") or shutil.which("espeak")
    if not espeak:
        raise ExhibitToolMissing("A text-to-speech command is needed for audio: `say` (macOS) or "
                                 "espeak-ng (`apt install espeak-ng`).")
    subprocess.run([espeak, *(["-v", voice] if voice else []), "-w", str(out), text], check=True)


def dialogue_to_audio(lines, out, pause: float = 0.45) -> pathlib.Path:
    """An .m4a of people speaking in turn: a call, a voice memo, a stand-up.

    ``lines`` is a list of ``(voice, text)``; on macOS a voice is a ``say`` voice name
    (see ``MAC_VOICES``), elsewhere an espeak voice. Write
    ``<file>.m4a.description.md`` with who speaks and the full transcript.
    """
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path(tempfile.mkdtemp())
    try:
        gap = work / "gap.wav"
        subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "anullsrc=r=22050:cl=mono", "-t", str(pause), str(gap)], check=True)
        parts = []
        for i, (voice, text) in enumerate(lines):
            raw = work / f"s{i:03d}.wav"
            _speak(voice, text, raw)
            norm = work / f"n{i:03d}.wav"
            subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(raw), "-ar", "22050",
                            "-ac", "1", str(norm)], check=True)
            parts += [norm, gap]
        (work / "list.txt").write_text("".join(f"file '{p}'\n" for p in parts))
        subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", str(work / "list.txt"), "-c:a", "aac", "-b:a", "64k", str(out)], check=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return out
