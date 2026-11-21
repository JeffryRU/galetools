"""How Gale lays out a Thunderstore package inside a profile. Pure path logic.

Gale strips the 'plugins/' (or 'BepInEx/plugins/') prefix, moves patchers/core to their own folders,
and flattens a single top-level folder ("Mod/Mod.dll" -> "Mod.dll").
"""
from __future__ import annotations

IGNORED_NAMES = {"manifest.json", "icon.png", "readme.md", "changelog.md", "license", "license.md", "license.txt"}
OPTIONAL_SUFFIXES = (".pdb", ".xml", ".mdb")
_PREFIXES = ("plugins/", "BepInEx/plugins/", "patchers/", "BepInEx/patchers/", "core/", "BepInEx/core/",
             "monomod/", "BepInEx/monomod/", "config/", "BepInEx/config/")
_SUBDIR_PREFIXES = (("patchers", ("patchers/", "bepinex/patchers/")),
                    ("plugins", ("plugins/", "bepinex/plugins/")))


def normalise(member: str) -> str:
    return member.replace("\\", "/")


def should_check(member: str) -> bool:
    """False for docs, configs and debug files, which may legitimately be absent."""
    member = normalise(member)
    low = member.lower()
    name = low.rsplit("/", 1)[-1]
    if member.endswith("/") or name in IGNORED_NAMES or low.endswith(OPTIONAL_SUFFIXES):
        return False
    return not (low.startswith("config/") or low.startswith("bepinex/config/"))


def candidate_paths(member: str) -> list[str]:
    """Relative paths (inside a mod folder) where Gale may have placed this zip member."""
    member = normalise(member)
    out = [member]
    for p in _PREFIXES:
        if member.lower().startswith(p.lower()):
            out.append(member[len(p):])
    if "/" in member:
        out.append(member.split("/", 1)[1])
    return out


def restore_target(member: str) -> tuple[str, str]:
    """(subfolder kind, relative path) where a missing member should be written back."""
    member = normalise(member)
    low = member.lower()
    for kind, prefixes in _SUBDIR_PREFIXES:
        for p in prefixes:
            if low.startswith(p):
                return kind, member[len(p):]
    return "plugins", member
