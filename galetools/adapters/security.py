"""Decompiler (ILSpy) and MalwareScanner (Windows Defender) adapters, plus a JSON cache."""
from __future__ import annotations

import json
import shutil
import struct
import subprocess
from pathlib import Path

from ..config import Settings
from ..domain.errors import GaleToolsError


class IlSpyDecompiler:
    """Uses ilspycmd, installed into the tool folder on first use (`dotnet tool install`)."""

    def __init__(self, settings: Settings):
        self.tools = settings.tools_home / "tools"

    def _exe(self) -> Path:
        found = sorted(self.tools.glob("ilspycmd*"))
        if found:
            return found[0]
        if not shutil.which("dotnet"):
            raise GaleToolsError("Hace falta el SDK de .NET (dotnet) para decompilar.")
        subprocess.run(["dotnet", "tool", "install", "ilspycmd", "--tool-path", str(self.tools)],
                       check=True, capture_output=True, text=True)
        found = sorted(self.tools.glob("ilspycmd*"))
        if not found:
            raise GaleToolsError("No se pudo instalar ilspycmd.")
        return found[0]

    def is_managed(self, path: Path) -> bool | None:
        try:
            data = path.read_bytes()
            if data[:2] != b"MZ":
                return None
            pe = struct.unpack_from("<I", data, 0x3C)[0]
            if data[pe:pe + 4] != b"PE\0\0":
                return None
            magic = struct.unpack_from("<H", data, pe + 24)[0]
            data_dirs = pe + 24 + (96 if magic == 0x10B else 112)
            clr_rva = struct.unpack_from("<I", data, data_dirs + 14 * 8)[0]  # CLR runtime header
            return clr_rva != 0
        except (OSError, struct.error):
            return None

    def decompile(self, dll: Path, out_dir: Path) -> str | None:
        r = subprocess.run([str(self._exe()), "-p", "-o", str(out_dir), str(dll)],
                           capture_output=True, text=True, errors="replace")
        if r.returncode != 0 and not any(out_dir.rglob("*.cs")):
            return (r.stderr or r.stdout).strip()[:200] or f"código {r.returncode}"
        return None


class DefenderScanner:
    def scan(self, path: Path) -> str:
        platform = Path(r"C:\ProgramData\Microsoft\Windows Defender\Platform")
        candidates = sorted(platform.glob("*/MpCmdRun.exe"), reverse=True) if platform.is_dir() else []
        exe = candidates[0] if candidates else Path(r"C:\Program Files\Windows Defender\MpCmdRun.exe")
        if not exe.is_file():
            return "no disponible"
        r = subprocess.run([str(exe), "-Scan", "-ScanType", "3", "-File", str(path), "-DisableRemediation"],
                           capture_output=True, text=True, errors="replace")
        lines = [l.strip() for l in r.stdout.splitlines() if "threat" in l.lower() or "amenaza" in l.lower()]
        if lines:
            return lines[-1]
        rest = r.stdout.strip().splitlines()
        return "error al escanear: " + (rest[-1] if rest else f"código {r.returncode}")


class JsonFileCache:
    def __init__(self, settings: Settings):
        self.path = settings.tools_home / "cache" / "kv.json"

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def get(self, key: str) -> dict | None:
        return self._load().get(key)

    def put(self, key: str, value: dict) -> None:
        data = self._load()
        data[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
