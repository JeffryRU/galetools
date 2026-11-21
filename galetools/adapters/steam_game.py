"""GameRunner adapter: starts Risk of Rain 2 through Steam with BepInEx pointed at a given profile.

Uses the same doorstop 4 arguments Gale uses, so no files of the game folder are modified.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import Settings
from ..domain.errors import GaleToolsError
from . import windows

EXE = "Risk of Rain 2.exe"


class SteamGameRunner:
    def __init__(self, settings: Settings):
        self.settings = settings

    def game_dir(self) -> Path:
        if self.settings.game_dir and (self.settings.game_dir / EXE).is_file():
            return self.settings.game_dir
        for lib in windows.steam_libraries():
            d = lib / "steamapps" / "common" / "Risk of Rain 2"
            if (d / EXE).is_file():
                return d
        raise GaleToolsError("No encuentro Risk of Rain 2. Define ROR2_DIR con la carpeta del juego.")

    def build_id(self) -> str:
        dll = self.game_dir() / "Risk of Rain 2_Data" / "Managed" / "RoR2.dll"
        try:
            st = dll.stat()
            return f"{st.st_size}-{int(st.st_mtime)}"
        except OSError:
            return "desconocido"

    def running_pids(self) -> set[int]:
        return windows.pids_of(EXE)

    def start_with_profile(self, profile_dir: Path) -> None:
        if not (self.game_dir() / "winhttp.dll").is_file():
            raise GaleToolsError("Falta winhttp.dll (doorstop) en la carpeta del juego. Lanza el juego una vez con mods desde Gale.")
        preloader = profile_dir / "BepInEx" / "core" / "BepInEx.Preloader.dll"
        steam = windows.steam_dir() / "steam.exe"
        subprocess.Popen([str(steam), "-applaunch", str(self.settings.steam_app_id),
                          "--doorstop-enabled", "true", "--doorstop-target-assembly", str(preloader)])

    def kill(self, pids: set[int]) -> None:
        windows.kill(pids)
