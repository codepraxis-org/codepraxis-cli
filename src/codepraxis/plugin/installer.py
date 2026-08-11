"""Install the CodePraxis authoring tools as a Claude Code plugin.

**This is the fallback, not the normal path.** The plugin is served straight
from the public repository, so almost everyone should add it as a hosted
marketplace and never touch this command — that works identically on every
machine, needs no path, and picks up prompt changes without a CLI upgrade.

Installing locally is for working offline, or for editing the prompts and
trying the result before it is merged.

The templates ship inside the wheel and are copied out verbatim; nothing is
fetched from the network.
"""

from __future__ import annotations

import contextlib
import shutil
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from ..errors import PraxisError

#: Marketplace root, relative to the project. Kept out of `.claude/` so it is a
#: visible, reviewable part of the repo rather than hidden editor state.
INSTALL_DIR = Path(".codepraxis") / "claude-plugin"

PLUGIN_NAME = "codepraxis"

#: The hosted marketplace: the repository itself, which carries a
#: `.claude-plugin/marketplace.json` at its root.
HOSTED_MARKETPLACE = "codepraxis-org/codepraxis-cli"
HOSTED_NAME = "codepraxis"

#: The local one is named differently on purpose. Marketplace names are global
#: in Claude Code, so sharing a name would mean a local install silently
#: displaced the hosted one — or refused to be added at all.
LOCAL_NAME = "codepraxis-local"


@dataclass(frozen=True)
class InstallResult:
    root: Path
    files: list[Path]
    overwritten: bool


def _templates():
    return resources.files("codepraxis.plugin") / "templates"


def _copy_tree(source, destination: Path, written: list[Path]) -> None:
    """Copy a traversable template tree onto disk.

    Uses importlib.resources rather than __file__ so this works from a wheel,
    a zip, or an editable install.
    """
    destination.mkdir(parents=True, exist_ok=True)
    for entry in source.iterdir():
        target = destination / entry.name
        if entry.is_dir():
            _copy_tree(entry, target, written)
        else:
            target.write_bytes(entry.read_bytes())
            written.append(target)


def install(project_root: Path, force: bool = False) -> InstallResult:
    """Materialise the plugin under ``project_root``.

    Refuses to clobber an existing install unless ``force`` — the author may
    have edited the commands, and silently reverting that is worse than failing.
    """
    root = (project_root / INSTALL_DIR).resolve()
    existed = root.exists()

    if existed and not force:
        raise PraxisError(
            f"{root} already exists. Re-run with --force to overwrite it "
            f"(any local edits to the commands will be lost)."
        )

    if existed:
        shutil.rmtree(root)

    templates = _templates()
    written: list[Path] = []

    # The layout mirrors the repository exactly: a marketplace manifest at the
    # root, and the plugin beside it in ./plugin. Keeping the two identical
    # means a prompt edited here can be moved upstream unchanged.
    marketplace_dir = root / ".claude-plugin"
    marketplace_dir.mkdir(parents=True, exist_ok=True)
    marketplace = marketplace_dir / "marketplace.json"
    marketplace.write_bytes((templates / "marketplace.json").read_bytes())
    written.append(marketplace)

    _copy_tree(templates / "plugin", root / "plugin", written)

    return InstallResult(root=root, files=written, overwritten=existed)


def describe(result: InstallResult) -> str:
    """The instructions an author needs after a successful install."""
    relative = result.root
    with contextlib.suppress(ValueError):
        relative = result.root.relative_to(Path.cwd())

    # A relative path, prefixed with "./". A bare `foo/bar` is read as GitHub
    # owner/repo shorthand and Claude Code tries to clone it; "./" cannot be
    # parsed that way, and unlike an absolute path it is the same string on
    # every machine.
    source = f"./{relative.as_posix()}" if not relative.is_absolute() else relative.as_posix()

    return "\n".join(
        [
            f"Installed the local plugin into {relative}",
            f"  {len(result.files)} files",
            "",
            "Enable it in Claude Code:",
            "",
            f"  /plugin marketplace add {source}",
            f"  /plugin install {PLUGIN_NAME}@{LOCAL_NAME}",
            "",
            "Then:",
            "",
            "  /codepraxis:new         design and build a question",
            "  /codepraxis:validate    check one and fix what fails",
            "",
            "Most people do not need this. The hosted plugin works the same on",
            "every machine and updates itself:",
            "",
            f"  /plugin marketplace add {HOSTED_MARKETPLACE}",
            f"  /plugin install {PLUGIN_NAME}@{HOSTED_NAME}",
        ]
    )
