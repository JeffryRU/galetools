"""ProfileRepository adapter: Gale profiles on disk.

Gale keeps each Thunderstore mod in BepInEx/{plugins,patchers,core}/<Owner-Name>/ and marks disabled
files with a '.old' suffix. Locally imported mods keep their own folder name (without "Owner-").
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from ..config import Settings
from ..domain.errors import GaleToolsError
from ..domain.models import InstalledMod

_SUBDIRS = ("plugins", "patchers", "core")
_GENERATED = ("MMHOOK",)  # created by HookGenPatcher, not a mod


class GaleProfileRepository:
    def __init__(self, settings: Settings):
        self.settings = settings

    # ------------------------------------------------------------------ reading

    def list_profiles(self) -> list[str]:
        d = self.settings.profiles_dir
        return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []

    def profile_dir(self, profile: str) -> Path:
        d = self.settings.profiles_dir / profile
        if not d.is_dir():
            raise GaleToolsError(f"No existe el perfil '{profile}'. Perfiles: " + (", ".join(self.list_profiles()) or "(ninguno)"))
        return d

    def installed_mods(self, profile: str) -> list[InstalledMod]:
        root = self.profile_dir(profile) / "BepInEx"
        mods: dict[str, InstalledMod] = {}
        for sub in _SUBDIRS:
            base = root / sub
            if not base.is_dir():
                continue
            for folder in base.iterdir():
                if not folder.is_dir() or folder.name in _GENERATED:
                    continue
                files = [f for f in folder.rglob("*") if f.is_file()]
                if not files:
                    continue
                mod = mods.get(folder.name)
                if mod is None:
                    manifest = _read_manifest(folder / "manifest.json")
                    mod = InstalledMod(
                        full_name=folder.name,
                        version=manifest.get("version_number", "?"),
                        dependencies=list(manifest.get("dependencies", [])),
                        local="-" not in folder.name,
                    )
                    mods[folder.name] = mod
                mod.folders.append(folder)
                code = [f for f in files if ".dll" in f.name.lower()]
                if code and all(f.name.endswith(".old") for f in code):
                    mod.enabled = False
                if sub == "plugins" and any(f.name.lower().endswith(".dll") for f in code):
                    mod.has_plugin_code = True
        if (root / "core" / "BepInEx.dll").is_file() and "bbepis-BepInExPack" not in mods:
            mods["bbepis-BepInExPack"] = InstalledMod("bbepis-BepInExPack", "?", folders=[root / "core"])
        return sorted(mods.values(), key=lambda m: m.full_name.lower())

    def read_log(self, profile: str) -> str | None:
        return self.read_text(self.profile_dir(profile) / "BepInEx" / "LogOutput.log")

    def read_text(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def file_exists(self, mod: InstalledMod, relative: str) -> bool:
        for folder in mod.folders:
            if (folder / relative).is_file() or (folder / (relative + ".old")).is_file():
                return True
        return False

    # ------------------------------------------------------------------ writing

    def write_mod_file(self, mod: InstalledMod, kind: str, relative: str, data: bytes) -> bool:
        folder = next((f for f in mod.folders if f.parent.name == kind), None) \
            or next((f for f in mod.folders if f.parent.name == "plugins"), None)
        if folder is None:
            return False
        dest = (folder / relative).resolve()
        if folder.resolve() not in dest.parents:
            return False  # never write outside the mod's own folder
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return True

    def build_test_profile(self, profile: str, mods: list[InstalledMod], name: str) -> Path:
        """A throw-away copy of the profile with only `mods`. Mod files are hard links (instant, no
        extra space); configs are real copies so tests can never change the user's settings."""
        src = self.profile_dir(profile)
        dst = self.settings.tools_home / "test-profiles" / name
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True)
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, dst / f.name)
        _copy_tree(src / "BepInEx" / "core", dst / "BepInEx" / "core", link=True)
        _copy_tree(src / "BepInEx" / "config", dst / "BepInEx" / "config", link=False)
        _copy_tree(src / "BepInEx" / "plugins" / "MMHOOK", dst / "BepInEx" / "plugins" / "MMHOOK", link=True)
        for mod in mods:
            for folder in mod.folders:
                rel = folder.relative_to(src)
                if rel.parts[:2] != ("BepInEx", "core"):
                    _copy_tree(folder, dst / rel, link=True)
        return dst


def _read_manifest(path: Path) -> dict:
    for candidate in (path, path.with_name(path.name + ".old")):
        if candidate.is_file():
            try:
                return json.loads(candidate.read_text(encoding="utf-8-sig"))
            except (json.JSONDecodeError, OSError):
                return {}
    return {}


def _copy_tree(src: Path, dst: Path, link: bool) -> None:
    if not src.is_dir():
        return
    for f in src.rglob("*"):
        if not f.is_file():
            continue
        target = dst / f.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        if link:
            try:
                os.link(f, target)
                continue
            except OSError:
                pass
        shutil.copy2(f, target)
