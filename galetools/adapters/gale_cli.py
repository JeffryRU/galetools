"""ModManager adapter: drives Gale through its own command line and ror2mm:// deep links.

Gale is single-instance, so a second gale.exe forwards its arguments to the open window.
This adapter never edits Gale's database.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from ..config import Settings
from ..domain.errors import GaleToolsError
from ..domain.models import PackageRef
from .windows import pids_of


class GaleCli:
    def __init__(self, settings: Settings):
        self.settings = settings

    def exe(self) -> Path:
        candidates = [
            self.settings.gale_exe,
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Gale" / "gale.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Gale" / "gale.exe",
        ]
        for c in candidates:
            if c and c.is_file():
                return c
        raise GaleToolsError("No encuentro gale.exe. Define la variable de entorno GALE_EXE con su ruta.")

    def _run(self, args: list[str], wait: float) -> None:
        flags = getattr(subprocess, "DETACHED_PROCESS", 0)
        subprocess.Popen([str(self.exe()), *args], close_fds=True, creationflags=flags)
        time.sleep(wait)

    def is_running(self) -> bool:
        return bool(pids_of("gale.exe"))

    def select_profile(self, profile: str) -> None:
        extra = [] if self.is_running() else ["--no-gui"]
        self._run(["--game", self.settings.game_slug, "--profile", profile, *extra], wait=2.0)

    def install_package(self, ref: PackageRef) -> None:
        if not ref.version:
            raise GaleToolsError("Hace falta una versión concreta para instalar.")
        if not self.is_running():
            self._run([], wait=8.0)  # let Gale open and fetch Thunderstore before handling the link
        self._run([f"ror2mm://v1/install/thunderstore.io/{ref.owner}/{ref.name}/{ref.version}/"], wait=3.0)

    def install_local(self, path: Path, profile: str | None) -> None:
        args = ["--game", self.settings.game_slug]
        if profile:
            args += ["--profile", profile]
        self._run(args + ["--install", str(path)], wait=4.0)

    def launch(self, profile: str | None, vanilla: bool) -> None:
        args = ["--game", self.settings.game_slug]
        if profile:
            args += ["--profile", profile]
        args.append("--launch")
        if vanilla:
            args.append("--vanilla")
        self._run(args, wait=2.0)
