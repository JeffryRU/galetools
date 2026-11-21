"""Small Windows helpers shared by adapters: processes, Steam location, clock."""
from __future__ import annotations

import csv
import io
import re
import subprocess
import time
from pathlib import Path


def pids_of(image_name: str) -> set[int]:
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True, errors="replace").stdout
    pids = set()
    for row in csv.reader(io.StringIO(out)):
        if len(row) > 1 and row[0].lower() == image_name.lower() and row[1].isdigit():
            pids.add(int(row[1]))
    return pids


def kill(pids: set[int]) -> None:
    for pid in pids:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)


def steam_dir() -> Path:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            return Path(winreg.QueryValueEx(key, "SteamPath")[0])
    except OSError:
        return Path(r"C:\Program Files (x86)\Steam")


def steam_libraries() -> list[Path]:
    libs = [steam_dir()]
    vdf = steam_dir() / "steamapps" / "libraryfolders.vdf"
    if vdf.is_file():
        text = vdf.read_text(encoding="utf-8", errors="replace")
        libs += [Path(p.replace("\\\\", "\\")) for p in re.findall(r'"path"\s+"([^"]+)"', text)]
    return libs


class SystemClock:
    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
