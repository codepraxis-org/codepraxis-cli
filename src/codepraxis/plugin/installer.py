"""Install the CodePraxis authoring tools as a Claude Code plugin.

Writes a self-contained local marketplace into the user's project, so authors
running Claude Code get the pack contract, a scaffolding command, and a
validate-and-fix loop without having to explain any of it.

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
MARKETPLACE_NAME = "codepraxis-local"


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

    # Marketplace manifest at the root; the plugin itself one level down, which
    # is the layout `/plugin marketplace add <dir>` expects.
    marketplace_dir = root / ".claude-plugin"
    marketplace_dir.mkdir(parents=True, exist_ok=True)
    marketplace = marketplace_dir / "marketplace.json"
    marketplace.write_bytes((templates / "marketplace.json").read_bytes())
    written.append(marketplace)

    plugin_root = root / PLUGIN_NAME
    plugin_manifest_dir = plugin_root / ".claude-plugin"
    plugin_manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = plugin_manifest_dir / "plugin.json"
    manifest.write_bytes((templates / "plugin.json").read_bytes())
    written.append(manifest)

    for name in ("commands", "skills"):
        _copy_tree(templates / name, plugin_root / name, written)

    return InstallResult(root=root, files=written, overwritten=existed)


def describe(result: InstallResult) -> str:
    """The instructions an author needs after a successful install."""
    relative = result.root
    with contextlib.suppress(ValueError):
        relative = result.root.relative_to(Path.cwd())

    return "\n".join(
        [
            f"Installed the Claude Code plugin into {relative}",
            f"  {len(result.files)} files",
            "",
            "Enable it in Claude Code:",
            "",
            f"  /plugin marketplace add {relative}",
            f"  /plugin install {PLUGIN_NAME}@{MARKETPLACE_NAME}",
            "",
            "Then:",
            "",
            "  /codepraxis:new    scaffold a pack from a description",
            "  /codepraxis:validate    validate a pack and fix what fails",
            "",
            "The pack-authoring skill loads automatically when Claude touches a pack.",
        ]
    )
